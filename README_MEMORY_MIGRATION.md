# Memory Schema Migration Guide

## 개요

이전 버전의 메모리 데이터베이스를 최신 스키마로 업그레이드하는 가이드입니다.

## 배경

Memory Maintainer의 Qdrant 동기화 기능을 사용하기 위해서는 다음 컬럼이 필요합니다:
- `id` (PRIMARY KEY)
- `sync_status` (동기화 상태: pending/synced/failed)
- `synced_at` (동기화 완료 시각)
- `qdrant_point_id` (Qdrant 포인트 ID)

이전 스키마의 DB는 이러한 컬럼이 없어 `no such column: ce.id` 에러가 발생합니다.

## 영향

**마이그레이션 전:**
- 🔴 Qdrant 동기화 실패 (`no such column: ce.id` 에러)
- ✅ 새 대화 저장은 정상 작동
- ✅ 기존 대화 검색은 정상 작동

**마이그레이션 후:**
- ✅ Qdrant 동기화 정상 작동
- ✅ 모든 대화가 벡터 검색 가능
- ✅ Memory Maintainer의 자동 동기화 활성화

## 사용법

### 1. Dry-run으로 확인

실제 변경 없이 마이그레이션 대상을 확인합니다:

```bash
python3 scripts/migrate_memory_schema.py --dry-run
```

출력 예시:
```
============================================================
Memory Database Schema Migration
============================================================

🔍 DRY RUN MODE - No changes will be made

Found 8 database(s)

✅ Up to date (4):
   • 5308fcdc-e918-4b25-8e62-864c714abe2f
   • d0567dcb
   • d0567dcb-de6e-41d6-804a-8cdb88746f79
   • default-project

🔄 Need migration (4):
   • 13d57514-64fa-4c02-9e44-830632a9d09d: Missing columns: id, synced_at
   • 64556d5e-771d-45be-8a8e-b841868f63db: Missing columns: id
   • 76daf135-d253-44ef-8bd0-84698f106123: Missing columns: id, synced_at
   • f623612b-694f-43a3-9542-775bd3f55813: Missing columns: id, synced_at

Migrating 13d57514-64fa-4c02-9e44-830632a9d09d...
  📋 Would apply: Recreate table with id PRIMARY KEY

...

============================================================
📋 Would migrate 4 database(s)
```

### 2. 전체 마이그레이션 실행

**⚠️ 중요: 자동으로 백업이 생성됩니다**

```bash
python3 scripts/migrate_memory_schema.py
```

확인 프롬프트가 나타납니다:
```
Proceed with migration? [y/N]: y
```

### 3. 특정 프로젝트만 마이그레이션

```bash
# 프로젝트 ID의 일부만 입력해도 됩니다
python3 scripts/migrate_memory_schema.py --project 13d57514
```

## 마이그레이션 상세

### 자동 백업

마이그레이션 실행 시 자동으로 백업이 생성됩니다:
```
/mnt/e/ai-data/memory/projects/PROJECT_ID/memory_backup_20250930_163000.db
```

### 스키마 변경 내용

1. **`conversation_embeddings` 테이블 재생성**:
   - `id INTEGER PRIMARY KEY AUTOINCREMENT` 추가
   - `sync_status TEXT DEFAULT 'pending'` 추가
   - `synced_at TEXT` 추가
   - `qdrant_point_id TEXT` 추가

2. **인덱스 생성**:
   - `idx_embeddings_conversation` (conversation_id)
   - `idx_embeddings_sync_status` (sync_status)

3. **기존 데이터 보존**:
   - 모든 기존 임베딩 데이터는 그대로 유지됩니다
   - `sync_status`는 자동으로 'pending'으로 설정됩니다

### 롤백 방법

문제가 발생한 경우 백업에서 복원:

```bash
# 백업 파일 확인
ls -lh /mnt/e/ai-data/memory/projects/PROJECT_ID/memory_backup_*.db

# 복원 (원본을 백업으로 교체)
cd /mnt/e/ai-data/memory/projects/PROJECT_ID
mv memory.db memory_failed.db
mv memory_backup_20250930_163000.db memory.db
```

## 마이그레이션 후 확인

### 1. Memory Maintainer 로그 확인

```bash
docker logs docker-memory-maintainer-1 --tail 50
```

에러가 사라졌는지 확인:
```
# 마이그레이션 전 (에러 발생)
ERROR - Qdrant 동기화 실패 - /app/memory/projects/13d57514.../memory.db: no such column: ce.id

# 마이그레이션 후 (정상)
INFO - Qdrant 동기화 작업 완료 - 동기화: 5, 실패: 0, 스킵: 0
```

### 2. 동기화 상태 확인

Memory Maintainer가 자동으로 5분마다 동기화를 시도합니다:
- 다음 동기화까지 최대 5분 대기
- 로그에서 "동기화: N" 카운트 확인

### 3. Qdrant에서 벡터 확인

```bash
# 컬렉션 목록 확인
curl http://localhost:6333/collections

# 특정 프로젝트 컬렉션 확인
curl http://localhost:6333/collections/memory_13d57514
```

## 주의사항

1. **Docker 컨테이너 재시작 불필요**:
   - 마이그레이션은 호스트에서 실행
   - Memory Maintainer가 자동으로 변경사항 감지

2. **데이터 손실 없음**:
   - 모든 기존 대화와 임베딩 보존
   - 백업 자동 생성

3. **실행 중 안전**:
   - Memory Maintainer가 실행 중이어도 안전
   - SQLite ACID 트랜잭션 보장

4. **롤백 가능**:
   - 백업 파일로 언제든지 복원 가능
   - 타임스탬프로 백업 버전 식별

## 문제 해결

### Q: "PermissionError: [Errno 13] Permission denied"

**원인**: 파일 권한 부족

**해결**:
```bash
# 소유권 확인
ls -la /mnt/e/ai-data/memory/projects/PROJECT_ID/memory.db

# 필요시 권한 변경 (사용자에 맞게 조정)
sudo chown $USER:$USER /mnt/e/ai-data/memory/projects/PROJECT_ID/memory.db
```

### Q: 마이그레이션 중 에러 발생

**해결**:
1. 에러 메시지 확인
2. 백업 파일 존재 확인
3. 백업에서 복원
4. GitHub issue 등록 (에러 로그 첨부)

### Q: 마이그레이션 후에도 에러 발생

**원인**: Memory Maintainer 캐시 문제

**해결**:
```bash
# Memory Maintainer 재시작
docker compose -f docker/compose.p3.yml restart memory-maintainer

# 로그 확인
docker logs docker-memory-maintainer-1 -f
```

## 참고 문서

- [Memory System Documentation](./docs/MEMORY_SYSTEM.md)
- [Docker Integration Test Results](./docs/DOCKER_INTEGRATION_TEST_RESULTS.md)
- [Implementation Summary](./docs/IMPLEMENTATION_SUMMARY.md)

## 도움말

마이그레이션 스크립트 도움말 보기:

```bash
python3 scripts/migrate_memory_schema.py --help
```