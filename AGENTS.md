# Repository Guidelines

## Project Structure & Module Organization
- `docker/`: Compose stacks (`compose.p1.yml` single-model, `compose.p2.yml` standard stack, `compose.p3.yml` dual-model + MCP). Phase-specific configs live in `services/api-gateway/`.
- `services/`: Core backends — `api-gateway/` (LiteLLM), `embedding/`, `rag/`, `mcp-server/`, plus inference Dockerfiles.
- `scripts/`: CLI tooling (`ai`, `ai.py`, `model_warmup.py`, analytics helpers) and install scripts.
- `desktop-app/`: Electron UI; `docs/`, `documents/`, `models/` hold reference material, indexed content, and GGUF weights.
- Tests live beside each service (e.g., `services/rag/tests/`); create directories if absent.

## Build, Test, and Development Commands
- `make up-p1`: Launch single inference + gateway; good for quick sanity checks.
- `make up-p2`: Bring up inference, gateway, embedding, Qdrant, and RAG (default dev stack).
- `make up-p3`: Run full dual-model + MCP + desktop stack for end-to-end flows.
- `make down`: Stop all containers; `make logs`: Tail combined Docker logs.
- `ai --mcp ...`: Invoke MCP tools (respects `working_dir`).

## Coding Style & Naming Conventions
- Python 3.11 with FastAPI; enforce 4-space indentation and ≤100-character lines.
- Use type hints, Pydantic models, and descriptive docstrings where logic is non-trivial.
- Naming: modules/functions/variables `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE`.
- Format with Black, lint with Ruff; pin dependencies in each service’s `requirements.txt`.

## Testing Guidelines
- Primary framework: `pytest`; target asynchronous routes with `httpx.AsyncClient`.
- Place tests near their services (`services/<service>/tests/test_*.py`).
- Cover success/error paths for new endpoints; snapshot regression is acceptable for CLI output.
- Run `pytest -q` inside the relevant container (Phase 2/3) to ensure dependencies match production images.

## Commit & Pull Request Guidelines
- Follow Conventional Commits (`feat(rag): add query route`, `fix(mcp): handle working_dir`).
- PRs should describe context, impacted services, linked issues (e.g., `Closes #123`), and validation steps (`make up-p2`, sample curls/MCP calls).
- Document env/config changes (`.env`, ports, model names) explicitly and include screenshots/log snippets for UI edits.

## Security & Configuration Tips
- Keep services bound to localhost; never expose Docker ports publicly.
- Store secrets in `.env` or host keychains; avoid committing credentials or analytics databases.
- Ensure GGUF models stay under `models/`; verify GPU passthrough before enabling high-load inference.
- RAG/MCP rely on `API_GATEWAY_CHAT_MODEL` / `API_GATEWAY_CODE_MODEL`; confirm these match LiteLLM config before deployment.
