.PHONY: up-p1 up-p2 up-p3 down down-p1 down-p2 down-p3 logs logs-p1 logs-p2 logs-p3

# Phase별 실행
up-p1:
	docker compose -f docker/compose.p1.yml --env-file .env up -d --build

up-p2:
	docker compose -f docker/compose.p2.yml --env-file .env up -d --build

up-p3:
	docker compose -f docker/compose.p3.yml --env-file .env up -d --build

# 전체 종료 (역순)
down:
	docker compose -f docker/compose.p3.yml down || true
	docker compose -f docker/compose.p2.yml down || true
	docker compose -f docker/compose.p1.yml down || true

# Phase별 종료
down-p1:
	docker compose -f docker/compose.p1.yml down

down-p2:
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
	docker compose -f docker/compose.p2.yml logs -f

logs-p3:
	docker compose -f docker/compose.p3.yml logs -f