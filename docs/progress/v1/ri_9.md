# GitHub Issue #18 Analysis & Solution Planning

## 📋 Issue Information Summary

**이슈 번호**: #18
**제목**: [Chore] Issue #8 RBAC 운영 준비 완료 (92% → 100%)
**상태**: OPEN
**생성일**: 2025-10-10
**담당자**: 없음
**라벨**: 없음 (권장: `priority: high`, `type: chore`, `component: security`, `effort: M`)
**마일스톤**: 없음

### Issue Content Analysis
**문제 유형**: Chore (운영 준비 작업)
**우선순위**: HIGH (Production readiness 95% 달성 필요)
**복잡도**: Medium (2-3시간 예상, 단순 반복 작업)

**핵심 요구사항**:
1. ✅ security.db 초기화 및 시드 데이터 투입 완료 (이미 완료됨)
2. ❌ approval_requests 테이블 추가 (Issue #16 스키마 적용 필요)
3. ❌ RBAC 기능 테스트 10개 이상 통과 (pytest)
4. ❌ 성능 벤치마크 목표 달성 (RPS 100+, 95p latency < 100ms)
5. ❌ SECURITY.md, RBAC_GUIDE.md 운영 가이드 작성 완료
6. ❌ CLAUDE.md에 Production readiness 95% 반영

**기술적 제약사항**:
- Python 3.11+ 환경
- SQLite 3.x (WAL 모드)
- FastAPI RBAC 미들웨어 통합
- Issue #16 승인 워크플로우 스키마와 충돌 없이 통합

---

## 🔍 Step 2: Technical Investigation

### Code Analysis Required

**현재 구현 상태 (2025-10-10 검증 완료)**:

#### ✅ 이미 완료된 작업

**1. security.db 기본 스키마 및 시드 데이터 (100% 완료)**
- 위치: `/mnt/e/ai-data/sqlite/security.db`
- 테이블: 7개 (security_users, security_roles, security_permissions, security_role_permissions, security_audit_logs, security_sessions, schema_version)
- 시드 데이터:
  - 4명 사용자 (guest_user, dev_user, admin_user + 1)
  - 3개 역할 (guest, developer, admin)
  - 21개 권한 (18개 MCP 도구 + 3개 파일 작업)

**2. RBAC 핵심 모듈 (100% 완료)**
- `services/mcp-server/rbac_manager.py`: TTL 기반 캐싱, 권한 검사
- `services/mcp-server/rbac_middleware.py`: FastAPI 미들웨어 자동 검증
- `services/mcp-server/audit_logger.py`: 비동기 감사 로깅
- `services/mcp-server/security_database.py`: SQLite DB Manager

**3. 통합 테스트 (100% 완료)**
- `services/mcp-server/tests/integration/test_rbac_integration.py`: 통합 테스트 작성 완료
- `services/mcp-server/tests/test_approval_workflow.py`: 승인 워크플로우 테스트 작성 완료

#### ❌ 미완료 작업

**1. approval_requests 테이블 추가 (Issue #16 통합 필요)**
- 현재 상태: `approval_schema.sql` 파일 존재, DB에 미적용
- 필요 작업: `apply_approval_schema.py` 실행하여 스키마 추가
- 예상 시간: 5분

**2. RBAC 기능 테스트 실행**
- 현재 상태: 테스트 파일 존재, pytest 미실행
- 필요 작업: pytest 실행 및 결과 로그 저장
- 예상 시간: 30분 (환경 구성 포함)

**3. 성능 벤치마크 스크립트 작성 및 실행**
- 현재 상태: 벤치마크 스크립트 없음
- 필요 작업: httpx 기반 부하 테스트 스크립트 작성 및 실행
- 예상 시간: 45분

**4. 운영 문서 작성**
- 현재 상태: SECURITY.md, RBAC_GUIDE.md 파일 없음
- 필요 작업: 운영 가이드 2개 파일 작성
- 예상 시간: 60분

**5. CLAUDE.md 업데이트**
- 현재 상태: Production readiness 85% (Issue #8 92% 완료 반영)
- 필요 작업: Issue #8/16 완료 상태 및 95% readiness 반영
- 예상 시간: 10분

### Dependency Check
**의존성 이슈**:
- ✅ Depends on: #8 - RBAC 시스템 구현 (92% 완료, 코드 구현 완료)
- ✅ Depends on: #16 - 승인 워크플로우 구현 (완료됨, 스키마 적용 필요)
- ❌ Blocks: Production deployment (보안 요구사항 충족 후 배포 가능)

---

## 💡 Step 3: Solution Strategy

### Approach Options

#### **Option 1: 순차적 완료 (하나씩 검증) ✅ 추천**

**장점**:
- 각 단계별 검증으로 오류 조기 발견
- 명확한 진행 상황 추적 가능
- 문제 발생 시 빠른 롤백 가능

**단점**:
- 전체 소요 시간 약간 증가 (대기 시간 포함)

**예상 시간**: 3시간 20분
**위험도**: Low

#### **Option 2: 병렬 작업 (문서 작성과 테스트 동시 진행)**

**장점**:
- 전체 소요 시간 단축
- 리소스 효율적 활용

**단점**:
- 테스트 결과가 문서에 반영되지 않을 위험
- 오류 발생 시 재작업 필요

**예상 시간**: 2시간
**위험도**: Medium

#### **Option 3: 자동화 스크립트 작성 후 일괄 실행**

**장점**:
- 재사용 가능한 자동화 스크립트
- 향후 CI/CD 파이프라인 통합 가능

**단점**:
- 초기 스크립트 작성 시간 추가
- 오버엔지니어링 가능성

**예상 시간**: 3시간
**위험도**: Low

### Recommended Approach
**선택한 접근법**: Option 1 - 순차적 완료

**선택 이유**:
1. **안정성 우선**: Production readiness 작업이므로 각 단계 검증 필수
2. **명확한 진행 추적**: 사용자에게 실시간 피드백 제공 가능
3. **즉시 시작 가능**: 추가 준비 없이 바로 작업 시작 가능
4. **위험 최소화**: 각 단계 완료 후 다음 단계 진행으로 오류 조기 발견

---

## 📝 Step 4: Detailed Implementation Plan

### **Phase 1: 데이터베이스 통합 및 검증 (30분)**

**목표**: approval_requests 테이블 추가 및 전체 DB 무결성 검증

| Task | Description | DoD | Risk |
|------|-------------|-----|------|
| P1-T1: approval_schema 적용 | Python으로 `approval_schema.sql` 수동 적용 | approval_requests 테이블 생성 확인 | Low |
| P1-T2: 외래키 무결성 검증 | PRAGMA foreign_key_check 실행 | 모든 외래키 제약조건 통과 | Low |
| P1-T3: 인덱스 검증 | approval_requests 인덱스 확인 | 3개 인덱스 생성 확인 | Low |
| P1-T4: 시드 데이터 재확인 | seed_security_data.py 재실행 (idempotent) | 사용자/역할/권한 데이터 일치 | Low |

**실행 명령어**:
```bash
# T1: approval_schema 적용 (Python으로 수동 실행)
python3 -c "
import sqlite3
with open('services/mcp-server/scripts/approval_schema.sql', 'r') as f:
    schema_sql = f.read()
conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
conn.executescript(schema_sql)
conn.commit()
cursor = conn.cursor()
cursor.execute('SELECT name FROM sqlite_master WHERE type=\"table\" AND name=\"approval_requests\"')
print('✓ approval_requests table created:', cursor.fetchone() is not None)
"

# T2: 외래키 무결성 검증
python3 -c "
import sqlite3
conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
cursor = conn.cursor()
cursor.execute('PRAGMA foreign_key_check')
errors = cursor.fetchall()
print('✓ Foreign key check passed' if not errors else f'✗ Errors: {errors}')
"

# T3: 인덱스 검증
python3 -c "
import sqlite3
conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
cursor = conn.cursor()
cursor.execute('SELECT name FROM sqlite_master WHERE type=\"index\" AND tbl_name=\"approval_requests\"')
indexes = cursor.fetchall()
print(f'✓ {len(indexes)} indexes created:', [idx[0] for idx in indexes])
"

# T4: 시드 데이터 재확인 (idempotent)
cd services/mcp-server && python3 scripts/seed_security_data.py
```

**산출물**:
- ✅ approval_requests 테이블 생성 확인 로그
- ✅ 외래키 무결성 검증 로그
- ✅ 인덱스 생성 확인 로그

---

### **Phase 2: RBAC 기능 테스트 (45분)**

**목표**: pytest 실행 및 10개 이상 테스트 케이스 통과

| Task | Description | DoD | Risk |
|------|-------------|-----|------|
| P2-T1: pytest 환경 구성 | requirements.txt 의존성 설치 | pytest, httpx, pytest-asyncio 설치 | Low |
| P2-T2: 통합 테스트 실행 | test_rbac_integration.py 실행 | 모든 테스트 케이스 통과 | Medium |
| P2-T3: 승인 워크플로우 테스트 | test_approval_workflow.py 실행 | 7개 시나리오 모두 통과 | Medium |
| P2-T4: 테스트 결과 로그 저장 | pytest --verbose 결과 저장 | TEST_RESULTS.md 파일 생성 | Low |

**사전 준비**: RBAC 미들웨어 테스트를 위해 `RBAC_ENABLED=true`로 활성화하고, 운영 DB 보호가 필요하면 `TEST_MODE=isolated`로 격리합니다.

**실행 명령어**:
```bash
# 사전 준비: RBAC 통합 테스트 활성화
export RBAC_ENABLED=true
export TEST_MODE=isolated  # 필요 시 운영 DB 격리

# T1: pytest 환경 구성
cd services/mcp-server
pip install pytest pytest-asyncio httpx aiosqlite

# T2: 통합 테스트 실행
pytest tests/integration/test_rbac_integration.py -v --tb=short > ../../TEST_RBAC_INTEGRATION.log 2>&1

# T3: 승인 워크플로우 테스트
pytest tests/test_approval_workflow.py -v --tb=short > ../../TEST_APPROVAL_WORKFLOW.log 2>&1

# T4: 테스트 결과 종합
cat ../../TEST_RBAC_INTEGRATION.log ../../TEST_APPROVAL_WORKFLOW.log > ../../TEST_RESULTS_ISSUE18.md
```

**테스트 시나리오** (최소 10개):
1. admin 역할로 CRITICAL 도구 호출 → 승인 요청 생성
2. user 역할로 HIGH 도구 호출 → 403 Forbidden
3. developer 역할로 MEDIUM 도구 호출 → 200 OK
4. 승인 요청 생성 후 승인 → 도구 실행 성공
5. 승인 요청 생성 후 거부 → 403 Forbidden
6. 승인 요청 타임아웃 → 408 Request Timeout
7. 동시 10개 승인 요청 → 모두 독립적 처리
8. 감사 로그 기록 확인 → security_audit_logs 조회
9. 권한 캐싱 동작 확인 → 두 번째 요청 빠른 응답
10. DB 연결 실패 시 에러 처리 → 500 Internal Server Error

**산출물**:
- `TEST_RESULTS_ISSUE18.md`: 전체 테스트 결과 로그

---

### **Phase 3: 성능 벤치마크 (45분)**

**목표**: RPS 100+, 95p latency < 100ms 달성 및 CSV 결과 저장

| Task | Description | DoD | Risk |
|------|-------------|-----|------|
| P3-T1: 벤치마크 스크립트 작성 | httpx 기반 부하 테스트 스크립트 | benchmark_rbac.py 파일 생성 | Low |
| P3-T2: MCP 서버 시작 | docker compose up mcp-server | localhost:8020 응답 확인 | Low |
| P3-T3: 부하 테스트 실행 | 1분간 100 RPS 부하 | CSV 결과 파일 생성 | Medium |
| P3-T4: 결과 분석 및 문서화 | 평균/95p latency, RPS, 에러율 계산 | BENCHMARK_RESULTS.md 생성 | Low |

**벤치마크 스크립트** (services/mcp-server/tests/benchmark_rbac.py):
```python
#!/usr/bin/env python3
"""
RBAC Performance Benchmark
목표: RPS 100+, 95p latency < 100ms
"""

import asyncio
import httpx
import time
import statistics
import csv
from pathlib import Path

BASE_URL = "http://localhost:8020"
DURATION = 60  # seconds
TARGET_RPS = 100

async def benchmark_tool_call(client, user_id, tool_name):
    """Single tool call with timing"""
    start = time.perf_counter()
    try:
        response = await client.post(
            f"{BASE_URL}/tools/{tool_name}/call",
            headers={"X-User-ID": user_id},
            json={"arguments": {}},
            timeout=5.0
        )
        latency = (time.perf_counter() - start) * 1000  # ms
        return {"success": True, "latency": latency, "status": response.status_code}
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return {"success": False, "latency": latency, "error": str(e)}

async def run_benchmark():
    """Run benchmark for DURATION seconds at TARGET_RPS"""
    results = []
    start_time = time.time()

    async with httpx.AsyncClient() as client:
        while time.time() - start_time < DURATION:
            tasks = []
            # Create TARGET_RPS tasks per second
            for _ in range(TARGET_RPS):
                # Alternate between different users and tools
                user_id = "dev_user"  # or cycle through users
                tool_name = "list_files"  # or cycle through tools
                tasks.append(benchmark_tool_call(client, user_id, tool_name))

            # Execute all tasks concurrently
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)

            # Wait for next second
            elapsed = time.time() - start_time
            await asyncio.sleep(max(0, 1 - (elapsed % 1)))

    return results

def analyze_results(results, output_csv):
    """Analyze and save results"""
    latencies = [r["latency"] for r in results if r.get("latency")]
    successes = [r for r in results if r.get("success")]
    errors = [r for r in results if not r.get("success")]

    stats = {
        "total_requests": len(results),
        "successful": len(successes),
        "errors": len(errors),
        "error_rate": len(errors) / len(results) * 100,
        "avg_latency": statistics.mean(latencies),
        "p50_latency": statistics.median(latencies),
        "p95_latency": statistics.quantiles(latencies, n=20)[18],  # 95th percentile
        "p99_latency": statistics.quantiles(latencies, n=100)[98],
        "min_latency": min(latencies),
        "max_latency": max(latencies),
        "rps": len(results) / DURATION
    }

    # Save to CSV
    with open(output_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=stats.keys())
        writer.writeheader()
        writer.writerow(stats)

    print(f"\n{'='*60}")
    print(f"Benchmark Results (Duration: {DURATION}s)")
    print(f"{'='*60}")
    for key, value in stats.items():
        if 'latency' in key:
            print(f"{key:20}: {value:8.2f} ms")
        elif 'rate' in key or 'rps' in key:
            print(f"{key:20}: {value:8.2f}")
        else:
            print(f"{key:20}: {value:8}")
    print(f"{'='*60}\n")

    # Check if goals met
    goals_met = (
        stats["rps"] >= 100 and
        stats["p95_latency"] < 100 and
        stats["error_rate"] < 1.0
    )

    print(f"✓ Goals met: {goals_met}")
    print(f"  - RPS >= 100: {stats['rps']:.2f} >= 100 = {stats['rps'] >= 100}")
    print(f"  - 95p latency < 100ms: {stats['p95_latency']:.2f} < 100 = {stats['p95_latency'] < 100}")
    print(f"  - Error rate < 1%: {stats['error_rate']:.2f}% < 1% = {stats['error_rate'] < 1.0}")

    return stats

if __name__ == "__main__":
    print(f"Starting RBAC benchmark (Target: {TARGET_RPS} RPS for {DURATION}s)")
    results = asyncio.run(run_benchmark())

    # 리포지토리 루트의 data/ 디렉터리에 결과 저장
    output_csv = Path(__file__).resolve().parents[3] / "data" / "rbac_benchmark.csv"
    output_csv.parent.mkdir(exist_ok=True)

    analyze_results(results, output_csv)
```

**실행 명령어**:
```bash
# T1: 스크립트 작성 (위 코드 저장)
# (Claude가 Write tool로 작성)

# T2: MCP 서버 시작
docker compose -f docker/compose.p3.yml up -d mcp-server
sleep 10  # 서버 시작 대기
curl http://localhost:8020/health

# T3: 벤치마크 실행
cd services/mcp-server
python3 tests/benchmark_rbac.py

# T4: 결과 확인
cat ../../data/rbac_benchmark.csv
```

**성능 기준**:
- **RPS**: ≥ 100 requests/sec
- **95p Latency**: < 100ms
- **에러율**: < 1% (권한 거부는 정상 응답)

**산출물**:
- `data/rbac_benchmark.csv`: 벤치마크 결과 CSV
- `BENCHMARK_RESULTS.md`: 결과 분석 문서

---

### **Phase 4: 운영 문서 작성 (60분)**

**목표**: 운영 조직이 바로 참고할 수 있는 SECURITY.md, RBAC_GUIDE.md 작성

| Task | Description | DoD | Risk |
|------|-------------|-----|------|
| P4-T1: SECURITY.md 작성 | 보안 시스템 전체 아키텍처 및 배포 절차 | Markdown 렌더링 확인 | Low |
| P4-T2: RBAC_GUIDE.md 작성 | 역할/권한 관리, CLI 사용법, 트러블슈팅 | 내부 링크 검증 | Low |
| P4-T3: 테스트/벤치마크 결과 삽입 | Phase 2/3 결과를 표/그래프로 추가 | 결과 데이터 정확성 확인 | Low |
| P4-T4: CLAUDE.md 업데이트 | Issue #8/16 완료, Production readiness 95% 반영 | Git diff 확인 | Low |

**SECURITY.md 구조**:
```markdown
# SECURITY.md

## Overview
- RBAC System Architecture
- Security Layers (AST validation, Sandbox, Rate limiting, RBAC, Audit logging)

## RBAC System
### Architecture
- SQLite database schema (ERD)
- Role-based access control flow (sequence diagram)

### Roles & Permissions
- Guest (7 permissions): read-only file/log access
- Developer (14 permissions): code execution + Git ops
- Admin (21 permissions): full access

### Approval Workflow
- HIGH/CRITICAL tools require approval
- Timeout: 5 minutes
- CLI approval: `python scripts/approval_cli.py`

## Deployment
### Database Initialization
```bash
cd services/mcp-server
python scripts/seed_security_data.py --reset
```

### Environment Variables
```
RBAC_ENABLED=true
SECURITY_DB_PATH=/mnt/e/ai-data/sqlite/security.db
APPROVAL_WORKFLOW_ENABLED=true
```

### Health Check
```bash
curl http://localhost:8020/health
```

## Audit Logging
### Log Format
- Table: security_audit_logs
- Fields: user_id, tool_name, action, status, timestamp, details

### Query Examples
```sql
-- Recent denials
SELECT * FROM security_audit_logs WHERE status = 'denied' ORDER BY timestamp DESC LIMIT 10;
```

## Testing & Performance
### Test Results
(Insert Phase 2 results)

### Benchmark Results
(Insert Phase 3 results)

## Troubleshooting
### Common Issues
1. Permission denied → Check role assignments
2. DB lock errors → Verify WAL mode
3. Approval timeout → Increase timeout in .env
```

**RBAC_GUIDE.md 구조**:
```markdown
# RBAC Operations Guide

## Getting Started
### Prerequisites
- Python 3.11+
- SQLite 3.x
- FastAPI MCP server running

### Quick Start
1. Initialize database: `python scripts/seed_security_data.py --reset`
2. Start MCP server: `docker compose up mcp-server`
3. Test permission: `curl -H "X-User-ID: dev_user" http://localhost:8020/tools/list_files/call`

## User Management
### Create User
```python
from security_database import get_security_database
db = get_security_database()
await db.create_user("new_user", "New User", role_id=2)  # developer
```

### Update User Role
```python
await db.update_user("new_user", role_id=3)  # admin
```

### Delete User
```python
await db.delete_user("new_user")
```

## Permission Management
### Tool Permission Matrix
| Tool | Guest | Developer | Admin |
|------|-------|-----------|-------|
| read_file | ✓ | ✓ | ✓ |
| write_file | ✗ | ✓ | ✓ |
| execute_python | ✗ | ✓ | ✓ |
| git_commit | ✗ | ✗ | ✓ |
...

### Update Permissions
```python
await db.add_permission_to_role(role_id=2, permission_id=15)  # Add web_automate to developer
```

## Approval Workflow
### Enable/Disable
```bash
# Enable
export APPROVAL_WORKFLOW_ENABLED=true

# Disable
export APPROVAL_WORKFLOW_ENABLED=false
```

### Approve/Reject Requests
```bash
# List pending approvals
python scripts/approval_cli.py list

# Approve request
python scripts/approval_cli.py approve <request_id> --reason "Authorized by security team"

# Reject request
python scripts/approval_cli.py reject <request_id> --reason "Policy violation"
```

### CLI Usage
```bash
# Check approval status
python scripts/approval_cli.py status <request_id>

# Auto-approve for testing (dev only)
python scripts/approval_cli.py auto-approve --duration 3600  # 1 hour
```

## Testing
### Unit Tests
```bash
pytest services/mcp-server/tests/integration/test_rbac_integration.py -v
```

### Approval Workflow Tests
```bash
pytest services/mcp-server/tests/test_approval_workflow.py -v
```

### Performance Benchmark
```bash
python services/mcp-server/tests/benchmark_rbac.py
```

## Troubleshooting
### Common Issues
**Problem**: `Permission denied` for valid user
**Solution**:
1. Check user role: `SELECT * FROM security_users WHERE user_id = 'dev_user'`
2. Verify permission mapping: `SELECT * FROM user_permissions_view WHERE user_id = 'dev_user'`
3. Clear cache: Restart MCP server

**Problem**: `Database is locked`
**Solution**:
1. Verify WAL mode: `PRAGMA journal_mode;` → should return `wal`
2. Kill zombie connections: `fuser -k /mnt/e/ai-data/sqlite/security.db`
3. Checkpoint WAL: `python scripts/backup_security_db.py`

**Problem**: `Approval timeout`
**Solution**:
1. Increase timeout: `APPROVAL_TIMEOUT=600` (10 minutes)
2. Check pending approvals: `python scripts/approval_cli.py list`
3. Auto-approve for dev: `export APPROVAL_WORKFLOW_ENABLED=false`

### Debug Commands
```bash
# Check DB integrity
python3 -c "import sqlite3; conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db'); print(conn.execute('PRAGMA integrity_check').fetchone())"

# Show all users and roles
python3 -c "import sqlite3; conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db'); cursor = conn.cursor(); cursor.execute('SELECT u.user_id, u.username, r.role_name FROM security_users u JOIN security_roles r ON u.role_id = r.role_id'); print('\\n'.join([str(row) for row in cursor.fetchall()]))"

# Count audit logs
python3 -c "import sqlite3; conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db'); print('Total logs:', conn.execute('SELECT COUNT(*) FROM security_audit_logs').fetchone()[0])"
```
```

**실행 명령어**:
```bash
# T1-T3: 문서 작성 (Claude가 Write tool로 작성)

# T4: CLAUDE.md 업데이트
# (Claude가 Edit tool로 수정)
```

**산출물**:
- `docs/security/SECURITY.md`: 보안 시스템 가이드
- `docs/security/RBAC_GUIDE.md`: RBAC 운영 매뉴얼
- `CLAUDE.md`: Production readiness 95% 반영

---

### **Phase 5: 최종 검증 및 커밋 (20분)**

**목표**: 모든 작업 완료 확인 및 Git 커밋

| Task | Description | DoD | Risk |
|------|-------------|-----|------|
| P5-T1: DoD 체크리스트 검증 | 이슈의 모든 DoD 항목 확인 | 6개 체크박스 모두 ✓ | Low |
| P5-T2: Git 커밋 | Conventional Commits 형식으로 커밋 | 커밋 메시지 검증 | Low |
| P5-T3: 최종 문서 리뷰 | Markdown 렌더링 및 링크 확인 | 모든 링크 정상 동작 | Low |
| P5-T4: PR 생성 준비 | COMMIT_MESSAGE.txt, PR_BODY.md 작성 | 파일 생성 확인 | Low |

**Definition of Done 체크리스트**:
- [ ] security.db 초기화 완료 및 verify_rbac_sqlite.py 결과 로그 첨부
- [ ] approval_requests 테이블 추가 완료
- [ ] RBAC pytest 스위트(권한/승인/에러) 100% 통과
- [ ] 성능 벤치마크 CSV 파일 생성 및 결과 분석
- [ ] 문서 Markdown 렌더링 확인 및 내부 링크 검증
- [ ] Conventional Commit 메시지로 Git commit 완료

**Git 커밋 메시지**:
```
chore(security): complete RBAC operational readiness (Issue #8 100%)

- feat(security): apply approval_requests schema to security.db
- test(security): run RBAC integration tests (10+ cases passed)
- test(security): add RBAC performance benchmark script
- docs(security): create SECURITY.md and RBAC_GUIDE.md
- docs: update CLAUDE.md to reflect Production readiness 95%

Issue: #18
Depends on: #8, #16
Production readiness: 85% → 95%

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

**실행 명령어**:
```bash
# T1: DoD 체크리스트 검증 (수동 확인)

# T2: Git 커밋
git add -A
git commit -m "$(cat <<'EOF'
chore(security): complete RBAC operational readiness (Issue #8 100%)

- feat(security): apply approval_requests schema to security.db
- test(security): run RBAC integration tests (10+ cases passed)
- test(security): add RBAC performance benchmark script
- docs(security): create SECURITY.md and RBAC_GUIDE.md
- docs: update CLAUDE.md to reflect Production readiness 95%

Issue: #18
Depends on: #8, #16
Production readiness: 85% → 95%

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"

# T3: 최종 문서 리뷰 (수동 확인)

# T4: PR 생성 준비 (사용자가 수동으로 gh pr create 실행)
```

---

## 🚨 Step 5: Risk Assessment & Mitigation

### High Risk Items

| Risk | Impact | Probability | Mitigation Strategy |
|------|--------|-------------|-------------------|
| pytest 실행 실패 (환경 문제) | High | Medium | 로컬 환경 사전 검증, requirements.txt 확인, venv 사용 |
| 성능 벤치마크 기준 미달 | Medium | Low | 현재 성능 기록 후 최적화 계획 수립, 목표 조정 가능 |
| approval_schema 적용 오류 | High | Low | 스키마 파일 검증, DB 백업 후 적용, 수동 롤백 준비 |
| 문서 작성 지연 | Low | Medium | 핵심 운영 가이드 우선, 상세 설명은 후속 작업 |

### Technical Challenges

**예상 기술적 난점**:

1. **aiosqlite 모듈 미설치** → 해결 방안: `pip install aiosqlite` 또는 수동 스키마 적용
2. **MCP 서버 시작 실패** → 해결 방안: Docker 로그 확인, 포트 충돌 체크
3. **pytest 환경 충돌** → 해결 방안: Python venv 사용, 의존성 재설치

### Rollback Plan

**롤백 시나리오**:
- **스키마 적용 실패** → DB 백업 복구: `cp /mnt/e/ai-data/sqlite/backup/security.db.backup /mnt/e/ai-data/sqlite/security.db`
- **테스트 실패** → 코드 수정 후 재실행, 실패 원인 로그 수집
- **벤치마크 실패** → 현재 성능 기록 후 최적화 계획 문서화

---

## 📦 Step 6: Resource Requirements

### Human Resources
- **개발자**: 1명 (백엔드 개발자, Python/SQLite/FastAPI 경험)
- **리뷰어**: 1명 (보안 검토 가능자)
- **QA**: 선택적 (자동화 테스트 위주)

### Technical Resources
- **개발 도구**: Python 3.11+, pytest, httpx, aiosqlite
- **테스트 환경**: Docker Compose, WSL2, localhost:8020
- **모니터링**: Docker logs, SQLite CLI

### Time Estimation
- **총 예상 시간**: 3시간 20분 (200분)
- **버퍼 시간**: 40분 (약 20%)
- **완료 목표일**: 2025-10-10 (당일 완료 가능, 버퍼 포함 최대 4시간)

**Phase별 시간**:
- Phase 1: 30분 (DB 통합)
- Phase 2: 45분 (기능 테스트)
- Phase 3: 45분 (성능 벤치마크)
- Phase 4: 60분 (문서 작성)
- Phase 5: 20분 (최종 검증)
- **총**: 200분 = 3시간 20분 (버퍼 포함)

---

## ✅ Step 7: Quality Assurance Plan

### Test Strategy

**테스트 레벨**:
- **Unit Tests**: RBAC Manager, Audit Logger 단위 테스트 (기존 테스트 활용)
- **Integration Tests**: `test_rbac_integration.py` 실행 (10+ 케이스)
- **E2E Tests**: `test_approval_workflow.py` 실행 (7개 시나리오)
- **Performance Tests**: `benchmark_rbac.py` 실행 (1분 부하 테스트)

### Test Cases

```gherkin
Feature: RBAC Permission Validation

  Scenario: Admin accesses CRITICAL tool
    Given user "admin_user" with role "admin"
    When POST /tools/execute_python/call with X-User-ID: admin_user
    Then response status is 202 (approval pending) or 200 (if approved)

  Scenario: Developer accesses MEDIUM tool
    Given user "dev_user" with role "developer"
    When POST /tools/list_files/call with X-User-ID: dev_user
    Then response status is 200

  Scenario: Guest accesses HIGH tool
    Given user "guest_user" with role "guest"
    When POST /tools/write_file/call with X-User-ID: guest_user
    Then response status is 403
    And response contains "Permission denied"

Feature: Approval Workflow

  Scenario: Approval granted
    Given HIGH tool approval request created
    When admin approves request via CLI
    Then tool executes successfully
    And audit log records approval event

  Scenario: Approval timeout
    Given CRITICAL tool approval request created
    When 5 minutes elapse without response
    Then request status becomes "timeout"
    And audit log records timeout event
```

### Performance Criteria

- **응답시간**:
  - 평균 latency < 50ms
  - 95p latency < 100ms
  - 99p latency < 200ms
- **처리량**: RPS ≥ 100
- **리소스 사용률**:
  - CPU < 50% (Docker container)
  - 메모리 < 512MB

---

## 📋 User Review Checklist

### Planning Review
- [x] **이슈 분석이 정확한가요?**
  - ✅ 핵심 요구사항: DB 초기화, 테스트, 벤치마크, 문서화 모두 파악
  - ✅ 기술적 제약사항: SQLite WAL, Issue #16 통합 고려

- [x] **선택한 해결 방안이 적절한가요?**
  - ✅ Option 1 (순차적 완료): 안정성 우선, 명확한 진행 추적
  - ✅ 각 Phase별 검증으로 오류 조기 발견 가능

- [x] **구현 계획이 현실적인가요?**
  - ✅ 5개 Phase로 세분화, 각 Task별 DoD 명확
  - ✅ 의존성 고려: approval_schema 적용 → 테스트 → 벤치마크 → 문서

### Resource Review
- [x] **시간 추정이 합리적인가요?**
  - ✅ Phase별 30-60분, 총 3시간 20분 (버퍼 40분 포함 시 최대 4시간)
  - ✅ 실제 작업량 고려: 스크립트 작성, 테스트 실행, 문서 작성

- [x] **필요한 리소스가 확보 가능한가요?**
  - ✅ Python 3.11+, Docker, WSL2 환경 이미 구축
  - ✅ 필요 도구: pytest, httpx, aiosqlite (pip로 즉시 설치 가능)

### Risk Review
- [x] **위험 요소가 충분히 식별되었나요?**
  - ✅ pytest 실행 실패, 성능 기준 미달, 스키마 적용 오류 고려
  - ✅ 각 위험에 대한 대응 방안 구체적 (환경 검증, 롤백 계획)

- [x] **롤백 계획이 현실적인가요?**
  - ✅ DB 백업 복구, 코드 수정 후 재실행 등 명확

### Quality Review
- [x] **테스트 전략이 충분한가요?**
  - ✅ Unit/Integration/E2E/Performance 모두 커버
  - ✅ 10개 이상 테스트 케이스, 7개 승인 워크플로우 시나리오

---

## 🚀 Next Steps

**진행 순서**:

1. **사용자 승인 확인**: "위 계획으로 진행해도 될까요?"
2. **Phase 1 시작**: DB 통합 및 검증 (30분)
3. **Phase 2 실행**: RBAC 기능 테스트 (45분)
4. **Phase 3 실행**: 성능 벤치마크 (45분)
5. **Phase 4 실행**: 운영 문서 작성 (60분)
6. **Phase 5 완료**: 최종 검증 및 커밋 (20분)

**사용자 액션 필요**:
- ✅ 계획 승인
- ✅ Phase별 진행 확인
- ❌ PR 생성 (수동): `gh pr create --title "chore(security): complete RBAC operational readiness" --body "$(cat PR_BODY.md)"`

---

## 💡 피드백 요청

**이 계획에 대해 검토 부탁드립니다:**

1. **시간 추정**: 3시간 20분이 적절한가요? (버퍼 40분 포함 시 최대 4시간)
2. **Phase 순서**: DB 통합 → 테스트 → 벤치마크 → 문서 순서가 맞나요?
3. **성능 목표**: RPS 100+, 95p latency < 100ms가 현실적인가요?
4. **문서 구조**: SECURITY.md와 RBAC_GUIDE.md 구조가 운영에 충분한가요?

**특히 우려되는 부분**:
- approval_schema 적용 시 외래키 충돌 가능성 (Issue #16 통합)
- pytest 실행 환경 (aiosqlite, httpx 의존성)
- 성능 벤치마크 목표 달성 여부

**수정이 필요하시면 알려주세요!** 바로 계획을 업데이트하거나 즉시 작업을 시작하겠습니다.

---

**⚠️ 주의사항**:
- PR 생성 및 병합은 자동으로 실행하지 않습니다.
- 모든 작업 완료 후 사용자가 직접 `gh pr create` 명령으로 PR을 생성해주세요.
- 커밋 메시지는 Conventional Commits 형식을 따릅니다.
