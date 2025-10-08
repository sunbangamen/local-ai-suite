# ADR-002: Memory System Implementation vs. Planning Document Discrepancies

## Status
Accepted

## Context
메모리 시스템이 9개 프로젝트에서 실사용 중인 시점에서 계획 문서(`memory_system_plan.md`)와 실제 구현(`scripts/memory_system.py`) 간 4가지 주요 불일치가 발견되었습니다.

### 발견된 불일치 사항

#### 1. 태그 저장 방식
- **계획**: `conversation_tags` 정규화 테이블 (N:M 관계)
- **실제**: `conversations.tags TEXT` (JSON 배열)
- **위치**: `memory_system.py:248`

#### 2. CLI 옵션 수
- **계획**: 6개 옵션
- **실제**: 7개 옵션 (`--memory-dir` 추가)
- **위치**: `ai.py:668-674`

#### 3. 경로 환경변수
- **계획**: `MEMORY_ROOT=~/.local/share/local-ai/memory`
- **실제**: `AI_MEMORY_DIR=/mnt/e/ai-data/memory`
- **위치**: `memory_system.py:92`

#### 4. 임베딩 구조
- **계획**: `embedding BLOB (1536차원)` + `vector_store_id`
- **실제**: `embedding_vector TEXT (JSON)` + `qdrant_point_id`
- **위치**: `memory_system.py:299`

## Decision

### 1. 태그 저장: JSON 배열 방식 채택

**선택한 접근법**: `conversations.tags TEXT (JSON)`

**이유**:
- **개발 속도**: 정규화 테이블 대비 스키마가 단순하고 구현이 빠름
- **충분한 성능**: 현재 9개 프로젝트 실사용에서 검색 성능 이슈 미발생
- **SQLite JSON 지원**: SQLite의 `json_each()`, `json_extract()` 함수로 충분히 쿼리 가능
- **소규모 태그**: 대화당 평균 3-5개 태그로 정규화 필요성 낮음

**트레이드오프**:
- ✅ 장점: 단순한 스키마, 빠른 개발, 원자적 업데이트
- ⚠️ 단점: 태그 중복 저장, 태그 단독 인덱싱 불가
- 🔄 재검토 트리거: 대화 수 10만 건 초과 시 또는 태그 검색 성능 저하 발생 시

**대안**:
- **Option A (정규화)**: `conversation_tags(conversation_id, tag)` 테이블
  - 장점: 태그 인덱스 가능, 저장 공간 효율적
  - 단점: JOIN 쿼리 필요, 스키마 복잡도 증가
  - 선택 안 한 이유: 현재 규모에서 과도한 엔지니어링

- **Option B (JSONB)**: PostgreSQL JSONB 타입 (GIN 인덱스)
  - 장점: JSON + 인덱싱 동시 지원
  - 단점: PostgreSQL 의존성 추가
  - 선택 안 한 이유: SQLite로 충분, 추가 의존성 불필요

### 2. CLI 옵션: 7개 옵션 공식화

**추가된 옵션**: `--memory-dir`

**이유**:
- **유연성**: 테스트/개발 시 임시 메모리 디렉토리 지정 필요
- **격리**: CI/CD 환경에서 독립적인 메모리 공간 활용
- **디버깅**: 문제 발생 시 격리된 환경에서 재현 용이

**명령어 체계**:
```bash
ai --memory                  # 상태 확인
ai --memory-init             # 초기화
ai --memory-search "query"   # 검색
ai --memory-cleanup          # 정리
ai --memory-backup [path]    # 백업
ai --memory-stats            # 통계
ai --memory-dir /path        # 경로 오버라이드 (신규)
```

**미구현 명령어**:
- `--memory --save`: 영구 저장 플래그 (자동 중요도 판정으로 대체)
- `--set-retention`: 보관기간 설정 (TTL 레벨 시스템으로 충분)
- `--set-auto-cleanup`: 자동 정리 토글 (수동 실행으로 충분)

### 3. 환경변수: `AI_MEMORY_DIR` 표준화

**선택한 변수명**: `AI_MEMORY_DIR`

**이유**:
- **명확성**: `AI_` 접두사로 프로젝트 네임스페이스 명확화
- **일관성**: 다른 환경변수(`AI_*`)와 일관된 네이밍
- **확장성**: 향후 `AI_CACHE_DIR`, `AI_LOG_DIR` 등 확장 용이

**경로 우선순위**:
1. `--memory-dir` CLI 옵션 (최우선)
2. `AI_MEMORY_DIR` 환경변수
3. `/mnt/e/ai-data/memory` (하드코드 기본값)
4. `{project_root}/.ai-memory-data` (로컬 폴백)
5. `{cwd}/.ai-memory-data` (최종 폴백)

**Docker 환경 특수 처리**:
- `DEFAULT_PROJECT_ID` 환경변수로 중앙집중식 메모리 관리
- `/.dockerenv` 파일 존재 시 `docker-default` 프로젝트 사용

### 4. 임베딩 구조: JSON 텍스트 저장

**선택한 구조**: `embedding_vector TEXT (JSON)` + `qdrant_point_id`

**이유**:
- **호환성**: JSON은 범용 포맷으로 디버깅 및 검증 용이
- **유연성**: 벡터 차원 변경 시 스키마 변경 불필요
- **Qdrant 동기화**: `qdrant_point_id`로 외부 스토어 직접 연결
- **로컬 폴백**: Qdrant 장애 시 SQLite에서 JSON 벡터 읽기 가능

**트레이드오프**:
- ✅ 장점: 가독성, 디버깅 용이, 스키마 유연성
- ⚠️ 단점: 저장 공간 3-4배 증가 (384차원 기준: BLOB 1.5KB vs JSON 4-6KB)
- 🔄 재검토 트리거: 저장 공간 이슈 발생 시 BLOB으로 마이그레이션

**대안**:
- **Option A (BLOB)**: `embedding BLOB` + pickle/numpy 직렬화
  - 장점: 저장 공간 효율적, 빠른 역직렬화
  - 단점: 바이너리 데이터로 디버깅 어려움
  - 선택 안 한 이유: 개발/운영 단계에서 가시성 우선

- **Option B (PostgreSQL pgvector)**: 네이티브 벡터 타입
  - 장점: 벡터 연산 DB 내장, 인덱스 지원
  - 단점: PostgreSQL 의존성
  - 선택 안 한 이유: SQLite + Qdrant 조합으로 충분

## Consequences

### Positive
1. **문서-코드 일치**: 신규 기여자 온보딩 개선
2. **의사결정 투명성**: 향후 개선 시 배경 컨텍스트 제공
3. **재검토 기준 명확화**: 성능 이슈 발생 시 즉각 대응 가능
4. **실사용 기반 검증**: 9개 프로젝트 실제 운영 데이터로 검증된 선택

### Negative
1. **기술 부채 인지**: JSON/태그 구조는 향후 마이그레이션 가능성 존재
2. **저장 공간 비효율**: 임베딩 JSON 저장으로 3-4배 공간 사용

### Neutral
1. **CLI 명령어 체계**: 복합 명령어 대신 독립 플래그로 단순화
2. **환경변수 네이밍**: `MEMORY_ROOT` → `AI_MEMORY_DIR` 표준화

## Validation

### 실사용 검증 (2025-10-08)
- ✅ 9개 프로젝트에서 안정적 운영 중
- ✅ 평균 대화 수: 200-500개/프로젝트
- ✅ 검색 응답 시간: <100ms (FTS5), <200ms (하이브리드)
- ✅ 권한 오류 자동 복구 동작 확인
- ✅ Docker/로컬 환경 자동 감지 정상

### 성능 벤치마크
```
검색 속도 (1000개 대화 기준):
- FTS5 키워드: 50-80ms
- 벡터 유사도: 120-150ms
- 하이브리드: 180-220ms

저장 공간 (프로젝트당):
- 대화 데이터: ~2MB (500개 대화)
- 임베딩 JSON: ~3MB (500개 벡터)
- 총합: ~5MB/500대화 (10KB/대화)
```

## Future Considerations

### 재검토 트리거
1. **태그 정규화**: 대화 수 10만 건 초과 또는 태그 검색 >500ms
2. **임베딩 BLOB 전환**: 프로젝트당 저장 공간 >100MB
3. **PostgreSQL 마이그레이션**: 동시 사용자 10명 이상 또는 동시성 이슈 발생
4. **백그라운드 정리 스케줄러**: 수동 정리 불편 피드백 누적 시

### 마이그레이션 경로
```
[현재 구조]
  ├─> 태그 정규화 (검색 성능 이슈 시)
  ├─> 임베딩 BLOB 전환 (저장 공간 이슈 시)
  └─> PostgreSQL 전환 (동시성 요구 증가 시)
      └─> pgvector 통합 (Qdrant 제거 옵션)
```

## References
- **Issue**: #12
- **구현**: `scripts/memory_system.py`
- **CLI**: `scripts/ai.py:668-674`
- **문서**: `memory_system_plan.md`
- **테스트**: `docs/MEMORY_SYSTEM_TEST_RESULTS.md`

## Metadata
- **Date**: 2025-10-08
- **Author**: AI Memory System Team
- **Status**: Accepted
- **Supersedes**: N/A
- **Superseded by**: N/A
