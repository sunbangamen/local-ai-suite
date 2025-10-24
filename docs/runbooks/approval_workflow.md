# Approval Workflow Runbook

**Local AI Suite - 승인 워크플로우 운영 가이드**

**작성일**: 2025-10-24
**버전**: 1.0
**대상**: 운영팀, 시스템 관리자

---

## Table of Contents

1. [개요](#개요)
2. [단계 1: 준비 (Preparation)](#단계-1-준비-preparation)
3. [단계 2: 진행 (Execution)](#단계-2-진행-execution)
4. [단계 3: 점검 (Verification)](#단계-3-점검-verification)
5. [FAQ & 트러블슈팅](#faq--트러블슈팅)
6. [참고 자료](#참고-자료)

---

## 개요

### 승인 워크플로우란?

승인 워크플로우는 **HIGH/CRITICAL 민감도 도구**의 실행을 제한하여 무단 접근을 방지합니다:

| 도구 | 민감도 | 기본 동작 | 승인 필요 |
|------|-------|---------|----------|
| `read_file` | MEDIUM | ✅ 즉시 실행 | ❌ |
| `write_file` | HIGH | ⏸️ 대기 | ✅ |
| `execute_python` | CRITICAL | ⏸️ 대기 | ✅ |
| `execute_bash` | CRITICAL | ⏸️ 대기 | ✅ |
| `git_commit` | HIGH | ⏸️ 대기 | ✅ |

### 기본 설정

```bash
APPROVAL_WORKFLOW_ENABLED=false          # 기본값: 개발 모드 (승인 불필요)
APPROVAL_TIMEOUT=300                     # 타임아웃: 5분
APPROVAL_POLLING_INTERVAL=1              # 폴링 간격: 1초
APPROVAL_MAX_PENDING=50                  # 최대 대기 요청: 50개
```

### 3단계 운영 절차

```
[준비]  → DB/환경 설정, 서비스 시작
   ↓
[진행]  → 승인 요청 수신, approval_cli.py로 승인/거부 처리
   ↓
[점검]  → 감사 로그 확인, 성능 메트릭 모니터링
```

---

## 단계 1: 준비 (Preparation)

프로덕션 환경에서 승인 워크플로우를 활성화하기 위한 준비 작업입니다.

### 1.1 보안 데이터베이스 준비

#### 1.1.1 DB 파일 확인

```bash
# 보안 DB 파일 위치 확인
ls -lh /mnt/e/ai-data/sqlite/security.db

# 출력 예시:
# -rw-r--r-- 1 user user 2.5M Oct 24 10:00 security.db
```

#### 1.1.2 초기 데이터 시딩

```bash
# 새 환경 또는 기존 DB 초기화 시
cd /mnt/e/worktree/issue-42
python services/mcp-server/scripts/seed_security_data.py --reset

# 출력 예시:
# ✓ Created 3 roles (admin, developer, guest)
# ✓ Created 21 permissions
# ✓ Created 3 test users
# ✓ Set role-permissions mapping
```

**생성되는 기본 사용자**:
```
admin_user    / admin     / 모든 권한
dev_user      / developer / 개발 도구 실행
guest_user    / guest     / 읽기 전용
```

#### 1.1.3 DB 무결성 검증

```bash
# 데이터베이스 상태 확인
sqlite3 /mnt/e/ai-data/sqlite/security.db "PRAGMA integrity_check;"
# 예상 출력: ok

# 테이블 개수 확인
sqlite3 /mnt/e/ai-data/sqlite/security.db \
  "SELECT COUNT(*) as table_count FROM sqlite_master WHERE type='table';"
# 예상 출력: 10 (또는 그 이상)

# WAL 모드 확인
sqlite3 /mnt/e/ai-data/sqlite/security.db "PRAGMA journal_mode;"
# 예상 출력: wal
```

### 1.2 환경 변수 설정

#### 1.2.1 .env 파일 업데이트

```bash
# 편집기로 .env 파일 열기
nano .env

# 다음 라인 찾아서 수정:
APPROVAL_WORKFLOW_ENABLED=true          # false → true로 변경
APPROVAL_TIMEOUT=300                    # 필요시 조정 (초 단위)
APPROVAL_POLLING_INTERVAL=1             # 1초 권장 (UX 최적화)
```

#### 1.2.2 환경 변수 확인

```bash
# 현재 설정 확인
grep "APPROVAL_" .env

# 출력 예시:
# APPROVAL_WORKFLOW_ENABLED=true
# APPROVAL_TIMEOUT=300
# APPROVAL_POLLING_INTERVAL=1
# APPROVAL_MAX_PENDING=50
```

### 1.3 서비스 시작

#### 1.3.1 Phase 3 스택 시작

```bash
# 기존 컨테이너 정지
make down-p3

# 새로운 설정으로 시작
make up-p3

# 또는 Docker Compose 직접 사용
docker compose -f docker/compose.p3.yml up -d
```

#### 1.3.2 서비스 상태 확인

```bash
# MCP 서버 헬스 체크
curl http://localhost:8020/health

# 출력 예시:
# {
#   "status": "healthy",
#   "rbac_enabled": true,
#   "approval_workflow_enabled": true
# }

# 컨테이너 로그 확인
docker logs mcp-server | tail -20

# 오류 있으면 확인
docker logs mcp-server | grep -i "error\|warning" | tail -10
```

#### 1.3.3 백업 설정

```bash
# 자동 백업 스크립트 실행
python services/mcp-server/scripts/backup_security_db.py \
  --output-dir /mnt/e/ai-data/backups

# 출력 예시:
# ✓ Checkpoint completed
# ✓ Backup created: security.db.backup.20251024_120000.db
# ✓ Old backups cleaned (kept 7 days)
```

**cron 설정 (일일 자동 백업, 선택)**:
```bash
# 매일 자정에 백업
0 0 * * * /usr/bin/python3 /mnt/e/worktree/issue-42/services/mcp-server/scripts/backup_security_db.py --output-dir /mnt/e/ai-data/backups >> /var/log/approval_backup.log 2>&1
```

---

## 단계 2: 진행 (Execution)

승인 워크플로우가 활성화된 상태에서의 일반적인 작업 흐름입니다.

### 2.1 승인 요청 생성

#### 2.1.1 사용자가 CRITICAL 도구 실행

**시나리오**: 개발자가 Python 코드 실행 요청

```bash
# Terminal A (사용자)
python scripts/ai.py --mcp execute_python \
  --mcp-args '{"code": "import os; print(os.getcwd())", "timeout": 30}'

# 출력 예시:
# ⏳ Approval pending for HIGH/CRITICAL tool
# Tool: execute_python
# Request ID: 550e8400-e29b-41d4-a716-446655440000
# Expires in: 5:00 (5 minutes)
#
# ⏳ Waiting for approval...
# [████░░░░░] 20% (100 seconds left)
```

#### 2.1.2 요청 데이터 DB 확인

```bash
# Terminal B (관리자)
sqlite3 /mnt/e/ai-data/sqlite/security.db \
  "SELECT request_id, tool_name, user_id, status, requested_at FROM approval_requests \
   WHERE status='pending' ORDER BY requested_at DESC LIMIT 5;"

# 출력 예시:
# 550e8400-e29b-41d4-a716-446655440000|execute_python|dev_user|pending|2025-10-24 12:00:15
```

### 2.2 승인/거부 처리

#### 2.2.1 approval_cli.py 실행 (자동 모드)

```bash
# Terminal B (관리자)
python scripts/approval_cli.py

# 자동으로 대기 중인 요청 목록 표시:
#
# ╔════════════════════════════════════════════════════════════╗
# ║             🔔 Pending Approval Requests                  ║
# ╚════════════════════════════════════════════════════════════╝
#
# [1] 550e8400...  execute_python   dev_user      5m 00s left
# [2] 661f9511...  git_commit       dev_user      4m 30s left
#
# Enter request ID or number (or 'q' to quit): 1
#
# ┌──────────────────────────────────────────────────────────┐
# │ Request: 550e8400-e29b-41d4-a716-446655440000          │
# │ Tool: execute_python                                     │
# │ User: dev_user (developer)                               │
# │ Time: 2025-10-24 12:00:15                                │
# │ Expires: 2025-10-24 12:05:15                             │
# └──────────────────────────────────────────────────────────┘
#
# (A)pprove, (R)eject, (S)kip: a
```

#### 2.2.2 approval_cli.py 실행 (연속 모드)

```bash
# 계속 대기 중인 요청 모니터링 (종료 시 Ctrl+C)
python scripts/approval_cli.py --continuous

# 또는 한 번만 실행하고 종료
python scripts/approval_cli.py --once

# 특정 요청만 조회/처리
python scripts/approval_cli.py --list          # 목록만 표시
python scripts/approval_cli.py --filter pending  # pending 요청만
```

#### 2.2.3 승인 처리 (SQL, 선택)

```bash
# 승인 (CLI 대신 SQL 직접 사용 가능)
sqlite3 /mnt/e/ai-data/sqlite/security.db << 'EOF'
UPDATE approval_requests
SET status='approved',
    responded_at=datetime('now'),
    responder_id='admin_user',
    response_reason='Verified safe code'
WHERE request_id='550e8400-e29b-41d4-a716-446655440000';
EOF

# 확인
sqlite3 /mnt/e/ai-data/sqlite/security.db \
  "SELECT status, responder_id, response_reason, responded_at FROM approval_requests \
   WHERE request_id='550e8400-e29b-41d4-a716-446655440000';"
```

### 2.3 자동 재실행

#### 2.3.1 사용자 CLI의 자동 폴링

```bash
# Terminal A (사용자) - 자동으로 계속 진행
#
# ✅ Request approved!
# Executing: execute_python
#
# Output:
# /mnt/e/worktree/issue-42
#
# ✅ Command completed successfully
```

#### 2.3.2 거부된 경우

```bash
# Terminal A (사용자) - 거부 시나리오
#
# ❌ Request rejected!
# Reason: Unsafe code detected
#
# ❌ Command execution cancelled
```

---

## 단계 3: 점검 (Verification)

운영 중 성능 및 보안을 모니터링합니다.

### 3.1 감사 로그 확인

#### 3.1.1 최근 활동 조회

```bash
# 최근 10개 요청 확인
sqlite3 /mnt/e/ai-data/sqlite/security.db \
  "SELECT timestamp, user_id, tool_name, status FROM security_audit_logs \
   ORDER BY timestamp DESC LIMIT 10;"

# 출력 예시:
# 2025-10-24 12:05:45|dev_user|execute_python|approved
# 2025-10-24 12:03:22|dev_user|execute_python|denied
# 2025-10-24 12:00:15|dev_user|execute_python|requested
```

#### 3.1.2 일일 통계

```bash
# 하루 동작 요약
sqlite3 /mnt/e/ai-data/sqlite/security.db << 'EOF'
SELECT
  DATE(timestamp) as date,
  COUNT(*) as total_requests,
  SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) as approved,
  SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END) as rejected,
  SUM(CASE WHEN status='timeout' THEN 1 ELSE 0 END) as timeout
FROM security_audit_logs
WHERE DATE(timestamp)=DATE('now')
GROUP BY DATE(timestamp);
EOF

# 출력 예시:
# 2025-10-24|45|40|3|2
# (총 45개, 승인 40개, 거부 3개, 타임아웃 2개)
```

#### 3.1.3 사용자별 활동

```bash
# 각 사용자의 활동 내역
sqlite3 /mnt/e/ai-data/sqlite/security.db \
  "SELECT user_id, COUNT(*) as count,
          SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) as approved,
          MIN(timestamp) as first_action,
          MAX(timestamp) as last_action
   FROM security_audit_logs
   WHERE DATE(timestamp)=DATE('now')
   GROUP BY user_id
   ORDER BY count DESC;"
```

### 3.2 성능 메트릭

#### 3.2.1 승인 처리 시간

```bash
# 평균 승인 대기 시간 측정
sqlite3 /mnt/e/ai-data/sqlite/security.db << 'EOF'
SELECT
  ROUND(AVG((julianday(responded_at) - julianday(requested_at)) * 86400), 2)
    as avg_approval_time_sec,
  MIN((julianday(responded_at) - julianday(requested_at)) * 86400)
    as min_time_sec,
  MAX((julianday(responded_at) - julianday(requested_at)) * 86400)
    as max_time_sec
FROM approval_requests
WHERE status IN ('approved', 'rejected')
  AND DATE(responded_at)=DATE('now');
EOF

# 출력 예시:
# 15.3|2.1|120.5
# (평균 15.3초, 최소 2.1초, 최대 120.5초)
```

#### 3.2.2 DB 성능

```bash
# WAL 체크포인트 상태
sqlite3 /mnt/e/ai-data/sqlite/security.db \
  "PRAGMA wal_checkpoint(RESTART);"

# 파일 크기 확인
ls -lh /mnt/e/ai-data/sqlite/security.db*

# 출력 예시:
# security.db       5.2M
# security.db-wal   1.8M  (활성 WAL 파일)
# security.db-shm   32K   (공유 메모리)
```

### 3.3 헬스 체크

#### 3.3.1 서비스 상태

```bash
# MCP 서버 헬스 체크
curl -s http://localhost:8020/health | python -m json.tool

# 출력:
# {
#   "status": "healthy",
#   "rbac_enabled": true,
#   "approval_workflow_enabled": true,
#   "db_available": true
# }

# 응답 시간 측정
time curl -s http://localhost:8020/health > /dev/null

# 출력 예시:
# real    0m0.015s
# user    0m0.002s
# sys     0m0.004s
```

#### 3.3.2 DB 연결 테스트

```bash
# SQLite 연결 확인 및 성능 테스트
sqlite3 /mnt/e/ai-data/sqlite/security.db << 'EOF'
-- 간단한 쿼리 성능 측정
.timer ON
SELECT COUNT(*) FROM security_audit_logs;
SELECT COUNT(*) FROM approval_requests WHERE status='pending';
.timer OFF
EOF
```

---

## FAQ & 트러블슈팅

### Q1: 승인 요청이 지연되는 경우

**증상**: CLI에서 10분 이상 대기 중, 승인하지 않음

**원인**:
- 승인자가 부재 중
- 네트워크 지연
- 타임아웃 설정이 너무 짧음

**해결**:
```bash
# 1. 현재 대기 요청 확인
python scripts/approval_cli.py --list

# 2. 요청 상태 확인
sqlite3 /mnt/e/ai-data/sqlite/security.db \
  "SELECT request_id, status, requested_at, expires_at FROM approval_requests \
   WHERE status='pending' AND request_id='xxx';"

# 3. 타임아웃 설정 확인 및 조정
grep "APPROVAL_TIMEOUT" .env
# APPROVAL_TIMEOUT=300 → 필요시 600(10분)으로 증가

# 4. 만료된 요청 정리
sqlite3 /mnt/e/ai-data/sqlite/security.db \
  "UPDATE approval_requests \
   SET status='timeout' \
   WHERE status='pending' AND datetime(expires_at) < datetime('now');"

# 5. 요청 수동 승인
python scripts/approval_cli.py --approve <request_id>
```

---

### Q2: DB 잠금 오류 발생 시 (`database is locked`)

**증상**: "database is locked" 오류로 API 실패

**원인**:
- 동시에 여러 프로세스가 DB 쓰기 시도
- WAL 체크포인트 미완료
- 장시간 미완료 트랜잭션

**해결**:
```bash
# 1. WAL 체크포인트 강제 실행
sqlite3 /mnt/e/ai-data/sqlite/security.db \
  "PRAGMA wal_checkpoint(RESTART);"

# 2. WAL 파일 상태 확인
ls -lh /mnt/e/ai-data/sqlite/security.db*

# 3. 필요시 WAL 파일 삭제 (주의!)
# - 먼저 서비스 정지: make down-p3
# - WAL 파일 제거: rm /mnt/e/ai-data/sqlite/security.db-*
# - 서비스 재시작: make up-p3

# 4. 재시도
python scripts/ai.py --mcp execute_python --mcp-args '{"code": "print(1)"}'
```

---

### Q3: 플래그 비활성화 후 동작 확인

**시나리오**: 프로덕션에서 승인 워크플로우 잠시 비활성화

**절차**:
```bash
# 1. .env 파일 수정
nano .env
# APPROVAL_WORKFLOW_ENABLED=false로 변경

# 2. 서비스 재시작
make down-p3 && make up-p3

# 3. 헬스 체크
curl http://localhost:8020/health

# 4. 기능 확인 (즉시 실행되어야 함)
python scripts/ai.py --mcp execute_python \
  --mcp-args '{"code": "print(\"Test\")", "timeout": 30}'

# 예상 결과: 바로 실행 완료, "Test" 출력

# 5. DB 데이터는 유지됨
sqlite3 /mnt/e/ai-data/sqlite/security.db \
  "SELECT COUNT(*) FROM approval_requests;"
# → 기존 데이터 모두 남아있음

# 6. 다시 활성화 시
# .env APPROVAL_WORKFLOW_ENABLED=true로 변경 후 재시작
```

---

### Q4: 대량의 승인 요청 처리

**시나리오**: 한 번에 50개 이상의 승인 요청

**권장 절차**:
```bash
# 1. approval_cli.py 연속 모드로 효율적 처리
python scripts/approval_cli.py --continuous

# 2. 또는 배치 SQL 처리 (자동 승인, 주의!)
sqlite3 /mnt/e/ai-data/sqlite/security.db << 'EOF'
-- 특정 사용자/도구의 pending 요청 일괄 승인
UPDATE approval_requests
SET status='approved',
    responded_at=datetime('now'),
    responder_id='admin_user'
WHERE status='pending'
  AND user_id='dev_user'
  AND tool_name='execute_python'
  AND datetime('now') < datetime(expires_at)
LIMIT 10;  -- 안전을 위해 최대 10개씩
EOF

# 3. 처리 결과 확인
sqlite3 /mnt/e/ai-data/sqlite/security.db \
  "SELECT COUNT(*) FROM approval_requests WHERE status='approved' AND DATE(responded_at)=DATE('now');"
```

---

### Q5: 긴급 롤백 필요 시

**상황**: 승인 워크플로우로 인한 장애

**빠른 복구**:
```bash
# 1. 즉시 플래그 비활성화
sed -i 's/APPROVAL_WORKFLOW_ENABLED=true/APPROVAL_WORKFLOW_ENABLED=false/g' .env

# 2. 서비스 재시작
make down-p3 && make up-p3

# 3. 확인
curl http://localhost:8020/health | grep approval_workflow_enabled

# 4. 문제 분석 (로그 확인)
docker logs mcp-server > /tmp/mcp-error.log 2>&1

# 5. 필요시 DB 백업에서 복구
cp /mnt/e/ai-data/backups/security.db.backup.*.db /mnt/e/ai-data/sqlite/security.db
```

---

## 참고 자료

### 관련 문서
- **RBAC 설정 가이드**: `docs/security/RBAC_GUIDE.md`
- **구현 상세 정보**: `docs/security/IMPLEMENTATION_SUMMARY.md`
- **배포 체크리스트**: `docs/security/IMPLEMENTATION_SUMMARY.md#-production-deployment-checklist`

### 유용한 명령어

```bash
# 빠른 승인 CLI 실행
alias approve='python scripts/approval_cli.py'

# DB 상태 확인 함수
check_approval_status() {
  sqlite3 /mnt/e/ai-data/sqlite/security.db \
    "SELECT COUNT(*) FROM approval_requests WHERE status='pending';"
}

# 로그 실시간 모니터링
watch_logs() {
  docker logs -f mcp-server | grep -i approval
}

# 일일 통계 확인
daily_stats() {
  sqlite3 /mnt/e/ai-data/sqlite/security.db \
    "SELECT DATE(timestamp) as date, COUNT(*) as requests, \
            SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) as approved \
     FROM security_audit_logs WHERE DATE(timestamp)=DATE('now');"
}
```

### 비상 연락처 (선택)
- **DBA**: 데이터베이스 문제 시
- **운영팀 리더**: 정책 결정 필요 시
- **개발팀**: 코드 관련 이슈 시

---

**Document Version**: 1.0
**Last Updated**: 2025-10-24
**Review Cycle**: 분기별 (Q1, Q2, Q3, Q4)

---

## 추가 참고

### WAL (Write-Ahead Logging) 모드

보안 DB는 **WAL 모드**를 사용합니다. 이는:
- ✅ 동시 읽기/쓰기 허용 (성능 향상)
- ✅ 데이터 무결성 보장 (충돌 시에도 안전)
- ⚠️ 3개 파일 관리 필요 (`.db`, `.db-wal`, `.db-shm`)

**주의**: WAL 파일을 수동 삭제하지 마세요. 항상 `PRAGMA wal_checkpoint()` 사용

### 보안 고려사항

1. **감사 로그 정기 검토**: 주1회 이상
2. **승인 기록 백업**: 규정 보유 기간 유지
3. **사용자 권한 감시**: 비정상 패턴 모니터링
4. **타임아웃 조정**: 환경에 맞게 튜닝

### 성능 최적화

- **폴링 간격**: 1초 (기본, UX 최적화) → 네트워크 느릴 시 2-3초
- **타임아웃**: 300초 (기본) → 팀 규모에 따라 600-900초 권장
- **DB 인덱스**: `security_audit_logs(timestamp)`, `approval_requests(status, expires_at)` 자동 생성됨
