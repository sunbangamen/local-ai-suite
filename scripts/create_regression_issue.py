#!/usr/bin/env python3
"""
GitHub Issue Auto-Creation for Performance Regressions

Analyzes regression detection results and automatically creates GitHub issues
when critical performance regressions are detected.

Usage:
    python scripts/create_regression_issue.py <regression_report_file> [--token TOKEN]

Example:
    python scripts/create_regression_issue.py load-test-results/regression-analysis.md
    python scripts/create_regression_issue.py load-test-results/regression-analysis.md --token ghp_xxx
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass
from datetime import datetime

try:
    import requests
except ImportError:
    print("❌ Error: 'requests' module not found. Install with: pip install requests")
    sys.exit(1)


@dataclass
class RegressionIssue:
    """Represents a regression issue to be created."""
    title: str
    body: str
    labels: List[str]
    milestone: Optional[str] = None

    def to_github_payload(self) -> Dict:
        """Convert to GitHub issue creation payload."""
        payload = {
            "title": self.title,
            "body": self.body,
            "labels": self.labels,
        }
        if self.milestone:
            payload["milestone"] = self.milestone
        return payload


class GitHubIssueCreator:
    """Creates GitHub issues for performance regressions."""

    # GitHub API configuration
    GITHUB_API_URL = "https://api.github.com"
    ISSUE_LABELS = ["performance", "regression", "automated"]
    ISSUE_PRIORITY_LABEL_MAP = {
        "critical": ["performance", "regression", "automated", "priority-critical"],
        "high": ["performance", "regression", "automated", "priority-high"],
        "medium": ["performance", "regression", "automated"],
    }

    def __init__(self, repo: str, token: Optional[str] = None):
        """Initialize GitHub issue creator.

        Args:
            repo: GitHub repository in format 'owner/repo'
            token: GitHub personal access token (reads from GITHUB_TOKEN env if not provided)
        """
        self.repo = repo
        self.token = token or os.environ.get("GITHUB_TOKEN")
        if not self.token:
            raise ValueError(
                "GitHub token not provided. "
                "Set GITHUB_TOKEN environment variable or pass --token argument"
            )
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Performance-Regression-Detector",
        }

    def parse_regression_report(self, report_path: str) -> Dict:
        """Parse regression analysis markdown report.

        Args:
            report_path: Path to regression-analysis.md file

        Returns:
            Dictionary with failures and warnings
        """
        try:
            with open(report_path, "r") as f:
                content = f.read()
        except FileNotFoundError:
            print(f"❌ Regression report not found: {report_path}")
            sys.exit(1)

        # Extract failures section
        failures_match = re.search(
            r"### ❌ Failures.*?(?=###|$)", content, re.DOTALL
        )
        failures_lines = []
        if failures_match:
            for line in failures_match.group(0).split("\n"):
                if line.startswith("| ") and line.count("|") >= 5:
                    failures_lines.append(line)

        # Extract warnings section
        warnings_match = re.search(
            r"### ⚠️ Warnings.*?(?=###|$)", content, re.DOTALL
        )
        warnings_lines = []
        if warnings_match:
            for line in warnings_match.group(0).split("\n"):
                if line.startswith("| ") and line.count("|") >= 5:
                    warnings_lines.append(line)

        return {
            "failures": failures_lines,
            "warnings": warnings_lines,
            "report_content": content,
        }

    def create_failure_issue(self, parsed_report: Dict) -> Optional[str]:
        """Create issue for critical performance failures.

        Args:
            parsed_report: Dictionary from parse_regression_report()

        Returns:
            Issue URL if created, None otherwise
        """
        if not parsed_report["failures"]:
            return None

        # Build issue details
        failure_count = len(parsed_report["failures"])
        timestamp = datetime.utcnow().isoformat() + "Z"

        title = f"🚨 Critical Performance Regression Detected ({failure_count} metrics)"

        body = f"""## Performance Regression Alert

**Timestamp**: {timestamp}

### Critical Failures ({failure_count} metrics)

{self._format_table_lines(parsed_report["failures"])}

### Details

A critical performance regression has been detected in the load testing results.
The following metrics have exceeded their defined thresholds and require immediate investigation.

### Investigation Steps

1. Review the full regression report in the CI/CD artifacts
2. Check recent code changes for performance impacts
3. Verify baseline measurements are accurate
4. Consider reverting problematic changes or implementing performance optimizations
5. Re-run load tests after fixes to validate improvements

### Baseline Comparison

Run the following to compare against baseline:
```bash
python scripts/compare_performance.py docs/performance-baselines.json load-results.json
```

### Next Steps

- [ ] Review code changes from recent commits
- [ ] Check for resource leaks or inefficient queries
- [ ] Validate database indexes and query performance
- [ ] Consider horizontal scaling or caching improvements
- [ ] Update baselines if new performance profile is acceptable

---
Auto-generated by Performance Regression Detector
"""

        return self._create_issue(
            title=title,
            body=body,
            labels=self.ISSUE_PRIORITY_LABEL_MAP["critical"],
        )

    def create_warning_issue(self, parsed_report: Dict) -> Optional[str]:
        """Create issue for performance warnings.

        Args:
            parsed_report: Dictionary from parse_regression_report()

        Returns:
            Issue URL if created, None otherwise
        """
        if not parsed_report["warnings"]:
            return None

        warning_count = len(parsed_report["warnings"])
        timestamp = datetime.utcnow().isoformat() + "Z"

        title = f"⚠️ Performance Warning ({warning_count} metrics trending towards regression)"

        body = f"""## Performance Warning

**Timestamp**: {timestamp}

### Warnings ({warning_count} metrics)

{self._format_table_lines(parsed_report["warnings"])}

### Details

The following metrics are showing signs of performance degradation but have not yet
exceeded critical thresholds. Monitor these metrics closely in upcoming releases.

### Monitoring Recommendations

1. Track these metrics in the next few load test runs
2. Investigate potential causes in recent code changes
3. Consider implementing performance optimizations proactively
4. Review architecture for scalability improvements

### Helpful Commands

```bash
# View detailed regression analysis
cat load-test-results/regression-analysis.md

# Compare with baseline
python scripts/compare_performance.py docs/performance-baselines.json load-results.json

# Extract current metrics
python scripts/extract_metrics.py load_results.json
```

---
Auto-generated by Performance Regression Detector
"""

        return self._create_issue(
            title=title,
            body=body,
            labels=self.ISSUE_PRIORITY_LABEL_MAP["medium"],
        )

    def _format_table_lines(self, lines: List[str]) -> str:
        """Format table lines from regression report."""
        if not lines:
            return "No data"
        # Skip header separator line
        return "\n".join(
            line for line in lines if line.strip() and not re.match(r"^\|\s*-+", line)
        )

    def _create_issue(self, title: str, body: str, labels: List[str]) -> Optional[str]:
        """Create a GitHub issue.

        Args:
            title: Issue title
            body: Issue body (markdown)
            labels: List of labels to attach

        Returns:
            Issue URL if successful, None otherwise
        """
        url = f"{self.GITHUB_API_URL}/repos/{self.repo}/issues"

        payload = {
            "title": title,
            "body": body,
            "labels": labels,
        }

        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=10)

            if response.status_code == 201:
                issue_data = response.json()
                issue_url = issue_data.get("html_url")
                print(f"✅ Issue created: {issue_url}")
                return issue_url
            elif response.status_code == 422:
                # Check if issue already exists
                error_data = response.json()
                if "already exists" in str(error_data):
                    print(f"⚠️ Issue already exists for this regression")
                    return None
                else:
                    print(f"❌ Validation error: {error_data}")
                    return None
            else:
                print(f"❌ Failed to create issue: {response.status_code}")
                print(f"   Response: {response.text}")
                return None

        except requests.RequestException as e:
            print(f"❌ Error connecting to GitHub API: {e}")
            return None

    def check_existing_issues(self, title_pattern: str) -> bool:
        """Check if issue with similar title already exists.

        Args:
            title_pattern: Regex pattern to match against issue titles

        Returns:
            True if similar issue exists, False otherwise
        """
        url = f"{self.GITHUB_API_URL}/repos/{self.repo}/issues"
        params = {"state": "open", "per_page": 100}

        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            if response.status_code == 200:
                issues = response.json()
                for issue in issues:
                    if re.search(title_pattern, issue.get("title", "")):
                        return True
            return False
        except requests.RequestException:
            return False


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/create_regression_issue.py <regression_report_file> [--token TOKEN]")
        print("\nExample:")
        print("  python scripts/create_regression_issue.py load-test-results/regression-analysis.md")
        print("  python scripts/create_regression_issue.py load-test-results/regression-analysis.md --token ghp_xxx")
        sys.exit(1)

    report_file = sys.argv[1]
    token = None

    # Parse --token argument if provided
    if "--token" in sys.argv:
        token_idx = sys.argv.index("--token")
        if token_idx + 1 < len(sys.argv):
            token = sys.argv[token_idx + 1]

    # Get repository from environment
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not repo:
        print("❌ Error: GITHUB_REPOSITORY environment variable not set")
        print("   Set it to 'owner/repo' format (e.g., 'sunbangamen/local-ai-suite')")
        sys.exit(1)

    # Initialize issue creator
    try:
        creator = GitHubIssueCreator(repo=repo, token=token)
    except ValueError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    # Parse regression report
    print(f"📋 Parsing regression report: {report_file}")
    parsed = creator.parse_regression_report(report_file)

    # Create issues
    issues_created = []

    if parsed["failures"]:
        print(f"🚨 Found {len(parsed['failures'])} critical failure(s)")
        issue_url = creator.create_failure_issue(parsed)
        if issue_url:
            issues_created.append(issue_url)
    else:
        print("✅ No critical failures detected")

    if parsed["warnings"]:
        print(f"⚠️ Found {len(parsed['warnings'])} warning(s)")
        issue_url = creator.create_warning_issue(parsed)
        if issue_url:
            issues_created.append(issue_url)
    else:
        print("✅ No warnings detected")

    # Summary
    print(f"\n📊 Summary:")
    print(f"  - Repository: {repo}")
    print(f"  - Issues created: {len(issues_created)}")

    if not issues_created:
        print("✅ No issues needed to be created")
        sys.exit(0)

    print("\n✅ Issues successfully created:")
    for url in issues_created:
        print(f"  - {url}")

    sys.exit(0)


if __name__ == "__main__":
    main()
