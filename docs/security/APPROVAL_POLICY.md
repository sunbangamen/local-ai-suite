# 승인 워크플로우 운영 정책 (Issue #26)

**문서**: APPROVAL_POLICY.md
**작성일**: 2025-10-20
**버전**: 1.0
**상태**: 프로덕션 준비 완료

---

## 📋 Overview

이 문서는 MCP 서버의 보안 승인 워크플로우 운영 정책을 정의합니다. HIGH/CRITICAL 등급 도구 실행 시 관리자 승인을 요구하는 프로세스를 각 환경별로 관리합니다.

---

## 🔧 Feature Flag Policy

### Development Environment

**설정**:
```bash
APPROVAL_WORKFLOW_ENABLED=false  # 기본값
RBAC_ENABLED=false              # 개발 편의성
```

**목적**: 개발자의 빠른 반복 개발 지원

**특징**:
- ✅ 승인 워크플로우 완전 비활성화
- ✅ RBAC 시스템 비활성화
- ✅ 모든 도구 무제한 접근 가능

**언제 사용**: 로컬 개발, 테스트, 프로토타이핑

**설정 방법**:
```bash
# .env (로컬 개발)
APPROVAL_WORKFLOW_ENABLED=false
RBAC_ENABLED=false
docker-compose -f docker/compose.p3.yml up -d mcp-server
```

---

### Staging Environment

**설정**:
```bash
APPROVAL_WORKFLOW_ENABLED=true   # 필수 활성화
RBAC_ENABLED=true                # 필수 활성화
APPROVAL_TIMEOUT=600             # 10분 (관리자 대응 시간)
APPROVAL_POLLING_INTERVAL=1      # 1초
```

**목적**: 프로덕션과 동일한 보안 정책 검증

**특징**:
- ✅ HIGH/CRITICAL 도구 승인 필요
- ✅ 역할 기반 접근 제어 (RBAC) 활성화
- ✅ 관리자 승인 필수
- ✅ 감사 로깅 기록

**언제 사용**: 프로덕션 배포 전 최종 테스트, 보안 검증

**설정 방법**:
```bash
# .env.staging
APPROVAL_WORKFLOW_ENABLED=true
RBAC_ENABLED=true
APPROVAL_TIMEOUT=600
docker-compose -f docker/compose.p3.yml up -d mcp-server
```

**테스트 시나리오**:
1. HIGH 등급 도구 실행 요청 → 승인 대기
2. 관리자 승인 CLI에서 승인
3. 사용자에게 즉시 도구 실행 완료
4. 감사 로그 확인

---

### Production Environment

**설정**:
```bash
APPROVAL_WORKFLOW_ENABLED=true   # 필수 활성화
RBAC_ENABLED=true                # 필수 활성화
APPROVAL_TIMEOUT=600             # 10분 (관리자 대응 시간)
APPROVAL_POLLING_INTERVAL=1      # 1초
APPROVAL_MAX_PENDING=50          # 동시 승인 요청 제한
```

**목적**: 보안 필수 요구사항으로 운영

**특징**:
- ✅ HIGH/CRITICAL 도구 승인 필수
- ✅ 역할 기반 접근 제어 (RBAC) 필수
- ✅ 모든 접근 감시 및 감사 로깅
- ✅ 성능 최적화 (동시 요청 제한)

**배포 체크리스트**:
- [ ] 환경 변수 설정 확인
- [ ] 관리자 역할 및 권한 설정 완료
- [ ] 승인자 1명 이상 준비
- [ ] CLI 모니터링 도구 설치 (`scripts/approval_cli.py`)
- [ ] 감사 로그 저장소 확인
- [ ] 롤백 절차 문서화

**설정 방법**:
```bash
# .env.production
APPROVAL_WORKFLOW_ENABLED=true
RBAC_ENABLED=true
APPROVAL_TIMEOUT=600
APPROVAL_POLLING_INTERVAL=1
APPROVAL_MAX_PENDING=50

# Docker 배포
docker-compose -f docker/compose.p3.yml up -d
```

---

## 📊 정책 비교표

| 항목 | Development | Staging | Production |
|------|-------------|---------|------------|
| Approval | ❌ 비활성화 | ✅ 활성화 | ✅ 활성화 |
| RBAC | ❌ 비활성화 | ✅ 활성화 | ✅ 활성화 |
| 타임아웃 | 없음 | 10분 | 10분 |
| 감사 로깅 | ❌ 비활성화 | ✅ 활성화 | ✅ 활성화 |
| 관리자 필요 | ❌ 없음 | ✅ 필수 | ✅ 필수 |
| 의도 | 빠른 개발 | 보안 검증 | 보안 운영 |

---

## 🚀 배포 및 전환

### Development → Staging

**단계**:
1. Staging 환경 구성 (별도 서버 또는 컨테이너)
2. `.env.staging` 설정 파일 생성
3. MCP 서버 재시작
4. 승인자 CLI 실행 (`python scripts/approval_cli.py`)
5. 테스트 시나리오 실행

**전환 시 주의사항**:
- ⚠️ 기존 pending 요청 정리 필요
- ⚠️ RBAC DB 초기화 필요
- ⚠️ 관리자 계정 생성 필수

**체크 커맨드**:
```bash
# Approval 활성화 확인
curl http://localhost:8020/health | grep approval

# RBAC 활성화 확인
curl http://localhost:8020/api/approvals/pending \
  -H "X-User-ID: admin"

# Expected response: 200 OK
```

---

### Staging → Production

**사전 준비**:
- [ ] Staging 테스트 완료
- [ ] 모든 시나리오 통과 (5/5)
- [ ] 관리자 인수인계 완료
- [ ] 감시 대시보드 설정 완료
- [ ] 롤백 플랜 검증

**배포 단계**:
1. Production 환경에 `.env.production` 배포
2. Docker 이미지 배포
3. 헬스 체크 확인
4. 관리자 승인 CLI 상시 운영 시작
5. 모니터링 및 로그 확인

**배포 후 모니터링** (첫 24시간):
```bash
# 1. Pending 요청 수 확인
sqlite3 /mnt/e/ai-data/sqlite/security.db \
  "SELECT COUNT(*) FROM approval_requests WHERE status='pending';"

# 2. 최근 승인 히스토리
sqlite3 /mnt/e/ai-data/sqlite/security.db \
  "SELECT * FROM approval_requests ORDER BY requested_at DESC LIMIT 10;"

# 3. 감사 로그
curl http://localhost:8020/security/logs/audit?limit=50 | jq
```

---

## 🔄 Rollback Procedure

### 상황 1: 승인 워크플로우로 인한 서비스 중단

**증상**: 사용자가 도구 실행 불가, "Approval Required" 계속 표시

**롤백 단계** (< 5분):
```bash
# 1. 환경 변수 변경
APPROVAL_WORKFLOW_ENABLED=false

# 2. MCP 서버 재시작
docker-compose -f docker/compose.p3.yml restart mcp-server

# 3. 헬스 체크
curl http://localhost:8020/health

# 4. Pending 요청 정리 (선택)
sqlite3 /mnt/e/ai-data/sqlite/security.db \
  "UPDATE approval_requests SET status='expired' WHERE status='pending';"
```

**확인**:
- ✅ 도구 실행 정상
- ✅ 승인 프롬프트 없음

---

### 상황 2: 승인 API 500 에러

**증상**: `/api/approvals/pending` 500 응답

**롤백 단계**:
```bash
# 1. 이전 Docker 이미지로 롤백
docker-compose -f docker/compose.p3.yml stop mcp-server
docker-compose -f docker/compose.p3.yml rm mcp-server
docker pull <registry>/mcp-server:previous-tag
docker-compose -f docker/compose.p3.yml up -d

# 2. 헬스 체크
curl http://localhost:8020/health
```

---

### 상황 3: 승인 요청 대량 누적

**증상**: Pending 요청 > 50개, DB 락 발생

**정리 단계**:
```bash
# 1. 만료된 요청 자동 정리
python services/mcp-server/scripts/cleanup_approvals.py

# 또는 수동으로:
sqlite3 /mnt/e/ai-data/sqlite/security.db << EOF
UPDATE approval_requests
SET status='expired'
WHERE status='pending'
  AND datetime('now') > expires_at;

VACUUM;
EOF

# 2. 상태 확인
sqlite3 /mnt/e/ai-data/sqlite/security.db \
  "SELECT status, COUNT(*) FROM approval_requests GROUP BY status;"
```

---

## 👥 관리자 운영 절차

### 승인자 역할 및 권한

**필요한 권한**:
- `approval.view`: 대기 승인 목록 조회
- `approval.manage`: 승인/거부 처리
- `admin` 역할 필수

**승인자 계정 생성**:
```bash
# RBAC DB에 관리자 계정 추가
cd services/mcp-server
python scripts/seed_security_data.py --add-user admin_john admin

# 또는 직접 SQL:
sqlite3 /mnt/e/ai-data/sqlite/security.db << EOF
INSERT INTO security_users (user_id, role, is_active)
VALUES ('admin_john', 'admin', 1);
EOF
```

---

### 일일 운영

**아침 시작**:
```bash
# 승인 CLI 시작 (항상 켜져 있어야 함)
cd /mnt/e/worktree/issue-26
python scripts/approval_cli.py --continuous

# 또는 tmux/screen에서:
tmux new-session -d -s approval "python scripts/approval_cli.py --continuous"
```

**요청 처리**:
1. 대기 중인 요청 목록 확인
2. 요청 상세 정보 검토
3. 승인/거부 선택
4. 사유 기입
5. 완료

**모니터링**:
```bash
# 실시간 pending 요청 수
watch -n 5 'sqlite3 /mnt/e/ai-data/sqlite/security.db \
  "SELECT COUNT(*) as pending FROM approval_requests WHERE status='\''pending'\'';"'
```

---

## 🛡️ 보안 주의사항

### 꼭 지켜야 할 사항

1. **승인자 계정 보안**
   - ⚠️ 승인자 비밀번호 정기 변경 (월 1회)
   - ⚠️ 승인자 계정 접근 제한
   - ⚠️ 승인 CLI 실행 서버 보안

2. **감사 로그 관리**
   - ⚠️ 감사 로그 정기 백업 (일 1회)
   - ⚠️ 로그 보존 기간 설정 (최소 90일)
   - ⚠️ 접근 권한 제한 (admin만)

3. **승인 정책 준수**
   - ⚠️ 5분 이상 미응답 요청 타임아웃 자동 처리
   - ⚠️ 승인 이유 반드시 기록
   - ⚠️ 의심 요청 거부 - 먼저 사용자 확인

---

## 📞 Troubleshooting

### Q1: "Approval workflow is disabled"

**원인**: `APPROVAL_WORKFLOW_ENABLED=false`

**해결**:
```bash
# .env에서 설정 변경
APPROVAL_WORKFLOW_ENABLED=true
docker-compose restart mcp-server
```

---

### Q2: 승인 요청이 타임아웃됨

**원인**: 관리자가 시간 내 응답하지 않음

**해결**:
```bash
# 타임아웃 시간 연장
APPROVAL_TIMEOUT=900  # 15분

# 또는 관리자 추가 배치
python scripts/approval_cli.py --responder admin_jane
```

---

### Q3: CLI에서 승인 감지 안 됨

**원인**: Status API 미응답

**해결**:
```bash
# 1. API 상태 확인
curl http://localhost:8020/health

# 2. MCP 서버 재시작
docker-compose restart mcp-server

# 3. DB 정합성 확인
sqlite3 /mnt/e/ai-data/sqlite/security.db \
  "PRAGMA integrity_check;"
```

---

## 📊 운영 권장치 (Phase 5 벤치마크 기반)

### 성능 기준 (SQLite WAL 모드)

**처리량**:
```
안정적 처리 범위:  10-50 RPS
  - 안전 범위: 10-25 RPS (여유도 50% 이상)
  - 최대 처리: 50 RPS (벤치마크 실측)
  - 피크 대응: 50 RPS까지 안정적 처리 가능

권장 설정:
  - 프로덕션: 10-25 RPS (안전 범위)
  - 스테이징: 25-50 RPS (테스트 범위)
```

**레이턴시**:
```
성능 지표 (ms):
  - 평균: ~71ms (우수)
  - P95: ~397ms (목표 < 500ms 충족)
  - P99: ~439ms (양호)
  - 최대: ~474ms (허용)

권장치:
  - 응답 시간: < 100ms (평상시)
  - 타임아웃: 600초 (여유도 포함)
  - 폴링 간격: 1초 (변경 불필요)
```

**안정성**:
```
신뢰성 지표:
  - 성공률: 100% (벤치마크 실측)
  - 오류율: 0% (완벽한 안정성)
  - 가용성: 99.9%+ 기대 가능

설정:
  - 승인 타임아웃: 300초 (표준)
  - 재시도 로직: 자동 3회 (기본값 유지)
  - 배치 처리: 100개 이상 권장
```

### 데이터베이스 관리

**백업**:
```
- 일일 1회 이상 (권장: 매 4시간)
- WAL 파일 정리: 주간 1회
- 전체 DB 점검: 월간 1회
```

**모니터링**:
```
- 쿼리 응답 시간: 일일 모니터링
- DB 용량 증가: 주간 검토
- 에러율: 실시간 모니터링
- 성능 메트릭: 월간 분석
```

### 운영 가이드

| 상황 | 조치 | 예상 시간 |
|------|------|----------|
| **성능 저하** | 1) DB 통계 갱신 2) 인덱스 재구성 | 5-15분 |
| **고장 복구** | 1) 최근 백업 복원 2) 재시작 | 10-30분 |
| **용량 증가** | 1) 정리 작업 2) 보관 3) 보류 | 30-60분 |
| **타임아웃 증가** | 1) 로드 분산 2) 설정 조정 3) HW 확대 | 분석 후 |

---

## 📚 관련 문서

- [APPROVAL_GUIDE.md](./APPROVAL_GUIDE.md) - 사용자 가이드
- [SECURITY.md](./SECURITY.md) - 보안 시스템 개요
- [RBAC_GUIDE.md](./RBAC_GUIDE.md) - 역할 기반 접근 제어
- [Phase 5 벤치마크](../benchmarks/approval_workflow_phase5.md) - 성능 벤치마크 결과
- [Issue #26](https://github.com/sunbangamen/local-ai-suite/issues/26) - 구현 계획

---

**최종 업데이트**: 2025-10-20
**상태**: ✅ Phase 5 벤치마크 완료 (모든 기준 충족)

---

## 🔄 Change Log

**2025-10-20**: 초안 작성
- 환경별 feature flag 정책 정의
- 배포 및 전환 절차 문서화
- 롤백 절차 정의
- Troubleshooting 추가

**예정**: 프로덕션 배포 후 피드백 반영
