"""
Seed the Qdrant vector store with integration test data.

Designed for the Phase 2 Docker stack (Issue #23 scope).
"""

from __future__ import annotations

import os
from typing import List

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "test-integration")
VECTOR_SIZE = int(os.getenv("EMBED_DIM", "384"))
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")


def build_points() -> List[PointStruct]:
    return [
        PointStruct(
            id=1,
            vector=[0.1] * VECTOR_SIZE,
            payload={"text": "Python file handling", "chunk_id": 1},
        ),
        PointStruct(
            id=2,
            vector=[0.2] * VECTOR_SIZE,
            payload={"text": "FastAPI endpoints", "chunk_id": 2},
        ),
    ]


def seed() -> None:
    client = QdrantClient(url=QDRANT_URL)

    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )

    client.upsert(collection_name=COLLECTION_NAME, points=build_points())
    print(f"✅ Qdrant seeded for collection '{COLLECTION_NAME}'.")


if __name__ == "__main__":
    seed()
