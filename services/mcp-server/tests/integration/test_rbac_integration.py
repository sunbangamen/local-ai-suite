#!/usr/bin/env python3
"""
RBAC Integration Tests
E2E tests for RBAC middleware with audit logging
"""

import asyncio
import sys
from pathlib import Path
from tempfile import gettempdir

import pytest
import pytest_asyncio
from httpx import AsyncClient

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app import app
from security_database import get_security_database
from settings import SecuritySettings

TEST_FILE_PATH = str(Path(gettempdir()) / "rbac-test.txt")


def temp_path(name: str) -> str:
    return str(Path(gettempdir()) / name)


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(scope="module")
async def client():
    """HTTP client for testing"""
    from httpx import ASGITransport

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.integration
@pytest.mark.requires_db
class TestRBACIntegration:
    """End-to-end RBAC integration tests"""

    @pytest.mark.asyncio
    async def test_guest_denied_execute_python(self, client):
        """Guest user should be denied execute_python access"""
        # Skip if RBAC disabled
        if not SecuritySettings.is_rbac_enabled():
            pytest.skip("RBAC disabled")

        response = await client.post(
            "/tools/execute_python/call",
            headers={"X-User-ID": "guest_user"},
            json={"arguments": {"code": "print(2+2)", "timeout": 30}},
        )

        # Should return 403 Forbidden
        assert (
            response.status_code == 403
        ), f"Expected 403, got {response.status_code}: {response.text}"

        data = response.json()
        assert "error" in data
        assert data["error"] == "Permission denied"
        assert data["user_id"] == "guest_user"
        assert data["tool_name"] == "execute_python"

        # Verify audit log entry
        db = get_security_database()
        logs = await db.get_audit_logs(user_id="guest_user", tool_name="execute_python", limit=1)

        assert len(logs) > 0, "Audit log should be created"
        log = logs[0]
        assert log["status"] == "denied"
        assert log["user_id"] == "guest_user"
        assert log["tool_name"] == "execute_python"

    @pytest.mark.asyncio
    async def test_developer_allowed_execute_python(self, client):
        """Developer user should be allowed execute_python access"""
        # Skip if RBAC disabled
        if not SecuritySettings.is_rbac_enabled():
            pytest.skip("RBAC disabled")

        response = await client.post(
            "/tools/execute_python/call",
            headers={"X-User-ID": "dev_user"},
            json={"arguments": {"code": "print(2+2)", "timeout": 30}},
        )

        # Should return 200 OK (or error from actual execution)
        # The important thing is NOT 403
        assert response.status_code != 403, f"Developer should not be denied: {response.text}"

        # Verify audit log entry
        db = get_security_database()
        logs = await db.get_audit_logs(user_id="dev_user", tool_name="execute_python", limit=1)

        assert len(logs) > 0, "Audit log should be created"
        log = logs[0]
        assert log["status"] == "success", f"Expected success, got {log['status']}"
        assert log["user_id"] == "dev_user"
        assert log["tool_name"] == "execute_python"
        assert log["execution_time_ms"] is not None

    @pytest.mark.asyncio
    async def test_guest_allowed_read_file(self, client):
        """Guest user should be allowed read_file access"""
        # Skip if RBAC disabled
        if not SecuritySettings.is_rbac_enabled():
            pytest.skip("RBAC disabled")

        response = await client.post(
            "/tools/read_file/call",
            headers={"X-User-ID": "guest_user"},
            json={"arguments": {"path": TEST_FILE_PATH}},
        )

        # Should NOT return 403 (guest has read_file permission)
        assert response.status_code != 403, "Guest should be allowed to read files"

    @pytest.mark.asyncio
    async def test_admin_allowed_git_commit(self, client):
        """Admin user should be allowed git_commit access"""
        # Skip if RBAC disabled
        if not SecuritySettings.is_rbac_enabled():
            pytest.skip("RBAC disabled")

        response = await client.post(
            "/tools/git_commit/call",
            headers={"X-User-ID": "admin_user"},
            json={"arguments": {"message": "test commit"}},
        )

        # Should NOT return 403 (admin has git_commit permission)
        assert response.status_code != 403, "Admin should be allowed to commit"

    @pytest.mark.asyncio
    async def test_developer_denied_git_commit(self, client):
        """Developer user should be denied git_commit access"""
        # Skip if RBAC disabled
        if not SecuritySettings.is_rbac_enabled():
            pytest.skip("RBAC disabled")

        response = await client.post(
            "/tools/git_commit/call",
            headers={"X-User-ID": "dev_user"},
            json={"arguments": {"message": "test commit"}},
        )

        # Should return 403 Forbidden (developer doesn't have git_commit)
        assert (
            response.status_code == 403
        ), f"Developer should be denied git_commit: {response.text}"

        data = response.json()
        assert data["error"] == "Permission denied"

    @pytest.mark.asyncio
    async def test_unknown_user_denied(self, client):
        """Unknown user should be denied all access"""
        # Skip if RBAC disabled
        if not SecuritySettings.is_rbac_enabled():
            pytest.skip("RBAC disabled")

        response = await client.post(
            "/tools/read_file/call",
            headers={"X-User-ID": "unknown_user_123"},
            json={"arguments": {"path": TEST_FILE_PATH}},
        )

        # Should return 403 Forbidden
        assert response.status_code == 403, "Unknown user should be denied"

    @pytest.mark.asyncio
    async def test_default_user_behavior(self, client):
        """Test default user when no X-User-ID header"""
        # Skip if RBAC disabled
        if not SecuritySettings.is_rbac_enabled():
            pytest.skip("RBAC disabled")

        response = await client.post(
            "/tools/read_file/call",
            # No X-User-ID header - should default to "default"
            json={"arguments": {"path": TEST_FILE_PATH}},
        )

        # Behavior depends on whether "default" user exists
        # If not exists, should be denied
        if response.status_code == 403:
            data = response.json()
            assert data["user_id"] == "default"

    @pytest.mark.asyncio
    async def test_audit_log_accumulation(self, client):
        """Test that audit logs accumulate correctly"""
        # Skip if RBAC disabled
        if not SecuritySettings.is_rbac_enabled():
            pytest.skip("RBAC disabled")

        db = get_security_database()
        import time

        # Record start time to filter only new logs
        start_time = time.time()

        # Make multiple requests
        for i in range(5):
            await client.post(
                "/tools/read_file/call",
                headers={"X-User-ID": "guest_user"},
                json={"arguments": {"path": temp_path(f"rbac-test{i}.txt")}},
            )

        # Wait for async logging
        await asyncio.sleep(0.5)

        # Count logs created after start_time
        all_logs = await db.get_audit_logs(limit=1000)
        new_logs = [log for log in all_logs if log.get("timestamp", "") >= str(start_time)]
        new_count = len(new_logs)

        assert new_count >= 5, f"Expected at least 5 new audit logs, got {new_count}"


@pytest.mark.integration
class TestAuditLoggerLifecycle:
    """Test audit logger start/stop lifecycle"""

    @pytest.mark.asyncio
    async def test_audit_logger_queue_overflow(self):
        """Test queue overflow handling"""
        from audit_logger import AuditLogger

        # Create logger with small queue
        logger = AuditLogger(queue_size=3)
        logger.start_async_writer()

        # Fill queue beyond capacity
        for i in range(10):
            await logger.log_tool_call(
                user_id=f"user_{i}",
                tool_name="test_tool",
                action="test",
                status="success",
            )

        # Queue should handle overflow gracefully
        stats = logger.get_queue_stats()
        assert stats["queue_size"] <= 3, "Queue should not exceed max size"

        await logger.stop_async_writer()

    @pytest.mark.asyncio
    async def test_audit_logger_start_stop(self):
        """Test audit logger lifecycle"""
        from audit_logger import AuditLogger

        logger = AuditLogger()

        # Start
        logger.start_async_writer()
        assert logger._running
        assert logger._writer_task is not None

        # Log some entries
        await logger.log_success("user1", "tool1", 100)
        await logger.log_denied("user2", "tool2", "Permission denied")
        await logger.log_error("user3", "tool3", "Error occurred")

        # Wait for processing
        await asyncio.sleep(0.2)

        # Stop
        await logger.stop_async_writer()
        assert not logger._running
        assert logger._writer_task is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
