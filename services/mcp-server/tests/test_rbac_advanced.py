#!/usr/bin/env python3
"""
Advanced RBAC tests aligned with the async security database.

These tests focus on:
1. Permission checks through RBACManager (including caching behaviour)
2. Approval requirements based on permission sensitivity levels
3. Audit logging helper interactions for denied and granted requests
4. Security validator coverage for dangerous pattern detection
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio

# Ensure service modules are importable when tests are executed from pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rbac_manager import RBACManager
from security import SecurityError, SecurityValidator, detect_dangerous_patterns
from security_database import SecurityDatabase, get_security_database, reset_security_database
from settings import SecuritySettings


# ============================================================================
# Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def security_db(tmp_path: Path, monkeypatch) -> AsyncGenerator[SecurityDatabase, None]:
    """
    Provide a temporary security database for RBAC tests.

    - Uses reset_security_database to point the singleton to a temporary path.
    - Forces RBAC and approval workflow to be enabled for the duration of the test.
    """
    db_path = tmp_path / "rbac-tests.db"
    original_path = reset_security_database(str(db_path))

    # Enable RBAC & approval workflow during tests
    monkeypatch.setattr(SecuritySettings, "RBAC_ENABLED", True, raising=False)
    monkeypatch.setattr(SecuritySettings, "APPROVAL_WORKFLOW_ENABLED", True, raising=False)

    # Create fresh database schema
    db = get_security_database()
    await db.initialize()

    try:
        yield db
    finally:
        # Restore singleton and settings
        reset_security_database(original_path)
        monkeypatch.setattr(SecuritySettings, "RBAC_ENABLED", False, raising=False)
        monkeypatch.setattr(SecuritySettings, "APPROVAL_WORKFLOW_ENABLED", False, raising=False)


@pytest_asyncio.fixture
async def rbac_manager(security_db: SecurityDatabase) -> AsyncGenerator[RBACManager, None]:
    """
    Create RBACManager instance wired to the temporary database fixture.
    """
    manager = RBACManager()
    manager.db = security_db  # type: ignore[attr-defined]
    manager._permission_cache.clear()
    manager._role_cache.clear()
    yield manager
    manager._permission_cache.clear()
    manager._role_cache.clear()


# ============================================================================
# Helper utilities
# ============================================================================


async def seed_basic_permissions(db: SecurityDatabase) -> None:
    """Populate the database with core roles, users, and permissions."""
    await db.insert_permission(
        permission_name="read_file",
        description="Read file contents",
        sensitivity_level="LOW",
        resource_type="tool",
        action="execute",
    )
    await db.insert_permission(
        permission_name="write_file",
        description="Write file contents",
        sensitivity_level="MEDIUM",
        resource_type="tool",
        action="execute",
    )
    await db.insert_permission(
        permission_name="execute_python",
        description="Execute arbitrary python code",
        sensitivity_level="HIGH",
        resource_type="tool",
        action="execute",
    )

    # Create users which also ensures roles exist
    await db.insert_user("viewer_user", "viewer")
    await db.insert_user("editor_user", "editor")
    await db.insert_user("admin_user", "admin")

    # Assign permissions to roles
    await db.assign_permission_to_role("viewer", "read_file")
    await db.assign_permission_to_role("editor", "read_file")
    await db.assign_permission_to_role("editor", "write_file")
    await db.assign_permission_to_role("admin", "read_file")
    await db.assign_permission_to_role("admin", "write_file")
    await db.assign_permission_to_role("admin", "execute_python")


# ============================================================================
# Tests
# ============================================================================


@pytest.mark.asyncio
async def test_permission_granted_and_cached(
    rbac_manager: RBACManager, security_db: SecurityDatabase
) -> None:
    """
    Verify that a user with the proper role can access a permission and that
    subsequent checks hit the RBACManager cache.
    """
    await seed_basic_permissions(security_db)

    allowed, reason = await rbac_manager.check_permission("admin_user", "write_file")
    assert allowed, reason

    # Second call should be served from cache without new DB hits.
    allowed_cached, reason_cached = await rbac_manager.check_permission("admin_user", "write_file")
    assert allowed_cached, reason_cached
    assert "admin_user:write_file" in rbac_manager._permission_cache


@pytest.mark.asyncio
async def test_permission_denied_for_missing_role(
    rbac_manager: RBACManager, security_db: SecurityDatabase
) -> None:
    """User without the permission should receive a denied response."""
    await seed_basic_permissions(security_db)

    allowed, reason = await rbac_manager.check_permission("viewer_user", "write_file")
    assert not allowed
    assert "denied" in reason.lower()


@pytest.mark.asyncio
async def test_permission_denied_unknown_user(rbac_manager: RBACManager) -> None:
    """Unknown users should receive a descriptive error."""
    allowed, reason = await rbac_manager.check_permission("unknown_user", "read_file")
    assert not allowed
    assert "not found" in reason


@pytest.mark.asyncio
async def test_requires_approval_high_sensitivity(
    rbac_manager: RBACManager, security_db: SecurityDatabase
) -> None:
    """HIGH sensitivity permissions should require approval."""
    await seed_basic_permissions(security_db)

    requires = await rbac_manager.requires_approval("execute_python")
    assert requires, "High sensitivity tools should require approval"

    requires_medium = await rbac_manager.requires_approval("write_file")
    assert not requires_medium, "Medium sensitivity tools should not require approval"


@pytest.mark.asyncio
async def test_audit_log_insert_and_query(security_db: SecurityDatabase) -> None:
    """Ensure audit logs can be inserted and queried back correctly."""
    log_id = await security_db.insert_audit_log(
        user_id="viewer_user",
        tool_name="read_file",
        action="execute",
        status="success",
        execution_time_ms=42,
        request_data=json.dumps({"path": "/tmp/test.txt"}),
    )
    assert log_id > 0

    logs = await security_db.get_audit_logs(
        user_id="viewer_user", tool_name="read_file", status="success", limit=1
    )
    assert len(logs) == 1
    entry = logs[0]
    assert entry["user_id"] == "viewer_user"
    assert entry["tool_name"] == "read_file"
    assert entry["status"] == "success"
    assert entry["execution_time_ms"] == 42


def test_security_validator_detects_dangerous_patterns() -> None:
    """The security validator should flag dangerous code patterns."""
    validator = SecurityValidator()
    dangerous_code = "import subprocess\nsubprocess.call(['rm', '-rf', '/'])"
    safe_code = "print('hello world')"

    # Safe code should pass validation
    assert validator.validate_code(safe_code)

    # Dangerous code should raise SecurityError
    with pytest.raises(SecurityError):
        validator.validate_code(dangerous_code)

    # Helper function should provide a descriptive report
    results = detect_dangerous_patterns(dangerous_code)
    assert results["is_safe"] is False
    assert any("subprocess" in issue for issue in results["issues"])
