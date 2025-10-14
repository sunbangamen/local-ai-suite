"""
Utility helpers for cleaning up integration test data.

This script removes seeded data from PostgreSQL and Qdrant.
"""

from __future__ import annotations

import asyncio
import os

import asyncpg
from qdrant_client import QdrantClient

SEED_COLLECTION = os.getenv("QDRANT_COLLECTION", "test-integration")
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")


async def cleanup_postgres() -> None:
    try:
        conn = await asyncpg.connect(
            host=os.getenv("POSTGRES_HOST", "postgres"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            user=os.getenv("POSTGRES_USER", "ai_user"),
            # nosec B106 - Test fixture default, overridden by env var
            password=os.getenv("POSTGRES_PASSWORD", "ai_secure_pass"),
            database=os.getenv("POSTGRES_DB", "ai_suite"),
        )
    except OSError as exc:
        print(f"⚠️ Skipping PostgreSQL cleanup (connection failed): {exc}")
        return
    try:
        await conn.execute(
            """
            DELETE FROM documents
            WHERE collection_id IN (
                SELECT id FROM collections WHERE name = $1
            )
            """,
            SEED_COLLECTION,
        )
        await conn.execute(
            "DELETE FROM collections WHERE name = $1",
            SEED_COLLECTION,
        )
    finally:
        await conn.close()


def cleanup_qdrant() -> None:
    try:
        client = QdrantClient(url=QDRANT_URL)
        if client.collection_exists(SEED_COLLECTION):
            client.delete_collection(collection_name=SEED_COLLECTION)
    except Exception as exc:
        print(f"⚠️ Skipping Qdrant cleanup: {exc}")


async def main() -> None:
    await cleanup_postgres()
    cleanup_qdrant()
    print("🧹 Integration test data cleaned up.")


if __name__ == "__main__":
    asyncio.run(main())
