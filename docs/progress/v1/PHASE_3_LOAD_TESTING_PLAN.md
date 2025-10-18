# Phase 3: Load Testing Infrastructure (Issue #24)

**Date**: 2025-10-17
**Status**: 🚀 In Progress - Phase 3.1 (Scenario Design)
**Goal**: Establish Locust-based performance testing with bottleneck identification
**Timeline**: ~3 working days (22 hours)
**Success Criteria**: 3 load scenarios operational, 80%+ performance targets met

---

## 1. Phase 3 Overview

### Objectives
- Design 3 load test scenarios (API Gateway, RAG, MCP)
- Establish baseline performance metrics
- Identify and document 3+ performance bottlenecks
- Apply optimizations to meet 80%+ of targets
- Create complete load testing infrastructure

### Performance Targets

| Component | Metric | Target | Acceptance (80%) |
|-----------|--------|--------|------------------|
| **API Gateway** | p95 latency | < 2.0s | < 2.5s |
| **API Gateway** | Error rate | < 1% | < 1.2% |
| **RAG Service** | p95 latency | < 3.0s | < 3.75s |
| **RAG Service** | Qdrant timeout | < 0.1% | < 0.125% |
| **MCP Server** | p95 latency | < 5.0s | < 6.25s |
| **MCP Server** | Sandbox violations | 0 | 0 |

---

## 2. Phase 3.1: Load Test Scenario Design

### Scenario 1: API Gateway Testing
**Purpose**: Validate OpenAI API compatibility layer under sustained load

**Load Profile**:
- **User Ramp**: 0 → 10 → 50 → 100 users (progressive)
- **Request Type**: Chat completions (POST /v1/chat/completions)
- **Request Pattern**:
  ```json
  {
    "model": "qwen2.5-14b-instruct",
    "messages": [{"role": "user", "content": "Explain Python decorators"}],
    "max_tokens": 150,
    "temperature": 0.7
  }
  ```
- **Think Time**: 2-5 seconds between requests (realistic user behavior)
- **Duration**: 5 minutes per load level

**Success Metrics**:
- Average response time: < 1.5s
- p95 latency: < 2.0s
- Error rate: < 1%
- Throughput: > 10 RPS at 100 users

**User Task Weighting**:
- Chat completions: 70%
- Model listing: 20%
- Health checks: 10%

---

### Scenario 2: RAG Service Testing
**Purpose**: Validate document indexing and query performance

**Load Profile**:
- **User Ramp**: 0 → 5 → 25 → 50 users
- **Request Types**:
  - Index documents (POST /index) - 30% of requests
  - Query RAG (POST /query) - 70% of requests
- **Query Patterns**:
  ```json
  {
    "query": "How do I optimize Python code for GPU computing?",
    "collection": "default",
    "top_k": 5
  }
  ```
- **Think Time**: 3-8 seconds (research-like behavior)
- **Duration**: 5 minutes per load level

**Success Metrics**:
- Query p95 latency: < 3.0s
- Index p95 latency: < 5.0s
- Qdrant timeout percentage: < 0.1%
- Database connection errors: 0
- Vector search failures: 0

**User Task Weighting**:
- Query operations: 70%
- Index operations: 30%

---

### Scenario 3: MCP Server Testing
**Purpose**: Validate MCP tool execution under sustained requests

**Load Profile**:
- **User Ramp**: 0 → 5 → 20 users
- **Tool Mix**:
  - File operations (read/write): 40%
  - Git commands (status/log): 40%
  - Web scraping: 20%
- **Request Examples**:
  ```json
  {
    "tool": "read_file",
    "args": {"file_path": "./services/rag/app.py"}
  }
  ```
- **Think Time**: 2-6 seconds
- **Duration**: 5 minutes per load level

**Success Metrics**:
- Tool execution p95 latency: < 5.0s
- Sandbox violations: 0
- Command execution success: > 99%
- Concurrent tool execution limit: respected

**User Task Weighting**:
- File operations: 40%
- Git commands: 40%
- Web tools: 20%

---

## 3. Performance Baseline Specification

### Metrics to Capture (Per Test Run)

**Response Time Metrics**:
- Minimum (ms)
- Average (ms)
- Median (p50, ms)
- p95 (ms)
- p99 (ms)
- Maximum (ms)

**Throughput Metrics**:
- Requests Per Second (RPS)
- Requests Per Minute (RPM)
- Total requests processed

**Error Metrics**:
- Error count (total)
- Error rate (%)
- Error types (timeout, connection, validation)
- Failed assertions

**Resource Metrics**:
- GPU memory usage (MB, via nvidia-smi)
- CPU usage (%)
- Memory usage (%)
- Disk I/O (IOPS)

**Service-Specific Metrics**:
- Qdrant operation success rate (%)
- Database query success rate (%)
- MCP tool execution success rate (%)

---

## 4. Baseline Establishment Procedure

### Environment Setup

```bash
# 1. Start Phase 2 CPU stack with monitoring
make up-p2
sleep 10

# 2. Verify all services healthy
curl http://localhost:8000/health  # API Gateway
curl http://localhost:8002/health  # RAG
curl http://localhost:8020/health  # MCP

# 3. Open Grafana dashboard
# Navigate to: http://localhost:3001
# Select: "AI Suite Overview" dashboard
```

### Baseline Test Execution

```bash
# 1. Run API Gateway scenario (no load)
locust -f tests/load/locustfile.py \
  --host http://localhost:8000 \
  --users 1 --spawn-rate 1 \
  --run-time 2m \
  --headless

# 2. Capture baseline metrics
# Expected: 1 user, ~1 RPS, <500ms avg response

# 3. Document baseline in PHASE_3_LOAD_TESTING_RESULTS.md
```

---

## 5. Load Test Execution Strategy

### Progressive Load Testing (Staged Approach)

```
Level 1 (10 users):    5 min
  ↓
Level 2 (50 users):    5 min
  ↓
Level 3 (100 users):   5 min
  ↓
Duration Stress:       15 min at max load
```

### Monitoring During Tests

**Live Monitoring**:
```bash
# Terminal 1: Locust web UI
locust -f tests/load/locustfile.py \
  --host http://localhost:8000 \
  --web -w

# Terminal 2: GPU monitoring
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,utilization.memory \
  --format=csv --loop=1

# Terminal 3: Docker stats
docker stats
```

**Grafana Dashboard**:
- Real-time throughput (RPS)
- API latency distribution
- Error rate trends
- GPU memory usage
- CPU/Memory trends

---

## 6. Bottleneck Analysis Framework

### Expected Bottlenecks (Priority Order)

**High Probability (Phase 2 Configuration)**:
1. **GPU Memory Exhaustion** (RTX 4050 6GB limit)
   - Symptom: OOM errors at >50 concurrent users
   - Indicator: GPU memory 95%+
   - Root cause: Both chat-7b + code-7b models loaded

2. **Qdrant Timeout Under Load**
   - Symptom: Search operations fail with timeout
   - Indicator: >0.5% timeout rate at 50+ users
   - Root cause: Connection pool exhaustion

3. **LLM Context Processing Latency**
   - Symptom: p95 latency >3s for RAG queries
   - Indicator: 2000-3000ms processing time
   - Root cause: Token processing on CPU during GPU memory pressure

**Medium Probability**:
4. **Database Connection Pool Exhaustion**
   - Symptom: "Too many connections" PostgreSQL error
   - Indicator: Connection refused at 30+ concurrent
   - Root cause: Default pool size too small

5. **Qdrant Vector Search Performance**
   - Symptom: Vector similarity search slow at large collection
   - Indicator: Search time >500ms for 1000+ vectors
   - Root cause: Collection size or index optimization

6. **MCP Tool Execution Serialization**
   - Symptom: Tool execution queues up (no parallel execution)
   - Indicator: Tool latency increases linearly with user count
   - Root cause: Single-threaded execution model

---

## 7. Optimization Strategies

### GPU Memory Optimization
```python
# Strategy 1: Selective Model Loading
# Load only chat-7b by default, code-7b on demand
# Expected impact: -2GB GPU memory, enables 50+ concurrent

# Strategy 2: Model Offloading
# Unload code-7b during peak load, swap on demand
# Expected impact: Reduce max memory usage
# Trade-off: Slower code model responses

# Strategy 3: Batch Processing
# Batch multiple requests for LLM inference
# Expected impact: +30% throughput, +20% latency
```

### Qdrant Connection Management
```python
# Current: Default connection pool (10 connections)
# Optimization: Increase to 30-50 connections
# Implementation: Update docker-compose.yml QDRANT_VECTOR_POOL_SIZE
# Expected impact: Support 50+ concurrent users
```

### Database Connection Pool
```python
# Current: SQLAlchemy default (5 pool_size)
# Optimization: Increase pool_size to 20, pool_pre_ping=True
# Implementation: Update RAG service environment config
# Expected impact: Support 30+ concurrent DB operations
```

---

## 8. Success Criteria Checklist

### Phase 3.1 (Scenario Design) ✅

**Deliverables**:
- [x] 3 load test scenarios defined with specifications
- [x] Performance targets documented (section 2)
- [x] Baseline metrics identified (section 3)
- [x] Execution procedures defined (section 4)
- [x] Bottleneck analysis framework created (section 6)

### Phase 3.2 (Implementation) - Pending

- [ ] `tests/load/locustfile.py` created with all 3 scenarios
- [ ] Load tasks properly weighted per scenario
- [ ] Error handling and validation
- [ ] Local test execution verified (1 user baseline)

### Phase 3.3 (Baseline) - Pending

- [ ] Baseline metrics captured for all 3 scenarios
- [ ] Results documented in spreadsheet or JSON
- [ ] Grafana dashboard configured for monitoring
- [ ] Baseline comparison ready for optimization

### Phase 3.4-3.6 (Execution & Optimization) - Pending

- [ ] Load tests at 10, 50, 100 users completed
- [ ] 3+ bottlenecks identified and documented
- [ ] Optimization strategies applied
- [ ] 80%+ performance targets achieved

---

## 9. Risk Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| GPU OOM during load tests | High | Critical | Monitor nvidia-smi, reduce max users to 50 |
| Qdrant timeout cascade | Medium | High | Implement retry with exponential backoff |
| Database connection errors | Medium | Medium | Enable connection pooling, pre-ping |
| Test environment instability | Medium | Medium | Auto-restart services on error, use health checks |
| Load test process hanging | Low | High | Set hard timeout (600s), implement graceful shutdown |

---

## 10. Next Steps

### Phase 3.1 ✅ Complete
- Load test scenarios designed
- Performance targets established
- Bottleneck framework created

### Phase 3.2 (Next: ~4 hours)
- Implement `tests/load/locustfile.py`
- Create 3 user behavior classes
- Write task definitions with proper weighting
- Test with 1 user baseline

### Phase 3.3 (Following: ~2 hours)
- Establish baseline metrics (1 user → 10 users)
- Capture baseline in documentation
- Prepare for load test execution

### Phase 3.4-3.6 (Final: ~11 hours)
- Run progressive load tests
- Analyze results and identify bottlenecks
- Apply optimizations
- Document findings

---

**Status**: Phase 3.1 Design Complete ✅
**Next Milestone**: Phase 3.2 Implementation (Locust scripts)
**Target Completion**: 3 working days (Phase 3 total)

