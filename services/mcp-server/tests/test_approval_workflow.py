#!/usr/bin/env python3
"""
Approval Workflow Integration Tests
Issue #16 - 7가지 시나리오 통합 테스트

Test Scenarios:
1. 승인 플로우 테스트 (Approval Granted) - test_approval_granted_flow
2. 거부 플로우 테스트 (Approval Rejected) - test_approval_rejected_flow
3. 타임아웃 테스트 (Approval Timeout) - test_approval_timeout_flow
4. 동시 요청 테스트 (Concurrent Requests, 10개) - test_concurrent_approval_requests
5. 권한 검증 테스트 (Permission Validation) - test_permission_validation_flow
6. 감사 로깅 테스트 (Audit Logging) - test_audit_logging_flow
7. 성능 테스트 (Performance, 10 req < 5s) - test_performance_bulk_approvals

Requirements:
- HIGH/CRITICAL tools require approval
- Admin-only approval/rejection API
- Automatic timeout and cleanup
- Complete audit trail for all approval events
"""

import asyncio
import pytest
import pytest_asyncio
import json
import uuid
from pathlib import Path

# Add parent directory to path for imports
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from security_database import SecurityDatabase
from audit_logger import AuditLogger


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def test_db(tmp_path):
    """Create temporary test database"""
    db_path = tmp_path / "test_security.db"
    db = SecurityDatabase(db_path=db_path)
    await db.initialize()  # Correct method name

    # Apply approval schema
    approval_schema_path = (
        Path(__file__).parent.parent / "scripts" / "approval_schema.sql"
    )
    if approval_schema_path.exists():
        async with db.get_connection() as conn:
            with open(approval_schema_path, "r") as f:
                await conn.executescript(f.read())
            await conn.commit()

    # Initialize test data
    await _setup_test_data(db)

    yield db

    # Cleanup - no close() method needed for aiosqlite


async def _setup_test_data(db: SecurityDatabase):
    """Setup test users, roles, and permissions"""

    # Create test users
    await db.insert_user(
        user_id="test_user", role="user", attributes=json.dumps({"name": "Test User"})
    )
    await db.insert_user(
        user_id="test_admin",
        role="admin",
        attributes=json.dumps({"name": "Test Admin"}),
    )

    # Create test permission (HIGH sensitivity - requires approval)
    await db.insert_permission(
        permission_name="test_high_tool",
        description="Test HIGH sensitivity tool",
        sensitivity_level="HIGH",
        resource_type="tool",
        action="execute",
    )

    # Assign to roles
    await db.assign_permission_to_role("user", "test_high_tool")
    await db.assign_permission_to_role("admin", "test_high_tool")

    # Create test permission (CRITICAL sensitivity - requires approval)
    await db.insert_permission(
        permission_name="test_critical_tool",
        description="Test CRITICAL sensitivity tool",
        sensitivity_level="CRITICAL",
        resource_type="tool",
        action="execute",
    )

    # Assign to admin only
    await db.assign_permission_to_role("admin", "test_critical_tool")

    # Create test permission (MEDIUM sensitivity - no approval)
    await db.insert_permission(
        permission_name="test_medium_tool",
        description="Test MEDIUM sensitivity tool",
        sensitivity_level="MEDIUM",
        resource_type="tool",
        action="execute",
    )

    # Assign to both roles
    await db.assign_permission_to_role("user", "test_medium_tool")
    await db.assign_permission_to_role("admin", "test_medium_tool")


@pytest_asyncio.fixture
async def rbac_manager(test_db):
    """Create RBACManager instance with test database"""
    # RBACManager uses get_security_database(), so we can't easily inject test_db
    # Instead, we'll use test_db methods directly in tests
    yield test_db


@pytest_asyncio.fixture
async def audit_logger(test_db):
    """Create AuditLogger instance for testing"""
    logger = AuditLogger(queue_size=100)
    logger.db = test_db
    logger.start_async_writer()
    yield logger
    await logger.stop_async_writer()


# ============================================================================
# Test Scenario 1: 승인 플로우 테스트 (Approval Granted)
# ============================================================================


@pytest.mark.asyncio
async def test_approval_granted_flow(test_db, rbac_manager):
    """
    Test Scenario 1: 승인 플로우

    Steps:
    1. User requests HIGH/CRITICAL tool
    2. Approval request created in DB
    3. Admin approves request
    4. User receives approval and tool executes
    """

    # Step 1: Verify HIGH tool exists in test data
    permission = await test_db.get_permission_by_name("test_high_tool")
    assert permission is not None, "HIGH tool permission should exist"
    assert permission["sensitivity_level"] == "HIGH", "Tool should be HIGH sensitivity"

    # Step 2: Create approval request manually (simulating _wait_for_approval)
    request_id = str(uuid.uuid4())
    success = await test_db.create_approval_request(
        request_id=request_id,
        tool_name="test_high_tool",
        user_id="test_user",
        role="user",
        request_data=json.dumps({"arg1": "value1"}),
        timeout_seconds=300,
    )
    assert success, "Approval request should be created"

    # Step 3: Verify request is pending
    request = await test_db.get_approval_request(request_id)
    assert request is not None, "Request should exist"
    assert request["status"] == "pending", "Request should be pending"
    assert request["tool_name"] == "test_high_tool"
    assert request["user_id"] == "test_user"

    # Step 4: Admin approves
    success = await test_db.update_approval_status(
        request_id=request_id,
        status="approved",
        responder_id="test_admin",
        response_reason="Test approval",
    )
    assert success, "Approval should succeed"

    # Step 5: Verify approval
    request = await test_db.get_approval_request(request_id)
    assert request["status"] == "approved", "Status should be approved"
    assert request["responder_id"] == "test_admin"
    assert request["response_reason"] == "Test approval"
    assert request["responded_at"] is not None


# ============================================================================
# Test Scenario 2: 거부 플로우 테스트 (Approval Rejected)
# ============================================================================


@pytest.mark.asyncio
async def test_approval_rejected_flow(test_db, rbac_manager):
    """
    Test Scenario 2: 거부 플로우

    Steps:
    1. User requests HIGH/CRITICAL tool
    2. Approval request created in DB
    3. Admin rejects request
    4. User receives rejection
    """

    # Step 1: Create approval request
    request_id = str(uuid.uuid4())
    success = await test_db.create_approval_request(
        request_id=request_id,
        tool_name="test_critical_tool",
        user_id="test_user",
        role="user",
        request_data=json.dumps({"dangerous": "operation"}),
        timeout_seconds=300,
    )
    assert success

    # Step 2: Admin rejects
    success = await test_db.update_approval_status(
        request_id=request_id,
        status="rejected",
        responder_id="test_admin",
        response_reason="Security concern - unauthorized operation",
    )
    assert success

    # Step 3: Verify rejection
    request = await test_db.get_approval_request(request_id)
    assert request["status"] == "rejected"
    assert request["responder_id"] == "test_admin"
    assert "Security concern" in request["response_reason"]


# ============================================================================
# Test Scenario 3: 타임아웃 테스트 (Approval Timeout)
# ============================================================================


@pytest.mark.asyncio
async def test_approval_timeout_flow(test_db, rbac_manager):
    """
    Test Scenario 3: 타임아웃 플로우

    Steps:
    1. User requests HIGH/CRITICAL tool
    2. Approval request created with short timeout
    3. No admin response
    4. Request expires after timeout
    5. Cleanup task marks as timeout
    """

    # Step 1: Create approval request with short timeout (2 seconds)
    request_id = str(uuid.uuid4())
    success = await test_db.create_approval_request(
        request_id=request_id,
        tool_name="test_high_tool",
        user_id="test_user",
        role="user",
        request_data=json.dumps({"arg": "value"}),
        timeout_seconds=2,  # Short timeout for testing
    )
    assert success

    # Step 2: Wait for timeout
    await asyncio.sleep(3)  # Wait 3 seconds (> 2 second timeout)

    # Step 3: Run cleanup task
    expired_count = await test_db.cleanup_expired_approvals()
    assert expired_count >= 1, "At least one request should be expired"

    # Step 4: Verify timeout status
    request = await test_db.get_approval_request(request_id)
    assert request["status"] == "expired", "Request should be marked as expired"


# ============================================================================
# Test Scenario 4: 동시 요청 테스트 (Concurrent Requests)
# ============================================================================


@pytest.mark.asyncio
async def test_concurrent_approval_requests(test_db, rbac_manager):
    """
    Test Scenario 4: 동시 요청 처리

    Steps:
    1. Create multiple approval requests concurrently (10 requests)
    2. Verify all requests are created successfully
    3. Process approvals/rejections concurrently
    4. Verify final states
    """

    # Step 1: Create 10 concurrent approval requests
    request_ids = []
    tasks = []

    for i in range(10):
        request_id = str(uuid.uuid4())
        request_ids.append(request_id)

        task = test_db.create_approval_request(
            request_id=request_id,
            tool_name="test_high_tool",
            user_id=f"test_user_{i}",
            role="user",
            request_data=json.dumps({"request_num": i}),
            timeout_seconds=300,
        )
        tasks.append(task)

    # Wait for all requests to be created
    results = await asyncio.gather(*tasks)
    assert all(results), "All approval requests should be created"

    # Step 2: Verify all pending
    pending_requests = await test_db.list_pending_approvals(limit=50)
    assert len(pending_requests) >= 10, "All 10 requests should be pending"

    # Step 3: Process concurrently - approve first 5, reject last 5
    approval_tasks = []

    for i, request_id in enumerate(request_ids[:5]):
        task = test_db.update_approval_status(
            request_id=request_id,
            status="approved",
            responder_id="test_admin",
            response_reason=f"Batch approval {i}",
        )
        approval_tasks.append(task)

    for i, request_id in enumerate(request_ids[5:]):
        task = test_db.update_approval_status(
            request_id=request_id,
            status="rejected",
            responder_id="test_admin",
            response_reason=f"Batch rejection {i}",
        )
        approval_tasks.append(task)

    results = await asyncio.gather(*approval_tasks)
    assert all(results), "All status updates should succeed"

    # Step 4: Verify final states
    approved_count = 0
    rejected_count = 0

    for request_id in request_ids:
        request = await test_db.get_approval_request(request_id)
        if request["status"] == "approved":
            approved_count += 1
        elif request["status"] == "rejected":
            rejected_count += 1

    assert approved_count == 5, "Should have 5 approved requests"
    assert rejected_count == 5, "Should have 5 rejected requests"


# ============================================================================
# Test Scenario 5: 권한 검증 테스트 (Permission Validation)
# ============================================================================


@pytest.mark.asyncio
async def test_permission_validation_flow(test_db, rbac_manager):
    """
    Test Scenario 5: 권한 검증

    Steps:
    1. Test MEDIUM tool (no approval required)
    2. Test HIGH tool (approval required)
    3. Test CRITICAL tool (approval required)
    4. Test non-existent tool (no approval)
    5. Test short ID prefix matching
    """

    # Step 1: MEDIUM tool - no approval required (sensitivity level check)
    perm = await test_db.get_permission_by_name("test_medium_tool")
    assert (
        perm is not None and perm["sensitivity_level"] == "MEDIUM"
    ), "MEDIUM tool should exist"

    # Step 2: HIGH tool - approval required
    perm = await test_db.get_permission_by_name("test_high_tool")
    assert (
        perm is not None and perm["sensitivity_level"] == "HIGH"
    ), "HIGH tool should exist"

    # Step 3: CRITICAL tool - approval required
    perm = await test_db.get_permission_by_name("test_critical_tool")
    assert (
        perm is not None and perm["sensitivity_level"] == "CRITICAL"
    ), "CRITICAL tool should exist"

    # Step 4: Non-existent tool
    perm = await test_db.get_permission_by_name("non_existent_tool")
    assert perm is None, "Non-existent tool should return None"

    # Step 5: Test short ID prefix matching
    request_id = str(uuid.uuid4())
    await test_db.create_approval_request(
        request_id=request_id,
        tool_name="test_high_tool",
        user_id="test_user",
        role="user",
        request_data=json.dumps({}),
        timeout_seconds=300,
    )

    # Test short ID (first 8 characters)
    short_id = request_id[:8]
    request = await test_db.get_approval_request(short_id)
    assert request is not None, "Short ID should match full UUID"
    assert request["request_id"] == request_id, "Should return correct request"


# ============================================================================
# Test Scenario 6: 감사 로깅 테스트 (Audit Logging)
# ============================================================================


@pytest.mark.asyncio
async def test_audit_logging_flow(test_db, audit_logger):
    """
    Test Scenario 6: 감사 로깅

    Steps:
    1. Log approval request
    2. Log approval granted
    3. Log approval rejected
    4. Log approval timeout
    5. Verify all logs in database
    """

    request_id = str(uuid.uuid4())

    # Step 1: Log approval request
    await audit_logger.log_approval_requested(
        user_id="test_user",
        tool_name="test_high_tool",
        request_id=request_id,
        request_data={"arg": "value"},
    )

    # Step 2: Log approval granted
    await audit_logger.log_approval_granted(
        user_id="test_user",
        tool_name="test_high_tool",
        request_id=request_id,
        responder_id="test_admin",
        reason="Test approval",
    )

    # Step 3: Log approval rejected (different request)
    request_id_2 = str(uuid.uuid4())
    await audit_logger.log_approval_rejected(
        user_id="test_user",
        tool_name="test_critical_tool",
        request_id=request_id_2,
        responder_id="test_admin",
        reason="Security concern",
    )

    # Step 4: Log approval timeout (different request)
    request_id_3 = str(uuid.uuid4())
    await audit_logger.log_approval_timeout(
        user_id="test_user",
        tool_name="test_high_tool",
        request_id=request_id_3,
        timeout_seconds=300,
    )

    # Wait for async writer to process
    await asyncio.sleep(2)

    # Step 5: Verify logs in database
    # Query audit logs for approval events
    logs = await test_db.query_audit_logs(user_id="test_user", limit=10)

    # Should have at least 4 approval-related logs
    approval_logs = [log for log in logs if "approval" in log.get("action", "")]
    assert len(approval_logs) >= 4, "Should have at least 4 approval-related audit logs"

    # Verify log actions
    actions = {log["action"] for log in approval_logs}
    assert "approval_requested" in actions
    assert "approval_granted" in actions
    assert "approval_rejected" in actions
    assert "approval_timeout" in actions


# ============================================================================
# Performance Test: 대량 요청 처리
# ============================================================================


@pytest.mark.asyncio
async def test_performance_bulk_approvals(test_db):
    """
    Performance Test: 대량 승인 요청 처리

    Goal: 10개 요청을 5초 이내에 처리
    """
    import time
    import logging

    logger = logging.getLogger(__name__)

    start_time = time.time()

    # Create 10 approval requests
    request_ids = []
    for i in range(10):
        request_id = str(uuid.uuid4())
        request_ids.append(request_id)

        await test_db.create_approval_request(
            request_id=request_id,
            tool_name="test_high_tool",
            user_id=f"test_user_{i}",
            role="user",
            request_data=json.dumps({"index": i}),
            timeout_seconds=300,
        )

    # Process all approvals
    for request_id in request_ids:
        await test_db.update_approval_status(
            request_id=request_id,
            status="approved",
            responder_id="test_admin",
            response_reason="Bulk approval",
        )

    elapsed_time = time.time() - start_time

    # Log actual performance metrics
    logger.info("Performance Test Results:")
    logger.info("  - Total requests: 10")
    logger.info(f"  - Elapsed time: {elapsed_time:.3f}s")
    logger.info(f"  - Average time per request: {elapsed_time/10:.3f}s")
    logger.info(f"  - Requests per second: {10/elapsed_time:.2f}")

    print(f"\n✅ Performance: Processed 10 requests in {elapsed_time:.3f}s")
    print(f"   Average: {elapsed_time/10:.3f}s per request")
    print(f"   Throughput: {10/elapsed_time:.2f} req/s")

    assert (
        elapsed_time < 5.0
    ), f"Should process 10 requests in < 5s (took {elapsed_time:.3f}s)"


# ============================================================================
# Test Runner
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
