#!/usr/bin/env bash
set -e

echo "🚀 최적 모델 다운로드 시작..."
echo "시스템: Ultra 7 + 32GB RAM + RTX 4050"
echo "목적: Claude Code/Desktop/Cursor 대체 + RAG + MCP"
echo "=================================================="

cd models/

echo "📥 [1/2] 채팅/추론용 모델 다운로드 중..."
echo "모델: Qwen2.5-14B-Instruct (최고 성능, ~8.5GB)"
if [ ! -f "qwen2.5-14b-instruct-q4_k_m.gguf" ]; then
    echo "⚠️  대용량 파일(8.5GB) 다운로드 시작..."
    wget -c --progress=bar:force:noscroll \
        "https://huggingface.co/bartowski/Qwen2.5-14B-Instruct-GGUF/resolve/main/Qwen2.5-14B-Instruct-Q4_K_M.gguf" \
        -O qwen2.5-14b-instruct-q4_k_m.gguf
    echo "✅ 채팅 모델 다운로드 완료"
else
    echo "✅ 채팅 모델 이미 존재"
fi

echo "📥 [2/2] 코딩용 모델 다운로드 중..."
echo "모델: Qwen2.5-Coder-14B-Instruct (코딩 최강, ~8.5GB)"
if [ ! -f "qwen2.5-coder-14b-instruct-q4_k_m.gguf" ]; then
    echo "⚠️  대용량 파일(8.5GB) 다운로드 시작..."
    wget -c --progress=bar:force:noscroll \
        "https://huggingface.co/bartowski/Qwen2.5-Coder-14B-Instruct-GGUF/resolve/main/Qwen2.5-Coder-14B-Instruct-Q4_K_M.gguf" \
        -O qwen2.5-coder-14b-instruct-q4_k_m.gguf
    echo "✅ 코딩 모델 다운로드 완료"
else
    echo "✅ 코딩 모델 이미 존재"
fi

echo "=================================================="
echo "🎉 모델 다운로드 완료!"
echo ""
echo "📊 다운로드된 모델:"
ls -lh *.gguf
echo ""
echo "💾 총 용량: ~17GB"
echo "⚡ 성능: Claude Code/Cursor 수준"
echo ""
echo "🔧 다음 단계:"
echo "1. .env 파일에서 모델 설정 확인"
echo "2. bash scripts/preflight.sh 실행"
echo "3. make up-p1 실행"
echo "=================================================="