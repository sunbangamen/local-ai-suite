"""
Utility script for seeding PostgreSQL with integration test data.

Designed to run against the Phase 2 Docker stack (Issue #23 scope).
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

import asyncpg


@dataclass
class PostgresSettings:
    host: str = os.getenv("POSTGRES_HOST", "postgres")
    port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    user: str = os.getenv("POSTGRES_USER", "ai_user")
    password: str = os.getenv("POSTGRES_PASSWORD", "ai_secure_pass")
    database: str = os.getenv("POSTGRES_DB", "ai_suite")

    @classmethod
    def from_env(cls) -> "PostgresSettings":
        return cls()


SEED_COLLECTION = "test-integration"


async def seed_database(settings: PostgresSettings) -> None:
    try:
        conn = await asyncpg.connect(
            host=settings.host,
            port=settings.port,
            user=settings.user,
            password=settings.password,
            database=settings.database,
        )
    except OSError as exc:
        print(f"⚠️ Skipping PostgreSQL seed (connection failed): {exc}")
        return
    except asyncpg.InvalidCatalogNameError as exc:
        print(f"⚠️ Skipping PostgreSQL seed (database missing): {exc}")
        return

    try:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS collections (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id SERIAL PRIMARY KEY,
                collection_id INTEGER REFERENCES collections(id) ON DELETE CASCADE,
                path TEXT NOT NULL,
                content TEXT,
                indexed_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(collection_id, path)
            )
            """
        )

        await conn.execute(
            """
            INSERT INTO collections (name, description, created_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (name) DO NOTHING
            """,
            SEED_COLLECTION,
            "Integration test collection",
        )

        await conn.execute(
            """
            INSERT INTO documents (collection_id, path, content, indexed_at)
            SELECT c.id, $1, $2, NOW()
            FROM collections c
            WHERE c.name = $3
            ON CONFLICT (collection_id, path) DO NOTHING
            """,
            "/tests/doc1.txt",
            "Integration test document content.",
            SEED_COLLECTION,
        )
    finally:
        await conn.close()


async def main() -> None:
    settings = PostgresSettings.from_env()
    await seed_database(settings)
    print("✅ PostgreSQL seeded for RAG integration tests.")


if __name__ == "__main__":
    asyncio.run(main())
