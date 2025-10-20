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

## 남은 보안 승인 워크플로우 작업
- MCP 승인 흐름을 사용자 경험까지 연결하기 위해 CLI·대시보드 등 요청/승인 경로 설계를 추가해야 합니다 (`scripts/ai.py` 등 클라이언트에 승인 처리 로직이 아직 없음).
- `APPROVAL_WORKFLOW_ENABLED` 기본값과 관련 문서를 재검토해 운영 환경에서 승인 기능을 활성화하는 절차를 정리해야 합니다 (`docs/security/IMPLEMENTATION_SUMMARY.md`).
- 승인 기능이 완성된 뒤에도 PostgreSQL 마이그레이션, Grafana 모니터링 대시보드 같은 장기 과제는 별도 이슈로 추적해야 합니다 (`docs/progress/v1/fb_5.md`).
- 보안 관리자 API/툴에 승인 요청 조회·처리 기능을 확장해 실운영에서 승인자가 워크플로우를 마칠 수 있게 해야 합니다 (`services/mcp-server/security_admin.py`).
- 승인 로직을 CI 검증 루틴에 포함시켜 컨테이너 내 `pytest` 실행과 결과 수집을 자동화하고, 보안 검증 문서에 최신 절차와 로그 수집 방법을 반영해야 합니다 (`docs/security/IMPLEMENTATION_SUMMARY.md`).
