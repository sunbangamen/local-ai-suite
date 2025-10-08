# Repository Guidelines

## Project Structure & Module Organization
Keep services under `services/`, with FastAPI backends such as `api-gateway/`, `embedding/`, `rag/`, and `mcp-server/`. Co-locate tests beside each service in `services/<service>/tests/`. Container definitions live in `docker/` (`compose.p1.yml`, `compose.p2.yml`, `compose.p3.yml`). Contributor tooling stays in `scripts/`, while client assets and docs reside in `desktop-app/`, `documents/`, `docs/`, and reference data in `data/`. Place model weights in `models/` and avoid mixing large binaries elsewhere.

## Build, Test, and Development Commands
Use `make up-p1` for a quick single-model smoke stack, `make up-p2` for the standard development suite, and `make up-p3` for the full dual-model plus MCP and desktop flow. Tail container output with `make logs` and stop everything via `make down`. Run targeted tooling with `ai --mcp <tool> --working_dir <path>`.

## Coding Style & Naming Conventions
Target Python 3.11 with 4-space indentation and ≤100-character lines. Prefer type hints, Pydantic models, and `snake_case` for functions and variables, `PascalCase` for classes, and `UPPER_SNAKE` for constants. Before pushing, run Black for formatting and Ruff for linting to keep style consistent across the suite.

## Testing Guidelines
Add `pytest` suites next to each service (`services/<service>/tests/test_*.py`). Cover success and failure paths, and exercise async FastAPI routes with `httpx.AsyncClient`. Mirror production dependencies by running `pytest -q` inside the Phase 2 or 3 containers. Capture CLI snapshots when regressions matter.

## Commit & Pull Request Guidelines
Follow Conventional Commits, e.g., `feat(rag): add query route`. PR descriptions should explain context, list impacted services, link issues (`Closes #123`), and note validation steps such as `make up-p2` or sample curls. Document any `.env` or port changes and include screenshots or logs for UI-facing updates.

## Security & Configuration Tips
Bind services to localhost, store secrets in `.env` files or host keychains, and never commit credentials. Keep GGUF weights confined to `models/` and verify GPU passthrough before enabling heavy inference. Ensure `API_GATEWAY_CHAT_MODEL` and `API_GATEWAY_CODE_MODEL` stay aligned with LiteLLM routing configs prior to deployment.
