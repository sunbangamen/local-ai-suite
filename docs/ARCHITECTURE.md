# 📦 Local AI Suite — 단계별 스캐폴드 (Claude Code & Codex 친화형)

> 외장 SSD(1TB) + RTX 4050 기준.
> **Phase 1 → 3** 순서로 점진 구축. 각 Phase는 독립 실행 가능.
>
> ✅ *모든 파일은 이 문서의 경로/내용대로 복붙하면 바로 시작할 수 있게 구성했습니다.*

---

## 🗂️ 0. 리포지토리 구조 (최종)

```
local-ai-suite/
├─ README.md
├─ Makefile
├─ .env.example
├─ docker/
│  ├─ compose.p1.yml   # Phase 1 (모델 + OpenAI 호환 게이트웨이)
│  ├─ compose.p2.yml   # Phase 2 (RAG + Qdrant + reranker 추가)
│  └─ compose.p3.yml   # Phase 3 (MCP 서버 추가)
├─ services/
│  ├─ api-gateway/
│  │  ├─ config.p1.yaml
│  │  └─ config.p2.yaml
│  ├─ inference/        # (선택) 로컬 실행 스크립트/헬퍼
│  ├─ rag/
│  │  ├─ Dockerfile
│  │  ├─ requirements.txt
│  │  └─ app.py
│  ├─ reranker/
│  │  ├─ Dockerfile
│  │  ├─ requirements.txt
│  │  └─ serve_reranker.py
│  └─ mcp/
│     ├─ Dockerfile
│     ├─ requirements.txt
│     └─ servers/
│        ├─ fs_server.py
│        ├─ git_server.py
│        └─ shell_server.py
├─ models/             # GGUF/OLLAMA 캐시(외장 SSD)
└─ data/
   ├─ rag_docs/        # PDF/MD/코드/문서 원본
   ├─ chunks/
   ├─ indices/
   └─ cache/
```

---

## 📘 1) README.md (리포 최상단)

**`README.md`**

````markdown
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
````

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

```
```

---

## ⚙️ 2) Makefile

**`Makefile`**

```make
.PHONY: up-p1 up-p2 up-p3 down logs

up-p1:
	docker compose -f docker/compose.p1.yml --env-file .env up -d --build

up-p2:
	docker compose -f docker/compose.p2.yml --env-file .env up -d --build

up-p3:
	docker compose -f docker/compose.p3.yml --env-file .env up -d --build

down:
	docker compose -f docker/compose.p3.yml down || true
	docker compose -f docker/compose.p2.yml down || true
	docker compose -f docker/compose.p1.yml down || true

logs:
	docker compose -f docker/compose.p3.yml logs -f || \
	docker compose -f docker/compose.p2.yml logs -f || \
	docker compose -f docker/compose.p1.yml logs -f
```

---

## 🔐 3) .env.example

**`.env.example`**

```dotenv
# 공통
HOST=0.0.0.0
API_GATEWAY_PORT=8000
INFERENCE_PORT=8001
RAG_PORT=8002
RERANKER_PORT=8003
MCP_PORT=8020

# 모델 파일명(실제 파일은 models/ 폴더에 둠)
CHAT_MODEL=llama3.1-8b-instruct-q4_k_m.gguf
CODE_MODEL=qwen2.5-coder-7b-q4_k_m.gguf

# RAG
QDRANT_URL=http://qdrant:6333
EMBEDDING_MODEL=bge-m3
RERANKER_URL=http://reranker:8003
```

> `.env`는 `.env.example`을 복사해 채우세요.

---

## 🐳 4) docker/compose.p1.yml (Phase 1)

**`docker/compose.p1.yml`**

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
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: ["gpu"]

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

---

## 🔌 5) services/api-gateway/config.p1.yaml (Phase 1)

**`services/api-gateway/config.p1.yaml`**

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

> VS Code/Cursor는 `http://localhost:8000/v1` 로 연결하세요.

---

## 🐳 6) docker/compose.p2.yml (Phase 2)

**`docker/compose.p2.yml`**

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
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: ["gpu"]

  qdrant:
    image: qdrant/qdrant:v1.11.0
    volumes:
      - ./qdrant:/qdrant/storage
    ports:
      - "6333:6333"
      - "6334:6334"

  reranker:
    build: ../services/reranker
    ports:
      - "${RERANKER_PORT:-8003}:8003"
    depends_on: [qdrant]

  rag:
    build: ../services/rag
    env_file: ../.env
    volumes:
      - ../data:/data
    ports:
      - "${RAG_PORT:-8002}:8002"
    depends_on: [qdrant, reranker]

  api-gateway:
    image: ghcr.io/berriai/litellm:latest
    environment:
      - LITELLM_CONFIG=/app/config.yaml
    volumes:
      - ../services/api-gateway/config.p2.yaml:/app/config.yaml
    ports:
      - "${API_GATEWAY_PORT:-8000}:8000"
    depends_on:
      - inference
      - rag
```

---

## 🔌 7) services/api-gateway/config.p2.yaml (Phase 2)

**`services/api-gateway/config.p2.yaml`**

```yaml
model_list:
  - model_name: "local-chat"
    litellm_params:
      model: "openai/generic"
      api_base: "http://inference:8001/v1"
      api_key: "none"

rag_providers:
  - name: "rag"
    base_url: "http://rag:8002"

defaults:
  temperature: 0.2
  max_tokens: 1024

server:
  host: 0.0.0.0
  port: 8000
```

---

## 🧠 8) services/rag/Dockerfile

**`services/rag/Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py ./
EXPOSE 8002
CMD ["python", "app.py"]
```

### services/rag/requirements.txt

**`services/rag/requirements.txt`**

```txt
fastapi==0.112.0
uvicorn[standard]==0.30.5
httpx==0.27.0
qdrant-client==1.9.2
pydantic==2.8.2
python-multipart==0.0.9
nltk==3.9.1
sentence-transformers==3.0.1
```

### services/rag/app.py (미니멀 RAG API)

**`services/rag/app.py`**

```python
from fastapi import FastAPI, UploadFile, File, Query
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
import os, glob, json

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bge-m3")
RERANKER_URL = os.getenv("RERANKER_URL", "http://localhost:8003")
DOC_DIR = "/data/rag_docs"

app = FastAPI(title="RAG Service")

# --- 매우 단순한 임베딩 placeholder (실전에서는 bge-m3 로 교체) ---
from sentence_transformers import SentenceTransformer
_embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

qdrant = QdrantClient(url=QDRANT_URL)

class QueryBody(BaseModel):
    query: str
    collection: str
    top_k: int = 5

@app.post("/index")
def index_collection(collection: str = Query(...)):
    # 1) 컬렉션 생성(없으면)
    qdrant.recreate_collection(
        collection_name=collection,
        vectors_config=qm.VectorParams(size=_embedder.get_sentence_embedding_dimension(), distance=qm.Distance.COSINE),
    )
    # 2) 파일 로드 & 분할(간단)
    docs = []
    for path in glob.glob(f"{DOC_DIR}/**/*", recursive=True):
        if os.path.isfile(path) and not os.path.basename(path).startswith('.'):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                if text.strip():
                    docs.append({"id": path, "text": text[:5000]})  # 데모: 앞부분만
            except Exception:
                pass
    # 3) 임베딩 & 업서트
    payloads = []
    vectors = []
    ids = []
    for d in docs:
        vec = _embedder.encode(d["text"]).tolist()
        ids.append(d["id"])  # path를 id로
        vectors.append(vec)
        payloads.append({"path": d["id"], "preview": d["text"][:200]})

    if vectors:
        qdrant.upsert(collection_name=collection, points=qm.Batch(ids=ids, vectors=vectors, payloads=payloads))
    return {"ok": True, "count": len(vectors)}

@app.post("/query")
def query_rag(body: QueryBody):
    q = body.query
    q_vec = _embedder.encode(q).tolist()
    res = qdrant.search(collection_name=body.collection, query_vector=q_vec, limit=body.top_k)
    # (선택) reranker 호출 생략 — 데모 단순화
    contexts = [
        {
            "score": float(hit.score),
            "path": hit.payload.get("path"),
            "preview": hit.payload.get("preview"),
        }
        for hit in res
    ]
    return {"query": q, "contexts": contexts}
```

> 실전에서는 bge-m3 임베딩 + reranker(아래)로 고도화하세요. 여기선 Phase 2 데모를 위해 간소화.

---

## 🧮 9) services/reranker

**`services/reranker/Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY serve_reranker.py ./
EXPOSE 8003
CMD ["python", "serve_reranker.py"]
```

**`services/reranker/requirements.txt`**

```txt
fastapi==0.112.0
uvicorn[standard]==0.30.5
scikit-learn==1.5.1
numpy==1.26.4
```

**`services/reranker/serve_reranker.py`**

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Reranker Stub")

class Item(BaseModel):
    text: str
    score: float

class RankBody(BaseModel):
    query: str
    items: list[Item]

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/rank")
def rank(body: RankBody):
    # 데모: 점수 내림차순만 (실전엔 bge-reranker 적용)
    ranked = sorted(body.items, key=lambda x: x.score, reverse=True)
    return {"items": [i.model_dump() for i in ranked]}
```

---

## 🧰 10) docker/compose.p3.yml (Phase 3: MCP)

**`docker/compose.p3.yml`**

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
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: ["gpu"]

  qdrant:
    image: qdrant/qdrant:v1.11.0
    volumes:
      - ./qdrant:/qdrant/storage
    ports: ["6333:6333", "6334:6334"]

  reranker:
    build: ../services/reranker
    ports: ["${RERANKER_PORT:-8003}:8003"]
    depends_on: [qdrant]

  rag:
    build: ../services/rag
    env_file: ../.env
    volumes:
      - ../data:/data
    ports: ["${RAG_PORT:-8002}:8002"]
    depends_on: [qdrant, reranker]

  api-gateway:
    image: ghcr.io/berriai/litellm:latest
    environment:
      - LITELLM_CONFIG=/app/config.yaml
    volumes:
      - ../services/api-gateway/config.p2.yaml:/app/config.yaml
    ports: ["${API_GATEWAY_PORT:-8000}:8000"]
    depends_on: [inference, rag]

  mcp:
    build: ../services/mcp
    volumes:
      - ../services/mcp:/app
      - ..:/workspace
    ports: ["${MCP_PORT:-8020}:8020"]
```

---

## 🧩 11) services/mcp (fs/git/shell — 데모)

**`services/mcp/Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY servers/ ./servers/
EXPOSE 8020
CMD ["python", "servers/fs_server.py"]
```

**`services/mcp/requirements.txt`**

```txt
fastapi==0.112.0
uvicorn[standard]==0.30.5
gitpython==3.1.43
```

**`services/mcp/servers/fs_server.py`**

```python
from fastapi import FastAPI
from pydantic import BaseModel
import os, pathlib

ROOT = pathlib.Path("/workspace").resolve()
app = FastAPI(title="MCP FS Server")

class ReadBody(BaseModel):
    path: str

class WriteBody(BaseModel):
    path: str
    content: str

@app.get("/health")
def health():
    return {"ok": True, "root": str(ROOT)}

@app.post("/fs/read")
def fs_read(body: ReadBody):
    p = (ROOT / body.path.lstrip("/ ")).resolve()
    if not str(p).startswith(str(ROOT)):
        return {"error": "out-of-root"}
    if not p.exists():
        return {"error": "not-found"}
    return {"path": str(p), "content": p.read_text(encoding="utf-8", errors="ignore")[:200000]}

@app.post("/fs/write")
def fs_write(body: WriteBody):
    p = (ROOT / body.path.lstrip("/ ")).resolve()
    if not str(p).startswith(str(ROOT)):
        return {"error": "out-of-root"}
    os.makedirs(p.parent, exist_ok=True)
    p.write_text(body.content, encoding="utf-8")
    return {"ok": True, "path": str(p)}
```

> `git_server.py`, `shell_server.py`도 같은 패턴으로 확장 가능.

---

## ✅ 12) 사용 순서 요약 (Claude Code / Codex 친화)

1. **리포 생성** 후 본 문서대로 파일/폴더 생성 → `.env.example` 복사해 `.env` 준비
2. **Phase 1**: `make up-p1` → VS Code에서 `http://localhost:8000/v1` 설정
3. **Phase 2**: `make up-p2` → `data/rag_docs`에 문서 넣고 인덱싱/질의
4. **Phase 3**: `make up-p3` → MCP 엔드포인트로 파일 읽기/쓰기 자동화 연결
5. 모델 전환은 `.env`의 `CHAT_MODEL`/`CODE_MODEL` 교체(파일만 바꾸면 즉시 반영)

---

## 🧪 13) 헬스체크 커맨드 모음

```bash
# 게이트웨이(Phase 1~)
curl http://localhost:8000/v1/models

# 추론 서버(Phase 1~)
curl http://localhost:8001/health || true  # 일부 빌드엔 /health 미제공

# Qdrant 대시보드(Phase 2~)
open http://localhost:6333/dashboard || xdg-open http://localhost:6333/dashboard || start http://localhost:6333/dashboard

# RAG(Phase 2~)
curl -X POST "http://localhost:8002/index?collection=test"
curl -H "Content-Type: application/json" -d '{"query":"hello","collection":"test"}' http://localhost:8002/query

# MCP(Phase 3~)
curl http://localhost:8020/health
```

---

## 📝 메모

* 성능이 느리면 `--parallel`, `--ctx-size`, 양자화(q4\_k\_m) 조정
* 긴 문서 질의는 RAG를 기본 경로로(컨텍스트 최소화)
* 로컬 전제라 인증 생략. 외부 노출 금지

```
```
