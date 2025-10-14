"""
Shared fixtures for RAG integration tests (Issue #23).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import AsyncIterator

import httpx
import pytest
import pytest_asyncio

# Ensure SQLite paths are writable in CI environments
os.environ.setdefault("RAG_DB_PATH", "/tmp/rag_analytics.db")

TESTS_DIR = Path(__file__).resolve().parents[1]
if str(TESTS_DIR) not in sys.path:
    sys.path.append(str(TESTS_DIR))

# Add services/rag to path for app imports
RAG_SERVICE_DIR = Path(__file__).resolve().parents[2]
if str(RAG_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_SERVICE_DIR))

from fixtures.cleanup_fixtures import cleanup_postgres, cleanup_qdrant
from fixtures.seed_postgres import PostgresSettings, seed_database
from fixtures.seed_qdrant import seed as seed_qdrant

# Import app module to ensure coverage tracking
# This allows pytest-cov to measure code execution even in E2E tests
try:
    import app as _  # noqa: F401
except ImportError:
    pass  # App may not be importable in all test environments

DEFAULT_BASE_URL = "http://localhost:8002"


@pytest.fixture(scope="session")
def rag_base_url() -> str:
    """Base URL for the running RAG service."""
    if os.getenv("RUN_RAG_INTEGRATION_TESTS") != "1":
        pytest.skip("Skipping RAG integration tests (set RUN_RAG_INTEGRATION_TESTS=1 to enable).")
    return os.getenv("RAG_BASE_URL", DEFAULT_BASE_URL)


@pytest_asyncio.fixture
async def rag_client(rag_base_url: str) -> AsyncIterator[httpx.AsyncClient]:
    """
    Yield an HTTP client connected to the live RAG service.

    Skips the suite if the service is unreachable to avoid false negatives.
    """
    async with httpx.AsyncClient(base_url=rag_base_url, timeout=10.0) as client:
        try:
            response = await client.get("/health")
            response.raise_for_status()
        except Exception as exc:  # pragma: no cover - best effort connectivity check
            pytest.skip(f"RAG service not available at {rag_base_url}: {exc}")
        yield client


@pytest_asyncio.fixture
async def seeded_environment() -> AsyncIterator[None]:
    """Seed external services before tests and clean up afterwards."""
    settings = PostgresSettings.from_env()
    await seed_database(settings)
    seed_qdrant()
    yield
    await cleanup_postgres()
    cleanup_qdrant()


def pytest_configure(config) -> None:  # pragma: no cover - pytest hook
    """Skip integration tests by default unless explicitly enabled."""
    config.addinivalue_line("markers", "integration: marks integration tests")

    if os.getenv("RUN_RAG_INTEGRATION_TESTS") == "1":
        return

    existing = getattr(config.option, "markexpr", "")
    if existing:
        config.option.markexpr = f"({existing}) and not integration"
    else:
        config.option.markexpr = "not integration"


def pytest_collection_modifyitems(config, items) -> None:  # pragma: no cover
    """Mark all tests under the integration package."""
    for item in items:
        if "services/rag/tests/integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
