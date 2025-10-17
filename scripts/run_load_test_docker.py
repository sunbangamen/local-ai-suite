#!/usr/bin/env python3
"""
Phase 3 Load Test Executor using Docker
Runs Locust load tests in Docker containers and extracts results
"""

import subprocess
import sys
import time
import json
import os
from pathlib import Path
from datetime import datetime


def ensure_results_dir():
    """Ensure tests/load directory exists"""
    Path("tests/load").mkdir(parents=True, exist_ok=True)


def run_locust_in_docker(
    scenario_name: str, host: str, user_class: str, users: int, spawn_rate: int, run_time: str
) -> dict:
    """
    Run a Locust load test in Docker and return results

    Args:
        scenario_name: Name of the scenario (for logging)
        host: Target host URL
        user_class: Locust user class to run
        users: Number of users
        spawn_rate: Rate at which to spawn users
        run_time: Duration to run test

    Returns:
        dict: Test results metadata
    """

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file = f"load_results_{scenario_name}_{timestamp}"
    output_dir = "/mnt/e/worktree/issue-24/tests/load"

    print(f"\n{'='*70}")
    print(f"🚀 Starting {scenario_name} Load Test (Docker)")
    print(f"{'='*70}")
    print(f"  Host: {host}")
    print(f"  Users: {users}")
    print(f"  Spawn Rate: {spawn_rate} users/sec")
    print(f"  Duration: {run_time}")
    print(f"  Results: {csv_file}_stats.csv")

    # Run Locust in a temporary Docker container
    cmd = [
        "docker",
        "run",
        "--rm",
        "--network",
        "docker_default",  # Use the same network as Phase 2 stack
        "-v",
        f"{output_dir}:/results",
        "-v",
        f"/mnt/e/worktree/issue-24/tests/load:/locust",
        "locustio/locust:latest",
        "-f",
        "/locust/locustfile.py",
        user_class,
        "--host",
        host,
        "--users",
        str(users),
        "--spawn-rate",
        str(spawn_rate),
        "--run-time",
        run_time,
        "--csv",
        f"/results/{csv_file}",
        "--headless",
        "--csv-full-history",
    ]

    try:
        print(f"\n  Executing: docker run locustio/locust:latest ...")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        # Check if CSV file was created
        csv_path = Path(output_dir) / f"{csv_file}_stats.csv"
        if csv_path.exists():
            print(f"\n✅ {scenario_name} test completed successfully")
            print(f"   CSV Results: {csv_file}_stats.csv")
            return {
                "scenario": scenario_name,
                "status": "completed",
                "timestamp": timestamp,
                "csv_file": f"{csv_file}_stats.csv",
                "users": users,
                "spawn_rate": spawn_rate,
                "run_time": run_time,
            }
        else:
            print(f"\n⚠️  {scenario_name} test may have issues - CSV file not created")
            print(f"   stdout: {result.stdout[:200]}")
            print(f"   stderr: {result.stderr[:200]}")
            return {
                "scenario": scenario_name,
                "status": "partial",
                "timestamp": timestamp,
                "error": "CSV file not created",
            }

    except subprocess.CalledProcessError as e:
        print(f"\n❌ {scenario_name} test failed with error:")
        print(f"   Return code: {e.returncode}")
        print(f"   stderr: {e.stderr[:300] if e.stderr else 'N/A'}")
        return {
            "scenario": scenario_name,
            "status": "failed",
            "timestamp": timestamp,
            "error": str(e),
        }
    except Exception as e:
        print(f"\n❌ {scenario_name} test failed with exception:")
        print(f"   {str(e)}")
        return {
            "scenario": scenario_name,
            "status": "failed",
            "timestamp": timestamp,
            "error": str(e),
        }


def main():
    """Run Phase 3 load test suite"""

    print("\n" + "=" * 70)
    print("Phase 3 Load Test Execution (Docker) - Issue #24")
    print("=" * 70)

    ensure_results_dir()

    results = []

    # Test 1: Baseline (1 user, 2 minutes)
    print("\n[PHASE 3.1] Baseline Test (1 user, 2 minutes)")
    baseline = run_locust_in_docker(
        scenario_name="baseline",
        host="http://api-gateway:8000",
        user_class="APIGatewayUser",
        users=1,
        spawn_rate=1,
        run_time="2m",
    )
    results.append(baseline)

    if baseline["status"] not in ["completed", "partial"]:
        print("\n⚠️  Baseline test failed. Attempting to continue...")

    # Wait between tests
    print("\n⏳ Waiting 30 seconds before next test...")
    time.sleep(30)

    # Test 2: API Gateway Progressive (10→50→100 users, 15 minutes total)
    print("\n[PHASE 3.2] API Gateway Progressive Load (target: 100 users, duration: 15m)")
    api_test = run_locust_in_docker(
        scenario_name="api_gateway",
        host="http://api-gateway:8000",
        user_class="APIGatewayUser",
        users=100,
        spawn_rate=10,
        run_time="15m",
    )
    results.append(api_test)

    if api_test["status"] in ["completed", "partial"]:
        print("\n⏳ Waiting 30 seconds before next test...")
        time.sleep(30)

    # Test 3: RAG Service Progressive (5→25→50 users, 15 minutes total)
    print("\n[PHASE 3.3] RAG Service Progressive Load (target: 50 users, duration: 15m)")
    rag_test = run_locust_in_docker(
        scenario_name="rag_service",
        host="http://rag:8002",
        user_class="RAGServiceUser",
        users=50,
        spawn_rate=5,
        run_time="15m",
    )
    results.append(rag_test)

    if rag_test["status"] in ["completed", "partial"]:
        print("\n⏳ Waiting 30 seconds before next test...")
        time.sleep(30)

    # Test 4: MCP Server Progressive (5→20 users, 10 minutes total)
    print("\n[PHASE 3.4] MCP Server Progressive Load (target: 20 users, duration: 10m)")
    mcp_test = run_locust_in_docker(
        scenario_name="mcp_server",
        host="http://mcp:8020",
        user_class="MCPServerUser",
        users=20,
        spawn_rate=5,
        run_time="10m",
    )
    results.append(mcp_test)

    # Summary
    print("\n" + "=" * 70)
    print("Phase 3 Load Test Summary")
    print("=" * 70)

    completed = sum(1 for r in results if r["status"] == "completed")
    partial = sum(1 for r in results if r["status"] == "partial")
    failed = sum(1 for r in results if r["status"] == "failed")

    print(f"\n✅ Completed: {completed}/{len(results)}")
    print(f"⚠️  Partial: {partial}/{len(results)}")
    print(f"❌ Failed: {failed}/{len(results)}")

    for result in results:
        if result["status"] == "completed":
            status_icon = "✅"
        elif result["status"] == "partial":
            status_icon = "⚠️ "
        else:
            status_icon = "❌"

        print(f"{status_icon} {result['scenario']}: {result['status']}")
        if "csv_file" in result:
            print(f"   → {result['csv_file']}")

    # Save results metadata
    metadata_file = "tests/load/test_execution_metadata.json"
    with open(metadata_file, "w") as f:
        json.dump(
            {
                "execution_time": datetime.now().isoformat(),
                "total_tests": len(results),
                "completed": completed,
                "partial": partial,
                "failed": failed,
                "results": results,
            },
            f,
            indent=2,
        )

    print(f"\n📊 Metadata saved: {metadata_file}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
