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
import aiosqlite

# Add parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from settings import SecuritySettings
from security_database import reset_security_database


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
                created_at TEXT DEFAULT (CURRENT_TIMESTAMP)
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
                action TEXT
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
        ("read_file", "file", "read"),
        ("write_file", "file", "write"),
        ("execute_python", "tool", "execute"),
        ("execute_bash", "tool", "execute"),
        ("git_commit", "tool", "execute"),
    ]

    for perm_name, resource, action in permissions:
        await test_db.execute(
            "INSERT INTO security_permissions (permission_name, resource_type, action) VALUES (?, ?, ?)",
            (perm_name, resource, action),
        )

    # Map role-permissions
    # Guest: read_file only
    await test_db.execute(
        "INSERT INTO security_role_permissions (role_id, permission_id) VALUES (1, 1)"
    )

    # Developer: read_file, write_file, execute_python, execute_bash
    for perm_id in [1, 2, 3, 4]:
        await test_db.execute(
            "INSERT INTO security_role_permissions (role_id, permission_id) VALUES (2, ?)",
            (perm_id,),
        )

    # Admin: all permissions
    for perm_id in [1, 2, 3, 4, 5]:
        await test_db.execute(
            "INSERT INTO security_role_permissions (role_id, permission_id) VALUES (3, ?)",
            (perm_id,),
        )

    # Insert test users
    await test_db.execute(
        "INSERT INTO security_users (user_id, username, role_id) VALUES (?, ?, ?)",
        ("guest_user", "Guest User", 1),
    )
    await test_db.execute(
        "INSERT INTO security_users (user_id, username, role_id) VALUES (?, ?, ?)",
        ("dev_user", "Developer User", 2),
    )
    await test_db.execute(
        "INSERT INTO security_users (user_id, username, role_id) VALUES (?, ?, ?)",
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
    config.addinivalue_line("markers", "slow: mark test as slow (deselect with '-m \"not slow\"')")


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
