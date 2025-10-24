# Issue #42 실사용 검증 결과

**이슈**: [Docs] 승인 워크플로우 문서화 및 운영 검증
**검증일**: 2025-10-24 (예정)
**상태**: 검증 계획 수립 완료, 실행 대기

---

## 검증 목표

Issue #42의 Acceptance Criteria 4개를 모두 충족하는지 확인:

- [ ] **AC1**: README, IMPLEMENTATION_SUMMARY, .env.example, Docker Compose 간 `APPROVAL_WORKFLOW_ENABLED=false` 기본값 일관성
- [ ] **AC2**: 운영 담당자가 3단계(준비→진행→점검) 절차를 따라 할 수 있는 가이드
- [ ] **AC3**: 실사용 검증 결과 (테스트 날짜, 실행 명령, 승인/거절 결과, 로그)
- [ ] **AC4**: FAQ (승인 지연, DB 잠금, 플래그 비활성화 시나리오)

---

## 검증 준비 사항

### 환경 요구사항

```
OS: WSL2 Ubuntu
Docker: 20.10+
Python: 3.11+
Git: 최신
Models: /mnt/e/ai-models/에 GGUF 모델 있음
```

### 사전 체크리스트

- [ ] Git 클린 상태 확인: `git status`
- [ ] 기존 Phase 3 스택 정지: `make down-p3`
- [ ] .env 파일 백업: `cp .env .env.backup-pre-validation`
- [ ] 기존 security.db 백업: `cp /mnt/e/ai-data/sqlite/security.db /tmp/security.db.bak`

---

## 검증 시나리오

### 시나리오 1: 기본 설정 확인 (AC1)

**목표**: 문서 일관성 확인

#### 1.1 README.md 확인

```bash
# 실행
grep -n "APPROVAL_WORKFLOW_ENABLED" README.md

# 예상 결과
# README.md에서 "APPROVAL_WORKFLOW_ENABLED=false" (기본값) 명시 확인
```

**검증 결과**:
- [ ] ✅ README.md에 승인 워크플로우 섹션 존재
- [ ] ✅ 기본값 `false` 명시됨
- [ ] ✅ 프로덕션 활성화 방법 설명됨

#### 1.2 IMPLEMENTATION_SUMMARY.md 확인

```bash
# 실행
grep -n "APPROVAL_WORKFLOW_ENABLED" docs/security/IMPLEMENTATION_SUMMARY.md

# 예상 결과
# docs/security/IMPLEMENTATION_SUMMARY.md에서 "APPROVAL_WORKFLOW_ENABLED=false" 명시 및 배포 체크리스트 존재
```

**검증 결과**:
- [ ] ✅ Production Deployment Checklist 섹션 존재
- [ ] ✅ 사전/배포/사후 점검 항목 포함
- [ ] ✅ 롤백 절차 명확함

#### 1.3 .env.example 확인

```bash
# 실행
grep -A 10 "APPROVAL_WORKFLOW_ENABLED" .env.example

# 예상 결과
# .env.example에서 기본값 false 및 프로덕션 활성화 가이드 확인
```

**검증 결과**:
- [ ] ✅ APPROVAL_WORKFLOW_ENABLED=false (기본값)
- [ ] ✅ 프로덕션 활성화 단계 설명됨
- [ ] ✅ 관련 문서 링크 제공됨

#### 1.4 docker/compose.p3.yml 확인

```bash
# 실행
grep -n "APPROVAL_WORKFLOW_ENABLED" docker/compose.p3.yml

# 예상 결과
# ${APPROVAL_WORKFLOW_ENABLED:-false} (기본값 false)
```

**검증 결과**:
- [ ] ✅ Docker Compose에서 기본값 false로 설정
- [ ] ✅ .env 파일의 값을 사용

---

### 시나리오 2: 운영 가이드 존재 (AC2)

**목표**: 3단계 절차 가이드 확인

#### 2.1 운영 가이드 파일 존재

```bash
# 실행
test -f docs/runbooks/approval_workflow.md && echo "✅ 파일 존재" || echo "❌ 파일 없음"

# 예상 결과
# ✅ 파일 존재
```

**검증 결과**:
- [ ] ✅ docs/runbooks/approval_workflow.md 파일 존재
- [ ] ✅ 파일 크기 > 500줄
- [ ] ✅ 3단계 구조 명확함 (준비→진행→점검)

#### 2.2 각 단계별 내용 확인

```bash
# 실행
grep -n "^## 단계" docs/runbooks/approval_workflow.md

# 예상 결과
# ## 단계 1: 준비 (Preparation)
# ## 단계 2: 진행 (Execution)
# ## 단계 3: 점검 (Verification)
```

**검증 결과**:
- [ ] ✅ 단계 1: 준비
  - [ ] ✅ DB 준비 (시딩, 검증)
  - [ ] ✅ 환경 변수 설정
  - [ ] ✅ 서비스 시작
  - [ ] ✅ 백업 설정

- [ ] ✅ 단계 2: 진행
  - [ ] ✅ 승인 요청 생성 방법
  - [ ] ✅ approval_cli.py 사용법
  - [ ] ✅ 승인/거부 처리
  - [ ] ✅ 자동 재실행

- [ ] ✅ 단계 3: 점검
  - [ ] ✅ 감사 로그 확인
  - [ ] ✅ 성능 메트릭
  - [ ] ✅ 헬스 체크

#### 2.3 FAQ 확인

```bash
# 실행
grep -n "^### Q" docs/runbooks/approval_workflow.md | head -5

# 예상 결과
# Q1: 승인 요청이 지연되는 경우
# Q2: DB 잠금 오류 발생 시
# Q3: 플래그 비활성화 후 동작 확인
```

**검증 결과**:
- [ ] ✅ Q1: 승인 지연 (Issue AC4 요구사항)
- [ ] ✅ Q2: DB 잠금 (Issue AC4 요구사항)
- [ ] ✅ Q3: 플래그 비활성화 (Issue AC4 요구사항)
- [ ] ✅ Q4: 대량 승인 요청
- [ ] ✅ Q5: 긴급 롤백

---

### 시나리오 3: 실사용 검증 테스트 (AC3)

**목표**: 승인 워크플로우 실제 동작 확인

#### 준비 단계

```bash
# 1. 테스트 환경 준비
make down-p3

# 2. .env 파일 수정 (APPROVAL_WORKFLOW_ENABLED=true)
sed -i 's/APPROVAL_WORKFLOW_ENABLED=false/APPROVAL_WORKFLOW_ENABLED=true/g' .env

# 3. DB 초기화
python services/mcp-server/scripts/seed_security_data.py --reset

# 4. Phase 3 스택 시작
make up-p3

# 5. 서비스 헬스 체크
sleep 10
curl http://localhost:8020/health | jq .

# 예상 응답:
# {
#   "status": "healthy",
#   "rbac_enabled": true,
#   "approval_workflow_enabled": true,
#   "db_available": true
# }
```

**테스트 1: 승인 성공 흐름**

```bash
# Terminal A (사용자)
# 시간: 2025-10-24 XX:XX:XX

python scripts/ai.py --mcp execute_python \
  --mcp-args '{"code": "import os\nprint(os.getcwd())", "timeout": 30}'

# 예상 응답:
# ⏳ Approval pending for HIGH/CRITICAL tool
# Tool: execute_python
# Request ID: 550e8400-e29b-41d4-a716-446655440000
# Expires in: 5:00
# ⏳ Waiting for approval...
# [████░░░░░] 40% (300 seconds left)

# Terminal B (관리자)
# 시간: 2025-10-24 XX:XX:15 (+15초)

python scripts/approval_cli.py

# 상호작용:
# Enter request ID or number: 1
# (A)pprove, (R)eject, (S)kip: a

# DB 확인
sqlite3 /mnt/e/ai-data/sqlite/security.db \
  "SELECT request_id, status, responder_id FROM approval_requests \
   WHERE request_id='550e8400-e29b-41d4-a716-446655440000';"

# 예상 결과:
# 550e8400-e29b-41d4-a716-446655440000|approved|admin_user

# Terminal A (계속 대기 중)
# 자동으로 승인 감지 후 재실행
# ✅ Request approved!
# Executing: execute_python
# /mnt/e/worktree/issue-42
# ✅ Command completed successfully
```

**검증 결과 - 시나리오 1 (승인 성공)**:

| 항목 | 예상 | 실제 | 결과 |
|------|------|------|------|
| 403 응답 | 받음 | ? | [ ] |
| Request ID 생성 | 됨 | ? | [ ] |
| approval_requests 테이블 pending 레코드 | 있음 | ? | [ ] |
| approval_cli.py 실행 | 성공 | ? | [ ] |
| 승인 처리 | 성공 | ? | [ ] |
| 자동 폴링 감지 | 됨 | ? | [ ] |
| 자동 재실행 | 됨 | ? | [ ] |
| 최종 결과 출력 | 정상 | ? | [ ] |

**테스트 2: 승인 거부 흐름**

```bash
# Terminal A (사용자)
python scripts/ai.py --mcp execute_python \
  --mcp-args '{"code": "import os", "timeout": 30}'

# Terminal B (관리자) - 거부 처리
python scripts/approval_cli.py
# (A)pprove, (R)eject, (S)kip: r

# Terminal A (예상 응답)
# ❌ Request rejected!
# Reason: (거부 사유)
# ❌ Command execution cancelled
```

**검증 결과 - 시나리오 2 (거부)**:

| 항목 | 예상 | 실제 |
|------|------|------|
| 요청 상태 변경 (rejected) | 됨 | ? |
| CLI 오류 메시지 표시 | 됨 | ? |
| 감사 로그 기록 | 됨 | ? |

**테스트 3: 플래그 비활성화 흐름**

```bash
# .env 파일 수정
sed -i 's/APPROVAL_WORKFLOW_ENABLED=true/APPROVAL_WORKFLOW_ENABLED=false/g' .env

# 서비스 재시작
make down-p3 && make up-p3
sleep 10

# 즉시 실행 테스트
python scripts/ai.py --mcp execute_python \
  --mcp-args '{"code": "print(\"Test\")", "timeout": 30}'

# 예상 결과:
# Test
# (즉시 실행, 승인 없음)
```

**검증 결과 - 시나리오 3 (플래그 비활성화)**:

| 항목 | 예상 | 실제 |
|------|------|------|
| 즉시 실행 (승인 없음) | 됨 | ? |
| 403 응답 없음 | 맞음 | ? |

---

## 로그 수집

### 감사 로그 조회

```bash
# 감사 로그 확인
sqlite3 /mnt/e/ai-data/sqlite/security.db << 'EOF'
.mode column
.headers on
SELECT timestamp, user_id, tool_name, status FROM security_audit_logs
WHERE DATE(timestamp)=DATE('now')
ORDER BY timestamp DESC;
EOF

# 예상 결과:
# timestamp                | user_id  | tool_name      | status
# 2025-10-24 XX:XX:XX      | dev_user | execute_python | denied
# 2025-10-24 XX:XX:XX      | dev_user | execute_python | approved
# 2025-10-24 XX:XX:XX      | dev_user | execute_python | requested
```

**검증 결과 - 감사 로그**:
- [ ] ✅ 요청 기록 (requested)
- [ ] ✅ 승인 기록 (approved)
- [ ] ✅ 거부 기록 (rejected)
- [ ] ✅ 타임스탬프 정확
- [ ] ✅ 사용자 ID 정확

### 성능 메트릭

```bash
# 승인 처리 시간 측정
sqlite3 /mnt/e/ai-data/sqlite/security.db << 'EOF'
SELECT
  ROUND(AVG((julianday(responded_at) - julianday(requested_at)) * 86400), 2) as avg_sec,
  MIN((julianday(responded_at) - julianday(requested_at)) * 86400) as min_sec,
  MAX((julianday(responded_at) - julianday(requested_at)) * 86400) as max_sec
FROM approval_requests
WHERE status IN ('approved', 'rejected') AND DATE(responded_at)=DATE('now');
EOF

# 예상 결과:
# avg_sec | min_sec | max_sec
# 15.3    | 2.1     | 120.5
```

**검증 결과 - 성능**:
- [ ] ✅ 평균 승인 시간 < 30초
- [ ] ✅ DB 쿼리 성능 < 100ms
- [ ] ✅ CLI 폴링 정상 작동 (1초 간격)

### 스크린샷 수집

검증 시 다음 항목의 스크린샷 또는 로그 저장:

```bash
# 1. 승인 CLI UI
# → approval_cli.py 실행 화면

# 2. 사용자 CLI 폴링
# → python scripts/ai.py --mcp execute_python 실행 및 대기 화면

# 3. DB 쿼리 결과
# → sqlite3 명령어 출력

# 4. 헬스 체크 응답
# → curl http://localhost:8020/health 응답
```

---

## 검증 체크리스트

### AC1: 문서 일관성
- [ ] README.md: APPROVAL_WORKFLOW_ENABLED=false 명시
- [ ] IMPLEMENTATION_SUMMARY.md: 배포 체크리스트 포함
- [ ] .env.example: 기본값 false + 프로덕션 가이드
- [ ] docker/compose.p3.yml: 기본값 false

### AC2: 운영 가이드 (3단계)
- [ ] 단계 1 준비: DB 시딩, 환경 설정, 서비스 시작
- [ ] 단계 2 진행: 요청 생성, CLI 사용, 승인 처리
- [ ] 단계 3 점검: 감사 로그, 성능, 헬스 체크

### AC3: 실사용 검증
- [ ] 시나리오 1: 승인 성공 (8개 항목)
- [ ] 시나리오 2: 승인 거부 (3개 항목)
- [ ] 시나리오 3: 플래그 비활성화 (2개 항목)
- [ ] 감사 로그 수집 (5개 항목)
- [ ] 성능 메트릭 (3개 항목)

### AC4: FAQ
- [ ] Q1: 승인 지연 (문제, 원인, 해결책)
- [ ] Q2: DB 잠금 (문제, 원인, 해결책)
- [ ] Q3: 플래그 비활성화 (절차)
- [ ] 추가 Q4, Q5: 대량 요청, 긴급 롤백

---

## 최종 정리

### 테스트 환경 정리

```bash
# 1. 원래 .env 파일 복구
sed -i 's/APPROVAL_WORKFLOW_ENABLED=true/APPROVAL_WORKFLOW_ENABLED=false/g' .env

# 2. Phase 3 스택 정지 (선택)
make down-p3

# 3. security.db 원래대로 (선택)
# rm /mnt/e/ai-data/sqlite/security.db
# cp /tmp/security.db.bak /mnt/e/ai-data/sqlite/security.db
```

### 검증 결과 요약

- **총 체크리스트 항목**: 24개 (AC1 4개 + AC2 3개 + AC3 13개 + AC4 4개)
- **예상 통과율**: 100% (모든 항목 통과 예상)
- **예상 검증 시간**: 1-2시간 (테스트 3개 시나리오 + 로그 수집)

### 다음 단계

1. ✅ 문서 업데이트 완료 (Phase 2)
2. ✅ 운영 가이드 작성 완료 (Phase 3)
3. ⏳ 실사용 검증 (Phase 4) ← **현재 단계**
4. ⏳ PR 생성 및 병합

---

**Document Version**: 1.0
**Last Updated**: 2025-10-24
**Author**: Claude Code
**Status**: 검증 계획 수립 완료, 실행 대기 (테스트 환경 필요)

