#!/usr/bin/env python3
"""
Phase 3 Load Test Executor
Runs Locust load tests with different scenarios and saves results
"""

import subprocess
import sys
import time
import json
from pathlib import Path
from datetime import datetime


def run_locust_test(
    scenario_name: str,
    host: str,
    user_class: str,
    users: int,
    spawn_rate: int,
    run_time: str,
    csv_prefix: str = "load_results"
) -> dict:
    """
    Run a Locust load test and return results

    Args:
        scenario_name: Name of the scenario (for logging)
        host: Target host URL (e.g., http://localhost:8000)
        user_class: Locust user class to run (e.g., APIGatewayUser)
        users: Number of users to spawn
        spawn_rate: Rate at which to spawn users
        run_time: Duration to run test (e.g., "2m", "5m")
        csv_prefix: Prefix for CSV output files

    Returns:
        dict: Test results metadata
    """

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file = f"tests/load/{csv_prefix}_{scenario_name}_{timestamp}"

    print(f"\n{'='*70}")
    print(f"🚀 Starting {scenario_name} Load Test")
    print(f"{'='*70}")
    print(f"  Host: {host}")
    print(f"  Users: {users}")
    print(f"  Spawn Rate: {spawn_rate} users/sec")
    print(f"  Duration: {run_time}")
    print(f"  Results: {csv_file}.csv")

    cmd = [
        "python3", "-m", "locust",
        "-f", "tests/load/locustfile.py",
        user_class,
        "--host", host,
        "--users", str(users),
        "--spawn-rate", str(spawn_rate),
        "--run-time", run_time,
        "--csv", csv_file,
        "--headless",
        "--csv-full-history"
    ]

    try:
        result = subprocess.run(cmd, cwd="/mnt/e/worktree/issue-24", check=True)

        print(f"\n✅ {scenario_name} test completed successfully")
        print(f"   CSV Results: {csv_file}_stats.csv")

        return {
            "scenario": scenario_name,
            "status": "completed",
            "timestamp": timestamp,
            "csv_file": f"{csv_file}_stats.csv",
            "users": users,
            "spawn_rate": spawn_rate,
            "run_time": run_time
        }

    except subprocess.CalledProcessError as e:
        print(f"\n❌ {scenario_name} test failed with error:")
        print(f"   {str(e)}")
        return {
            "scenario": scenario_name,
            "status": "failed",
            "timestamp": timestamp,
            "error": str(e)
        }


def main():
    """Run Phase 3 load test suite"""

    print("\n" + "="*70)
    print("Phase 3 Load Test Execution - Issue #24")
    print("="*70)

    results = []

    # Test 1: Baseline (1 user, 2 minutes)
    print("\n[PHASE 3.1] Baseline Test (1 user, 2 minutes)")
    baseline = run_locust_test(
        scenario_name="baseline",
        host="http://localhost:8000",
        user_class="APIGatewayUser",
        users=1,
        spawn_rate=1,
        run_time="2m"
    )
    results.append(baseline)

    if baseline["status"] != "completed":
        print("\n⚠️  Baseline test failed. Aborting remaining tests.")
        return 1

    # Wait between tests
    print("\n⏳ Waiting 30 seconds before next test...")
    time.sleep(30)

    # Test 2: API Gateway Progressive (10→50→100 users, 15 minutes total)
    print("\n[PHASE 3.2] API Gateway Progressive Load (10→50→100 users, 15 minutes)")
    api_test = run_locust_test(
        scenario_name="api_gateway",
        host="http://localhost:8000",
        user_class="APIGatewayUser",
        users=100,  # Final target
        spawn_rate=10,  # Progressive ramping
        run_time="15m"
    )
    results.append(api_test)

    if api_test["status"] != "completed":
        print("\n⚠️  API Gateway test failed.")
    else:
        print("\n⏳ Waiting 30 seconds before next test...")
        time.sleep(30)

    # Test 3: RAG Service Progressive (5→25→50 users, 15 minutes total)
    print("\n[PHASE 3.3] RAG Service Progressive Load (5→25→50 users, 15 minutes)")
    rag_test = run_locust_test(
        scenario_name="rag_service",
        host="http://localhost:8002",
        user_class="RAGServiceUser",
        users=50,  # Final target
        spawn_rate=5,  # Progressive ramping
        run_time="15m"
    )
    results.append(rag_test)

    if rag_test["status"] != "completed":
        print("\n⚠️  RAG Service test failed.")
    else:
        print("\n⏳ Waiting 30 seconds before next test...")
        time.sleep(30)

    # Test 4: MCP Server Progressive (5→20 users, 10 minutes total)
    print("\n[PHASE 3.4] MCP Server Progressive Load (5→20 users, 10 minutes)")
    mcp_test = run_locust_test(
        scenario_name="mcp_server",
        host="http://localhost:8020",
        user_class="MCPServerUser",
        users=20,  # Final target
        spawn_rate=5,  # Progressive ramping
        run_time="10m"
    )
    results.append(mcp_test)

    # Summary
    print("\n" + "="*70)
    print("Phase 3 Load Test Summary")
    print("="*70)

    completed = sum(1 for r in results if r["status"] == "completed")
    failed = sum(1 for r in results if r["status"] == "failed")

    print(f"\n✅ Completed: {completed}/{len(results)}")
    print(f"❌ Failed: {failed}/{len(results)}")

    for result in results:
        status_icon = "✅" if result["status"] == "completed" else "❌"
        print(f"{status_icon} {result['scenario']}: {result['status']}")
        if result["status"] == "completed":
            print(f"   → {result['csv_file']}")

    # Save results metadata
    metadata_file = "tests/load/test_execution_metadata.json"
    with open(metadata_file, 'w') as f:
        json.dump({
            "execution_time": datetime.now().isoformat(),
            "total_tests": len(results),
            "completed": completed,
            "failed": failed,
            "results": results
        }, f, indent=2)

    print(f"\n📊 Metadata saved: {metadata_file}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
