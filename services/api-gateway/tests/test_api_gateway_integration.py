#!/usr/bin/env python3
"""
API Gateway Integration Tests (Phase 2)
Tests for memory router endpoints and integration

Focus areas:
1. Health check endpoint
2. Model listing
3. Chat completion routing
4. Error handling
5. Performance metrics
"""

import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI
from fastapi.responses import JSONResponse


# ============================================================================
# Mock API Gateway App (simplified)
# ============================================================================


def create_mock_api_gateway_app():
    """Create a simplified mock API Gateway app for testing"""
    app = FastAPI(title="API Gateway", version="1.0.0")

    # Track metrics
    app.state.request_count = 0
    app.state.last_error = None

    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "service": "api-gateway",
            "version": "1.0.0",
        }

    @app.get("/v1/models")
    async def list_models():
        """List available models"""
        return {
            "object": "list",
            "data": [
                {"id": "chat-7b", "object": "model", "owned_by": "local"},
                {"id": "code-7b", "object": "model", "owned_by": "local"},
            ],
        }

    @app.post("/v1/chat/completions")
    async def chat_completion(request_data: dict):
        """Handle chat completion requests"""
        app.state.request_count += 1

        # Route based on model selection
        model = request_data.get("model", "chat-7b")
        messages = request_data.get("messages", [])

        if not messages:
            app.state.last_error = "No messages provided"
            return JSONResponse(
                status_code=400,
                content={"error": "No messages provided"},
            )

        return {
            "object": "chat.completion",
            "model": model,
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Mock response from " + model,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
            },
        }

    @app.get("/metrics")
    async def metrics():
        """Get metrics"""
        return {
            "request_count": app.state.request_count,
            "last_error": app.state.last_error,
        }

    return app


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_health_check_endpoint():
    """Test /health endpoint"""
    app = create_mock_api_gateway_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data
        assert data["service"] == "api-gateway"


@pytest.mark.asyncio
async def test_list_models_endpoint():
    """Test /v1/models endpoint"""
    app = create_mock_api_gateway_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/models")

        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        assert len(data["data"]) >= 2
        assert data["data"][0]["id"] in ["chat-7b", "code-7b"]


@pytest.mark.asyncio
async def test_chat_completion_basic():
    """Test basic chat completion request"""
    app = create_mock_api_gateway_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "chat-7b",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "chat-7b"
        assert "choices" in data
        assert len(data["choices"]) > 0
        assert "message" in data["choices"][0]


@pytest.mark.asyncio
async def test_chat_completion_code_model():
    """Test chat completion with code model"""
    app = create_mock_api_gateway_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "code-7b",
                "messages": [{"role": "user", "content": "Write Python code"}],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "code-7b"
        assert "choices" in data


@pytest.mark.asyncio
async def test_chat_completion_empty_messages():
    """Test chat completion with empty messages (error case)"""
    app = create_mock_api_gateway_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "chat-7b",
                "messages": [],
            },
        )

        assert response.status_code == 400
        data = response.json()
        assert "error" in data


@pytest.mark.asyncio
async def test_chat_completion_multiple_turns():
    """Test chat completion with multi-turn conversation"""
    app = create_mock_api_gateway_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "chat-7b",
                "messages": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there!"},
                    {"role": "user", "content": "How are you?"},
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "choices" in data


@pytest.mark.asyncio
async def test_metrics_endpoint():
    """Test /metrics endpoint"""
    app = create_mock_api_gateway_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Make some requests
        await client.post(
            "/v1/chat/completions",
            json={
                "model": "chat-7b",
                "messages": [{"role": "user", "content": "Test"}],
            },
        )

        # Check metrics
        response = await client.get("/metrics")

        assert response.status_code == 200
        data = response.json()
        assert "request_count" in data
        assert data["request_count"] >= 1


@pytest.mark.asyncio
async def test_concurrent_chat_completions():
    """Test multiple concurrent chat completion requests"""
    app = create_mock_api_gateway_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tasks = [
            client.post(
                "/v1/chat/completions",
                json={
                    "model": "chat-7b",
                    "messages": [{"role": "user", "content": f"Message {i}"}],
                },
            )
            for i in range(5)
        ]

        import asyncio

        responses = await asyncio.gather(*tasks)

        assert len(responses) == 5
        assert all(r.status_code == 200 for r in responses)


@pytest.mark.asyncio
async def test_response_includes_usage_info():
    """Test that responses include token usage information"""
    app = create_mock_api_gateway_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "chat-7b",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "usage" in data
        assert "prompt_tokens" in data["usage"]
        assert "completion_tokens" in data["usage"]
        assert "total_tokens" in data["usage"]


if __name__ == "__main__":
    import asyncio

    loop = asyncio.get_event_loop()

    tests = [
        test_health_check_endpoint(),
        test_list_models_endpoint(),
        test_chat_completion_basic(),
        test_chat_completion_code_model(),
        test_chat_completion_empty_messages(),
        test_chat_completion_multiple_turns(),
        test_metrics_endpoint(),
        test_concurrent_chat_completions(),
        test_response_includes_usage_info(),
    ]

    for test in tests:
        try:
            loop.run_until_complete(test)
            print("✓ Test passed")
        except Exception as e:
            print(f"✗ Test failed: {e}")

    print("\n✅ All API Gateway integration tests completed!")
