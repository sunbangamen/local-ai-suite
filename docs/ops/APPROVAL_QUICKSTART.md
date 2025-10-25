# 승인 워크플로우 빠른 시작 가이드 (Issue #45 Phase 6.3)

## 개요

Local AI Suite의 승인 워크플로우는 HIGH/CRITICAL 도구 실행을 관리자의 명시적 승인으로 제어합니다.

## 1️⃣ 활성화 확인

### 환경 변수 설정
```bash
export APPROVAL_WORKFLOW_ENABLED=true
```

### 상태 확인
```bash
curl http://localhost:8020/health
# 응답에서 "approval_workflow_enabled": true 확인
```

## 2️⃣ 승인 요청 흐름

### 사용자 관점
```bash
# 승인이 필요한 도구 실행 (예: git_commit)
ai --mcp git_commit --mcp-args '{"message": "fix: issue #123"}'

# 응답: 승인 대기 중 메시지
# Request ID: 550e8400-1234
# Status: Pending approval
# Expires in: 5 minutes
# Polling... (1초 간격)

# 관리자가 승인하면 자동으로 진행
```

### 관리자 관점
```bash
# 대기 중인 승인 목록 확인
python scripts/approval_admin.py list

# 승인 ID로 승인 처리
python scripts/approval_admin.py approve 550e8400-1234 \
  --reason "Approved for scheduled maintenance"

# 또는 거부
python scripts/approval_admin.py reject 550e8400-1234 \
  --reason "Does not meet security policy"
```

## 3️⃣ REST API 사용

### API Key 생성
```bash
# 기본 API Key (개발용)
API_KEY="approval-admin-001"
```

### 승인 목록 조회
```bash
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8020/api/v1/approvals?status=pending

# 응답:
# {
#   "approvals": [...],
#   "total": 5,
#   "limit": 50,
#   "offset": 0
# }
```

### 승인 처리
```bash
curl -X PUT \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  http://localhost:8020/api/v1/approvals/{request_id} \
  -d '{
    "action": "approve",
    "reason": "Approved for automated testing"
  }'
```

### 통계 조회
```bash
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8020/api/v1/approvals/stats

# 응답:
# {
#   "total_requests": 157,
#   "pending_count": 5,
#   "approved_count": 135,
#   "rejected_count": 12,
#   "expired_count": 5,
#   "approval_rate": 0.918,
#   "avg_response_time_seconds": 120.45
# }
```

## 4️⃣ 모니터링

### Grafana 대시보드 접속
- **URL**: http://localhost:3001
- **로그인**: admin / admin
- **대시보드**: Approval Workflow Metrics

### 주요 메트릭
- **승인 대기 시간 (p95)**: 목표 < 2분
- **승인 성공률**: 목표 > 95%
- **타임아웃 발생**: 실시간 감지

### Prometheus 쿼리
```promql
# 승인 요청 상태별 분포
sum by (status) (approval_requests_total)

# 평균 응답 시간
rate(approval_response_time_seconds_sum[5m]) /
rate(approval_response_time_seconds_count[5m])

# 거부율
sum(rate(approval_requests_total{status="rejected"}[5m])) /
sum(rate(approval_requests_total[5m]))
```

## 5️⃣ 운영 팁

### 승인 타임아웃 설정
```bash
# .env 파일에서 설정
APPROVAL_TIMEOUT_SECONDS=300  # 5분

# 재시작 후 적용
docker restart mcp-server
```

### 정책 기반 자동 승인 (향후)
```python
# 향후 버전에서 지원할 예정
APPROVAL_AUTO_APPROVE_PATTERNS = [
  "^read_file:.*",  # 파일 읽기는 자동 승인
  "^git_status$",   # 상태 조회는 자동 승인
]
```

### 감사 로그 확인
```bash
# SQLite 데이터베이스에서 직접 조회
sqlite3 /mnt/e/ai-data/security.db

# SQL 쿼리 예시:
# SELECT * FROM audit_logs
# WHERE action='approval_granted'
# ORDER BY timestamp DESC LIMIT 10;
```

## 6️⃣ 문제 해결

### 승인 요청이 생성되지 않음
```bash
# 1. 워크플로우 활성화 확인
echo $APPROVAL_WORKFLOW_ENABLED

# 2. 도구가 HIGH/CRITICAL 레벨인지 확인
curl http://localhost:8020/tool-info/git_commit | grep approval_required

# 3. 데이터베이스 연결 확인
sqlite3 /mnt/e/ai-data/security.db ".tables"
```

### 승인 폴링이 작동 안 함
```bash
# 1. MCP 서버 헬스 확인
curl http://localhost:8020/health

# 2. 방화벽/포트 확인
netstat -tulpn | grep 8020

# 3. 로그 확인
docker logs mcp-server | grep -i approval
```

### API Key 문제
```bash
# 1. 기본 API Key 사용 가능 확인
# 기본값: approval-admin-001

# 2. 또는 API Key 생성
# (향후 버전에서 관리 API 제공 예정)
```

## 7️⃣ 추가 리소스

- **API 문서**: http://localhost:8020/docs (Swagger UI)
- **OpenAPI 스펙**: `/docs/api/APPROVAL_API_SPEC.yaml`
- **구현 가이드**: `/docs/security/IMPLEMENTATION_SUMMARY.md`
- **RBAC 가이드**: `/docs/security/RBAC_GUIDE.md`
- **운영 가이드**: `/docs/ops/SERVICE_RELIABILITY.md`
