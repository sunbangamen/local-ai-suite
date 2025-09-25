# Codex Memo — 프로젝트 평가 및 비용 추정

## 평가 요약
- 종합 점수: 7.5–8.5/10
- 사유: Phase 1/2/3(게이트웨이·RAG·MCP) 흐름과 CLI가 잘 구성됨. 다만 경로/모델/권한/워크트리 등 통합 이슈가 일부 남아 감점.

## 강점
- Docker Compose 기반 멀티 서비스: inference, API Gateway(LiteLLM), RAG, Embedding, MCP.
- OpenAI 호환 게이트웨이 + RAG API + 로컬 CLI 통합 UX.
- 문서화와 운영 명령 구조: README/ARCHITECTURE/memo, make 타깃 일관성.

## 개선 필요(리스크/이슈)
- 경로/권한: `/mnt/e` 하드코딩, `PROJECT_ROOT`/`WORKSPACE` 불일치, SQLite 쓰기 경로 권한.
- 모델명 불일치: MCP `ai_chat` 기본값 vs 게이트웨이 등록 모델 불일치로 400 발생.
- Git worktree: 컨테이너에서 `.git` 포인터 절대경로 불일치로 fatal.
- 운영 준비: 에러 핸들링, 최소 테스트, 포맷/린트, 비밀/설정 관리.

## 비용 추정(대략)
- 로컬 하드웨어(일회성): 250–550만 원 (RTX 4070/4080 + 외장 SSD 등).
- 클라우드 GPU(대안, 월): 80–350만 원/월 (A10G/L4급·지역/사용량 변동).
- 개발 인건비(현재 수준까지): 900–2,500만 원 (약 70–120h × 12–20만 원/h).
- 프로덕션 하드닝 추가: +500–1,200만 원 (모니터링/로그, 보안·비밀관리, 테스트 강화, CI/CD).
- 주의: 모델/성능 목표·보안 요건·데이터 양에 따라 ±30% 이상 변동 가능.

## 점수 상향을 위한 즉시 과제
- 모델 정합: 게이트웨이 `model_name`과 MCP 기본 모델 통일(또는 ENV `API_GATEWAY_MODEL`).
- 경로 표준화: `PROJECT_ROOT=/mnt/workspace`, SQLite를 `data/sqlite/*.db`로 기본 지정 + ENV 오버라이드.
- Git 안전 사용: `--git-dir/--work-tree` 적용 또는 global `safe.directory` 설정.
- 최소 품질 바: pytest 스모크 테스트, Black/Ruff 설정, 기본 에러 핸들링.

## 오늘 상태(마무리)
- 컨테이너: 모두 중지됨(`make down` 처리 완료).
- 문서: `AGENTS.md`(KO) 커밋 완료, `codex_memo.md`는 미커밋 상태 유지.
- CLI: `scripts/ai` 래퍼가 심볼릭 링크·PATH 사용을 지원하도록 개선됨.

## 내일 재개 체크리스트
- 모델 정합: MCP `ai_chat` 기본 모델 ↔ Gateway `model_name`(현재 `local-7b`) 일치.
- 경로 표준화: `PROJECT_ROOT=/mnt/workspace`(compose p3 환경변수), Git `safe.directory` 추가.
- Analytics DB: `AI_ANALYTICS_DB`로 경로 오버라이드 또는 `/mnt/e/ai-data/sqlite` 쓰기 권한 확인.
- 기동/헬스체크: `make up-p2` 또는 `make up-p3` 후 `curl http://localhost:8000/health`, RAG 인덱스/질의 확인.
