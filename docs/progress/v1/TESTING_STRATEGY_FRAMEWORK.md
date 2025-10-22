# Testing Strategy Framework for AI Suite (2025-10-22)

**Status**: 📋 **STRATEGIC GUIDANCE**
**Scope**: Unit tests, integration tests, coverage goals
**Audience**: Developers, QA, DevOps

---

## Executive Summary

This framework provides decision criteria for choosing between unit tests, integration tests, and acceptance tests, based on lessons learned from Issue #22 Phase 2-3.

### The Central Principle

> **Better design enables high coverage with fewer tests. Conversely, complex integration surfaces often require different test types.**

**Corollary**: Coverage % is a symptom, not the goal. Goal is **confidence in reliability**.

---

## Part 1: Test Type Decision Matrix

### When to Use UNIT TESTS (Mock-based)

**Criteria**:
✅ Function has clear input/output contract
✅ Function logic is deterministic
✅ Function dependencies can be mocked
✅ Execution is <100ms
✅ No external system calls

**Services in Project**:
- ✅ **Embedding** (FastAPI + FastEmbed): Excellent fit
  - Clear contract: texts → embeddings
  - Mockable: FastEmbed, file I/O
  - Fast: 10-100ms per batch
  - Result: 84.5% unit test coverage, 100% critical paths

**Coverage Target**: 70-90%

**Example**:
```python
def test_embed_with_truncation():
    """Unit test: MAX_CHARS limit enforced"""
    req = EmbedRequest(texts=["x" * 9000])  # > MAX_CHARS
    resp = embed(req)
    assert len(resp.embeddings[0]) > 0  # Should succeed (truncated)
```

---

### When to Use INTEGRATION TESTS (Live Services)

**Criteria**:
✅ Function orchestrates multiple services
✅ External system behavior is important
✅ Mocking would hide real issues
✅ Failure modes include network/timeout
✅ Can tolerate 1-10 second execution

**Services in Project**:
- ⚠️ **RAG** (Qdrant + Embedding + LLM): Needs integration tests
  - Orchestrates: Indexing (Embedding + Qdrant + DB)
  - Critical: Qdrant connection, retry logic
  - Failure modes: Timeout, connection refused, storage full
  - Result: 66.7% unit coverage, but 78 lines are integration-only

**Coverage Target**: 70-80% (combined with unit tests)

**Example**:
```python
@pytest.mark.integration
async def test_index_with_qdrant_timeout(qdrant_service_down):
    """Integration test: Handle Qdrant connection timeout"""
    # qdrant_service_down fixture stops Qdrant container
    with pytest.raises(HTTPException) as exc:
        await index(IndexRequest(collection="test"))
    assert exc.value.status_code == 503  # Should return 503
    # Verify retry attempts were made
    assert mock_qdrant.call_count >= 3
```

---

### When to Use END-TO-END TESTS (Full Scenario)

**Criteria**:
✅ Testing user-facing workflow
✅ Multiple services involved in sequence
✅ Business logic is critical
✅ Can tolerate 10+ second execution
✅ Test must be reproducible

**Services in Project**:
- ⚠️ **RAG Query** (Index → Query → LLM Answer)
  - User sees: "Upload docs, ask question, get answer"
  - Critical: Full pipeline works
  - Test: Create collection → Index docs → Query → Verify answer

**Coverage Target**: Not coverage %, but "scenario passing %"

**Example**:
```python
@pytest.mark.e2e
async def test_rag_query_workflow(docker_phase2_up):
    """E2E test: Upload docs, index, query, get answer"""
    # 1. Create collection
    resp = await index(IndexRequest(collection="e2e_test"))
    assert resp.chunks > 0

    # 2. Query
    resp = await query(QueryRequest(
        query="What is the main topic?",
        collection="e2e_test"
    ))
    assert len(resp.answer) > 0
    assert len(resp.context) > 0
```

---

## Part 2: Coverage Goals by Service Type

### Service Classification

```
SIMPLE SERVICES (Single responsibility)
├─ Embedding Service
├─ API Gateway (if stateless)
└─ Health Check Service
   └── Unit Test Coverage Goal: 80-90%
   └── Justification: Few dependencies, high fan-in/low fan-out

COMPLEX SERVICES (Multiple responsibilities)
├─ RAG Service
├─ MCP Server
└─ CLI tools
   └── Unit Test Coverage Goal: 60-70%
   └── Integration Test Coverage: 70-80%
   └── Combined Effective Coverage: 75-85%

INFRASTRUCTURE (Platform concerns)
├─ Docker Compose
├─ Kubernetes manifests
├─ CI/CD pipelines
├─ Database migrations
   └── Test Approach: Infrastructure-as-code testing
   └── Coverage Goal: 100% (declarative, not calculated %)
```

### AI Suite Service Classification

| Service | Type | Unit Goal | Integration | Combined | Recommendation |
|---------|------|-----------|-------------|----------|-----------------|
| Embedding | SIMPLE | **85%** | N/A | **85%** | ✅ Current: 84.5% (DONE) |
| RAG | COMPLEX | **67%** | **75%** | **74%** | ⚠️ Current: 66.7% (Need integration) |
| MCP | COMPLEX | **60%** | **70%** | **70%** | ⏳ Not started |
| API Gateway | COMPLEX | **65%** | **70%** | **70%** | ⏳ Not started |

---

## Part 3: Mock vs Integration Decision Framework

### Decision Tree

```
Does the function have external dependencies?
├─ NO → Unit test with mocks of collaborators
│   └─ Example: Embedding._load_model()
│       (even if mocking FastEmbed, still unit)
│
└─ YES → Ask: "Is mocking realistic?"
    ├─ YES (mock behavior matches reality)
    │   └─ Example: LLM timeout
    │       Mock: sleep(5), raise Timeout
    │       Unit test approach OK (with timeout=5 fixture)
    │
    └─ NO (mock would hide real issues)
        └─ Example: Qdrant connection failures
            Real: Network retry, exponential backoff
            Mock cannot replicate
            └─ Use integration test (docker-compose, real service)
```

### RAG Service: Specific Decision

**Indexing Endpoint**:
- Mock Qdrant? ❌ NO
  - Real behavior: connection retry, batch size limits, network timeouts
  - Mock hides: slow networks, storage failures, partial writes
  - Risk: Code works in test, fails in production under load

- Solution: ✅ Integration test with real Qdrant
  - Docker-compose Phase 2: Real Qdrant container
  - Can test: Connection failures, slow operations, data consistency
  - Result: Higher confidence

---

## Part 4: Practical Implementation Guide

### Unit Test Pattern: Input Validation

```python
class TestEmbedValidation(TestCase):
    """Test input validation (always unit test)"""

    def test_empty_texts(self):
        """Empty input → empty output"""
        req = EmbedRequest(texts=[])
        resp = embed(req)
        assert resp.embeddings == []
        assert resp.dim == _model_dim

    def test_max_texts_truncation(self):
        """Truncate to MAX_TEXTS"""
        req = EmbedRequest(texts=["text"] * (MAX_TEXTS + 100))
        resp = embed(req)
        assert len(resp.embeddings) == MAX_TEXTS

    def test_max_chars_per_text(self):
        """Truncate each text to MAX_CHARS"""
        req = EmbedRequest(texts=["x" * (MAX_CHARS + 100)])
        resp = embed(req)
        # Text should be truncated
        assert len(resp.embeddings) == 1
```

**Why unit test?**
- No external service needed
- Can run offline
- Fast (< 100ms)
- Clear pass/fail
- High ROI (catches common errors)

---

### Unit Test Pattern: Error Handling

```python
class TestRagErrorHandling(TestCase):
    """Test error paths (mostly unit, some mocked integration)"""

    @mock.patch('qdrant.get_collections')
    def test_health_qdrant_failure(self, mock_qdrant):
        """Health check: Qdrant connection failure"""
        mock_qdrant.side_effect = Exception("Connection refused")
        resp = health()
        assert resp["status"] == "unhealthy"
        assert "Connection" in resp["reason"]

    @mock.patch('httpx.post')  # Mock LLM API
    def test_query_llm_timeout(self, mock_post):
        """Query: LLM timeout → return error"""
        mock_post.side_effect = httpx.TimeoutException()
        req = QueryRequest(query="test")
        with pytest.raises(HTTPException) as exc:
            query(req)
        assert exc.value.status_code == 504  # Gateway Timeout
```

**Why unit test with mocks?**
- Real error behavior: timeout, connection refused, etc.
- Mock replicates: `side_effect`, exception types
- Fast: no waiting for real timeout
- Comprehensive: test all error branches

**Note**: This is "unit test with realistic mocks," different from mocking Qdrant entirely.

---

### Integration Test Pattern: Full Workflow

```python
@pytest.mark.integration
class TestRagIntegration:
    """Test with real Docker Phase 2 services"""

    @pytest.fixture(scope="class")
    def docker_phase2(self):
        """Start Docker Phase 2 stack"""
        import subprocess
        subprocess.run(["docker-compose", "-f", "docker/compose.p2.cpu.yml",
                       "up", "-d"], check=True)
        time.sleep(5)  # Wait for services
        yield
        subprocess.run(["docker-compose", "-f", "docker/compose.p2.cpu.yml",
                       "down"], check=True)

    def test_index_with_real_qdrant(self, docker_phase2):
        """Index documents with real Qdrant"""
        # Real indexing: read docs → chunk → embed → Qdrant store
        resp = index(IndexRequest(collection="integration_test"))

        # Verify: Qdrant actually has points
        collection_info = qdrant.get_collection("integration_test")
        assert collection_info.points_count > 0

    def test_query_with_real_qdrant(self, docker_phase2):
        """Query with real vector search"""
        # Real query: embedding → Qdrant search → LLM answer
        resp = query(QueryRequest(query="test question",
                                 collection="integration_test"))
        assert len(resp.context) > 0
        assert len(resp.answer) > 0
```

**Why integration test?**
- Real services: Qdrant, Embedding, LLM
- Real failure scenarios: timeout, connection loss
- Real data flow: index documents → query → answer
- Confidence: "This works in production-like environment"

**Trade-off**: Slower (5-30 seconds), requires Docker, but catches real issues

---

## Part 5: Maintenance Strategy

### Test Decay Prevention

**Problem**: As code evolves, tests become outdated, creating false confidence.

**Prevention**:

1. **Annual Coverage Review** (Q4 2025)
   - Run: `coverage report -m` for each service
   - Update: Missing line analysis (like Phase 3)
   - Decide: Test new features, or accept coverage plateau?

2. **Breaking Change Testing**
   - When refactoring services, rerun integration tests
   - Example: If changing Qdrant upsert logic, run `test_index_with_real_qdrant`
   - Cost: 30 minutes, benefit: prevent regression

3. **Production Incident → Test**
   - When bugs found in production, add test case
   - Example: "Qdrant upsert timeout not retried" → add test
   - Prevent: Same bug happening again

### Test Cost Management

**Challenge**: Integration tests are slow (Docker startup takes 10-30 seconds)

**Solution**: Layered CI/CD

```
CI Pipeline:
├─ Fast (unit tests): Run on every commit, < 2 min
│  └─ service: pytest services/*/tests/test_*.py -m "not integration"
│
├─ Slow (integration tests): Run nightly, 15-30 min
│  └─ service: make test-rag-integration (Phase 4)
│
└─ E2E (full scenario): Run weekly, 30-60 min
   └─ service: E2E tests with real deployment
```

**Budget**:
- Fast unit tests: Free (every commit)
- Integration tests: 10-20 min/day (nightly)
- E2E tests: 30-60 min/week

---

## Part 6: Issue #22 Application

### What We Learned

| Lesson | Applied | Result |
|--------|---------|--------|
| Unit tests plateau at 66-85% | Accept limits | RAG 66.7% OK, not a failure |
| Complex systems need integration | Plan Phase 4 | RAG integration tests 1-2 weeks |
| Good design = fewer tests | Prefer simplicity | Embedding achieved 84.5%, not 90% |
| Coverage % ≠ reliability | Focus on critical paths | RAG query/health 90%+ OK |
| Env variables need parametrization | Low priority | Skip custom config tests |

### Application to Other Services

**MCP Server** (planned, not yet tested):
- Type: COMPLEX (multiple tools: file, git, web, notion)
- Unit test goal: 65-70% (focus on common tools)
- Integration test goal: 75-80% (focus on tool orchestration)
- Strategy: Start with unit tests, add integration if time permits

**API Gateway** (in progress):
- Type: COMPLEX (multi-service routing)
- Unit test goal: 70-75% (logic & validation)
- Integration test goal: 75-80% (failover & fallback)
- Strategy: Unit tests now, integration tests in Phase 4

---

## Part 7: Success Metrics

### Metric 1: Coverage by Risk Level

Not all coverage % is equal. Distinguish:

```
CRITICAL PATH COVERAGE (>90% target)
├─ User-facing functionality
├─ Example: RAG query endpoint (96%), Embedding embed endpoint (100%)
└─ Metric: Critical coverage % (not total)

NORMAL PATH COVERAGE (70-85% target)
├─ Standard operations
├─ Example: RAG index endpoint (partial)
└─ Metric: Total coverage %

EDGE CASE COVERAGE (40-70% OK)
├─ Error handling, timeouts, retries
├─ Example: RAG health errors, Embedding config options
└─ Metric: Edge case coverage % (less critical)
```

**AI Suite Metrics**:
```
Embedding Service:
├─ Critical path: 100% ✅
├─ Normal path: 84.5% ✅
└─ Edge case: 60% OK

RAG Service:
├─ Critical path: 96% ✅
├─ Normal path: 66.7% ⚠️ (needs integration)
└─ Edge case: 40% OK
```

### Metric 2: Test Execution Time

```
Goal: < 2 minutes for unit tests (CI/CD friendly)

AI Suite (actual):
- Embedding tests: 15 seconds ✅
- RAG tests: 45 seconds ✅
- Combined: 60 seconds ✅

Integration tests (separate):
- RAG integration: 5-10 min ⏳
- E2E tests: 15-30 min ⏳
```

### Metric 3: Production Confidence

**Confidence Scoring**:

```
RAG Service (after Phase 4):
├─ Unit test: 66.7% → Confidence: 60% (handles happy path)
├─ Integration test: 74% → Confidence: 80% (handles failures)
├─ Combined: 70% → Confidence: 75% (realistic)
└─ Production ready? YES with caveats (monitor in production)

Embedding Service (now):
├─ Unit test: 84.5% → Confidence: 85% (very good design)
├─ Critical path: 100% → Confidence: 95% (all main flows)
└─ Production ready? YES, immediately
```

---

## Part 8: Conclusion & Next Steps

### Key Takeaway

> **Pursue "sufficient confidence," not "100% coverage."**

- Embedding: 84.5% is sufficient (move to production)
- RAG: 66.7% is not sufficient (add integration tests)
- MCP: Plan integration tests from start (learn from RAG)

### Recommended Actions

**Immediate** (Today):
1. ✅ Review this framework (30 min)
2. ✅ Share with team (30 min)
3. ✅ Update CLAUDE.md with Phase 3 findings (1 hour)

**Near-term** (Next 1-2 weeks):
1. Decide: RAG integration tests? (decision point)
2. If YES: Start Phase 4 integration test planning
3. If NO: Document known limitations, proceed to production with monitoring

**Medium-term** (Next month):
1. Complete any chosen integration tests
2. Establish CI/CD pipeline with test layers
3. Setup production monitoring for untested paths
4. Quarterly: Review coverage trends

### Framework Maintenance

This document should be reviewed/updated:
- ✅ Quarterly (Q1, Q2, Q3, Q4)
- ✅ When new service added
- ✅ When major test failure occurs
- ✅ When coverage goals change

---

## Appendix: Quick Reference

### Unit Test Checklist

```
Before writing tests, ask:
☐ Does function depend on external services? (Qdrant, LLM, DB, etc.)
  ├─ YES: Can you mock it realistically?
  │  ├─ YES: Mock it, use unit test
  │  └─ NO: Use integration test
  └─ NO: Write unit test
☐ Is execution < 100ms?
☐ Can test run offline?
☐ Have you identified 3-5 interesting test cases?
```

### Integration Test Checklist

```
Before writing integration tests, ask:
☐ Does test require real external services?
☐ Is execution time acceptable (< 10 sec)?
☐ Can you start/stop services in CI/CD?
☐ Have you written unit tests for same logic first?
☐ Does integration test add new insights beyond unit tests?
```

### Coverage Goals by Service

| Service | Unit Target | Integration | Combined | Timeline |
|---------|-----------|-------------|----------|----------|
| Embedding | 85% | N/A | 85% | Done |
| RAG | 67% | 75% | 75% | Phase 4 (1-2 weeks) |
| MCP | 65% | 70% | 70% | TBD |
| API Gateway | 70% | 75% | 75% | TBD |

---

**Document Version**: 1.0 (2025-10-22)
**Next Review**: 2025-12-31 (Q4 2025)

