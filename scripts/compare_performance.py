#!/usr/bin/env python3
"""
Performance Regression Detection Script
Compares current load test results against baseline metrics to detect performance degradation.

Usage:
    python scripts/compare_performance.py <baseline_file> <current_results_file>

Example:
    python scripts/compare_performance.py docs/performance-baselines.json load-results.json
"""

import json
import sys
import os
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class RegressionResult:
    """Represents a single regression comparison result."""

    service: str
    metric: str
    baseline: float
    current: float
    change_pct: float
    threshold: float
    status: str  # 'pass', 'warning', 'fail'

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "service": self.service,
            "metric": self.metric,
            "baseline": self.baseline,
            "current": self.current,
            "change_pct": self.change_pct,
            "threshold": self.threshold,
            "status": self.status,
        }


class PerformanceComparator:
    """Compares current metrics against baseline and detects regressions."""

    # Alert thresholds per service
    THRESHOLDS = {
        "api_gateway": [
            ("p95_latency_ms", 0.50),  # Fail if > 50% increase
            ("error_rate_pct", 0.005),  # Fail if > 0.5% increase
            ("rps", -0.30),  # Fail if > 30% decrease
        ],
        "rag_service": [
            ("query_p95_ms", 0.50),
            ("error_rate_pct", 0.005),
            ("qdrant_timeout_rate_pct", 0.001),
        ],
        "mcp_server": [
            ("tool_p95_ms", 0.50),
            ("error_rate_pct", 0.005),
            ("sandbox_violations", 0),  # Must stay at 0 (absolute threshold)
        ],
    }

    def __init__(self, baseline_file: str, current_file: str):
        """Initialize with baseline and current result files."""
        self.baseline_file = baseline_file
        self.current_file = current_file
        self.baseline = self._load_json(baseline_file)
        self.current = self._load_json(current_file)
        self.regressions: List[RegressionResult] = []

    @staticmethod
    def _load_json(filepath: str) -> Dict:
        """Load JSON file with error handling."""
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ File not found: {filepath}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in {filepath}: {e}")
            sys.exit(1)

    def compare(self) -> List[RegressionResult]:
        """Compare current metrics against baseline.

        Returns:
            List of RegressionResult objects
        """
        self.regressions = []

        for service_key, current_metrics in self.current.items():
            baseline_metrics = self.baseline.get(service_key, {})

            if not baseline_metrics:
                print(f"⚠️  No baseline found for service: {service_key}")
                continue

            # Get thresholds for this service
            thresholds = dict(self.THRESHOLDS.get(service_key, []))

            for metric, threshold in thresholds.items():
                if metric not in baseline_metrics or metric not in current_metrics:
                    continue

                baseline_val = baseline_metrics[metric]
                current_val = current_metrics[metric]

                # Calculate change percentage
                if baseline_val == 0:
                    change_pct = float("inf") if current_val > 0 else 0
                else:
                    change_pct = (current_val - baseline_val) / baseline_val

                # Determine status
                status = self._determine_status(change_pct, threshold, current_val)

                result = RegressionResult(
                    service=service_key,
                    metric=metric,
                    baseline=baseline_val,
                    current=current_val,
                    change_pct=change_pct,
                    threshold=threshold,
                    status=status,
                )
                self.regressions.append(result)

        return self.regressions

    @staticmethod
    def _determine_status(change_pct: float, threshold: float, current_val: float) -> str:
        """Determine regression status based on threshold.

        For positive thresholds (latency, error_rate): fail if change_pct > threshold
        For negative thresholds (rps decrease tolerance): fail if change_pct < threshold
        """
        # Handle absolute threshold (e.g., sandbox_violations must be 0)
        if isinstance(threshold, int):
            return "fail" if current_val > threshold else "pass"

        # Handle percentage thresholds
        if threshold < 0:
            # Negative threshold: fail if change is worse (more negative) than threshold
            # E.g., for rps with threshold -0.30, fail only if change < -0.30 (30%+ decrease)
            if change_pct < threshold:
                return "fail"
            # Add small tolerance for measurement noise (±1%)
            elif change_pct < threshold * 1.5 and change_pct < -0.01:
                return "warning"
        else:
            # Positive threshold: fail if change is worse (more positive) than threshold
            # E.g., for latency with threshold 0.50, fail only if change > 0.50 (50%+ increase)
            if change_pct > threshold:
                # Warning if between threshold and 1.5x threshold
                if change_pct < threshold * 1.5:
                    return "warning"
                else:
                    return "fail"

        return "pass"

    def generate_report(self) -> str:
        """Generate markdown report of regression analysis."""
        failures = [r for r in self.regressions if r.status == "fail"]
        warnings = [r for r in self.regressions if r.status == "warning"]
        passes = [r for r in self.regressions if r.status == "pass"]

        report = "## Performance Regression Analysis\n\n"

        if failures:
            report += "### ❌ Failures (Action Required)\n\n"
            report += "| Service | Metric | Expected | Current | Change | Impact |\n"
            report += "|---------|--------|----------|---------|--------|--------|\n"
            for r in failures:
                pct = f"{r.change_pct*100:+.1f}%" if r.change_pct != float("inf") else "∞"
                report += f"| {r.service} | {r.metric} | {r.baseline} | {r.current} | {pct} | ❌ Critical |\n"
            report += "\n"

        if warnings:
            report += "### ⚠️ Warnings (Monitor)\n\n"
            report += "| Service | Metric | Expected | Current | Change |\n"
            report += "|---------|--------|----------|---------|--------|\n"
            for r in warnings:
                pct = f"{r.change_pct*100:+.1f}%"
                report += f"| {r.service} | {r.metric} | {r.baseline} | {r.current} | {pct} |\n"
            report += "\n"

        if passes:
            report += f"### ✅ Passed ({len(passes)} metrics within thresholds)\n\n"
            report += "All measured metrics are within acceptable thresholds.\n"

        # Summary
        total = len(self.regressions)
        report += "\n## Summary\n\n"
        report += f"- **Total Metrics**: {total}\n"
        report += f"- **Failures**: {len(failures)}\n"
        report += f"- **Warnings**: {len(warnings)}\n"
        report += f"- **Passed**: {len(passes)}\n"

        return report

    def save_report(self, output_file: str) -> None:
        """Save regression report to file."""
        report = self.generate_report()
        with open(output_file, "w") as f:
            f.write(report)
        print(f"✅ Report saved to: {output_file}")

    def has_failures(self) -> bool:
        """Check if there are any critical failures."""
        return any(r.status == "fail" for r in self.regressions)


def main():
    """Main entry point."""
    if len(sys.argv) != 3:
        print("Usage: python scripts/compare_performance.py <baseline_file> <current_results_file>")
        print("\nExample:")
        print(
            "  python scripts/compare_performance.py docs/performance-baselines.json load-results.json"
        )
        sys.exit(1)

    baseline_file = sys.argv[1]
    current_file = sys.argv[2]

    # Create comparator
    comparator = PerformanceComparator(baseline_file, current_file)

    # Run comparison
    comparator.compare()

    # Generate and print report
    report = comparator.generate_report()
    print(report)

    # Save report
    report_file = Path("load-test-results") / "regression-analysis.md"
    report_file.parent.mkdir(exist_ok=True)
    comparator.save_report(str(report_file))

    # Exit with failure if critical regressions found
    if comparator.has_failures():
        print("\n❌ Critical performance regressions detected!")
        sys.exit(1)
    else:
        print("\n✅ No critical performance regressions detected")
        sys.exit(0)


if __name__ == "__main__":
    main()
