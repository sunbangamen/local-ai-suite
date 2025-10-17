# Local AI Suite (Phase-by-Phase)

외장 SSD + RTX 4050에서 **클로드 데스크탑/코드/커서 느낌**을 로컬 모델 + RAG + MCP로 구현하는 스캐폴드.

## Quick Start

### 0) 사전 준비
- Docker Desktop + WSL 통합(Windows)
- 외장 SSD에 이 리포지토리 클론 후 `models/` 폴더 생성
- 7B GGUF 모델 파일을 `models/`에 배치(예: llama3.1-8b-instruct-q4_k_m.gguf, qwen2.5-coder-7b-q4_k_m.gguf)

### 1) Phase 1: 최소 동작 (모델 + OpenAI 호환 게이트웨이)
```bash
make up-p1
# 확인
curl http://localhost:8000/v1/models
```

* VS Code/Cursor에서 OpenAI 호환 엔드포인트를 `http://localhost:8000/v1` 로 설정

### 2) Phase 2: RAG + Qdrant + reranker 추가

```bash
make up-p2
# 문서 인덱싱
curl -X POST "http://localhost:8002/index?collection=myproj"
# 질의
curl -H "Content-Type: application/json" \
     -d '{"query":"테스트 실패 원인 정리","collection":"myproj"}' \
     http://localhost:8002/query
```

### 3) Phase 3: MCP 서버

```bash
make up-p3
# MCP(파일/깃/셸) 엔드포인트 확인
curl http://localhost:8020/health
```

### 보안 기능 세부사항

**차단되는 위험한 코드:**
```python
import subprocess  # ❌ 차단
import ctypes      # ❌ 차단
import socket      # ❌ 차단
importlib.import_module('subprocess')  # ❌ 우회 차단
```

**허용되는 안전한 코드:**
```python
import os          # ✅ 허용
import sys         # ✅ 허용
import pathlib     # ✅ 허용
import json        # ✅ 허용
```

**차단되는 위험한 경로:**
```bash
/etc/passwd                    # ❌ 차단
C:/Windows/System32/config/SAM  # ❌ 차단 (슬래시)
C:\Windows\System32            # ❌ 차단 (백슬래시)
../../../etc/shadow            # ❌ 경로 탈출 차단
```

## 폴더 요약

* `docker/compose.p1.yml` : 추론서버 + API 게이트웨이(litellm)
* `docker/compose.p2.yml` : + Qdrant + RAG(FastAPI) + reranker
* `docker/compose.p3.yml` : + MCP 서버(fs/git/shell)

## 보안

* 모든 서비스는 로컬호스트만 노출 권장.
* 외부 포트 개방 금지. 토큰/키 필요 없음(완전 로컬 전제).

### 보안 테스트 실행

MCP 서버의 보안 시스템을 검증하려면 자동화된 테스트를 실행할 수 있습니다:

```bash
# pytest 설치 (한 번만)
pip install pytest

# 보안 테스트 실행
pytest tests/security_tests.py -q

# 또는 직접 기본 보안 테스트 실행
python3 tests/security_tests.py
```

**테스트 항목:**
- ✅ AST 기반 코드 보안 검증
- ✅ 동적 import 우회 시도 차단 (`importlib.import_module` 등)
- ✅ 절대 경로 매핑 보안 (경로 탈출 방지)
- ✅ Windows/Linux 멀티플랫폼 경로 보안
- ✅ 슬래시/백슬래시 혼합 경로 차단
- ✅ 시스템 파일 및 민감 디렉터리 접근 방지

**기대 결과:** 모든 보안 테스트가 통과해야 하며, 실패 시 보안 취약점이 있음을 의미합니다.

### RAG 통합 테스트 실행

RAG 서비스의 end-to-end 통합 테스트를 실행하여 전체 시스템 동작을 검증할 수 있습니다:

```bash
# 1. Phase 2 스택 시작 (PostgreSQL + Qdrant + Embedding + RAG)
make up-p2

# 2. 통합 테스트 실행 (기본)
make test-rag-integration

# 3. 커버리지 측정과 함께 실행
make test-rag-integration-coverage

# 4. 스택 종료
make down-p2
```

**테스트 시나리오:**
- ✅ 문서 인덱싱 파이프라인 (PostgreSQL + Qdrant + Embedding)
- ✅ 쿼리 및 컨텍스트 검색 (벡터 검색 + LLM 응답)
- ✅ 캐시 동작 및 폴백 메커니즘
- ✅ 타임아웃 및 에러 처리
- ✅ 헬스체크 및 의존성 검증

**커버리지 리포트:**
- 출력 위치: `docs/rag_integration_coverage.json`
- **app.py 커버리지**: 44% (150/342 statements) ✅
- 전체 커버리지: 37% (329/890 statements)
- 커버리지 범위: app.py, 테스트 fixtures, 통합 테스트 코드
- 참고: `test_app_module.py`가 pytest 프로세스 내에서 FastAPI 앱을 직접 import하여 커버리지 측정

**요구사항:**
- Docker Phase 2 스택이 실행 중이어야 함
- 약 5-10초 소요 (의존성 시딩 + 테스트 실행)

### 종합 테스트 & QA (Issue #24 - Testing & QA Enhancement)

전체 테스트 스위트(단위 테스트, 통합 테스트, E2E 테스트, 부하 테스트)를 실행하여 시스템 품질을 검증합니다:

#### Phase 1: RAG 통합 테스트 (21개 테스트)
```bash
# Phase 2 스택 시작
make up-p2

# 확장된 RAG 통합 테스트 실행 (21/21 테스트)
make test-rag-integration-extended

# 종료
make down-p2
```

**결과:**
- ✅ 21개 테스트 모두 통과
- ⏱️ 실행 시간: 6.06초
- 📊 커버리지: `docs/rag_extended_coverage.json`

#### Phase 2: E2E Playwright 테스트 (22개 테스트)
```bash
# Desktop 앱 E2E 테스트 (3개 브라우저 × 여러 시나리오)
cd desktop-app
npm run test:e2e         # Chromium, Firefox, WebKit 자동 실행

# 디버그 모드
npm run test:e2e:debug   # Playwright Inspector 사용

# UI 모드
npm run test:e2e:ui      # Playwright Test UI 실행
```

**테스트 항목:**
- ✅ 22개 테스트 (로그인, 대화, 모델 선택 등)
- 🌐 다중 브라우저: Chromium, Firefox, WebKit
- 📱 반응형 UI 검증
- ⏱️ 예상 시간: 10분

#### Phase 3: 부하 테스트 (3개 시나리오)
```bash
# Phase 2 스택 시작
make up-p2

# 기준선 테스트 (1 사용자, 2분)
make test-load-baseline

# API 게이트웨이 부하 테스트 (10→50→100 사용자, 15분)
make test-load-api

# RAG 서비스 부하 테스트 (5→25→50 사용자, 15분)
make test-load-rag

# MCP 서버 부하 테스트 (5→20 사용자, 10분)
make test-load-mcp

# 전체 부하 테스트 (모든 시나리오 순차 실행, 40분)
make test-load

# 종료
make down-p2
```

**성능 목표:**
- API Gateway: p95 < 2.0초, 오류율 < 1%
- RAG Service: 쿼리 p95 < 3.0초, 오류율 < 1%
- MCP Server: 도구 p95 < 5.0초, 샌드박스 위반 0건

**세부 정보:** `docs/ops/LOAD_TESTING_GUIDE.md` 참조

#### Phase 4: CI/CD 자동화

GitHub Actions에서 자동으로 실행되는 테스트:

```bash
# PR 확인 (23분)
- Lint, Security, Unit Tests
- RAG Integration Tests
- E2E Playwright Tests (브라우저 3개)

# 주 병합 (36분)
- 모든 PR 체크
- 추가 통합 테스트

# 주간 부하 테스트 (일요일 2am UTC, 76분)
- 전체 부하 테스트 스위트
- 성능 회귀 감지
- 자동 GitHub issue 생성 (회귀 발견 시)
```

**수동 실행:**
```bash
# 특정 테스트 수동 트리거
gh workflow run ci.yml -f run_load_tests=true
```

**예산:** 월 829분 (2,000분 중 41.5%)

### 테스트 정보 요약

| 테스트 유형 | 수량 | 상태 | 시간 |
|----------|-----|------|------|
| Unit Tests | ~103개 | ✅ 통과 | <5분 |
| Phase 1 (RAG Integration) | 21개 | ✅ 통과 | 6초 |
| Phase 2 (E2E Playwright) | 22개 | ⏳ 준비 완료 | 10분 |
| Phase 3 (부하 테스트) | 3 시나리오 | ⏳ 준비 완료 | 40분 |
| **합계** | **149+** | - | - |

**세부 문서:**
- 테스트 계획: `docs/progress/v1/PHASE_3_LOAD_TESTING_PLAN.md`
- 부하 테스트: `docs/ops/LOAD_TESTING_GUIDE.md`
- 테스트 전략: `docs/progress/v1/PHASE_4.2_TEST_SELECTION_STRATEGY.md`
- 회귀 감지: `docs/progress/v1/PHASE_4.3_REGRESSION_DETECTION.md`

## 트러블슈팅

* 모델 경로/파일명 오타 → `docker logs`에서 확인
* GPU 인식 안될 때 → Docker Desktop에서 WSL GPU 지원/드라이버 확인
* RAG 품질이 낮을 때 → bge-m3 임베딩, bge-reranker 설정 확인
