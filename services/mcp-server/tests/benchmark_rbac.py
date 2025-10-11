#!/usr/bin/env python3
"""
RBAC Performance Benchmark
Target: RPS 100+, 95p latency < 100ms, error rate < 1%

Usage:
    python3 tests/benchmark_rbac.py
    python3 tests/benchmark_rbac.py --duration 60 --rps 100
"""

import asyncio
import httpx
import time
import statistics
import csv
import argparse
from pathlib import Path
from typing import List, Dict

BASE_URL = "http://localhost:8020"
DEFAULT_DURATION = 60  # seconds
DEFAULT_RPS = 100

# Test scenarios: cycle through different users and tools
TEST_SCENARIOS = [
    {"user_id": "dev_user", "tool_name": "list_files", "args": {}},
    {"user_id": "dev_user", "tool_name": "read_file", "args": {"file_path": "/tmp/test.txt"}},
    {"user_id": "guest_user", "tool_name": "git_status", "args": {}},
    {"user_id": "guest_user", "tool_name": "git_log", "args": {"max_count": 5}},
    {"user_id": "admin_user", "tool_name": "get_current_model", "args": {}},
]


async def benchmark_tool_call(client: httpx.AsyncClient, scenario: Dict) -> Dict:
    """
    Execute single tool call with timing

    Returns:
        dict: {success: bool, latency: float (ms), status: int, error: str}
    """
    start = time.perf_counter()

    try:
        response = await client.post(
            f"{BASE_URL}/tools/{scenario['tool_name']}/call",
            headers={"X-User-ID": scenario["user_id"]},
            json={"arguments": scenario["args"]},
            timeout=5.0
        )
        latency = (time.perf_counter() - start) * 1000  # convert to ms

        return {
            "success": response.status_code < 500,  # 4xx are expected (permission denied)
            "latency": latency,
            "status": response.status_code,
            "error": None
        }
    except httpx.TimeoutException as e:
        latency = (time.perf_counter() - start) * 1000
        return {
            "success": False,
            "latency": latency,
            "status": 0,
            "error": "Timeout"
        }
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return {
            "success": False,
            "latency": latency,
            "status": 0,
            "error": str(e)
        }


async def run_benchmark(duration: int, target_rps: int) -> List[Dict]:
    """
    Run benchmark for specified duration at target RPS

    Args:
        duration: Test duration in seconds
        target_rps: Target requests per second

    Returns:
        List of result dictionaries
    """
    results = []
    start_time = time.time()
    scenario_index = 0

    print(f"Starting benchmark: {target_rps} RPS for {duration}s")
    print(f"Test scenarios: {len(TEST_SCENARIOS)} scenarios")
    print("="*60)

    async with httpx.AsyncClient() as client:
        # Warmup: single request to each scenario
        print("Warmup...")
        for scenario in TEST_SCENARIOS:
            await benchmark_tool_call(client, scenario)
        print("✓ Warmup complete\n")

        # Main benchmark loop
        print("Running benchmark...")
        while time.time() - start_time < duration:
            tasks = []

            # Create target_rps tasks for this second
            for _ in range(target_rps):
                scenario = TEST_SCENARIOS[scenario_index % len(TEST_SCENARIOS)]
                scenario_index += 1
                tasks.append(benchmark_tool_call(client, scenario))

            # Execute all tasks concurrently
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out exceptions and add valid results
            for result in batch_results:
                if isinstance(result, dict):
                    results.append(result)
                else:
                    results.append({
                        "success": False,
                        "latency": 0,
                        "status": 0,
                        "error": str(result)
                    })

            # Progress indicator
            elapsed = time.time() - start_time
            if int(elapsed) % 10 == 0 and len(results) > 0:
                recent = results[-target_rps*10:] if len(results) >= target_rps*10 else results
                avg_latency = statistics.mean([r["latency"] for r in recent if r["latency"] > 0])
                print(f"  {int(elapsed)}s: {len(results)} requests, avg latency: {avg_latency:.2f}ms")

            # Wait for next second (maintain RPS)
            elapsed = time.time() - start_time
            sleep_time = max(0, 1 - (elapsed % 1))
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    actual_duration = time.time() - start_time
    print(f"\n✓ Benchmark complete: {len(results)} requests in {actual_duration:.2f}s")

    return results


def analyze_results(results: List[Dict], duration: int, output_csv: Path) -> Dict:
    """
    Analyze benchmark results and save to CSV

    Args:
        results: List of result dictionaries
        duration: Actual test duration
        output_csv: Path to output CSV file

    Returns:
        Dictionary of statistics
    """
    # Filter valid latencies
    latencies = [r["latency"] for r in results if r.get("latency") and r["latency"] > 0]

    if not latencies:
        print("⚠️  No valid latency data collected")
        return {}

    successes = [r for r in results if r.get("success")]
    errors = [r for r in results if not r.get("success")]

    # Calculate statistics
    stats = {
        "duration_sec": duration,
        "total_requests": len(results),
        "successful": len(successes),
        "errors": len(errors),
        "error_rate_pct": (len(errors) / len(results) * 100) if results else 0,
        "rps": len(results) / duration,
        "avg_latency_ms": statistics.mean(latencies),
        "median_latency_ms": statistics.median(latencies),
        "min_latency_ms": min(latencies),
        "max_latency_ms": max(latencies),
        "p95_latency_ms": statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else statistics.quantiles(latencies, n=len(latencies))[int(len(latencies)*0.95)] if len(latencies) > 1 else latencies[0],
        "p99_latency_ms": statistics.quantiles(latencies, n=100)[98] if len(latencies) >= 100 else statistics.quantiles(latencies, n=len(latencies))[int(len(latencies)*0.99)] if len(latencies) > 1 else latencies[0],
    }

    # Save to CSV
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=stats.keys())
        writer.writeheader()
        writer.writerow(stats)

    print(f"\n{'='*60}")
    print(f"Benchmark Results")
    print(f"{'='*60}")
    print(f"Duration:             {stats['duration_sec']:8.2f} sec")
    print(f"Total Requests:       {stats['total_requests']:8}")
    print(f"Successful:           {stats['successful']:8}")
    print(f"Errors:               {stats['errors']:8}")
    print(f"Error Rate:           {stats['error_rate_pct']:8.2f} %")
    print(f"RPS:                  {stats['rps']:8.2f}")
    print(f"{'='*60}")
    print(f"Latency (ms):")
    print(f"  Min:                {stats['min_latency_ms']:8.2f}")
    print(f"  Average:            {stats['avg_latency_ms']:8.2f}")
    print(f"  Median:             {stats['median_latency_ms']:8.2f}")
    print(f"  95th percentile:    {stats['p95_latency_ms']:8.2f}")
    print(f"  99th percentile:    {stats['p99_latency_ms']:8.2f}")
    print(f"  Max:                {stats['max_latency_ms']:8.2f}")
    print(f"{'='*60}\n")

    # Check if goals met
    goals = {
        "RPS >= 100": stats["rps"] >= 100,
        "95p latency < 100ms": stats["p95_latency_ms"] < 100,
        "Error rate < 1%": stats["error_rate_pct"] < 1.0
    }

    goals_met = all(goals.values())

    print(f"Performance Goals:")
    for goal, met in goals.items():
        status = "✓" if met else "✗"
        print(f"  {status} {goal}: {'PASS' if met else 'FAIL'}")

    print(f"\n{'='*60}")
    print(f"Overall: {'✓ ALL GOALS MET' if goals_met else '✗ SOME GOALS NOT MET'}")
    print(f"{'='*60}\n")

    print(f"Results saved to: {output_csv}")

    return stats


async def main():
    parser = argparse.ArgumentParser(description="RBAC Performance Benchmark")
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION, help="Test duration in seconds")
    parser.add_argument("--rps", type=int, default=DEFAULT_RPS, help="Target requests per second")
    parser.add_argument("--output", type=str, help="Output CSV file path")

    args = parser.parse_args()

    # Default output path: repo_root/data/rbac_benchmark.csv
    if args.output:
        output_csv = Path(args.output)
    else:
        # Resolve path relative to repository root
        script_path = Path(__file__).resolve()
        repo_root = script_path.parents[2]  # services/mcp-server/tests -> repo root
        output_csv = repo_root / "data" / "rbac_benchmark.csv"

    print(f"\nRBAC Performance Benchmark")
    print(f"{'='*60}")
    print(f"Target URL:      {BASE_URL}")
    print(f"Duration:        {args.duration} seconds")
    print(f"Target RPS:      {args.rps}")
    print(f"Output:          {output_csv}")
    print(f"{'='*60}\n")

    # Check if server is accessible
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/health", timeout=5.0)
            print(f"✓ Server is accessible (status: {response.status_code})\n")
    except Exception as e:
        print(f"⚠️  Server may not be accessible: {e}")
        print(f"   Make sure MCP server is running on {BASE_URL}\n")
        return 1

    # Run benchmark
    results = await run_benchmark(args.duration, args.rps)

    if not results:
        print("✗ No results collected")
        return 1

    # Analyze results
    stats = analyze_results(results, args.duration, output_csv)

    # Return exit code based on goals
    goals_met = (
        stats.get("rps", 0) >= 100 and
        stats.get("p95_latency_ms", float('inf')) < 100 and
        stats.get("error_rate_pct", 100) < 1.0
    )

    return 0 if goals_met else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
