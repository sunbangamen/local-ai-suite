# Embedding Service Missing Lines Checklist (81% Coverage)

**Date**: 2025-10-13
**Coverage**: 81% (88 statements, 17 missing)
**Status**: ✅ 80% target achieved

---

## Summary

**Total Missing**: 17 lines across 5 functions
**Target**: 80% coverage ✅ ACHIEVED (81%)

Missing lines from `/tmp/embedding_final_coverage.log:53`:
```
app.py: 53-58, 65-68, 85-89, 165-166, 170-172
```

---

## Missing Lines Breakdown

### 1. `_load_model()` - Lines 53-58 (6 lines) ❌ NOT COVERED

**Function Code**:
```python
def _load_model(model_name: str) -> TextEmbedding:
    kwargs: Dict[str, Any] = {}              # Line 53 ❌
    if CACHE_DIR:                            # Line 54 ❌
        kwargs["cache_dir"] = CACHE_DIR      # Line 55 ❌
    if NUM_THREADS and NUM_THREADS > 0:      # Line 56 ❌
        kwargs["threads"] = NUM_THREADS      # Line 57 ❌
    return TextEmbedding(model_name=model_name, **kwargs)  # Line 58 ❌
```

**Why Not Covered**:
- Mocked in all tests via `app_with_mocks` fixture
- Real TextEmbedding initialization takes ~5s
- Mocking required for fast unit tests

**To Cover**:
- [ ] Remove mock and allow real TextEmbedding loading
- [ ] Accept 5s+ test execution time
- [ ] OR: Move to integration tests

**Priority**: ⬇️ LOW (performance tradeoff)

---

### 2. `_ensure_model()` - Lines 65, 67-68 (3 lines) ⚠️ PARTIALLY COVERED (40%)

**Function Code**:
```python
def _ensure_model() -> None:
    global _model, _model_name, _model_dim
    with _model_lock:                        # ✅ Covered
        if _model is None:                   # ✅ Covered
            _model = _load_model(_model_name)          # Line 65 ❌ (calls mocked function)
            # 차원 파악: 짧은 텍스트 한 개 임베딩
            sample = list(_model.embed(["dimension probe"], batch_size=1, normalize=NORMALIZE))  # Line 67 ❌
            _model_dim = len(sample[0])      # Line 68 ❌
```

**Why Not Covered**:
- Lines 65, 67-68: Model loading and dimension probing
- Requires unmocking `_load_model()`
- Dimension probing depends on real model

**To Cover**:
- [ ] Unmock `_load_model()` in specific test
- [ ] Allow real embedding generation for dimension check
- [ ] Accept slower test execution

**Priority**: ⬇️ LOW (requires real model)

---

### 3. `on_startup()` - Lines 85-89 (4 lines) ❌ NOT COVERED

**Function Code**:
```python
@app.on_event("startup")
def on_startup():
    # 지연 로딩이지만, 초기 스타트업 시도(캐시/네트워크 미리 당기기 용)
    try:                                     # Line 85 ❌
        _ensure_model()                      # Line 86 ❌
    except Exception:                        # Line 87 ❌
        # 모델 캐시 다운로드가 늦거나 오프라인일 수 있으므로 실패해도 서비스는 기동
        pass                                 # Line 89 ❌
```

**Why Not Covered**:
- FastAPI lifecycle hook (`@app.on_event("startup")`)
- Never triggered in test environment
- Tests use direct endpoint calls, not full app startup

**To Cover**:
- [ ] Use TestClient with `lifespan` context manager
- [ ] Test full FastAPI application lifecycle
- [ ] Verify graceful failure on model load error

**Priority**: ⬇️ LOW (infrastructure code, graceful failure design)

**Note**: FastAPI deprecated `@app.on_event`, recommends lifespan handlers

---

### 4. `prewarm()` - Lines 165-166 (2 lines) ❌ NOT COVERED

**Function Code**:
```python
@app.post("/prewarm")
def prewarm():
    """프리워밍: 모델 로딩 및 캐시 준비"""
    _ensure_model()                          # Line 165 ❌
    return {"ok": True, "model": _model_name, "dim": _model_dim}  # Line 166 ❌
```

**Why Not Covered**:
- `/prewarm` endpoint never called in tests
- Similar to `on_startup`: preloads model cache

**To Cover**:
- [ ] Add simple test: `client.post("/prewarm")`
- [ ] Verify response format
- [ ] Check model initialization

**Priority**: ⬆️ MEDIUM-LOW (trivial to add, ~5 minutes)

**Impact**: Would increase coverage to ~83%

---

### 5. `__main__` - Lines 170, 172 (2 lines) ❌ NOT COVERED

**Function Code**:
```python
if __name__ == "__main__":
    import uvicorn                           # Line 170 ❌

    uvicorn.run(app, host="0.0.0.0", port=8003)  # Line 172 ❌
```

**Why Not Covered**:
- Script entry point
- Only runs when `app.py` executed directly
- Not relevant for API testing

**To Cover**:
- N/A (not applicable for unit tests)

**Priority**: ❌ N/A (script entry point)

---

## Coverage Target Analysis

### Current State: 81% ✅
- **Covered**: 71/88 lines
- **Missing**: 17/88 lines
- **Target**: 80% ✅ EXCEEDED by 1%

### To Reach Higher Coverage

#### 83% Coverage (+2 lines, +2%)
**Effort**: ~5 minutes
**Actions**:
- [ ] Add `test_prewarm_endpoint()` to call `/prewarm`
- [ ] Verify response: `{"ok": True, "model": "...", "dim": 384}`

**Pros**: Easy win, shows endpoint completeness
**Cons**: Low value, prewarm is infrastructure code

---

#### 87% Coverage (+6 lines, +6%)
**Effort**: ~15 minutes
**Actions**:
- [ ] Add `/prewarm` test (+2 lines)
- [ ] Add FastAPI lifespan test for `on_startup()` (+4 lines)
  - Use TestClient with lifespan context
  - Mock `_ensure_model()` to raise exception
  - Verify app starts despite failure

**Pros**: Tests infrastructure paths
**Cons**: Still doesn't cover real model loading

---

#### 97% Coverage (+16 lines, +16%)
**Effort**: 1+ hour
**Actions**:
- [ ] Add `/prewarm` test (+2 lines)
- [ ] Add lifespan test (+4 lines)
- [ ] Unmock `_load_model()` in integration test (+6 lines)
- [ ] Unmock `_ensure_model()` dimension probing (+3 lines)
- [ ] Accept 5s+ test execution time

**Pros**: Near-complete coverage
**Cons**:
- Requires real TextEmbedding model loading
- Slow test suite (5s+ per test)
- Better suited for integration tests

---

## Recommendation

### ✅ ACCEPT 81% as Excellent Unit Test Coverage

**Reasoning**:
1. **Target Achieved**: 81% exceeds 80% target by 1%
2. **Critical Paths Covered**: 100% for health/embed/reload endpoints
3. **Fast Tests**: 18 tests in <1s (0.94s)
4. **Infrastructure Intentionally Uncovered**: Lifecycle hooks, model loading mocked
5. **Practical Maximum**: Further coverage requires integration tests or performance sacrifice

**Missing 19% Breakdown**:
- 6 lines: `_load_model()` - Mocked for performance (5s → <1s)
- 3 lines: `_ensure_model()` - Mocked dimension probing
- 4 lines: `on_startup()` - Lifecycle hook, graceful failure
- 2 lines: `prewarm()` - Infrastructure endpoint (trivial to add)
- 2 lines: `__main__` - Script entry (N/A)

---

## Test Coverage by Function

| Function | Statements | Covered | Missing | Coverage | Status |
|----------|-----------|---------|---------|----------|--------|
| `health()` | 6 | 6 | 0 | 100% | ✅ Fully covered |
| `embed()` | 10 | 10 | 0 | 100% | ✅ Fully covered |
| `reload_model()` | 10 | 10 | 0 | 100% | ✅ Fully covered |
| `_load_model()` | 6 | 0 | 6 | 0% | ❌ Mocked |
| `_ensure_model()` | 5 | 2 | 3 | 40% | ⚠️ Partial |
| `on_startup()` | 4 | 0 | 4 | 0% | ❌ Lifecycle |
| `prewarm()` | 2 | 0 | 2 | 0% | ❌ Not tested |
| `__main__` | 2 | 0 | 2 | 0% | ❌ Script entry |

---

## Evidence Files

### Coverage Artifacts (All in `docs/`)
1. ✅ `embedding_final_coverage.log` (3.3KB) - Terminal output
2. ✅ `embedding_final_coverage.json` (14KB) - Machine-readable data
3. ✅ `.coverage_embedding_final` (52KB) - Binary database
4. ✅ `embedding_final_coverage_analysis.txt` (7.2KB) - Detailed analysis
5. ✅ `coverage_embedding.json` (14KB) - Phase 1 measurement

### Phase Reports
1. ✅ `docs/progress/v1/PHASE_1_COVERAGE_MEASUREMENT.md` (8.2KB)
2. ✅ `docs/progress/v1/PHASE_2.2_EMBEDDING_COMPLETE.md` (15KB)

---

## Conclusion

✅ **81% coverage confirmed** via pytest-cov measurement
✅ **All artifacts saved** to `docs/` directory
✅ **Target exceeded** by 1% (80% → 81%)
✅ **Documentation complete** with missing line analysis

**Status**: Issue #22 Phase 2.2 (Embedding) ✅ COMPLETE

**Next**: Decide on RAG service approach (currently 67%, -13% from target)

---

**Generated**: 2025-10-13
**Tool**: pytest-cov 7.0.0
**Environment**: Docker Compose Phase 2 CPU
