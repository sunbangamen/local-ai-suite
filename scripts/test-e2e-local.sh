#!/bin/bash

# E2E 테스트 로컬 실행 스크립트 (Issue #24 Phase 2)
# Desktop App Chat UI E2E 테스트를 로컬에서 실행

set -e

echo "=========================================="
echo "E2E Test Local Execution Script"
echo "Issue #24 Phase 2 - Desktop App Chat UI"
echo "=========================================="
echo ""

# 1. 포트 체크
echo "1️⃣ Checking port availability..."
if lsof -i :3000 > /dev/null 2>&1; then
    echo "⚠️  Port 3000 is already in use. Killing existing process..."
    lsof -ti:3000 | xargs kill -9 2>/dev/null || true
    sleep 2
fi

if lsof -i :8000 > /dev/null 2>&1; then
    echo "✓ API Gateway is running on port 8000"
else
    echo "❌ API Gateway is NOT running on port 8000"
    echo "Please start Phase 2 stack: make up-p2"
    exit 1
fi

# 2. Desktop App 웹 서버 시작
echo ""
echo "2️⃣ Starting Desktop App web server (port 3000)..."
cd "$(dirname "$0")/../desktop-app/src"
python3 -m http.server 3000 > /tmp/web-server.log 2>&1 &
WEB_SERVER_PID=$!
sleep 2

# 헬스 체크
if curl -s http://localhost:3000 > /dev/null; then
    echo "✓ Web server started successfully (PID: $WEB_SERVER_PID)"
else
    echo "❌ Web server failed to start"
    kill $WEB_SERVER_PID 2>/dev/null || true
    cat /tmp/web-server.log
    exit 1
fi

# 3. Playwright 설치
echo ""
echo "3️⃣ Installing Playwright browsers..."
cd "$(dirname "$0")/../desktop-app"
if ! npm list @playwright/test > /dev/null 2>&1; then
    echo "Installing dependencies..."
    npm install
fi

# 4. E2E 테스트 실행
echo ""
echo "4️⃣ Running E2E tests..."
echo "Browser: Chromium"
echo "Base URL: http://localhost:3000"
echo "API Gateway: http://localhost:8000"
echo ""

export PLAYWRIGHT_TEST_BASE_URL=http://localhost:3000
npx playwright test --project=chromium --reporter=html --reporter=list

TEST_RESULT=$?

# 5. 정리
echo ""
echo "5️⃣ Cleaning up..."
kill $WEB_SERVER_PID 2>/dev/null || true
echo "✓ Web server stopped"

# 결과 출력
echo ""
echo "=========================================="
if [ $TEST_RESULT -eq 0 ]; then
    echo "✅ E2E Tests Passed!"
else
    echo "❌ E2E Tests Failed"
    echo ""
    echo "📋 Test Report:"
    if [ -f "playwright-report/index.html" ]; then
        echo "Open: file://$(pwd)/playwright-report/index.html"
    fi
    echo ""
    echo "📊 Web Server Logs:"
    cat /tmp/web-server.log
fi
echo "=========================================="

exit $TEST_RESULT
