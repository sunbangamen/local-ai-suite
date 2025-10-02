# Test Isolation Guide

## Overview

통합 테스트는 기본적으로 실제 DB를 사용하지만, `TEST_MODE=isolated` 환경변수로 임시 DB를 사용하는 격리 모드를 활성화할 수 있습니다.

## Usage

### 기본 모드 (실제 DB 사용)

```bash
# RBAC이 활성화된 경우, 실제 DB에 INSERT OR IGNORE로 시딩
RBAC_ENABLED=true pytest tests/integration/test_rbac_integration.py -v
```

- 실제 DB 경로: `SecuritySettings.get_db_path()` (예: `/mnt/e/ai-data/sqlite/security.db`)
- 기존 데이터 보존 (INSERT OR IGNORE)
- 테스트 후 정리하지 않음

### 격리 모드 (임시 DB 사용)

```bash
# 임시 DB를 생성하여 테스트, 완료 후 자동 삭제
TEST_MODE=isolated RBAC_ENABLED=true pytest tests/integration/test_rbac_integration.py -v
```

- 임시 DB 경로: `/tmp/tmp*.db` (자동 생성)
- 싱글턴 리셋으로 테스트 프로세스가 임시 DB 사용
- 테스트 완료 후 임시 DB 및 WAL/SHM 파일 자동 삭제

## Implementation Details

### 싱글턴 리셋 메커니즘

`security_database.py`의 `reset_security_database()` 함수:

```python
def reset_security_database(db_path: Optional[str] = None) -> Optional[str]:
    """
    Reset singleton instance and optionally override DB path

    Args:
        db_path: New database path (overrides SecuritySettings.SECURITY_DB_PATH)

    Returns:
        Original DB path (for restoration)
    """
    global _security_db

    # Get original path
    original_path = str(SecuritySettings.get_db_path())

    # Reset singleton
    _security_db = None

    # Override path if provided
    if db_path:
        SecuritySettings.SECURITY_DB_PATH = db_path

    return original_path
```

### Fixture Workflow (TEST_MODE=isolated)

1. **Setup (before yield)**:
   - 임시 DB 파일 생성 (`tempfile.NamedTemporaryFile`)
   - `reset_security_database(test_db_path)` 호출 → 싱글턴 리셋 및 경로 오버라이드
   - `SecuritySettings.RBAC_ENABLED = True` 강제 설정
   - `seed_security_data.py --reset` 실행 → 임시 DB 초기화 및 시딩

2. **Test Execution**:
   - `yield` → 테스트 실행
   - 모든 DB 작업은 임시 DB에 수행됨
   - 감사 로그도 임시 DB에 기록됨

3. **Teardown (after yield)**:
   - `reset_security_database(original_path)` → 원래 경로로 복구
   - `SecuritySettings.RBAC_ENABLED` 복구
   - 임시 DB 파일 삭제 (`*.db`, `*.db-wal`, `*.db-shm`)

## Verification

### 임시 DB 사용 확인

테스트 실행 시 다음 로그가 출력되어야 합니다:

```
Test DB isolation enabled: /tmp/tmp12345.db
Test DB seeded successfully: /tmp/tmp12345.db
... (테스트 실행)
Test DB restored: /mnt/e/ai-data/sqlite/security.db
```

### 감사 로그 확인

격리 모드에서는 감사 로그가 임시 DB에만 기록되고, 실제 DB는 영향받지 않습니다.

```python
# 테스트 내부에서 확인 가능
from security_database import get_security_database

db = get_security_database()
logs = await db.get_audit_logs()  # 임시 DB의 로그만 조회됨
```

### 실제 DB 보존 확인

격리 모드 실행 전후로 실제 DB를 확인:

```bash
# 테스트 전
sqlite3 /mnt/e/ai-data/sqlite/security.db "SELECT COUNT(*) FROM security_audit_logs;"

# 격리 모드 테스트 실행
TEST_MODE=isolated RBAC_ENABLED=true pytest tests/integration/ -v

# 테스트 후 (카운트가 동일해야 함)
sqlite3 /mnt/e/ai-data/sqlite/security.db "SELECT COUNT(*) FROM security_audit_logs;"
```

## Troubleshooting

### 문제: 테스트 중 "database is locked" 에러

**원인**: 임시 DB 파일이 yield 전에 삭제되거나, WAL 모드가 제대로 설정되지 않음

**해결**:
- Fixture가 `delete=False`로 임시 파일 생성하는지 확인
- 시딩 스크립트가 WAL 모드를 활성화하는지 확인
- yield 이후에만 파일 삭제가 실행되는지 확인

### 문제: 실제 DB가 여전히 사용됨

**원인**: 싱글턴이 리셋되지 않아 기존 인스턴스가 계속 사용됨

**해결**:
- `reset_security_database(test_db_path)` 호출이 시딩 전에 실행되는지 확인
- `SecuritySettings.get_db_path()` 출력으로 경로 확인
- 로그에서 "Security DB path overridden" 메시지 확인

### 문제: 테스트 완료 후 임시 파일이 남아있음

**원인**: 예외 발생으로 teardown이 실행되지 않음

**해결**:
- `missing_ok=True`로 파일 삭제 안전성 확보 (이미 적용됨)
- `/tmp/tmp*.db*` 파일 수동 정리: `rm /tmp/tmp*.db*`

## Best Practices

1. **로컬 개발**: `TEST_MODE=isolated` 사용으로 실제 DB 보호
2. **CI/CD**: 격리 모드로 병렬 테스트 안전성 확보
3. **디버깅**: 기본 모드로 실제 DB 상태 확인
4. **성능 테스트**: 실제 DB로 프로덕션 환경 시뮬레이션

## Examples

### 단일 테스트 격리 실행

```bash
TEST_MODE=isolated RBAC_ENABLED=true pytest tests/integration/test_rbac_integration.py::TestRBACIntegration::test_guest_denied_execute_python -v
```

### 전체 통합 테스트 격리 실행

```bash
TEST_MODE=isolated RBAC_ENABLED=true pytest tests/integration/ -v
```

### 실제 DB로 디버깅

```bash
RBAC_ENABLED=true pytest tests/integration/test_rbac_integration.py::TestRBACIntegration::test_developer_allowed_execute_python -v -s
```

### 성능 비교 (격리 vs 실제)

```bash
# 격리 모드
time TEST_MODE=isolated RBAC_ENABLED=true pytest tests/integration/ -v

# 실제 DB
time RBAC_ENABLED=true pytest tests/integration/ -v
```
