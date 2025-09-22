.PHONY: up-p1 up-p2 up-p3 down logs

up-p1:
	docker compose -f docker/compose.p1.yml --env-file .env up -d --build

up-p2:
	docker compose -f docker/compose.p2.yml --env-file .env up -d --build

up-p3:
	docker compose -f docker/compose.p3.yml --env-file .env up -d --build

down:
	docker compose -f docker/compose.p3.yml down || true
	docker compose -f docker/compose.p2.yml down || true
	docker compose -f docker/compose.p1.yml down || true

logs:
	docker compose -f docker/compose.p3.yml logs -f || \
	docker compose -f docker/compose.p2.yml logs -f || \
	docker compose -f docker/compose.p1.yml logs -f