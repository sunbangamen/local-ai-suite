# 승인 워크플로우 운영 가이드

**Issue #40: 승인 워크플로우 운영화 개선**
**작성일**: 2025-10-24
**대상**: 운영팀, DevOps 엔지니어

---

## 📋 개요

이 가이드는 Local AI Suite의 승인 워크플로우(Approval Workflow) 시스템을 프로덕션 환경에서 운영하기 위한 실전 매뉴얼입니다.

### 승인 워크플로우란?

HIGH 및 CRITICAL 보안 레벨의 MCP 도구 실행 시 관리자의 명시적 승인을 요구하는 시스템입니다.

**보호 대상 도구 예시:**
- `execute_python` (CRITICAL) - Python 코드 실행
- `run_command` (CRITICAL) - 시스템 명령어 실행
- `write_file` (HIGH) - 파일 쓰기
- `web_automate` (HIGH) - 웹 자동화

---

## 🚀 배포 가이드

### 사전 요구사항

```bash
# 필수 파일 확인
- docker-compose.p3.yml
- .env (또는 .env.example)
- services/mcp-server/app.py
- scripts/approval_cli.py
- scripts/ai.py

# 데이터베이스
- /mnt/e/ai-data/sqlite/security.db (자동 생성)
```

### 배포 절차 (운영팀 체크리스트)

#### Step 1: 환경 변수 설정

```bash
# 1. 프로덕션 .env 파일 편집
vi .env

# 2. 다음 변수 확인/수정
APPROVAL_WORKFLOW_ENABLED=true           # ✅ 활성화
APPROVAL_TIMEOUT=300                     # ✅ 5분 (권장)
APPROVAL_POLLING_INTERVAL=1              # ✅ 1초 (권장)
APPROVAL_MAX_PENDING=50                  # ✅ 동시 50개 요청 (권장)

# 3. 보안 관련 변수도 함께 확인
RBAC_ENABLED=true                        # RBAC 활성화 (권장)
SECURITY_DB_PATH=/mnt/e/ai-data/sqlite/security.db
SANDBOX_ENABLED=true
RATE_LIMIT_ENABLED=true
```

#### Step 2: 서비스 시작

```bash
# Phase 3 스택 시작
docker compose -f docker/compose.p3.yml up -d

# 서비스 정상화 확인 (30초 대기)
sleep 30
curl http://localhost:8020/health

# 예상 응답: {"status": "ok"}
```

#### Step 3: 기능 검증

```bash
# 1. 승인 요청 DB 테이블 확인
sqlite3 /mnt/e/ai-data/sqlite/security.db \
  "SELECT name FROM sqlite_master WHERE type='table' AND name='approval_requests';"

# 출력: approval_requests (있어야 함)

# 2. 관리자 CLI 도구 테스트
python scripts/approval_cli.py --help

# 3. 테스트 승인 요청 생성 (별도 터미널)
export APPROVAL_WORKFLOW_ENABLED=true
python scripts/ai.py --mcp execute_python \
  --mcp-args '{"code": "print(\"test\")"}'

# 4. 관리자 승인 처리 (메인 터미널)
python scripts/approval_cli.py
# → 대기 요청 표시됨
# → 'a' 입력으로 승인
```

#### Step 4: 운영팀 교육

- [ ] 관리자 CLI 도구 사용법 숙지 (30분)
- [ ] 승인 워크플로우 타임아웃 이해 (5분)
- [ ] 롤백 절차 숙지 (15분)
- [ ] 로그 조회 쿼리 실습 (30분)

---

## 👨‍💼 운영팀 일일 작업

### 아침 점검 (매일 09:00)

```bash
#!/bin/bash
# file: ops/daily_check.sh

echo "=== 승인 워크플로우 일일 점검 ==="

# 1. 서비스 상태 확인
echo "1️⃣ 서비스 상태"
curl -s http://localhost:8020/health | jq .

# 2. 대기 중인 승인 요청 확인
echo "2️⃣ 대기 중인 요청 (최근 1시간)"
sqlite3 /mnt/e/ai-data/sqlite/security.db << 'EOF'
SELECT
  SUBSTR(request_id, 1, 8) as id,
  tool_name,
  user_id,
  strftime('%H:%M:%S', requested_at) as time,
  CAST((julianday(expires_at) - julianday('now')) * 60 AS INTEGER) as expires_min
FROM approval_requests
WHERE status = 'pending'
  AND datetime('now', '-1 hour') < requested_at
ORDER BY requested_at DESC;
EOF

# 3. 어제 승인 통계
echo "3️⃣ 어제 승인 통계"
sqlite3 /mnt/e/ai-data/sqlite/security.db << 'EOF'
SELECT
  COUNT(*) as total,
  SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
  SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
  SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
FROM approval_requests
WHERE DATE(requested_at) = DATE('now', '-1 day');
EOF

# 4. 오류 로그 확인
echo "4️⃣ 최근 MCP 서버 오류"
docker logs mcp-server --since 24h --until 5m 2>&1 | grep -i "error\|exception" | tail -5
```

### 승인 관리 (필요 시 수시)

```bash
# 1. 대기 요청 확인 (5분 간격 폴링)
python scripts/approval_cli.py --list

# 2. 승인 처리 (Interactive UI)
python scripts/approval_cli.py

# 3. 배치 승인 (미리 정의된 요청들)
# Phase 2에서 추가 예정

# 4. 거부 처리
python scripts/approval_cli.py
# → 선택 후 거부 이유 입력
```

### 저녁 보고 (매일 18:00)

```bash
#!/bin/bash
# file: ops/daily_report.sh

echo "=== 승인 워크플로우 일일 보고 ==="
echo "작성일: $(date +'%Y-%m-%d %H:%M:%S')"
echo ""

# 1. 일일 통계
sqlite3 /mnt/e/ai-data/sqlite/security.db << 'EOF'
SELECT
  'Total Requests' as metric,
  COUNT(*) as value
FROM approval_requests
WHERE DATE(requested_at) = DATE('now')
UNION ALL
SELECT 'Approved', COUNT(*)
FROM approval_requests
WHERE DATE(requested_at) = DATE('now') AND status = 'approved'
UNION ALL
SELECT 'Rejected', COUNT(*)
FROM approval_requests
WHERE DATE(requested_at) = DATE('now') AND status = 'rejected'
UNION ALL
SELECT 'Pending', COUNT(*)
FROM approval_requests
WHERE DATE(requested_at) = DATE('now') AND status = 'pending';
EOF

echo ""

# 2. 도구별 상위 요청 (Top 5)
echo "Top 5 Tools by Requests:"
sqlite3 /mnt/e/ai-data/sqlite/security.db << 'EOF'
SELECT tool_name, COUNT(*) as count
FROM approval_requests
WHERE DATE(requested_at) = DATE('now')
GROUP BY tool_name
ORDER BY count DESC
LIMIT 5;
EOF

echo ""

# 3. 평균 승인 시간
echo "Avg Approval Time:"
sqlite3 /mnt/e/ai-data/sqlite/security.db << 'EOF'
SELECT
  ROUND(AVG(
    (julianday(responded_at) - julianday(requested_at)) * 24 * 60
  ), 2) as avg_minutes
FROM approval_requests
WHERE DATE(requested_at) = DATE('now') AND responded_at IS NOT NULL;
EOF
```

---

## 🔧 운영 명령어 모음

### 대기 요청 모니터링

```bash
# 실시간 모니터링 (5초 갱신)
watch -n 5 'sqlite3 /mnt/e/ai-data/sqlite/security.db \
  "SELECT COUNT(*) as pending FROM approval_requests WHERE status = \"pending\";"'

# 상세 목록
sqlite3 /mnt/e/ai-data/sqlite/security.db \
  "SELECT SUBSTR(request_id,1,8), tool_name, user_id, requested_at \
   FROM approval_requests WHERE status='pending' ORDER BY requested_at;"
```

### 승인/거부 처리

```bash
# 특정 요청 승인 (API 직접 호출)
curl -X POST http://localhost:8020/api/approvals/{request_id}/approve \
  -H "X-User-ID: admin_user" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Approved by operations team"}'

# 특정 요청 거부
curl -X POST http://localhost:8020/api/approvals/{request_id}/reject \
  -H "X-User-ID: admin_user" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Security policy violation"}'
```

### 통계 및 리포팅

```bash
# 주간 요약
sqlite3 /mnt/e/ai-data/sqlite/security.db << 'EOF'
SELECT
  STRFTIME('%Y-W%W', requested_at) as week,
  COUNT(*) as total,
  SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
  ROUND(100.0 * SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) / COUNT(*), 1) as approval_rate
FROM approval_requests
WHERE requested_at > datetime('now', '-4 weeks')
GROUP BY week
ORDER BY week DESC;
EOF

# 도구별 위험도 분석
sqlite3 /mnt/e/ai-data/sqlite/security.db << 'EOF'
SELECT
  tool_name,
  COUNT(*) as requests,
  SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejections,
  ROUND(100.0 * SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) / COUNT(*), 1) as rejection_rate
FROM approval_requests
GROUP BY tool_name
ORDER BY rejection_rate DESC;
EOF
```

### 문제 진단

```bash
# 타임아웃 분석
sqlite3 /mnt/e/ai-data/sqlite/security.db << 'EOF'
SELECT
  request_id,
  tool_name,
  user_id,
  requested_at,
  expires_at,
  CAST((julianday(expires_at) - julianday('now')) * 86400 AS INTEGER) as seconds_until_expiry
FROM approval_requests
WHERE status = 'pending' AND datetime('now') >= expires_at
LIMIT 10;
EOF

# 동시성 문제 확인
sqlite3 /mnt/e/ai-data/sqlite/security.db ".timeout 1000"
SELECT COUNT(*) FROM approval_requests WHERE status = 'pending';

# 데이터베이스 크기
du -h /mnt/e/ai-data/sqlite/security.db*
```

---

## ⚠️ 롤백 절차

### Scenario 1: 승인 워크플로우 비활성화 (급작스러운 문제)

```bash
#!/bin/bash
# 명령어: bash ops/rollback_disable.sh

echo "🔄 승인 워크플로우 비활성화 중..."

# 1. .env 파일 수정
sed -i 's/APPROVAL_WORKFLOW_ENABLED=true/APPROVAL_WORKFLOW_ENABLED=false/' .env

# 2. 서비스 재시작
docker compose -f docker/compose.p3.yml restart mcp-server

# 3. 검증
sleep 5
curl http://localhost:8020/health
echo "✅ 비활성화 완료"

# 4. 알림
echo "⚠️ 모든 HIGH/CRITICAL 도구가 승인 없이 실행됩니다!"
```

### Scenario 2: CLI 호환성 문제 (AI 승인 폴링 실패)

```bash
#!/bin/bash
# 명령어: bash ops/rollback_cli.sh

echo "🔄 CLI를 이전 버전으로 복원..."

# 1. 이전 버전 복원
git checkout HEAD~1 -- scripts/ai.py

# 2. 검증
python scripts/ai.py --help

echo "✅ CLI 복원 완료"
echo "⚠️ 서버는 여전히 승인 워크플로우를 실행합니다"
```

### Scenario 3: 환경 변수 전파 문제

```bash
#!/bin/bash
# 명령어: bash ops/rollback_env.sh

echo "🔄 환경 변수 문제 해결..."

# 1. Docker 컨테이너 중지
docker compose -f docker/compose.p3.yml stop mcp-server

# 2. .env 수정
APPROVAL_WORKFLOW_ENABLED=false

# 3. 컨테이너 제거 후 재시작 (환경 변수 재로드)
docker compose -f docker/compose.p3.yml rm -f mcp-server
docker compose -f docker/compose.p3.yml up -d mcp-server

# 4. 검증
sleep 10
docker logs mcp-server | grep "APPROVAL"

echo "✅ 환경 변수 재설정 완료"
```

---

## 🚨 긴급 연락처

| 상황 | 연락처 | 대응 시간 |
|------|--------|---------|
| **서비스 다운** | On-Call Engineer | 15분 |
| **성능 저하** | DevOps Lead | 30분 |
| **대량 거부** | Security Lead | 1시간 |
| **데이터 손상** | Database Admin | 30분 |

---

## 📚 참고 자료

- **IMPLEMENTATION_SUMMARY.md**: 배포 절차, Feature Flags
- **APPROVAL_GUIDE.md**: 기술 아키텍처, API 명세
- **RBAC_GUIDE.md**: 사용자 권한 관리
- **SECURITY.md**: 전체 보안 시스템 개요

---

## ✅ 운영팀 최종 체크리스트

배포 전에 다음을 모두 확인하세요:

- [ ] 환경 변수 설정 완료 (APPROVAL_WORKFLOW_ENABLED=true)
- [ ] 데이터베이스 백업 생성
- [ ] 롤백 절차 스크립트 준비
- [ ] 운영팀 전원 교육 완료
- [ ] approval_cli.py 도구 테스트 성공
- [ ] 로그 조회 쿼리 동작 확인
- [ ] 일일 점검 스크립트 설정
- [ ] 일일 보고 스크립트 설정
- [ ] 긴급 연락처 공유 완료
- [ ] 승인 워크플로우 활성화 최종 확인
