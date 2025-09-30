# 메모리 백업 관리 정책

## 개요

메모리 데이터베이스 백업 파일의 생성, 보관, 정리 정책을 정의합니다.

## 백업 파일 생성

### 자동 백업 시점

1. **스키마 마이그레이션 시**
   - 파일명: `memory_backup_YYYYMMDD_HHMMSS.db`
   - 위치: 각 프로젝트 디렉토리 (`/mnt/e/ai-data/memory/projects/PROJECT_ID/`)
   - 타임스탬프: 마이그레이션 실행 시각

2. **Memory Maintainer 백업 (예정)**
   - 스케줄: 매일 03:00 (한국시간)
   - 위치: `/mnt/e/ai-data/memory/backups/daily/`
   - 파일명: `PROJECT_ID_YYYYMMDD.db`

## 백업 보관 정책

### 단기 백업 (마이그레이션)

**보관 기간**: 30일
- 최근 30일간의 마이그레이션 백업 유지
- 30일이 지난 백업은 자동 삭제 또는 아카이브

**정리 스크립트**:
```bash
# 30일 이상된 마이그레이션 백업 삭제
find /mnt/e/ai-data/memory/projects -name "memory_backup_*.db" \
  -type f -mtime +30 -delete
```

### 장기 백업 (일일)

**보관 기간**: 3개월
- 최근 3개월간의 일일 백업 유지
- 매월 1일 백업은 1년간 보관

**정리 스크립트**:
```bash
# 90일 이상된 일일 백업 삭제 (단, 매월 1일 백업 제외)
find /mnt/e/ai-data/memory/backups/daily -name "*_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9].db" \
  -type f -mtime +90 ! -name "*_????01[0-9].db" -delete
```

## 백업 구조

```
/mnt/e/ai-data/memory/
├── projects/
│   ├── PROJECT_ID_1/
│   │   ├── memory.db                              # 현재 DB
│   │   └── memory_backup_20250930_192607.db       # 마이그레이션 백업
│   └── PROJECT_ID_2/
│       ├── memory.db
│       └── memory_backup_20250930_192607.db
└── backups/
    ├── daily/                                      # 일일 백업 (예정)
    │   ├── PROJECT_ID_1_20250930.db
    │   └── PROJECT_ID_2_20250930.db
    └── monthly/                                    # 월별 아카이브 (예정)
        ├── PROJECT_ID_1_202509.tar.gz
        └── PROJECT_ID_2_202509.tar.gz
```

## 현재 백업 상태 (2025-09-30)

### 마이그레이션 백업

- **생성 일시**: 2025-09-30 19:26:07
- **백업 개수**: 4개
- **총 용량**: 약 336KB (84KB × 4)

**백업된 프로젝트**:
1. `13d57514-64fa-4c02-9e44-830632a9d09d`
2. `64556d5e-771d-45be-8a8e-b841868f63db`
3. `76daf135-d253-44ef-8bd0-84698f106123`
4. `f623612b-694f-43a3-9542-775bd3f55813`

## 백업 확인 및 복원

### 백업 목록 확인

```bash
# 모든 마이그레이션 백업 확인
find /mnt/e/ai-data/memory/projects -name "memory_backup_*.db" -ls

# 특정 프로젝트 백업 확인
ls -lh /mnt/e/ai-data/memory/projects/PROJECT_ID/memory_backup_*.db
```

### 백업 복원

```bash
# 1. 현재 DB를 안전하게 이동
cd /mnt/e/ai-data/memory/projects/PROJECT_ID
mv memory.db memory_failed_$(date +%Y%m%d_%H%M%S).db

# 2. 백업에서 복원
cp memory_backup_20250930_192607.db memory.db

# 3. 권한 확인
chmod 644 memory.db
chown limeking:limeking memory.db

# 4. Memory Maintainer 재시작 (선택)
docker compose -f docker/compose.p3.yml restart memory-maintainer
```

## 백업 관리 명령어

### 백업 용량 확인

```bash
# 프로젝트별 백업 용량
du -sh /mnt/e/ai-data/memory/projects/*/memory_backup_*.db

# 전체 백업 용량
du -sh /mnt/e/ai-data/memory/projects/*/memory_backup_*.db | awk '{sum+=$1} END {print sum}'
```

### 오래된 백업 정리

```bash
# 30일 이상된 백업 목록 확인 (삭제 전 확인)
find /mnt/e/ai-data/memory/projects -name "memory_backup_*.db" \
  -type f -mtime +30 -ls

# 실제 삭제 (주의!)
find /mnt/e/ai-data/memory/projects -name "memory_backup_*.db" \
  -type f -mtime +30 -delete
```

### 백업 아카이브

```bash
# 특정 프로젝트 백업을 압축 아카이브
tar -czf /mnt/e/ai-data/memory/backups/PROJECT_ID_archive_$(date +%Y%m).tar.gz \
  /mnt/e/ai-data/memory/projects/PROJECT_ID/memory_backup_*.db

# 압축 후 원본 삭제 (확인 후 실행)
rm /mnt/e/ai-data/memory/projects/PROJECT_ID/memory_backup_*.db
```

## 자동화 (Cron 예제)

### 월간 백업 정리

```bash
# /etc/cron.monthly/cleanup_memory_backups.sh
#!/bin/bash

# 30일 이상된 마이그레이션 백업 삭제
find /mnt/e/ai-data/memory/projects -name "memory_backup_*.db" \
  -type f -mtime +30 -delete

# 90일 이상된 일일 백업 삭제 (매월 1일 제외)
find /mnt/e/ai-data/memory/backups/daily -name "*_[0-9]*.db" \
  -type f -mtime +90 ! -name "*_????01[0-9].db" -delete

# 로그 기록
echo "$(date): Memory backup cleanup completed" >> /var/log/memory_backup_cleanup.log
```

## 모니터링

### 백업 무결성 검증

```bash
# SQLite 백업 파일 무결성 검증
for backup in /mnt/e/ai-data/memory/projects/*/memory_backup_*.db; do
  echo "Checking $backup..."
  sqlite3 "$backup" "PRAGMA integrity_check;" || echo "FAILED: $backup"
done
```

### 디스크 용량 경고

```bash
# 백업 디렉토리 용량이 1GB 초과 시 경고
BACKUP_SIZE=$(du -sb /mnt/e/ai-data/memory/projects/*/memory_backup_*.db 2>/dev/null | awk '{sum+=$1} END {print sum}')
if [ "$BACKUP_SIZE" -gt 1073741824 ]; then
  echo "WARNING: Memory backups exceeding 1GB: $(($BACKUP_SIZE / 1048576))MB"
fi
```

## 주의사항

1. **삭제 전 확인**: 백업 삭제 전 반드시 목록 확인 (`-ls` 옵션 사용)
2. **권한 관리**: 복원 후 파일 권한 및 소유자 확인 필수
3. **서비스 중단**: 복원 작업 시 Memory Maintainer 일시 중지 권장
4. **압축 보관**: 장기 보관 시 압축하여 디스크 공간 절약
5. **버전 관리**: 마이그레이션 백업은 스키마 버전별로 구분 보관

## 참고 문서

- [메모리 스키마 마이그레이션 가이드](../README_MEMORY_MIGRATION.md)
- [Docker 통합 테스트 결과](./DOCKER_INTEGRATION_TEST_RESULTS.md)
- [메모리 시스템 문서](./MEMORY_SYSTEM.md)

---

**최종 업데이트**: 2025-09-30
**작성자**: Claude Code (Memory System Migration)