# Issue #22 Phase 5: pytest-asyncio 호환성 개선 및 통합 테스트 재실행 계획

**상태**: 📋 계획 수립
**목표**: 67% → 75%+ 커버리지 달성
**의존성**: Phase 4 실패 분석 (8개 통합 테스트 event loop 이슈)
**예상 소요**: 2-3시간

---

## 1. 현재 상황 분석

### Phase 4 실행 결과 (2025-10-22)

```
총 46개 테스트:
├─ ✅ PASSED: 33개 (71.7%) - Unit tests (test_rag.py)
│  └─ 지속적으로 안정적 실행
├─ ❌ FAILED: 8개 (17.4%) - Integration tests (test_rag_integration.py)
│  └─ 모두 동일한 원인: pytest-asyncio fixture scope 이슈
├─ ⏭️ SKIPPED: 5개 (10.9%)
└─ 실행 시간: ~1.5분

커버리지:
├─ 현재: 67% (228/342 statements)
├─ 목표: 74-76%
├─ 미달: -7~9%
└─ 상태: 실용적 최대치 (현 아키텍처로)
```

### 실패 원인 (근본 분석)

```
근본 원인: @pytest_asyncio.fixture(scope="module")
├─ 문제: pytest-asyncio 최신 버전에서 module scope
│        event loop 관리 방식 변경
├─ 증상: RuntimeError: Event loop is closed
├─ 영향: 모든 async fixture 기반 테스트 실패
└─ 영역: 전체 통합 테스트 8개

Code 위치: services/rag/tests/test_rag_integration.py:33, 57, 64
```

### 손실 분석

```
예상 추가 커버리지: +8-10%
├─ Infrastructure (27 lines) 일부
│  └─ _split_sentences_ko(), _sliding_chunks() 호출 경로
├─ Endpoint Error Paths (54 lines) 일부
│  └─ index() 오류 처리 분기
└─ 통합 시나리오: indexing, query, cache, health

현 상태 미커버:
├─ 114 라인 (27+54+33 administrative)
├─ 통합 테스트 미실행으로 인한 손실: ~8-10%
└─ 개선 가능성: 충분함 (fixture 수정으로)
```

---

## 2. 해결 방안 (3가지 옵션)

### Option B.1: Fixture Scope 변경 (권장, 간단)

**변경점**:
```python
# Before (현재)
@pytest_asyncio.fixture(scope="module")
async def client():
    async with httpx.AsyncClient(...) as c:
        yield c

# After (변경)
@pytest_asyncio.fixture(scope="function")
async def client():
    async with httpx.AsyncClient(...) as c:
        yield c
```

**장점**:
- 최소 변경 (2-3줄)
- pytest-asyncio 최신 버전과 호환
- 각 테스트마다 독립적인 event loop

**단점**:
- 약간의 성능 저하 (매 테스트마다 client 재생성)
- 테스트 시간 증가 (1.5분 → 2-3분 예상)

**예상 결과**:
- 8개 통합 테스트 통과 가능성: 85-95%
- 커버리지 상승: +8-10% (목표 75%+ 달성 가능)

---

### Option B.2: AsyncClient Context Manager 직접 사용 (대안)

**변경점**:
```python
# Before (fixture)
@pytest_asyncio.fixture(scope="module")
async def client():
    async with httpx.AsyncClient(...) as c:
        yield c

# After (직접 사용)
@pytest.mark.asyncio
async def test_index_with_real_services():
    async with httpx.AsyncClient(base_url=RAG_API_URL) as client:
        response = await client.post(...)
        assert response.status_code == 200
```

**장점**:
- Fixture 생명주기 문제 완벽 해결
- 가장 안정적
- 테스트별 독립성 최대

**단점**:
- 각 테스트마다 반복 코드 증가
- 코드 변경량 많음 (모든 테스트 수정)

**예상 결과**:
- 8개 통합 테스트 통과: 95%+
- 커버리지 상승: +8-10% (거의 확실)

---

### Option B.3: testcontainers 라이브러리 (고급)

**개념**:
- Docker 컨테이너를 자동으로 관리하는 라이브러리
- 각 테스트마다 격리된 환경 제공

**장점**:
- 가장 격리도 높음
- 프로덕션과 유사한 환경

**단점**:
- 추가 라이브러리 설치 필요
- 초기 설정 복잡
- 테스트 시간 크게 증가 (5-10분)
- ROI 낮음 (Option B.1만으로 충분)

**추천**: Phase 6+ (Low priority)

---

## 3. 구현 계획 (Option B.1 선택 가정)

### Step 1: 코드 수정 (15분)

**파일**: `services/rag/tests/test_rag_integration.py`

**변경**:
```python
# Line 33, 57, 64에서
- @pytest_asyncio.fixture(scope="module")
+ @pytest_asyncio.fixture(scope="function")

# 또는 더 간단하게:
- @pytest_asyncio.fixture(scope="module")
+ @pytest_asyncio.fixture
# (기본값이 function)
```

**검증**:
```bash
# 문법 검사
python -m py_compile services/rag/tests/test_rag_integration.py
```

---

### Step 2: Docker Phase 2 실행 (5분)

```bash
# Phase 2 스택 시작
make up-p2

# 준비 완료 확인
docker compose -f docker/compose.p2.cpu.yml ps
# (모든 서비스 running 상태)
```

---

### Step 3: 수정된 통합 테스트 재실행 (10-20분)

```bash
# 테스트 파일 복사 (수정본)
docker compose -f docker/compose.p2.cpu.yml cp \
  services/rag/tests/test_rag_integration.py \
  rag:/app/tests/

# 통합 테스트 재실행
docker compose -f docker/compose.p2.cpu.yml exec rag \
  python -m pytest tests/test_rag_integration.py -v \
  --tb=short

# 전체 테스트 (unit + integration)
docker compose -f docker/compose.p2.cpu.yml exec rag \
  python -m pytest tests/ -v
```

**예상 결과**:
```
총 46개 테스트:
├─ PASSED: 40-43개 (87-93%) ← 8개 중 5-8개 추가 통과 예상
├─ FAILED: 3-5개 (6-11%) ← 추가 환경 이슈 가능성
└─ SKIPPED: 5개 (10.9%)
```

---

### Step 4: 커버리지 측정 및 리포트 생성 (5분)

```bash
# 커버리지 포함하여 재실행
docker compose -f docker/compose.p2.cpu.yml exec rag \
  python -m pytest tests/ -v \
  --cov=app \
  --cov-report=json \
  --cov-report=html:htmlcov_phase5

# 아티팩트 추출
docker compose -f docker/compose.p2.cpu.yml cp \
  rag:/app/coverage.json /tmp/coverage-rag-phase5.json

docker compose -f docker/compose.p2.cpu.yml cp \
  rag:/app/htmlcov_phase5 /tmp/htmlcov_phase5
```

**기대 커버리지**:
```
Unit Tests (33개): 67% = 228/342
Integration Tests (5-8개 추가): +8-10%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
예상 최종: 75-77% (목표 74-76% 달성!)
```

---

### Step 5: 결과 검증 및 문서화 (20분)

```bash
# JSON 파일 검증
jq '.totals' /tmp/coverage-rag-phase5.json

# HTML 리포트 확인
open /tmp/htmlcov_phase5/index.html
# (새 커버리지 % 표시 확인)

# 아티팩트를 저장소로 이동
cp /tmp/coverage-rag-phase5.json \
  docs/coverage-rag-phase5-integration.json

cp -r /tmp/htmlcov_phase5 \
  docs/coverage-rag-phase5-integration/
```

---

### Step 6: Docker 스택 정리 및 문서 작성 (10분)

```bash
# 스택 정지
make down-p2

# 결과 분석 및 Phase 5 보고서 작성
# docs/progress/v1/ISSUE_22_PHASE_5_EXECUTION_RESULTS.md
```

---

## 4. 성공 기준

### 필수 (Must Have)
- [ ] 8개 통합 테스트 중 ≥5개 통과
- [ ] 전체 테스트 통과율 ≥85%
- [ ] 커버리지 ≥75%
- [ ] 커버리지 JSON/HTML 리포트 생성

### 선택 (Nice to Have)
- [ ] 전체 테스트 통과율 95%+
- [ ] 커버리지 76%+
- [ ] 모든 8개 통합 테스트 통과

### 실패 시 대응
```
만약 통합 테스트가 여전히 실패하면:
├─ Option B.2로 전환 (context manager 직접 사용)
├─ 또는 testcontainers 고려
└─ 또는 현 상태(67%)를 "실용적 최대"로 인정
```

---

## 5. 리스크 및 대응책

| 리스크 | 확률 | 대응 |
|--------|------|------|
| 통합 테스트 여전히 실패 | 중 (30%) | Option B.2 전환 또는 직접 import |
| Event loop 외 다른 오류 | 낮음 (10%) | 개별 테스트 디버깅 |
| 성능 저하 (테스트 시간 2배) | 높음 (70%) | 수용 가능 (2-3분 vs 1.5분) |
| Docker 환경 변경 필요 | 매우낮음 (5%) | 환경 재점검 |

---

## 6. 예상 타임라인

| 단계 | 소요 시간 | 누적 |
|------|----------|------|
| 코드 수정 검토 | 10분 | 10분 |
| Docker 준비 | 5분 | 15분 |
| 통합 테스트 실행 | 15분 | 30분 |
| 커버리지 측정 | 5분 | 35분 |
| 결과 검증 | 10분 | 45분 |
| 문서 작성 | 20분 | 65분 |
| **총 예상** | **~65분** | |

---

## 7. 최종 의사결정 프레임워크

### Phase 5 실행 여부 판단

**"Option B를 수행해야 하나?"** 체크리스트:

- ✅ 목표 미달 (67% vs 74-76%)
- ✅ 실패 원인 명확 (pytest-asyncio fixture scope)
- ✅ 해결 방안 간단 (scope 변경만)
- ✅ 성공 가능성 높음 (85-95%)
- ✅ 소요 시간 적음 (~1시간)
- ✅ 프로덕션 신뢰도 향상

**결론**: **Yes, Phase 5 실행 권장** ✅

---

## 8. 후속 작업

### Phase 5 완료 후
1. 커버리지 재측정 결과 분석
2. 목표 달성 여부 판정
3. 최종 보고서 작성
4. Issue #22 종료 또는 장기 과제로 이관

### 추가 고려 사항
- [ ] Admin 엔드포인트 테스트 (Option C) - Phase 6+
- [ ] MCP/API Gateway 테스트 실행 (선택적)
- [ ] CI/CD 자동화 (Issue #24와 통합)

---

## 📌 최종 권장사항

**진행 방향**: Option B.1 (fixture scope 변경) 강력 권장

**근거**:
1. 최소 변경으로 최대 효과 (2-3줄 코드 수정 → 75%+ 달성)
2. 실패 원인 명확 (fixture scope issue 완전 파악)
3. 성공 가능성 높음 (85-95% 통과율 기대)
4. 시간 효율적 (~1시간 소요)
5. 프로덕션 신뢰도 대폭 향상

**다음 단계**:
1. ✅ Phase 5 계획 승인
2. ⏳ 코드 수정 및 재실행
3. 📊 결과 분석 및 최종 보고

---

**작성자**: Claude Code
**날짜**: 2025-10-22
**상태**: 📋 계획 수립 완료, 실행 대기

**관련 문서**:
- Phase 4 결과: `ISSUE_22_PHASE_4_EXECUTION_RESULTS.md`
- Phase 3 분석: `ISSUE_22_PHASE_3_COVERAGE_VS_RISK_ANALYSIS.md`
- CLAUDE.md 업데이트 필요 (Phase 5 계획 추가)
