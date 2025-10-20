#!/usr/bin/env python3
"""
Extract Metrics from Load Test Results
Parses various load test result formats and generates normalized JSON for comparison.

Supports:
- Locust CSV output
- Locust JSON export
- Custom JSON format

Usage:
    python scripts/extract_metrics.py <input_file> [output_file]

Example:
    python scripts/extract_metrics.py load_results.csv load-results.json
    python scripts/extract_metrics.py locust_results.json load-results.json
"""

import csv
import json
import sys
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Union


class MetricsExtractor:
    """Extracts metrics from load test results in various formats."""

    def __init__(self, input_file: str):
        """Initialize with load test results file."""
        self.input_file = input_file
        self.file_type = self._detect_file_type(input_file)
        self.raw_data = self._load_input()

    @staticmethod
    def _detect_file_type(filepath: str) -> str:
        """Detect file type based on extension."""
        path = Path(filepath)
        ext = path.suffix.lower()

        if ext == ".csv":
            return "csv"
        elif ext == ".json":
            return "json"
        elif ext == ".txt":
            return "text"
        else:
            # Try to detect by content
            return "auto"

    def _load_input(self) -> Union[list, dict]:
        """Load input file based on detected type."""
        try:
            if self.file_type == "csv":
                return self._load_csv()
            elif self.file_type == "json":
                return self._load_json()
            else:
                # Try JSON first, then CSV
                try:
                    return self._load_json()
                except json.JSONDecodeError:
                    return self._load_csv()

        except Exception as e:
            print(f"❌ Error loading input file: {e}")
            sys.exit(1)

    @staticmethod
    def _load_csv() -> list:
        """Load Locust CSV stats file."""
        rows = []
        with open(sys.argv[1], "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        return rows

    @staticmethod
    def _load_json() -> dict:
        """Load Locust JSON export."""
        with open(sys.argv[1], "r") as f:
            return json.load(f)

    def extract_from_csv(self) -> Dict:
        """Extract metrics from Locust CSV format."""
        metrics = {}

        for row in self.raw_data:
            name = row.get("Name", "").lower()

            # Skip "Total" row
            if "total" in name:
                continue

            # Map Locust names to service names
            service_key = self._map_service_name(name)
            if not service_key:
                continue

            try:
                # Handle both Locust CSV column formats (CamelCase and lowercase with #)
                requests = int(row.get("Request Count", row.get("# requests", 0)) or 0)
                failures = int(row.get("Failure Count", row.get("# failures", 0)) or 0)
                avg_time = row.get(
                    "Average Response Time", row.get("Average response time", "0")
                )
                median_time = row.get(
                    "Median Response Time", row.get("Median response time", "0")
                )
                min_time = row.get(
                    "Min Response Time", row.get("Min response time", "0")
                )
                max_time = row.get(
                    "Max Response Time", row.get("Max response time", "0")
                )

                metrics[service_key] = {
                    "avg_latency_ms": self._parse_time(avg_time),
                    "median_latency_ms": self._parse_time(median_time),
                    "p95_latency_ms": self._parse_time(row.get("95%", "0")),
                    "p99_latency_ms": self._parse_time(row.get("99%", "0")),
                    "min_latency_ms": self._parse_time(min_time),
                    "max_latency_ms": self._parse_time(max_time),
                    "error_rate_pct": self._parse_error_rate(requests, failures),
                    "rps": float(row.get("Requests/s", 0) or 0),
                    "total_requests": requests,
                    "total_failures": failures,
                }
            except (ValueError, KeyError):
                continue

        return metrics

    def extract_from_json(self) -> Dict:
        """Extract metrics from Locust JSON format or custom JSON."""
        metrics = {}

        # Handle Locust JSON format
        if "stats" in self.raw_data:
            for stat in self.raw_data["stats"]:
                name = stat.get("name", "").lower()

                # Skip "Total" row
                if "total" in name:
                    continue

                service_key = self._map_service_name(name)
                if not service_key:
                    continue

                response_times = stat.get("response_times", {})
                metrics[service_key] = {
                    "avg_latency_ms": stat.get("avg_response_time", 0),
                    "median_latency_ms": (
                        response_times.get(0.50, 0)
                        if isinstance(response_times, dict)
                        else 0
                    ),
                    "p95_latency_ms": (
                        response_times.get(0.95, 0)
                        if isinstance(response_times, dict)
                        else 0
                    ),
                    "p99_latency_ms": (
                        response_times.get(0.99, 0)
                        if isinstance(response_times, dict)
                        else 0
                    ),
                    "min_latency_ms": stat.get("min_response_time", 0),
                    "max_latency_ms": stat.get("max_response_time", 0),
                    "error_rate_pct": self._parse_error_rate(
                        stat.get("num_requests", 0), stat.get("num_failures", 0)
                    ),
                    "rps": stat.get("requests_per_second", 0),
                    "total_requests": stat.get("num_requests", 0),
                    "total_failures": stat.get("num_failures", 0),
                }
        else:
            # Handle custom JSON format (already in normalized form)
            return self.raw_data

        return metrics

    @staticmethod
    def _map_service_name(name: str) -> Optional[str]:
        """Map test name to service key."""
        name = name.lower()

        if "api" in name or "gateway" in name or "chat" in name or "models" in name:
            return "api_gateway"
        elif "rag" in name or "query" in name or "index" in name:
            return "rag_service"
        elif "mcp" in name or "tool" in name:
            return "mcp_server"

        return None

    @staticmethod
    def _parse_time(time_str: str) -> float:
        """Parse time string and return milliseconds."""
        if not time_str or time_str == "-":
            return 0.0

        time_str = str(time_str).strip()

        try:
            if "s" in time_str:
                return float(time_str.replace("s", "")) * 1000
            elif "ms" in time_str:
                return float(time_str.replace("ms", ""))
            else:
                return float(time_str)
        except ValueError:
            return 0.0

    @staticmethod
    def _parse_error_rate(total: int, failures: int) -> float:
        """Calculate error rate percentage."""
        if total == 0:
            return 0.0
        return round((failures / total) * 100, 2)

    def extract(self) -> Dict:
        """Extract metrics based on input file type."""
        if self.file_type == "csv" or (
            self.file_type == "auto" and isinstance(self.raw_data, list)
        ):
            return self.extract_from_csv()
        else:
            return self.extract_from_json()

    def save_metrics(self, output_file: str) -> None:
        """Save extracted metrics to JSON file."""
        metrics = self.extract()

        output_path = Path(output_file)
        output_path.parent.mkdir(exist_ok=True)

        with open(output_file, "w") as f:
            json.dump(metrics, f, indent=2)

        print(f"✅ Metrics extracted and saved to: {output_file}")
        print(f"\n📊 Extracted metrics for {len(metrics)} services:")
        for service, data in metrics.items():
            print(
                f"  - {service}: {data.get('total_requests', 0)} requests, "
                f"{data.get('error_rate_pct', 0)}% errors"
            )


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/extract_metrics.py <input_file> [output_file]")
        print("\nExample:")
        print(
            "  python scripts/extract_metrics.py load_results_stats.csv load-results.json"
        )
        print(
            "  python scripts/extract_metrics.py locust_results.json load-results.json"
        )
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "load-results.json"

    # Extract metrics
    extractor = MetricsExtractor(input_file)
    extractor.save_metrics(output_file)


if __name__ == "__main__":
    main()
