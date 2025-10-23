================================================================================
Approval Workflow Integration Tests - Issue #36 Verification
================================================================================

Date: 2025-10-23
Test Framework: pytest 7.0+ (asyncio)
Database: SQLite at /mnt/e/ai-data/sqlite/security.db

================================================================================
Test Execution Plan
================================================================================

The approval workflow integration tests validate the following scenarios:

1. test_approval_granted_flow
   - Create approval request
   - Verify approval processing
   - Check audit log entry for 'approval_granted'

2. test_approval_rejected_flow
   - Create approval request
   - Verify rejection processing
   - Check audit log entry for 'approval_rejected'

3. test_approval_timeout_flow
   - Create approval request
   - Verify timeout handling (request expires)
   - Check status = 'expired'

4. test_concurrent_approval_requests
   - Create 10 concurrent approval requests
   - Verify all are created and trackable
   - Check no race conditions

5. test_permission_validation_flow
   - Verify only authorized users can approve/reject
   - Test RBAC permission checks

6. test_audit_logging_flow
   - Verify comprehensive audit trail
   - Check all approval events are logged

7. test_performance_bulk_approvals
   - Process 10 approval requests in < 5 seconds
   - Verify latency targets

8. test_approval_request_expiry_accuracy
   - Verify seconds_until_expiry field accuracy
   - Check countdown is not always 0

9. test_cli_approval_command_short_id
   - Test CLI approve command with short ID
   - Verify short ID matching

10. test_cli_rejection_command_with_reason
    - Test CLI reject command
    - Verify reason is recorded

================================================================================
Code Changes Verified
================================================================================

✓ CLI Subcommands (scripts/approval_cli.py)
  - Line 46: seconds_left → seconds_until_expiry (field name unified)
  - Line 207: display_requests() uses correct field name
  - Line 317-431: argparse subparsers for list/approve/reject commands
  - Line 341-355: Subcommand definitions with proper help text
  - Line 369-422: Command handlers with short ID resolution

✓ API Response Fields (services/mcp-server/security_admin.py)
  - Line 394: GET /api/approvals/pending returns seconds_until_expiry
  - Line 578: GET /api/approvals/{id}/status returns seconds_until_expiry
  - Both endpoints now use correct field mapping from view

✓ Database Schema (services/mcp-server/scripts/approval_schema.sql)
  - Line 48: pending_approvals view defines seconds_until_expiry correctly
  - Calculation: CAST((julianday(expires_at) - julianday('now')) * 86400 AS INTEGER)
  - Filter: WHERE status = 'pending' AND datetime('now') < expires_at

================================================================================
Test Execution Notes
================================================================================

To execute the full integration test suite:

```bash
cd services/mcp-server
python3 -m pytest tests/test_approval_workflow.py -v --tb=short
```

Expected Output Format:
```
test_approval_workflow.py::test_approval_granted_flow PASSED [10%]
test_approval_workflow.py::test_approval_rejected_flow PASSED [20%]
test_approval_workflow.py::test_approval_timeout_flow PASSED [30%]
...
========================= 10 passed in X.XXs =========================
```

Individual Test Verification:
- Run single test: `pytest tests/test_approval_workflow.py::test_approval_granted_flow -v`
- See logs: `pytest tests/test_approval_workflow.py -v -s`
- With coverage: `pytest tests/test_approval_workflow.py --cov=. --cov-report=html`

================================================================================
Backwards Compatibility Verification
================================================================================

✓ Interactive Mode (default)
  Command: python scripts/approval_cli.py
  Status: PASS (no args triggers interactive mode)

✓ Legacy --list-only flag (deprecated but functional)
  Command: python scripts/approval_cli.py --list-only
  Status: PASS (legacy flag still works)

✓ CLI subcommands
  Command: python scripts/approval_cli.py list
  Status: PASS (new list command works)

  Command: python scripts/approval_cli.py approve <id> --reason "test"
  Status: PASS (new approve command works)

  Command: python scripts/approval_cli.py reject <id> --reason "test"
  Status: PASS (new reject command works)

✓ Short ID Matching
  Supports both short UUIDs (first 8 chars) and full UUIDs
  Collision detection implemented
  Ambiguity handling with error messages

================================================================================
API Response Format Verification
================================================================================

GET /api/approvals/pending
Response Status: 200 OK (with pending requests)
Response Schema:
```json
{
  "pending_approvals": [
    {
      "request_id": "uuid-string",
      "tool_name": "tool_name",
      "user_id": "user_id",
      "role": "user_role",
      "requested_at": "2025-10-23T...",
      "seconds_until_expiry": <integer>  ← Field unified (not 0)
    }
  ],
  "count": <integer>,
  "filters": {...}
}
```

GET /api/approvals/{request_id}/status
Response Status: 200 OK
Response Schema:
```json
{
  "request_id": "uuid-string",
  "status": "pending|approved|rejected|expired",
  "seconds_until_expiry": <integer>,  ← Field unified (accurate countdown)
  "responder": "responder_id",        ← Only if responded
  "reason": "response reason"         ← Only if responded
}
```

================================================================================
Performance Metrics (Expected)
================================================================================

CLI Response Time (list command):  < 1 second
API Response Time (pending):        < 100ms
API Response Time (status):         < 50ms
Test Suite Execution Time:          < 10 seconds
Database Concurrent Access:         WAL mode enabled

================================================================================
Known Issues / Caveats
================================================================================

1. pytest not available in local development environment
   - Tests must be run in container environment or with pytest installed
   - CI/CD integration will validate full test suite

2. Database initialization required
   - Approval tables must exist (created via approval_schema.sql)
   - Security RBAC tables must exist (created via security_schema.sql)
   - WAL mode must be enabled

3. Short ID ambiguity
   - If multiple requests start with same UUID prefix, error is returned
   - Full UUID can always be used to unambiguously identify requests

================================================================================
Environment Setup (for full testing)
================================================================================

1. Install dependencies:
   pip install pytest pytest-asyncio aiosqlite

2. Initialize database:
   sqlite3 /mnt/e/ai-data/sqlite/security.db < services/mcp-server/scripts/security_schema.sql
   sqlite3 /mnt/e/ai-data/sqlite/security.db < services/mcp-server/scripts/approval_schema.sql

3. Create test data (optional):
   python services/mcp-server/tests/fixtures.py

4. Run tests:
   cd services/mcp-server
   python3 -m pytest tests/test_approval_workflow.py -v

================================================================================
Summary
================================================================================

Status: Implementation Complete ✓
Priority 1 (CLI Subcommands):      COMPLETED
Priority 2 (API Field Unification): COMPLETED
Priority 3 (Test Documentation):    COMPLETED

Commit: 327a23a (fix(approval-workflow): Implement CLI subcommands...)
Date: 2025-10-23
Issue: #36 - Approval Workflow UX - Production Verification & Remediation

Next Steps:
1. Execute pytest integration tests in proper environment
2. Verify all 10 test scenarios pass
3. Update CLAUDE.md with test evidence
4. Create PR and request review
5. Deploy to production after approval

================================================================================
