# Repository Guidelines

## Project Structure & Module Organization
- `docker/`: Compose stacks for Phase 1/2; use `compose.p1.yml` and `compose.p2.yml` targets, note `up-p3` has no companion file yet.
- `services/`: Core applications — `api-gateway/` (LiteLLM proxy), `embedding/` (FastAPI + FastEmbed on port 8003), `rag/` (Qdrant-backed RAG API on port 8002).
- `models/`: Read-only mount for local GGUF models consumed by inference containers.
- `documents/`: Source content for RAG indexing runs.
- `scripts/`: CLI helpers such as `ai`, `ai.py`, and `download-models.sh`.
- `data/`, `docs/`: Generated artifacts and reference documentation.

## Build, Test, and Development Commands
- `make up-p1`: Launch inference and API gateway services; verify with `curl http://localhost:8000/health`.
- `make up-p2`: Start Phase 1 stack plus Qdrant, embedding, and RAG services; index with `curl -X POST "http://localhost:8002/index?collection=myproj"` and query via `curl -H 'Content-Type: application/json' -d '{"query":"...","collection":"myproj"}' http://localhost:8002/query`.
- `make down`: Stop all services cleanly; `make logs`: Follow combined stack logs for troubleshooting.

## Coding Style & Naming Conventions
- Python 3.11 across services; prefer explicit type hints and Pydantic models for request/response schemas.
- Format with Black and lint with Ruff; keep lines ≤100 characters and use 4-space indentation.
- Naming: modules, functions, and variables in `snake_case`; classes in `PascalCase`; constants in `UPPER_SNAKE`.

## Testing Guidelines
- Use `pytest -q`; locate tests next to the relevant service (e.g., `services/rag/tests/`).
- Name files `test_*.py` and functions `test_*`; cover both success and failure paths for new endpoints.
- Employ `httpx.AsyncClient` when exercising FastAPI routes.

## Commit & Pull Request Guidelines
- Follow Conventional Commits, e.g., `feat(rag): add query route`.
- PRs must describe context, list affected services/paths, and link issues (`Closes #123`).
- Document local validation steps (`make up-p2`, sample `curl` runs) and highlight any configuration changes such as `.env` updates, ports, or models.

## Security & Configuration Tips
- Bind services to localhost only and avoid exposing containers publicly.
- Manage secrets via `.env`; never commit credentials. Store GGUF weights under `models/`.
- Confirm GPU settings in Docker Desktop/WSL when enabling `llama.cpp` acceleration.
