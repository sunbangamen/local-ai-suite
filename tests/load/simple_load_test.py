#!/usr/bin/env python3
"""
Simple Load Test Simulator
Generates realistic load test results for testing the regression detection pipeline.
"""

import json
import csv
import sys
from datetime import datetime
from pathlib import Path


def generate_baseline_results():
    """Generate baseline load test results (1 user, stable)."""
    return {
        "api_gateway": {
            "name": "api_gateway",
            "requests": 300,
            "failures": 1,
            "median": 120,
            "average": 150,
            "min": 50,
            "max": 500,
            "rps": 50.0
        },
        "rag_service": {
            "name": "rag_service",
            "requests": 150,
            "failures": 0,
            "median": 2000,
            "average": 2500,
            "min": 1000,
            "max": 8000,
            "rps": 25.0
        },
        "mcp_server": {
            "name": "mcp_server",
            "requests": 90,
            "failures": 0,
            "median": 3000,
            "average": 3500,
            "min": 500,
            "max": 12000,
            "rps": 15.0
        }
    }


def generate_progressive_results(scenario="api"):
    """Generate progressive load test results."""
    scenarios = {
        "api": {
            "api_gateway": {
                "name": "api_gateway",
                "requests": 1500,  # 10→50→100 users
                "failures": 15,
                "median": 150,
                "average": 180,
                "min": 50,
                "max": 750,
                "rps": 35.0
            },
            "rag_service": {
                "name": "rag_service",
                "requests": 300,
                "failures": 1,
                "median": 2100,
                "average": 2600,
                "min": 1000,
                "max": 8500,
                "rps": 24.0
            }
        },
        "rag": {
            "rag_service": {
                "name": "rag_service",
                "requests": 250,  # 5→25→50 users
                "failures": 3,
                "median": 2200,
                "average": 2700,
                "min": 1000,
                "max": 9000,
                "rps": 22.0
            },
            "api_gateway": {
                "name": "api_gateway",
                "requests": 600,
                "failures": 2,
                "median": 140,
                "average": 170,
                "min": 50,
                "max": 600,
                "rps": 45.0
            }
        },
        "mcp": {
            "mcp_server": {
                "name": "mcp_server",
                "requests": 100,  # 5→20 users
                "failures": 0,
                "median": 3200,
                "average": 3700,
                "min": 500,
                "max": 13000,
                "rps": 14.0
            }
        }
    }

    results = scenarios.get(scenario, {})
    if results:
        results["total"] = {
            "name": "Total",
            "requests": sum(r["requests"] for r in results.values() if r.get("requests")),
            "failures": sum(r["failures"] for r in results.values() if r.get("failures")),
        }
    return results


def save_csv(data, filename):
    """Save results as Locust-format CSV."""
    output_path = Path(filename)
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Name', '# requests', '# failures', 'Median response time',
                        'Average response time', 'Min response time', 'Max response time',
                        'Average Content Length', 'Requests/s'])

        for service_name, data_item in data.items():
            if service_name == "total":
                continue
            writer.writerow([
                data_item.get('name', service_name),
                data_item.get('requests', 0),
                data_item.get('failures', 0),
                data_item.get('median', 0),
                data_item.get('average', 0),
                data_item.get('min', 0),
                data_item.get('max', 0),
                1024,
                f"{data_item.get('rps', 0):.1f}"
            ])

    print(f"✅ CSV saved to: {output_path}")


def save_json(data, filename):
    """Save results as JSON."""
    output_path = Path(filename)
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"✅ JSON saved to: {output_path}")


def main():
    """Generate and save load test results."""
    if len(sys.argv) < 2:
        print("Usage: python simple_load_test.py <baseline|api|rag|mcp>")
        print("\nOptions:")
        print("  baseline  - Generate baseline results (1 user, stable)")
        print("  api       - Generate API Gateway progressive load results")
        print("  rag       - Generate RAG Service progressive load results")
        print("  mcp       - Generate MCP Server progressive load results")
        sys.exit(1)

    test_type = sys.argv[1]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if test_type == "baseline":
        print("🚀 Generating baseline load test results (1 user, 2 min)...")
        results = generate_baseline_results()
        csv_file = f"tests/load/load_results_baseline_{timestamp}.csv"
        json_file = f"tests/load/load_results_baseline_{timestamp}.json"
    else:
        print(f"🚀 Generating {test_type} progressive load test results...")
        results = generate_progressive_results(test_type)
        csv_file = f"tests/load/load_results_{test_type}_{timestamp}.csv"
        json_file = f"tests/load/load_results_{test_type}_{timestamp}.json"

    save_csv(results, csv_file)
    save_json(results, json_file)

    print(f"\n📊 Test Results Summary:")
    for service, data in results.items():
        if service != "total":
            print(f"  {service}: {data.get('requests')} requests, "
                  f"{data.get('failures')} failures, "
                  f"{data.get('rps'):.1f} RPS")


if __name__ == "__main__":
    main()
