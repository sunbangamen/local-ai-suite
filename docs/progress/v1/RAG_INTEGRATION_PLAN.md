# RAG Integration Tests Plan (Issue #23)

**Created**: 2025-10-13
**Goal**: Raise confidence beyond 67% unit coverage by adding realistic integration scenarios
**Target**: ~75% effective coverage via combined unit + integration evidence

---

## Objective

Current RAG service unit test coverage is **67%** with 22 tests. The missing 33% consists primarily of:
- Database operations (PostgreSQL utilities)
- Complex integration paths (Qdrant + Embedding + LLM)
- Infrastructure code (startup, shutdown, lifecycle)

**Integration tests will validate real-world scenarios** that are difficult or impractical to test with mocks, raising overall confidence to ~75% effective coverage.

---

## Environment Setup

### Prerequisites

**Docker Stack**: Phase 2 Docker Compose environment
```bash
# Start full Phase 2 stack
make up-p2

# Verify all services running
docker compose -f docker/compose.p2.cpu.yml ps

# Expected services:
# - postgres (port 5432)
# - qdrant (port 6333)
# - embedding (port 8003)
# - rag (port 8002)
# - api-gateway (port 8000)
# - inference-chat (port 8001)
# - inference-code (port 8004)
```

### Connection Details

**From `.env` file**:
```bash
# PostgreSQL
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=ai_suite
POSTGRES_USER=ai_user
POSTGRES_PASSWORD=ai_secure_pass

# Qdrant
QDRANT_URL=http://qdrant:6333

# Embedding
EMBEDDING_URL=http://embedding:8003

# API Gateway (LLM)
API_GATEWAY_URL=http://api-gateway:8000
```

**Connection from host**:
```python
# For integration tests running on host
POSTGRES_HOST = "localhost"  # Port forwarded from Docker
QDRANT_URL = "http://localhost:6333"
EMBEDDING_URL = "http://localhost:8003"
RAG_URL = "http://localhost:8002"
```

---

## Data Fixtures

### Fixture Setup Scripts

Create fixture management under `services/rag/tests/fixtures/`:

**1. PostgreSQL Seed Script** (`seed_postgres.py`):
```python
"""
Seed PostgreSQL with test collections and documents
Creates minimal dataset for integration testing
"""
import asyncpg
import asyncio

async def seed_database():
    conn = await asyncpg.connect(
        host="localhost",
        port=5432,
        user="ai_user",
        password="ai_secure_pass",
        database="ai_suite"
    )

    # Create test collection
    await conn.execute("""
        INSERT INTO collections (name, description, created_at)
        VALUES ('test-integration', 'Integration test collection', NOW())
        ON CONFLICT (name) DO NOTHING
    """)

    # Add test documents
    await conn.execute("""
        INSERT INTO documents (collection_id, path, content, indexed_at)
        SELECT c.id, '/test/doc1.txt', 'Test document content', NOW()
        FROM collections c WHERE c.name = 'test-integration'
        ON CONFLICT DO NOTHING
    """)

    await conn.close()
    print("✅ PostgreSQL seeded successfully")

if __name__ == "__main__":
    asyncio.run(seed_database())
```

**2. Qdrant Seed Script** (`seed_qdrant.py`):
```python
"""
Seed Qdrant with test vectors
Creates small collection with sample embeddings
"""
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

def seed_qdrant():
    client = QdrantClient(url="http://localhost:6333")

    collection_name = "test-integration"

    # Create collection if not exists
    try:
        client.get_collection(collection_name)
        print(f"Collection '{collection_name}' already exists")
    except:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )
        print(f"✅ Created collection '{collection_name}'")

    # Add test vectors
    points = [
        PointStruct(
            id=1,
            vector=[0.1] * 384,  # Mock embedding
            payload={"text": "Python file handling", "chunk_id": 1}
        ),
        PointStruct(
            id=2,
            vector=[0.2] * 384,
            payload={"text": "FastAPI endpoints", "chunk_id": 2}
        ),
    ]

    client.upsert(collection_name=collection_name, points=points)
    print(f"✅ Seeded {len(points)} vectors to Qdrant")

if __name__ == "__main__":
    seed_qdrant()
```

**3. Cleanup Script** (`cleanup_fixtures.py`):
```python
"""
Clean up test fixtures after integration tests
"""
import asyncpg
import asyncio
from qdrant_client import QdrantClient

async def cleanup():
    # Clean PostgreSQL
    conn = await asyncpg.connect(
        host="localhost", port=5432,
        user="ai_user", password="ai_secure_pass", database="ai_suite"
    )
    await conn.execute("DELETE FROM collections WHERE name = 'test-integration'")
    await conn.close()
    print("✅ PostgreSQL cleaned")

    # Clean Qdrant
    client = QdrantClient(url="http://localhost:6333")
    try:
        client.delete_collection("test-integration")
        print("✅ Qdrant collection deleted")
    except:
        print("⚠️ Qdrant collection not found (already clean)")

if __name__ == "__main__":
    asyncio.run(cleanup())
```

### Seed Commands

**Setup fixtures**:
```bash
# From project root
cd services/rag/tests/fixtures
python3 seed_postgres.py
python3 seed_qdrant.py
```

**Cleanup fixtures**:
```bash
python3 cleanup_fixtures.py
```

---

## Test Plan (5 Priority Flows)

### Flow 1: Indexing Pipeline End-to-End ✅

**Purpose**: Verify document ingestion from file → chunks → embeddings → Qdrant storage

**Test**: `test_indexing_pipeline_end_to_end`
```python
async def test_indexing_pipeline_end_to_end():
    """
    Test complete indexing flow:
    1. POST /index with document content
    2. Verify chunks created in PostgreSQL
    3. Verify vectors stored in Qdrant
    4. Verify embeddings have correct dimension
    """
    # POST /index
    response = await client.post("/index", json={
        "collection": "test-integration",
        "documents": [{"path": "/test/doc.txt", "content": "Test content"}]
    })
    assert response.status_code == 200

    # Verify PostgreSQL chunks
    chunks = await db.fetch("SELECT * FROM chunks WHERE collection = 'test-integration'")
    assert len(chunks) > 0

    # Verify Qdrant vectors
    qdrant_client = QdrantClient(url="http://localhost:6333")
    vectors = qdrant_client.scroll(collection_name="test-integration", limit=100)
    assert len(vectors[0]) > 0
```

**Coverage Impact**: Lines 137-150 (chunking), 256 (index endpoint)

---

### Flow 2: Query with Embeddings ✅

**Purpose**: Verify query → embedding → vector search → LLM generation

**Test**: `test_query_with_embeddings_flow`
```python
async def test_query_with_embeddings_flow():
    """
    Test complete query flow:
    1. POST /query with user question
    2. Verify embedding service called
    3. Verify Qdrant search executed
    4. Verify LLM called with context
    5. Verify response contains answer
    """
    response = await client.post("/query", json={
        "query": "How to read files in Python?",
        "collection": "test-integration"
    })
    assert response.status_code == 200
    assert "answer" in response.json()
    assert len(response.json()["answer"]) > 0
```

**Coverage Impact**: Lines 470-549 (query pipeline)

---

### Flow 3: Cache Hit / Fallback ✅

**Purpose**: Verify caching behavior and fallback when cache miss

**Test**: `test_cache_hit_and_fallback`
```python
async def test_cache_hit_and_fallback():
    """
    Test query caching:
    1. First query → cache miss → full pipeline
    2. Second identical query → cache hit → fast response
    3. Verify cache statistics
    """
    query = {"query": "Python file handling", "collection": "test-integration"}

    # First query (cache miss)
    start1 = time.time()
    response1 = await client.post("/query", json=query)
    duration1 = time.time() - start1

    # Second query (cache hit)
    start2 = time.time()
    response2 = await client.post("/query", json=query)
    duration2 = time.time() - start2

    assert response1.status_code == 200
    assert response2.status_code == 200
    assert duration2 < duration1 * 0.5  # Cache should be significantly faster
```

**Coverage Impact**: Lines 383-411 (cache logic)

---

### Flow 4: LLM Timeout Handling ✅

**Purpose**: Verify graceful degradation when LLM times out

**Test**: `test_llm_timeout_handling`
```python
async def test_llm_timeout_handling():
    """
    Test LLM timeout behavior:
    1. Configure short timeout (1 second)
    2. POST /query
    3. Verify timeout error handled gracefully
    4. Verify 503 status with Retry-After header
    """
    # Use mock LLM that sleeps for 5 seconds
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = asyncio.TimeoutError()

        response = await client.post("/query", json={
            "query": "Test query",
            "collection": "test-integration"
        })

        assert response.status_code == 503
        assert "Retry-After" in response.headers
```

**Coverage Impact**: Lines 586 (timeout handling), 214 (error responses)

---

### Flow 5: Health Checks with Dependency Degradation ✅

**Purpose**: Verify health endpoint reports degraded state correctly

**Test**: `test_health_dependency_degradation`
```python
async def test_health_dependency_degradation():
    """
    Test health check with failing dependencies:
    1. GET /health with all services up → healthy
    2. Stop Qdrant container → degraded
    3. Stop Embedding container → degraded
    4. Verify status and dependency details
    """
    # All services healthy
    response1 = await client.get("/health")
    assert response1.status_code == 200
    assert response1.json()["ok"] == True

    # Simulate Qdrant failure
    with patch("qdrant_client.QdrantClient.get_collections") as mock_qdrant:
        mock_qdrant.side_effect = Exception("Connection refused")

        response2 = await client.get("/health")
        assert response2.status_code == 200
        assert response2.json()["ok"] == False
        assert "qdrant" in response2.json()["dependencies"]
```

**Coverage Impact**: Lines 338-355 (health checks), 454 (dependency validation)

---

## Implementation Steps

### Step 1: Create Integration Test Structure

```bash
services/rag/tests/
├── fixtures/
│   ├── __init__.py
│   ├── seed_postgres.py
│   ├── seed_qdrant.py
│   └── cleanup_fixtures.py
├── integration/
│   ├── __init__.py
│   ├── conftest.py          # Pytest fixtures for live services
│   ├── test_indexing.py     # Flow 1
│   ├── test_query.py        # Flow 2
│   ├── test_cache.py        # Flow 3
│   ├── test_timeout.py      # Flow 4
│   └── test_health.py       # Flow 5
└── test_rag.py              # Existing unit tests
```

### Step 2: Configure Pytest Fixtures (`conftest.py`)

```python
import pytest
import httpx
from qdrant_client import QdrantClient
import asyncpg

@pytest.fixture(scope="session")
async def rag_client():
    """HTTP client for RAG service"""
    async with httpx.AsyncClient(base_url="http://localhost:8002") as client:
        yield client

@pytest.fixture(scope="session")
async def db_conn():
    """PostgreSQL connection"""
    conn = await asyncpg.connect(
        host="localhost", port=5432,
        user="ai_user", password="ai_secure_pass", database="ai_suite"
    )
    yield conn
    await conn.close()

@pytest.fixture(scope="session")
def qdrant_client():
    """Qdrant client"""
    return QdrantClient(url="http://localhost:6333")

@pytest.fixture(autouse=True)
async def setup_teardown():
    """Run seed before tests, cleanup after"""
    # Seed fixtures
    await seed_postgres()
    seed_qdrant()

    yield

    # Cleanup
    await cleanup_fixtures()
```

### Step 3: Implement Tests

Create 5 test files (one per flow) with realistic scenarios using live services.

**Mock Strategy**:
- ✅ Use real PostgreSQL, Qdrant, Embedding services
- ⚠️ Mock external LLM only if API Gateway unavailable
- ✅ Use actual Docker containers for all internal services

### Step 4: Handle LLM Dependency

**Option A: Use Real API Gateway** (Preferred)
```python
# No mocking needed, use real inference-chat/code servers
response = await client.post("/query", json={"query": "test"})
```

**Option B: Mock LLM for CI**
```python
# Only if API Gateway unavailable in CI
with patch("httpx.AsyncClient.post") as mock_llm:
    mock_llm.return_value.json.return_value = {"answer": "Mock answer"}
    response = await client.post("/query", json={"query": "test"})
```

---

## Automation

### Make Target

Add to `Makefile`:
```makefile
.PHONY: test-rag-integration
test-rag-integration:
	@echo "Running RAG integration tests..."
	@echo "Prerequisites: Docker Phase 2 stack must be running (make up-p2)"
	cd services/rag/tests/fixtures && python3 seed_postgres.py && python3 seed_qdrant.py
	pytest services/rag/tests/integration/ -v --tb=short
	cd services/rag/tests/fixtures && python3 cleanup_fixtures.py
	@echo "✅ Integration tests complete"
```

**Usage**:
```bash
# Start environment
make up-p2

# Run integration tests
make test-rag-integration

# Run with coverage
make test-rag-integration PYTEST_ARGS="--cov=services/rag --cov-report=term"
```

---

## CI Integration

### Manual Run Until Pipelines Ready

**GitHub Actions Checklist** (TODO for CI/CD):
- [ ] Add job: `test-rag-integration`
- [ ] Requires: Docker Phase 2 stack running
- [ ] Run: `make test-rag-integration`
- [ ] Upload: Coverage reports as artifacts

**Current Approach**: Manual local execution
```bash
# Developer workflow
make up-p2                    # Start services
make test-rag-integration     # Run tests
make down                     # Stop services
```

---

## Documentation Updates

### CLAUDE.md Updates

Add section under "Testing Infrastructure":
```markdown
### Integration Testing Strategy

**RAG Service**: Combined unit (67%) + integration tests (~75% effective)
- Unit tests: 22 tests, mock-based, fast execution
- Integration tests: 5 tests, live services, realistic scenarios
- Coverage: Unit 67% + Integration 8% = 75% effective confidence

**Integration Test Flows**:
1. Indexing pipeline (document → chunks → vectors)
2. Query with embeddings (search → LLM → answer)
3. Cache hit/fallback behavior
4. LLM timeout handling
5. Health checks with degraded dependencies

**Run**: `make test-rag-integration` (requires `make up-p2`)
```

### New Artifacts

Track in documentation:
- `docs/progress/v1/RAG_INTEGRATION_PLAN.md` (this file)
- `services/rag/tests/fixtures/` (seed scripts)
- `services/rag/tests/integration/` (test suite)
- Coverage reports: `docs/rag_integration_coverage.json`

---

## Issue #23 Tracking

### Title
**"Increase RAG reliability via integration tests"**

### Prerequisites
- ✅ Issue #22 complete (unit tests established)
- ✅ Docker Phase 2 stack operational
- ✅ PostgreSQL + Qdrant + Embedding services running
- ✅ Fixture seed scripts created

### Deliverables
1. **Integration test suite**: 5 tests covering priority flows
2. **Fixture management**: Seed/cleanup scripts for PostgreSQL + Qdrant
3. **Make target**: `make test-rag-integration` automation
4. **Documentation**: Integration plan, CLAUDE.md updates, coverage reports
5. **Coverage goal**: ~75% effective confidence (67% unit + 8% integration)

### Acceptance Criteria
- [ ] All 5 integration tests pass (green)
- [ ] Fixture seed/cleanup works reliably
- [ ] Make target executes successfully
- [ ] CLAUDE.md updated with integration strategy
- [ ] Coverage artifacts saved to docs/
- [ ] Issue #23 closed with summary report

### Estimated Effort
- **Fixture scripts**: 1 hour
- **Integration tests**: 3-4 hours (5 tests, realistic scenarios)
- **Make target + docs**: 1 hour
- **Total**: ~5-6 hours

### Priority
**LOW** - Current 67% unit coverage already covers critical paths. Integration tests add confidence for production reliability but not blocking for development.

---

## Success Metrics

### Before Integration Tests
- **Unit Coverage**: 67% (22 tests)
- **Confidence**: Medium (mocked dependencies)
- **Scenarios**: Limited to isolated units

### After Integration Tests
- **Effective Coverage**: ~75% (22 unit + 5 integration)
- **Confidence**: High (real services validated)
- **Scenarios**: End-to-end flows tested

### Key Indicators
- ✅ All critical flows validated end-to-end
- ✅ Real PostgreSQL + Qdrant + Embedding integration confirmed
- ✅ Timeout and error handling verified with live services
- ✅ Health checks validate actual dependency state

---

## Timeline

| Phase | Duration | Activities |
|-------|----------|-----------|
| **Week 1** | 2 hours | Create fixture scripts, test structure |
| **Week 1** | 3 hours | Implement 5 integration tests |
| **Week 1** | 1 hour | Make target, documentation updates |
| **Week 2** | - | Review, fix issues, measure coverage |

**Target Completion**: 1-2 weeks (5-6 hours active work)

---

## Risk Mitigation

### Risk 1: Docker Services Not Running
**Mitigation**: Add prerequisite check in Make target
```makefile
test-rag-integration:
	@docker compose -f docker/compose.p2.cpu.yml ps | grep -q "Up" || \
		(echo "❌ Docker services not running. Run: make up-p2" && exit 1)
```

### Risk 2: Fixture Conflicts
**Mitigation**: Use unique collection names, cleanup after each test

### Risk 3: LLM Unavailable in CI
**Mitigation**: Mock LLM responses for CI, use real services locally

### Risk 4: Slow Test Execution
**Mitigation**: Run integration tests separately from unit tests, accept slower execution for higher confidence

---

## Conclusion

Integration tests will raise RAG service confidence from 67% (unit only) to ~75% (unit + integration), validating:
- ✅ Real database operations
- ✅ Multi-service integration paths
- ✅ Timeout and error handling with live dependencies
- ✅ End-to-end data flows

**Status**: Ready for implementation (Issue #23)
**Prerequisites**: Issue #22 complete ✅
**Estimated Effort**: 5-6 hours
**Priority**: LOW (optional quality improvement)

---

**Created**: 2025-10-13
**Author**: Claude Code (Issue #23 Planning)
**Related**: Issue #22 (Test Coverage Improvement)
