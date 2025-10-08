# Phase 1 구현 계획: 기본 모델 서빙 + OpenAI 호환 API

**목표**: 로컬 GGUF 모델을 OpenAI 호환 API로 서빙하는 최소 동작 환경 구축

---

## 문제 분석

### 1. 문제 정의 및 복잡성 평가
- **문제**: Claude Desktop/Code/Cursor 같은 AI 도구를 위한 로컬 모델 서빙 인프라 구축
- **복잡성 수준**: 중간 (Docker 컨테이너 2개 + 설정 파일)
- **예상 소요 시간**: 2-4시간
- **주요 도전 과제**:
  - GPU 패스스루 설정
  - 모델 파일 마운트 및 경로 설정
  - OpenAI 호환 API 포맷 맞추기

### 2. 범위 및 제약조건
- **포함 범위**:
  - llama.cpp 기반 추론 서버
  - LiteLLM 기반 OpenAI 호환 API 게이트웨이
  - Docker Compose 설정
- **제외 범위**:
  - RAG 기능 (Phase 2)
  - MCP 서버 (Phase 3)
  - 모델 다운로드 (사용자가 직접)
- **제약조건**:
  - RTX 4050 GPU 사용
  - Docker Desktop + WSL2 환경
  - 외장 SSD에서 실행
- **전제조건**:
  - Docker Desktop 설치
  - GGUF 모델 파일 준비
  - `.env` 파일 설정

---

## 작업 분해

### Phase 1.1: 환경 설정 및 준비
**목표**: 구현을 위한 기반 환경 구축

| 작업 | 설명 | 완료 기준 (DoD) | 우선순위 |
|------|------|-----------------|----------|
| 브랜치 생성 | `feature/phase1` 브랜치 생성 및 체크아웃 | 브랜치 생성 완료 | 높음 |
| 환경 파일 설정 | `.env.example`을 복사하여 `.env` 생성 | 환경 변수 설정 완료 | 높음 |
| 모델 다운로드 가이드 | 사용자가 모델을 다운로드할 수 있는 가이드 제공 | 모델 다운로드 방법 문서화 | 높음 |

### Phase 1.2: Docker 서비스 구현
**목표**: 추론 서버와 API 게이트웨이 구현

| 작업 | 설명 | 완료 기준 (DoD) | 의존성 |
|------|------|-----------------|--------|
| Docker Compose 파일 생성 | `docker/compose.p1.yml` 작성 | 파일 생성 및 문법 검증 | Phase 1.1 완료 |
| API Gateway 설정 생성 | `services/api-gateway/config.p1.yaml` 작성 | 설정 파일 생성 | Docker Compose 파일 |
| 디렉토리 구조 생성 | 필요한 폴더 구조 생성 | 모든 필요 디렉토리 존재 | - |

### Phase 1.3: 통합 및 테스트
**목표**: 전체 시스템 통합 및 동작 확인

| 작업 | 설명 | 완료 기준 (DoD) | 위험도 |
|------|------|-----------------|--------|
| 컨테이너 실행 테스트 | `make up-p1` 명령으로 서비스 실행 | 모든 컨테이너 정상 실행 | 높음 |
| API 응답 테스트 | `/v1/models` 엔드포인트 테스트 | 모델 목록 응답 확인 | 중간 |
| OpenAI 호환성 테스트 | 채팅 완성 API 테스트 | 실제 응답 생성 확인 | 높음 |
| IDE 연동 테스트 | VS Code/Cursor에서 연결 테스트 | IDE에서 AI 기능 동작 | 낮음 |

---

## 구체적 구현 내용

### 1. Docker Compose 설정 (`docker/compose.p1.yml`)
```yaml
version: "3.9"
services:
  inference:
    image: ghcr.io/ggerganov/llama.cpp:full
    command: ["--server", "--host", "0.0.0.0", "--port", "8001",
              "--model", "/models/${CHAT_MODEL}",
              "--parallel", "4", "--ctx-size", "8192"]
    volumes:
      - ../models:/models
    ports:
      - "${INFERENCE_PORT:-8001}:8001"
    device_requests:        # ✅ Docker Compose용 GPU 설정 (deploy는 Swarm 전용)
      - driver: "nvidia"
        count: -1
        capabilities: [["gpu"]]

  api-gateway:
    image: ghcr.io/berriai/litellm:latest
    environment:
      - LITELLM_CONFIG=/app/config.yaml
    volumes:
      - ../services/api-gateway/config.p1.yaml:/app/config.yaml
    ports:
      - "${API_GATEWAY_PORT:-8000}:8000"
    depends_on:
      - inference
```

### 2. API Gateway 설정 (`services/api-gateway/config.p1.yaml`)
**옵션 A: LiteLLM `llamacpp` 프로바이더 사용 (권장)**
```yaml
model_list:
  - model_name: "local-chat"
    litellm_params:
      model: "llamacpp/generic"    # llamacpp 프로바이더 사용
      api_base: "http://inference:8001"  # /v1 경로 불필요
      api_key: "none"

defaults:
  temperature: 0.2
  max_tokens: 1024

server:
  host: 0.0.0.0
  port: 8000
```

**옵션 B: OpenAI 호환 경로 사용**
```yaml
model_list:
  - model_name: "local-chat"
    litellm_params:
      model: "openai/generic"
      api_base: "http://inference:8001/v1"
      api_key: "none"

defaults:
  temperature: 0.2
  max_tokens: 1024

server:
  host: 0.0.0.0
  port: 8000
```

---

## 실행 계획

### 우선순위 매트릭스
```
긴급 & 중요          | 중요하지만 덜 긴급
--------------------|------------------
- 브랜치 생성        | - IDE 연동 테스트
- Docker 파일 생성   | - 문서 업데이트
- 환경 설정         |

긴급하지만 덜 중요   | 덜 중요 & 덜 긴급
--------------------|------------------
- 컨테이너 실행     | - 성능 최적화
```

### 마일스톤
- **Day 1**: Phase 1.1 완료 (환경 설정)
- **Day 2**: Phase 1.2 완료 (Docker 서비스 구현)
- **Day 3**: Phase 1.3 완료 (통합 및 테스트)

### 위험 요소 및 대응 방안
| 위험 요소 | 가능성 | 영향도 | 대응 방안 |
|-----------|--------|--------|-----------|
| GPU 인식 실패 | 중간 | 높음 | Docker Desktop GPU 설정 확인, WSL2 드라이버 업데이트 |
| 모델 로딩 실패 | 높음 | 높음 | 모델 파일 경로 확인, 권한 설정 점검 |
| 포트 충돌 | 낮음 | 중간 | `.env`에서 포트 번호 변경 |
| 메모리 부족 | 중간 | 중간 | 모델 크기 축소 또는 양자화 버전 사용 |

---

## 품질 체크리스트

### 각 작업 완료 시 확인사항
- [ ] 설정 파일 문법 검증 완료
- [ ] Docker 이미지 풀 성공
- [ ] 컨테이너 로그에 에러 없음
- [ ] API 엔드포인트 응답 확인
- [ ] 다음 작업 차단 요소 없음

### 전체 완료 기준
- [ ] `make up-p1` 명령 성공
- [ ] `curl http://localhost:8000/v1/models` 응답 확인
- [ ] 채팅 완성 API 정상 동작
- [ ] VS Code에서 `http://localhost:8000/v1` 연결 성공
- [ ] 실제 AI 응답 생성 확인

---

## 테스트 시나리오

### 1. 기본 동작 테스트
```bash
# 1. 서비스 실행
make up-p1

# 2. 헬스체크
curl http://localhost:8000/v1/models                    # API 게이트웨이
curl http://localhost:8001 || curl http://localhost:8001/metrics  # 추론 서버 (llama.cpp는 /health 없음)

# 3. 채팅 테스트
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "local-chat",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 50
  }'
```

### 2. IDE 연동 테스트
- **VS Code**: OpenAI/Copilot 확장에서:
  - Base URL: `http://localhost:8000/v1`
  - API Key: `dummy-key` (아무 문자열, 일부 확장에서 필수 요구)
- **Cursor**: Settings → Models → Add Custom Model:
  - Provider: OpenAI Compatible
  - Base URL: `http://localhost:8000/v1`
  - API Key: `dummy-key`
- 코드 완성/채팅 기능 테스트

---

## 리소스 및 참고자료

### 필요한 리소스
- **도구**: Docker Desktop, Make, curl
- **모델**: llama3.1-8b-instruct-q4_k_m.gguf (약 4.6GB)
- **인프라**: RTX 4050, 최소 8GB RAM

### 학습 자료
- [llama.cpp 공식 문서](https://github.com/ggerganov/llama.cpp)
- [LiteLLM 문서](https://docs.litellm.ai/)
- [Docker Compose GPU 설정](https://docs.docker.com/compose/gpu-support/)

### 모델 다운로드 가이드
```bash
# GGUF 모델 다운로드 (실제 예시)
# 1. huggingface-hub 설치
pip install huggingface-hub

# 2. GGUF 모델 다운로드 예시들
# Llama 3.1 8B (약 4.6GB)
huggingface-cli download microsoft/Llama-2-7b-Chat-GGUF llama-2-7b-chat.q4_k_m.gguf --local-dir ./models

# 또는 Qwen2.5 Coder (코딩 특화)
huggingface-cli download Qwen/Qwen2.5-Coder-7B-Instruct-GGUF qwen2.5-coder-7b-instruct-q4_k_m.gguf --local-dir ./models

# 3. .env 파일에 모델명 정확히 기입
# CHAT_MODEL=llama-2-7b-chat.q4_k_m.gguf
# CODE_MODEL=qwen2.5-coder-7b-instruct-q4_k_m.gguf
```

**주의**: GGUF 파일만 사용 가능. 파일명을 `.env`에 정확히 입력하세요.

---

**💡 추가 고려사항**
- 첫 실행 시 Docker 이미지 다운로드로 시간 소요 예상
- GPU 드라이버 이슈 시 CPU 모드로 우선 테스트
- 모델 로딩 시간(수분) 고려하여 테스트 계획
- Phase 2 진행 전 Phase 1 완전 동작 확인 필수