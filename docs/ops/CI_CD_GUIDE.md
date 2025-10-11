# CI/CD 가이드

## 1. GitHub Actions 워크플로우 개요

Local AI Suite는 GitHub Actions 기반 CI/CD 파이프라인을 사용하여 코드 품질을 자동으로 검증합니다.

### 워크플로우 구조

**파일 위치**: `.github/workflows/ci.yml`

### 트리거 조건
```yaml
on:
  push:
    branches: [ main, develop, issue-* ]
  pull_request:
    branches: [ main, develop ]
```

**자동 실행 시나리오**:
- `main`, `develop` 브랜치에 Push
- `issue-*` 패턴 브랜치에 Push (예: `issue-20`)
- `main`, `develop`로의 Pull Request

---

### Job 구조

| Job | 용도 | 실행 시간 | 필수 여부 |
|-----|------|-----------|-----------|
| **lint** | 코드 포맷 및 린트 검사 | ~1분 | ✅ 필수 |
| **security-scan** | 보안 취약점 스캔 | ~2분 | ⚠️ 경고만 |
| **unit-tests** | 서비스별 유닛 테스트 | ~3분 | ✅ 필수 |
| **integration-tests** | CPU 프로필 통합 테스트 (Mock LLM) | ~2분 | ✅ 필수 |
| **build-check** | Docker 빌드 검증 | ~5분 | ✅ 필수 |
| **summary** | CI 결과 요약 | ~10초 | ✅ 항상 |

**전체 소요 시간**: 약 8-10분 (병렬 실행)

---

## 2. 로컬 테스트 실행

### 2.1 린트 체크

**Black (코드 포맷팅)**:
```bash
# 포맷 검사
black --check services/ scripts/

# 자동 수정
black services/ scripts/

# 특정 파일만
black services/rag/app.py
```

**Ruff (린트)**:
```bash
# 린트 검사
ruff check services/ scripts/

# 자동 수정 가능한 항목 수정
ruff check --fix services/ scripts/

# 특정 규칙 비활성화 (pyproject.toml)
[tool.ruff]
ignore = ["E501"]  # 줄 길이 제한 무시
```

---

### 2.2 유닛 테스트

**단일 서비스 테스트**:
```bash
# MCP Server (기존 테스트 5개)
cd services/mcp-server
pytest tests/ -v

# RAG Service (5개 테스트)
cd services/rag
pytest tests/ -v --cov

# Embedding Service (7개 테스트)
cd services/embedding
pytest tests/ -v --cov
```

**전체 서비스 테스트**:
```bash
# 모든 서비스 순차 실행
for service in mcp-server rag embedding; do
  echo "Testing $service..."
  (cd services/$service && pytest tests/ -v --cov)
done
```

**커버리지 리포트**:
```bash
# HTML 리포트 생성
pytest tests/ --cov=. --cov-report=html

# 브라우저에서 확인
open htmlcov/index.html

# 터미널에서 요약 확인
pytest tests/ --cov=. --cov-report=term-missing
```

---

### 2.3 통합 테스트 (수동 실행)

**⚠️ 주의**: 통합 테스트는 GPU + 모델 파일 필요

#### CI 러너 전략 (Option 2: CPU 프로필 + 로컬 GPU 테스트)

**선택 근거**:
- GitHub Actions 무료 티어 활용 (비용 효율적)
- CI에서는 Mock LLM 서버로 헬스체크 및 기본 통합 테스트 실행
- GPU 통합 테스트는 로컬 환경에서 수동 실행

**구현 방법**:
- `docker/compose.p2.cpu.yml`: Mock inference 서버 사용 (GPU 불필요)
- `services/mock-inference/`: FastAPI 기반 OpenAI-compatible stub
- CI에서 헬스체크 + 서비스 간 연결 검증

**CI 워크플로우 동작**:
- ✅ Lint, Security Scan, Unit Tests (16개): **자동 실행**
- ✅ Integration Tests (CPU Profile): **Health check 1개만 자동** (test_api_gateway_health)
- ✅ Docker Build: **자동 실행**
- ⚠️ Integration Tests (GPU 필요 3개): **로컬에서 수동 실행** (chat/code/failover)

**로컬 CPU 프로필 테스트** (CI와 동일한 환경):
```bash
# CPU 프로필로 서비스 시작 (Mock LLM 서버)
docker compose -f docker/compose.p2.cpu.yml up -d

# 서비스 상태 확인
docker compose -f docker/compose.p2.cpu.yml ps

# 헬스체크
curl http://localhost:8001/health  # Mock Chat model
curl http://localhost:8004/health  # Mock Code model
curl http://localhost:8000/health  # API Gateway
curl http://localhost:8002/health  # RAG
curl http://localhost:8003/health  # Embedding

# 정리
docker compose -f docker/compose.p2.cpu.yml down -v
```

**로컬 GPU 통합 테스트** (실제 모델 추론):
```bash
# Phase 2 서비스 시작 (실제 GPU 모델)
make up-p2

# 서비스 상태 확인
docker compose -f docker/compose.p2.yml ps

# 헬스체크
curl http://localhost:8001/health  # Chat model (3B, GPU)
curl http://localhost:8004/health  # Code model (7B, GPU)
curl http://localhost:8000/health  # API Gateway
curl http://localhost:8002/health  # RAG
curl http://localhost:8003/health  # Embedding
```

**통합 테스트 실행**:
```bash
# CI 자동 실행 (health check 1개)
pytest tests/integration/test_api_gateway.py::test_api_gateway_health -v

# GPU 필요 테스트 (로컬 수동 3개)
export RUN_INTEGRATION_TESTS=true
pytest tests/integration/test_api_gateway.py::test_chat_model_inference -v
pytest tests/integration/test_api_gateway.py::test_code_model_inference -v
pytest tests/integration/test_api_gateway.py::test_failover_from_chat_to_code -v

# 또는 전체 실행
pytest tests/integration/test_api_gateway.py -v
```

**CI 실행 범위**:
- ✅ **자동 실행 (1개)**: `test_api_gateway_health` - CPU 프로필에서 Mock LLM 사용
- ⚠️ **수동 실행 (3개)**: `chat/code/failover` - GPU + 실제 모델 필요 (`pytest.mark.skipif`로 CI skip)

---

## 3. 보안 스캔

### 3.1 Bandit (AST 기반 코드 스캔)

**기본 실행**:
```bash
# 전체 스캔
bandit -r services/

# JSON 리포트
bandit -r services/ -f json -o bandit-report.json

# 심각도 필터 (Low/Medium/High)
bandit -r services/ -ll  # Low 레벨 이상만
```

**일반적인 경고**:
- `B101`: `assert` 사용 (테스트 코드는 괜찮음)
- `B201`: `pickle` 사용 (신뢰할 수 없는 데이터 주의)
- `B603`: 서브프로세스 호출 (입력 검증 필요)

---

### 3.2 Safety (의존성 취약점 검사)

**의존성 스캔**:
```bash
# requirements.txt 스캔
safety check --file services/mcp-server/requirements.txt

# 전체 서비스 스캔
find services -name "requirements.txt" -exec cat {} \; > all-requirements.txt
safety check --file all-requirements.txt

# JSON 출력
safety check --json
```

**취약점 발견 시**:
1. 패키지 버전 업데이트: `pip install --upgrade <package>`
2. 대체 패키지 검토
3. 보안 패치 확인: GitHub Security Advisories

---

## 4. Docker 빌드 테스트

### 4.1 단일 서비스 빌드

```bash
# RAG Service
cd services/rag
docker build -t rag:test .

# Embedding Service
cd services/embedding
docker build -t embedding:test .

# MCP Server
cd services/mcp-server
docker build -t mcp-server:test .
```

---

### 4.2 Compose 빌드 (전체)

```bash
# Phase 1 빌드
docker compose -f docker/compose.p1.yml build

# Phase 2 빌드 (권장)
docker compose -f docker/compose.p2.yml build

# Phase 3 빌드 (전체)
docker compose -f docker/compose.p3.yml build

# 캐시 없이 빌드 (클린 빌드)
docker compose -f docker/compose.p2.yml build --no-cache
```

---

## 5. CI 실패 시 디버깅

### 5.1 Lint 실패

**Black 포맷 오류**:
```bash
# 에러 메시지 예시
would reformat services/rag/app.py

# 해결: 자동 포맷팅
black services/rag/app.py

# 전체 자동 수정
black services/ scripts/
```

**Ruff 린트 오류**:
```bash
# 에러 메시지 예시
services/rag/app.py:10:1: F401 [*] `os` imported but unused

# 해결: 자동 수정
ruff check --fix services/rag/app.py

# 수동 수정 (import 제거)
# Before: import os
# After: (삭제)
```

---

### 5.2 테스트 실패

**로컬 재현 방법**:
```bash
# 실패한 테스트만 재실행
pytest services/rag/tests/test_rag.py::test_health_endpoint -v

# 상세 로그 출력
pytest tests/ -v -s

# pdb 디버거 활성화
pytest tests/ --pdb

# 실패 시 즉시 중단
pytest tests/ -x
```

**일반적인 실패 원인**:
1. **Fixture 오류**: `@pytest.fixture` 정의 확인
2. **Import 오류**: 의존성 설치 (`pip install -r requirements.txt`)
3. **비동기 테스트**: `@pytest.mark.asyncio` 누락
4. **Mock 오류**: `httpx.ASGITransport` API 변경 확인

---

### 5.3 빌드 실패

**Docker 빌드 로그 확인**:
```bash
# 로컬 빌드로 에러 재현
cd services/rag
docker build -t rag:debug .

# 상세 로그 출력
docker build --progress=plain -t rag:debug .

# 특정 단계까지만 빌드
docker build --target builder -t rag:debug .
```

**일반적인 빌드 오류**:
- **파일 없음**: `COPY requirements.txt` 경로 확인
- **의존성 설치 실패**: `requirements.txt` 버전 호환성 확인
- **권한 오류**: `Dockerfile`에서 `chmod +x` 추가

---

## 6. Coverage 리포트 확인

### 6.1 로컬 Coverage

```bash
# 커버리지 측정
pytest tests/ --cov=services --cov-report=html

# 리포트 확인
open htmlcov/index.html

# 누락된 라인 확인
pytest tests/ --cov=services --cov-report=term-missing
```

**출력 예시**:
```
Name                                Stmts   Miss  Cover   Missing
-----------------------------------------------------------------
services/rag/app.py                   150     45    70%   42-56, 89-103
services/embedding/app.py              80     12    85%   67-72
-----------------------------------------------------------------
TOTAL                                 230     57    75%
```

---

### 6.2 Codecov 대시보드

**접속**: https://codecov.io/gh/YOUR_REPO

**주요 지표**:
- **Total Coverage**: 전체 커버리지 (목표: 50-60%)
- **Diff Coverage**: PR에서 변경된 코드 커버리지 (목표: 70%+)
- **File Coverage**: 파일별 커버리지

**CI 통합**:
- GitHub PR에 자동 댓글 추가
- 커버리지 하락 시 경고 표시

---

### 6.3 커버리지 목표

| 단계 | 목표 | 현재 | 상태 |
|------|------|------|------|
| Phase 1 (MVP) | 30% | ~35% | ✅ 달성 |
| **Phase 2 (현재)** | **Unit Tests 16개** | **16개 작성** | ✅ **달성** |
| Phase 3 (이상) | 80% | - | 🎯 Issue #21 |

---

## 7. GitHub Actions 고급 설정

### 7.1 캐싱 최적화

**Python 의존성 캐싱**:
```yaml
- uses: actions/setup-python@v5
  with:
    python-version: '3.11'
    cache: 'pip'  # pip 캐싱 활성화
```

**Docker 레이어 캐싱**:
```yaml
- uses: docker/setup-buildx-action@v3
- uses: docker/build-push-action@v5
  with:
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

---

### 7.2 Matrix 병렬 실행

**현재 설정**:
```yaml
strategy:
  fail-fast: false
  matrix:
    service: [mcp-server, rag, embedding]
```

**최대 병렬도**: 3개 서비스 동시 실행 → 시간 단축

---

### 7.3 Artifacts 업로드

**Coverage 리포트 저장**:
```yaml
- uses: actions/upload-artifact@v4
  with:
    name: coverage-${{ matrix.service }}
    path: services/${{ matrix.service }}/htmlcov/
    retention-days: 30
```

**다운로드**: GitHub Actions → Workflow Run → Artifacts

---

## 8. CI/CD 모범 사례

### 체크리스트
- [ ] PR 생성 전 로컬에서 `black`, `ruff`, `pytest` 실행
- [ ] 새 코드 작성 시 유닛 테스트 추가 (최소 1개)
- [ ] 커버리지 50% 이상 유지
- [ ] 보안 스캔 경고 검토 (Bandit/Safety)
- [ ] Docker 빌드 성공 확인

### Commit Hooks (선택적)

**pre-commit 설정** (`.pre-commit-config.yaml`):
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black

  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.0.270
    hooks:
      - id: ruff
        args: [--fix]
```

**설치**:
```bash
pip install pre-commit
pre-commit install
```

---

## 9. 트러블슈팅 FAQ

### Q1: "Black would reformat" 오류
**A**: `black services/ scripts/` 실행 후 커밋

### Q2: Coverage 업로드 실패
**A**: Codecov 토큰 확인 (GitHub Secrets → `CODECOV_TOKEN`)

### Q3: Docker 빌드 시간 초과
**A**: GitHub Actions 무료 티어는 6시간 제한, 빌드 캐싱 활성화

### Q4: 통합 테스트 Skip
**A**: 정상 동작 (GPU 필요), 로컬에서 `RUN_INTEGRATION_TESTS=true` 설정

---

## 10. 참고 자료

- [GitHub Actions 문서](https://docs.github.com/en/actions)
- [pytest 공식 가이드](https://docs.pytest.org/)
- [Black 코드 스타일](https://black.readthedocs.io/)
- [Ruff 린터](https://beta.ruff.rs/docs/)
- [Codecov 통합](https://docs.codecov.com/docs)

**프로젝트 파일**:
- `.github/workflows/ci.yml` - CI 워크플로우
- `services/*/tests/` - 유닛 테스트
- `tests/integration/` - 통합 테스트
- `pyproject.toml` - Linting 설정 (추가 예정)
