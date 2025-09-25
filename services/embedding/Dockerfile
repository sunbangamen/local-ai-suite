FROM python:3.11-slim

# 기본 런타임 의존성(경량)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./

# 환경 변수 기본값 (필요 시 compose에서 오버라이드)
ENV EMBEDDING_MODEL="BAAI/bge-small-en-v1.5" \
    EMBEDDING_BATCH_SIZE="64" \
    EMBEDDING_NORMALIZE="true" \
    EMBEDDING_THREADS="0"

EXPOSE 8003
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8003", "--workers", "1"]