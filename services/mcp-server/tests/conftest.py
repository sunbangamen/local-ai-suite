#!/usr/bin/env python3
"""
Pytest Configuration and Shared Fixtures
MCP Server Security Tests
"""

import asyncio
import os
import sys
import tempfile
import subprocess
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
import aiosqlite

try:
    from settings import SecuritySettings
    from security_database import get_security_database, reset_security_database
except ImportError:  # pragma: no cover
    PARENT = Path(__file__).resolve().parents[1]
    if str(PARENT) not in sys.path:
        sys.path.insert(0, str(PARENT))

    from settings import SecuritySettings  # type: ignore
    from security_database import get_security_database, reset_security_database  # type: ignore

# Tell pytest to ignore __init__.py in service root (prevents relative import errors)
collect_ignore = ["../__init__.py"]
collect_ignore_glob = ["../__init__.py"]


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def temp_db_path() -> Generator[Path, None, None]:
    """Temporary SQLite database path for testing"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    yield db_path

    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest_asyncio.fixture(autouse=True)
async def override_security_paths(monkeypatch, temp_db_path: Path):
    """Provide each test with an isolated, writable security DB."""
    temp_dir = temp_db_path.parent

    original_db_path = SecuritySettings.SECURITY_DB_PATH
    original_data_dir = SecuritySettings.DATA_DIR

    monkeypatch.setenv("SECURITY_DB_PATH", str(temp_db_path))
    monkeypatch.setenv("DATA_DIR", str(temp_dir))

    SecuritySettings.SECURITY_DB_PATH = str(temp_db_path)
    SecuritySettings.DATA_DIR = str(temp_dir)

    # Reset singleton and initialize schema on the temporary database
    reset_security_database()
    db = get_security_database()
    await db.initialize()

    yield

    reset_security_database()
    SecuritySettings.SECURITY_DB_PATH = original_db_path
    SecuritySettings.DATA_DIR = original_data_dir
    monkeypatch.delenv("SECURITY_DB_PATH", raising=False)
    monkeypatch.delenv("DATA_DIR", raising=False)


@pytest.fixture(scope="function")
async def test_db(temp_db_path: Path) -> AsyncGenerator[aiosqlite.Connection, None]:
    """SQLite test database connection with schema"""
    async with aiosqlite.connect(temp_db_path) as db:
        # Enable WAL mode
        await db.execute("PRAGMA journal_mode=WAL")

        # Create tables
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS security_users (
                user_id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                role_id INTEGER,
                created_at TEXT DEFAULT (CURRENT_TIMESTAMP),
                is_active INTEGER DEFAULT 1
            )
        """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS security_roles (
                role_id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_name TEXT NOT NULL UNIQUE,
                description TEXT
            )
        """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS security_permissions (
                permission_id INTEGER PRIMARY KEY AUTOINCREMENT,
                permission_name TEXT NOT NULL UNIQUE,
                resource_type TEXT,
                action TEXT,
                sensitivity_level INTEGER DEFAULT 0
            )
        """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS security_role_permissions (
                role_id INTEGER,
                permission_id INTEGER,
                PRIMARY KEY (role_id, permission_id),
                FOREIGN KEY (role_id) REFERENCES security_roles(role_id) ON DELETE CASCADE,
                FOREIGN KEY (permission_id) REFERENCES security_permissions(permission_id) ON DELETE CASCADE
            )
        """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS security_audit_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                tool_name TEXT,
                action TEXT,
                status TEXT,
                error_message TEXT,
                timestamp TEXT DEFAULT (CURRENT_TIMESTAMP),
                execution_time_ms INTEGER
            )
        """
        )

        await db.execute(
            """
            CREATE VIEW IF NOT EXISTS v_user_permissions AS
            SELECT
                u.user_id,
                u.username,
                r.role_name,
                p.permission_name,
                p.resource_type,
                p.action,
                p.sensitivity_level
            FROM security_users u
            JOIN security_roles r ON u.role_id = r.role_id
            JOIN security_role_permissions rp ON r.role_id = rp.role_id
            JOIN security_permissions p ON rp.permission_id = p.permission_id
            WHERE u.is_active = 1
            """
        )

        await db.commit()

        yield db


@pytest.fixture(scope="function")
async def seeded_db(test_db: aiosqlite.Connection) -> aiosqlite.Connection:
    """Test database with seeded default data"""
    # Insert default roles
    await test_db.execute(
        "INSERT INTO security_roles (role_name, description) VALUES (?, ?)",
        ("guest", "Read-only access"),
    )
    await test_db.execute(
        "INSERT INTO security_roles (role_name, description) VALUES (?, ?)",
        ("developer", "Developer access with code execution"),
    )
    await test_db.execute(
        "INSERT INTO security_roles (role_name, description) VALUES (?, ?)",
        ("admin", "Full administrative access"),
    )

    # Insert permissions
    permissions = [
        ("read_file", "file", "read", 0),
        ("write_file", "file", "write", 1),
        ("execute_python", "tool", "execute", 2),
        ("execute_bash", "tool", "execute", 2),
        ("git_commit", "tool", "execute", 3),
    ]

    for perm_name, resource, action, sensitivity in permissions:
        await test_db.execute(
            """
            INSERT INTO security_permissions (permission_name, resource_type, action, sensitivity_level)
            VALUES (?, ?, ?, ?)
            """,
            (perm_name, resource, action, sensitivity),
        )

    # Map role-permissions
    # Guest: read_file only
    await test_db.execute(
        "INSERT INTO security_role_permissions (role_id, permission_id) VALUES (1, 1)"
    )

    # Developer: read_file, write_file, execute_python, execute_bash
    await test_db.executemany(
        "INSERT INTO security_role_permissions (role_id, permission_id) VALUES (?, ?)",
        [(2, perm_id) for perm_id in [1, 2, 3, 4]],
    )

    # Admin: all permissions
    await test_db.executemany(
        "INSERT INTO security_role_permissions (role_id, permission_id) VALUES (?, ?)",
        [(3, perm_id) for perm_id in [1, 2, 3, 4, 5]],
    )

    # Insert test users
    await test_db.execute(
        "INSERT INTO security_users (user_id, username, role_id, is_active) VALUES (?, ?, ?, 1)",
        ("guest_user", "Guest User", 1),
    )
    await test_db.execute(
        "INSERT INTO security_users (user_id, username, role_id, is_active) VALUES (?, ?, ?, 1)",
        ("dev_user", "Developer User", 2),
    )
    await test_db.execute(
        "INSERT INTO security_users (user_id, username, role_id, is_active) VALUES (?, ?, ?, 1)",
        ("admin_user", "Admin User", 3),
    )

    await test_db.commit()

    return test_db


@pytest.fixture(scope="function")
def test_settings() -> SecuritySettings:
    """Test security settings with overrides"""
    # Save original values
    original_rbac = SecuritySettings.RBAC_ENABLED
    original_db_path = SecuritySettings.SECURITY_DB_PATH

    # Override for testing
    SecuritySettings.RBAC_ENABLED = True
    SecuritySettings.SECURITY_DB_PATH = ":memory:"

    yield SecuritySettings

    # Restore original values
    SecuritySettings.RBAC_ENABLED = original_rbac
    SecuritySettings.SECURITY_DB_PATH = original_db_path


@pytest.fixture(scope="function")
def mock_user_id() -> str:
    """Mock user ID for testing"""
    return "test_user_123"


@pytest.fixture(scope="function")
def mock_tool_name() -> str:
    """Mock tool name for testing"""
    return "execute_python"


@pytest.fixture(scope="session", autouse=True)
def setup_integration_test_db():
    """
    자동으로 통합 테스트용 DB 시딩

    - 통합 테스트 시작 전 실행
    - INSERT OR IGNORE로 중복 방지
    - 반복 실행 가능
    """
    # 통합 테스트 실행 여부 확인 (integration 마커가 있는 테스트가 선택되었는지)
    # pytest의 config를 통해 확인하기 어려우므로, 환경 변수나 마커로 제어

    # RBAC 활성화 확인
    if not SecuritySettings.is_rbac_enabled():
        # RBAC 비활성화 시 스킵
        yield
        return

    # 시딩 스크립트 경로
    script_dir = Path(__file__).parent.parent / "scripts"
    seed_script = script_dir / "seed_security_data.py"

    if not seed_script.exists():
        print(f"Warning: Seed script not found: {seed_script}")
        yield
        return

    # DB 경로 확인
    SecuritySettings.get_db_path()

    # 테스트용 임시 DB 사용 (선택적)
    # 환경 변수 TEST_MODE가 설정되어 있으면 실제 DB 건드리지 않음
    if os.getenv("TEST_MODE") == "isolated":
        # 임시 DB 파일 생성 (delete=False로 수동 관리)
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            test_db_path = f.name

        # 싱글턴 리셋 및 경로 오버라이드
        original_path = reset_security_database(test_db_path)
        print(f"Test DB isolation enabled: {test_db_path}")

        # RBAC 활성화 (테스트용)
        original_rbac_enabled = SecuritySettings.RBAC_ENABLED
        SecuritySettings.RBAC_ENABLED = True

        # 시딩 실행
        try:
            result = subprocess.run(
                [sys.executable, str(seed_script), "--reset"],
                capture_output=True,
                text=True,
                cwd=script_dir.parent,
            )
            if result.returncode != 0:
                print(f"Warning: Seed script failed: {result.stderr}")
            else:
                print(f"Test DB seeded successfully: {test_db_path}")
        except Exception as e:
            print(f"Warning: Failed to run seed script: {e}")

        yield  # 테스트 실행

        # 정리: 싱글턴 복구
        reset_security_database(original_path)
        SecuritySettings.RBAC_ENABLED = original_rbac_enabled
        print(f"Test DB restored: {original_path}")

        # 임시 DB 삭제
        Path(test_db_path).unlink(missing_ok=True)
        # WAL/SHM 파일도 삭제
        Path(f"{test_db_path}-wal").unlink(missing_ok=True)
        Path(f"{test_db_path}-shm").unlink(missing_ok=True)
    else:
        # 실제 DB 사용 (기본)
        # INSERT OR IGNORE 보장을 위해 스크립트 실행 (--reset 없이)
        try:
            result = subprocess.run(
                [sys.executable, str(seed_script)],
                capture_output=True,
                text=True,
                cwd=script_dir.parent,
            )
            if result.returncode != 0:
                print(f"Warning: Seed script failed: {result.stderr}")
            else:
                print("Integration test DB seeded successfully")
        except Exception as e:
            print(f"Warning: Failed to run seed script: {e}")

        yield
        # 실제 DB는 정리하지 않음 (운영 데이터 보존)


# Markers for skipping tests based on environment
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "docker: mark test as requiring Docker (skip if Docker unavailable)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow (deselect with '-m \"not slow\"')"
    )


def pytest_collection_modifyitems(config, items):
    """Skip Docker tests if Docker is not available"""
    try:
        import subprocess

        subprocess.run(["docker", "ps"], capture_output=True, check=True)
        docker_available = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        docker_available = False

    skip_docker = pytest.mark.skip(reason="Docker not available")

    for item in items:
        if "requires_docker" in item.keywords and not docker_available:
            item.add_marker(skip_docker)


# ============================================================================
# Approval Workflow Fixtures (Issue #26, Phase 4)
# ============================================================================


@pytest.fixture(scope="function")
async def auto_approve(monkeypatch):
    """
    Auto-approve fixture for CI/CD testing (Issue #26, Phase 4)

    Mocks the RBAC Manager's _wait_for_approval to immediately approve requests.
    Used in CI environments where manual approval is impossible.

    Usage:
        @pytest.mark.asyncio
        async def test_approval_flow_ci(auto_approve):
            # Approval requests will be auto-approved
            result = await call_mcp_tool("run_command")
            assert result["status"] == "success"
    """
    try:
        from rbac_manager import get_rbac_manager, RBACManager

    except ImportError:  # pragma: no cover
        PARENT = Path(__file__).resolve().parents[1]
        if str(PARENT) not in sys.path:
            sys.path.insert(0, str(PARENT))
        from rbac_manager import get_rbac_manager, RBACManager  # type: ignore

    import uuid
    import json

    # Save original method
    rbac_manager = get_rbac_manager()
    original_wait = rbac_manager._wait_for_approval

    # Mock auto-approve
    async def mock_wait_for_approval(user_id, tool_name, request_data, timeout):
        """Immediately approve requests without waiting"""
        from security_database import get_security_database

        request_id = str(uuid.uuid4())
        db = get_security_database()

        # Create and immediately approve the request
        success = await db.create_approval_request(
            request_id=request_id,
            tool_name=tool_name,
            user_id=user_id,
            role="test_user",
            request_data=json.dumps(request_data),
            timeout_seconds=timeout,
        )

        if success:
            # Immediately approve
            await db.update_approval_status(
                request_id=request_id,
                status="approved",
                responder_id="ci_bot",
                response_reason="Auto-approved for CI testing",
            )
        return success

    # Apply mock
    monkeypatch.setattr(rbac_manager, "_wait_for_approval", mock_wait_for_approval)

    yield  # Test runs with mocked approval

    # Restore original method
    monkeypatch.setattr(rbac_manager, "_wait_for_approval", original_wait)


@pytest.fixture(scope="function")
def approval_settings(monkeypatch):
    """
    Enable approval workflow settings for testing (Issue #26, Phase 4)

    Usage:
        @pytest.mark.asyncio
        async def test_approval_required(approval_settings):
            # APPROVAL_WORKFLOW_ENABLED=true
            result = await handle_tool_request("run_command")
            assert result["approval_required"] == True
    """
    try:
        from settings import SecuritySettings

    except ImportError:  # pragma: no cover
        PARENT = Path(__file__).resolve().parents[1]
        if str(PARENT) not in sys.path:
            sys.path.insert(0, str(PARENT))
        from settings import SecuritySettings  # type: ignore

    # Save original values
    original_approval_enabled = SecuritySettings.APPROVAL_WORKFLOW_ENABLED
    original_approval_timeout = SecuritySettings.APPROVAL_TIMEOUT
    original_approval_polling = SecuritySettings.APPROVAL_POLLING_INTERVAL

    # Enable approval workflow for testing
    monkeypatch.setenv("APPROVAL_WORKFLOW_ENABLED", "true")
    monkeypatch.setenv("APPROVAL_TIMEOUT", "300")
    monkeypatch.setenv("APPROVAL_POLLING_INTERVAL", "1")

    SecuritySettings.APPROVAL_WORKFLOW_ENABLED = True
    SecuritySettings.APPROVAL_TIMEOUT = 300
    SecuritySettings.APPROVAL_POLLING_INTERVAL = 1

    yield SecuritySettings

    # Restore original values
    SecuritySettings.APPROVAL_WORKFLOW_ENABLED = original_approval_enabled
    SecuritySettings.APPROVAL_TIMEOUT = original_approval_timeout
    SecuritySettings.APPROVAL_POLLING_INTERVAL = original_approval_polling
    monkeypatch.delenv("APPROVAL_WORKFLOW_ENABLED", raising=False)
    monkeypatch.delenv("APPROVAL_TIMEOUT", raising=False)
    monkeypatch.delenv("APPROVAL_POLLING_INTERVAL", raising=False)
