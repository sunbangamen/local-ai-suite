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

## 폴더 요약

* `docker/compose.p1.yml` : 추론서버 + API 게이트웨이(litellm)
* `docker/compose.p2.yml` : + Qdrant + RAG(FastAPI) + reranker
* `docker/compose.p3.yml` : + MCP 서버(fs/git/shell)

## 보안

* 모든 서비스는 로컬호스트만 노출 권장.
* 외부 포트 개방 금지. 토큰/키 필요 없음(완전 로컬 전제).

## 트러블슈팅

* 모델 경로/파일명 오타 → `docker logs`에서 확인
* GPU 인식 안될 때 → Docker Desktop에서 WSL GPU 지원/드라이버 확인
* RAG 품질이 낮을 때 → bge-m3 임베딩, bge-reranker 설정 확인