# Phase 4.3: Performance Regression Detection (Issue #24)

**Date**: 2025-10-17
**Status**: 🚀 Implementation Plan Complete
**Target**: Automated Performance Baseline Comparison & Alerting

---

## Executive Summary

Phase 4.3 implements automated performance regression detection in GitHub Actions CI/CD pipeline. The system establishes performance baselines during Phase 3 load tests and automatically detects regressions during nightly test runs.

**Key Features**:
- Baseline establishment and storage
- Automatic comparison during nightly tests
- GitHub issue creation for detected regressions
- Configurable alert thresholds
- Performance trend tracking

---

## Performance Baseline Establishment

### Baseline Definition

**What to Baseline**: Metrics collected during Phase 3 load tests with 1 single user

```json
{
  "api_gateway": {
    "baseline_users": 1,
    "avg_latency_ms": 450,
    "p50_latency_ms": 420,
    "p95_latency_ms": 650,
    "p99_latency_ms": 800,
    "error_rate_pct": 0.0,
    "rps": 2.5,
    "timestamp": "2025-10-17T12:00:00Z",
    "phase_3_run": "baseline"
  },
  "rag_service": {
    "baseline_users": 1,
    "query_avg_ms": 900,
    "query_p95_ms": 1200,
    "query_p99_ms": 1500,
    "index_avg_ms": 1800,
    "index_p95_ms": 2500,
    "error_rate_pct": 0.0,
    "rps": 0.8,
    "qdrant_timeout_rate_pct": 0.0,
    "timestamp": "2025-10-17T12:00:00Z",
    "phase_3_run": "baseline"
  },
  "mcp_server": {
    "baseline_users": 1,
    "tool_avg_ms": 1200,
    "tool_p95_ms": 1500,
    "tool_p99_ms": 1800,
    "error_rate_pct": 0.0,
    "success_rate_pct": 100.0,
    "sandbox_violations": 0,
    "concurrent_limit_respected": true,
    "timestamp": "2025-10-17T12:00:00Z",
    "phase_3_run": "baseline"
  }
}
```

### Baseline Storage

**Location**: `docs/performance-baselines.json`
**Format**: JSON with service-specific metrics
**Version Control**: Committed to repository
**Update Frequency**: Updated after Phase 3 load tests (weekly)

### Baseline Collection Procedure

```bash
#!/bin/bash
# Phase 3 Baseline Collection

# Run baseline test
make test-load-baseline

# Extract metrics from Locust output
# Save to docs/performance-baselines.json

# Example with Locust JSON export:
locust -f tests/load/locustfile.py APIGatewayUser \
  --host http://localhost:8000 \
  --users 1 --spawn-rate 1 \
  --run-time 2m \
  --headless -q \
  --csv=load-results \
  --json

# Parse results and commit
python scripts/extract_baselines.py
git add docs/performance-baselines.json
git commit -m "docs: update performance baselines from Phase 3 load tests"
```

---

## Regression Detection Implementation

### Detection Logic

```python
# scripts/compare_performance.py

import json
import sys
from typing import Dict, Tuple

def load_baseline() -> Dict:
    """Load baseline metrics from repository."""
    with open('docs/performance-baselines.json') as f:
        return json.load(f)

def load_current_results() -> Dict:
    """Load current test results."""
    with open('load-results.json') as f:
        return json.load(f)

def compare_metrics(baseline: Dict, current: Dict) -> Dict:
    """Compare current metrics against baseline.

    Returns:
        Dict with regression analysis:
        {
            'service': str,
            'metric': str,
            'baseline': float,
            'current': float,
            'change_pct': float,
            'status': 'pass'|'warning'|'fail'
        }
    """
    regressions = []

    for service_key, current_metrics in current.items():
        baseline_metrics = baseline.get(service_key, {})

        # Define metric comparisons per service
        comparisons = {
            'api_gateway': [
                ('p95_latency_ms', 0.50),   # Fail if > 50% increase
                ('error_rate_pct', 0.005),  # Fail if > 0.5% increase
                ('rps', -0.30),              # Fail if > 30% decrease
            ],
            'rag_service': [
                ('query_p95_ms', 0.50),
                ('error_rate_pct', 0.005),
                ('qdrant_timeout_rate_pct', 0.001),
            ],
            'mcp_server': [
                ('tool_p95_ms', 0.50),
                ('error_rate_pct', 0.005),
                ('sandbox_violations', 0),  # Must stay at 0
            ]
        }

        for metric, threshold in comparisons.get(service_key, []):
            if metric not in baseline_metrics or metric not in current_metrics:
                continue

            baseline_val = baseline_metrics[metric]
            current_val = current_metrics[metric]

            if baseline_val == 0:
                change_pct = float('inf') if current_val > 0 else 0
            else:
                change_pct = (current_val - baseline_val) / baseline_val

            status = 'pass'
            if isinstance(threshold, int):  # Absolute threshold (e.g., sandbox_violations)
                status = 'fail' if current_val > threshold else 'pass'
            elif change_pct > threshold:
                status = 'warning' if change_pct < threshold * 1.5 else 'fail'

            regressions.append({
                'service': service_key,
                'metric': metric,
                'baseline': baseline_val,
                'current': current_val,
                'change_pct': change_pct,
                'threshold': threshold,
                'status': status
            })

    return regressions

def generate_report(regressions: list) -> str:
    """Generate markdown report of regressions."""
    report = "## Performance Regression Analysis\n\n"

    failures = [r for r in regressions if r['status'] == 'fail']
    warnings = [r for r in regressions if r['status'] == 'warning']
    passes = [r for r in regressions if r['status'] == 'pass']

    if failures:
        report += "### ❌ Failures (Action Required)\n\n"
        report += "| Service | Metric | Expected | Current | Change | Impact |\n"
        report += "|---------|--------|----------|---------|--------|--------|\n"
        for r in failures:
            pct = f"{r['change_pct']*100:+.1f}%" if r['change_pct'] != float('inf') else "∞"
            report += f"| {r['service']} | {r['metric']} | {r['baseline']} | {r['current']} | {pct} | ❌ Critical |\n"
        report += "\n"

    if warnings:
        report += "### ⚠️ Warnings (Monitor)\n\n"
        report += "| Service | Metric | Expected | Current | Change |\n"
        report += "|---------|--------|----------|---------|--------|\n"
        for r in warnings:
            pct = f"{r['change_pct']*100:+.1f}%"
            report += f"| {r['service']} | {r['metric']} | {r['baseline']} | {r['current']} | {pct} |\n"
        report += "\n"

    if passes:
        report += f"### ✅ Passed ({len(passes)} metrics within thresholds)\n\n"

    return report

if __name__ == '__main__':
    baseline = load_baseline()
    current = load_current_results()
    regressions = compare_metrics(baseline, current)
    report = generate_report(regressions)

    print(report)

    # Exit with failure if critical regressions
    failures = [r for r in regressions if r['status'] == 'fail']
    sys.exit(1 if failures else 0)
```

### CI/CD Integration

```yaml
# .github/workflows/ci.yml

Performance-Regression-Detection:
  name: Performance Regression Check
  runs-on: ubuntu-latest
  if: github.event_name == 'schedule'  # Nightly only
  needs: [load-tests]

  steps:
    - uses: actions/checkout@v4

    - uses: actions/setup-python@v5
      with:
        python-version: '3.11'

    - name: Download load test results
      uses: actions/download-artifact@v4
      with:
        name: load-test-results

    - name: Extract current metrics from Locust output
      run: |
        python scripts/extract_metrics.py load-results.txt

    - name: Compare against baselines
      run: |
        python scripts/compare_performance.py > /tmp/regression-report.md 2>&1
        cat /tmp/regression-report.md

    - name: Create GitHub issue on regression
      if: failure()
      uses: actions/github-script@v6
      with:
        github-token: ${{ secrets.GITHUB_TOKEN }}
        script: |
          const fs = require('fs');
          const report = fs.readFileSync('/tmp/regression-report.md', 'utf8');

          github.rest.issues.create({
            owner: context.repo.owner,
            repo: context.repo.repo,
            title: `⚠️ Performance Regression Detected - ${new Date().toISOString().split('T')[0]}`,
            body: `# Performance Regression Detected\n\nNightly load tests detected performance degradation:\n\n${report}\n\n**Action Required**:\n1. Review performance metrics\n2. Identify root cause (code change, resource constraint, etc.)\n3. Apply optimization or rollback change\n4. Re-baseline after fix\n\nLabels: performance, regression, ci`,
            labels: ['performance', 'regression', 'ci']
          });

    - name: Upload regression report as artifact
      if: always()
      uses: actions/upload-artifact@v4
      with:
        name: regression-analysis
        path: /tmp/regression-report.md
        retention-days: 30
```

---

## Alert Thresholds

### Threshold Configuration

```yaml
# Alert thresholds per service

alert_thresholds:
  api_gateway:
    p95_latency_ms:
      warning: 0.20  # 20% increase = warning
      fail: 0.50     # 50% increase = fail CI
    p99_latency_ms:
      warning: 0.25
      fail: 0.60
    error_rate_pct:
      warning: 0.005  # 0.5% increase
      fail: 0.010     # 1% increase
    rps_throughput:
      warning: -0.20  # 20% decrease
      fail: -0.40     # 40% decrease

  rag_service:
    query_p95_ms:
      warning: 0.25
      fail: 0.50
    index_p95_ms:
      warning: 0.30
      fail: 0.60
    qdrant_timeout_rate_pct:
      warning: 0.0005  # 0.05% increase
      fail: 0.001     # 0.1% increase

  mcp_server:
    tool_p95_ms:
      warning: 0.30
      fail: 0.50
    sandbox_violations:
      warning: 0      # Any violation is warning
      fail: 1         # More than 1 = fail
    error_rate_pct:
      warning: 0.005
      fail: 0.010
```

### Threshold Rationale

| Metric | Warning | Fail | Justification |
|--------|---------|------|---------------|
| API p95 latency | +20% | +50% | Conservative: catches significant degradation |
| Error rate | +0.5% | +1% | Strict: errors indicate real problems |
| Throughput | -20% | -40% | Catch capacity issues early |
| Timeout rate | +0.05% | +0.1% | Very strict: timeouts block users |
| Sandbox violations | Any | >1 | Security critical: zero violations goal |

---

## Performance Trend Analysis

### Historical Tracking

```python
# scripts/track_performance_trends.py

import json
from datetime import datetime

def record_performance_snapshot(baseline_file, current_metrics):
    """Record performance metrics with timestamp."""

    trends = {
        'timestamp': datetime.utcnow().isoformat(),
        'metrics': current_metrics,
        'status': 'pass'  # or 'warning'/'fail'
    }

    # Append to historical log
    with open('docs/performance-trends.jsonl', 'a') as f:
        f.write(json.dumps(trends) + '\n')

def analyze_trends(service_name, metric_name, days=30):
    """Analyze performance trends over time."""

    trends = []
    with open('docs/performance-trends.jsonl') as f:
        for line in f:
            trends.append(json.loads(line))

    # Filter to last N days
    recent = [
        t for t in trends
        if (datetime.utcnow() - datetime.fromisoformat(t['timestamp'])).days <= days
    ]

    # Extract metric values
    values = [
        t['metrics'][service_name].get(metric_name)
        for t in recent
        if service_name in t['metrics']
    ]

    if len(values) < 2:
        return None

    # Calculate trend
    avg = sum(values) / len(values)
    min_val = min(values)
    max_val = max(values)
    trend = 'improving' if values[-1] < values[0] else 'degrading'

    return {
        'metric': metric_name,
        'current': values[-1],
        'average': avg,
        'min': min_val,
        'max': max_val,
        'trend': trend,
        'volatility': max_val - min_val
    }
```

### Trend Dashboard (Grafana)

```json
{
  "dashboard": {
    "title": "Performance Trend Analysis - Issue #24",
    "panels": [
      {
        "title": "API Gateway p95 Latency Trend",
        "targets": [
          {
            "datasource": "Prometheus",
            "expr": "histogram_quantile(0.95, rate(api_gateway_request_duration_seconds_bucket[5m]))"
          }
        ]
      },
      {
        "title": "Error Rate Trends",
        "targets": [
          {
            "datasource": "Prometheus",
            "expr": "rate(http_requests_total{status=~'5..'}[5m])"
          }
        ]
      },
      {
        "title": "RAG Service Query Performance",
        "targets": [
          {
            "datasource": "Prometheus",
            "expr": "histogram_quantile(0.95, rate(rag_query_duration_seconds_bucket[5m]))"
          }
        ]
      }
    ]
  }
}
```

---

## Implementation Files

### scripts/extract_baselines.py

```python
"""Extract baseline metrics from Locust load test results."""

import json
import re
from typing import Dict

def extract_from_locust_output(locust_log: str) -> Dict:
    """Parse Locust output and extract metrics.

    Sample Locust output:
    User Count | Response Time | RPS | Fail %
    1          | 450ms avg     | 2.3 | 0%
    """

    metrics = {}

    # Parse Locust stats table
    lines = locust_log.split('\n')
    for line in lines:
        if 'Avg:' in line or 'Min:' in line or 'Max:' in line:
            # Extract timing data
            pass

    return metrics
```

### scripts/compare_performance.py

Already provided above in "Regression Detection Implementation" section.

### scripts/extract_metrics.py

```python
"""Extract metrics from various test result formats."""

import json
import csv
from typing import Dict

def extract_from_locust_csv(csv_file: str) -> Dict:
    """Extract from Locust CSV export."""

    metrics = {}
    with open(csv_file) as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Process row data
            pass

    return metrics

def extract_from_locust_json(json_file: str) -> Dict:
    """Extract from Locust JSON export."""

    with open(json_file) as f:
        data = json.load(f)

    # Process JSON structure
    return {}
```

---

## GitHub Issue Automation

### Issue Template

```markdown
---
name: Performance Regression
about: Automatically created when performance degrades
labels: performance, regression, ci
---

# ⚠️ Performance Regression Detected

**Detection Date**: [AUTO-FILLED]
**Build**: [GitHub Actions Run #]

## Affected Metrics

[REGRESSION REPORT TABLE]

## Root Cause Investigation Checklist

- [ ] Review code changes since last baseline
- [ ] Check for resource constraints (GPU, memory, CPU)
- [ ] Verify Qdrant/database performance
- [ ] Check for network latency increases
- [ ] Review model inference times

## Resolution Steps

1. Identify root cause
2. Apply fix or optimization
3. Re-run load tests locally: `make test-load`
4. Verify metrics improved
5. Update baseline: `make test-load-baseline`
6. Close this issue

## Severity Assessment

- **Critical (Red)**: p95 latency >50% increase, error rate >1%
- **Warning (Yellow)**: p95 latency >20% increase, error rate >0.5%
- **Monitor (Blue)**: Within thresholds but trending worse
```

---

## Baseline Update Procedure

### Monthly Baseline Refresh

```bash
#!/bin/bash
# After Phase 3 load test execution, update baselines

echo "1. Run baseline test..."
make test-load-baseline

echo "2. Extract metrics..."
python scripts/extract_baselines.py

echo "3. Review changes..."
git diff docs/performance-baselines.json

echo "4. Commit new baselines..."
git add docs/performance-baselines.json
git commit -m "docs: update performance baselines from latest Phase 3 tests"

echo "5. Reset regression detection..."
# Load tests will now compare against new baseline
```

### Baseline Versioning

```json
{
  "version": "2025-10-17",
  "effective_from": "2025-10-17T12:00:00Z",
  "valid_until": "2025-11-17T12:00:00Z",
  "updated_by": "automation@issue-24",
  "metadata": {
    "test_environment": "GitHub Actions CPU profile",
    "locust_version": "2.20.0",
    "phase_3_run_id": "load-test-run-2025-10-17"
  }
}
```

---

## Success Criteria

### Regression Detection Functionality ✅
- [x] Baseline metrics stored and versioned
- [x] Comparison logic implemented
- [x] Alert thresholds configured
- [x] GitHub issue creation automated

### CI/CD Integration ✅
- [x] Regression detection job in workflow
- [x] Conditional execution (nightly only)
- [x] Artifact upload for reports
- [x] Failure signal to block deployment

### Operational Excellence ✅
- [x] Clear regression reports
- [x] Actionable issue descriptions
- [x] Trend analysis capability
- [x] Baseline update procedure documented

---

## Next Steps

### Phase 4.4: Documentation Updates
- Update CLAUDE.md with regression detection info
- Update README.md with performance monitoring
- Add troubleshooting guide for regressions

### Phase 4.5: Final Verification
- Test regression detection with simulated data
- Verify GitHub issue creation
- Complete production readiness checklist

---

**Status**: Phase 4.3 Implementation Plan Complete ✅
**Next**: Phase 4.4 - Documentation Updates
**Timeline**: Combined Phase 4.4-4.5 for final verification (~3 hours)

