# GitHub Issue Analysis & Solution Planning Command

**이 문서는 Issue #1의 분석 및 구현 계획 결과입니다.**

**관련 명령**:
- AI CLI로 이슈 조회: `python scripts/ai.py "이슈 분석"`
- 승인 워크플로우 관리: `python scripts/approval_cli.py`

---

## Step 1: Issue Retrieval & Analysis

### Fetch Issue Details
```bash
gh issue view 1 --json title,body,labels,assignees,milestone,state,createdAt,updatedAt
```

### Issue Information Summary
**이슈 번호**: #1
**제목**: [Feature] Phase 1: 기본 모델 서빙 + OpenAI 호환 API 구축
**상태**: Open
**생성일**: 2025-09-22T09:52:19Z
**담당자**: (없음)
**라벨**: (없음)
**마일스톤**: (없음)

### Issue Content Analysis
**문제 유형**: Feature Implementation
**우선순위**: High
**복잡도**: Medium

**핵심 요구사항**:
- 로컬 GGUF 모델을 OpenAI 호환 API로 서빙하는 환경 구축
- `make up-p1` 명령으로 서비스 정상 실행
- `curl http://localhost:8000/v1/models` 및 `/v1/chat/completions` API 정상 동작
- VS Code/Cursor에서 `http://localhost:8000/v1` 연결 성공
- RTX 4050 + WSL2 환경에서 GPU 활용

**기술적 제약사항**:
- Docker Compose 기반 구현
- llama.cpp (추론 서버) + LiteLLM (API 게이트웨이) 사용
- GPU 패스스루 설정 필요 (`device_requests` 사용)
- 외장 SSD 환경 고려

---

## Step 2: Technical Investigation

### Code Analysis Required
```bash
# 관련 파일들 검색
find . -name "*.yml" -o -name "*.yaml" -o -name "Makefile*" -o -name ".env*"
```

**영향 범위 분석**:
- **Infrastructure**: Docker Compose 설정 및 컨테이너 구성
- **Networking**: 포트 8000(API Gateway), 8001(Inference Server)
- **Storage**: 모델 파일 마운트 (`models/` 디렉토리)
- **GPU**: NVIDIA Docker runtime 설정

### Dependency Check
**의존성 이슈**:
- Depends on: Docker Desktop + GPU 지원, GGUF 모델 파일
- Blocks: Phase 2 (RAG 시스템), Phase 3 (MCP 서버)
- Related to: 전체 Local AI Suite 프로젝트

**현재 프로젝트 상태**:
- **Makefile**: Phase 1-3 명령어 이미 정의됨 (`make up-p1`)
- **.env.example**: 환경 변수 설정 준비됨
- **README.md**: 전체 아키텍처 및 사용법 문서화됨
- **필수 파일 확인**:
  - `docker/compose.p1.yml` (포트: 8000/8001, GPU 설정, 모델 경로 확인 필요)
  - `services/api-gateway/config.p1.yaml` (LiteLLM 설정, OpenAI 호환성 확인 필요)

---

## Step 3: Solution Strategy

### Approach Options
**Option 1: llama.cpp + LiteLLM 조합 (추천안)**
- **장점**: 검증된 스택, OpenAI 완벽 호환, GPU 최적화
- **단점**: 두 개 컨테이너 관리 필요
- **예상 시간**: 2-3시간
- **위험도**: Low

**Option 2: vLLM 단일 서버**
- **장점**: 단일 컨테이너, 높은 성능
- **단점**: GGUF 지원 제한, 메모리 요구량 높음
- **예상 시간**: 3-4시간
- **위험도**: Medium

**Option 3: Ollama 기반**
- **장점**: 설정 간단, 모델 관리 편리
- **단점**: 버전에 따라 OpenAI API 호환 범위가 다를 수 있음 (사전 확인 필요)
- **예상 시간**: 1-2시간
- **위험도**: Medium

### Recommended Approach
**선택한 접근법**: Option 1 - llama.cpp + LiteLLM 조합
**선택 이유**: 이슈 명세서에서 요구한 기술 스택이며, RTX 4050 환경에서 검증된 성능과 OpenAI 완벽 호환성 제공

---

## Step 4: Detailed Implementation Plan

### Phase 0: 사전점검 (Preflight) (15분)
**목표**: 실행 환경 및 의존성 사전 검증

| Task | Description | Owner | DoD | Risk |
|------|-------------|-------|-----|------|
| GPU 환경 검증 | `nvidia-smi`, Docker GPU 지원 확인 | Dev | GPU 인식 확인 | High |
| 모델 파일 확인 | GGUF 모델 파일 존재 및 접근 권한 확인 | Dev | 모델 파일 로딩 가능 | High |
| 포트 충돌 검사 | 8000, 8001 포트 사용 현황 확인 | Dev | 포트 사용 가능 | Medium |
| 환경변수 검증 | `.env` 파일 로드 및 필수 변수 확인 | Dev | 설정값 정상 | Low |

### Phase 1.1: 환경 설정 및 준비 (30분)
**목표**: 개발 환경 및 기본 설정 완료

| Task | Description | Owner | DoD | Risk |
|------|-------------|-------|-----|------|
| 브랜치 생성 | `feature/phase1` 브랜치 생성 및 체크아웃 | Dev | 브랜치 생성 완료 | Low |
| 환경파일 생성 | `.env.example` → `.env` 복사 | Dev | `.env` 파일 생성 | Low |
| 파일 검토 및 조정 | `docker/compose.p1.yml` 및 API Gateway 설정 검토 후 필요시 조정 | Dev | Phase 1 설정값과 일치 확인 | Low |

### Phase 1.2: Docker 서비스 구현 (1.5시간)
**목표**: 컨테이너 설정 및 서비스 정의

| Task | Description | Owner | DoD | Risk |
|------|-------------|-------|-----|------|
| Docker Compose 작성 | `docker/compose.p1.yml` 생성 | Dev | 추론서버+게이트웨이 정의 | Medium |
| API Gateway 설정 | LiteLLM 설정파일 작성 | Dev | OpenAI 호환 설정 완료 | Medium |
| GPU 설정 구성 | device_requests로 GPU 패스스루 | Dev | GPU 인식 확인 | High |
| 볼륨 마운트 설정 | 모델 파일 경로 설정 | Dev | 모델 로딩 확인 | Medium |

### Phase 1.3: 테스트 및 검증 (1시간)
**목표**: 전체 시스템 동작 확인

| Task | Description | Owner | DoD | Risk |
|------|-------------|-------|-----|------|
| 컨테이너 실행 테스트 | `make up-p1` 실행 확인 | Dev | 모든 컨테이너 정상 실행 | Medium |
| API 응답 테스트 | `/v1/models`, `/v1/chat/completions` 테스트 | Dev | 정상 응답 확인 | Low |
| IDE 연동 테스트 | VS Code/Cursor 연결 테스트 | Dev | AI 응답 생성 확인 | Low |

---

## Step 5: Risk Assessment & Mitigation

### High Risk Items
| Risk | Impact | Probability | Mitigation Strategy |
|------|--------|-------------|-------------------|
| GPU 인식 실패 | High | Medium | Docker Desktop GPU 설정 확인, nvidia-docker2 설치 검증 |
| 모델 로딩 실패 | High | High | 모델 파일 경로/권한 확인, GGUF 포맷 검증 |
| 메모리 부족 | Medium | Medium | 4K context 제한, Q4 양자화 모델 사용 |

### Technical Challenges
**예상 기술적 난점**:
1. **GPU 패스스루 설정** - WSL2 + Docker Desktop 환경에서 `device_requests` 설정
2. **포트 바인딩** - 8000, 8001 포트 충돌 방지
3. **모델 로딩 시간** - 첫 요청 시 수분 소요될 수 있음

### Rollback Plan
**롤백 시나리오**:
- GPU 실패 시 → CPU 모드로 폴백 (`CUDA_VISIBLE_DEVICES=""`)
- 컨테이너 실패 시 → `make down` 후 재시작

---

## Step 6: Resource Requirements

### Human Resources
- **개발자**: 1명 (Docker, GPU 설정 경험 필요)
- **리뷰어**: 1명 (인프라 검증)

### Technical Resources
- **개발 도구**: Docker Desktop, NVIDIA Container Toolkit
- **테스트 환경**: RTX 4050 + WSL2
- **모델 파일**: GGUF 포맷 7B 모델 (~4GB)

### Time Estimation
- **사전점검**: 15분
- **핵심 구현**: 2.5시간
- **테스트 & 검증**: 1시간
- **총 예상 시간**: 3.75시간
- **버퍼 시간**: 1.25시간 (33% 버퍼)
- **완료 목표일**: 2025-09-22

---

## Step 7: Quality Assurance Plan

### Test Strategy
**테스트 레벨**:
- **Integration Tests**: 컨테이너 간 통신 및 API 호출
- **System Tests**: 전체 워크플로우 테스트
- **Compatibility Tests**: IDE 연동 테스트

### Test Cases
```gherkin
Feature: Phase 1 기본 모델 서빙

Scenario: 서비스 정상 실행
  Given Docker Desktop이 실행 중이고
  And 모델 파일이 models/ 디렉토리에 있을 때
  When make up-p1을 실행하면
  Then 모든 컨테이너가 정상 실행된다

Scenario: API 호출 성공
  Given Phase 1 서비스가 실행 중일 때
  When /v1/models API를 호출하면
  Then 사용 가능한 모델 리스트를 반환한다
  And /v1/chat/completions API 호출 시
  Then AI 응답을 정상 생성한다

Scenario: IDE 연동 성공
  Given API 서버가 실행 중일 때
  When VS Code에서 http://localhost:8000/v1로 연결하면
  Then AI 코드 어시스턴트가 동작한다
```

### Performance Criteria
- **응답시간**: 첫 요청 < 30초, 이후 요청 < 5초
- **처리량**: 연속 요청 처리 가능
- **리소스 사용률**: GPU 메모리 < 6GB, CPU < 70%

---

## Step 8: Communication Plan

### Status Updates
- **이슈 댓글 업데이트**: 주요 마일스톤마다 진행상황 공유
- **Git 커밋**: 단계별 작업 완료 시점에 커밋

### Stakeholder Notification
- **GitHub Issue**: 구현 완료 시 완료 상태로 업데이트
- **README**: 성공적 구현 시 사용법 가이드 업데이트

---

## 📋 구현할 파일 목록

### 사전점검 스크립트

**scripts/preflight.sh**
```bash
#!/usr/bin/env bash
set -e
echo "[1/4] GPU 체크"; docker run --rm --gpus all nvidia/cuda:12.2-base-ubuntu20.04 nvidia-smi >/dev/null && echo "✅ GPU 인식 성공"
echo "[2/4] 모델 파일 체크"; test -f "./models/${CHAT_MODEL}" && echo "✅ 모델 파일 존재" || (echo "❌ 모델 파일 없음: ${CHAT_MODEL}"; exit 1)
echo "[3/4] 포트 체크"; nc -z localhost ${API_GATEWAY_PORT:-8000} 2>/dev/null && echo "⚠️  포트 ${API_GATEWAY_PORT:-8000} 사용중" || echo "✅ 포트 ${API_GATEWAY_PORT:-8000} 사용 가능"
nc -z localhost ${INFERENCE_PORT:-8001} 2>/dev/null && echo "⚠️  포트 ${INFERENCE_PORT:-8001} 사용중" || echo "✅ 포트 ${INFERENCE_PORT:-8001} 사용 가능"
echo "[4/4] .env 검증"; source .env && grep -E "CHAT_MODEL|PORT" .env && echo "✅ 환경변수 로드 성공"
echo "🚀 Preflight 점검 완료"
```

### 필수 파일 구성 및 조정 가이드

기존 `docker/compose.p1.yml` 및 `services/api-gateway/config.p1.yaml` 파일이 저장소에 이미 존재합니다.

**다음 파라미터를 확인 및 조정하세요**:

| 파라미터 | 파일 | 기존값 | 설정값 | 설명 |
|---------|------|--------|--------|------|
| `CHAT_MODEL` | compose.p1.yml | `Qwen2.5-3B-Instruct-Q4_K_M.gguf` | .env에서 정의 | 3B 모델 (추론 서버용) |
| `--n-gpu-layers` | compose.p1.yml | 35 | RTX 4050 기준 35 | GPU 계층 수 조정 |
| `--ctx-size` | compose.p1.yml | 8192 | 1024 (권장) | 메모리 최적화 |
| `INFERENCE_PORT` | compose.p1.yml | 8001 | 필요시 변경 | 추론 서버 포트 |
| `API_GATEWAY_PORT` | compose.p1.yml | 8000 | 필요시 변경 | API 게이트웨이 포트 |
| `api_base` | config.p1.yaml | `http://inference:8001` | Docker 환경에서 자동 | 내부 컨테이너 통신 |

**조정 후 확인**:
```bash
# 기존 파일 확인
ls -la docker/compose.p1.yml
ls -la services/api-gateway/config.p1.yaml

# 환경 변수 설정
cp .env.example .env
# .env 파일 편집하여 필요한 값 조정

# Phase 1 시작
make up-p1
```

3. **환경변수 설정 (.env)**
```bash
# 복사 명령: cp .env.example .env
# 필수 설정값 확인
API_GATEWAY_PORT=8000
INFERENCE_PORT=8001
CHAT_MODEL=llama3.1-8b-instruct-q4_k_m.gguf
CODE_MODEL=qwen2.5-coder-7b-q4_k_m.gguf

# GPU 설정 (필요시 조정)
CUDA_VISIBLE_DEVICES=0
```

---

## 📋 User Review Checklist

**다음 항목들을 검토해주세요:**

### Planning Review
- [x] **이슈 분석이 정확한가요?**
  - 핵심 요구사항: 로컬 GGUF 모델 → OpenAI API 서빙
  - 기술적 제약사항: Docker + GPU + llama.cpp + LiteLLM

- [x] **선택한 해결 방안이 적절한가요?**
  - llama.cpp + LiteLLM 조합은 이슈에서 요구한 정확한 스택
  - 검증된 방식이며 RTX 4050 환경에 최적화됨

- [x] **구현 계획이 현실적인가요?**
  - 3개 Phase로 단계별 구현 (환경설정 → 구현 → 테스트)
  - 각 단계별 명확한 DoD와 위험도 평가

### Resource Review
- [x] **시간 추정이 합리적인가요?**
  - 총 3-4시간은 Docker + GPU 설정 경험 기준으로 적절
  - 33% 버퍼 시간으로 예상 이슈 대응 가능

- [x] **필요한 리소스가 확보 가능한가요?**
  - Docker Desktop, GPU 드라이버는 이미 설치 전제
  - GGUF 모델 파일만 다운로드 필요

### Risk Review
- [x] **위험 요소가 충분히 식별되었나요?**
  - GPU 인식 실패: WSL2 환경의 대표적 이슈
  - 모델 로딩 실패: 파일 경로/권한 문제 자주 발생
  - 메모리 부족: RTX 4050 6GB 제한 고려

- [x] **롤백 계획이 현실적인가요?**
  - GPU 실패 시 CPU 폴백은 즉시 적용 가능
  - `make down`으로 완전 정리 후 재시작 가능

### Quality Review
- [x] **테스트 전략이 충분한가요?**
  - 컨테이너 실행 → API 호출 → IDE 연동까지 전체 플로우 커버
  - 성능/안정성 기준도 구체적으로 설정

---

## 🚀 Next Steps

**검토 완료 후 진행할 작업:**

1. **Plan Approval**: 위 검토를 통과하면 계획 승인
2. **Issue Update**: GitHub 이슈에 상세 계획 댓글로 추가
3. **Branch Creation**: `feature/phase1` 브랜치 생성
4. **Implementation**: 단계별 파일 생성 및 구현
5. **Testing**: 각 단계별 테스트 실행

**구현 순서:**
0. **사전점검 실행**: `bash scripts/preflight.sh`
1. **환경 설정**: `.env` 생성, 디렉토리 구조 생성
2. **Docker Compose 작성**: GPU 패스스루 포함한 완성된 설정
3. **LiteLLM 설정**: OpenAI 호환 API 게이트웨이 구성
4. **서비스 실행**: `make up-p1` 및 헬스체크 확인
5. **API 테스트**: `/v1/models`, `/v1/chat/completions` 검증
6. **IDE 연동 테스트**: VS Code/Cursor 연결 확인
7. **문제 발생 시**: 로그 확인 및 트러블슈팅

**핵심 실행 명령어:**
```bash
# 사전점검
bash scripts/preflight.sh

# 서비스 실행
make up-p1

# API 테스트
curl http://localhost:8000/v1/models
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "local-chat", "messages": [{"role": "user", "content": "Hello!"}], "max_tokens": 50}'

# 서비스 중지
make down
```

---

**💡 피드백 요청**
이 계획에 대해 어떤 부분을 수정하거나 보완해야 할까요? 특히:
- GPU 설정 부분에서 추가 고려사항이 있는지?
- 시간 추정이 현실적인지?
- 누락된 위험 요소나 테스트 시나리오가 있는지?

**주의:** PR 생성 및 병합은 자동으로 실행하지 않습니다.
필요 시 사용자가 직접 `gh pr create` 등의 명령으로 수동 진행하세요.