## Performance Regression Analysis

### ❌ Failures (Action Required)

| Service | Metric | Expected | Current | Change | Impact |
|---------|--------|----------|---------|--------|--------|
| api_gateway | error_rate_pct | 0.33 | 1.0 | +203.0% | ❌ Critical |
| rag_service | error_rate_pct | 0.0 | 0.33 | ∞ | ❌ Critical |

### ✅ Passed (2 metrics within thresholds)

All measured metrics are within acceptable thresholds.

## Summary

- **Total Metrics**: 4
- **Failures**: 2
- **Warnings**: 0
- **Passed**: 2
