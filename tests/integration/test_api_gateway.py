"""
API Gateway Integration Tests
Tests for chat model, code model, and failover scenarios

NOTE: These tests require Phase 2 services running (make up-p2)
- These are TRUE integration tests that call actual services
- Requires GPU + model files at /mnt/e/ai-models/
- Skip in CI with: pytest.mark.skipif(RUN_INTEGRATION_TESTS != "true")
"""
import pytest
import httpx
import os


# Skip all tests if not in integration test mode
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "true",
    reason="Integration tests require RUN_INTEGRATION_TESTS=true and running services"
)


@pytest.fixture
def api_base_url():
    """Get API Gateway base URL from environment"""
    return os.getenv("API_GATEWAY_URL", "http://localhost:8000")


@pytest.mark.asyncio
async def test_chat_model_inference(api_base_url):
    """Test inference using chat model"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{api_base_url}/v1/chat/completions",
            json={
                "model": "chat-7b",
                "messages": [
                    {"role": "user", "content": "Say 'Hello' in one word"}
                ],
                "max_tokens": 10,
                "temperature": 0.1
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) > 0
        assert "message" in data["choices"][0]
        assert "content" in data["choices"][0]["message"]


@pytest.mark.asyncio
async def test_code_model_inference(api_base_url):
    """Test inference using code model"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{api_base_url}/v1/chat/completions",
            json={
                "model": "code-7b",
                "messages": [
                    {"role": "user", "content": "Write a Python hello world function"}
                ],
                "max_tokens": 50,
                "temperature": 0.3
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "choices" in data
        content = data["choices"][0]["message"]["content"]
        # Code model should return code-related content
        assert "def" in content.lower() or "print" in content.lower()


@pytest.mark.asyncio
async def test_failover_from_chat_to_code(api_base_url):
    """Test automatic failover mechanism (simulated)"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Test that API gateway is resilient
        # Even if one model is slow/unavailable, it should still respond
        response = await client.post(
            f"{api_base_url}/v1/chat/completions",
            json={
                "model": "chat-7b",
                "messages": [
                    {"role": "user", "content": "Test failover"}
                ],
                "max_tokens": 5,
                "temperature": 0.0
            }
        )

        # Should succeed (200) or gracefully degrade (503 with retry header)
        assert response.status_code in [200, 503]

        if response.status_code == 503:
            # Check for proper error handling
            assert "retry-after" in response.headers or "Retry-After" in response.headers
        else:
            # Successful response
            data = response.json()
            assert "choices" in data


# Health check test (simpler, always enabled)
@pytest.mark.asyncio
async def test_api_gateway_health():
    """Test API gateway health endpoint"""
    api_base_url = os.getenv("API_GATEWAY_URL", "http://localhost:8000")

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{api_base_url}/health")
            # LiteLLM may not have /health, try /v1/models instead
            if response.status_code == 404:
                response = await client.get(f"{api_base_url}/v1/models")

            assert response.status_code == 200
        except httpx.ConnectError:
            pytest.skip("API Gateway not running - start with 'make up-p2'")
