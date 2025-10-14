from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_query_handles_empty_input(rag_client):  # type: ignore[func-arg]
    payload = {"query": "", "collection": "test-integration"}
    response = await rag_client.post("/query", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["answer"] == ""
    assert data["context"] == []
    assert "error" in data["usage"]
