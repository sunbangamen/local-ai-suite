# Memory System CLI Reference

> **현재 구현 버전**: v1.0 (2025-10-08)
> **실사용 현황**: 9개 프로젝트에서 안정적으로 운영 중

## 📚 Overview

메모리 시스템은 AI 대화를 프로젝트별로 저장하고 검색하는 장기 기억 기능을 제공합니다.

**주요 기능:**
- 프로젝트별 독립적인 SQLite 데이터베이스
- FTS5 전문 검색 + Qdrant 벡터 검색
- 중요도 기반 자동 TTL 관리 (1-10 레벨)
- JSON 백업/복원 기능
- Docker/로컬 환경 자동 대응

---

## 🎯 CLI Commands

### 1. `--memory`
**메모리 시스템 상태 표시**

```bash
ai --memory
```

**출력 예시:**
```
🧠 Memory System Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Project ID:    13d57514-64fa-4c02-9e44-830632a9d09d
Data Dir:      /mnt/e/ai-data/memory
Storage:       ✅ Available
Vector Search: ✅ Enabled (Qdrant)

📊 Statistics:
  Total Conversations: 347
  Avg Importance:      5.2
  Oldest:             2025-09-15 10:23:45
  Latest:             2025-10-08 14:30:12

💾 Storage:
  Database Size:  2.3 MB
  Embeddings:     285 synced, 12 pending
```

**용도**: 현재 프로젝트의 메모리 상태 및 통계 확인

---

### 2. `--memory-init`
**프로젝트 메모리 초기화**

```bash
ai --memory-init
```

**동작:**
1. 현재 디렉토리의 Git 루트를 프로젝트로 인식
2. `.ai-memory/project.json`에 UUID 생성 및 저장
3. SQLite 데이터베이스 스키마 생성
4. 인덱스 및 FTS5 테이블 초기화

**출력 예시:**
```
✅ Memory system initialized
Project ID: 13d57514-64fa-4c02-9e44-830632a9d09d
Database:   /mnt/e/ai-data/memory/projects/13d57514-64fa-4c02-9e44-830632a9d09d/memory.db
```

**주의사항:**
- 기존 프로젝트에서 실행해도 안전 (멱등성 보장)
- Docker 환경에서는 `docker-default` 프로젝트 자동 사용

---

### 3. `--memory-search <query>`
**대화 검색 (FTS5 기반)**

```bash
ai --memory-search "Docker 설정"
ai --memory-search "Python 함수"
```

**검색 방식:**
- FTS5 전문 검색 (BM25 랭킹)
- 중요도 가중치 적용 (`bm25 + importance_score * 0.1`)
- 최대 10개 결과 반환

**출력 예시:**
```
🔍 Search Results for "Docker 설정"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[1] 2025-10-05 14:23:11 (Importance: 7) 📌
Q: Docker Compose에서 환경변수를 어떻게 설정하나요?
A: Docker Compose에서 환경변수는 3가지 방법으로 설정할 수 있습니다...
   (Relevance: 0.87)

[2] 2025-10-03 09:15:44 (Importance: 6)
Q: Docker 볼륨 마운트 설정 방법
A: 볼륨 마운트는 `volumes:` 섹션에서...
   (Relevance: 0.72)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Found 2 results in 45ms
```

**옵션:**
```bash
# 중요도 필터링
ai --memory-search "Docker" --importance-min 7

# 벡터 검색 (Qdrant 사용)
ai --memory-search "Docker" --vector
```

---

### 4. `--memory-cleanup`
**만료된 대화 정리 (TTL 기반)**

```bash
ai --memory-cleanup
```

**동작:**
1. `expires_at < NOW()` 조건으로 만료 대화 검색
2. 고아 임베딩 정리 (`conversation_embeddings` 외래키 체크)
3. FTS5 인덱스 자동 동기화

**출력 예시:**
```
🗑️ Cleaning up expired conversations...

Deleted Conversations:
  Importance 1 (즉시삭제):  12개
  Importance 2 (3일 보관):   8개
  Importance 3 (1주 보관):   5개

✅ Total deleted: 25 conversations
🧹 Orphaned embeddings removed: 3
```

**TTL 기준:**
| Importance | TTL | 설명 |
|------------|-----|------|
| 1 | 즉시 | 인사, 테스트 |
| 2 | 3일 | 간단한 질문 |
| 3 | 7일 | 일반 대화 |
| 4 | 14일 | 정보성 질문 |
| 5 | 30일 | 기본값 |
| 6 | 30일 | 코드 관련 |
| 7 | 90일 | 프로젝트 설정 |
| 8 | 180일 | 중요 결정사항 |
| 9 | 365일 | 핵심 문서화 |
| 10 | 영구 | 사용자 중요표시 |

**자동화 권장:**
```bash
# crontab 등록 (매일 새벽 3시)
0 3 * * * cd /your/project && ai --memory-cleanup >> /var/log/ai-cleanup.log 2>&1
```

---

### 5. `--memory-backup [PATH]`
**JSON 백업 생성**

```bash
# 기본 경로에 타임스탬프 백업 생성
ai --memory-backup

# 특정 경로에 백업
ai --memory-backup /path/to/backup.json
```

**백업 포함 데이터:**
- `conversations`: 모든 대화 기록
- `conversation_embeddings`: 임베딩 벡터 (JSON)
- `conversation_summaries`: AI 생성 요약
- `important_facts`: 중요 사실
- `user_preferences`: 사용자 선호도

**출력 예시:**
```
💾 Backing up memory...

Backup Created:
  Path:     /mnt/e/ai-data/memory/backups/memory_13d57514_20251008_143012.json
  Size:     3.2 MB
  Items:    347 conversations, 285 embeddings

✅ Backup completed successfully
```

**복원 방법:**
```bash
# Python 스크립트로 직접 복원
python3 -c "
from scripts.memory_system import get_memory_system
mem = get_memory_system()
mem.import_memory_backup('project_id', '/path/to/backup.json')
"
```

---

### 6. `--memory-stats`
**상세 통계 정보**

```bash
ai --memory-stats
```

**출력 예시:**
```
📊 Memory System Statistics
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 Overall Stats:
  Total Conversations:  347
  Avg Importance:       5.2
  Oldest Conversation:  2025-09-15 10:23:45
  Latest Conversation:  2025-10-08 14:30:12

🎯 Importance Distribution:
  Level 1-3 (단기):     15 (4.3%)
  Level 4-6 (중기):    210 (60.5%)
  Level 7-9 (장기):    120 (34.6%)
  Level 10 (영구):       2 (0.6%)

🤖 Model Usage:
  chat-7b:  180 (51.9%)
  code-7b:  167 (48.1%)

💾 Storage:
  Database Size:  2.3 MB
  Avg per Conv:   6.8 KB

🔄 Sync Status:
  Synced:    285 (82.1%)
  Pending:    12 (3.5%)
  Failed:      0 (0.0%)
  No Vector:  50 (14.4%)
```

---

### 7. `--memory-dir <path>`
**메모리 저장 경로 오버라이드**

```bash
# 임시 메모리 디렉토리 사용
ai --memory-dir /tmp/test-memory "Hello"

# 테스트 격리 환경
ai --memory-dir ./test-data --memory-init
```

**용도:**
- 테스트/개발 시 격리된 메모리 공간
- CI/CD 환경에서 독립적인 실행
- 디버깅 시 재현 환경 구축

**우선순위:**
```
1. --memory-dir (CLI 옵션)      ← 최우선
2. AI_MEMORY_DIR (환경변수)
3. /mnt/e/ai-data/memory (기본)
4. {project_root}/.ai-memory-data
5. {cwd}/.ai-memory-data
```

---

## 🔧 Environment Variables

### `AI_MEMORY_DIR`
메모리 데이터 저장 디렉토리

```bash
export AI_MEMORY_DIR=/custom/path/memory
ai --memory
```

**기본값**: `/mnt/e/ai-data/memory`

---

### `DEFAULT_PROJECT_ID`
Docker 환경에서 프로젝트 ID 강제 지정

```bash
# docker-compose.yml
environment:
  - DEFAULT_PROJECT_ID=docker-default
```

**동작**: 프로젝트별 UUID 생성을 건너뛰고 지정된 ID 사용

---

### `EMBEDDING_URL`
임베딩 서비스 URL (FastEmbed)

```bash
export EMBEDDING_URL=http://localhost:8003
```

**기본값**: `http://localhost:8003`

---

### `QDRANT_URL`
Qdrant 벡터 데이터베이스 URL

```bash
export QDRANT_URL=http://localhost:6333
```

**기본값**: `http://localhost:6333`

---

## 📊 Usage Examples

### 기본 사용 패턴
```bash
# 1. 프로젝트 초기화 (첫 사용 시)
ai --memory-init

# 2. 일반 대화 (자동으로 메모리에 저장됨)
ai "Docker Compose 설정 방법 알려줘"

# 3. 이전 대화 검색
ai --memory-search "Docker"

# 4. 주기적인 정리
ai --memory-cleanup

# 5. 백업 (중요 작업 전)
ai --memory-backup
```

---

### 고급 사용 사례

#### 1. 테스트 격리 환경
```bash
# 테스트용 임시 메모리 생성
mkdir -p /tmp/test-memory
ai --memory-dir /tmp/test-memory --memory-init

# 테스트 실행
ai --memory-dir /tmp/test-memory "Test query"

# 정리
rm -rf /tmp/test-memory
```

#### 2. CI/CD 통합
```yaml
# .github/workflows/test.yml
- name: AI Memory Test
  run: |
    export AI_MEMORY_DIR=${{ github.workspace }}/.test-memory
    ai --memory-init
    ai "Run tests"
    ai --memory-stats
```

#### 3. 백업 자동화
```bash
#!/bin/bash
# backup-memory.sh

DATE=$(date +%Y%m%d)
BACKUP_PATH="/backups/memory-$DATE.json"

ai --memory-backup "$BACKUP_PATH"

# S3 업로드 (선택)
aws s3 cp "$BACKUP_PATH" s3://my-bucket/memory-backups/
```

#### 4. 통계 모니터링
```bash
# stats-monitor.sh
while true; do
  echo "=== $(date) ==="
  ai --memory-stats | grep "Total Conversations"
  sleep 3600  # 1시간마다
done
```

---

## 🚨 Troubleshooting

### 권한 오류
```
⚠️ Warning: Cannot create memory directories: Permission denied
💡 Memory system will be disabled for this session.
```

**해결 방법:**
```bash
# 디렉토리 권한 확인
ls -ld /mnt/e/ai-data/memory

# 권한 수정
sudo chown -R $USER:$USER /mnt/e/ai-data/memory

# 또는 로컬 폴백 사용
export AI_MEMORY_DIR=$HOME/.ai-memory
```

---

### 벡터 검색 비활성화
```
💡 Vector search dependencies not available. Text search only.
```

**원인**: `httpx`, `qdrant-client` 미설치

**해결 방법:**
```bash
pip install httpx qdrant-client
```

---

### Qdrant 연결 실패
```
⚠️ Qdrant connection failed: Connection refused
💡 Vector search will be disabled for this session.
```

**해결 방법:**
```bash
# Qdrant 서비스 확인
curl http://localhost:6333/collections

# Docker Compose로 시작
docker compose -f docker/compose.p3.yml up -d qdrant

# 연결 테스트
ai --memory  # Vector Search: ✅ Enabled 확인
```

---

### 검색 결과 없음
```
🔍 Search Results for "query"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
No results found.
```

**체크리스트:**
1. 대화가 저장되었는지 확인: `ai --memory-stats`
2. FTS5 인덱스 재구축:
   ```python
   from scripts.memory_system import get_memory_system
   mem = get_memory_system()
   mem.rebuild_fts_index('project_id')
   ```
3. 검색어 변경 (동의어, 유사어 시도)

---

## 📚 Related Documentation

- **Implementation**: `scripts/memory_system.py`
- **Planning**: `memory_system_plan.md`
- **ADR**: `docs/adr/adr-002-memory-system-impl-vs-plan.md`
- **Test Results**: `docs/MEMORY_SYSTEM_TEST_RESULTS.md`
- **User Guide**: `docs/MEMORY_SYSTEM_GUIDE.md`

---

## 🔄 Version History

### v1.0 (2025-10-08)
- 7개 CLI 명령어 구현
- FTS5 + Qdrant 하이브리드 검색
- 자동 TTL 관리
- Docker/로컬 환경 자동 대응
- 9개 프로젝트 실사용 검증

---

## 💡 Tips & Best Practices

1. **정기 백업**: 중요 작업 전 `--memory-backup` 실행
2. **주기 정리**: 매주 `--memory-cleanup`으로 디스크 공간 확보
3. **검색 활용**: 긴 프로젝트에서는 `--memory-search`로 이전 결정사항 빠르게 찾기
4. **중요 대화 보호**: 중요 대화는 importance 10으로 수동 설정 (Python API)
5. **테스트 격리**: 테스트 시 `--memory-dir`로 독립 환경 사용
