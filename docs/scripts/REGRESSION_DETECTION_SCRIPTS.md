# Performance Regression Detection Scripts

Complete automation pipeline for detecting, reporting, and alerting on performance regressions.

## Overview

The regression detection system consists of 4 Python scripts that work together to:

1. **Extract metrics** from load test results (CSV/JSON formats)
2. **Establish baselines** from reference test runs
3. **Compare** current metrics against baselines with configurable thresholds
4. **Automatically create GitHub issues** when regressions are detected

## Quick Start

### 1. Extract Metrics from Load Test Results

```bash
# Auto-detect format (CSV or JSON)
python scripts/extract_metrics.py load_results_stats.csv load-results.json

# Supports multiple formats:
# - Locust CSV stats: load_results_stats.csv
# - Locust JSON export: locust_results.json
# - Custom normalized JSON: metrics.json
```

**Output**: Normalized JSON file with extracted metrics for all services

### 2. Establish Performance Baselines

```bash
# Extract baselines from a clean/reference test run
python scripts/extract_baselines.py load_results_stats.csv docs/performance-baselines.json

# This creates the reference point for future regression detection
```

**Output**: `docs/performance-baselines.json` with timestamp-tagged baseline metrics

### 3. Compare Against Baselines and Detect Regressions

```bash
# Run after each load test to compare against baseline
python scripts/compare_performance.py docs/performance-baselines.json load-results.json

# Generates:
# - Console output with markdown report
# - load-test-results/regression-analysis.md file
# - Exit code 1 if critical failures detected (for CI)
```

**Output**: Markdown report with pass/warning/fail status for each metric

### 4. Auto-Create GitHub Issues for Regressions

```bash
# Create GitHub issues for detected regressions
export GITHUB_TOKEN=ghp_xxxx
export GITHUB_REPOSITORY=owner/repo

python scripts/create_regression_issue.py load-test-results/regression-analysis.md
```

**Output**: GitHub issues with regression details and investigation steps

## Script Details

### extract_metrics.py

**Purpose**: Normalize load test results from various formats

**Inputs**:
- `<input_file>`: Load test result file (CSV or JSON)
- `[output_file]`: Output JSON file (default: `load-results.json`)

**Output Format**:
```json
{
  "api_gateway": {
    "avg_latency_ms": 150.0,
    "median_latency_ms": 120.0,
    "p95_latency_ms": 450.0,
    "p99_latency_ms": 800.0,
    "min_latency_ms": 50.0,
    "max_latency_ms": 2000.0,
    "error_rate_pct": 0.5,
    "rps": 50.0,
    "total_requests": 5000,
    "total_failures": 25
  },
  "rag_service": { ... },
  "mcp_server": { ... }
}
```

**Service Detection**:
- `api_gateway`: Matches "api", "gateway", "chat", "models"
- `rag_service`: Matches "rag", "query", "index"
- `mcp_server`: Matches "mcp", "tool"

**Time Format Handling**:
- Converts `s` (seconds) to milliseconds: `1.5s` → `1500ms`
- Converts `ms` to float: `150ms` → `150.0`
- Assumes milliseconds if no unit: `150` → `150.0`

---

### extract_baselines.py

**Purpose**: Extract performance baselines from reference load test

**Inputs**:
- `<stats_csv_file>`: Locust stats CSV file
- `[output_file]`: Output JSON file (default: `docs/performance-baselines.json`)

**Output Format**:
```json
{
  "api_gateway": {
    "baseline_users": 1,
    "avg_latency_ms": 150.0,
    "median_latency_ms": 120.0,
    "p95_latency_ms": 210.0,
    "p99_latency_ms": 255.0,
    "min_latency_ms": 50.0,
    "max_latency_ms": 500.0,
    "error_rate_pct": 0.0,
    "rps": 5.0,
    "total_requests": 300,
    "total_failures": 0,
    "timestamp": "2025-10-17T14:30:00Z"
  },
  "rag_service": { ... },
  "mcp_server": { ... }
}
```

**Percentile Estimation**:
- p95: ~1.4x average (for services where exact data unavailable)
- p99: ~1.7x average (for services where exact data unavailable)
- Uses actual values if available in CSV

**CSV Expected Columns**:
- `Name`: Test name (identifies service)
- `# requests`: Total request count
- `# failures`: Total failure count
- `Median response time`: Median latency
- `Average response time`: Average latency
- `Min response time`: Minimum latency
- `Max response time`: Maximum latency
- `Requests/s`: Throughput (RPS)

---

### compare_performance.py

**Purpose**: Detect performance regressions against baseline

**Inputs**:
- `<baseline_file>`: Baseline JSON from extract_baselines.py
- `<current_results_file>`: Current metrics JSON from extract_metrics.py

**Thresholds** (configurable in THRESHOLDS dict):

**API Gateway**:
- p95_latency_ms: +50% failure threshold
- error_rate_pct: +0.5% absolute failure threshold
- rps: -30% failure threshold (throughput decrease)

**RAG Service**:
- query_p95_ms: +50% failure threshold
- error_rate_pct: +0.5% absolute failure threshold
- qdrant_timeout_rate_pct: +0.1% failure threshold

**MCP Server**:
- tool_p95_ms: +50% failure threshold
- error_rate_pct: +0.5% absolute failure threshold
- sandbox_violations: 0 violations (absolute threshold)

**Output Format** (load-test-results/regression-analysis.md):

```markdown
## Performance Regression Analysis

### ❌ Failures (Action Required)

| Service | Metric | Expected | Current | Change | Impact |
|---------|--------|----------|---------|--------|--------|
| api_gateway | p95_latency_ms | 450 | 750 | +66.7% | ❌ Critical |

### ⚠️ Warnings (Monitor)

| Service | Metric | Expected | Current | Change |
|---------|--------|----------|---------|--------|
| rag_service | query_p95_ms | 3000 | 4200 | +40.0% |

### ✅ Passed (15 metrics within thresholds)

All measured metrics are within acceptable thresholds.

## Summary

- **Total Metrics**: 20
- **Failures**: 1
- **Warnings**: 1
- **Passed**: 18
```

**Status Determination**:
- **Pass**: Change within threshold
- **Warning**: Change 100-150% of threshold
- **Fail**: Change >150% of threshold or exceeds threshold

**Exit Codes**:
- `0`: No critical failures
- `1`: Critical failures detected (for CI/CD failure triggers)

---

### create_regression_issue.py

**Purpose**: Automatically create GitHub issues for performance regressions

**Inputs**:
- `<regression_report_file>`: Markdown report from compare_performance.py
- Environment variables:
  - `GITHUB_TOKEN`: GitHub personal access token (or `--token` argument)
  - `GITHUB_REPOSITORY`: Repository in format `owner/repo`

**Environment Setup**:

```bash
# GitHub CLI: Automatically sets GITHUB_TOKEN from `gh auth token`
export GITHUB_TOKEN=$(gh auth token)
export GITHUB_REPOSITORY=$(gh repo view --json nameWithOwner --jq .nameWithOwner)

# Or manually:
export GITHUB_TOKEN=ghp_xxxx
export GITHUB_REPOSITORY=sunbangamen/local-ai-suite
```

**Issue Creation**:

**Critical Failure Issue** (created if failures detected):
- Title: `🚨 Critical Performance Regression Detected (N metrics)`
- Labels: `performance`, `regression`, `automated`, `priority-critical`
- Body: Detailed failure analysis with investigation steps

**Warning Issue** (created if warnings detected):
- Title: `⚠️ Performance Warning (N metrics trending towards regression)`
- Labels: `performance`, `regression`, `automated`
- Body: Monitoring recommendations and helpful commands

**Exit Codes**:
- `0`: Issues created or no regressions detected
- `1`: Error creating issues or GitHub API failure

**Token Scopes Required**:
- `repo`: Full repository access (for issue creation)
- Or minimal: `issues:write` if available

**Generate Token**:
```bash
# GitHub UI: https://github.com/settings/tokens/new
# Scopes: repo, issues:write

# Or use GitHub CLI
gh auth create --web --scopes repo
gh auth token
```

## Workflow Integration

### GitHub Actions

```yaml
# .github/workflows/ci.yml
- name: Run Load Tests
  run: make test-load

- name: Extract Metrics
  run: python scripts/extract_metrics.py locust_stats.csv load-results.json

- name: Compare Performance
  run: python scripts/compare_performance.py docs/performance-baselines.json load-results.json

- name: Create Regression Issues
  if: failure()  # Only if compare_performance exits with 1
  run: python scripts/create_regression_issue.py load-test-results/regression-analysis.md
```

### Local Development

```bash
# 1. Establish baseline from clean/reference run
make test-load-baseline
python scripts/extract_baselines.py load_results_stats.csv docs/performance-baselines.json

# 2. After code changes, run load test
make test-load

# 3. Extract metrics and compare
python scripts/extract_metrics.py load_results_stats.csv load-results.json
python scripts/compare_performance.py docs/performance-baselines.json load-results.json

# 4. If regressions detected, create issue (requires token)
export GITHUB_TOKEN=ghp_xxxx
python scripts/create_regression_issue.py load-test-results/regression-analysis.md
```

## Example Output

### Successful Baseline Creation

```bash
$ python scripts/extract_baselines.py load_results_stats.csv docs/performance-baselines.json

✅ Extracted baseline for api_gateway
✅ Extracted baseline for rag_service
✅ Extracted baseline for mcp_server

✅ Baselines saved to: docs/performance-baselines.json

📊 Extracted 3 service baselines
```

### Regression Detection - No Issues

```bash
$ python scripts/compare_performance.py docs/performance-baselines.json load-results.json

## Performance Regression Analysis

### ✅ Passed (18 metrics within thresholds)

All measured metrics are within acceptable thresholds.

## Summary

- **Total Metrics**: 18
- **Failures**: 0
- **Warnings**: 0
- **Passed**: 18

✅ Report saved to: load-test-results/regression-analysis.md
✅ No critical performance regressions detected
```

### Regression Detection - Critical Failure

```bash
$ python scripts/compare_performance.py docs/performance-baselines.json load-results.json

## Performance Regression Analysis

### ❌ Failures (Action Required)

| Service | Metric | Expected | Current | Change | Impact |
|---------|--------|----------|---------|--------|--------|
| api_gateway | p95_latency_ms | 450 | 900 | +100.0% | ❌ Critical |
| api_gateway | error_rate_pct | 0.5 | 2.0 | +300.0% | ❌ Critical |

## Summary

- **Total Metrics**: 18
- **Failures**: 2
- **Warnings**: 0
- **Passed**: 16

❌ Report saved to: load-test-results/regression-analysis.md
❌ Critical performance regressions detected!

[Exit code: 1]
```

### GitHub Issue Auto-Creation

```bash
$ export GITHUB_TOKEN=ghp_xxxx
$ export GITHUB_REPOSITORY=sunbangamen/local-ai-suite
$ python scripts/create_regression_issue.py load-test-results/regression-analysis.md

📋 Parsing regression report: load-test-results/regression-analysis.md
🚨 Found 2 critical failure(s)
✅ Issue created: https://github.com/sunbangamen/local-ai-suite/issues/125

📊 Summary:
  - Repository: sunbangamen/local-ai-suite
  - Issues created: 1

✅ Issues successfully created:
  - https://github.com/sunbangamen/local-ai-suite/issues/125
```

## Troubleshooting

### Issue: "GITHUB_REPOSITORY environment variable not set"

**Solution**:
```bash
# In GitHub Actions, automatically set
export GITHUB_REPOSITORY=owner/repo

# Or in CI/CD context
export GITHUB_REPOSITORY=$(gh repo view --json nameWithOwner --jq .nameWithOwner)
```

### Issue: "GitHub token not provided"

**Solution**:
```bash
# Set via environment
export GITHUB_TOKEN=ghp_xxxx

# Or pass as argument
python scripts/create_regression_issue.py report.md --token ghp_xxxx

# Or use GitHub CLI
gh auth login
export GITHUB_TOKEN=$(gh auth token)
```

### Issue: "Validation error: already exists"

**Explanation**: An issue with similar title already exists

**Solution**: Close existing issue or wait for manual resolution

### Issue: "Failed to create issue: 403"

**Solution**: Verify token has `repo` or `issues:write` scope
```bash
gh auth status  # Check scopes
```

## Performance Baseline Management

### Initial Baseline Establishment

```bash
# 1. Ensure system is clean/stable
make down-p2 && make up-p2

# 2. Run baseline test (single user, short duration)
make test-load-baseline

# 3. Extract baseline metrics
python scripts/extract_baselines.py load_results_stats.csv docs/performance-baselines.json

# 4. Commit baseline to version control
git add docs/performance-baselines.json
git commit -m "docs: establish performance baseline"
```

### Baseline Update After Optimization

```bash
# 1. Verify optimization is legitimate (not measurement artifact)
# 2. Run load tests multiple times to confirm consistency
# 3. Update baseline
python scripts/extract_baselines.py load_results_stats.csv docs/performance-baselines.json

# 4. Commit with clear rationale
git add docs/performance-baselines.json
git commit -m "docs: update performance baseline after optimization (X% improvement in p95 latency)"
```

### Threshold Tuning

Edit `THRESHOLDS` in `compare_performance.py`:

```python
THRESHOLDS = {
    'api_gateway': [
        ('p95_latency_ms', 0.50),      # 50% increase failure threshold
        ('error_rate_pct', 0.005),      # 0.5% absolute increase failure threshold
        ('rps', -0.30),                 # 30% decrease failure threshold
    ],
    # ... adjust based on tolerance levels
}
```

## Related Documentation

- **Load Testing Guide**: `docs/ops/LOAD_TESTING_GUIDE.md`
- **CI/CD Strategy**: `docs/progress/v1/PHASE_4.2_TEST_SELECTION_STRATEGY.md`
- **Regression Detection Plan**: `docs/progress/v1/PHASE_4.3_REGRESSION_DETECTION.md`
- **Performance Baselines**: `docs/performance-baselines.json`
