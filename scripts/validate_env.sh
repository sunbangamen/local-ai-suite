#!/bin/bash
# validate_env.sh - Phase 1 환경 검증 자동화 스크립트
# Issue #30: Phase 3 프로덕션 배포 준비 및 시스템 검증

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         Phase 1: Pre-Deployment Environment Validation         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

# Helper functions
check_pass() {
    echo -e "${GREEN}✅ PASS${NC}: $1"
    ((PASS_COUNT++))
}

check_fail() {
    echo -e "${RED}❌ FAIL${NC}: $1"
    ((FAIL_COUNT++))
}

check_warn() {
    echo -e "${YELLOW}⚠️  WARN${NC}: $1"
    ((WARN_COUNT++))
}

check_info() {
    echo -e "${BLUE}ℹ️  INFO${NC}: $1"
}

# 1. Docker/Compose 버전 확인
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1️⃣  Docker & Docker Compose Version Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

DOCKER_VERSION=$(docker --version | grep -oP '\d+\.\d+\.\d+' | head -1)
COMPOSE_VERSION=$(docker compose version 2>/dev/null | grep -oP 'v\d+\.\d+\.\d+' | head -1 || echo "unknown")

if [[ $(echo "$DOCKER_VERSION" | cut -d. -f1) -ge 20 ]]; then
    check_pass "Docker version $DOCKER_VERSION (requirement: 20.10+)"
else
    check_fail "Docker version $DOCKER_VERSION (requirement: 20.10+)"
fi

if [[ ! "$COMPOSE_VERSION" == "unknown" ]]; then
    check_pass "Docker Compose version $COMPOSE_VERSION (requirement: 2.0+)"
else
    check_fail "Docker Compose version not detected"
fi
echo ""

# 2. GPU 드라이버 확인
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2️⃣  GPU Driver & NVIDIA-SMI Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command -v nvidia-smi &> /dev/null; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    GPU_MEMORY=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader 2>/dev/null | head -1)
    CUDA_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1)

    check_pass "NVIDIA GPU detected: $GPU_NAME"
    check_pass "GPU Memory: $GPU_MEMORY"
    check_info "CUDA Version: $CUDA_VERSION"
else
    check_fail "nvidia-smi not found - GPU driver may not be installed"
fi
echo ""

# 3. 포트 충돌 검사
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3️⃣  Port Availability Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

PORTS=(8000 8001 8002 8003 8004 8005 8020 8021 6333 9090 3001)
PORT_FAIL=0

for port in "${PORTS[@]}"; do
    if lsof -i :$port 2>/dev/null | grep -q LISTEN; then
        check_fail "Port $port is in use"
        PORT_FAIL=$((PORT_FAIL + 1))
    else
        check_info "Port $port: Available"
    fi
done

if [ $PORT_FAIL -eq 0 ]; then
    echo -e "${GREEN}✅ PASS${NC}: All required ports are available"
    ((PASS_COUNT++))
else
    echo -e "${RED}❌ FAIL${NC}: $PORT_FAIL port(s) are in use"
    ((FAIL_COUNT++))
fi
echo ""

# 4. 모델 파일 존재 확인
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4️⃣  Model Files Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

MODELS_DIR="${MODELS_DIR:-/mnt/e/ai-models}"
MODEL_3B="Qwen2.5-3B-Instruct-Q4_K_M.gguf"
MODEL_7B="qwen2.5-coder-7b-instruct-q4_k_m.gguf"

if [ -f "$MODELS_DIR/$MODEL_3B" ]; then
    SIZE_3B=$(du -h "$MODELS_DIR/$MODEL_3B" | cut -f1)
    check_pass "3B Chat Model found: $MODEL_3B ($SIZE_3B)"
else
    check_fail "3B Chat Model not found: $MODELS_DIR/$MODEL_3B"
fi

if [ -f "$MODELS_DIR/$MODEL_7B" ]; then
    SIZE_7B=$(du -h "$MODELS_DIR/$MODEL_7B" | cut -f1)
    check_pass "7B Code Model found: $MODEL_7B ($SIZE_7B)"
else
    check_fail "7B Code Model not found: $MODELS_DIR/$MODEL_7B"
fi
echo ""

# 5. Git 상태 확인
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5️⃣  Git Status Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
MODIFIED=$(git status --porcelain 2>/dev/null | wc -l)
COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

check_info "Current branch: $BRANCH"
check_info "Latest commit: $COMMIT"

if [ "$MODIFIED" -eq 0 ]; then
    check_pass "Working tree is clean (no modifications)"
else
    check_warn "Working tree has $MODIFIED modified/untracked file(s)"
fi
echo ""

# 6. 디스크 공간 확인
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "6️⃣  Disk Space Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

DATA_DIR="${DATA_DIR:-/mnt/e/ai-data}"
AVAILABLE=$(df "$DATA_DIR" | awk 'NR==2 {print $4}')
AVAILABLE_GB=$((AVAILABLE / 1024 / 1024))

check_info "Mount point: $(df "$DATA_DIR" | awk 'NR==2 {print $1}')"
check_info "Total usage: $(df -h "$DATA_DIR" | awk 'NR==2 {print $2}')"
check_info "Used: $(df -h "$DATA_DIR" | awk 'NR==2 {print $3}')"

if [ "$AVAILABLE_GB" -ge 20 ]; then
    check_pass "Available disk space: ${AVAILABLE_GB}GB (requirement: ≥ 20GB)"
else
    check_fail "Available disk space: ${AVAILABLE_GB}GB (requirement: ≥ 20GB)"
fi
echo ""

# Summary
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    Validation Summary                          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo -e "  ${GREEN}PASS${NC}:  $PASS_COUNT"
echo -e "  ${YELLOW}WARN${NC}:  $WARN_COUNT"
echo -e "  ${RED}FAIL${NC}:  $FAIL_COUNT"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}✅ Phase 1 Validation Successful!${NC}"
    echo "Ready to proceed to Phase 2: Service Stack Startup"
    exit 0
else
    echo -e "${RED}❌ Phase 1 Validation Failed!${NC}"
    echo "Please fix the above issues and re-run this script."
    exit 1
fi
