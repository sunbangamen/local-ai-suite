# Phase 2 RAG 시스템 구현 완료 상태 및 점검사항

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

**⏰ 마지막 업데이트:** 2025-09-23 12:49
**✅ 현재 상태:** Phase 2 RAG 시스템 완전 구현 완료
**⏭️ 다음 작업:** Phase 3 MCP 서버 구현 + AI CLI와 RAG 통합
