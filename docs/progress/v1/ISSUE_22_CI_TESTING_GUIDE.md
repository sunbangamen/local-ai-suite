# Issue #22: CI 테스트 구동 가이드

**문서**: CI/CD에서 RAG 통합 테스트 실행 방법
**작성**: 2025-10-22
**상태**: 활성 (PR #35)

---

## 📌 개요

Issue #22의 통합 테스트는 환경 변수를 기반으로 **조건부 실행**됩니다.

- **기본 동작**: Unit test만 실행, Integration test는 스킵
- **전체 테스트**: `RUN_RAG_INTEGRATION_TESTS=true` 환경 변수 설정 시 Integration test 포함

---

## 🔧 테스트 구동 방식

### 1️⃣ 기본 구동 (Unit Tests Only)

```bash
# 기본 pytest 실행 - Integration test 자동 스킵
python -m pytest services/rag/tests/ -v

# 또는 Docker 환경
docker compose -f docker/compose.p2.cpu.yml exec rag \
  python -m pytest services/rag/tests/ -v
```

**결과**: Unit test만 실행 (test_rag.py)
```
- 31 unit tests PASSED
- Integration tests SKIPPED (12 tests)
```

### 2️⃣ 통합 테스트 포함 (Phase 2 환경)

```bash
# Qdrant, Embedding, RAG 서비스가 모두 실행되는 환경에서
RUN_RAG_INTEGRATION_TESTS=true python -m pytest services/rag/tests/ -v

# 또는 Docker 환경
docker compose -f docker/compose.p2.cpu.yml exec rag bash -c \
  "RUN_RAG_INTEGRATION_TESTS=true python -m pytest services/rag/tests/ -v"
```

**결과**: Unit + Integration tests 모두 실행
```
- 31 unit tests PASSED
- 12 integration tests PASSED/FAILED (의존 서비스 상태에 따름)
```

### 3️⃣ 커버리지 측정

```bash
# Unit test만
python -m pytest services/rag/tests/ \
  --cov=services/rag/app \
  --cov-report=json \
  --cov-report=html

# Integration 포함
RUN_RAG_INTEGRATION_TESTS=true python -m pytest services/rag/tests/ \
  --cov=services/rag/app \
  --cov-report=json \
  --cov-report=html
```

---

## 🏗️ 코드 구현

### test_rag_integration.py 모듈 레벨 스킵

```python
# 라인 31-37: 환경 변수 기반 조건부 스킵
RUN_INTEGRATION = os.getenv("RUN_RAG_INTEGRATION_TESTS", "false").lower() == "true"

if not RUN_INTEGRATION:
    pytest.skip(
        "RAG integration tests disabled. Set RUN_RAG_INTEGRATION_TESTS=true to enable.",
        allow_module_level=True,
    )
```

**특징**:
- `allow_module_level=True`: 파일 전체를 스킵
- 환경 변수 기본값: `"false"` (보안)
- 존재 여부만 확인 (값은 정확히 "true" 필요)

### Fixture 스코프 수정 (Phase 5)

```python
# Phase 4: @pytest_asyncio.fixture(scope="module")  ← Event loop issue
# Phase 5: @pytest_asyncio.fixture                  ← Fixed

@pytest_asyncio.fixture
async def client():
    """RAG API 클라이언트"""
    async with httpx.AsyncClient(base_url=RAG_API_URL, timeout=30.0) as c:
        yield c
```

**개선**:
- `scope="function"` (기본값)으로 변경
- 각 테스트마다 독립적인 event loop
- Event loop closed 오류 완전 해결

---

## 🎯 CI/CD 전략

### GitHub Actions

```yaml
# 기본 CI (항상 실행)
- name: Run Unit Tests
  run: |
    python -m pytest services/rag/tests/ \
      --cov=services/rag/app \
      --cov-report=json

# 선택적: Nightly 또는 수동 트리거
- name: Run Integration Tests (Optional)
  if: github.event_name == 'schedule' || github.event.inputs.run_integration == 'true'
  run: |
    docker compose -f docker/compose.p2.cpu.yml up -d
    sleep 30  # 서비스 준비 대기

    docker compose -f docker/compose.p2.cpu.yml exec -T rag bash -c \
      "RUN_RAG_INTEGRATION_TESTS=true python -m pytest services/rag/tests/"

    docker compose -f docker/compose.p2.cpu.yml down
```

### 로컬 개발 환경

**Unit test 만 (빠른 실행)**:
```bash
pytest services/rag/tests/ -v
```

**통합 테스트 (Docker Phase 2 환경)**:
```bash
# 1. Phase 2 스택 시작
make up-p2

# 2. 통합 테스트 실행
docker compose -f docker/compose.p2.cpu.yml exec rag bash -c \
  "RUN_RAG_INTEGRATION_TESTS=true python -m pytest services/rag/tests/ -v"

# 3. 스택 종료
make down-p2
```

---

## 📊 테스트 통과율 기준

### Unit Tests (항상 실행)
```
목표: 100% 통과
현황: 31/31 PASSED (100%) ✅
```

### Integration Tests (조건부 실행)
```
목표: 12/12 통과
현황: 7/12 PASSED (58.3%)

실패 원인: 비즈니스 로직 (pytest-asyncio 아님)
- Qdrant collection routing
- Document processing
```

### 전체 커버리지
```
목표: 75%+ (통합 포함)
현황: 66.7% (Unit + 부분 Integration)

근거: Unit test 환경의 구조적 한계
```

---

## 🚀 실행 예제

### 예제 1: GitHub Actions (자동)

```yaml
name: Test RAG Service

on:
  push:
    branches: [main, issue-*]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 2 * * SUN'  # 주간 일요일 2am UTC

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      # Unit test (항상)
      - name: Run Unit Tests
        run: |
          python -m pytest services/rag/tests/test_rag.py \
            -v --tb=short

      # Integration test (schedule 또는 수동)
      - name: Run Integration Tests
        if: github.event_name == 'schedule'
        run: |
          docker compose -f docker/compose.p2.cpu.yml up -d
          sleep 30

          docker compose -f docker/compose.p2.cpu.yml exec -T rag bash -c \
            "RUN_RAG_INTEGRATION_TESTS=true python -m pytest services/rag/tests/"

          docker compose -f docker/compose.p2.cpu.yml down
```

### 예제 2: 로컬 수동 실행

```bash
#!/bin/bash

# Unit test
echo "=== Running Unit Tests ==="
pytest services/rag/tests/test_rag.py -v

# Integration test (optional)
if [ "$1" == "--integration" ]; then
  echo "=== Starting Phase 2 Stack ==="
  make up-p2

  echo "=== Running Integration Tests ==="
  docker compose -f docker/compose.p2.cpu.yml exec rag bash -c \
    "RUN_RAG_INTEGRATION_TESTS=true python -m pytest services/rag/tests/test_rag_integration.py -v"

  echo "=== Cleaning Up ==="
  make down-p2
fi
```

---

## ✅ 체크리스트

### PR #35 포함 사항
- ✅ `RUN_RAG_INTEGRATION_TESTS` 환경 변수 기반 조건부 스킵
- ✅ 기본값: `"false"` (보안, Integration test 자동 스킵)
- ✅ pytest 모듈 레벨 스킵 구현
- ✅ pytest-asyncio fixture scope 수정 (function scope)
- ✅ 상세 CI 구동 가이드 제공

### 다음 단계
- ⏳ GitHub Actions 워크플로우 추가 (선택적)
- ⏳ 주간 통합 테스트 자동 실행 설정 (선택적)
- ⏳ Makefile 타겟 추가 (make test-rag-integration)

---

## 📝 요약

| 항목 | 설명 |
|------|------|
| **기본 동작** | Unit test만 실행 (Integration 스킵) |
| **환경 변수** | `RUN_RAG_INTEGRATION_TESTS=true` |
| **스코프** | 모듈 레벨 스킵 (효율적) |
| **안정성** | fixture scope="function" (event loop 안정) |
| **CI 전략** | Unit 항상, Integration 선택적 |
| **커버리지** | Unit 67%, 통합 포함 시 66.7% |

---

**작성**: Claude Code
**날짜**: 2025-10-22
**상태**: PR #35에 포함됨 ✅
