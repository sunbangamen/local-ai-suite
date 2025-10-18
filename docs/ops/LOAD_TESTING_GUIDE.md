# Load Testing Guide (Issue #24 Phase 3)

**Date**: 2025-10-17
**Version**: 1.0
**Status**: Ready for execution
**Framework**: Locust v2.20+

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Detailed Execution](#detailed-execution)
5. [Monitoring & Metrics](#monitoring--metrics)
6. [Performance Baselines](#performance-baselines)
7. [Troubleshooting](#troubleshooting)
8. [Results Interpretation](#results-interpretation)

---

## Overview

This guide covers how to execute load tests for Issue #24 Phase 3, which validates performance targets for:
- **API Gateway** (OpenAI-compatible endpoint)
- **RAG Service** (Document retrieval and querying)
- **MCP Server** (Tool execution)

Load tests simulate realistic user behavior with progressive user ramp-up to identify performance bottlenecks.

---

## Prerequisites

### Software Requirements
```bash
# Install Locust and dependencies
pip install locust==2.20.0 fasthttp

# Verify installation
locust --version
```

### System Requirements
- **Docker**: Phase 2 CPU stack running
- **Network**: Access to localhost ports 8000, 8002, 8020
- **Disk Space**: ~1GB for test results and logs
- **GPU Memory**: Monitor with `nvidia-smi` during tests

### Environment Setup
```bash
# Start Phase 2 stack
make up-p2
sleep 10

# Verify services are healthy
curl http://localhost:8000/health  # API Gateway
curl http://localhost:8002/health  # RAG Service
curl http://localhost:8020/health  # MCP Server

# Expected: All return HTTP 200
```

---

## Quick Start

### Baseline Test (2 minutes)
```bash
cd /path/to/issue-24
make test-load-baseline
```

**Expected Output**:
```
Running Locust baseline test (1 user)...
Load test started
Host: http://localhost:8000
Scenarios configured: API Gateway, RAG Service, MCP Server

# After 2 minutes:
Load test completed
Total requests: ~15-20
Total failures: 0
Average response time: 500-800ms
```

### Full Load Test Suite (40 minutes)
```bash
make test-load
```

This runs all three scenarios sequentially:
1. API Gateway (15 minutes)
2. RAG Service (15 minutes)
3. MCP Server (10 minutes)

---

## Detailed Execution

### Test 1: API Gateway Load Testing

**Purpose**: Validate OpenAI API compatibility layer performance

**Command**:
```bash
make test-load-api
```

**Load Profile**:
```
Level 1: 10 users for 5 minutes
  ├─ Spawn rate: 1 user/sec
  ├─ Total requests expected: ~1,500-2,000
  └─ Success rate target: > 99%

Level 2: 50 users for 5 minutes
  ├─ Spawn rate: 5 users/sec
  ├─ Total requests expected: ~5,000-6,000
  └─ Error rate target: < 1%

Level 3: 100 users for 5 minutes
  ├─ Spawn rate: 10 users/sec
  ├─ Total requests expected: ~8,000-10,000
  └─ p95 latency target: < 2.0s
```

**Expected Results**:
| Metric | Baseline | Level 1 | Level 2 | Level 3 |
|--------|----------|---------|---------|---------|
| Avg Latency | 400ms | 450ms | 600ms | 800ms |
| p95 Latency | 600ms | 900ms | 1,200ms | 1,500-2,000ms |
| Error Rate | 0% | < 0.1% | < 1% | < 1% |
| RPS | 3 | 10 | 20 | 35 |

---

### Test 2: RAG Service Load Testing

**Purpose**: Validate document retrieval and query performance

**Command**:
```bash
make test-load-rag
```

**Load Profile**:
```
Level 1: 5 users for 5 minutes
  ├─ Spawn rate: 1 user/sec
  ├─ Operations: 70% query, 30% index
  └─ Expected Qdrant timeouts: 0

Level 2: 25 users for 5 minutes
  ├─ Spawn rate: 3 users/sec
  ├─ Operations: 70% query, 30% index
  └─ Expected database errors: 0

Level 3: 50 users for 5 minutes
  ├─ Spawn rate: 5 users/sec
  ├─ Operations: 70% query, 30% index
  └─ p95 query latency target: < 3.0s
```

**Expected Results**:
| Metric | Baseline | Level 1 | Level 2 | Level 3 |
|--------|----------|---------|---------|---------|
| Query p95 | 800ms | 1,200ms | 2,000ms | 2,500-3,000ms |
| Index p95 | 1,500ms | 2,000ms | 3,000ms | 4,000ms |
| Qdrant Timeout | 0% | 0% | 0% | < 0.1% |
| DB Errors | 0 | 0 | 0 | 0 |

---

### Test 3: MCP Server Load Testing

**Purpose**: Validate MCP tool execution and sandbox isolation

**Command**:
```bash
make test-load-mcp
```

**Load Profile**:
```
Level 1: 5 users for 5 minutes
  ├─ Spawn rate: 1 user/sec
  ├─ Tools: 40% file ops, 40% git, 20% web
  └─ Success rate target: > 99%

Level 2: 20 users for 5 minutes
  ├─ Spawn rate: 2 users/sec
  ├─ Tools: 40% file ops, 40% git, 20% web
  └─ Sandbox violations: 0
```

**Expected Results**:
| Metric | Baseline | Level 1 | Level 2 |
|--------|----------|---------|---------|
| Tool p95 | 1,000ms | 1,500ms | 2,500ms |
| Success Rate | 100% | > 99% | > 99% |
| Sandbox Violations | 0 | 0 | 0 |
| Concurrent Limit Respected | ✓ | ✓ | ✓ |

---

## Monitoring & Metrics

### Live Monitoring During Tests

**Terminal 1: Locust Web UI**
```bash
locust -f tests/load/locustfile.py \
  --host http://localhost:8000 \
  --web -w
# Open: http://localhost:8089
```

**Terminal 2: GPU Monitoring**
```bash
watch -n 1 'nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,utilization.memory --format=csv --loop=1'
```

**Terminal 3: Container Stats**
```bash
docker stats --no-stream
```

**Terminal 4: Grafana Dashboard**
- Navigate to: http://localhost:3001
- Select: "AI Suite Overview" dashboard
- Watch: RPS, latency, error rate in real-time

### Key Metrics to Track

**Response Times**:
- Minimum (fastest response)
- Average (typical response)
- Median (p50 - middle value)
- p95 (95th percentile - near worst-case)
- p99 (99th percentile - extreme case)
- Maximum (slowest response)

**Throughput**:
- Requests Per Second (RPS)
- Total requests processed
- Success vs. failure ratio

**Errors**:
- Connection errors
- Timeout errors
- HTTP error codes (4xx, 5xx)
- Application-specific errors

**Resource Usage**:
- GPU memory (nvidia-smi)
- CPU usage (%)
- Memory usage (%)
- Disk I/O

---

## Performance Baselines

### Baseline Establishment Procedure

```bash
# Step 1: Run single-user test
make test-load-baseline

# Step 2: Capture metrics
# Record the following from Locust output:
# - Average response time
# - p95 latency
# - Error rate
# - Requests per second (RPS)
```

### Sample Baseline Results (1 user)

**API Gateway**:
```
Average response: 400-500ms
p95 latency: 600-800ms
Error rate: 0%
RPS: 2-3
```

**RAG Service**:
```
Query avg response: 800-1,000ms
Query p95 latency: 1,200-1,500ms
Index avg response: 1,500-2,000ms
Error rate: 0%
RPS: 0.5-1
```

**MCP Server**:
```
Tool avg response: 1,000-1,500ms
Tool p95 latency: 1,500-2,000ms
Error rate: 0%
RPS: 0.5-1
Success rate: 100%
```

### Baseline Comparison Strategy

After running load tests at each level, compare against baseline:

```
Performance Degradation Formula:
  Degradation % = ((Current p95 - Baseline p95) / Baseline p95) * 100

Target Degradation:
  Level 1 (10 users): < 50% increase acceptable
  Level 2 (50 users): < 100% increase acceptable
  Level 3 (100 users): < 150% increase acceptable
```

---

## Troubleshooting

### Issue 1: "Phase 2 stack not running"

**Error Message**:
```
❌ Phase 2 stack not running. Start with: make up-p2
```

**Solution**:
```bash
docker compose -f docker/compose.p2.cpu.yml up -d
sleep 10
# Verify
docker ps | grep p2
```

### Issue 2: "Locust not installed"

**Error Message**:
```
❌ Locust not installed. Install: pip install locust
```

**Solution**:
```bash
pip install locust==2.20.0 fasthttp
locust --version
```

### Issue 3: Connection refused on localhost:8000

**Error Message**:
```
ConnectionRefusedError: [Errno 111] Connection refused
```

**Solution**:
```bash
# Check service health
curl http://localhost:8000/health
curl http://localhost:8002/health
curl http://localhost:8020/health

# If unavailable, restart stack
make down
make up-p2
sleep 10
```

### Issue 4: GPU Out Of Memory (OOM)

**Error Message**:
```
CUDA out of memory. Tried to allocate X GB
```

**Solution**:
```bash
# Reduce test load
make test-load-api  # Try with fewer users (10 → 50 only)

# Or restart services with model unloading
make down
make up-p2

# Monitor GPU during test
nvidia-smi --query-gpu=memory.used --format=csv --loop=1
```

### Issue 5: Test hangs/doesn't complete

**Error Message**:
```
Test appears stuck at Level 2 or Level 3
```

**Solution**:
```bash
# Kill stuck Locust process
pkill -f locust

# Restart stack
make down
make up-p2
sleep 10

# Run with shorter duration
locust -f tests/load/locustfile.py APIGatewayUser \
  --host http://localhost:8000 \
  --users 10 --spawn-rate 1 \
  --run-time 1m --headless -q
```

---

## Results Interpretation

### Understanding Locust Output

```
User Count | Response Time | RPS  | Fail % | Error Type
-----------|---------------|------|--------|----------
1          | 450ms avg     | 2.3  | 0%     | None
10         | 580ms avg     | 9.8  | 0.2%   | Timeout
50         | 820ms avg     | 18.5 | 0.8%   | Connection
100        | 1200ms avg    | 25.3 | 1.2%   | Timeout/Error
```

### Performance Targets Evaluation

**Passing Criteria** (All must be true):
- [ ] p95 latency < target (e.g., 2.0s for API Gateway)
- [ ] Error rate < target (e.g., 1% for API Gateway)
- [ ] No cascading failures at max load
- [ ] Resource utilization reasonable (GPU < 95%, CPU < 90%)

**Bottleneck Indicators**:
- ✗ Error rate increasing linearly with user count
- ✗ Latency spikes at specific user thresholds
- ✗ GPU memory approaching 100%
- ✗ Connection pool exhaustion errors
- ✗ Timeout errors at higher loads

### Sample Analysis

**Good Results**:
```
✓ p95 latency increases gradually (linear scaling)
✓ Error rate stays < 1% even at 100 users
✓ No sudden spikes or cascading failures
✓ GPU memory peaks at ~85%, recovers after test
```

**Bottleneck Detected**:
```
✗ Error rate jumps from 0% → 5% at 50 users
✗ p95 latency jumps from 1.2s → 3.5s at 50 users
✗ GPU memory hits 100% at 30 users, then OOM errors
→ Bottleneck: GPU memory exhaustion
```

---

## Next Steps

### After Baseline Establishment
1. Document baseline metrics in `LOAD_TESTING_RESULTS.md`
2. Compare actual vs. target performance
3. Proceed to Phase 3.4 (progressive load tests)
4. If targets met: Proceed to Phase 3.8 documentation
5. If targets not met: Proceed to Phase 3.5 bottleneck analysis

### Phase 3.4 Execution
```bash
make test-load  # Runs all scenarios
# Or individual:
make test-load-api   # API Gateway (15 min)
make test-load-rag   # RAG Service (15 min)
make test-load-mcp   # MCP Server (10 min)
```

---

## References

- **Locust Documentation**: https://docs.locust.io
- **Performance Plan**: `docs/progress/v1/PHASE_3_LOAD_TESTING_PLAN.md`
- **Test Scripts**: `tests/load/locustfile.py`
- **Makefile Targets**: `make test-load*`

---

**Status**: Guide Ready for Phase 3.3-3.4 Execution
**Next**: Run baseline and progressive load tests
**Timeline**: ~11 hours (Phases 3.3-3.6)

