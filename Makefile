.PHONY: up-p1 up-p2 up-p3 down down-p1 down-p2 down-p3 logs logs-p1 logs-p2 logs-p3

# Phase별 실행
up-p1:
	docker compose -f docker/compose.p1.yml --env-file .env up -d --build

up-p2:
	docker compose -f docker/compose.p2.cpu.yml --env-file .env up -d --build

up-p2-gpu:
	docker compose -f docker/compose.p2.yml --env-file .env up -d --build

up-p3:
	docker compose -f docker/compose.p3.yml --env-file .env up -d --build

# 전체 종료 (역순)
down:
	docker compose -f docker/compose.p2.cpu.yml down || true
	docker compose -f docker/compose.p3.yml down || true
	docker compose -f docker/compose.p2.yml down || true
	docker compose -f docker/compose.p1.yml down || true

# Phase별 종료
down-p1:
	docker compose -f docker/compose.p1.yml down

down-p2:
	docker compose -f docker/compose.p2.cpu.yml down

down-p2-gpu:
	docker compose -f docker/compose.p2.yml down

down-p3:
	docker compose -f docker/compose.p3.yml down

# 전체 로그
logs:
	docker compose -f docker/compose.p3.yml logs -f || \
	docker compose -f docker/compose.p2.yml logs -f || \
	docker compose -f docker/compose.p1.yml logs -f

# Phase별 로그
logs-p1:
	docker compose -f docker/compose.p1.yml logs -f

logs-p2:
	docker compose -f docker/compose.p2.cpu.yml logs -f

logs-p2-gpu:
	docker compose -f docker/compose.p2.yml logs -f

logs-p3:
	docker compose -f docker/compose.p3.yml logs -f

.PHONY: test-rag-integration test-rag-integration-coverage test-rag-integration-extended test-load test-load-api test-load-rag test-load-mcp test-load-baseline

test-rag-integration:
	@echo "Running RAG integration tests in Docker container..."
	@docker compose -f docker/compose.p2.cpu.yml ps | grep -q "Up" || \
		(echo "❌ Phase 2 stack not running. Start with: make up-p2" && exit 1)
	docker compose -f docker/compose.p2.cpu.yml exec rag bash -lc "rm -rf /app/services/rag/tests && mkdir -p /app/services/rag"
	docker compose -f docker/compose.p2.cpu.yml cp services/rag/tests rag:/app/services/rag
	docker compose -f docker/compose.p2.cpu.yml exec rag bash -lc \
		"cd /app && RUN_RAG_INTEGRATION_TESTS=1 pytest services/rag/tests/integration -v --tb=short"
	@echo "✅ Integration tests complete."

test-rag-integration-coverage:
	@echo "Running RAG integration tests with coverage..."
	@docker compose -f docker/compose.p2.cpu.yml ps | grep -q "Up" || \
		(echo "❌ Phase 2 stack not running. Start with: make up-p2" && exit 1)
	docker compose -f docker/compose.p2.cpu.yml exec rag bash -lc "rm -rf /app/services/rag/tests && mkdir -p /app/services/rag"
	docker compose -f docker/compose.p2.cpu.yml cp services/rag/tests rag:/app/services/rag
	docker compose -f docker/compose.p2.cpu.yml exec rag bash -lc \
		"cd /app && RUN_RAG_INTEGRATION_TESTS=1 pytest services/rag/tests/integration \
		--cov=app --cov=services/rag/tests --cov-report=term-missing --cov-report=json"
	docker compose -f docker/compose.p2.cpu.yml cp rag:/app/coverage.json docs/rag_integration_coverage.json
	@echo "✅ Coverage saved to docs/rag_integration_coverage.json."

test-rag-integration-extended:
	@echo "Running extended RAG integration tests (Phase 1 - Issue #24)..."
	@docker compose -f docker/compose.p2.cpu.yml ps | grep -q "Up" || \
		(echo "❌ Phase 2 stack not running. Start with: make up-p2" && exit 1)
	docker compose -f docker/compose.p2.cpu.yml exec rag bash -lc "rm -rf /app/services/rag/tests && mkdir -p /app/services/rag"
	docker compose -f docker/compose.p2.cpu.yml cp services/rag/tests rag:/app/services/rag
	docker compose -f docker/compose.p2.cpu.yml exec rag bash -lc \
		"cd /app && RUN_RAG_INTEGRATION_TESTS=1 pytest services/rag/tests/integration/test_extended_coverage.py \
		-v --tb=short --cov=app --cov=services/rag/tests --cov-report=term-missing --cov-report=json"
	docker compose -f docker/compose.p2.cpu.yml cp rag:/app/coverage.json docs/rag_extended_coverage.json
	@echo "✅ Extended tests complete. Coverage saved to docs/rag_extended_coverage.json."

# Load Testing Targets (Phase 3 - Issue #24)
test-load-baseline:
	@echo "Running Locust baseline test (1 user)..."
	@command -v locust >/dev/null 2>&1 || (echo "❌ Locust not installed. Install: pip install locust" && exit 1)
	@docker compose -f docker/compose.p2.cpu.yml ps | grep -q "Up" || \
		(echo "❌ Phase 2 stack not running. Start with: make up-p2" && exit 1)
	locust -f tests/load/locustfile.py APIGatewayUser \
		--host http://localhost:8000 \
		--users 1 --spawn-rate 1 \
		--run-time 2m \
		--headless -q
	@echo "✅ Baseline test complete."

test-load-api:
	@echo "Running API Gateway load test (10 → 50 → 100 users)..."
	@command -v locust >/dev/null 2>&1 || (echo "❌ Locust not installed. Install: pip install locust" && exit 1)
	@docker compose -f docker/compose.p2.cpu.yml ps | grep -q "Up" || \
		(echo "❌ Phase 2 stack not running. Start with: make up-p2" && exit 1)
	@echo "Level 1: 10 users (5 min)"
	locust -f tests/load/locustfile.py APIGatewayUser \
		--host http://localhost:8000 \
		--users 10 --spawn-rate 1 \
		--run-time 5m \
		--headless -q
	@echo "Level 2: 50 users (5 min)"
	locust -f tests/load/locustfile.py APIGatewayUser \
		--host http://localhost:8000 \
		--users 50 --spawn-rate 5 \
		--run-time 5m \
		--headless -q
	@echo "Level 3: 100 users (5 min)"
	locust -f tests/load/locustfile.py APIGatewayUser \
		--host http://localhost:8000 \
		--users 100 --spawn-rate 10 \
		--run-time 5m \
		--headless -q
	@echo "✅ API Gateway load test complete."

test-load-rag:
	@echo "Running RAG Service load test (5 → 25 → 50 users)..."
	@command -v locust >/dev/null 2>&1 || (echo "❌ Locust not installed. Install: pip install locust" && exit 1)
	@docker compose -f docker/compose.p2.cpu.yml ps | grep -q "Up" || \
		(echo "❌ Phase 2 stack not running. Start with: make up-p2" && exit 1)
	@echo "Level 1: 5 users (5 min)"
	locust -f tests/load/locustfile.py RAGServiceUser \
		--host http://localhost:8002 \
		--users 5 --spawn-rate 1 \
		--run-time 5m \
		--headless -q
	@echo "Level 2: 25 users (5 min)"
	locust -f tests/load/locustfile.py RAGServiceUser \
		--host http://localhost:8002 \
		--users 25 --spawn-rate 3 \
		--run-time 5m \
		--headless -q
	@echo "Level 3: 50 users (5 min)"
	locust -f tests/load/locustfile.py RAGServiceUser \
		--host http://localhost:8002 \
		--users 50 --spawn-rate 5 \
		--run-time 5m \
		--headless -q
	@echo "✅ RAG Service load test complete."

test-load-mcp:
	@echo "Running MCP Server load test (5 → 20 users)..."
	@command -v locust >/dev/null 2>&1 || (echo "❌ Locust not installed. Install: pip install locust" && exit 1)
	@docker compose -f docker/compose.p2.cpu.yml ps | grep -q "Up" || \
		(echo "❌ Phase 2 stack not running. Start with: make up-p2" && exit 1)
	@echo "Level 1: 5 users (5 min)"
	locust -f tests/load/locustfile.py MCPServerUser \
		--host http://localhost:8020 \
		--users 5 --spawn-rate 1 \
		--run-time 5m \
		--headless -q
	@echo "Level 2: 20 users (5 min)"
	locust -f tests/load/locustfile.py MCPServerUser \
		--host http://localhost:8020 \
		--users 20 --spawn-rate 2 \
		--run-time 5m \
		--headless -q
	@echo "✅ MCP Server load test complete."

test-load:
	@echo "Running full load test suite (all 3 scenarios)..."
	@make test-load-api
	@make test-load-rag
	@make test-load-mcp
	@echo "✅ Full load test suite complete."
