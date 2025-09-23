#!/usr/bin/env python3
"""
RAG (Retrieval-Augmented Generation) Service
Document indexing and query service for Local AI Suite
"""

import os
import asyncio
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import hashlib

from fastapi import FastAPI, HTTPException, UploadFile, File, Query as QueryParam, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
import tiktoken

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
EMBEDDING_URL = os.getenv("EMBEDDING_URL", "http://localhost:8003")
LLM_URL = os.getenv("LLM_URL", "http://localhost:8000/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5-14b-instruct")
DOCUMENTS_DIR = Path("/app/documents")

# Initialize FastAPI
app = FastAPI(
    title="RAG Service",
    description="Document indexing and retrieval service for Local AI Suite",
    version="1.0.0"
)

# Initialize clients
qdrant_client = QdrantClient(url=QDRANT_URL)

# Pydantic models
class QueryRequest(BaseModel):
    query: str
    collection: str = "default"
    limit: int = 5
    score_threshold: float = 0.7
    include_context: bool = True

class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    context_used: str

class IndexRequest(BaseModel):
    collection: str = "default"
    chunk_size: int = 1000
    chunk_overlap: int = 200

# Utility functions
def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
    """Split text into overlapping chunks"""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        # Try to break at sentence boundaries
        if end < len(text):
            last_period = chunk.rfind('.')
            last_newline = chunk.rfind('\n')
            break_point = max(last_period, last_newline)

            if break_point > start + chunk_size // 2:
                chunk = text[start:start + break_point + 1]
                end = start + break_point + 1

        chunks.append(chunk.strip())
        start = end - chunk_overlap

        if start >= len(text):
            break

    return chunks

def get_file_hash(file_path: Path) -> str:
    """Generate hash for file content"""
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

async def get_embeddings(texts: List[str]) -> List[List[float]]:
    """Get embeddings from embedding service"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{EMBEDDING_URL}/embed",
                json={"inputs": texts}
            )
            response.raise_for_status()
            result = response.json()
            return result["embeddings"]
        except Exception as e:
            logger.error(f"Error getting embeddings: {e}")
            raise HTTPException(status_code=500, detail=f"Embedding service error: {e}")

async def query_llm(prompt: str, context: str = "") -> str:
    """Query the LLM with context"""
    system_prompt = """You are a helpful assistant. Use the provided context to answer questions accurately.
If the context doesn't contain relevant information, say so clearly.

Context:
{context}

Answer the following question based on the context above:"""

    messages = [
        {"role": "system", "content": system_prompt.format(context=context)},
        {"role": "user", "content": prompt}
    ]

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{LLM_URL}/chat/completions",
                json={
                    "model": LLM_MODEL,
                    "messages": messages,
                    "max_tokens": 1000,
                    "temperature": 0.3
                }
            )
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"Error querying LLM: {e}")
            raise HTTPException(status_code=500, detail=f"LLM service error: {e}")

# API Routes
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check Qdrant connection
        collections = qdrant_client.get_collections()

        # Check embedding service
        async with httpx.AsyncClient(timeout=5.0) as client:
            emb_response = await client.get(f"{EMBEDDING_URL}/health")
            emb_response.raise_for_status()

        return {"status": "healthy", "services": {"qdrant": "ok", "embedding": "ok"}}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.get("/collections")
async def list_collections():
    """List all available collections"""
    try:
        collections = qdrant_client.get_collections()
        return {"collections": [col.name for col in collections.collections]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing collections: {e}")

@app.post("/index")
async def index_documents(
    request: IndexRequest = Depends(),
    collection: str = QueryParam(default="default", description="Collection name")
):
    """Index documents from the documents directory"""
    try:
        request.collection = collection

        # Create collection if it doesn't exist
        try:
            qdrant_client.get_collection(request.collection)
        except:
            qdrant_client.create_collection(
                collection_name=request.collection,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE)
            )

        indexed_files = []
        total_chunks = 0

        # Process all text files in documents directory
        for file_path in DOCUMENTS_DIR.rglob("*"):
            if not file_path.is_file():
                continue

            # Skip binary files and hidden files
            if file_path.name.startswith('.'):
                continue

            try:
                # Try to read as text
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                logger.warning(f"Skipping binary file: {file_path}")
                continue
            except Exception as e:
                logger.error(f"Error reading {file_path}: {e}")
                continue

            if not content.strip():
                continue

            # Generate file hash for deduplication
            file_hash = get_file_hash(file_path)

            # Check if file already indexed
            existing = qdrant_client.scroll(
                collection_name=request.collection,
                scroll_filter=Filter(
                    must=[FieldCondition(key="file_hash", match=MatchValue(value=file_hash))]
                ),
                limit=1
            )[0]

            if existing:
                logger.info(f"File already indexed: {file_path}")
                continue

            # Chunk the document
            chunks = chunk_text(content, request.chunk_size, request.chunk_overlap)

            # Get embeddings for all chunks
            embeddings = await get_embeddings(chunks)

            # Create points for Qdrant
            points = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                # Use hash of file_hash + index as integer ID
                point_id = hash(f"{file_hash}_{i}") % (2**31)  # Ensure positive 32-bit int
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "text": chunk,
                            "file_path": str(file_path.relative_to(DOCUMENTS_DIR)),
                            "file_hash": file_hash,
                            "chunk_index": i,
                            "total_chunks": len(chunks)
                        }
                    )
                )

            # Insert into Qdrant
            qdrant_client.upsert(
                collection_name=request.collection,
                points=points
            )

            indexed_files.append({
                "file": str(file_path.relative_to(DOCUMENTS_DIR)),
                "chunks": len(chunks)
            })
            total_chunks += len(chunks)

            logger.info(f"Indexed {file_path}: {len(chunks)} chunks")

        return {
            "message": "Indexing completed",
            "collection": request.collection,
            "indexed_files": indexed_files,
            "total_chunks": total_chunks
        }

    except Exception as e:
        logger.error(f"Error during indexing: {e}")
        raise HTTPException(status_code=500, detail=f"Indexing error: {e}")

@app.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    """Query documents and get AI-generated answer"""
    try:
        # Get query embedding
        query_embedding = (await get_embeddings([request.query]))[0]

        # Search in Qdrant
        search_results = qdrant_client.search(
            collection_name=request.collection,
            query_vector=query_embedding,
            limit=request.limit,
            score_threshold=request.score_threshold
        )

        if not search_results:
            return QueryResponse(
                answer="I couldn't find any relevant information in the documents for your query.",
                sources=[],
                context_used=""
            )

        # Prepare context from search results
        context_parts = []
        sources = []

        for result in search_results:
            context_parts.append(f"[Source: {result.payload['file_path']}]\n{result.payload['text']}")
            sources.append({
                "file_path": result.payload['file_path'],
                "chunk_index": result.payload['chunk_index'],
                "score": result.score,
                "text_preview": result.payload['text'][:200] + "..." if len(result.payload['text']) > 200 else result.payload['text']
            })

        context = "\n\n".join(context_parts)

        # Query LLM with context if requested
        if request.include_context:
            answer = await query_llm(request.query, context)
        else:
            answer = "Context retrieved. Use include_context=true to get AI answer."

        return QueryResponse(
            answer=answer,
            sources=sources,
            context_used=context[:1000] + "..." if len(context) > 1000 else context
        )

    except Exception as e:
        logger.error(f"Error during query: {e}")
        raise HTTPException(status_code=500, detail=f"Query error: {e}")

@app.delete("/collection/{collection_name}")
async def delete_collection(collection_name: str):
    """Delete a collection"""
    try:
        qdrant_client.delete_collection(collection_name)
        return {"message": f"Collection '{collection_name}' deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting collection: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)