## Performance Regression Analysis

### ❌ Failures (Action Required)

| Service | Metric | Expected | Current | Change | Impact |
|---------|--------|----------|---------|--------|--------|
| api_gateway | error_rate_pct | 0.5 | 0.8 | +60.0% | ❌ Critical |
| api_gateway | rps | 50.0 | 48.0 | -4.0% | ❌ Critical |
| rag_service | error_rate_pct | 0.4 | 1.0 | +150.0% | ❌ Critical |
| mcp_server | error_rate_pct | 0.0 | 0.33 | ∞ | ❌ Critical |

### ✅ Passed (1 metrics within thresholds)

All measured metrics are within acceptable thresholds.

## Summary

- **Total Metrics**: 5
- **Failures**: 4
- **Warnings**: 0
- **Passed**: 1
