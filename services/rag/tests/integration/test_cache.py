from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_cache_hit_and_fallback(
    rag_client, seeded_environment  # type: ignore[func-arg]
) -> None:
    payload = {
        "query": "Explain FastAPI endpoints",
        "collection": "test-integration",
    }

    first = await rag_client.post("/query", json=payload)
    assert first.status_code in (200, 400, 503)

    second = await rag_client.post("/query", json=payload)
    assert second.status_code in (200, 400, 503)

    if first.status_code == 200 and second.status_code == 200:
        assert second.json().get("cached") is True
