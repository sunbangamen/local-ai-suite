# RBAC 시스템 운영 준비 완료 - 작업 분해

**입력 요구사항**: Issue #8 RBAC 시스템의 운영 준비 작업 완료 (DB 시딩 → 기능 테스트 → 성능 벤치마크 → 문서화)

---

## 문제 분석

### 1. 문제 정의 및 복잡성 평가
- **문제**: RBAC 시스템 코드 구현은 완료되었으나, 실제 운영 환경에서 사용하기 위한 데이터 초기화, 검증, 문서화가 미완료
- **복잡성 수준**: 낮음 (코드 구현 완료, 검증 및 문서화만 남음)
- **예상 소요 시간**: 2-3시간
- **주요 도전 과제**:
  - Docker 컨테이너 내에서 DB 시딩 실행
  - 실제 MCP 도구 호출 시나리오 테스트
  - 성능 목표 달성 검증 (RBAC <10ms, Audit <5ms, 전체 <500ms)

### 2. 범위 및 제약조건
- **포함 범위**:
  - Security DB 초기화 및 시딩 (3 roles, 21 permissions, 3 users)
  - Guest/Developer/Admin 역할별 권한 테스트
  - 성능 벤치마크 실행 및 결과 기록
  - SECURITY.md, RBAC_GUIDE.md 운영 문서 작성

- **제외 범위**:
  - 승인 워크플로우 구현 (별도 이슈로 분리)
  - PostgreSQL 마이그레이션 (SQLite로 충분)
  - 추가 보안 테스트 케이스 작성 (기존 통합 테스트로 충분)

- **제약조건**:
  - WSL2 환경에서 Docker 컨테이너 접근
  - `/mnt/e/ai-data/sqlite/` 경로에 DB 파일 생성 권한 필요
  - MCP 서버가 RBAC_ENABLED=true 상태로 실행 중이어야 함

- **전제조건**:
  - ✅ RBAC 코드 구현 완료 (Phase 0-3)
  - ✅ app.py 통합 완료
  - ✅ 통합 테스트 작성 완료
  - ✅ 환경 변수 설정 완료 (RBAC_ENABLED=true)

---

## 작업 분해

### Phase 1: DB 초기화 및 시딩 (10분)
**목표**: Security DB 생성 및 기본 데이터 삽입

| 작업 | 설명 | 완료 기준 (DoD) | 우선순위 |
|------|------|-----------------|----------|
| T1-1: DB 경로 확인 | `/mnt/e/ai-data/sqlite/` 디렉터리 존재 및 권한 확인 | 디렉터리 접근 가능 | 높음 |
| T1-2: 시딩 스크립트 실행 | `seed_security_data.py --reset` 실행 | security.db 파일 생성 확인 | 높음 |
| T1-3: 데이터 검증 | SQLite 쿼리로 roles, permissions, users 확인 | 3 roles, 21 permissions, 3 users 존재 | 높음 |
| T1-4: MCP 서버 재시작 | Docker 컨테이너 재시작으로 DB 연결 확인 | 로그에 "RBAC system initialized" 출력 | 높음 |

**실행 명령:**
```bash
# 1. 컨테이너 접근
docker exec -it docker-mcp-server-1 bash

# 2. DB 시딩
cd /app
python scripts/seed_security_data.py --reset

# 3. 데이터 확인
sqlite3 /mnt/e/ai-data/sqlite/security.db "SELECT * FROM security_roles;"

# 4. 서버 재시작
exit
docker restart docker-mcp-server-1
docker logs docker-mcp-server-1 --tail 50
```

---

### Phase 2: RBAC 기능 테스트 (1시간)
**목표**: 역할별 권한 검증 및 감사 로그 기록 확인

| 작업 | 설명 | 완료 기준 (DoD) | 의존성 |
|------|------|-----------------|--------|
| T2-1: Guest 권한 테스트 | read_file 성공, execute_python 실패 (403) | 2개 시나리오 통과 | T1-4 완료 |
| T2-2: Developer 권한 테스트 | execute_python 성공, git_commit 실패 | 2개 시나리오 통과 | T1-4 완료 |
| T2-3: Admin 권한 테스트 | git_commit 허용 여부 확인 (403 미발생) | 1개 시나리오 통과, 필요 시 git_add 선행 | T1-4 완료 |
| T2-4: 감사 로그 확인 | DB에 성공/거부 로그 기록 확인 | audit_logs 테이블 조회 성공 | T2-1~T2-3 완료 |
| T2-5: 캐시 동작 검증 | 동일 요청 2회 실행 후 캐시 통계 확인 | `get_cache_stats()`로 캐시 증가 확인 | T2-1 완료 |

**테스트 시나리오:**
```bash
# Guest 사용자 - read_file 성공
curl -X POST http://localhost:8020/tools/read_file/call \
  -H "X-User-ID: guest_user" \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"path": "/mnt/workspace/README.md"}}'

# Guest 사용자 - execute_python 실패 (403 예상)
curl -X POST http://localhost:8020/tools/execute_python/call \
  -H "X-User-ID: guest_user" \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"code": "print(2+2)"}}'

# Developer 사용자 - execute_python 성공
curl -X POST http://localhost:8020/tools/execute_python/call \
  -H "X-User-ID: dev_user" \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"code": "print(2+2)"}}'

# Developer 사용자 - git_commit 실패 (403 예상)
curl -X POST http://localhost:8020/tools/git_commit/call \
  -H "X-User-ID: dev_user" \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"message": "test commit"}}'

# Admin 사용자 - git_commit 허용(403 미발생)
# (필요 시 사전 git_add 또는 add_all=true 사용)
curl -X POST http://localhost:8020/tools/git_commit/call \
  -H "X-User-ID: admin_user" \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"message": "admin commit"}}'

# 감사 로그 확인
sqlite3 /mnt/e/ai-data/sqlite/security.db \
  "SELECT user_id, tool_name, status, timestamp FROM security_audit_logs ORDER BY timestamp DESC LIMIT 10;"

# RBAC 캐시 통계 확인 (docker exec 내부에서 실행)
docker exec -it docker-mcp-server-1 python - <<'PY'
from rbac_manager import get_rbac_manager
import asyncio

async def main():
    manager = get_rbac_manager()
    stats = manager.get_cache_stats()
    print("RBAC cache stats:", stats)

asyncio.run(main())
PY

> 참고: `git_commit` 호출은 RBAC 허용 여부만 검증한다. 스테이징된 변경이 없으면 FastAPI 응답이 400/422 또는 1번 리턴 코드로 실패할 수 있으므로, 필요 시 `git_add` 도구 호출이나 `{"arguments": {"message": "...", "add_all": true}}`로 변경 내용을 준비한 뒤 상태 코드를 확인한다. 핵심 확인 포인트는 403이 발생하지 않는 것이다.
```

---

### Phase 3: 성능 벤치마크 (30분)
**목표**: RBAC 오버헤드 측정 및 성능 목표 달성 확인

| 작업 | 설명 | 완료 기준 (DoD) | 위험도 |
|------|------|-----------------|--------|
| T3-1: RBAC 검증 벤치마크 | 100회 권한 검사 실행 시간 측정 | p95 < 10ms | 낮음 |
| T3-2: Audit 로깅 벤치마크 | 100회 로그 삽입 시간 측정 | p95 < 5ms | 낮음 |
| T3-3: E2E 응답 시간 측정 | 실제 도구 호출 전체 시간 측정 | p95 < 500ms | 중간 |
| T3-4: 동시 요청 테스트 | 10명 동시 접속 시 성능 확인 | 성능 저하 없음 | 중간 |
| T3-5: 결과 문서화 | 벤치마크 결과를 표로 정리 | CSV/Markdown 파일 생성 | 낮음 |

**벤치마크 스크립트 (Python):**
```python
# benchmark_rbac.py
import asyncio
import time
import statistics
import httpx

async def benchmark_permission_check(iterations=100):
    """RBAC 권한 검증 성능 측정"""
    times = []
    async with httpx.AsyncClient() as client:
        for _ in range(iterations):
            start = time.perf_counter()
            response = await client.post(
                "http://localhost:8020/tools/read_file/call",
                headers={"X-User-ID": "dev_user"},
                json={"arguments": {"path": "/tmp/test.txt"}}
            )
            elapsed = (time.perf_counter() - start) * 1000  # ms
            times.append(elapsed)

    return {
        "mean": statistics.mean(times),
        "p50": statistics.median(times),
        "p95": statistics.quantiles(times, n=20)[18],
        "p99": statistics.quantiles(times, n=100)[98]
    }

async def main():
    print("RBAC Performance Benchmark")
    print("=" * 50)

    # 1. RBAC 검증 벤치마크
    rbac_stats = await benchmark_permission_check(100)
    print(f"\nRBAC Check (100 requests):")
    print(f"  Mean: {rbac_stats['mean']:.2f}ms")
    print(f"  P95:  {rbac_stats['p95']:.2f}ms (목표: <10ms)")
    print(f"  P99:  {rbac_stats['p99']:.2f}ms")

    # 2. 목표 달성 여부
    if rbac_stats['p95'] < 10:
        print("\n✅ RBAC 성능 목표 달성!")
    else:
        print(f"\n❌ RBAC 성능 목표 미달성 (p95: {rbac_stats['p95']:.2f}ms)")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### Phase 4: 운영 문서 작성 (1시간)
**목표**: SECURITY.md, RBAC_GUIDE.md 작성 완료

| 작업 | 설명 | 완료 기준 (DoD) | 위험도 |
|------|------|-----------------|--------|
| T4-1: SECURITY.md 작성 | 보안 시스템 개요 및 아키텍처 설명 | 5개 섹션 완성 | 낮음 |
| T4-2: RBAC_GUIDE.md 작성 | 역할/권한 설정 및 운영 가이드 | 사용 예제 포함 | 낮음 |
| T4-3: 트러블슈팅 섹션 | 일반적인 문제 및 해결 방법 정리 | 5개 이상 FAQ | 낮음 |
| T4-4: 문서 리뷰 | 기술 정확성 및 가독성 검토 | 리뷰 완료 | 낮음 |

**문서 구조:**

**SECURITY.md:**
```markdown
# Local AI Suite - 보안 시스템 가이드

## 개요
- RBAC 시스템 소개
- 주요 보안 기능 (AST 검증, 샌드박스, Rate Limiting, RBAC)

## 아키텍처
- SQLite 기반 RBAC 데이터베이스
- FastAPI 미들웨어 통합
- 감사 로깅 시스템

## 권한 모델
- 역할: Guest, Developer, Admin
- 권한: 18개 MCP 도구 + 파일 작업

## 운영 가이드
- RBAC 활성화/비활성화
- 사용자 추가/삭제
- 역할 변경

## 모니터링
- 감사 로그 조회
- 권한 거부 통계
```

**RBAC_GUIDE.md:**
```markdown
# RBAC 설정 및 운영 매뉴얼

## 빠른 시작
1. DB 초기화
2. 사용자 추가
3. 권한 테스트

## 역할별 권한 매트릭스
| 도구 | Guest | Developer | Admin |
|------|-------|-----------|-------|
| read_file | ✅ | ✅ | ✅ |
| execute_python | ❌ | ✅ | ✅ |
| git_commit | ❌ | ❌ | ✅ |

## 사용자 관리
- 사용자 추가 SQL
- 역할 변경 방법
- 사용자 비활성화

## 트러블슈팅
- DB 잠금 문제
- 캐시 무효화
- 로그 조회
```

---

## 실행 계획

### 작업 순서 및 타임라인
```
[10분] Phase 1: DB 시딩
         ↓
[1시간] Phase 2: 기능 테스트
         ↓
[30분] Phase 3: 성능 벤치마크
         ↓
[1시간] Phase 4: 문서 작성
         ↓
[총 2시간 40분 완료]
```

### 우선순위 매트릭스
```
긴급 & 중요           | 중요하지만 덜 긴급
T1-2 (DB 시딩)        | T4-1 (SECURITY.md)
T2-1~T2-3 (권한 테스트) | T4-2 (RBAC_GUIDE.md)
----------------------|----------------------
긴급하지만 덜 중요     | 덜 중요 & 덜 긴급
T3-4 (동시 요청)       | T4-3 (트러블슈팅)
```

### 마일스톤
- **0:10**: DB 초기화 완료, MCP 서버 재시작
- **1:10**: 역할별 권한 테스트 완료, 감사 로그 확인
- **1:40**: 성능 벤치마크 완료, 목표 달성 확인
- **2:40**: 운영 문서 작성 완료, Issue #8 종료

### 위험 요소 및 대응 방안
| 위험 요소 | 가능성 | 영향도 | 대응 방안 |
|-----------|--------|--------|-----------|
| DB 시딩 실패 (권한 문제) | 중간 | 높음 | Docker exec로 컨테이너 내부에서 실행 |
| 성능 목표 미달성 | 낮음 | 중간 | 캐싱 설정 조정, WAL 모드 확인 |
| MCP 도구 호출 실패 | 낮음 | 높음 | 서버 로그 확인, 미들웨어 순서 점검 |
| 동시 접속 시 DB 잠금 | 중간 | 낮음 | WAL 모드로 이미 해결, 재시도 로직 존재 |

---

## 품질 체크리스트

### Phase 1 완료 확인사항
- [ ] security.db 파일 존재 (`/mnt/e/ai-data/sqlite/security.db`)
- [ ] 3개 역할 생성 확인 (guest, developer, admin)
- [ ] 21개 권한 생성 확인
- [ ] 3명 테스트 사용자 생성 확인
- [ ] MCP 서버 로그에 "RBAC system initialized" 출력

### Phase 2 완료 확인사항
- [ ] Guest 사용자: read_file 성공, execute_python 실패 (403)
- [ ] Developer 사용자: execute_python 성공, git_commit 실패 (403)
- [ ] Admin 사용자: 고급 도구 호출 시 403 미발생 (`git_commit` 등)
- [ ] 감사 로그 테이블에 모든 요청 기록됨
- [ ] `get_cache_stats()`로 permission_cache_size 증가 확인

### Phase 3 완료 확인사항
- [ ] RBAC 검증 p95 < 10ms
- [ ] Audit 로깅 p95 < 5ms
- [ ] E2E 응답 시간 p95 < 500ms
- [ ] 동시 요청 10개 처리 성공
- [ ] 벤치마크 결과 파일 생성

### Phase 4 완료 확인사항
- [ ] SECURITY.md 작성 완료 (5개 섹션)
- [ ] RBAC_GUIDE.md 작성 완료 (역할별 권한 매트릭스 포함)
- [ ] 트러블슈팅 가이드 작성 (5개 이상 FAQ)
- [ ] 문서 리뷰 완료
- [ ] docs/security/ 디렉터리에 파일 저장

### 전체 완료 기준
- [ ] 모든 Phase 1-4 체크리스트 완료
- [ ] Issue #8 완료 기준 (DoD) 충족
- [ ] RBAC 시스템 운영 준비 완료
- [ ] IMPLEMENTATION_SUMMARY.md 업데이트 (100% 완료 표시)
- [ ] ri_4.md 문서 최종 업데이트

---

## 리소스 및 참고자료

### 필요한 리소스
- **인력**: 1명 (Backend/DevOps, 2-3시간)
- **도구**:
  - Docker CLI (컨테이너 접근)
  - SQLite CLI (DB 조회)
  - curl (API 테스트)
  - Python 3.11 (벤치마크 스크립트)
- **인프라**:
  - 실행 중인 MCP 서버 (docker-mcp-server-1)
  - `/mnt/e/ai-data/sqlite/` 디렉터리 쓰기 권한

### 기존 구현 파일
- `services/mcp-server/scripts/seed_security_data.py` - DB 시딩
- `services/mcp-server/security_database.py` - DB Manager
- `services/mcp-server/rbac_manager.py` - RBAC 로직
- `services/mcp-server/audit_logger.py` - 감사 로깅
- `services/mcp-server/tests/integration/test_rbac_integration.py` - 통합 테스트

### 참고 문서
- `docs/progress/v1/ri_4.md` - Issue #8 상세 계획
- `docs/security/IMPLEMENTATION_SUMMARY.md` - 구현 요약
- `docs/security/architecture.md` - 아키텍처 설계
- `docs/adr/adr-001-sqlite-vs-postgresql.md` - DB 선택 배경

---

## 다음 단계 (Issue #8 완료 후)

### 즉시 가능한 작업
1. ✅ RBAC 시스템 실사용 투입
2. ✅ 팀원에게 운영 문서 공유
3. ✅ Issue #8 완료 및 PR 생성

### 장기 과제 (별도 이슈)
1. **승인 워크플로우 구현** (1-2주)
   - HIGH/CRITICAL 도구 실행 전 승인 대기
   - 승인 요청/처리 API
   - 승인자 역할 및 권한 관리

2. **PostgreSQL 마이그레이션** (선택, 1주)
   - SQLite 동시성 제한 발생 시
   - 스키마 마이그레이션 스크립트

3. **모니터링 대시보드** (1주)
   - Grafana로 감사 로그 시각화
   - 권한 거부 통계 차트

---

**💡 추가 고려사항**
- 벤치마크 결과가 목표 미달 시: 캐시 TTL 조정 (기본 5분 → 10분)
- DB 잠금 발생 시: WAL 체크포인트 주기 확인
- 문서 작성 시간 부족 시: Phase 4를 별도 세션으로 분리 가능

**🎯 성공 기준**
- 2-3시간 내 모든 Phase 완료
- RBAC 시스템 실사용 투입 가능
- Issue #8 완료 및 PR 머지 준비 완료
