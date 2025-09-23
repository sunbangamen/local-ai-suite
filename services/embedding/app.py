#!/usr/bin/env python3
"""
Local Embedding Service
Completely offline embedding service using FastEmbed (PyTorch-free)
"""

import os
import logging
from typing import List, Dict, Any
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from fastembed import TextEmbedding
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
MODEL_NAME = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
MODEL_CACHE_DIR = "/app/models"

# Initialize FastAPI
app = FastAPI(
    title="Local Embedding Service",
    description="Offline embedding service for Local AI Suite",
    version="1.0.0"
)

# Global model variable
embedding_model = None

# Pydantic models
class EmbedRequest(BaseModel):
    inputs: List[str]
    normalize: bool = True

class EmbedResponse(BaseModel):
    embeddings: List[List[float]]
    model_name: str
    dimensions: int
    processing_time: float

# Model loading
def load_model():
    """Load the embedding model"""
    global embedding_model

    try:
        logger.info(f"Loading embedding model: {MODEL_NAME}")
        logger.info(f"Cache directory: {MODEL_CACHE_DIR}")

        # Create cache directory if it doesn't exist
        os.makedirs(MODEL_CACHE_DIR, exist_ok=True)

        # Load model with local cache using FastEmbed
        embedding_model = TextEmbedding(
            model_name=MODEL_NAME,
            cache_dir=MODEL_CACHE_DIR
        )

        logger.info(f"Model loaded successfully")

        # Test to get dimensions
        test_embedding = list(embedding_model.embed(["test"]))[0]
        dimensions = len(test_embedding)
        logger.info(f"Model dimensions: {dimensions}")

    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise RuntimeError(f"Model loading failed: {e}")

# API Routes
@app.on_event("startup")
async def startup_event():
    """Load model on startup"""
    load_model()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if embedding_model is None:
        return {"status": "unhealthy", "error": "Model not loaded"}

    try:
        # Test embedding with a simple text
        test_embedding = list(embedding_model.embed(["test"]))[0]
        return {
            "status": "healthy",
            "model": MODEL_NAME,
            "dimensions": len(test_embedding),
            "test_embedding_shape": f"({len(test_embedding)},)"
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.get("/info")
async def model_info():
    """Get model information"""
    if embedding_model is None:
        raise HTTPException(status_code=500, detail="Model not loaded")

    try:
        test_embedding = list(embedding_model.embed(["test"]))[0]
        dimensions = len(test_embedding)
    except Exception:
        dimensions = "unknown"

    return {
        "model_name": MODEL_NAME,
        "dimensions": dimensions,
        "cache_dir": MODEL_CACHE_DIR,
        "backend": "FastEmbed (ONNX)"
    }

@app.post("/embed", response_model=EmbedResponse)
async def create_embeddings(request: EmbedRequest):
    """Create embeddings for input texts"""
    if embedding_model is None:
        raise HTTPException(status_code=500, detail="Model not loaded")

    if not request.inputs:
        raise HTTPException(status_code=400, detail="No input texts provided")

    if len(request.inputs) > 100:  # Prevent memory issues
        raise HTTPException(status_code=400, detail="Too many inputs (max 100)")

    try:
        start_time = time.time()

        logger.info(f"Processing {len(request.inputs)} texts")

        # Generate embeddings using FastEmbed
        embeddings_generator = embedding_model.embed(request.inputs)
        embeddings_list = [embedding.tolist() for embedding in embeddings_generator]

        # Apply normalization if requested
        if request.normalize:
            embeddings_list = [
                (np.array(emb) / np.linalg.norm(np.array(emb))).tolist()
                for emb in embeddings_list
            ]

        processing_time = time.time() - start_time

        logger.info(f"Generated embeddings in {processing_time:.3f}s")

        return EmbedResponse(
            embeddings=embeddings_list,
            model_name=MODEL_NAME,
            dimensions=len(embeddings_list[0]) if embeddings_list else 0,
            processing_time=processing_time
        )

    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {e}")

@app.post("/embed/single")
async def create_single_embedding(text: str):
    """Create embedding for a single text (simplified endpoint)"""
    if embedding_model is None:
        raise HTTPException(status_code=500, detail="Model not loaded")

    try:
        start_time = time.time()

        # Generate embedding using FastEmbed
        embedding_generator = embedding_model.embed([text])
        embedding = list(embedding_generator)[0]

        # Normalize the embedding
        embedding_normalized = embedding / np.linalg.norm(embedding)
        embedding_list = embedding_normalized.tolist()

        processing_time = time.time() - start_time

        return {
            "embedding": embedding_list,
            "dimensions": len(embedding_list),
            "processing_time": processing_time
        }

    except Exception as e:
        logger.error(f"Error generating single embedding: {e}")
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {e}")

# Utility endpoints
@app.get("/models/download")
async def download_model():
    """Force download/update model (useful for setup)"""
    try:
        logger.info("Force downloading model...")
        global embedding_model

        # Clear existing model
        embedding_model = None

        # Reload model (will download if not cached)
        load_model()

        return {
            "status": "success",
            "message": "Model downloaded successfully",
            "model": MODEL_NAME,
            "cache_dir": MODEL_CACHE_DIR,
            "backend": "FastEmbed (ONNX)"
        }

    except Exception as e:
        logger.error(f"Error downloading model: {e}")
        raise HTTPException(status_code=500, detail=f"Model download failed: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)