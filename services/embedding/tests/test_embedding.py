"""
Embedding Service Unit Tests
Tests for /embed, /health, batch processing, error handling using real app with mocks
This tests the ACTUAL app.py module with dependency injection

NOTE: Embedding service truncates large inputs instead of rejecting them:
- MAX_TEXTS exceeded: truncates to first MAX_TEXTS items (returns 200)
- MAX_CHARS exceeded: truncates each text to MAX_CHARS (returns 200)
- Empty texts: returns empty embeddings array (returns 200)
"""

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path to import app module
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import the REAL app module (not a mock)
import app as embedding_app_module


@pytest.fixture
def mock_text_embedding():
    """Mock FastEmbed TextEmbedding model"""
    model = MagicMock()

    def mock_embed(texts, batch_size=64, normalize=True):
        """Return mock embeddings for texts"""
        # Return generator that yields 384-dim embeddings
        for _ in texts:
            yield [0.1] * 384

    model.embed = mock_embed
    return model


@pytest.fixture
def app_with_mocks(mock_text_embedding):
    """
    Get REAL Embedding FastAPI app with mocked FastEmbed model
    - Uses actual services/embedding/app.py module
    - Mocks: TextEmbedding model
    - Restores original state after test
    """
    # Store original values (including _model_name)
    original_model = embedding_app_module._model
    original_model_name = embedding_app_module._model_name
    original_model_dim = embedding_app_module._model_dim

    # Override global model
    embedding_app_module._model = mock_text_embedding
    embedding_app_module._model_name = "BAAI/bge-small-en-v1.5"
    embedding_app_module._model_dim = 384

    yield embedding_app_module.app

    # Restore original values (cleanup)
    embedding_app_module._model = original_model
    embedding_app_module._model_name = original_model_name
    embedding_app_module._model_dim = original_model_dim


@pytest.mark.asyncio
async def test_embed_single_text(app_with_mocks):
    """Test embedding a single text (success path)"""
    transport = ASGITransport(app=app_with_mocks)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/embed", json={"texts": ["Hello world"]})

        assert response.status_code == 200
        data = response.json()
        assert "embeddings" in data
        assert len(data["embeddings"]) == 1
        assert isinstance(data["embeddings"][0], list)
        assert data["dim"] == 384
        assert "model" in data


@pytest.mark.asyncio
async def test_embed_batch_texts(app_with_mocks):
    """Test embedding multiple texts in a batch (success path)"""
    transport = ASGITransport(app=app_with_mocks)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        texts = [f"Document {i}" for i in range(10)]
        response = await client.post("/embed", json={"texts": texts})

        assert response.status_code == 200
        data = response.json()
        assert len(data["embeddings"]) == 10
        assert all(len(emb) == 384 for emb in data["embeddings"])


@pytest.mark.asyncio
async def test_health_shows_model_info(app_with_mocks):
    """Test /health endpoint returns model information"""
    transport = ASGITransport(app=app_with_mocks)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "model" in data
        assert "dim" in data
        assert data["dim"] == 384


@pytest.mark.asyncio
async def test_exceed_max_texts_truncates(app_with_mocks):
    """
    Test MAX_TEXTS limit behavior (SERVICE TRUNCATES, not rejects)
    Service truncates to first MAX_TEXTS items and returns 200
    """
    transport = ASGITransport(app=app_with_mocks)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create batch exceeding MAX_TEXTS (default 1024)
        large_batch = [f"Text {i}" for i in range(2000)]
        response = await client.post("/embed", json={"texts": large_batch})

        # Service TRUNCATES to MAX_TEXTS and returns 200
        assert response.status_code == 200
        data = response.json()
        assert "embeddings" in data
        # Should be truncated to MAX_TEXTS (1024)
        max_texts = embedding_app_module.MAX_TEXTS
        assert len(data["embeddings"]) == max_texts


@pytest.mark.asyncio
async def test_exceed_max_chars_truncates(app_with_mocks):
    """
    Test MAX_CHARS limit behavior (SERVICE TRUNCATES, not rejects)
    Service truncates each text to MAX_CHARS and returns 200
    """
    transport = ASGITransport(app=app_with_mocks)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create text exceeding MAX_CHARS (default 8000)
        very_long_text = "a" * 10000
        response = await client.post("/embed", json={"texts": [very_long_text]})

        # Service TRUNCATES text to MAX_CHARS and returns 200
        assert response.status_code == 200
        data = response.json()
        assert "embeddings" in data
        assert len(data["embeddings"]) == 1
        # Text was truncated but still embedded


@pytest.mark.asyncio
async def test_empty_texts_list_returns_empty(app_with_mocks):
    """
    Test empty texts list behavior (SERVICE RETURNS EMPTY, not rejects)
    Service returns empty embeddings array with 200
    """
    transport = ASGITransport(app=app_with_mocks)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/embed", json={"texts": []})

        # Service returns empty array with 200
        assert response.status_code == 200
        data = response.json()
        assert "embeddings" in data
        assert len(data["embeddings"]) == 0


@pytest.mark.asyncio
async def test_reload_model_successfully(app_with_mocks):
    """Test reloading embedding model (success path)"""
    transport = ASGITransport(app=app_with_mocks)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Patch _load_model to avoid actual model loading
        with patch("app._load_model") as mock_load:
            mock_model = MagicMock()
            mock_model.embed = lambda texts, **kwargs: [[0.1] * 384 for _ in texts]
            mock_load.return_value = mock_model

            response = await client.post(
                "/reload", json={"model": "BAAI/bge-small-en-v1.5"}
            )

            assert response.status_code == 200
            data = response.json()
            assert "reloaded" in data
            assert "model" in data
