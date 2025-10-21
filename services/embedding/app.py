import os
import threading
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, Body
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator

# FastEmbed: 경량 ONNX 임베딩 (기본 CPU)
from fastembed import TextEmbedding

"""
Embedding Service (FastAPI + FastEmbed)
- POST /embed  { "texts": ["...","..."] } -> { "embeddings": [[...],[...]] }
- GET  /health -> 모델/차원/상태
- POST /reload -> 모델 교체(옵션)
환경변수:
  EMBEDDING_MODEL        (기본: BAAI/bge-small-en-v1.5)
  EMBEDDING_BATCH_SIZE   (기본: 64)
  EMBEDDING_NORMALIZE    (기본: "true" → L2 normalize)
  FASTEMBED_CACHE        (기본: ~/.cache/fastembed)
  EMBEDDING_THREADS      (기본: 0 → auto)
"""

DEFAULT_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "64"))
NORMALIZE = os.getenv("EMBEDDING_NORMALIZE", "true").lower() in {
    "1",
    "true",
    "yes",
    "y",
}
CACHE_DIR = os.getenv("FASTEMBED_CACHE", None)
NUM_THREADS = int(os.getenv("EMBEDDING_THREADS", "0"))

# 안전 제한 (OOM/타임아웃 방지)
MAX_TEXTS = int(os.getenv("EMBEDDING_MAX_TEXTS", "1024"))
MAX_CHARS = int(os.getenv("EMBEDDING_MAX_CHARS", "8000"))

app = FastAPI(title="Embedding Service (FastEmbed)", version="1.0.0")

# Prometheus metrics
Instrumentator().instrument(app).expose(app)

# ---- Global model holder (thread-safe) ----
_model_lock = threading.Lock()
_loader_guard = threading.Lock()
_model: Optional[TextEmbedding] = None
_model_name: str = DEFAULT_MODEL
_model_dim: Optional[int] = None
_model_loader: Optional[threading.Thread] = None
_last_load_error: Optional[str] = None


def _load_model(model_name: str) -> TextEmbedding:
    kwargs: Dict[str, Any] = {}
    if CACHE_DIR:
        kwargs["cache_dir"] = CACHE_DIR
    if NUM_THREADS and NUM_THREADS > 0:
        kwargs["threads"] = NUM_THREADS
    return TextEmbedding(model_name=model_name, **kwargs)


def _ensure_model() -> None:
    global _model, _model_name, _model_dim
    with _model_lock:
        if _model is None:
            _model = _load_model(_model_name)
            # 차원 파악: 짧은 텍스트 한 개 임베딩
            sample = list(_model.embed(["dimension probe"], batch_size=1, normalize=NORMALIZE))
            _model_dim = len(sample[0])


class EmbedRequest(BaseModel):
    texts: List[str]


class EmbedResponse(BaseModel):
    embeddings: List[List[float]]
    model: str
    dim: int
    normalize: bool


def _start_background_load() -> None:
    global _model_loader
    with _loader_guard:
        if _model is not None:
            return
        if _model_loader and _model_loader.is_alive():
            return

        def _target() -> None:
            global _last_load_error, _model_loader
            try:
                _ensure_model()
                _last_load_error = None
            except Exception as exc:
                _last_load_error = repr(exc)
            finally:
                with _loader_guard:
                    _model_loader = None

        _model_loader = threading.Thread(target=_target, daemon=True)
        _model_loader.start()


@app.on_event("startup")
def on_startup():
    # 지연 로딩이지만, 앱 기동은 블로킹하지 않도록 백그라운드에서만 시도
    _start_background_load()


@app.get("/health")
def health():
    _start_background_load()
    with _loader_guard:
        loader_alive = bool(_model_loader and _model_loader.is_alive())
    ok = _model is not None and not loader_alive
    return {
        "ok": ok,
        "model": _model_name,
        "dim": _model_dim,
        "batch_size": BATCH_SIZE,
        "normalize": NORMALIZE,
        "threads": NUM_THREADS,
        "loading": loader_alive,
        "error": _last_load_error,
    }


@app.post("/embed", response_model=EmbedResponse)
def embed(req: EmbedRequest = Body(...)):
    if not req.texts:
        return EmbedResponse(
            embeddings=[], model=_model_name, dim=_model_dim or 0, normalize=NORMALIZE
        )

    # 안전 제한: 입력 개수와 길이
    if len(req.texts) > MAX_TEXTS:
        req.texts = req.texts[:MAX_TEXTS]

    # 항목별 길이 제한 (초과분 컷)
    safe_texts = [t[:MAX_CHARS] if t and len(t) > MAX_CHARS else (t or "") for t in req.texts]

    _ensure_model()
    assert _model is not None

    # FastEmbed는 제너레이터 형태 -> 리스트로 수집
    vecs = list(_model.embed(safe_texts, batch_size=BATCH_SIZE, normalize=NORMALIZE))
    # 안전: float 변환
    out = [list(map(float, v)) for v in vecs]

    return EmbedResponse(
        embeddings=out,
        model=_model_name,
        dim=_model_dim or len(out[0]),
        normalize=NORMALIZE,
    )


class ReloadRequest(BaseModel):
    model: str


@app.post("/reload")
def reload_model(req: ReloadRequest):
    """모델 교체(옵션). 예: {"model": "sentence-transformers/all-MiniLM-L6-v2"}"""
    global _model, _model_name, _model_dim
    if not req.model or req.model == _model_name:
        return {"reloaded": False, "model": _model_name, "dim": _model_dim}

    with _model_lock:
        new_model = _load_model(req.model)
        # 차원 미리 확인
        sample = list(new_model.embed(["dimension probe"], batch_size=1, normalize=NORMALIZE))
        new_dim = len(sample[0])
        _model = new_model
        _model_name = req.model
        _model_dim = new_dim

    return {"reloaded": True, "model": _model_name, "dim": _model_dim}


@app.post("/prewarm")
def prewarm():
    """프리워밍: 모델 로딩 및 캐시 준비"""
    _ensure_model()
    return {"ok": True, "model": _model_name, "dim": _model_dim}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("EMBEDDING_HOST", "0.0.0.0"),  # nosec B104 - container binding by default
        port=int(os.getenv("EMBEDDING_PORT", "8003")),
    )
