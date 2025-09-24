# Phase 2 RAG 시스템 구현 완료 상태 및 점검사항

## 🛠 2025-09-23 업데이트: 추론/게이트웨이 기동 오류 해결 및 모델 경로 정정

### 증상
- inference(8001)가 재시작 루프 → health 미응답, gateway(8000)도 unhealthy.
- 로그: `invalid argument: --ubatch`, `failed to open GGUF file`(모델 파일 경로/이름 불일치), gateway는 `unexpected extra argument (litellm)`.

### 원인
- llama.cpp 서버 이미지가 `--ubatch` 플래그 미지원.
- 컨테이너는 리눅스 대소문자 구분 → 모델 파일명이 설정과 1글자라도 다르면 로딩 실패.
- api-gateway 엔트리포인트가 이미 `litellm`를 실행하는데 command에 `litellm`를 중복 지정.

### 조치
- Compose(inference) 수정
  - `--ubatch` 제거, 안정 파라미터 유지: `--parallel 2 --n-gpu-layers 24 -c 4096`.
  - 모델 볼륨 고정: `${MODELS_DIR:-/mnt/e/ai-models}:/models:ro`.
  - 기본 모델 파일명(대소문자 일치): `/models/Qwen2.5-7B-Instruct-Q4_K_M.gguf`.
- Compose(api-gateway) 수정
  - command에서 `litellm` 토큰 제거 → `--config /app/config.yaml --port 8000 --host 0.0.0.0`.
  - 설정 파일 마운트: `../services/api-gateway/config.p1.yaml:/app/config.yaml:ro`.
- RAG 서비스는 이전에 타임아웃/토큰 환경변수화 및 `/health?llm=true` 스모크 체크 추가 완료.

### 확인 방법
```bash
docker compose -f docker/compose.p2.yml up -d
curl -s http://localhost:8001/health   # inference: ok → 모델 로딩 후 전환
curl -s http://localhost:8000/health   # gateway: healthy_endpoints에 inference 표시
curl -s http://localhost:8003/health   # embedding: ok
curl -s http://localhost:8002/health   # rag: healthy (옵션: ?llm=true)
```

### 비고
- 모델 경로/이름은 대소문자까지 정확히 일치해야 합니다. 다른 경로를 쓰면 `.env`의 `MODELS_DIR`로 오버라이드하세요.
- 4050 기준 성능 튜닝 베이스는 유지(ngl=24, ctx=4096, parallel=2). 필요 시 `scripts/bench_inference.sh`로 비교 측정.

## 🛠 2025-09-23 업데이트: RAG LLM 타임아웃/토큰 설정 개선

### 문제
- RAG 질의 시 `include_context=true`일 때 14B 모델 응답이 느려 `rag` 서비스 내부 LLM 호출(`httpx` 60초) 타임아웃 발생 → 500 에러.

### 원인
- 14B q4 모델 + 긴 컨텍스트 + `max_tokens=1000` 고정값 조합이 60초를 초과할 수 있음.

### 조치(근본 수정)
- `services/rag/app.py`에 LLM 호출 파라미터를 환경변수로 노출:
  - `RAG_LLM_TIMEOUT` (기본 120)
  - `RAG_LLM_MAX_TOKENS` (기본 512)
  - `RAG_LLM_TEMPERATURE` (기본 0.3)
- 반영 후 재빌드/재기동:
```bash
docker compose -f docker/compose.p2.yml build rag-service && \
docker compose -f docker/compose.p2.yml up -d rag-service
```

### 검증 결과
- 인덱싱: `test-run` 컬렉션(문서 2개, 총 6 청크) 성공
- 질의: `include_context=true`로 정상 응답 수신(프로젝트 설정/실행 요약 반환)

### RTX 4050 최적화 벤치마크 결과 (2025-09-23)
**벤치마크 테스트:** `scripts/bench_inference.sh` 실행
- 테스트 대상: n-gpu-layers 22, 24, 26
- 모델: qwen2.5-14b-instruct-q4_k_m.gguf (Q4_K_M, 8.4GB)
- 기타 설정: ctx-size=4096, parallel=2

**성능 결과:**
- `n-gpu-layers=22`: 3.55 tok/s (predicted_per_token_ms=281.6ms)
- `n-gpu-layers=24`: **6.03 tok/s** (predicted_per_token_ms=165.8ms) ⭐ **최적**
- `n-gpu-layers=26`: 3.55 tok/s (predicted_per_token_ms=281.6ms)

**최종 권장 설정 (RTX 4050):**
- `--ctx-size 4096`, `--parallel 2`, `--n-gpu-layers 24`
- 성능 개선: 70% 향상 (6.03 vs 3.55 tok/s)
- 현재 시스템에 적용됨 (`docker/compose.p2.yml`)

## 📋 현재 완료된 작업 (2025-09-23 12:49)

### ✅ Phase 1 + Phase 2 성공적으로 완료된 항목

1. **Phase 1: 기본 AI 서빙 시스템 완료**
   - `qwen2.5-14b-instruct-q4_k_m.gguf` (8.4GB) - 일반 대화형 모델
   - `qwen2.5-coder-14b-instruct-q4_k_m.gguf` (8.4GB) - 코딩 전용 모델
   - 추론 서버 (포트 8001): ✅ 정상 동작
   - API Gateway (포트 8000): ✅ 정상 동작 (헬스체크 문제 해결됨)
   - AI CLI 도구 (`scripts/ai.py`): ✅ 자동 모델 선택 지원

2. **Phase 2: RAG 시스템 완료**
   - **FastEmbed 임베딩 서비스** (포트 8003): ✅ PyTorch-free 경량화 완료
     - 모델: `BAAI/bge-small-en-v1.5` (384차원)
     - ONNX 런타임 기반으로 빠른 임베딩 생성
   - **Qdrant 벡터 데이터베이스** (포트 6333): ✅ 고성능 벡터 검색
   - **RAG 서비스** (포트 8002): ✅ 문서 인덱싱 + 질의응답
   - **한국어 코딩 문서 인덱싱** 완료: 6개 청크 처리

3. **통합 시스템 구성 완료**
   - `docker/compose.p2.yml`: 전체 RAG 파이프라인 Docker Compose
   - 환경변수 설정 완료 (`.env`)
   - 헬스체크 문제 분석 및 해결 완료

### ✅ 검증 완료된 기능

**1. llama.cpp 추론 서버 (포트 8001)**
```bash
# 모델 목록 확인 (성공)
curl -s http://localhost:8001/v1/models

# 채팅 완료 API 테스트 (성공)
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "안녕하세요!"}], "max_tokens": 100}'
```

**2. API Gateway (포트 8000) - LiteLLM**
```bash
# OpenAI 호환 모델 목록 (성공)
curl -s http://localhost:8000/v1/models

# OpenAI 호환 채팅 API (성공)
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen2.5-14b-instruct", "messages": [{"role": "user", "content": "Hello"}]}'
```

**3. RAG 시스템 완전 동작 검증**
```bash
# 문서 인덱싱 (성공)
curl -X POST http://localhost:8002/index \
  -H "Content-Type: application/json" \
  -d '{"collection": "default"}'

# 한국어 질의응답 (성공)
curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Python에서 파일을 읽는 방법", "collection": "default"}'
```

**실제 RAG 응답 예시:**
> "Python에서 파일을 읽는 방법은 다음과 같습니다:
> ```python
> def read_file(file_path):
>     try:
>         with open(file_path, 'r', encoding='utf-8') as file:
>             return file.read()
>     except FileNotFoundError:
>         return "파일을 찾을 수 없습니다."
> ```"

---

## ✅ 해결 완료된 이전 문제점들

### 1. ~~LiteLLM API Gateway (포트 8000) 문제~~ → **해결됨**
**이전 증상:**
- API Gateway 컨테이너가 포트 4000에서 실행되지만 8000으로 매핑 안 됨

**해결 방법:**
- Docker Compose 명령어에 `--host` 및 `--port` 파라미터 명시적 추가
- 모델 설정을 실제 파일 경로로 수정: `/models/qwen2.5-14b-instruct-q4_k_m.gguf`

### 2. ~~환경변수 경고~~ → **해결됨**
**이전 문제:**
```
The "CHAT_MODEL" variable is not set. Defaulting to a blank string.
```
**해결 방법:**
- `.env` 파일 정리 및 환경변수 직접 명시

### 3. ~~헬스체크 문제~~ → **분석 및 해결 완료**
**문제 분석:**
- API Gateway: LiteLLM 컨테이너에 `curl` 없음, HEAD 메소드 지원 안 함
- Qdrant: 컨테이너에 HTTP 클라이언트 도구 없음

**해결 방법:**
- API Gateway: `wget` + GET 요청 방식으로 변경
- Qdrant: 헬스체크 비활성화 (`disable: true`)

---

## ✅ Phase 3 완료: MCP (Model Context Protocol) 서버 (2025-09-23)

### 1. MCP 서버 구현 완료

**목표 달성:**
- ✅ FastMCP 프레임워크 기반 MCP 서버 구현
- ✅ Playwright 웹 자동화 도구 통합 (4개 도구)
- ✅ Notion API 연동 기능 구현 (3개 도구)
- ✅ 기존 7개 + 신규 7개 = 총 14개 도구 제공

**구현된 MCP 도구들:**
```python
# 기존 7개 도구
- list_files: 디렉토리 파일 목록
- read_file: 파일 내용 읽기
- write_file: 파일 작성
- create_directory: 디렉토리 생성
- search_files: 파일 검색
- run_command: 시스템 명령 실행
- get_system_info: 시스템 정보

# 새로 추가된 Playwright 도구들 (4개)
- web_screenshot: 웹페이지 스크린샷
- web_scrape: 웹 콘텐츠 추출
- web_analyze_ui: UI/디자인 분석
- web_automate: 웹 자동화 작업

# 새로 추가된 Notion 도구들 (3개)
- notion_create_page: Notion 페이지 생성
- notion_search: Notion 검색
- web_to_notion: 웹 콘텐츠를 Notion에 저장
```

**MCP 서버 상태:**
- 포트: 8020
- 프레임워크: FastMCP (Python)
- Docker 빌드: ✅ 완료 (`docker-mcp-server:latest`)
- 기능: 웹 자동화 + Notion 연동 + 파일 시스템 관리

## ✅ Phase 4 완료: Claude Desktop 스타일 데스크탑 앱 (2025-09-23)

### 1. 데스크탑 애플리케이션 구현 완료

**기술 스택:**
- ✅ Electron 기반 크로스플랫폼 앱
- ✅ 웹/Electron 호환 코드 구조
- ✅ WSL 개발환경 최적화

**핵심 기능들:**
```javascript
// 자동/수동 모델 선택
- 🤖 자동 모드: 질문 내용 분석으로 Chat/Code 모델 자동 선택
- 👤 수동 모드: 사용자 직접 모델 선택
- 지능적 키워드 감지: 코딩 관련 질문 자동 인식

// UI/UX 기능
- Claude Desktop 스타일 다크 테마
- Markdown 코드 블록 렌더링
- 코드 복사 기능 (VS Code 스타일)
- 실시간 모델 상태 표시
```

**개발/배포 환경:**
- 개발: WSL2에서 웹브라우저 테스트 (`http://localhost:3000`)
- 배포: Windows에서 Electron 앱 실행
- 권한문제 해결: `--no-bin-links` 플래그로 WSL 심링크 이슈 해결

**자동 모델 감지 키워드:**
```javascript
// 코딩 모델 선택 트리거
'function', 'class', 'import', 'export', 'const', 'let', 'var',
'def', 'return', 'if', 'for', 'while', 'try', 'catch', 'async', 'await',
'코드', '함수', '프로그래밍', '버그', 'API', 'HTML', 'CSS', 'JavaScript',
'Python', 'React', '개발', '구현', '디버그', '스크립트', '라이브러리',
'npm', 'pip', 'git', 'docker', '배포', '테스트', '알고리즘'
```

---

## 🚀 Phase 5 계획: 통합 및 최적화

### 2. AI CLI 도구와 RAG 통합 (현재 진행중)

**목표:**
- `ai` 명령어에 RAG 기능 추가
- 문서 기반 질의응답 지원

**구현 방향:**
```bash
# RAG 기능 추가
ai --rag "Python 파일 읽기 방법은?"  # 문서 기반 답변
ai --index ./docs/                   # 새 문서 인덱싱
ai --chat "일반 질문"                # 기존 채팅 기능
```

### 3. 전체 시스템 최적화

**성능 최적화:**
- 모델 로딩 시간 단축
- 임베딩 캐싱 구현
- 벡터 검색 성능 튜닝

---

## 📁 주요 파일 위치

```
/mnt/e/worktree/issue-1/
├── .env                                      # 환경변수 설정 (Phase 1+2)
├── Makefile                                 # make up-p1, make up-p2 명령
├── docker/
│   ├── compose.p1.yml                       # Phase 1: 기본 AI 서빙
│   └── compose.p2.yml                       # Phase 2: RAG 시스템
├── services/
│   ├── api-gateway/config.p1.yaml          # LiteLLM 설정
│   ├── embedding/                           # FastEmbed 임베딩 서비스
│   │   ├── app.py                          # FastAPI 임베딩 API
│   │   ├── requirements.txt                # PyTorch-free 의존성
│   │   └── Dockerfile
│   └── rag/                                # RAG 서비스
│       ├── app.py                          # 문서 인덱싱 + 질의응답 API
│       ├── requirements.txt
│       └── Dockerfile
├── scripts/
│   └── ai.py                               # AI CLI 도구 (자동 모델 선택)
├── models/
│   ├── qwen2.5-14b-instruct-q4_k_m.gguf     # 일반 모델 (8.4GB)
│   └── qwen2.5-coder-14b-instruct-q4_k_m.gguf # 코더 모델 (8.4GB)
├── documents/                              # RAG 인덱싱 대상 문서들
│   ├── coding_examples.md                  # 한국어 코딩 예제
│   └── project_guide.md                    # 프로젝트 가이드
└── memo.md                                 # 이 파일
```

---

## 🎯 Phase 2 최종 목표 상태 (완료!)

**Phase 1 완료 기준:** ✅ ALL COMPLETE
- [x] `make up-p1` 명령으로 서비스 정상 실행
- [x] `curl http://localhost:8001/v1/models` 정상 응답 ✅
- [x] `curl http://localhost:8001/v1/chat/completions` 정상 응답 ✅
- [x] `curl http://localhost:8000/v1/models` 정상 응답 (API Gateway) ✅
- [x] `curl http://localhost:8000/v1/chat/completions` 정상 응답 (API Gateway) ✅
- [x] VS Code/Cursor에서 `http://localhost:8000/v1` 연결 성공 ✅

**Phase 2 완료 기준:** ✅ ALL COMPLETE
- [x] FastEmbed 기반 임베딩 서비스 구현 ✅
- [x] Qdrant 벡터 데이터베이스 설정 ✅
- [x] 문서 인덱싱 API 구현 ✅
- [x] RAG 질의응답 API 구현 ✅
- [x] 한국어 문서 기반 질의응답 검증 ✅
- [x] 전체 파이프라인 통합 테스트 ✅

**핵심 성과:**
- ✅ 로컬 GGUF 모델 → OpenAI 호환 API 서빙 완료
- ✅ RTX 4050 + WSL2 환경에서 GPU 활용 완료
- ✅ 한국어 질문/응답 정상 동작 완료
- ✅ PyTorch-free RAG 시스템 구현 완료
- ✅ 문서 기반 지식 검색 및 답변 생성 완료

---

## 🚀 재시작 명령어

### Phase 1 (기본 AI 서빙)
```bash
# 현재 위치 확인
cd /mnt/e/worktree/issue-1

# Phase 1 시작
docker-compose -f docker/compose.p1.yml up -d

# 테스트
curl -s http://localhost:8001/v1/models  # 추론 서버 ✅
curl -s http://localhost:8000/v1/models  # API Gateway ✅
```

### Phase 2 (RAG 시스템 전체)
```bash
# Phase 2 전체 시작 (Phase 1 포함)
docker-compose -f docker/compose.p2.yml up -d

# 서비스 확인
curl -s http://localhost:8001/health    # 추론 서버 ✅
curl -s http://localhost:8000/health    # API Gateway ✅
curl -s http://localhost:8003/health    # 임베딩 서비스 ✅
curl -s http://localhost:6333/collections # Qdrant ✅
curl -s http://localhost:8002/health    # RAG 서비스 ✅

# RAG 기능 테스트
curl -X POST http://localhost:8002/index \
  -H "Content-Type: application/json" \
  -d '{"collection": "default"}'  # 문서 인덱싱

curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Python에서 파일을 읽는 방법", "collection": "default"}'  # RAG 질의

# AI CLI 도구 사용
python scripts/ai.py "Hello world"      # 일반 채팅
python scripts/ai.py --code "Python function to read file"  # 코딩 질문
```

### 서비스 중지
```bash
# Phase 2 전체 중지
docker-compose -f docker/compose.p2.yml down

# Phase 1만 중지
docker-compose -f docker/compose.p1.yml down
```

---

## 🚀 2025-09-23 21:20 업데이트: ChatGPT 최적화 및 7B 모델 전환

### Phase 5B: 7B 모델 최적화 (RTX 4050 6GB 특화)

**문제 인식:**
- 14B 모델 2개 + RAG 동시 실행 시 RTX 4050 6GB VRAM 부족
- RAG 서비스 LLM 타임아웃 빈발 (60초+ 소요)

**ChatGPT 제안 적용 완료:**

1. **7B 모델 다운로드 완료** ✅
   - `Qwen2.5-7B-Instruct-Q4_K_M.gguf` (4.4GB)
   - `qwen2.5-coder-7b-instruct-q4_k_m.gguf` (4.4GB)
   - 기존 14B 모델 유지 (향후 업그레이드용)

2. **Docker Compose 최적화** ✅
   - 컨텍스트 크기: 4096 → 2048
   - 병렬 처리: 2 → 1
   - GPU 레이어: 자동 최대 (999)
   - 배치 최적화: -b 256 --ubatch 128

3. **RAG 서비스 완전 재구현** ✅
   - 환경변수 기반 튜닝 시스템
   - 한국어 문장 분할기 추가
   - 컨텍스트 예산 관리 (1200 토큰)
   - 슬라이딩 청크 + 배치 임베딩

4. **임베딩 서비스 안전화** ✅
   - 입력 제한: 최대 1024개 텍스트
   - 문자 제한: 항목당 8000자
   - OOM/타임아웃 방지

5. **Prewarm 엔드포인트** ✅
   - 콜드 스타트 방지
   - 모델/서비스 사전 로딩

**현재 진행 상황:**
- Docker 빌드 진행 중 (RAG + 임베딩 서비스)
- 빌드 완료 후 7B 모델 테스트 예정

**기대 효과:**
- VRAM 사용량 50% 감소 (14B → 7B)
- RAG 응답 속도 대폭 개선
- 시스템 안정성 향상

---

## 🚀 2025-09-24 10:30 업데이트: 7B 모델 성능 최적화 완료 및 데이터 아키텍처 설계

### ✅ 7B 모델 성능 최적화 완료

**CPU 문제 해결:**
- CPU 사용량: **2000% → 13%** (99% 개선)
- Docker CPU 제한: 4.0 코어
- 스레드 제한: 4개 고정
- 배치 크기: 256 → 128

**최종 최적화 설정:**
```yaml
# RTX 4050 6GB 최적화 (7B 모델)
-t 4                    # CPU 스레드 제한
-c 1024                 # 컨텍스트 최적화 (속도 우선)
-b 128                  # 배치 크기 (메모리 효율)
--n-gpu-layers 999      # GPU 최대 활용
--parallel 1            # 단일 처리 (안정성)
```

**성능 테스트 결과:**
- **단순 질문**: ~7초 (50토큰)
- **긴 대화**: ~15초 (55% 개선)
- **복잡 코딩**: ~25-30초
- **RAG 질의**: ~24초
- **장문 처리**: 3-4천자까지 안정적

### 🏗️ 데이터 아키텍처 재설계 (PostgreSQL 추가)

**E드라이브 1TB SSD 통합 구조:**
```
/mnt/e/
├── ai-models/                    # ✅ AI 모델들 (8GB+)
├── ai-data/                      # 🆕 모든 데이터 통합
│   ├── postgresql/              # 일반 DB (메타데이터)
│   ├── vectors/                 # 벡터 DB (Qdrant)
│   ├── documents/               # 원본 문서들
│   ├── cache/                   # 처리 캐시
│   └── logs/                    # 시스템 로그
├── local-ai-suite/              # 메인 개발
└── worktree/issue-1/            # 현재 작업
```

**PostgreSQL 스키마 설계:**
- **RAG**: collections, documents, chunks, search_logs
- **MCP**: mcp_requests, notion_pages, web_scrapes
- **시스템**: system_settings, user_preferences

**데이터 분리 전략:**
- 워크트리: 임시 코드 (머지 후 삭제)
- 공통 데이터: 모델, DB, 벡터, 문서 (영구 보존)
- 확장성: 각 컴포넌트 독립 관리

### 📊 현재 완료 상태 (2025-09-24)

**Phase 1-2 완료:**
- ✅ 7B 모델 최적화 및 안정화
- ✅ CPU 사용률 99% 개선
- ✅ RAG 시스템 정상 동작
- ✅ 한국어 질의응답 완벽 지원
- ✅ 실사용 성능 검증 완료

**Phase 5C 진행 중:**
- 🔄 PostgreSQL 통합 설계
- 🔄 데이터 아키텍처 재구성
- ⏳ Docker Compose 업데이트 예정

## 🚀 2025-09-24 11:20 업데이트: PostgreSQL 통합 진행 중 (권한 이슈 발생)

### ✅ PostgreSQL 통합 구현 완료 항목

**1. 데이터 구조 생성:**
```
/mnt/e/ai-data/
├── postgresql/data     # PostgreSQL 데이터
├── vectors/qdrant      # 벡터 DB
├── documents/          # 원본 문서들
│   ├── personal/
│   ├── projects/
│   ├── knowledge/     # 테스트 문서 이동됨
│   └── uploads/
├── cache/             # 처리 캐시
└── logs/              # 시스템 로그
```

**2. PostgreSQL 설정:**
- Docker Compose에 postgres:16-alpine 추가 ✅
- 환경변수 설정 완료 ✅
- 포트: 5432, DB: ai_suite, User: ai_user ✅

**3. 데이터베이스 스키마:**
- 초기화 스크립트 생성: `docker/init-db/01-init-schema.sql` ✅
- 시드 데이터: `docker/init-db/02-seed-data.sql` ✅
- 테이블 설계: collections, documents, chunks, search_logs ✅
- MCP 테이블: mcp_requests, notion_pages, web_scrapes ✅
- 시스템 테이블: system_settings, user_preferences ✅

### ⚠️ 현재 문제: WSL 권한 이슈

**증상:**
```bash
initdb: error: could not change permissions of directory "/var/lib/postgresql/data": Operation not permitted
Status: Restarting (1)
```

**원인:**
- WSL2의 Windows 파일시스템 마운트 권한 문제
- PostgreSQL 컨테이너(UID 999)가 /mnt/e/ 경로에 쓰기 불가
- chmod 777 적용해도 WSL-Windows 경계에서 제한

**시도된 해결책:**
- 수동 권한 변경: `chmod 777` ✅ (하지만 효과 없음)
- 소유권 변경 시도: `sudo chown 999:999` (실패)

**권장 해결책:**
1. **Docker named volume 사용** (권장)
   - WSL 권한 문제 회피
   - Docker가 자동 권한 관리
   - 백업/복구 가능

2. **또는 WSL 내부 경로 사용**
   - `/var/lib/postgresql/data` 등 WSL 네이티브 경로

### 📊 현재 서비스 상태 (2025-09-24 11:20)

**정상 동작:**
- ✅ inference (port 8001) - 7B 모델 최적화 적용
- ✅ rag (port 8002) - 문서 볼륨 연결 완료
- ✅ embedding (port 8003) - 정상 동작
- ✅ qdrant (port 6333) - 벡터 스토리지 정상

**문제 있음:**
- ❌ postgres (port 5432) - 권한 문제로 재시작 반복
- ⚠️ api-gateway (port 8000) - unhealthy 상태

**다음 작업 우선순위:**
1. PostgreSQL 권한 문제 해결 (Docker volume 전환)
2. API Gateway 상태 점검
3. 통합 테스트 및 검증

---

**⏰ 마지막 업데이트:** 2025-09-24 11:20
**✅ 현재 상태:** PostgreSQL 스키마/설정 완료, WSL 권한 이슈 해결 필요
**⏭️ 다음 작업:** PostgreSQL Docker volume 전환 및 통합 테스트
