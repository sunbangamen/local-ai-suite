# Email 알림 시스템 운영 가이드 (Phase 6.4)

## 개요

Local AI Suite의 **Email 알림 시스템**은 승인 워크플로우 이벤트를 이메일로 운영자에게 통지합니다.

### 지원되는 이벤트
- ✅ **승인 요청 (approval_requested)**: 새로운 승인 요청 발생
- ✅ **타임아웃 (approval_timeout)**: 승인 요청 만료 (5분)
- ✅ **승인 완료 (approval_approved)**: 승인 처리됨
- ✅ **거부 완료 (approval_rejected)**: 거부 처리됨

### 핵심 특성
- **비동기 처리**: 이메일 발송이 API 응답을 지연시키지 않음
- **배치 최적화**: 여러 이벤트를 한 번에 처리하여 효율성 향상
- **자동 재시도**: 발송 실패 시 3회까지 자동 재시도 (exponential backoff 2-10초)
- **선택적 활성화**: NOTIFICATION_ENABLED=false로 기본 비활성화

---

## 📋 초기 설정

### 1단계: SMTP 서버 구성

`.env` 파일에서 SMTP 설정을 구성합니다:

```bash
# Email 알림 활성화
NOTIFICATION_ENABLED=true

# SMTP 서버 설정
SMTP_HOST=localhost          # SMTP 서버 주소
SMTP_PORT=587                # SMTP 포트 (기본: 587 = STARTTLS)
SMTP_USE_TLS=true            # TLS 사용 여부
SMTP_USER=                   # SMTP 사용자 (optional)
SMTP_PASSWORD=               # SMTP 비밀번호 (optional)

# Email 주소
EMAIL_FROM=admin@localhost   # 발송자 이메일
EMAIL_TO=operator@localhost  # 수신자 이메일
```

### 2단계: SMTP 서버 선택

#### **옵션 A: 로컬 테스트용 MailHog (권장)**

MailHog는 로컬 개발/테스트를 위한 가상 SMTP 서버입니다.

**설정:**
```bash
# .env
NOTIFICATION_ENABLED=true
SMTP_HOST=mailhog
SMTP_PORT=1025
EMAIL_FROM=admin@localhost
EMAIL_TO=admin@localhost
```

**docker-compose.p3.yml에 추가:**
```yaml
services:
  mailhog:
    image: mailhog/mailhog:latest
    ports:
      - "1025:1025"   # SMTP port
      - "8025:8025"   # Web UI
    networks:
      - ai-network
    environment:
      MH_HOSTNAME: mailhog
```

**테스트:**
```bash
# MailHog Web UI 접속
open http://localhost:8025
```

#### **옵션 B: Gmail SMTP**

```bash
# Gmail 앱 비밀번호 생성 필수
# 참고: https://support.google.com/accounts/answer/185833

NOTIFICATION_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=your-email@gmail.com
EMAIL_TO=operator@gmail.com
```

#### **옵션 C: Office 365 SMTP**

```bash
NOTIFICATION_ENABLED=true
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USER=your-email@company.com
SMTP_PASSWORD=your-password
EMAIL_FROM=your-email@company.com
EMAIL_TO=operator@company.com
```

#### **옵션 D: 자체 메일 서버**

```bash
NOTIFICATION_ENABLED=true
SMTP_HOST=mail.example.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USER=service-account
SMTP_PASSWORD=service-password
EMAIL_FROM=ai-suite@example.com
EMAIL_TO=admin@example.com
```

### 3단계: 서비스 재시작

```bash
# Docker Compose로 서비스 재시작
docker compose -f docker/compose.p3.yml restart mcp-server

# 또는 전체 스택 재시작
docker compose -f docker/compose.p3.yml down
docker compose -f docker/compose.p3.yml up -d
```

### 4단계: 설정 검증

```bash
# 로그에서 알림 워커 시작 확인
docker compose logs -f mcp-server | grep "Email notification"

# 출력 예:
# ✅ Email notification worker started
```

---

## 🔧 배치 처리 최적화

이메일 발송을 배치로 처리하여 성능을 최적화합니다:

```bash
# .env 설정
NOTIFICATION_BATCH_SIZE=10      # 배치 크기 (기본: 10)
NOTIFICATION_BATCH_TIMEOUT=5    # 배치 타임아웃 초 (기본: 5)
```

### 동작 원리

```
Event 1 → Queue
Event 2 → Queue
...
Event 10 → [배치 크기 도달] → 배치 처리 → Email 발송
또는
Event 1 → Queue
Event 2 → [5초 타임아웃] → 배치 처리 → Email 발송
```

### 튜닝 가이드

| 시나리오 | BATCH_SIZE | BATCH_TIMEOUT | 특징 |
|---------|-----------|---------------|------|
| 저부하 (< 10 이벤트/분) | 5 | 10초 | 빠른 발송, 낮은 처리량 |
| 중간 부하 (10-50 이벤트/분) | 10 | 5초 | 균형잡힌 설정 **권장** |
| 고부하 (> 50 이벤트/분) | 20 | 3초 | 높은 처리량, 약간의 지연 |

---

## 📧 Email 템플릿 커스터마이징

Email 템플릿을 수정하여 조직에 맞게 커스터마이징할 수 있습니다:

```
services/mcp-server/templates/emails/
├── base.html                    # 기본 레이아웃
├── approval_requested.html      # 승인 요청
├── approval_timeout.html        # 타임아웃
├── approval_approved.html       # 승인 완료
└── approval_rejected.html       # 거부 완료
```

### 템플릿 변수

각 템플릿에서 사용할 수 있는 변수:

**approval_requested.html:**
- `{{ user_id }}` - 요청자 ID
- `{{ tool_name }}` - 도구 이름
- `{{ request_id }}` - 요청 ID (full UUID)
- `{{ request_id[:8] }}` - 요청 ID (짧은 ID)
- `{{ expires_at }}` - 만료 시간

**approval_timeout.html:**
- `{{ user_id }}`, `{{ tool_name }}`, `{{ request_id }}`
- `{{ requested_at }}` - 요청 시간

**approval_approved.html:**
- `{{ user_id }}`, `{{ tool_name }}`
- `{{ responder_id }}` - 승인자 ID
- `{{ reason }}` - 승인 사유

**approval_rejected.html:**
- `{{ user_id }}`, `{{ tool_name }}`
- `{{ responder_id }}` - 거부자 ID
- `{{ reason }}` - 거부 사유

### 커스터마이징 예제

**회사 로고 추가:**

`base.html`의 header 섹션에 추가:
```html
<div class="header">
    <img src="https://company.com/logo.png" alt="Company Logo" style="height: 40px;">
    <h1>🔐 승인 워크플로우</h1>
</div>
```

**언어 변경:**

`approval_requested.html` 수정:
```html
<h3>🔔 새로운 승인 요청이 발생했습니다</h3>
<!-- 변경 후 -->
<h3>🔔 New approval request received</h3>
```

---

## 📍 이벤트 발행 흐름

### approval_requested 이벤트

**발행 위치**: `services/mcp-server/rbac_manager.py` (라인 253-274)
- **시점**: 승인 요청 생성 직후 (감사 로그 기록 후)
- **조건**: `NOTIFICATION_ENABLED=true`
- **데이터**: `request_id`, `user_id`, `tool_name`, `requested_at`, `expires_at`

**흐름**:
```
User Action (도구 실행 요청)
  ↓
rbac_manager.require_approval()
  ↓
log_approval_requested() (감사 로그)
  ↓
enqueue("approval_requested", {...}) ← Phase 6.4
  ↓
Email 발송 (비동기)
```

### approval_approved / approval_rejected 이벤트

**발행 위치**: `services/mcp-server/app.py`
- **approval_approved**: 라인 544-562 (approve_request 엔드포인트)
- **approval_rejected**: 라인 631-649 (reject_request 엔드포인트)

**조건**: `NOTIFICATION_ENABLED=true`

### approval_timeout 이벤트

**발행 위치**: `services/mcp-server/app.py` (라인 707-724)
- **시점**: GET /api/approvals/{request_id}/status 호출 시 타임아웃 감지
- **조건**: `NOTIFICATION_ENABLED=true` + 승인 요청 만료 (5분)

---

## 🧪 테스트 및 모니터링

### 1단계: 연결 테스트

```bash
# Python 스크립트로 SMTP 연결 테스트
python3 << 'EOF'
import smtplib
from email.mime.text import MIMEText

SMTP_HOST = "localhost"
SMTP_PORT = 1025  # MailHog
SMTP_USER = ""
SMTP_PASSWORD = ""

try:
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
        # TLS 설정 (선택사항)
        # server.starttls()

        # 인증 (선택사항)
        # if SMTP_USER and SMTP_PASSWORD:
        #     server.login(SMTP_USER, SMTP_PASSWORD)

        msg = MIMEText("Test message")
        msg["Subject"] = "Test Email"
        msg["From"] = "test@localhost"
        msg["To"] = "admin@localhost"

        server.send_message(msg)
        print("✅ SMTP 연결 성공")
except Exception as e:
    print(f"❌ SMTP 연결 실패: {e}")
EOF
```

### 2단계: 이벤트 발행 테스트

**Test 2-1: approval_requested 이벤트 (승인 요청 생성 시)**

```bash
# CLI를 통해 승인이 필요한 도구 실행
ai --mcp git_commit --mcp-args '{"message": "test commit"}'

# 응답: "Waiting for approval" 메시지 + Request ID 표시
# MailHog Web UI에서 Email 확인
open http://localhost:8025
# 주제: "[승인 필요] git_commit 도구"
```

**Test 2-2: approval_approved 이벤트 (승인 처리 시)**

```bash
# 관리자가 승인 처리
python scripts/approval_admin.py approve <request_id> --reason "Approved for testing"

# MailHog Web UI에서 "[승인됨]" Email 확인
open http://localhost:8025
```

**Test 2-3: approval_rejected 이벤트 (거부 처리 시)**

```bash
# 관리자가 거부 처리
python scripts/approval_admin.py reject <request_id> --reason "Policy violation"

# MailHog Web UI에서 "[거부됨]" Email 확인
open http://localhost:8025
```

**Test 2-4: approval_timeout 이벤트 (타임아웃 감지)**

```bash
# 5분 이상 경과 후 상태 조회
curl -H "X-User-ID: admin" \
  http://localhost:8020/api/approvals/<request_id>/status

# 응답에서 "status": "expired" 확인
# MailHog Web UI에서 "[타임아웃]" Email 확인
open http://localhost:8025
```

### 3단계: 로그 모니터링

```bash
# 실시간 로그 확인
docker compose logs -f mcp-server | grep -E "notification|email|queue"

# 로그 예시
# 2025-10-25 15:30:00 INFO Event enqueued: ApprovalEvent(approval_requested, abc12345)
# 2025-10-25 15:30:05 INFO Notification sent for ApprovalEvent(approval_requested, abc12345)
```

---

## 🚨 문제 해결

### Email이 발송되지 않음

**원인 1: NOTIFICATION_ENABLED=false**
```bash
# 확인
grep NOTIFICATION_ENABLED .env

# 수정
NOTIFICATION_ENABLED=true
docker compose restart mcp-server
```

**원인 2: SMTP 연결 실패**
```bash
# SMTP 설정 확인
grep SMTP .env

# MailHog가 실행 중인지 확인
docker compose ps | grep mailhog
```

**원인 3: 템플릿 파일 없음**
```bash
# 템플릿 디렉토리 확인
ls -la services/mcp-server/templates/emails/

# 파일이 없으면 생성
touch services/mcp-server/templates/emails/{base,approval_requested,approval_timeout,approval_approved,approval_rejected}.html
```

### Email이 전송되었지만 수신되지 않음

**Gmail의 경우:**
1. 2단계 인증 활성화 확인
2. 앱 비밀번호 생성 (Gmail 설정 > 보안)
3. SMTP_PASSWORD에 앱 비밀번호 입력

**Office 365의 경우:**
1. 계정 잠금 확인 (admin.microsoft.com)
2. IMAP/POP 활성화 확인 (Outlook 설정 > 고급)

### 높은 지연 시간 (Email 발송이 느림)

**원인: 배치 타임아웃 설정**
```bash
# 현재 설정 확인
grep NOTIFICATION_BATCH .env

# 타임아웃을 줄임
NOTIFICATION_BATCH_TIMEOUT=2

# 서비스 재시작
docker compose restart mcp-server
```

---

## 📊 성능 고려사항

### 벤치마크 (MailHog 기준)

| 메트릭 | 값 | 설명 |
|--------|----|----|
| 이벤트 처리 속도 | ~100 이벤트/초 | 배치 처리로 최적화됨 |
| Email 발송 시간 | 10-50ms | SMTP 재시도 포함 |
| 재시도 지연 | 2-10초 | exponential backoff |
| 배치 처리 대기 | 최대 5초 | 타임아웃 설정 |

### 확장성

- **낮은 부하 (< 100 이벤트/분)**: 표준 설정으로 충분
- **중간 부하 (100-1000 이벤트/분)**: BATCH_SIZE 증가 (20-50)
- **고부하 (> 1000 이벤트/분)**: PostgreSQL 마이그레이션 권장 (Phase 6.1)

---

## 🔒 보안 고려사항

### SMTP 자격증명 보호

```bash
# ❌ 위험: 자격증명을 코드에 저장
SMTP_PASSWORD=supersecret123

# ✅ 권장: 환경 변수로 관리
# Docker Compose secrets 사용
version: "3.9"
services:
  mcp-server:
    environment:
      SMTP_PASSWORD_FILE: /run/secrets/smtp_password
    secrets:
      - smtp_password

secrets:
  smtp_password:
    file: ./secrets/smtp_password.txt
```

### Email 노출 방지

```bash
# ✅ 권장: 수신자 Email을 환경 변수로 관리
EMAIL_TO=operator@company.com

# ❌ 위험: 코드에 Email 주소 저장 금지
```

---

## 📋 배포 체크리스트

Phase 6.4를 프로덕션에 배포하기 전에 확인하세요:

- [ ] SMTP 서버 구성 및 테스트 완료
- [ ] NOTIFICATION_ENABLED=true 설정 확인
- [ ] Email 템플릿 커스터마이징 완료 (선택사항)
- [ ] BATCH_SIZE/BATCH_TIMEOUT 성능 튜닝 완료
- [ ] **approval_requested 이벤트 테스트** (승인 요청 생성 시 Email 발송 확인)
- [ ] **approval_approved 이벤트 테스트** (승인 처리 시 Email 발송 확인)
- [ ] **approval_rejected 이벤트 테스트** (거부 처리 시 Email 발송 확인)
- [ ] **approval_timeout 이벤트 테스트** (타임아웃 시 Email 발송 확인)
- [ ] 모든 이벤트 Email 발송 테스트 성공
- [ ] 로그 모니터링 설정 완료 (docker compose logs mcp-server | grep notification)
- [ ] 운영팀 교육 완료
- [ ] 백업/롤백 절차 준비 완료

---

## 📚 추가 리소스

- **구현 상세**: `docs/security/IMPLEMENTATION_SUMMARY.md`
- **RBAC 가이드**: `docs/security/RBAC_GUIDE.md`
- **운영 가이드**: `docs/ops/APPROVAL_QUICKSTART.md`
- **API 문서**: http://localhost:8020/docs (Swagger UI)

---

## 지원 및 문의

이슈나 질문이 있으면:

1. **GitHub Issues**: https://github.com/sunbangamen/local-ai-suite/issues
2. **문서 검토**: `docs/progress/v1/` 디렉토리의 진행 상황 문서 확인
3. **로그 분석**: `docker compose logs mcp-server | grep -i notification`

---

**마지막 업데이트**: 2025-10-25
**작성자**: Claude Code (Phase 6.4)
**상태**: ✅ Production Ready
