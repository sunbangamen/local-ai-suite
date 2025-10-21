#!/bin/bash
# health_check_all.sh - Phase 2 헬스체크 자동화 스크립트
# Issue #30: Phase 3 프로덕션 배포 준비 및 시스템 검증

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║    Phase 2: Service Stack Health Check Automation              ║"
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
TIMEOUT_COUNT=0

# Helper functions
check_pass() {
    echo -e "${GREEN}✅ PASS${NC}: $1"
    ((PASS_COUNT++))
}

check_fail() {
    echo -e "${RED}❌ FAIL${NC}: $1"
    ((FAIL_COUNT++))
}

check_timeout() {
    echo -e "${YELLOW}⏱️  TIMEOUT${NC}: $1"
    ((TIMEOUT_COUNT++))
}

check_info() {
    echo -e "${BLUE}ℹ️  INFO${NC}: $1"
}

# Configuration
COMPOSE_FILE="${COMPOSE_FILE:-docker/compose.p3.yml}"
MAX_RETRIES=30  # 30 seconds timeout
RETRY_INTERVAL=1

# Check if compose file exists
if [ ! -f "$COMPOSE_FILE" ]; then
    echo -e "${RED}❌ FAIL${NC}: Docker Compose file not found: $COMPOSE_FILE"
    exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Checking if Phase 3 stack is running..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Get running containers
RUNNING=$(docker compose -f "$COMPOSE_FILE" ps 2>/dev/null | grep -c "Up" || echo "0")
TOTAL=$(docker compose -f "$COMPOSE_FILE" config --services 2>/dev/null | wc -l)

check_info "Running containers: $RUNNING/$TOTAL"
echo ""

# Define services and their health endpoints (8 direct health checks)
# Note: Memory-API included as 8th service
declare -A SERVICES=(
    ["mcp-server"]="http://localhost:8020/health"
    ["api-gateway"]="http://localhost:8000/health"
    ["rag"]="http://localhost:8002/health"
    ["embedding"]="http://localhost:8003/health"
    ["inference-chat"]="http://localhost:8001/health"
    ["inference-code"]="http://localhost:8004/health"
    ["qdrant"]="http://localhost:6333/collections"
    ["memory-api"]="http://localhost:8005/v1/memory/health"
)

# Health check function
check_service_health() {
    local service=$1
    local url=$2
    local retries=0

    while [ $retries -lt $MAX_RETRIES ]; do
        response=$(curl -s -w "\n%{http_code}" "$url" 2>/dev/null || echo "000")
        http_code=$(echo "$response" | tail -n 1)

        if [ "$http_code" = "200" ]; then
            check_pass "$service (HTTP $http_code)"
            return 0
        fi

        retries=$((retries + 1))
        if [ $retries -lt $MAX_RETRIES ]; then
            sleep $RETRY_INTERVAL
        fi
    done

    check_timeout "$service (HTTP $http_code after $MAX_RETRIES retries)"
    return 1
}

# Check each service
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Service Health Checks"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

for service in "${!SERVICES[@]}"; do
    url="${SERVICES[$service]}"
    check_service_health "$service" "$url"
done
echo ""

# Backup Infrastructure Check
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Backup Infrastructure Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check Memory backup directory
if [ -d "/mnt/e/ai-data/memory/backups" ]; then
    check_pass "Memory backup directory exists"
else
    check_info "Memory backup directory not found (will be created)"
fi

# Check Qdrant snapshot capability via API
if curl -s http://localhost:6333/health >/dev/null 2>&1; then
    check_pass "Qdrant API accessible for snapshots"
fi
echo ""

# Check for critical errors in logs
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Error Log Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

ERROR_COUNT=$(docker compose -f "$COMPOSE_FILE" logs 2>/dev/null | grep -i "error\|exception\|fatal" | grep -v "connection refused\|retrying" | wc -l || echo "0")

if [ "$ERROR_COUNT" -eq 0 ]; then
    check_pass "No critical errors found in logs"
else
    check_fail "$ERROR_COUNT critical error(s) found in logs"
fi
echo ""

# GPU Status Check
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "GPU Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if command -v nvidia-smi &> /dev/null; then
    GPU_MEMORY=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader 2>/dev/null | head -1 | awk '{print $1}')
    GPU_TOTAL=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader 2>/dev/null | head -1 | awk '{print $1}')
    GPU_UTIL=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader 2>/dev/null | head -1)

    check_info "GPU Memory: ${GPU_MEMORY}MB / ${GPU_TOTAL}MB"
    check_info "GPU Utilization: $GPU_UTIL"

    # Check if GPU memory usage is within acceptable limits
    LIMIT=5500  # 90% of 6GB RTX 4050
    if [ "${GPU_MEMORY%.*}" -lt "$LIMIT" ]; then
        check_pass "GPU memory within limits (${GPU_MEMORY}MB < ${LIMIT}MB)"
    else
        check_fail "GPU memory exceeds limits (${GPU_MEMORY}MB > ${LIMIT}MB)"
    fi
else
    check_info "NVIDIA GPU monitoring not available"
fi
echo ""

# Summary
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                  Health Check Summary                          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo -e "  ${GREEN}PASS${NC}: $PASS_COUNT | ${YELLOW}TIMEOUT${NC}: $TIMEOUT_COUNT | ${RED}FAIL${NC}: $FAIL_COUNT"
echo ""

if [ $FAIL_COUNT -eq 0 ] && [ $TIMEOUT_COUNT -eq 0 ]; then
    echo -e "${GREEN}✅ All Health Checks Passed!${NC}"
    echo "Ready to proceed to Phase 3: Monitoring Stack Verification"
    exit 0
elif [ $TIMEOUT_COUNT -gt 0 ] && [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Some services are still starting up${NC}"
    echo "Please wait a moment and re-run this script"
    exit 1
else
    echo -e "${RED}❌ Health Checks Failed!${NC}"
    echo "Please review the failures above and check service logs"
    exit 1
fi
