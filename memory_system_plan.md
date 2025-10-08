# 🧠 프로젝트별 장기 기억 시스템 - 현재 구현 상태

> **⚠️ 문서 상태**: 이 문서는 실제 구현(`scripts/memory_system.py`)에 기반한 현재 운영 중인 시스템을 반영합니다.
>
> **✅ 운영 현황**: 9개 프로젝트에서 안정적으로 실사용 중 (2025-10-08 기준)

## 📋 시스템 개요

**핵심 기능:**
- 프로젝트별 독립적인 장기 기억 (SQLite 기반)
- 무제한 대화 이력 저장 및 검색
- 중요도 기반 자동 TTL 관리 (1-10 레벨)
- FTS5 전문 검색 + Qdrant 벡터 검색 (하이브리드)
- Docker/로컬 환경 자동 감지 및 대응

## 🏗️ 시스템 아키텍처 설계

### 1. 데이터 저장 구조

**실제 경로 우선순위:**
1. `--memory-dir` CLI 옵션 (명시적 지정)
2. `AI_MEMORY_DIR` 환경변수
3. `/mnt/e/ai-data/memory` (기본 경로)
4. 프로젝트 로컬 폴백: `{project_root}/.ai-memory-data`
5. 최종 폴백: `{current_dir}/.ai-memory-data`

**디렉토리 구조:**
```
/mnt/e/ai-data/memory/              # 기본 데이터 디렉토리
├── projects/
│   ├── {project_uuid}/
│   │   ├── memory.db               # SQLite DB (WAL 모드)
│   │   └── project.json            # 프로젝트 메타데이터
│   └── docker-default/             # Docker 환경 전용
│       ├── memory.db
│       └── project.json
├── global/
│   └── (글로벌 설정용 예약)
└── backups/
    └── memory_{project_id}_{timestamp}.json  # JSON 백업
```

> **⚠️ 태그 저장 방식**: `conversation_tags` 정규화 테이블이 아닌 **`conversations.tags TEXT (JSON 배열)`** 형태로 저장됩니다.
> 이는 간단한 구조와 빠른 개발을 위한 선택이며, 향후 검색 성능 이슈 발생 시 정규화 검토 예정입니다.

### 2. 데이터베이스 스키마 (SQLite)

**현재 구현된 스키마** (memory_system.py:236-357):

```sql
-- 대화 기록 테이블
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    user_query TEXT NOT NULL,
    ai_response TEXT NOT NULL,
    model_used VARCHAR(50),
    importance_score INTEGER DEFAULT 5,      -- 1(즉시삭제) ~ 10(영구보관)
    tags TEXT,                               -- JSON 배열 형태로 저장 ⚠️
    session_id VARCHAR(50),
    token_count INTEGER,
    response_time_ms INTEGER,
    project_context TEXT,                    -- JSON 형태 프로젝트 컨텍스트
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME                      -- TTL 자동 삭제용
);

-- 대화 요약 테이블
CREATE TABLE conversation_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_range TEXT,                         -- "2024-09-01 to 2024-09-07"
    summary TEXT,                            -- AI 생성 요약
    conversation_count INTEGER,
    importance_level INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 중요 사실 테이블
CREATE TABLE important_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact TEXT NOT NULL,
    category VARCHAR(100),                   -- code, config, decision 등
    source_conversation_id INTEGER,
    user_marked BOOLEAN DEFAULT FALSE,
    ai_suggested BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_conversation_id) REFERENCES conversations(id)
);

-- 사용자 선호도 테이블
CREATE TABLE user_preferences (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 벡터 임베딩 테이블 (Qdrant 동기화용)
CREATE TABLE conversation_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    embedding_vector TEXT,                   -- JSON 형태 임베딩 벡터 ⚠️
    qdrant_point_id TEXT,                    -- Qdrant 포인트 ID ⚠️
    sync_status TEXT DEFAULT 'pending',      -- 'pending', 'synced', 'failed'
    synced_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id),
    UNIQUE(conversation_id)
);

-- FTS5 전문 검색 테이블
CREATE VIRTUAL TABLE conversations_fts USING fts5(
    user_query,
    ai_response,
    content='conversations',
    content_rowid='id'
);

-- 인덱스
CREATE INDEX idx_conversations_timestamp ON conversations(timestamp);
CREATE INDEX idx_conversations_importance ON conversations(importance_score);
CREATE INDEX idx_conversations_expires_at ON conversations(expires_at);
CREATE INDEX idx_conversations_session_id ON conversations(session_id);
CREATE INDEX idx_conversations_model_used ON conversations(model_used);
CREATE INDEX idx_important_facts_category ON important_facts(category);
CREATE INDEX idx_conversation_embeddings_sync_status ON conversation_embeddings(sync_status);
```

**⚠️ 계획 문서와의 차이점:**

1. **`conversation_tags` 테이블 없음**: 대신 `conversations.tags TEXT (JSON)` 사용
2. **임베딩 구조**: `embedding BLOB`이 아닌 `embedding_vector TEXT (JSON)` 사용
3. **벡터 스토어 ID**: `vector_store_id` 대신 `qdrant_point_id` 사용
4. **동기화 상태 추적**: `sync_status`, `synced_at` 필드로 Qdrant 동기화 관리
5. **TTL 지원**: `expires_at` 필드로 자동 만료 관리

> **설계 결정 배경**: JSON 기반 접근은 스키마 단순성과 빠른 개발을 우선했습니다.
> 실사용 중 검색 성능 이슈가 발생하지 않았으며, SQLite의 JSON 함수로 충분히 관리 가능합니다.

### 3. 중요도 기반 자동 정리 시스템

**중요도 점수 시스템 (1-10):**
```python
IMPORTANCE_LEVELS = {
    1: {"name": "즉시삭제", "ttl_days": 0, "description": "인사, 테스트"},
    2: {"name": "단기보관", "ttl_days": 3, "description": "간단한 질문"},
    3: {"name": "1주보관", "ttl_days": 7, "description": "일반 대화"},
    4: {"name": "2주보관", "ttl_days": 14, "description": "정보성 질문"},
    5: {"name": "기본보관", "ttl_days": 30, "description": "기본값"},
    6: {"name": "1개월", "ttl_days": 30, "description": "코드 관련"},
    7: {"name": "3개월", "ttl_days": 90, "description": "프로젝트 설정"},
    8: {"name": "6개월", "ttl_days": 180, "description": "중요 결정사항"},
    9: {"name": "1년보관", "ttl_days": 365, "description": "핵심 문서화"},
    10: {"name": "영구보관", "ttl_days": -1, "description": "사용자 중요표시"}
}
```

**자동 중요도 판정 로직:**
```python
def calculate_importance_score(query: str, response: str, context: dict) -> int:
    score = 5  # 기본값

    # 키워드 기반 점수 조정
    high_importance_keywords = [
        "설정", "config", "환경변수", "architecture", "design pattern",
        "버그", "해결", "문제", "오류", "에러", "fix", "bug",
        "구현", "알고리즘", "최적화", "성능", "performance"
    ]

    low_importance_keywords = [
        "안녕", "hello", "테스트", "test", "확인", "체크"
    ]

    if any(word in query or word in response for word in high_importance_keywords):
        score += 2
    if any(word in query or word in response for word in low_importance_keywords):
        score -= 2

    # 응답 길이 고려 (긴 응답 = 더 중요)
    if len(response) > 1000:
        score += 1
    if len(response) > 2000:
        score += 1

    # 코드 포함 여부
    if "```" in response or "def " in response or "class " in response:
        score += 1

    # 사용자 피드백 반영
    if context.get("user_saved", False):
        score = 10
    if context.get("user_dismissed", False):
        score = min(score, 3)

    return max(1, min(10, score))
```

### 4. 컨텍스트 검색 및 관련성 시스템

**관련성 검색 알고리즘:**
```python
def get_relevant_context(current_query: str, project_path: str, limit: int = 5) -> List[Dict]:
    """현재 질문과 관련된 이전 대화 검색"""

    # 1. 키워드 매칭
    # 2. 의미적 유사성 (임베딩 기반)
    # 3. 시간적 근접성
    # 4. 중요도 가중치

    return relevant_conversations
```

> 의미 검색은 `conversation_embeddings` 테이블 또는 Qdrant 컬렉션에서 cosine 유사도로 수행하고, 결과는 태그/중요도 기준으로 재정렬.

### 5. 사용자 인터페이스

**현재 구현된 CLI 명령어** (ai.py:668-674):

```bash
# 메모리 관리 명령어 (7개 옵션)
ai --memory                           # 메모리 시스템 상태 표시
ai --memory-init                      # 프로젝트 메모리 초기화
ai --memory-search "키워드"           # 대화 검색 (FTS5 기반)
ai --memory-cleanup                   # 만료된 대화 정리 (TTL)
ai --memory-backup [PATH]             # JSON 백업 생성
ai --memory-stats                     # 상세 통계 정보
ai --memory-dir /custom/path          # 메모리 저장 경로 오버라이드
```

**⚠️ 계획 문서와의 차이점:**
- 총 **7개 옵션** 구현 (계획: 6개)
- `--memory-dir` 옵션 추가됨 (동적 경로 지정)
- 복합 명령어(`--memory --save`, `--memory --forget`) 대신 독립적인 플래그 사용
- 세부 설정 명령어(`--set-retention`, `--set-auto-cleanup`)는 미구현

**환경 변수:**
| 변수명 | 용도 | 기본값 | 우선순위 |
|--------|------|--------|----------|
| `AI_MEMORY_DIR` | 메모리 데이터 디렉토리 | `/mnt/e/ai-data/memory` | 2순위 |
| `DEFAULT_PROJECT_ID` | Docker 환경 프로젝트 ID | (없음) | Docker 우선 |
| `EMBEDDING_URL` | 임베딩 서비스 URL | `http://localhost:8003` | - |
| `QDRANT_URL` | Qdrant 벡터 DB URL | `http://localhost:6333` | - |

**Desktop App UI:**
- ⚠️ 현재 미구현 (Phase 4 예정)

## 📊 구현 현황

### ✅ Phase 1: 기본 저장 시스템 (완료)
- ✅ SQLite 데이터베이스 설계 및 생성 (WAL 모드)
- ✅ 기본 대화 저장/조회 기능
- ✅ 프로젝트 식별 시스템 (UUID 기반)
- ✅ JSON 백업 시스템
- ✅ Thread-safe 연결 관리

### ✅ Phase 2: 자동 정리 시스템 (완료)
- ✅ 중요도 자동 판정 로직 (1-10 레벨)
- ✅ TTL 기반 자동 삭제 (`expires_at` 필드)
- ✅ 수동 정리 명령어 (`--memory-cleanup`)
- ⚠️ 백그라운드 정리 스케줄러 (미구현, 수동 실행 필요)

### ✅ Phase 3: 검색 및 컨텍스트 시스템 (완료)
- ✅ FTS5 전문 검색 (BM25 랭킹)
- ✅ 하이브리드 검색 (FTS5 + 벡터 유사도)
- ✅ Qdrant 벡터 스토어 동기화
- ✅ 배치 임베딩 처리
- ✅ 자동 복구 메커니즘
- ✅ 성능 최적화 (인덱스, WAL 모드)

### 🔶 Phase 4: 사용자 인터페이스 (부분 완료)
- ✅ AI CLI 메모리 명령어 (7개 옵션)
- ✅ 통계 정보 (`--memory-stats`)
- ❌ Desktop App 메모리 관리 UI (미구현)
- ❌ 시각화 대시보드 (미구현)
- ⚠️ 세부 설정 관리 (일부 미구현)

### 🔶 Phase 5: 고급 기능 (부분 완료)
- ⚠️ AI 요약 생성 (스키마만 존재, 로직 미구현)
- ⚠️ 중요 사실 자동 추출 (스키마만 존재)
- ✅ 백업/복원 시스템
- ✅ 데이터베이스 최적화 (VACUUM, ANALYZE)
- ✅ 동기화 재시도 메커니즘

### 🎯 운영 현황 (2025-10-08)
- **실사용 프로젝트**: 9개
- **안정성**: 권한 오류 자동 복구, 폴백 메커니즘 완비
- **성능**: FTS5 + 벡터 검색으로 대용량 대화 지원
- **확장성**: Docker/로컬 환경 자동 대응

## 🔧 실무적 고려사항

### 안전성
- 삭제 전 확인 시스템
- 백업 자동화
- 데이터 무결성 검사
- 롤백 기능

### 성능
- 인덱스 최적화
- 페이징 처리
- 캐싱 시스템
- 백그라운드 처리

### 관리성
- 로깅 시스템
- 오류 처리
- 설정 파일 관리
- 마이그레이션 지원

## 🎯 성공 지표

**기술적 목표:**
- 100만개 대화 처리 가능
- 1초 이내 검색 응답
- 99.9% 데이터 안정성

**사용성 목표:**
- 제로 설정 자동 동작
- 직관적인 명령어
- 명확한 피드백

## 📝 실제 구현 파일 구조

```
scripts/
├── memory_system.py          # 메모리 시스템 코어 (1359 라인)
│   ├── MemorySystem 클래스
│   ├── FTS5 + 벡터 검색
│   ├── Qdrant 동기화
│   └── 백업/복원 기능
├── memory_utils.py           # 유틸리티 함수
│   └── ensure_qdrant_collection()
└── ai.py                     # CLI 통합
    ├── 메모리 명령어 파싱 (668-674)
    └── 대화 저장 로직

/mnt/e/ai-data/memory/
├── projects/
│   └── {uuid}/
│       ├── memory.db         # SQLite DB
│       └── project.json      # 메타데이터
├── global/
└── backups/
```

## 🔄 향후 개선 방향

### 단기 개선 사항 (1-3개월)
1. **백그라운드 정리 스케줄러**: 자동 TTL 정리를 위한 cron/systemd 통합
2. **Desktop App UI**: 메모리 관리 탭 구현
3. **AI 요약 생성**: 주기적 대화 요약 자동 생성
4. **중요 사실 추출**: 키워드 기반 자동 추출 로직

### 중기 개선 사항 (3-6개월)
1. **태그 정규화 검토**: 검색 성능 이슈 발생 시 `conversation_tags` 테이블로 마이그레이션
2. **임베딩 최적화**: BLOB 저장으로 전환하여 저장 공간 절약
3. **PostgreSQL 마이그레이션**: 동시성 요구 증가 시 검토
4. **모니터링 대시보드**: Grafana 통합

### 장기 개선 사항 (6개월+)
1. **분산 벡터 검색**: 멀티 프로젝트 통합 검색
2. **AI 컨텍스트 자동 포함**: 질문 시 관련 이전 대화 자동 삽입
3. **메모리 압축**: 오래된 대화 요약 및 압축 저장
4. **클라우드 동기화**: 선택적 백업 동기화 기능

## 📚 관련 문서
- **구현 코드**: `scripts/memory_system.py`
- **CLI 통합**: `scripts/ai.py`
- **CLI 레퍼런스**: `docs/MEMORY_CLI_REFERENCE.md`
- **DB 스키마**: `docs/MEMORY_SCHEMA_DIAGRAM.md`
- **사용자 가이드**: `docs/MEMORY_SYSTEM_GUIDE.md`
- **테스트 결과**: `docs/MEMORY_SYSTEM_TEST_RESULTS.md`
- **ADR**: `docs/adr/adr-002-memory-system-impl-vs-plan.md`
