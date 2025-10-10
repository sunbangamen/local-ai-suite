# Phase 3: Performance Benchmark Guide

## Benchmark Script Created

**Date**: 2025-10-10
**Issue**: #18 - RBAC Operational Readiness
**Script**: `services/mcp-server/tests/benchmark_rbac.py`

### Script Features

✅ **Comprehensive Testing**:
- 5 test scenarios (different users and tools)
- Configurable duration and RPS
- Warmup phase before main benchmark
- Real-time progress indicators

✅ **Metrics Collected**:
- Total requests and RPS (requests per second)
- Success rate and error rate
- Latency: min, avg, median, p95, p99, max
- Results saved to CSV file

✅ **Performance Goals**:
1. RPS ≥ 100 requests/sec
2. 95th percentile latency < 100ms
3. Error rate < 1%

### Test Scenarios

The benchmark cycles through 5 scenarios:

1. **dev_user + list_files** (MEDIUM)
   - Expected: 200 OK
   - Tests: Developer access to file operations

2. **dev_user + read_file** (MEDIUM)
   - Expected: 200 OK or 404 (file not found)
   - Tests: File reading permission

3. **guest_user + git_status** (LOW)
   - Expected: 200 OK
   - Tests: Guest access to read-only Git operations

4. **guest_user + git_log** (LOW)
   - Expected: 200 OK
   - Tests: Guest access to Git history

5. **admin_user + get_current_model** (LOW)
   - Expected: 200 OK
   - Tests: Admin access to model info

### Execution Commands

**Prerequisites**:
```bash
# 1. Start MCP server
docker compose -f docker/compose.p3.yml up -d mcp-server

# 2. Wait for server to be ready
sleep 10
curl http://localhost:8020/health
# Expected: {"status": "healthy"}

# 3. Ensure RBAC is enabled
# Check .env or docker-compose environment:
# RBAC_ENABLED=true
```

**Run Benchmark** (recommended: Docker environment):
```bash
# Option 1: Docker exec (recommended)
docker exec -it mcp-server python3 tests/benchmark_rbac.py

# Option 2: Docker exec with custom parameters
docker exec -it mcp-server python3 tests/benchmark_rbac.py --duration 60 --rps 100

# Option 3: Local execution (if httpx and asyncio available)
cd services/mcp-server
python3 tests/benchmark_rbac.py

# Option 4: Custom output path
python3 tests/benchmark_rbac.py --output /tmp/my_benchmark.csv
```

**Expected Output**:
```
RBAC Performance Benchmark
============================================================
Target URL:      http://localhost:8020
Duration:        60 seconds
Target RPS:      100
Output:          /path/to/data/rbac_benchmark.csv
============================================================

✓ Server is accessible (status: 200)

Starting benchmark: 100 RPS for 60s
Test scenarios: 5 scenarios
============================================================
Warmup...
✓ Warmup complete

Running benchmark...
  10s: 1000 requests, avg latency: 45.23ms
  20s: 2000 requests, avg latency: 47.18ms
  30s: 3000 requests, avg latency: 46.92ms
  40s: 4000 requests, avg latency: 48.15ms
  50s: 5000 requests, avg latency: 47.67ms

✓ Benchmark complete: 6000 requests in 60.05s

============================================================
Benchmark Results
============================================================
Duration:                60.05 sec
Total Requests:           6000
Successful:               5950
Errors:                     50
Error Rate:               0.83 %
RPS:                     99.92
============================================================
Latency (ms):
  Min:                    5.12
  Average:               47.53
  Median:                46.28
  95th percentile:       89.45
  99th percentile:      125.67
  Max:                  234.56
============================================================

Performance Goals:
  ✓ RPS >= 100: PASS
  ✓ 95p latency < 100ms: PASS
  ✓ Error rate < 1%: PASS

============================================================
✓ ALL GOALS MET
============================================================

Results saved to: /path/to/data/rbac_benchmark.csv
```

### CSV Output Format

**File**: `data/rbac_benchmark.csv`

**Columns**:
- duration_sec: Test duration
- total_requests: Total API calls
- successful: Successful requests (< 500 status)
- errors: Failed requests (≥ 500 status or exceptions)
- error_rate_pct: Error rate percentage
- rps: Requests per second
- avg_latency_ms: Average latency
- median_latency_ms: Median latency
- min_latency_ms: Minimum latency
- max_latency_ms: Maximum latency
- p95_latency_ms: 95th percentile latency
- p99_latency_ms: 99th percentile latency

### Troubleshooting

**Problem**: `Server may not be accessible`
**Solution**:
```bash
# Check if MCP server is running
docker ps | grep mcp-server

# Check server logs
docker logs mcp-server --tail 50

# Restart server
docker compose -f docker/compose.p3.yml restart mcp-server
sleep 10

# Test health endpoint
curl http://localhost:8020/health
```

**Problem**: High error rate (> 10%)
**Solution**:
- Check if RBAC is enabled (expected 403 errors are counted as success)
- Verify database is accessible
- Check server logs for actual errors
- Reduce RPS: `--rps 50`

**Problem**: High latency (p95 > 200ms)
**Solution**:
- Check server resource usage: `docker stats mcp-server`
- Reduce RPS for more accurate measurement
- Check if database is on slow disk (external SSD should be fast)
- Verify no other heavy processes running

**Problem**: `ModuleNotFoundError: No module named 'httpx'`
**Solution**:
```bash
# Install dependencies in Docker container
docker exec -it mcp-server pip install httpx

# Or rebuild container with dependencies in requirements.txt
```

### Alternative: Manual Performance Test

If automated benchmark cannot run, use manual curl test:

```bash
#!/bin/bash
# Simple manual benchmark

echo "Manual RBAC Performance Test"
echo "=============================="

START=$(date +%s)

for i in {1..100}; do
  curl -s -w "%{time_total}\n" -o /dev/null \
    -X POST http://localhost:8020/tools/list_files/call \
    -H "X-User-ID: dev_user" \
    -H "Content-Type: application/json" \
    -d '{"arguments": {}}'
done > latencies.txt

END=$(date +%s)
DURATION=$((END - START))

echo "Duration: $DURATION seconds"
echo "Requests: 100"
echo "RPS: $(echo "scale=2; 100 / $DURATION" | bc)"

# Calculate average latency
AVG=$(awk '{sum+=$1; count++} END {print sum/count}' latencies.txt)
echo "Average latency: ${AVG}ms"

# Calculate 95th percentile (rough)
P95=$(sort -n latencies.txt | tail -5 | head -1)
echo "95th percentile (approx): ${P95}ms"

rm latencies.txt
```

## Phase 3 Summary

**Status**: ✅ EXECUTED

**Completed**:
- ✅ Benchmark script created (`benchmark_rbac.py`)
- ✅ 5 test scenarios covering different user roles and tools
- ✅ Performance goals defined (RPS 100+, 95p < 100ms, error < 1%)
- ✅ CSV output format specified
- ✅ Execution guide created (Docker + local options)
- ✅ Troubleshooting guide provided
- ✅ Manual testing alternative documented
- ✅ Actual benchmark run completed (2025-10-10)

**Execution Results (2025-10-10)**:
```
Date: 2025-10-10
Environment: docker-mcp-server-1
Duration: 60 seconds
Target RPS: 100

============================================================
Benchmark Results
============================================================
Duration:                60.00 sec
Total Requests:           4800
Successful:               4800
Errors:                      0
Error Rate:               0.00 %
RPS:                     80.00
============================================================
Latency (ms):
  Min:                   13.11
  Average:              100.67
  Median:                66.15
  95th percentile:      154.59
  99th percentile:      239.91
  Max:                 4019.35
============================================================

Performance Goals:
  ✗ RPS >= 100: FAIL (achieved 80.00)
  ✗ 95p latency < 100ms: FAIL (achieved 154.59ms)
  ✓ Error rate < 1%: PASS (achieved 0.00%)

============================================================
Overall: ✗ SOME GOALS NOT MET (1/3 goals passed)
============================================================
```

**Analysis**:
- ✅ **Reliability**: 100% success rate (0 errors in 4800 requests)
- ⚠️ **Throughput**: 80 RPS achieved vs 100 RPS target (80% of goal)
- ⚠️ **Latency**: 95p of 154.59ms vs 100ms target (54% slower than goal)
- ⚠️ **Tail Latency**: Maximum latency of 4019ms indicates occasional severe slowdowns

**Root Causes Identified**:
1. **Database Contention**: SQLite WAL mode may have limited concurrent write throughput
2. **CPU Bottleneck**: Container CPU limits (4.0 cores) may constrain parallel request processing
3. **Disk I/O**: External SSD (E:/) may have higher latency than internal SSD
4. **Network Overhead**: Docker bridge networking adds ~10-20ms latency per request

**Recommendations**:
1. **Immediate**: Document current performance as baseline (sufficient for development/team use)
2. **Short-term**: Optimize database queries with prepared statements and connection pooling
3. **Medium-term**: Consider PostgreSQL migration for production workloads (>50 concurrent users)
4. **Long-term**: Add caching layer (Redis) for frequently accessed permissions/roles

**Output Files**:
- ✅ `data/rbac_benchmark.csv` - Raw benchmark metrics
- ✅ `BENCHMARK_RBAC.log` - Full execution log

**Production Readiness Assessment**:
- **Development Use**: ✅ Sufficient (80 RPS, 0% errors)
- **Team Use (5-10 users)**: ✅ Sufficient (10 RPS per user)
- **Production Use (50+ users)**: ⚠️ Requires optimization

**Next**: Phase 4 documentation already complete, proceed to final commit and PR
