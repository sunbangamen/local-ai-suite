from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_indexing_pipeline_end_to_end(
    rag_client, seeded_environment  # type: ignore[func-arg]
) -> None:
    response = await rag_client.post(
        "/index", params={"collection": "test-integration"}
    )
    assert response.status_code == 200

    data = response.json()
    assert data["collection"] == "test-integration"
    assert data["chunks"] >= 0
