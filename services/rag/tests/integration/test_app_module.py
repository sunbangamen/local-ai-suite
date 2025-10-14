"""
Direct FastAPI execution to ensure services/rag/app.py is covered during integration runs.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from tempfile import gettempdir

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_route_executes_within_same_process() -> None:
    """
    Exercise the /health endpoint inside the pytest process so coverage captures app.py.
    Falls back to the existing HTTP-based tests for full E2E behaviour.
    """
    if os.getenv("RUN_RAG_INTEGRATION_TESTS") != "1":
        pytest.skip("Skipping RAG integration tests (RUN_RAG_INTEGRATION_TESTS!=1).")

    os.environ.setdefault("RAG_DB_PATH", str(Path(gettempdir()) / "rag_analytics.db"))

    # Add /app to sys.path for importing the service module
    app_dir = Path("/app")
    if app_dir.exists() and str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))

    # Import inside the test so we reuse the same module the service uses.
    from app import health, on_startup  # type: ignore

    # Ensure globals such as qdrant clients are initialised.
    await on_startup()

    result = await health()
    status_code = getattr(result, "status_code", 200)

    if hasattr(result, "body"):
        payload = json.loads(result.body.decode())
    else:
        payload = result

    assert payload["service"] == "rag"
    assert status_code in (200, 503)
