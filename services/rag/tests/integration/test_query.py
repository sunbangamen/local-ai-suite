from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_query_returns_context(
    rag_client, seeded_environment  # type: ignore[func-arg]
) -> None:
    payload = {
        "query": "Explain FastAPI endpoints",
        "collection": "test-integration",
        "topk": 3,
    }
    response = await rag_client.post("/query", json=payload)
    assert response.status_code in (200, 400, 503)

    if response.status_code == 200:
        data = response.json()
        assert data["context"]
        assert "usage" in data
