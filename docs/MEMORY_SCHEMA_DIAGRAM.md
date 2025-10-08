# Memory System Database Schema

> **현재 구현**: `scripts/memory_system.py:236-357`
> **버전**: v1.0 (2025-10-08)
> **실사용**: 9개 프로젝트 운영 중

## 📊 Entity Relationship Diagram

```
┌────────────────────────────────────────────────────────────────────┐
│                         conversations                              │
├────────────────────────────────────────────────────────────────────┤
│ PK  id                    INTEGER                                  │
│     timestamp             DATETIME                                 │
│     user_query            TEXT                                     │
│     ai_response           TEXT                                     │
│     model_used            VARCHAR(50)                              │
│     importance_score      INTEGER (1-10)                           │
│     tags                  TEXT (JSON array) ⚠️                     │
│     session_id            VARCHAR(50)                              │
│     token_count           INTEGER                                  │
│     response_time_ms      INTEGER                                  │
│     project_context       TEXT (JSON)                              │
│     created_at            DATETIME                                 │
│     updated_at            DATETIME                                 │
│     expires_at            DATETIME (TTL)                           │
└────────────────────────────────────────────────────────────────────┘
                                   │
                                   │ 1:1
                                   ├─────────────────────────────────┐
                                   │                                 │
                    1:N            ▼                                 ▼
┌──────────────────────────────────────────────┐   ┌──────────────────────────────────────┐
│        conversation_embeddings               │   │      important_facts                 │
├──────────────────────────────────────────────┤   ├──────────────────────────────────────┤
│ PK  id                   INTEGER             │   │ PK  id                   INTEGER     │
│ FK  conversation_id      INTEGER (UNIQUE)    │   │     fact                 TEXT        │
│     embedding_vector     TEXT (JSON) ⚠️      │   │     category             VARCHAR(100)│
│     qdrant_point_id      TEXT ⚠️             │   │ FK  source_conversation_id INTEGER   │
│     sync_status          TEXT                │   │     user_marked          BOOLEAN     │
│     synced_at            DATETIME            │   │     ai_suggested         BOOLEAN     │
│     created_at           DATETIME            │   │     created_at           DATETIME    │
└──────────────────────────────────────────────┘   └──────────────────────────────────────┘
                                                             │
                                                             │ FK
                                                             └──────┐
                                                                    │
                                                                    ▼
                                                    [conversations.id]


┌────────────────────────────────────────────┐   ┌──────────────────────────────────────┐
│      conversation_summaries                │   │       user_preferences               │
├────────────────────────────────────────────┤   ├──────────────────────────────────────┤
│ PK  id                   INTEGER           │   │ PK  key                  VARCHAR(100)│
│     date_range           TEXT              │   │     value                TEXT        │
│     summary              TEXT              │   │     updated_at           DATETIME    │
│     conversation_count   INTEGER           │   └──────────────────────────────────────┘
│     importance_level     INTEGER           │
│     created_at           DATETIME          │
└────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│              conversations_fts (FTS5 Virtual Table)                │
├────────────────────────────────────────────────────────────────────┤
│     rowid                INTEGER (→ conversations.id)              │
│     user_query           TEXT (indexed)                            │
│     ai_response          TEXT (indexed)                            │
│                                                                    │
│  Auto-synced via triggers:                                        │
│   - conversations_ai_insert (AFTER INSERT)                        │
│   - conversations_ai_update (AFTER UPDATE)                        │
│   - conversations_ai_delete (AFTER DELETE)                        │
└────────────────────────────────────────────────────────────────────┘
```

---

## 🔍 Table Details

### 1. `conversations` (핵심 대화 테이블)

**용도**: 모든 AI 대화 기록 저장

**주요 필드:**
| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| `id` | INTEGER | 기본키 (자동 증가) | |
| `timestamp` | DATETIME | 대화 시각 | 자동 생성 |
| `user_query` | TEXT | 사용자 질문 | NOT NULL |
| `ai_response` | TEXT | AI 응답 | NOT NULL |
| `model_used` | VARCHAR(50) | 사용된 모델 | `chat-7b`, `code-7b` |
| `importance_score` | INTEGER | 중요도 (1-10) | 기본값: 5 |
| `tags` | TEXT | 태그 배열 | **JSON 형태** ⚠️ |
| `session_id` | VARCHAR(50) | 세션 식별자 | 대화 그룹핑용 |
| `token_count` | INTEGER | 토큰 수 | 통계용 |
| `response_time_ms` | INTEGER | 응답 시간 (ms) | 성능 모니터링 |
| `project_context` | TEXT | 프로젝트 컨텍스트 | JSON 형태 |
| `expires_at` | DATETIME | 만료 시각 | TTL 기반 삭제 |

**인덱스:**
- `idx_conversations_timestamp` (검색 성능)
- `idx_conversations_importance` (중요도 필터)
- `idx_conversations_expires_at` (TTL 정리)
- `idx_conversations_session_id` (세션 추적)
- `idx_conversations_model_used` (모델 통계)

**예제 데이터:**
```sql
INSERT INTO conversations (
    user_query, ai_response, model_used, importance_score,
    tags, session_id, token_count, response_time_ms,
    project_context, expires_at
) VALUES (
    'Docker Compose 설정 방법',
    'Docker Compose는 여러 컨테이너를...',
    'chat-7b',
    7,
    '["docker", "devops", "configuration"]',
    'session-abc123',
    512,
    1200,
    '{"project_name": "local-ai-suite", "branch": "main"}',
    '2026-01-08 10:00:00'
);
```

---

### 2. `conversation_embeddings` (벡터 임베딩)

**용도**: Qdrant 동기화 및 로컬 폴백 벡터 저장

**주요 필드:**
| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| `id` | INTEGER | 기본키 | |
| `conversation_id` | INTEGER | 외래키 (UNIQUE) | 1:1 관계 |
| `embedding_vector` | TEXT | 임베딩 벡터 | **JSON 형태** ⚠️ |
| `qdrant_point_id` | TEXT | Qdrant 포인트 ID | `conversation_id`와 동일 |
| `sync_status` | TEXT | 동기화 상태 | `pending`, `synced`, `failed` |
| `synced_at` | DATETIME | 동기화 완료 시각 | |

**동기화 워크플로우:**
```
[대화 저장]
    ↓
[conversation_embeddings INSERT]
    sync_status = 'pending'
    ↓
[배치 임베딩 생성]
    FastEmbed API 호출 (http://localhost:8003)
    ↓
[Qdrant 업로드]
    collection: memory_{project_id[:8]}
    ↓
[상태 업데이트]
    sync_status = 'synced'
    synced_at = NOW()
```

**인덱스:**
- `idx_conversation_embeddings_sync_status` (동기화 큐 관리)

**예제 데이터:**
```sql
INSERT INTO conversation_embeddings (
    conversation_id, embedding_vector, qdrant_point_id, sync_status
) VALUES (
    123,
    '[0.123, -0.456, 0.789, ...]',  -- 384차원 벡터 (JSON)
    '123',
    'synced'
);
```

---

### 3. `conversation_summaries` (AI 생성 요약)

**용도**: 주기적 대화 요약 저장 (미래 기능)

**상태**: ⚠️ 스키마만 존재, 로직 미구현

**주요 필드:**
| Field | Type | Description |
|-------|------|-------------|
| `id` | INTEGER | 기본키 |
| `date_range` | TEXT | 요약 기간 (예: "2024-09-01 to 2024-09-07") |
| `summary` | TEXT | AI 생성 요약 |
| `conversation_count` | INTEGER | 요약된 대화 수 |
| `importance_level` | INTEGER | 요약의 중요도 |

**계획된 사용 사례:**
- 주간/월간 프로젝트 진행 요약
- 중요 결정사항 자동 추출
- 대화 압축 (긴 프로젝트 히스토리)

---

### 4. `important_facts` (중요 사실)

**용도**: 프로젝트별 중요 사실 수동/자동 추출

**상태**: ⚠️ 스키마만 존재, 로직 미구현

**주요 필드:**
| Field | Type | Description |
|-------|------|-------------|
| `id` | INTEGER | 기본키 |
| `fact` | TEXT | 중요 사실 내용 |
| `category` | VARCHAR(100) | 카테고리 (code, config, decision 등) |
| `source_conversation_id` | INTEGER | 출처 대화 (외래키) |
| `user_marked` | BOOLEAN | 사용자 수동 표시 여부 |
| `ai_suggested` | BOOLEAN | AI 자동 추출 여부 |

**인덱스:**
- `idx_important_facts_category` (카테고리 필터)

---

### 5. `user_preferences` (사용자 선호도)

**용도**: 프로젝트별 사용자 설정 저장

**주요 필드:**
| Field | Type | Description |
|-------|------|-------------|
| `key` | VARCHAR(100) | 설정 키 (기본키) |
| `value` | TEXT | 설정 값 (JSON 지원) |
| `updated_at` | DATETIME | 최종 수정 시각 |

**예제 사용:**
```sql
INSERT INTO user_preferences (key, value) VALUES
    ('default_importance', '6'),
    ('auto_cleanup_enabled', 'true'),
    ('retention_days', '90'),
    ('preferred_model', 'code-7b');
```

---

### 6. `conversations_fts` (FTS5 전문 검색)

**타입**: Virtual Table (SQLite FTS5)

**용도**: 빠른 키워드 기반 전문 검색

**주요 필드:**
| Field | Type | Description |
|-------|------|-------------|
| `rowid` | INTEGER | conversations.id 참조 |
| `user_query` | TEXT | 인덱스된 질문 텍스트 |
| `ai_response` | TEXT | 인덱스된 응답 텍스트 |

**검색 알고리즘**: BM25 (Best Matching 25)

**자동 동기화 트리거:**
```sql
-- INSERT 시
CREATE TRIGGER conversations_ai_insert AFTER INSERT ON conversations
BEGIN
    INSERT INTO conversations_fts(rowid, user_query, ai_response)
    VALUES (NEW.id, NEW.user_query, NEW.ai_response);
END;

-- UPDATE 시
CREATE TRIGGER conversations_ai_update AFTER UPDATE ON conversations
BEGIN
    UPDATE conversations_fts SET
        user_query = NEW.user_query,
        ai_response = NEW.ai_response
    WHERE rowid = NEW.id;
END;

-- DELETE 시
CREATE TRIGGER conversations_ai_delete AFTER DELETE ON conversations
BEGIN
    DELETE FROM conversations_fts WHERE rowid = OLD.id;
END;
```

**검색 예시:**
```sql
-- 기본 검색
SELECT c.* FROM conversations c
JOIN conversations_fts fts ON c.id = fts.rowid
WHERE conversations_fts MATCH 'Docker AND config'
ORDER BY bm25(conversations_fts);

-- 중요도 가중치 적용
SELECT c.*,
       bm25(conversations_fts) as relevance,
       (bm25(conversations_fts) + c.importance_score * 0.1) as combined_score
FROM conversations c
JOIN conversations_fts fts ON c.id = fts.rowid
WHERE conversations_fts MATCH 'Docker'
ORDER BY combined_score DESC;
```

---

## 🔑 Key Design Decisions

### 1. Tags as JSON (Not Normalized)

**선택**: `conversations.tags TEXT` (JSON 배열)

**이유**:
- 단순한 스키마 (JOIN 불필요)
- 대화당 평균 3-5개 태그로 정규화 불필요
- SQLite의 `json_each()` 함수로 충분히 쿼리 가능
- 실사용 환경에서 성능 이슈 미발생

**예제 쿼리**:
```sql
-- 특정 태그 검색
SELECT * FROM conversations
WHERE json_each(tags) IN ('docker', 'devops');

-- 태그 통계
SELECT json_each.value as tag, COUNT(*) as count
FROM conversations, json_each(conversations.tags)
GROUP BY tag
ORDER BY count DESC;
```

---

### 2. Embeddings as JSON (Not BLOB)

**선택**: `embedding_vector TEXT` (JSON 배열)

**이유**:
- 디버깅 및 검증 용이 (가독성)
- 벡터 차원 변경 시 스키마 변경 불필요
- Qdrant를 주요 벡터 검색에 사용하므로 SQLite는 백업용

**저장 공간 비교** (384차원 기준):
- BLOB (float32): ~1.5 KB
- JSON: ~4-6 KB
- 트레이드오프: 3-4배 공간 사용, 가시성 확보

---

### 3. 1:1 Relationship (Conversations ↔ Embeddings)

**선택**: `UNIQUE(conversation_id)`

**이유**:
- 하나의 대화는 하나의 임베딩만 가짐
- 동일 대화 재처리 방지
- 동기화 상태 추적 단순화

---

### 4. TTL via `expires_at` (Not Scheduled Jobs)

**선택**: `expires_at DATETIME` + 수동 정리

**이유**:
- 스케줄러 없이 단순하게 구현
- 사용자 제어 가능 (`ai --memory-cleanup`)
- cron/systemd 등 외부 스케줄러 활용 가능

**자동화 예시**:
```bash
# crontab -e
0 3 * * * cd /project && ai --memory-cleanup
```

---

## 📈 Performance Characteristics

### 검색 성능 (1000개 대화 기준)

| 검색 방식 | 평균 응답 시간 | 사용 사례 |
|----------|----------------|-----------|
| FTS5 키워드 | 50-80ms | 정확한 키워드 매칭 |
| 벡터 유사도 (Qdrant) | 120-150ms | 의미적 유사성 |
| 하이브리드 | 180-220ms | 최고 정확도 |
| Importance 필터 | +10-20ms | 중요 대화만 검색 |

### 저장 공간

**프로젝트당 평균**:
- 대화 500개 기준: ~5 MB
- 대화당 평균: ~10 KB
  - 텍스트: ~4 KB
  - 임베딩 JSON: ~5 KB
  - 메타데이터: ~1 KB

### 인덱스 효율성

```sql
-- 인덱스 사용 통계 확인
PRAGMA index_list(conversations);
PRAGMA index_info(idx_conversations_timestamp);

-- 쿼리 플랜 확인
EXPLAIN QUERY PLAN
SELECT * FROM conversations
WHERE importance_score >= 7
ORDER BY timestamp DESC
LIMIT 10;
```

---

## 🔄 Migration Paths

### 향후 정규화 시나리오

**트리거 조건**: 대화 수 10만 건 초과 또는 태그 검색 >500ms

**마이그레이션 스크립트**:
```sql
-- 1. 새 테이블 생성
CREATE TABLE conversation_tags (
    conversation_id INTEGER NOT NULL,
    tag TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (conversation_id, tag),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- 2. 데이터 마이그레이션
INSERT INTO conversation_tags (conversation_id, tag)
SELECT c.id, json_each.value
FROM conversations c, json_each(c.tags)
WHERE c.tags IS NOT NULL;

-- 3. 인덱스 생성
CREATE INDEX idx_conversation_tags_tag ON conversation_tags(tag);

-- 4. 기존 컬럼 제거 (선택적)
-- ALTER TABLE conversations DROP COLUMN tags;  -- SQLite 3.35.0+
```

---

### BLOB 임베딩 전환

**트리거 조건**: 프로젝트당 저장 공간 >100MB

**마이그레이션**:
```python
import json
import struct
import sqlite3

def migrate_to_blob(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT id, embedding_vector FROM conversation_embeddings")

    for row in cursor:
        embedding_id, json_vector = row
        vector = json.loads(json_vector)
        blob = struct.pack(f'{len(vector)}f', *vector)

        conn.execute(
            "UPDATE conversation_embeddings SET embedding_vector = ? WHERE id = ?",
            (blob, embedding_id)
        )

    conn.commit()
```

---

## 📚 Related Documentation

- **Implementation**: `scripts/memory_system.py:236-357`
- **Planning**: `memory_system_plan.md`
- **ADR**: `docs/adr/adr-002-memory-system-impl-vs-plan.md`
- **CLI Reference**: `docs/MEMORY_CLI_REFERENCE.md`
- **User Guide**: `docs/MEMORY_SYSTEM_GUIDE.md`

---

## 🔧 Schema Verification

### 스키마 검증 스크립트

```bash
# SQLite 버전 확인
sqlite3 --version

# 테이블 목록
sqlite3 /path/to/memory.db ".tables"

# 전체 스키마 확인
sqlite3 /path/to/memory.db ".schema"

# 특정 테이블 스키마
sqlite3 /path/to/memory.db ".schema conversations"

# 인덱스 확인
sqlite3 /path/to/memory.db "SELECT name, sql FROM sqlite_master WHERE type='index';"

# 데이터 통계
sqlite3 /path/to/memory.db "
SELECT
    'conversations' as table_name,
    COUNT(*) as row_count,
    SUM(LENGTH(user_query) + LENGTH(ai_response)) as total_size
FROM conversations
UNION ALL
SELECT
    'conversation_embeddings',
    COUNT(*),
    SUM(LENGTH(embedding_vector))
FROM conversation_embeddings;
"
```

---

**Last Updated**: 2025-10-08
**Schema Version**: 1.0
**Operational Status**: ✅ 9 projects in production
