# Memory System Improvements Log

코덱스 피드백 반영 및 개선 사항 기록

---

## 2025-09-30: Qdrant 동기화 로직 통일 및 성능 검증

### 🔧 개선 사항

#### 1. Qdrant 헬퍼 함수 분리 및 통일 (✅ 완료)

**문제점**:
- `memory_maintainer.py`와 `memory_system.py`가 각각 독립적인 Qdrant 접근 로직 보유
- 컬렉션 이름 생성 규칙 불일치 가능성
- 페이로드 구조 차이로 인한 데이터 불일치
- 코드 중복

**해결 방법**:
```python
# scripts/memory_utils.py에 공통 함수 추가

def get_collection_name(project_id: str) -> str:
    """통일된 컬렉션 이름 생성: memory_{project_id[:8]}"""
    return f"memory_{project_id[:8]}"

def ensure_qdrant_collection(project_id, qdrant_url, vector_size=384, distance="Cosine"):
    """Qdrant 컬렉션 존재 확인 및 생성 (공통 함수)"""
    # 구현...

def upsert_to_qdrant(project_id, points, qdrant_url):
    """Qdrant 배치 업로드 (공통 함수)"""
    # 구현...

def build_qdrant_payload(conversation_id, user_query, ai_response, ...):
    """통일된 Qdrant 페이로드 생성"""
    return {
        "conversation_id": conversation_id,
        "user_query": user_query[:500],
        "ai_response": ai_response[:1000],
        "model_used": model_used or "unknown",
        "importance_score": importance_score,
        "created_at": created_at or datetime.now().isoformat()
    }
```

**변경 파일**:
- `scripts/memory_utils.py`: 공통 헬퍼 함수 추가 (130줄)
- `scripts/memory_maintainer.py`: 공통 함수 사용으로 변경
  - `sync_to_qdrant()`: 정확한 컬럼명 사용, 배치 업로드
  - `run_qdrant_sync()`: 공통 헬퍼 함수 호출
  - `ensure_qdrant_collection()`: 제거 (공통 함수로 대체)

**효과**:
- ✅ 컬렉션 이름 규칙 통일 (`memory_{project_id[:8]}`)
- ✅ 페이로드 구조 통일 (6개 필드 표준화)
- ✅ 코드 중복 제거 (~50줄 감소)
- ✅ 유지보수성 향상

---

#### 2. memory_maintainer.py 동기화 로직 수정 (✅ 완료)

**문제점**:
- SELECT 구문에서 존재하지 않는 컬럼 참조 (`c.content`, `c.model_type`)
- 실제 스키마와 불일치
  - 실제: `c.user_query`, `c.ai_response`, `c.model_used`
  - 기존 코드: `c.content`, `c.model_type`

**해결 방법**:
```python
# 수정 전 (잘못된 컬럼)
SELECT ce.*, c.content, c.model_type, c.importance_score
FROM conversation_embeddings ce
JOIN conversations c ON ce.conversation_id = c.id

# 수정 후 (정확한 컬럼 + Row factory)
conn.row_factory = sqlite3.Row  # 딕셔너리 형태 접근

SELECT
    ce.id as embedding_id,
    ce.conversation_id,
    ce.embedding_vector,
    ce.created_at as embedding_created_at,
    c.user_query,           # 정확한 컬럼명
    c.ai_response,          # 정확한 컬럼명
    c.model_used,           # 정확한 컬럼명
    c.importance_score,
    c.created_at
FROM conversation_embeddings ce
JOIN conversations c ON ce.conversation_id = c.id
WHERE ce.sync_status != 'synced' OR ce.sync_status IS NULL
LIMIT 100
```

**변경 내용**:
- `sqlite3.Row` factory 사용으로 컬럼 이름 접근
- 배치 업로드로 전환 (개별 → 배치)
- 공통 헬퍼 함수로 페이로드 생성
- Qdrant point ID를 `conversation_id`로 통일

**효과**:
- ✅ 스키마 에러 해결
- ✅ 동기화 성능 향상 (배치 업로드)
- ✅ 페이로드 구조 일관성 확보

---

#### 3. 성능 벤치마크 스크립트 작성 (✅ 완료)

**목적**:
- 100만개 대화 저장/검색 성능 검증
- 1초 내 검색 응답 목표 달성 여부 확인
- 하이브리드 검색 (FTS5 + 벡터) 동작 검증

**구현**:
```bash
# scripts/benchmark_memory_perf.py

# 기본 테스트 (1,000개)
python scripts/benchmark_memory_perf.py --size 1000

# 대규모 테스트 (100만개, ~1시간 소요)
python scripts/benchmark_memory_perf.py --full

# 출력 예시:
# [Benchmark 1] 대화 저장 성능 (1,000개)
# ✅ 저장 완료:
#    총 시간: 12.34초
#    평균 저장 시간: 12.34ms/conversation
#    처리량: 81.0 conversations/sec
#
# [Benchmark 2] FTS5 검색 성능 (100개 쿼리)
# ✅ 검색 완료:
#    평균 검색 시간: 45.67ms
#    P95 검색 시간: 89.12ms
#    목표 달성 여부: ✅ PASS (목표: < 1000ms)
```

**벤치마크 항목**:
1. **저장 성능**: 대량 대화 저장 속도
2. **FTS5 검색**: 전문 검색 응답 시간 (평균, P95, P99)
3. **벡터 검색**: 임베딩 생성 + 유사도 검색
4. **하이브리드 검색**: FTS5 + 벡터 결합 검색
5. **통계 조회**: 메타데이터 집계 성능

**결과 저장**:
- JSON 형식으로 자동 저장
- `/tmp/memory_benchmark_YYYYMMDD_HHMMSS.json`

**효과**:
- ✅ 성능 목표 달성 여부 자동 검증
- ✅ 회귀 테스트 가능
- ✅ CI/CD 통합 가능

---

### 📊 개선 전후 비교

| 항목 | 개선 전 | 개선 후 | 효과 |
|------|---------|---------|------|
| Qdrant 헬퍼 중복 | 2곳 (maintainer, memory_system) | 1곳 (memory_utils) | 유지보수성 ↑ |
| 컬렉션 이름 규칙 | 불일치 가능성 | 통일 (`memory_{project_id[:8]}`) | 버그 방지 |
| 페이로드 구조 | 불일치 가능성 | 6필드 표준화 | 일관성 확보 |
| 동기화 로직 | 컬럼 에러 | 정확한 스키마 | 동작 안정성 ↑ |
| 성능 검증 | 수동 테스트 | 자동화 벤치마크 | 회귀 방지 |

---

### 🧪 테스트 방법

#### 1. Qdrant 동기화 테스트

```bash
# Memory maintainer 테스트 (수동)
python scripts/memory_maintainer.py

# 로그 확인
tail -f /mnt/e/ai-data/memory/logs/memory_maintainer.log
```

#### 2. 성능 벤치마크 실행

```bash
# 소규모 테스트 (1,000개, ~15초)
python scripts/benchmark_memory_perf.py --size 1000

# 중규모 테스트 (10,000개, ~2분)
python scripts/benchmark_memory_perf.py --size 10000

# 대규모 테스트 (100만개, ~1시간)
python scripts/benchmark_memory_perf.py --full
```

#### 3. 통합 테스트

```bash
# 기존 통합 테스트 실행
python tests/test_memory_integration.py
```

---

### 📝 추가 개선 제안 (향후)

#### A. 테스트 스키마 수정 (Pending)

**문제점**:
- `tests/memory/test_qdrant_failure.py`의 mock 스키마가 실제 스키마와 불일치
- `schedule` 의존성 문제

**해결 방안**:
```python
# tests/memory/test_qdrant_failure.py 수정 필요

# Mock 스키마 수정
mock_conversations = [
    {
        'conversation_id': 1,
        'user_query': 'test query',    # content → user_query
        'ai_response': 'test response',  # 추가
        'model_used': 'chat-7b',       # model_type → model_used
        'importance_score': 5,
        'created_at': datetime.now().isoformat()
    }
]

# schedule 의존성 처리
try:
    import schedule
    SCHEDULE_AVAILABLE = True
except ImportError:
    SCHEDULE_AVAILABLE = False
    pytest.skip("schedule not available")
```

#### B. CI/CD 통합 (Pending)

```yaml
# .github/workflows/memory-tests.yml (예시)

name: Memory System Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      qdrant:
        image: qdrant/qdrant:latest
        ports:
          - 6333:6333

    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run integration tests
        run: python tests/test_memory_integration.py

      - name: Run benchmark (small)
        run: python scripts/benchmark_memory_perf.py --size 100
```

#### C. 모니터링 대시보드 (Pending)

- Grafana + Prometheus 통합
- 실시간 메모리 사용량, 검색 지연, 동기화 상태 모니터링

---

### ✅ 완료 체크리스트

- [x] Qdrant 헬퍼 함수 분리 (`memory_utils.py`)
- [x] `memory_maintainer.py` 동기화 로직 수정
- [x] 컬렉션 이름 규칙 통일
- [x] 페이로드 구조 표준화
- [x] 성능 벤치마크 스크립트 작성
- [x] 개선 사항 문서화
- [x] 테스트 스키마 수정 (2025-09-30 완료)
- [x] schedule 의존성 모킹 (2025-09-30 완료)
- [x] 테스트 환경 변수 설정 (2025-09-30 완료)
- [ ] CI/CD 통합 (향후)
- [ ] 모니터링 대시보드 (향후)

---

### 📚 관련 문서

- [Memory System Documentation](./MEMORY_SYSTEM.md)
- [Implementation Summary](./IMPLEMENTATION_SUMMARY.md)
- [Test Results](./MEMORY_SYSTEM_TEST_RESULTS.md) - 향후 추가 예정

---

**작성일**: 2025-09-30
**작성자**: @sunbangamen (코덱스 피드백 반영)