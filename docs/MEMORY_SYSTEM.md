# AI Memory System - 프로젝트별 장기 기억 시스템

## 개요

AI Memory System은 **프로젝트별로 무제한 대화를 저장**하고, **중요도 기반 자동 정리**, **빠른 검색**, **벡터 유사도 검색**을 제공하는 장기 기억 시스템입니다.

## 주요 기능

### ✅ 구현 완료 (100%)

- **프로젝트별 대화 저장** - SQLite 기반 프로젝트 격리 저장
- **중요도 자동 판정** - 1-10단계 자동 점수 계산
- **TTL 기반 자동 정리** - 중요도별 차등 보관 기간
- **빠른 전문 검색** - SQLite FTS5 전문 검색 (1초 내 응답)
- **벡터 유사도 검색** - Qdrant + FastEmbed (384차원)
- **하이브리드 검색** - FTS5 + 벡터 검색 결합
- **AI CLI 통합** - 자동 메모리 저장 및 검색 명령어
- **REST API** - OpenAI 호환 메모리 API (포트 8005)
- **자동 백업** - 일일 SQL/JSON 백업
- **Desktop App UI** - 메모리 검색/통계 UI

## 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                      AI CLI / Desktop App                    │
│                    (User Interface Layer)                    │
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
               ▼                              ▼
┌──────────────────────────┐    ┌────────────────────────────┐
│   Memory API Service     │    │  Memory Maintainer Service │
│   (REST API: 8005)       │    │  (Background Worker)       │
│   - Conversation CRUD    │    │  - TTL Cleanup (hourly)    │
│   - Search (FTS5/Vector) │    │  - Qdrant Sync (5min)      │
│   - Stats & Analytics    │    │  - Backup (daily 3AM)      │
└────────┬─────────────────┘    └────────────┬───────────────┘
         │                                   │
         ▼                                   ▼
┌─────────────────────────────────────────────────────────────┐
│                   Memory System Core                         │
│                  (scripts/memory_system.py)                  │
│  - SQLite Management (WAL mode, FTS5)                       │
│  - Project Isolation (UUID-based)                           │
│  - Importance Scoring Algorithm                             │
│  - Embedding Queue Management                               │
└──────────┬────────────────────────────────┬─────────────────┘
           │                                │
           ▼                                ▼
┌──────────────────────┐          ┌─────────────────────────┐
│  SQLite Databases    │          │  Qdrant Vector Store    │
│  /ai-data/memory/    │          │  (Port 6333)            │
│  projects/           │          │  - 384-dim vectors      │
│    {project-id}/     │          │  - Cosine similarity    │
│      memory.db       │◄─────────┤  - Collection per       │
│      (WAL + FTS5)    │   sync   │    project              │
└──────────────────────┘          └─────────────────────────┘
           │
           │ backup
           ▼
┌──────────────────────┐
│  Backup Storage      │
│  /ai-data/memory/    │
│  backups/            │
│    {project}_{time}  │
│      .sql / .json    │
└──────────────────────┘
```

## 데이터베이스 스키마

### conversations 테이블
```sql
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    user_query TEXT NOT NULL,
    ai_response TEXT NOT NULL,
    model_used VARCHAR(50),              -- chat-7b, code-7b
    importance_score INTEGER DEFAULT 5,  -- 1-10
    tags TEXT,                           -- JSON 배열
    session_id VARCHAR(50),
    token_count INTEGER,
    response_time_ms INTEGER,
    project_context TEXT,                -- JSON 메타데이터
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME                  -- TTL 기반 자동 삭제
)
```

### conversation_embeddings 테이블
```sql
CREATE TABLE conversation_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    embedding_vector TEXT,               -- JSON 형태 (로컬 폴백)
    qdrant_point_id TEXT,
    sync_status TEXT DEFAULT 'pending',  -- pending, synced, failed
    synced_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
)
```

### FTS5 전문 검색 테이블
```sql
CREATE VIRTUAL TABLE conversations_fts USING fts5(
    user_query,
    ai_response,
    content='conversations',
    content_rowid='id'
)
```

## 중요도 점수 시스템

### 점수 레벨 (1-10)

| 점수 | 레벨 | TTL | 설명 |
|------|------|-----|------|
| 10 | 영구보관 | 무제한 | 사용자 명시적 중요 표시 |
| 9 | 1년보관 | 365일 | 핵심 문서화, 아키텍처 결정 |
| 8 | 6개월 | 180일 | 중요 결정사항, 설계 패턴 |
| 7 | 3개월 | 90일 | 프로젝트 설정, 구성 정보 |
| 6 | 1개월 | 30일 | 코드 구현, 버그 수정 |
| 5 | 기본 | 30일 | 일반 대화 (기본값) |
| 4 | 2주 | 14일 | 정보성 질문 |
| 3 | 1주 | 7일 | 단순 대화 |
| 2 | 단기 | 3일 | 간단한 질문 |
| 1 | 즉시삭제 | 0일 | 인사, 테스트 메시지 |

### 자동 점수 계산 알고리즘

```python
def calculate_importance_score(user_query, ai_response, model_used, context):
    score = 5  # 기본값

    # 키워드 분석
    if contains_high_importance_keywords(query + response):
        score += min(keyword_count, 3)  # 최대 +3

    if contains_low_importance_keywords(query + response):
        score -= min(keyword_count, 2)  # 최대 -2

    # 응답 길이 (상세도 반영)
    if len(response) > 2000: score += 2
    elif len(response) > 1000: score += 1
    elif len(response) < 100: score -= 1

    # 코드 포함 여부
    if contains_code_block(response):
        score += 1

    # 모델 타입
    if model_used == "code-7b":
        score += 1  # 코딩 모델 사용시 중요도 증가

    # 사용자 피드백
    if context.get("user_saved"): score = 10
    elif context.get("user_important"): score = max(score, 8)

    # 질문 길이 (상세한 질문일수록 중요)
    if len(user_query) > 200: score += 1

    return max(1, min(10, score))  # 1-10 범위로 제한
```

## 사용 방법

### 1. AI CLI 명령어

```bash
# 기본 사용 (자동 메모리 저장)
ai "Python 함수 만들어줘"

# 메모리 상태 확인
ai --memory

# 메모리 검색
ai --memory-search "Python 함수"

# 메모리 통계
ai --memory-stats

# 만료된 대화 정리
ai --memory-cleanup

# 메모리 백업
ai --memory-backup

# 프로젝트 메모리 초기화
ai --memory-init

# 커스텀 메모리 디렉토리 사용
ai --memory-dir /custom/path --memory
```

### 2. Python API 사용

```python
from memory_system import MemorySystem

# 메모리 시스템 초기화
memory = MemorySystem()

# 프로젝트 ID 획득
project_id = memory.get_project_id()

# 대화 저장
conversation_id = memory.save_conversation(
    project_id=project_id,
    user_query="Python에서 파일 읽는 방법?",
    ai_response="open() 함수를 사용합니다...",
    model_used="chat-7b",
    session_id="session-123"
)

# 대화 검색 (FTS5)
results = memory.search_conversations(
    project_id=project_id,
    query="파일 읽기",
    importance_min=5,
    limit=10
)

# 벡터 검색 (하이브리드)
import asyncio
results = asyncio.run(
    memory.hybrid_search_conversations(
        project_id=project_id,
        query="Python 파일 처리",
        limit=10
    )
)

# 통계 조회
stats = memory.get_conversation_stats(project_id)
print(f"총 대화: {stats['total_conversations']}")
print(f"평균 중요도: {stats['avg_importance']}")

# TTL 정리
deleted = memory.cleanup_expired_conversations(project_id)
print(f"정리된 대화: {deleted}개")

# 벡터 동기화
sync_stats = memory.batch_sync_to_qdrant(project_id, batch_size=64)
print(f"동기화: {sync_stats['synced']}, 실패: {sync_stats['failed']}")
```

### 3. REST API 사용

```bash
# 대화 저장
curl -X POST http://localhost:8005/v1/memory/conversations \
  -H "Content-Type: application/json" \
  -d '{
    "user_query": "Python 함수 만들어줘",
    "ai_response": "def example()...",
    "model_used": "code-7b",
    "session_id": "session-123"
  }'

# 대화 검색
curl -X POST http://localhost:8005/v1/memory/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Python 함수",
    "use_vector": true,
    "importance_min": 5,
    "limit": 10
  }'

# 통계 조회
curl http://localhost:8005/v1/memory/stats

# 만료된 대화 정리
curl -X POST http://localhost:8005/v1/memory/cleanup

# 벡터 동기화
curl -X POST http://localhost:8005/v1/memory/sync-vectors?batch_size=64

# 헬스체크
curl http://localhost:8005/health
```

### 4. Desktop App 사용

1. **Memory Client 초기화**
```javascript
// memory-client.js 로드
const memoryClient = new MemoryClient();

// 메모리 서비스 상태 확인
await memoryClient.checkMemoryService();
```

2. **대화 자동 저장**
```javascript
// AI 응답 후 자동 저장
await memoryClient.saveConversation(
    userQuery,
    aiResponse,
    modelUsed,
    sessionId,
    responseTimeMs,
    tokenCount
);
```

3. **메모리 검색 UI**
```javascript
// 검색 UI 표시
await memoryClient.showMemorySearchUI();

// 검색 실행
const results = await memoryClient.searchConversations(
    "검색어",
    useVector = true,
    importanceMin = 5,
    limit = 20
);
```

4. **메모리 통계 UI**
```javascript
// 통계 UI 표시
await memoryClient.showMemoryStatsUI();
```

## 서비스 관리

### Docker Compose 시작

```bash
# 전체 스택 시작 (메모리 포함)
docker compose -f docker/compose.p3.yml up -d

# 메모리 서비스만 재시작
docker compose -f docker/compose.p3.yml restart memory-api memory-maintainer

# 로그 확인
docker compose -f docker/compose.p3.yml logs -f memory-api
docker compose -f docker/compose.p3.yml logs -f memory-maintainer
```

### 서비스 헬스체크

```bash
# Memory API
curl http://localhost:8005/health

# Qdrant
curl http://localhost:6333/

# Embedding Service
curl http://localhost:8003/health
```

### 백그라운드 작업 모니터링

```bash
# Memory Maintainer 로그
tail -f /mnt/e/ai-data/memory/logs/memory_maintainer.log

# 백업 디렉토리 확인
ls -lh /mnt/e/ai-data/memory/backups/
```

## 성능 최적화

### SQLite 최적화 설정

```python
# WAL 모드 (동시성 향상)
PRAGMA journal_mode=WAL;

# 동기화 모드 (성능 우선)
PRAGMA synchronous=NORMAL;

# 캐시 크기 (10MB)
PRAGMA cache_size=10000;

# 외래 키 활성화
PRAGMA foreign_keys=ON;
```

### 인덱스 전략

```sql
-- 타임스탬프 조회
CREATE INDEX idx_conversations_timestamp ON conversations(timestamp);

-- 중요도 필터
CREATE INDEX idx_conversations_importance ON conversations(importance_score);

-- TTL 정리
CREATE INDEX idx_conversations_expires_at ON conversations(expires_at);

-- 세션 추적
CREATE INDEX idx_conversations_session_id ON conversations(session_id);

-- 모델별 조회
CREATE INDEX idx_conversations_model_used ON conversations(model_used);

-- 벡터 동기화 상태
CREATE INDEX idx_conversation_embeddings_sync_status ON conversation_embeddings(sync_status);
```

### 벡터 검색 최적화

```python
# 배치 임베딩 생성 (64개 단위)
embeddings = await get_embeddings_batch(texts, batch_size=64)

# Qdrant 배치 업로드
qdrant.upsert(collection_name, points=batch_points)

# 하이브리드 검색 (FTS5 + 벡터)
results = await hybrid_search(query, limit=10)
```

## 성능 목표 달성 현황

| 목표 | 상태 | 실측치 |
|------|------|--------|
| 100만개 대화 처리 | ✅ 달성 | SQLite WAL + 인덱스 최적화 |
| 1초 이내 검색 응답 | ✅ 달성 | FTS5 BM25 알고리즘 |
| 벡터 검색 지원 | ✅ 달성 | Qdrant + FastEmbed 384차원 |
| 자동 정리 스케줄러 | ✅ 달성 | 1시간마다 TTL 정리 |
| 일일 자동 백업 | ✅ 달성 | 새벽 3시 SQL/JSON 백업 |

## 환경 변수

```bash
# Memory API Service
AI_MEMORY_DIR=/mnt/e/ai-data/memory
MEMORY_SERVICE_PORT=8005
QDRANT_URL=http://qdrant:6333
EMBEDDING_URL=http://embedding:8003
DEFAULT_PROJECT_ID=default-project

# Memory Maintainer
MEMORY_BACKUP_CRON=03:00           # 백업 시간 (HH:MM)
MEMORY_SYNC_INTERVAL=300           # Qdrant 동기화 간격 (초)
TTL_CHECK_INTERVAL=3600            # TTL 정리 간격 (초)
```

## 트러블슈팅

### 메모리 서비스 연결 실패

```bash
# 서비스 상태 확인
docker compose -f docker/compose.p3.yml ps

# 로그 확인
docker compose -f docker/compose.p3.yml logs memory-api

# 수동 헬스체크
curl http://localhost:8005/health
```

### 벡터 검색 비활성화

```bash
# Qdrant 상태 확인
curl http://localhost:6333/

# 수동 벡터 복구
python3 -c "
from memory_system import get_memory_system
m = get_memory_system()
m.try_vector_recovery()
"
```

### 데이터베이스 최적화

```bash
# Python에서 최적화 실행
python3 -c "
from memory_system import get_memory_system
m = get_memory_system()
project_id = m.get_project_id()
m.optimize_database(project_id)
"

# 또는 REST API 사용
curl -X POST http://localhost:8005/v1/memory/optimize
```

### 백업 복원

```bash
# SQL 백업에서 복원
sqlite3 /mnt/e/ai-data/memory/projects/{project-id}/memory.db < backup.sql

# JSON 백업에서 복원 (Python)
python3 -c "
from memory_system import get_memory_system
from pathlib import Path
m = get_memory_system()
project_id = m.get_project_id()
m.import_memory_backup(project_id, Path('backup.json'))
"
```

## 보안 고려사항

### 데이터 프라이버시

- **로컬 저장**: 모든 데이터는 `/mnt/e/ai-data/memory`에 로컬 저장
- **프로젝트 격리**: UUID 기반 프로젝트별 데이터베이스 분리
- **암호화 없음**: SQLite 데이터베이스는 암호화되지 않음 (필요시 OS 레벨 암호화 사용)

### 접근 제어

- **포트 제한**: Memory API는 localhost(8005)에만 바인딩
- **인증 없음**: 현재 버전은 인증/인가 없음 (로컬 개발 환경 전용)
- **프로덕션 배포 시**: 반드시 인증 레이어 추가 필요

### 데이터 정리

- **TTL 기반 자동 삭제**: 중요도에 따라 자동 정리
- **수동 백업**: 중요 데이터는 별도 백업 권장
- **완전 삭제**: SQLite VACUUM으로 디스크 공간 회수

## 향후 개선 계획

### Phase 6: 고급 기능 (예정)

- [ ] **요약 생성**: 대화 세션 자동 요약
- [ ] **태그 자동 추출**: NER 기반 자동 태깅
- [ ] **관련 대화 추천**: 벡터 유사도 기반 추천
- [ ] **대화 스레드 추적**: 연관 대화 그룹화
- [ ] **사용자 선호도 학습**: 개인화된 중요도 판정

### Phase 7: 프로덕션 준비 (예정)

- [ ] **인증/인가**: JWT 기반 사용자 인증
- [ ] **멀티테넌시**: 사용자별 프로젝트 관리
- [ ] **암호화**: 민감 데이터 암호화
- [ ] **감사 로그**: 모든 작업 로깅
- [ ] **백업 암호화**: 백업 파일 암호화

## 참고 문서

- [Memory System Architecture](./progress/v1/ri_3.md)
- [SQLite FTS5 Documentation](https://www.sqlite.org/fts5.html)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [FastEmbed Documentation](https://github.com/qdrant/fastembed)

## 기여

Issue #5 구현: @sunbangamen
버전: 1.0.0
날짜: 2025-09-30