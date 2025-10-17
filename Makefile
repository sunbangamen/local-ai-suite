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

.PHONY: test-rag-integration test-rag-integration-coverage test-rag-integration-extended

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
