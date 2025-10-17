#!/usr/bin/env python3
"""
Extract Baseline Metrics from Locust Load Test Results
Parses Locust test output and generates JSON baseline metrics for performance regression detection.

Usage:
    python scripts/extract_baselines.py <locust_stats_file> <output_file>

Example:
    python scripts/extract_baselines.py load_results_stats.csv docs/performance-baselines.json
"""

import csv
import json
import sys
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional


class BaselineExtractor:
    """Extracts performance baseline metrics from Locust test results."""

    def __init__(self, stats_file: str):
        """Initialize with Locust stats CSV file."""
        self.stats_file = stats_file
        self.stats = self._parse_csv(stats_file)

    @staticmethod
    def _parse_csv(filepath: str) -> list:
        """Parse Locust stats CSV file.

        Expected CSV format from Locust:
        Name,# requests,# failures,Median response time,Average response time,Min response time,Max response time,Average Content Length,Requests/s
        """
        rows = []
        try:
            with open(filepath, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append(row)
            return rows
        except FileNotFoundError:
            print(f"❌ Stats file not found: {filepath}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error parsing CSV: {e}")
            sys.exit(1)

    @staticmethod
    def _parse_response_time(time_str: str) -> float:
        """Parse response time string and return milliseconds.

        Handle formats like: "650", "1200ms", "1.5s"
        """
        if not time_str or time_str == '-':
            return 0.0

        # Remove whitespace
        time_str = time_str.strip()

        # Convert to milliseconds
        if 's' in time_str:
            return float(time_str.replace('s', '')) * 1000
        elif 'ms' in time_str:
            return float(time_str.replace('ms', ''))
        else:
            # Assume milliseconds if no unit
            try:
                return float(time_str)
            except ValueError:
                return 0.0

    @staticmethod
    def _parse_rate(rate_str: str) -> float:
        """Parse request rate and return RPS."""
        if not rate_str or rate_str == '-':
            return 0.0

        try:
            return float(rate_str)
        except ValueError:
            return 0.0

    @staticmethod
    def _parse_error_rate(requests: int, failures: int) -> float:
        """Calculate error rate as percentage."""
        if requests == 0:
            return 0.0
        return (failures / requests) * 100

    def extract_service_metrics(self, service_name: str) -> Optional[Dict]:
        """Extract metrics for a specific service from Locust results.

        Args:
            service_name: 'api_gateway', 'rag_service', or 'mcp_server'

        Returns:
            Dictionary with service metrics or None if not found
        """
        # Map service names to endpoint patterns or use Aggregated row for API Gateway
        endpoint_patterns = {
            'api_gateway': 'Aggregated',  # Use aggregated metrics for API Gateway
            'rag_service': '/query',  # RAG service query endpoint
            'mcp_server': '/tools'    # MCP server tools endpoint
        }

        pattern = endpoint_patterns.get(service_name, service_name)
        service_rows = [r for r in self.stats if pattern.lower() in r.get('Name', '').lower()]

        if not service_rows:
            print(f"⚠️  No data found for service: {service_name} (pattern: {pattern})")
            return None

        # Aggregate metrics (typically one row per service from Locust)
        if len(service_rows) > 1:
            print(f"⚠️  Multiple rows found for {service_name}, using first row")

        row = service_rows[0]

        try:
            # Handle both Locust column name formats
            requests = int(row.get('Request Count', row.get('# requests', '0')) or 0)
            failures = int(row.get('Failure Count', row.get('# failures', '0')) or 0)
            median_ms = self._parse_response_time(row.get('Median Response Time', row.get('Median response time', '0')))
            avg_ms = self._parse_response_time(row.get('Average Response Time', row.get('Average response time', '0')))
            min_ms = self._parse_response_time(row.get('Min Response Time', row.get('Min response time', '0')))
            max_ms = self._parse_response_time(row.get('Max Response Time', row.get('Max response time', '0')))
            rps = self._parse_rate(row.get('Requests/s', '0'))
            error_rate = self._parse_error_rate(requests, failures)

            metrics = {
                'baseline_users': 1,  # Single user baseline
                'avg_latency_ms': avg_ms,
                'median_latency_ms': median_ms,
                'min_latency_ms': min_ms,
                'max_latency_ms': max_ms,
                'p95_latency_ms': int(avg_ms * 1.4),  # Estimate p95 as ~1.4x average
                'p99_latency_ms': int(avg_ms * 1.7),  # Estimate p99 as ~1.7x average
                'error_rate_pct': round(error_rate, 2),
                'rps': round(rps, 2),
                'total_requests': requests,
                'total_failures': failures,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }

            return metrics

        except (ValueError, KeyError) as e:
            print(f"❌ Error processing metrics for {service_name}: {e}")
            return None

    def extract_all_baselines(self) -> Dict:
        """Extract baselines for all known services."""
        # For Phase 3, we have baseline data for api_gateway only
        # RAG service and MCP server baselines will be added when their test data is available
        services_to_extract = ['api_gateway']
        baselines = {}

        for service in services_to_extract:
            metrics = self.extract_service_metrics(service)
            if metrics:
                baselines[service] = metrics
                print(f"✅ Extracted baseline for {service}")
            else:
                print(f"⏳ Baseline data not available for {service} (will add in future phases)")

        return baselines

    def save_baselines(self, output_file: str) -> None:
        """Save extracted baselines to JSON file.

        Output structure (service-based for compatibility with compare_performance.py):
        {
            "api_gateway": {
                "avg_latency_ms": ...,
                "error_rate_pct": ...,
                ...
            }
        }
        """
        baselines = self.extract_all_baselines()

        output_path = Path(output_file)
        output_path.parent.mkdir(exist_ok=True)

        # Save in simple service-based structure (not nested under "baseline_test")
        with open(output_file, 'w') as f:
            json.dump(baselines, f, indent=2)

        print(f"\n✅ Baselines saved to: {output_file}")
        print(f"📊 Extracted {len(baselines)} service baselines")

        if baselines:
            print("\n📋 Services included:")
            for service in baselines.keys():
                print(f"  - {service}")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/extract_baselines.py <stats_csv_file> [output_file]")
        print("\nExample:")
        print("  python scripts/extract_baselines.py load_results_stats.csv docs/performance-baselines.json")
        sys.exit(1)

    stats_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'docs/performance-baselines.json'

    # Extract baselines
    extractor = BaselineExtractor(stats_file)
    extractor.save_baselines(output_file)


if __name__ == '__main__':
    main()
