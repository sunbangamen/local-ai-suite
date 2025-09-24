import os
import glob
import math
import asyncio
import re
import time
import hashlib
from typing import List, Optional, Dict, Any, Tuple

import httpx
from fastapi import FastAPI, Query
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from database import db

"""
RAG FastAPI (경량/안정화 버전)
- 환경변수 기반 튜닝(토큰/타임아웃/TopK/청크)
- 임베딩 서비스와 Qdrant만 있으면 동작
- LLM 호출은 OpenAI 호환 게이트웨이(예: LiteLLM)에 위임
"""

# -------- ENV & DEFAULTS --------
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
EMBEDDING_URL = os.getenv("EMBEDDING_URL", "http://embedding:8003")

RAG_LLM_API_BASE = os.getenv("RAG_LLM_API_BASE", "http://api-gateway:8000/v1")
RAG_LLM_MODEL = os.getenv("RAG_LLM_MODEL", "local-7b")
RAG_LLM_TIMEOUT = float(os.getenv("RAG_LLM_TIMEOUT", "60"))
RAG_LLM_MAX_TOKENS = int(os.getenv("RAG_LLM_MAX_TOKENS", "256"))
RAG_LLM_TEMPERATURE = float(os.getenv("RAG_LLM_TEMPERATURE", "0.3"))

RAG_TOPK = int(os.getenv("RAG_TOPK", "4"))
RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "512"))
RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "100"))

DOCUMENTS_DIR = os.getenv("DOCUMENTS_DIR", "./documents")
COLLECTION_DEFAULT = os.getenv("RAG_DEFAULT_COLLECTION", "myproj")

# 게이트웨이 스트리밍은 클라이언트에서 설정, 여기서는 비스트림 기본
OPENAI_CHAT_COMPLETIONS = f"{RAG_LLM_API_BASE}/chat/completions"

# -------- FastAPI --------
app = FastAPI(title="RAG Service", version="1.0.0")

# -------- Globals --------
qdrant: Optional[QdrantClient] = None
EMBED_DIM: Optional[int] = None


# -------- Models --------
class IndexResponse(BaseModel):
    collection: str
    chunks: int


class QueryRequest(BaseModel):
    query: str
    collection: Optional[str] = None
    topk: Optional[int] = None


class QueryResponse(BaseModel):
    answer: str
    context: List[Dict[str, Any]]
    usage: Dict[str, Any]
    cached: Optional[bool] = False
    response_time_ms: Optional[int] = None

class AnalyticsResponse(BaseModel):
    total_searches: int
    avg_response_time: float
    avg_results_count: float
    total_tokens: int
    top_queries: List[Dict[str, Any]]
    collection_usage: List[Dict[str, Any]]


# -------- Utils --------
def _approx_tokens(text: str) -> int:
    # 매우 러프한 토큰 근사(영문/한글 혼용 환경에서 대략 단어당 1~2토큰 가정)
    # chunk size는 "토큰" 기준으로 쓰지만 실제론 단어 수로 근사
    return max(1, math.ceil(len(text) / 4))  # 대강 4문자 ≈ 1토큰


# 한국어 문장 분할기 (품질 향상)
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|(?<=\n)\s*")

def _split_sentences_ko(text: str, max_chars: int = 400) -> List[str]:
    """
    한국어 문장 분할 (간단 버전)
    매우 단순: 문장 구분자 기준 → 너무 길면 다시 고정폭 슬라이스
    """
    parts = [p.strip() for p in _SENT_SPLIT.split(text) if p.strip()]
    out, buf = [], ""
    for p in parts:
        if len(buf) + len(p) + 1 <= max_chars:
            buf = (buf + " " + p).strip()
        else:
            if buf:
                out.append(buf)
            buf = p if len(p) <= max_chars else p[:max_chars]
    if buf:
        out.append(buf)
    return out


def _sliding_chunks(text: str, chunk_tokens: int, overlap_tokens: int) -> List[str]:
    words = text.split()
    # 단어 수 기준으로 근사 변환
    # (chunk_tokens ~ 단어수로 취급)
    size = max(8, chunk_tokens)  # 안전 하한
    step = max(1, size - overlap_tokens)
    chunks = []
    for i in range(0, len(words), step):
        w = words[i : i + size]
        if not w:
            break
        chunks.append(" ".join(w))
        if i + size >= len(words):
            break
    return chunks


async def _probe_embedding_dim(client: httpx.AsyncClient) -> int:
    # 임베딩 서비스 규약: POST /embed  { "texts": ["..."] } -> { "embeddings": [[...]] }
    r = await client.post(f"{EMBEDDING_URL}/embed", json={"texts": ["dimension probe"]}, timeout=30.0)
    r.raise_for_status()
    data = r.json()
    emb = data["embeddings"][0]
    return len(emb)


async def _embed_texts(client: httpx.AsyncClient, texts: List[str]) -> List[List[float]]:
    r = await client.post(f"{EMBEDDING_URL}/embed", json={"texts": texts}, timeout=60.0)
    r.raise_for_status()
    data = r.json()
    return data["embeddings"]


async def _llm_answer(client: httpx.AsyncClient, system: str, user: str) -> Tuple[str, Dict[str, Any]]:
    payload = {
        "model": RAG_LLM_MODEL,
        "temperature": RAG_LLM_TEMPERATURE,
        "max_tokens": RAG_LLM_MAX_TOKENS,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    r = await client.post(OPENAI_CHAT_COMPLETIONS, json=payload, timeout=RAG_LLM_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    return content, usage


def _ensure_collection(collection: str, dim: int):
    assert qdrant is not None
    existing = [c.name for c in qdrant.get_collections().collections]
    if collection in existing:
        return
    qdrant.create_collection(
        collection_name=collection,
        vectors_config=qmodels.VectorParams(size=dim, distance=qmodels.Distance.COSINE),
    )


def _upsert_points(collection: str, embeddings: List[List[float]], payloads: List[Dict[str, Any]]):
    assert qdrant is not None
    points = []
    for idx, (vec, pl) in enumerate(zip(embeddings, payloads)):
        points.append(qmodels.PointStruct(id=pl["point_id"], vector=vec, payload=pl))
    qdrant.upsert(collection_name=collection, points=points)


def _search(collection: str, query_vec: List[float], topk: int) -> List[Dict[str, Any]]:
    assert qdrant is not None
    res = qdrant.search(
        collection_name=collection,
        query_vector=query_vec,
        limit=topk,
        with_payload=True,
        score_threshold=None,
    )
    out = []
    for p in res:
        item = {
            "id": p.id,
            "score": p.score,
            **(p.payload or {}),
        }
        out.append(item)
    return out


def _read_documents(path: str) -> List[Tuple[str, str]]:
    """
    지정 폴더에서 텍스트 파일 읽기. (md/txt)
    반환: [(doc_id, text), ...]
    """
    files = sorted(glob.glob(os.path.join(path, "**", "*.*"), recursive=True))
    out = []
    for f in files:
        if f.lower().endswith((".md", ".txt")):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    out.append((f, fp.read()))
            except Exception:
                # 파일 하나 실패해도 전체 인덱싱은 계속
                continue
    return out


# -------- Lifespan --------
@app.on_event("startup")
async def on_startup():
    global qdrant, EMBED_DIM
    qdrant = QdrantClient(url=QDRANT_URL, timeout=30.0)
    async with httpx.AsyncClient() as client:
        try:
            EMBED_DIM = await _probe_embedding_dim(client)
        except Exception:
            # 임베딩 서버가 아직 안 떠 있을 수 있음 -> 지연 초기화
            EMBED_DIM = None


# -------- Routes --------
@app.get("/health")
async def health(llm: bool = Query(False, description="LLM까지 점검하려면 true")):
    # Qdrant 체크
    q_ok = False
    try:
        assert qdrant is not None
        _ = qdrant.get_collections()
        q_ok = True
    except Exception:
        q_ok = False

    # 임베딩 체크
    e_ok = False
    dim = None
    try:
        async with httpx.AsyncClient() as client:
            dim = await _probe_embedding_dim(client)
            e_ok = dim > 0
    except Exception:
        e_ok = False

    # LLM 체크(옵션)
    l_ok = None
    if llm:
        try:
            async with httpx.AsyncClient() as client:
                ans, _ = await _llm_answer(client, "You are a health checker.", "Reply with 'ok'.")
                l_ok = ans.strip().lower().startswith("ok")
        except Exception:
            l_ok = False

    return {
        "qdrant": q_ok,
        "embedding": e_ok,
        "embed_dim": dim,
        "llm": l_ok,
        "config": {
            "RAG_TOPK": RAG_TOPK,
            "RAG_CHUNK_SIZE": RAG_CHUNK_SIZE,
            "RAG_CHUNK_OVERLAP": RAG_CHUNK_OVERLAP,
            "RAG_LLM_TIMEOUT": RAG_LLM_TIMEOUT,
            "RAG_LLM_MAX_TOKENS": RAG_LLM_MAX_TOKENS,
        },
    }


@app.post("/index", response_model=IndexResponse)
async def index(collection: Optional[str] = Query(None, description="컬렉션 이름")):
    """
    ./documents 아래 md/txt를 읽어 chunk → embed → Qdrant upsert
    """
    col = collection or COLLECTION_DEFAULT
    docs = _read_documents(DOCUMENTS_DIR)

    if not docs:
        return IndexResponse(collection=col, chunks=0)

    async with httpx.AsyncClient() as client:
        # embed dim lazy init
        global EMBED_DIM
        if EMBED_DIM is None:
            EMBED_DIM = await _probe_embedding_dim(client)

        _ensure_collection(col, EMBED_DIM)

        all_chunks: List[str] = []
        payloads: List[Dict[str, Any]] = []

        chunk_tokens = RAG_CHUNK_SIZE
        overlap_tokens = min(RAG_CHUNK_OVERLAP, RAG_CHUNK_SIZE - 8)

        pid = 0
        for doc_id, text in docs:
            # Calculate document metadata
            file_size = len(text.encode('utf-8'))
            checksum = hashlib.sha256(text.encode()).hexdigest()[:16]

            # 너무 큰 문서 방어적 컷(선택)
            if _approx_tokens(text) > 200_000:
                text = text[:800_000]  # 대략 컷

            # 1) 먼저 문장 단위로 전처리 (한국어 품질 향상)
            sentences = _split_sentences_ko(text, max_chars=400)
            text = "\n".join(sentences)

            # 2) 기존 슬라이딩 청크 적용
            chunks = _sliding_chunks(text, chunk_tokens, overlap_tokens)
            for i, ch in enumerate(chunks):
                all_chunks.append(ch)
                payloads.append(
                    {
                        "point_id": pid,  # Use integer ID instead of string
                        "doc_id": doc_id,
                        "chunk_id": i,
                        "text": ch,
                        "source": doc_id,
                    }
                )
                pid += 1

        if not all_chunks:
            return IndexResponse(collection=col, chunks=0)

        # 임베딩 (배치 처리)
        # 너무 길면 끊어서
        batch = 64
        embeddings: List[List[float]] = []
        for i in range(0, len(all_chunks), batch):
            eb = await _embed_texts(client, all_chunks[i : i + batch])
            embeddings.extend(eb)

        _upsert_points(col, embeddings, payloads)

        # Update document metadata for each processed document
        embedding_model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
        doc_chunks = {}
        for pl in payloads:
            doc_id = pl['doc_id']
            if doc_id not in doc_chunks:
                doc_chunks[doc_id] = 0
            doc_chunks[doc_id] += 1

        # Find original docs to get metadata
        for doc_id, text in docs:
            if doc_id in doc_chunks:
                file_size = len(text.encode('utf-8'))
                checksum = hashlib.sha256(text.encode()).hexdigest()[:16]
                db.update_document_metadata(
                    doc_id=doc_id,
                    filename=os.path.basename(doc_id),
                    file_size=file_size,
                    chunk_count=doc_chunks[doc_id],
                    embedding_model=embedding_model,
                    checksum=checksum
                )

        return IndexResponse(collection=col, chunks=len(all_chunks))


@app.post("/query", response_model=QueryResponse)
async def query(body: QueryRequest):
    """
    질의 → 임베딩 → Qdrant 검색 → 컨텍스트 구성 → LLM 답변
    Performance optimized with caching and analytics
    """
    start_time = time.time()
    col = body.collection or COLLECTION_DEFAULT
    topk = body.topk or RAG_TOPK
    q = (body.query or "").strip()
    if not q:
        return QueryResponse(answer="", context=[], usage={"error": "empty query"})

    # Check cache first
    cached_result = db.get_cached_query(q, col)
    if cached_result:
        response_time_ms = int((time.time() - start_time) * 1000)
        return QueryResponse(
            answer=cached_result['response'],
            context=cached_result['context_data'],
            usage={"cached": True, "cached_at": cached_result['cached_at']},
            cached=True,
            response_time_ms=response_time_ms
        )

    async with httpx.AsyncClient() as client:
        # embed dim lazy init
        global EMBED_DIM
        if EMBED_DIM is None:
            EMBED_DIM = await _probe_embedding_dim(client)

        # ensure collection 존재
        _ensure_collection(col, EMBED_DIM)

        # Time embedding
        embed_start = time.time()
        qvec = (await _embed_texts(client, [q]))[0]
        embed_time_ms = (time.time() - embed_start) * 1000

        # Time vector search
        search_start = time.time()
        hits = _search(col, qvec, topk)
        search_time_ms = (time.time() - search_start) * 1000

        # 컨텍스트 구성(길이 제한 방어)
        ctx_texts = []
        total_tokens = 0
        budget = 1200  # 프롬프트 컨텍스트 예산(모델 ctx 2048 기준 안전치)
        for h in hits:
            t = h.get("text", "")
            t_tokens = _approx_tokens(t)
            if total_tokens + t_tokens > budget:
                # 너무 길면 자르기
                remain = max(0, budget - total_tokens)
                if remain > 0:
                    approx_chars = remain * 4
                    t = t[:approx_chars]
                    t_tokens = _approx_tokens(t)
                else:
                    break
            ctx_texts.append(t)
            total_tokens += t_tokens

        system_msg = (
            "You are a concise assistant. Use ONLY the provided context to answer. "
            "If the answer is not in the context, say you don't know."
        )
        user_msg = (
            "Question:\n"
            f"{q}\n\n"
            "Context:\n"
            + "\n\n".join([f"[{i+1}] {c}" for i, c in enumerate(ctx_texts)])
            + "\n\nAnswer in Korean."
        )

        # Time LLM response
        llm_start = time.time()
        answer, usage = await _llm_answer(client, system_msg, user_msg)
        llm_time_ms = int((time.time() - llm_start) * 1000)

        # Calculate total response time
        total_time_ms = int((time.time() - start_time) * 1000)

        # 응답에 참고 문맥 정보 반환
        ctx_out = [{"score": h.get("score", 0.0), "doc_id": h.get("doc_id"), "chunk_id": h.get("chunk_id")} for h in hits]

        # Cache the result for future queries
        db.cache_query(q, col, answer, ctx_out, ttl_hours=6)  # Cache for 6 hours

        # Log search analytics
        db.log_search(
            collection=col,
            query=q,
            results_count=len(hits),
            response_time_ms=total_time_ms,
            llm_tokens_used=usage.get('total_tokens', 0),
            embedding_time_ms=int(embed_time_ms),
            vector_search_time_ms=int(search_time_ms),
            llm_response_time_ms=llm_time_ms,
            context_length=len('\n'.join(ctx_texts))
        )

        # Track document access for analytics
        for h in hits:
            if h.get('doc_id'):
                db.track_document_access(h['doc_id'])

        return QueryResponse(answer=answer, context=ctx_out, usage=usage,
                           cached=False, response_time_ms=total_time_ms)


@app.post("/prewarm")
async def prewarm():
    """프리워밍: 모델/서비스 준비 및 첫 호출 최적화"""
    global EMBED_DIM
    async with httpx.AsyncClient() as client:
        if EMBED_DIM is None:
            EMBED_DIM = await _probe_embedding_dim(client)
        # LLM 한 번 호출(아주 짧게)
        try:
            await _llm_answer(client, "You are prewarming.", "ok")
        except Exception:
            pass
    return {"ok": True, "embed_dim": EMBED_DIM}


@app.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(hours: int = Query(24, description="Hours to look back")):
    """Get search analytics for the specified time period"""
    analytics = db.get_search_analytics(hours)
    return AnalyticsResponse(**analytics)


@app.post("/optimize")
async def optimize_database():
    """Run database optimization and cleanup"""
    result = db.optimize_database()
    return {"message": "Database optimized", **result}


@app.get("/cache/stats")
async def cache_stats():
    """Get cache statistics"""
    with db.transaction() as conn:
        cursor = conn.execute("""
            SELECT
                COUNT(*) as total_entries,
                AVG(accessed_count) as avg_access_count,
                COUNT(CASE WHEN expires_at > CURRENT_TIMESTAMP THEN 1 END) as active_entries,
                COUNT(CASE WHEN expires_at <= CURRENT_TIMESTAMP THEN 1 END) as expired_entries
            FROM query_cache
        """)
        stats = dict(cursor.fetchone())

    return stats


@app.delete("/cache")
async def clear_cache():
    """Clear query cache"""
    with db.transaction() as conn:
        cursor = conn.execute("DELETE FROM query_cache")
        cleared = cursor.rowcount

    return {"message": f"Cleared {cleared} cache entries"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)