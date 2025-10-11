# SECURITY.md

**Local AI Suite - Security Guide**

Last Updated: 2025-10-10
Version: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [RBAC System](#rbac-system)
3. [Approval Workflow](#approval-workflow)
4. [Deployment](#deployment)
5. [Audit Logging](#audit-logging)
6. [Testing & Performance](#testing--performance)
7. [Troubleshooting](#troubleshooting)

---

## Overview

Local AI Suite implements a multi-layered security architecture to protect against unauthorized access and malicious code execution:

### Security Layers

1. **AST-based Code Validation** (`security.py`)
   - Blocks dangerous modules: subprocess, socket, importlib
   - Prevents dynamic imports: `__import__`, `import_module`
   - Rejects unsafe functions: `eval`, `exec`, `compile`

2. **Docker Sandbox** (`sandbox.py`)
   - Container isolation with read-only filesystem
   - Resource limits: 512MB RAM, 30s CPU, 10 processes
   - Network isolation and capability removal
   - Automatic cleanup and session management

3. **Rate Limiting** (`rate_limiter.py`)
   - Tool-based sensitivity levels (LOW/MEDIUM/HIGH/CRITICAL)
   - Request rate and concurrency limits
   - Development/Production mode separation

4. **RBAC (Role-Based Access Control)** (`rbac_manager.py`, `rbac_middleware.py`)
   - 3 predefined roles: guest, developer, admin
   - 21 fine-grained permissions for 18 MCP tools
   - TTL-based permission caching (5 minutes)
   - Automatic FastAPI middleware integration

5. **Approval Workflow** (`security_database.py`)
   - HIGH/CRITICAL tools require admin approval
   - 5-minute timeout for pending requests
   - CLI-based approval/rejection interface
   - Complete audit trail

6. **Audit Logging** (`audit_logger.py`)
   - SQLite-based structured logging
   - Asynchronous queue processing (<5ms overhead)
   - Records all tool calls, denials, and errors

---

## RBAC System

### Architecture

**Database**: SQLite 3.x with WAL mode
**Location**: `/mnt/e/ai-data/sqlite/security.db`

**Schema**:
```
security_users (4 users)
├── user_id (PRIMARY KEY)
├── username
├── role_id (FOREIGN KEY → security_roles)
├── created_at
└── updated_at

security_roles (3 roles)
├── role_id (PRIMARY KEY)
├── role_name (UNIQUE)
├── description
└── is_system_role

security_permissions (21 permissions)
├── permission_id (PRIMARY KEY)
├── permission_name (UNIQUE)
├── resource_type (file, tool)
├── action (read, write, execute)
├── sensitivity_level (LOW, MEDIUM, HIGH, CRITICAL)
└── description

security_role_permissions (43 mappings)
├── role_id (FOREIGN KEY)
└── permission_id (FOREIGN KEY)

security_audit_logs
├── log_id (PRIMARY KEY)
├── user_id
├── tool_name
├── action
├── status (success, denied, error, pending_approval)
├── timestamp
├── execution_time_ms
└── details (JSON)

approval_requests
├── request_id (PRIMARY KEY, UUID)
├── tool_name
├── user_id (FOREIGN KEY → security_users)
├── role
├── request_data (JSON)
├── status (pending, approved, rejected, expired, timeout)
├── requested_at
├── responded_at
├── responder_id
├── response_reason
└── expires_at
```

### Roles & Permissions

#### Guest (7 permissions)
**Purpose**: Read-only access for observers

Permissions:
- `read_file`: View file contents
- `list_files`: Browse directories
- `rag_search`: Search documents
- `ai_chat`: AI chat interactions
- `git_status`: View repository status
- `git_log`: View commit history
- `git_diff`: View code changes

#### Developer (15 permissions)
**Purpose**: Code execution and development workflows

All Guest permissions, plus:
- `write_file`: Modify files
- `execute_python`: Run Python code (approval required)
- `execute_bash`: Run shell commands (approval required)
- `git_add`: Stage changes
- `web_screenshot`: Capture web pages
- `web_scrape`: Extract web content
- `web_analyze_ui`: Analyze UI elements
- `get_current_model`: View active AI model

#### Admin (21 permissions)
**Purpose**: Full system control

All Developer permissions, plus:
- `git_commit`: Create commits (approval required)
- `web_automate`: Web automation (approval required)
- `notion_create_page`: Create Notion pages
- `notion_search`: Search Notion workspace
- `web_to_notion`: Save web content to Notion
- `switch_model`: Change AI model

### RBAC Flow

```
┌──────────────┐
│ API Request  │
│ X-User-ID    │
└──────┬───────┘
       │
       ▼
┌──────────────────────┐
│ RBAC Middleware      │
│ 1. Extract user_id   │
│ 2. Identify tool     │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ RBAC Manager         │
│ 1. Check cache       │
│ 2. Query DB if miss  │
│ 3. Update cache      │
└──────┬───────────────┘
       │
       ├─► Permission Granted ─► Execute Tool ─► Audit Log (success)
       │
       └─► Permission Denied ──► HTTP 403 ──────► Audit Log (denied)
```

---

## Approval Workflow

### Configuration

**Environment Variables**:
```bash
APPROVAL_WORKFLOW_ENABLED=true  # Enable approval workflow
APPROVAL_TIMEOUT=300            # 5 minutes (seconds)
```

### Approval Required Tools

**HIGH Sensitivity** (require approval):
- `write_file`: File modifications
- `git_commit`: Repository commits
- `web_automate`: Web automation
- `switch_model`: Model switching

**CRITICAL Sensitivity** (require approval):
- `execute_python`: Python code execution
- `execute_bash`: Shell command execution

### Workflow States

```
Request Created (pending)
    │
    ├──► Admin Approves ──► approved ──► Tool Executes ──► success
    │
    ├──► Admin Rejects ───► rejected ──► HTTP 403
    │
    └──► Timeout (5min) ──► timeout ───► HTTP 408
```

### CLI Approval Commands

**List pending approvals**:
```bash
python scripts/approval_cli.py list

# Output:
# Request ID: a1b2c3d4-...
# Tool: execute_python
# User: dev_user (developer)
# Requested: 2025-10-10 14:23:15
# Expires in: 243 seconds
```

**Approve request**:
```bash
python scripts/approval_cli.py approve <request_id> \
  --reason "Authorized by security team"

# Output:
# ✓ Approval granted for request a1b2c3d4-...
```

**Reject request**:
```bash
python scripts/approval_cli.py reject <request_id> \
  --reason "Policy violation: unapproved code execution"

# Output:
# ✓ Request rejected: a1b2c3d4-...
```

**Check status**:
```bash
python scripts/approval_cli.py status <request_id>

# Output:
# Request: a1b2c3d4-...
# Status: approved
# Responded by: admin_user
# Reason: Authorized by security team
```

---

## Deployment

### Database Initialization

**First-time setup**:
```bash
cd services/mcp-server

# 1. Initialize database schema
python scripts/seed_security_data.py --reset

# 2. Apply approval workflow schema
python3 -c "
import sqlite3
with open('scripts/approval_schema.sql', 'r') as f:
    schema = f.read()
conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
conn.executescript(schema)
conn.commit()
"

# 3. Verify database
python3 -c "
import sqlite3
conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM security_users')
print('Users:', cursor.fetchone()[0])
cursor.execute('SELECT COUNT(*) FROM security_roles')
print('Roles:', cursor.fetchone()[0])
cursor.execute('SELECT COUNT(*) FROM security_permissions')
print('Permissions:', cursor.fetchone()[0])
"
```

### Environment Variables

**Required**:
```bash
# RBAC System
RBAC_ENABLED=true
SECURITY_DB_PATH=/mnt/e/ai-data/sqlite/security.db
SECURITY_QUEUE_SIZE=1000

# Approval Workflow
APPROVAL_WORKFLOW_ENABLED=true
APPROVAL_TIMEOUT=300

# Audit Logging
AUDIT_LOG_PATH=/mnt/e/ai-data/logs/audit.log
```

**Optional**:
```bash
# Cache Configuration
RBAC_CACHE_TTL=300              # 5 minutes
RBAC_CACHE_MAX_SIZE=1000

# Performance Tuning
QDRANT_TIMEOUT=30
EMBEDDING_TIMEOUT=30
LLM_REQUEST_TIMEOUT=60
```

### Health Checks

**MCP Server**:
```bash
curl http://localhost:8020/health

# Expected response:
# {"status": "healthy", "rbac_enabled": true, "approval_enabled": true}
```

**Database**:
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
print('WAL mode:', conn.execute('PRAGMA journal_mode').fetchone()[0])
print('Integrity:', conn.execute('PRAGMA integrity_check').fetchone()[0])
"

# Expected:
# WAL mode: wal
# Integrity: ok
```

---

## Audit Logging

### Log Format

**Table**: `security_audit_logs`

**Fields**:
- `log_id`: Auto-increment primary key
- `user_id`: User identifier
- `tool_name`: MCP tool name
- `action`: Action type (call, deny, approve, reject)
- `status`: Result (success, denied, error, pending_approval, approved, rejected, timeout)
- `timestamp`: ISO 8601 timestamp
- `execution_time_ms`: Tool execution time (milliseconds)
- `details`: JSON-encoded additional data

### Query Examples

**Recent denials**:
```sql
SELECT
    timestamp,
    user_id,
    tool_name,
    details
FROM security_audit_logs
WHERE status = 'denied'
ORDER BY timestamp DESC
LIMIT 10;
```

**User activity**:
```sql
SELECT
    tool_name,
    COUNT(*) as call_count,
    AVG(execution_time_ms) as avg_time
FROM security_audit_logs
WHERE user_id = 'dev_user'
  AND status = 'success'
  AND timestamp > datetime('now', '-7 days')
GROUP BY tool_name
ORDER BY call_count DESC;
```

**Approval statistics**:
```sql
SELECT
    tool_name,
    status,
    COUNT(*) as count
FROM security_audit_logs
WHERE action IN ('approve', 'reject')
  AND timestamp > datetime('now', '-30 days')
GROUP BY tool_name, status
ORDER BY tool_name, status;
```

**Performance analysis**:
```sql
SELECT
    tool_name,
    MIN(execution_time_ms) as min_ms,
    AVG(execution_time_ms) as avg_ms,
    MAX(execution_time_ms) as max_ms,
    COUNT(*) as calls
FROM security_audit_logs
WHERE status = 'success'
  AND execution_time_ms IS NOT NULL
  AND timestamp > datetime('now', '-1 day')
GROUP BY tool_name
ORDER BY avg_ms DESC;
```

---

## Testing & Performance

### Test Results (Phase 2)

**Integration Tests**: `services/mcp-server/tests/integration/test_rbac_integration.py`

Test Scenarios (13 total):
1. ✅ Guest denied CRITICAL tool (execute_python)
2. ✅ Developer allowed MEDIUM tool (execute_python)
3. ✅ Guest allowed LOW tool (read_file)
4. ✅ Developer denied HIGH tool (git_commit)
5. ✅ Admin allowed all tools
6. ✅ Approval granted flow
7. ✅ Approval rejected flow
8. ✅ Approval timeout flow
9. ✅ Concurrent approval requests (10 simultaneous)
10. ✅ Permission validation before approval
11. ✅ All events logged
12. ✅ Audit log query performance
13. ✅ Bulk approval processing

**Execution**:
```bash
docker exec -it mcp-server pytest tests/integration/test_rbac_integration.py -v
docker exec -it mcp-server pytest tests/test_approval_workflow.py -v
```

### Performance Benchmark (Phase 3)

**Benchmark Script**: `services/mcp-server/tests/benchmark_rbac.py`

**Performance Goals**:
- RPS ≥ 100 requests/second
- 95th percentile latency < 100ms
- Error rate < 1%

**Execution**:
```bash
docker exec -it mcp-server python3 tests/benchmark_rbac.py --duration 60 --rps 100
```

**Expected Results**:
```
============================================================
Benchmark Results
============================================================
Duration:                60.05 sec
Total Requests:           6000
Successful:               5950
Errors:                     50
Error Rate:               0.83 %
RPS:                     99.92
============================================================
Latency (ms):
  Min:                    5.12
  Average:               47.53
  Median:                46.28
  95th percentile:       89.45
  99th percentile:      125.67
  Max:                  234.56
============================================================
✓ ALL GOALS MET
============================================================
```

---

## Troubleshooting

### Common Issues

#### 1. Permission Denied for Valid User

**Symptoms**:
- User receives 403 Forbidden unexpectedly
- Audit log shows `status='denied'`

**Diagnosis**:
```bash
# Check user role
python3 -c "
import sqlite3
conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
cursor = conn.cursor()
cursor.execute('''
    SELECT u.user_id, u.username, r.role_name
    FROM security_users u
    JOIN security_roles r ON u.role_id = r.role_id
    WHERE u.user_id = 'dev_user'
''')
print(cursor.fetchone())
"

# Check permissions
python3 -c "
import sqlite3
conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
cursor = conn.cursor()
cursor.execute('''
    SELECT p.permission_name
    FROM security_users u
    JOIN security_role_permissions rp ON u.role_id = rp.role_id
    JOIN security_permissions p ON rp.permission_id = p.permission_id
    WHERE u.user_id = 'dev_user'
    ORDER BY p.permission_name
''')
for row in cursor.fetchall():
    print(row[0])
"
```

**Solution**:
- Verify user exists and has correct role
- Check if permission is assigned to role
- Clear cache: Restart MCP server

#### 2. Database is Locked

**Symptoms**:
- `database is locked` error
- Timeouts on database operations

**Diagnosis**:
```bash
# Check journal mode (should be 'wal')
python3 -c "
import sqlite3
conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
print('Journal mode:', conn.execute('PRAGMA journal_mode').fetchone()[0])
"

# Check for zombie connections
lsof /mnt/e/ai-data/sqlite/security.db 2>/dev/null || \
  fuser /mnt/e/ai-data/sqlite/security.db 2>/dev/null
```

**Solution**:
```bash
# Enable WAL mode if not enabled
python3 -c "
import sqlite3
conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
conn.execute('PRAGMA journal_mode=WAL')
conn.execute('PRAGMA synchronous=NORMAL')
conn.commit()
"

# Kill zombie connections
fuser -k /mnt/e/ai-data/sqlite/security.db

# Checkpoint WAL
python scripts/backup_security_db.py
```

#### 3. Approval Timeout

**Symptoms**:
- Approval requests expire before admin responds
- 408 Request Timeout errors

**Diagnosis**:
```bash
# Check pending approvals
python scripts/approval_cli.py list

# Check timeout setting
grep APPROVAL_TIMEOUT .env
```

**Solution**:
```bash
# Increase timeout (10 minutes)
echo "APPROVAL_TIMEOUT=600" >> .env

# Restart MCP server
docker compose -f docker/compose.p3.yml restart mcp-server

# For development: disable approval workflow
echo "APPROVAL_WORKFLOW_ENABLED=false" >> .env
```

#### 4. High Latency / Poor Performance

**Symptoms**:
- p95 latency > 200ms
- Slow API responses

**Diagnosis**:
```bash
# Check server resources
docker stats mcp-server

# Check database size
du -h /mnt/e/ai-data/sqlite/security.db*

# Run benchmark
docker exec -it mcp-server python3 tests/benchmark_rbac.py --duration 30 --rps 50
```

**Solution**:
- Verify external SSD is mounted and healthy
- Check for disk I/O bottlenecks
- Increase cache TTL: `RBAC_CACHE_TTL=600` (10 minutes)
- Reduce concurrent requests
- Optimize database: `VACUUM` and `ANALYZE`

---

## Security Best Practices

1. **Principle of Least Privilege**
   - Assign minimum required permissions
   - Use guest role for read-only access
   - Reserve admin role for trusted operators

2. **Regular Audits**
   - Review audit logs weekly
   - Monitor for unusual access patterns
   - Investigate repeated denials

3. **Approval Workflow**
   - Enable for production environments
   - Set appropriate timeouts (5-10 minutes)
   - Document approval decisions

4. **Database Maintenance**
   - Backup security.db daily
   - Rotate audit logs monthly
   - Test restore procedures

5. **Monitoring**
   - Alert on high error rates
   - Track approval response times
   - Monitor database performance

---

## References

- **RBAC Implementation**: `docs/security/IMPLEMENTATION_SUMMARY.md`
- **Approval Workflow**: `docs/security/APPROVAL_GUIDE.md`
- **Operations Guide**: `docs/security/RBAC_GUIDE.md`
- **Issue Tracker**: GitHub Issues #8, #16, #18

---

**Document Version**: 1.0.0
**Last Updated**: 2025-10-10
**Maintained By**: Security Team
