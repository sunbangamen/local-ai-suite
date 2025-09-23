# Repository Guidelines

## 프로젝트 구조 & 모듈 구성
- `docker/`: Phase 1/2용 Compose 파일(`compose.p1.yml`, `compose.p2.yml`).
- `services/`: 애플리케이션 서비스
  - `api-gateway/`: LiteLLM 설정(OpenAI 호환 프록시)
  - `embedding/`: FastEmbed(ONNX) 기반 FastAPI — 포트 8003
  - `rag/`: Qdrant + LLM 기반 RAG FastAPI — 포트 8002
- `models/`: 로컬 GGUF 모델(추론 컨테이너에 읽기 전용 마운트)
- `documents/`: RAG 인덱싱 대상 문서
- `scripts/`: CLI 도구(`ai`, `ai.py`, `download-models.sh` 등)
- `data/`, `docs/`: 데이터/문서 산출물

## 빌드, 테스트, 로컬 실행
- `make up-p1`: 추론 + 게이트웨이(Phase 1) 기동. `curl http://localhost:8000/health`로 확인.
- `make up-p2`: Phase 1 + Qdrant, Embedding, RAG 기동.
  - 인덱스: `curl -X POST "http://localhost:8002/index?collection=myproj"`
  - 질의: `curl -H 'Content-Type: application/json' -d '{"query":"...","collection":"myproj"}' http://localhost:8002/query`
- `make down`: 전체 중지. `make logs`: 현재 스택 로그 팔로우.
- 참고: `up-p3` 타깃은 있으나 `docker/compose.p3.yml`은 아직 없습니다.

## 코딩 스타일 & 네이밍 규칙
- Python 3.11(FastAPI). 타입 힌트와 Pydantic 모델 사용.
- 들여쓰기 4칸, 가능하면 줄 길이 100자 이내.
- 네이밍: 함수/변수/파일 `snake_case`, 클래스 `PascalCase`, 상수 `UPPER_SNAKE`.
- 의존성은 각 서비스의 `requirements.txt`에 고정(pinned).
- 포매팅/린팅: Black + Ruff 권장(도입 시 설정 파일 포함).

## 테스트 가이드
- 프레임워크: pytest + `httpx.AsyncClient`(FastAPI 엔드포인트 테스트).
- 위치: 서비스 인접 배치(예: `services/rag/tests/`).
- 명명: 파일 `test_*.py`, 함수 `test_*`.
- 실행: dev 의존성에 pytest 추가 후 `pytest -q`. 당장은 health 엔드포인트와 위 curl로 수동 검증.

## 커밋 & PR 가이드
- 커밋: Conventional Commits(히스토리 참조) — `feat:`, `fix:`, `add:` 등. 필요 시 스코프 표기(e.g., `feat(rag): ...`).
- PR에는 다음 포함:
  - 요약/배경과 영향 받는 서비스/경로
  - 연결 이슈(`Closes #123` 등)
  - 로컬 검증 단계(`make up-p2`, 예시 `curl`)와 스크린샷/로그
  - 설정 변경(`.env`, 포트 등) 명확히 표기

## 보안 & 설정 팁
- 서비스는 로컬호스트로만 바인딩하고 외부 노출 금지.
- `.env`로 포트/모델 제어, 비밀값 커밋 금지. GGUF는 `models/`에 배치.
- llama.cpp 사용 시 Docker Desktop/WSL의 GPU 사용 설정과 드라이버 확인.
