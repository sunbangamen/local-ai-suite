from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health_reports_dependencies(rag_client):  # type: ignore[func-arg]
    response = await rag_client.get("/health", params={"llm": "true"})
    assert response.status_code in (200, 503)

    data = response.json()
    deps = data.get("dependencies", {})
    assert "qdrant" in deps
    assert "embedding" in deps
    if response.status_code == 200 and "api_gateway" in deps:
        assert deps["api_gateway"]
