# GitHub Issue #8 Analysis & Solution Planning

## 📋 Issue Information Summary

**이슈 번호**: #8
**제목**: [Feature] MCP 보안 강화 - 샌드박싱 및 접근 제어 시스템 구축
**상태**: OPEN
**생성일**: 2025-09-30
**우선순위**: HIGH (Phase 4 차단 이슈)
**복잡도**: COMPLEX (2-3주 예상)

### 핵심 요구사항

1. **Python 코드 실행 샌드박싱**: Docker 컨테이너 기반 격리 실행 환경
2. **RBAC 시스템**: 역할 기반 접근 제어로 18개 MCP 도구 권한 관리
3. **감사 로깅**: SQLite 기반 모든 도구 호출 및 보안 위반 기록
4. **보안 테스트**: 샌드박스 탈출 50+, 권한 우회 30+ 테스트 케이스

### 기술적 제약사항

- **기존 아키텍처**: 이미 Docker 컨테이너 환경, Docker-in-Docker 필요
- **성능 목표**: 샌드박스 오버헤드 <100ms, RBAC <10ms, 로깅 <5ms
- **호환성 유지**: 기존 18개 MCP 도구 API 호환성 보장
- **WSL2 환경**: cgroups 제한 고려 필요

---

## 🔍 Technical Investigation

### 현재 구현 상태 (Code Analysis)

#### ✅ 이미 완료된 보안 기능

**1. AST 기반 코드 검증 (security.py:services/mcp-server/security.py)**
- AST 파싱으로 위험 모듈(subprocess, socket, importlib) 차단
- 동적 import 우회 방지 (`__import__`, `import_module`)
- 3단계 보안 레벨(strict/normal/legacy) 지원
- 위험 함수(`eval`, `exec`, `compile`) 차단

**2. Docker 기반 샌드박스 (sandbox.py:services/mcp-server/sandbox.py)**
- `ContainerSandbox` 클래스로 Docker 컨테이너 격리 실행
- 리소스 제한: 메모리 512MB, CPU 30초, 프로세스 10개
- 읽기 전용 파일시스템 + tmpfs 격리
- 네트워크 격리 및 capability 제거 (`--cap-drop ALL`)
- 프로세스 폴백 실행 (Docker 없을 경우)
- 감사 로깅: `SandboxLogger`로 `security_audit.log` 기록
- 세션 관리: `SessionManager`로 세션당 위반 추적

**3. Rate Limiting & Access Control (rate_limiter.py:services/mcp-server/rate_limiter.py)**
- 도구별 민감도 수준(LOW/MEDIUM/HIGH/CRITICAL) 분류
- Rate limit: 도구별 시간 창 내 요청 수 제한
- 동시 실행 제한: 도구별 최대 동시 실행 수 제어
- Development/Production 모드 분리

**4. 안전한 파일 API (safe_api.py:services/mcp-server/safe_api.py)**
- 경로 탐색 방지: 심볼릭 링크 해석 후 작업공간 검증
- 시스템 경로 차단: `/etc`, `/root`, `C:\Windows` 등
- 민감 파일 차단: `/etc/passwd`, `SAM`, `SECURITY` 등

#### ❌ 부족한 보안 기능 (기술적 갭)

**1. RBAC 시스템 없음**
- 현재: 모든 사용자가 모든 도구에 동일한 접근 권한
- 필요: Guest/Developer/Admin 역할별 권한 차등 부여
- 영향: Production 환경에서 권한 관리 불가능

**2. SQLite 기반 메타데이터 저장소 없음**
- 현재: 텍스트 파일(`security_audit.log`) 로깅만 존재
- 필요: 구조화된 DB로 사용자/역할/권한/감사로그 관리
- 영향: 로그 조회, 통계 분석, 권한 정책 변경 불가능

**3. 미들웨어 통합 없음**
- 현재: 각 도구에서 개별적으로 보안 체크 호출
- 필요: FastAPI 미들웨어로 모든 요청 자동 검증
- 영향: 보안 정책 누락 가능성, 일관성 부족

**4. 승인 워크플로우 없음**
- 현재: `require_approval` 플래그만 존재 (구현 없음)
- 필요: HIGH/CRITICAL 도구 실행 전 승인 대기 메커니즘
- 영향: 위험한 작업 사전 차단 불가

**5. WAL 모드 백업 검증 없음**
- 현재: SQLite 사용 계획만 존재, 실제 PoC 없음
- 필요: WAL 모드 동시 접근 테스트, 백업 스크립트 검증
- 영향: 다중 접속 시 DB 잠금 충돌 위험

---

## 💡 Solution Strategy

### Approach Options

#### Option 1: SQLite RBAC + Docker Sandbox 강화 (✅ 추천)

**장점:**
- 기존 코드 재사용: `ContainerSandbox`, `SecurityValidator` 활용
- 낮은 복잡도: SQLite로 추가 의존성 없음
- 빠른 구현: 기존 인프라 위에 RBAC만 추가
- 성능 우수: 파일 기반 DB로 오버헤드 최소화

**단점:**
- SQLite 동시 접근 제한: WAL 모드로도 Writer 1개만 가능
- 확장성 제한: 대규모 동시 사용자 지원 어려움

**예상 시간:** 2주
**위험도:** Low (기존 시스템 활용)

---

#### Option 2: PostgreSQL RBAC + gVisor 샌드박스

**장점:**
- 확장성: 다중 Writer 지원, 대규모 시스템 대비
- 강력한 샌드박싱: gVisor로 커널 수준 격리

**단점:**
- 높은 복잡도: PostgreSQL 설치 및 스키마 마이그레이션
- 성능 오버헤드: gVisor는 Docker보다 느림 (200-300ms)
- 기존 코드 대폭 변경: 인증/세션 시스템 새로 구축

**예상 시간:** 4-5주
**위험도:** High (아키텍처 변경)

---

#### Option 3: 레거시 텍스트 로깅 + AST 검증 강화

**장점:**
- 최소 변경: 기존 시스템 유지
- 빠른 배포: 1주 이내 완료 가능

**단점:**
- RBAC 부재: Production 환경 부적합
- 로그 분석 불가: 텍스트 파일 검색만 가능
- 요구사항 미달: 이슈 #8의 Acceptance Criteria 달성 불가

**예상 시간:** 1주
**위험도:** Medium (요구사항 미충족)

---

### ✅ Recommended Approach: Option 1 - SQLite RBAC + Docker Sandbox 강화

**선택 이유:**

1. **요구사항 충족**: 이슈 #8의 모든 DoD 달성 가능
2. **기존 자산 활용**: `ContainerSandbox`, `SessionManager` 재사용
3. **성능 목표 달성**: SQLite는 <10ms RBAC 검증 가능
4. **낮은 리스크**: 기존 Docker 인프라 위에 점진적 추가
5. **WAL 모드 지원**: 다중 Reader + 1 Writer로 충분한 동시성

**Trade-off:**
- SQLite 동시 Writer 제한은 현재 단일 MCP 서버 인스턴스 환경에서는 문제 없음
- 향후 다중 인스턴스 필요 시 PostgreSQL로 마이그레이션 경로 확보

---

## 📐 Detailed Implementation Plan

### Phase 0: 환경 및 설계 정리 (Day 0)

#### 목표: 본 개발 착수 전에 환경 변수, 테스트 구조, 설계 산출물 정리

| Task | Description | Files | DoD | Risk |
|------|-------------|-------|-----|------|
| **P0-T1** | 환경 변수 정의 및 설정 경로 정리 | `services/mcp-server/.env.example`, `services/mcp-server/settings.py` | `RBAC_ENABLED`, `SECURITY_DB_PATH`, `SECURITY_QUEUE_SIZE` 등 신규 항목 추가 및 애플리케이션 연동 | Low |
| **P0-T2** | 초기화 경로 및 의존성 맵 작성 | `services/mcp-server/` | 샌드박스, 레이트리미터, 보안 모듈 간 의존성 다이어그램 준비 | Low |
| **P0-T3** | 테스트 구조 확정 및 마커 추가 | `services/mcp-server/tests/security/` | 전용 디렉터리/마커 생성, 샘플 테스트 배치 | Low |
| **P0-T4** | RBAC/샌드박스 흐름 설계 아티팩트 작성 | `docs/security/` | ERD 및 시퀀스 다이어그램 초안 공유 | Low |
| **P0-T5** | 데이터베이스 선택 ADR 작성 | `docs/adr/adr-sqlite-vs-postgres.md` | SQLite 선택 배경과 향후 PostgreSQL 전환 경로 문서화 | Low |

---

### Phase 1: SQLite RBAC 데이터베이스 구축 (Day 1-3)

#### 목표: RBAC 스키마 완성 및 WAL 모드 PoC 검증

| Task | Description | Files | DoD | Risk |
|------|-------------|-------|-----|------|
| **P1-T1** | SQLite 스키마 설계 | `security_db.sql` | 6개 테이블 생성 스크립트 완성 (users, roles, permissions, role_permissions, audit_logs, sessions) | Low |
| **P1-T2** | SQLite DB Manager 모듈 개발 | `security_database.py` | CRUD 함수 + 연결 풀링 | Low |
| **P1-T3** | WAL 모드 활성화 및 동시 접근 테스트 | `test_wal_mode.py` | 10+ 동시 연결 성공 | Medium |
| **P1-T4** | 백업 스크립트 작성 | `backup_security_db.py` | 자동 백업 + 복구 검증 | Low |
| **P1-T5** | 초기 데이터 시딩 (기본 역할/권한) | `seed_security_data.py` | Guest/Dev/Admin 역할 생성 | Low |

**핵심 스키마:**

```sql
-- users 테이블
CREATE TABLE IF NOT EXISTS security_users (
    user_id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    role_id INTEGER,
    created_at TEXT DEFAULT (CURRENT_TIMESTAMP),
    FOREIGN KEY (role_id) REFERENCES security_roles(role_id)
);

-- roles 테이블
CREATE TABLE IF NOT EXISTS security_roles (
    role_id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_name TEXT NOT NULL UNIQUE,  -- guest, developer, admin
    description TEXT
);

-- permissions 테이블
CREATE TABLE IF NOT EXISTS security_permissions (
    permission_id INTEGER PRIMARY KEY AUTOINCREMENT,
    permission_name TEXT NOT NULL UNIQUE,  -- read_file, execute_python, etc.
    resource_type TEXT,  -- tool, file, system
    action TEXT  -- read, write, execute
);

-- role_permissions 매핑
CREATE TABLE IF NOT EXISTS security_role_permissions (
    role_id INTEGER,
    permission_id INTEGER,
    PRIMARY KEY (role_id, permission_id),
    FOREIGN KEY (role_id) REFERENCES security_roles(role_id) ON DELETE CASCADE,
    FOREIGN KEY (permission_id) REFERENCES security_permissions(permission_id) ON DELETE CASCADE
);

-- audit_logs 테이블
CREATE TABLE IF NOT EXISTS security_audit_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    tool_name TEXT,
    action TEXT,
    status TEXT,  -- success, denied, error
    error_message TEXT,
    timestamp TEXT DEFAULT (CURRENT_TIMESTAMP),
    execution_time_ms INTEGER
);
```

---

### Phase 2: RBAC 미들웨어 및 권한 검증 통합 (Day 4-7)

#### 목표: FastAPI 미들웨어로 모든 MCP 도구 자동 권한 검증

| Task | Description | Files | DoD | Risk |
|------|-------------|-------|-----|------|
| **P2-T1** | RBAC Manager 모듈 개발 | `rbac_manager.py` | 역할-권한 매핑 조회 | Low |
| **P2-T2** | FastAPI 미들웨어 구현 | `rbac_middleware.py` | 모든 `/tools/*` 요청 검증 | Medium |
| **P2-T3** | 도구별 권한 정책 매핑 | `tool_permissions.yaml` | 18개 도구 권한 정의 | Low |
| **P2-T4** | 기존 도구에 RBAC 적용 | `app.py` | `@mcp.tool()` 데코레이터 통합 | Medium |
| **P2-T5** | 권한 거부 응답 표준화 | `rbac_middleware.py` | HTTP 403 + 상세 메시지 | Low |

**미들웨어 의사코드:**

```python
# rbac_middleware.py
class RBACMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. 사용자 식별 (헤더/세션에서)
        user_id = request.headers.get("X-User-ID", "default")

        # 2. 도구명 추출
        if request.url.path.startswith("/tools/"):
            tool_name = request.url.path.split("/")[2]

            # 3. RBAC 검증
            rbac = get_rbac_manager()
            allowed, reason = rbac.check_permission(user_id, tool_name)

            if not allowed:
                # 4. 감사 로깅
                audit_log(user_id, tool_name, "denied", reason)
                return JSONResponse(
                    status_code=403,
                    content={"error": f"Permission denied: {reason}"}
                )

        return await call_next(request)
```

---

### Phase 3: 감사 로깅 및 샌드박스 통합 (Day 8-12)

#### 목표: 모든 도구 호출 SQLite 로깅 + 샌드박스 강화

| Task | Description | Files | DoD | Risk |
|------|-------------|-------|-----|------|
| **P3-T1** | 비동기 감사 로깅 모듈 | `audit_logger.py` | SQLite 비동기 삽입 <5ms | Low |
| **P3-T2** | 샌드박스 로깅 통합 | `sandbox.py` | `ContainerSandbox`에 DB 로깅 | Low |
| **P3-T3** | 로그 조회 API 개발 | `app.py` | `/security/logs` 엔드포인트 | Low |
| **P3-T4** | 실시간 알림 시스템 (선택) | `alerting.py` | 보안 위반 시 알림 발송 | Medium |
| **P3-T5** | 로그 파티셔닝 전략 | `audit_logger.py` | 월별 테이블 분할 스크립트 | Low |

**감사 로깅 개선:**

```python
# audit_logger.py
class AuditLogger:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.queue = asyncio.Queue()
        asyncio.create_task(self._async_writer())

    async def log_tool_call(self, user_id: str, tool_name: str, result: Dict):
        """비동기 로깅 (메인 스레드 블록 방지)"""
        await self.queue.put({
            "user_id": user_id,
            "tool_name": tool_name,
            "status": "success" if result["success"] else "error",
            "execution_time_ms": int(result.get("execution_time", 0) * 1000)
        })

    async def _async_writer(self):
        """백그라운드 로그 작성"""
        while True:
            log_entry = await self.queue.get()
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO security_audit_logs (...) VALUES (...)",
                    (log_entry["user_id"], log_entry["tool_name"], ...)
                )
                await db.commit()
```

---

### Phase 4: 테스트 및 문서화 (Day 13-16)

#### 목표: 보안 테스트 80개+ 통과 및 문서 작성

| Task | Description | Files | DoD | Risk |
|------|-------------|-------|-----|------|
| **P4-T1** | 샌드박스 탈출 테스트 | `test_sandbox_escape.py` | 50+ 테스트 케이스 차단 확인 | Medium |
| **P4-T2** | 권한 우회 테스트 | `test_rbac_bypass.py` | 30+ 테스트 케이스 차단 확인 | Medium |
| **P4-T3** | 성능 벤치마크 | `benchmark_security.py` | <100ms 샌드박스, <10ms RBAC | Low |
| **P4-T4** | 통합 테스트 | `test_integration.py` | 전체 워크플로우 E2E 테스트 | Medium |
| **P4-T5** | SECURITY.md 문서 작성 | `SECURITY.md` | 아키텍처 다이어그램 포함 | Low |
| **P4-T6** | RBAC_GUIDE.md 작성 | `RBAC_GUIDE.md` | 사용자 매뉴얼 + 설정 예제 | Low |

**테스트 시나리오 예시:**

---

## 🔧 추가 개선 아이디어

- **스키마 버전 관리**: 간단한 마이그레이션 러너 혹은 경량 Alembic 도입으로 향후 스키마 변경 이력 추적.
- **권한 캐싱**: TTL 기반 인메모리 캐시로 RBAC 조회 p95 <10ms 목표 안정화.
- **QA 역할 위임 도구**: QA가 안전하게 역할을 전환하며 시나리오 테스트할 수 있는 CLI 제공.
- **모니터링 연동**: Prometheus 메트릭(403 건수, 샌드박스 위반) 추가 후 Grafana 대시보드와 연계.
- **사고 대응 플레이북**: `RBAC_ENABLED` 토글 절차, 감사 DB 복구 순서, 샌드박스 폴백 가이드 정리.

```python
# test_rbac_bypass.py
async def test_guest_cannot_execute_python():
    """Guest 역할은 execute_python 도구 사용 불가"""
    rbac = get_rbac_manager()
    allowed, reason = rbac.check_permission("guest_user", "execute_python")

    assert allowed == False
    assert "Permission denied" in reason

async def test_admin_can_use_all_tools():
    """Admin 역할은 모든 도구 사용 가능"""
    rbac = get_rbac_manager()
    for tool in ["read_file", "execute_python", "git_commit"]:
        allowed, _ = rbac.check_permission("admin_user", tool)
        assert allowed == True
```

---

## 🧪 Test Cases

### 샌드박스 탈출 테스트 (50개+)

**정상 케이스 (10개):**
1. 간단한 Python 계산 (`print(2+2)`)
2. 허용된 모듈 import (`import json`)
3. 타임아웃 내 정상 종료
4. 허용된 파일 읽기 (`/tmp` 내)

**에러 케이스 (40개):**
1. `import subprocess` 차단
2. `os.system('rm -rf /')` 차단
3. `__import__('subprocess')` 동적 import 차단
4. `/etc/passwd` 읽기 차단
5. 무한 루프 타임아웃 강제 종료
6. 메모리 폭탄 OOM 차단
7. 네트워크 접속 시도 차단
8. 심볼릭 링크 경로 탈출 차단
9. Docker 소켓 접근 차단
10. 특권 상승 시도 차단

### RBAC 권한 우회 테스트 (30개+)

**정상 케이스 (10개):**
1. Guest → `read_file` 허용
2. Developer → `execute_python` 허용
3. Admin → `git_commit` 허용

**에러 케이스 (20개):**
1. Guest → `execute_python` 거부 (403)
2. Developer → `git_commit` 거부 (승인 필요)
3. 헤더 조작으로 역할 변경 시도 차단
4. SQL Injection (`user_id = "admin' OR 1=1"`) 차단
5. 권한 없는 도구 직접 API 호출 차단
6. 세션 하이재킹 시도 차단

---

## 🚨 Risk Assessment & Mitigation

### High Risk Items

| Risk | Impact | Probability | Mitigation Strategy |
|------|--------|-------------|-------------------|
| Docker-in-Docker 성능 저하 | 높음 | 중간 | 벤치마크 후 프로세스 격리 폴백 옵션 유지 |
| SQLite 동시 Writer 잠금 | 중간 | 낮음 | WAL 모드 + 재시도 로직, 필요 시 PostgreSQL 경로 확보 |
| 기존 MCP 도구 호환성 깨짐 | 높음 | 낮음 | Feature flag (`RBAC_ENABLED=false`) 도입 |
| 승인 워크플로우 UI 복잡도 | 중간 | 중간 | Phase 4로 연기, CLI 기반 수동 승인으로 시작 |

### Technical Challenges

1. **WSL2 cgroups 제한**: Docker Desktop 리소스 제한 설정 활용
2. **비동기 로깅 성능**: `aiosqlite` + 큐 기반 배치 삽입
3. **미들웨어 순서**: CORS → RBAC → Rate Limiting 순서 보장
4. **레거시 호환**: 기존 `execute_python` 호출 코드 변경 최소화

### Rollback Plan

- **RBAC 실패 시**: Feature flag로 레거시 모드 복귀 (`RBAC_ENABLED=false`)
- **샌드박스 실패 시**: 프로세스 격리 폴백 (`USE_ENHANCED_SANDBOX=false`)
- **DB 손상 시**: 백업 스크립트로 WAL 파일 복구

---

## 📦 Resource Requirements

### Human Resources
- **개발자**: 1명 (Full-stack, Docker/Python 경험 필수)
- **리뷰어**: 1명 (보안 아키텍처 검토)
- **QA**: 1명 (침투 테스트 담당)

### Technical Resources
- **개발 도구**: Python 3.11, Docker 20.10+, SQLite 3.37+ (WAL 지원)
- **테스트 환경**: WSL2 + Docker Desktop, RTX 4050 GPU
- **모니터링**: Prometheus + Grafana (기존 인프라 활용)

### Time Estimation
- **총 예상 시간**: 16일 (약 2.5주)
- **버퍼 시간**: 4일 (25% 버퍼)
- **완료 목표일**: 2025-10-18

---

## 🎯 Quality Assurance Plan

### Test Strategy

**Unit Tests (커버리지 > 80%):**
- `security_database.py`: CRUD 함수 테스트
- `rbac_manager.py`: 권한 검증 로직
- `audit_logger.py`: 비동기 로깅 동작

**Integration Tests:**
- RBAC 미들웨어 + FastAPI 통합
- 샌드박스 + 감사 로깅 통합
- WAL 모드 동시 접근 시나리오

**E2E Tests:**
- Guest 사용자가 `execute_python` 호출 → 403 응답
- Admin 사용자가 `git_commit` 호출 → 성공 + 로그 기록

### Performance Criteria

- **RBAC 검증**: <10ms (p95)
- **샌드박스 오버헤드**: <100ms (p95)
- **감사 로깅**: <5ms (비동기)
- **전체 응답 시간**: <500ms (p95)

---

## 📋 User Review Checklist

### Planning Review
- [x] **이슈 분석 정확성**: 모든 DoD 항목 식별 완료
- [x] **해결 방안 적절성**: Option 1이 요구사항/성능/리스크 균형 최적
- [x] **구현 계획 현실성**: 4개 Phase로 명확한 마일스톤

### Resource Review
- [x] **시간 추정 합리성**: 16일 + 4일 버퍼 = 약 3주
- [x] **리소스 확보 가능성**: 기존 Docker/SQLite 인프라 활용

### Risk Review
- [x] **위험 요소 식별**: Docker-in-Docker, SQLite 동시성, 호환성
- [x] **대응 방안 구체성**: Feature flag, 폴백 옵션, 백업 스크립트

### Quality Review
- [x] **테스트 전략 충분성**: 80+ 보안 테스트 케이스
- [x] **성능 목표 달성 가능성**: SQLite+Docker로 <100ms 달성 가능

---

## 🚀 Next Steps

1. **계획 공유 및 승인**: 본 문서를 팀에 공유하고 Phase 0~4 범위에 대한 승인 확보.
2. **Phase 0 착수**: 환경 변수 추가, 테스트 구조 생성, ERD/시퀀스 다이어그램, ADR 문서화를 우선 수행.
3. **Phase 1 진행**: `migrate_security_db.py`, `seed_security_data.py`, WAL 동시성 테스트 등 DB 기반 작업 완료.
4. **RBAC 기능 통합**: Feature flag(`RBAC_ENABLED`)를 활용해 미들웨어 PoC를 구현하고 주요 도구에 연결.
5. **감사 로깅 및 성능 검증**: Audit Logger, 샌드박스 연동 후 성능 벤치마크와 우회/탈출 테스트 실행.
6. **문서 및 운영 가이드 확정**: SECURITY.md, RBAC_GUIDE.md, 사고 대응 플레이북을 업데이트하고 Issue/PR 기록에 반영.

**수정 필요 사항:**
- RBAC 역할 구조 변경 요청 시 `seed_security_data.py` 수정
- 성능 목표 조정 시 벤치마크 기준 재설정
- 추가 테스트 케이스 요청 시 `test_*.py` 파일 보강

---

## 💡 피드백 요청

이 계획에 대해 검토 부탁드립니다. 특히 다음 사항 확인 필요:

1. **SQLite vs PostgreSQL**: 동시 접근 제한 수용 가능 여부
2. **승인 워크플로우**: Phase 4 연기 vs 즉시 구현 선호
3. **테스트 커버리지**: 80+ 케이스로 충분 vs 추가 필요
