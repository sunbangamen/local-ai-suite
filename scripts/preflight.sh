#!/usr/bin/env bash
set -e

echo "🚀 Phase 1 Preflight Check Starting..."
echo "==============================================="

# Load environment variables
if [ -f .env ]; then
    source .env
    echo "✅ [1/5] .env file loaded successfully"
else
    echo "❌ [1/5] .env file not found. Please copy .env.example to .env"
    exit 1
fi

# Check Docker
if command -v docker &> /dev/null; then
    if docker ps &> /dev/null; then
        echo "✅ [2/5] Docker is running"
    else
        echo "❌ [2/5] Docker daemon is not running"
        exit 1
    fi
else
    echo "❌ [2/5] Docker is not installed"
    exit 1
fi

# Check GPU (optional for CPU fallback)
echo "🔍 [3/5] Checking GPU availability..."
if command -v nvidia-smi &> /dev/null; then
    if nvidia-smi &> /dev/null; then
        echo "✅ [3/5] NVIDIA GPU detected and accessible"
        GPU_AVAILABLE=true
    else
        echo "⚠️  [3/5] NVIDIA GPU driver issues detected, will use CPU mode"
        GPU_AVAILABLE=false
    fi
else
    echo "⚠️  [3/5] nvidia-smi not found, will use CPU mode"
    GPU_AVAILABLE=false
fi

# Check model files
echo "🔍 [4/5] Checking model files..."
if [ -n "${CHAT_MODEL}" ]; then
    if [ -f "./models/${CHAT_MODEL}" ]; then
        echo "✅ [4/5] Chat model found: ${CHAT_MODEL}"
    else
        echo "❌ [4/5] Chat model not found: ./models/${CHAT_MODEL}"
        echo "Please download a GGUF model file to the models/ directory"
        echo "Example: llama3.1-8b-instruct-q4_k_m.gguf"
        exit 1
    fi
else
    echo "❌ [4/5] CHAT_MODEL not set in .env"
    exit 1
fi

# Check port availability
echo "🔍 [5/5] Checking port availability..."
API_PORT=${API_GATEWAY_PORT:-8000}
INFERENCE_PORT=${INFERENCE_PORT:-8001}

if nc -z localhost ${API_PORT} 2>/dev/null; then
    echo "⚠️  [5/5] Port ${API_PORT} is in use"
else
    echo "✅ [5/5] Port ${API_PORT} is available"
fi

if nc -z localhost ${INFERENCE_PORT} 2>/dev/null; then
    echo "⚠️  [5/5] Port ${INFERENCE_PORT} is in use"
else
    echo "✅ [5/5] Port ${INFERENCE_PORT} is available"
fi

echo "==============================================="
if [ "$GPU_AVAILABLE" = true ]; then
    echo "🎉 Preflight check completed! GPU mode ready."
else
    echo "🎉 Preflight check completed! CPU mode ready."
    echo "Note: Performance will be slower without GPU acceleration"
fi
echo "You can now run: make up-p1"
echo "==============================================="