"""
Mock LLM Inference Server for CI Testing
OpenAI-compatible API that returns mock responses without GPU/models
"""

import os
import time
import uuid
from typing import List, Optional, Dict, Any

from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn


app = FastAPI(title="Mock Inference Server", version="1.0.0")

MODEL_NAME = os.getenv("MODEL_NAME", "mock-model")
PORT = int(os.getenv("PORT", "8001"))
HOST = os.getenv("MOCK_INFERENCE_HOST", "127.0.0.1")


class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = None
    messages: List[Message]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 100
    stream: Optional[bool] = False


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "model": MODEL_NAME, "backend": "mock"}


@app.get("/v1/models")
async def list_models():
    """List available models (OpenAI-compatible)"""
    return {
        "object": "list",
        "data": [
            {
                "id": MODEL_NAME,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "mock-inference",
            }
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """
    Mock chat completion endpoint (OpenAI-compatible)
    Returns fixed response without actual LLM inference
    """
    # Generate mock response based on last user message
    user_message = ""
    for msg in reversed(request.messages):
        if msg.role == "user":
            user_message = msg.content
            break

    # Simple mock response
    mock_content = f"Mock response to: {user_message[:50]}..."

    # Check if it's a code-related query (basic heuristic)
    code_keywords = [
        "code",
        "function",
        "python",
        "javascript",
        "def",
        "class",
        "import",
    ]
    is_code = any(keyword in user_message.lower() for keyword in code_keywords)

    if is_code:
        mock_content = (
            "```python\ndef mock_function():\n    return 'This is a mock code response'\n```"
        )

    response = ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
        created=int(time.time()),
        model=request.model or MODEL_NAME,
        choices=[
            {
                "index": 0,
                "message": {"role": "assistant", "content": mock_content},
                "finish_reason": "stop",
            }
        ],
        usage={
            "prompt_tokens": sum(len(m.content.split()) for m in request.messages),
            "completion_tokens": len(mock_content.split()),
            "total_tokens": sum(len(m.content.split()) for m in request.messages)
            + len(mock_content.split()),
        },
    )

    return response


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Mock LLM Inference Server",
        "model": MODEL_NAME,
        "endpoints": ["/health", "/v1/models", "/v1/chat/completions"],
    }


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=HOST,  # nosec B104 - override via MOCK_INFERENCE_HOST when needed
        port=PORT,
    )
