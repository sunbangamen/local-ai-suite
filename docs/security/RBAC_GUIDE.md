# RBAC Operations Guide

**Local AI Suite - RBAC Administration Manual**

Last Updated: 2025-10-10
Version: 1.0.0

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [User Management](#user-management)
3. [Role Management](#role-management)
4. [Permission Management](#permission-management)
5. [Approval Workflow](#approval-workflow)
6. [Testing](#testing)
7. [Monitoring](#monitoring)
8. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Prerequisites

- Python 3.11+
- SQLite 3.x
- FastAPI MCP server running on port 8020
- Security database at `/mnt/e/ai-data/sqlite/security.db`

### Quick Start

**1. Verify Installation**:
```bash
# Check if database exists
ls -lh /mnt/e/ai-data/sqlite/security.db

# Check server status
curl http://localhost:8020/health

# Expected: {"status": "healthy", "rbac_enabled": true}
```

**2. Test Permission Check**:
```bash
# Developer accessing allowed tool
curl -X POST http://localhost:8020/tools/list_files/call \
  -H "X-User-ID: dev_user" \
  -H "Content-Type: application/json" \
  -d '{"arguments": {}}'

# Expected: 200 OK (or 404 if working_dir not set)

# Guest accessing denied tool
curl -X POST http://localhost:8020/tools/execute_python/call \
  -H "X-User-ID: guest_user" \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"code": "print(2+2)", "timeout": 30}}'

# Expected: 403 Forbidden with {"error": "Permission denied"}
```

**3. Check Audit Logs**:
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
cursor = conn.cursor()
cursor.execute('''
    SELECT timestamp, user_id, tool_name, status
    FROM security_audit_logs
    ORDER BY timestamp DESC
    LIMIT 10
''')
print('Recent Activity:')
for row in cursor.fetchall():
    print(f'  {row[0]} | {row[1]:15} | {row[2]:20} | {row[3]}')
"
```

---

## User Management

### List All Users

```python
# Python script: list_users.py
import sqlite3

conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
cursor = conn.cursor()

cursor.execute('''
    SELECT u.user_id, u.username, r.role_name, u.created_at
    FROM security_users u
    JOIN security_roles r ON u.role_id = r.role_id
    ORDER BY u.created_at DESC
''')

print(f"{'User ID':<20} {'Username':<25} {'Role':<15} {'Created':<20}")
print("="*80)
for row in cursor.fetchall():
    print(f"{row[0]:<20} {row[1]:<25} {row[2]:<15} {row[3]:<20}")

conn.close()
```

**Output Example**:
```
User ID              Username                  Role            Created
================================================================================
admin_user           Admin User                admin           2025-09-24 10:15:30
dev_user             Developer User            developer       2025-09-24 10:15:30
guest_user           Guest User                guest           2025-09-24 10:15:30
```

### Create User

**Option 1: SQL Command**:
```bash
python3 -c "
import sqlite3

conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
cursor = conn.cursor()

# Get role_id for 'developer'
cursor.execute('SELECT role_id FROM security_roles WHERE role_name = ?', ('developer',))
role_id = cursor.fetchone()[0]

# Create user
cursor.execute('''
    INSERT INTO security_users (user_id, username, role_id)
    VALUES (?, ?, ?)
''', ('new_dev', 'New Developer', role_id))

conn.commit()
print('✓ User created: new_dev')
"
```

**Option 2: Python Function**:
```python
# create_user.py
import sqlite3
import sys
from datetime import datetime

def create_user(user_id, username, role_name='developer'):
    \"\"\"Create a new user with specified role\"\"\"
    conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
    cursor = conn.cursor()

    try:
        # Get role_id
        cursor.execute('SELECT role_id FROM security_roles WHERE role_name = ?', (role_name,))
        result = cursor.fetchone()
        if not result:
            print(f'✗ Role not found: {role_name}')
            return False

        role_id = result[0]

        # Create user
        cursor.execute('''
            INSERT INTO security_users (user_id, username, role_id, created_at)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, role_id, datetime.now().isoformat()))

        conn.commit()
        print(f'✓ User created: {user_id} ({role_name})')
        return True

    except sqlite3.IntegrityError:
        print(f'✗ User already exists: {user_id}')
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: python create_user.py <user_id> <username> [role_name]')
        sys.exit(1)

    user_id = sys.argv[1]
    username = sys.argv[2]
    role_name = sys.argv[3] if len(sys.argv) > 3 else 'developer'

    create_user(user_id, username, role_name)
```

**Usage**:
```bash
python create_user.py john_doe "John Doe" developer
# ✓ User created: john_doe (developer)
```

### Update User Role

```bash
python3 -c "
import sqlite3

conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
cursor = conn.cursor()

# Get role_id for 'admin'
cursor.execute('SELECT role_id FROM security_roles WHERE role_name = ?', ('admin',))
role_id = cursor.fetchone()[0]

# Update user
cursor.execute('''
    UPDATE security_users
    SET role_id = ?, updated_at = datetime('now')
    WHERE user_id = ?
''', (role_id, 'john_doe'))

conn.commit()
print(f'✓ User updated: john_doe → admin ({cursor.rowcount} rows)')
"
```

### Delete User

```bash
python3 -c "
import sqlite3

conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
cursor = conn.cursor()

# Delete user
cursor.execute('DELETE FROM security_users WHERE user_id = ?', ('john_doe',))

conn.commit()
print(f'✓ User deleted: john_doe ({cursor.rowcount} rows)')
"
```

---

## Role Management

### List All Roles

```bash
python3 -c "
import sqlite3

conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
cursor = conn.cursor()

cursor.execute('''
    SELECT r.role_name, r.description, COUNT(rp.permission_id) as perm_count
    FROM security_roles r
    LEFT JOIN security_role_permissions rp ON r.role_id = rp.role_id
    GROUP BY r.role_id, r.role_name, r.description
    ORDER BY r.role_name
''')

print(f\"{'Role':<15} {'Permissions':<12} {'Description':<50}\")
print('='*80)
for row in cursor.fetchall():
    print(f'{row[0]:<15} {row[2]:<12} {row[1]:<50}')
"
```

**Output**:
```
Role            Permissions  Description
================================================================================
admin           21           Full administrative access to all MCP tools
developer       15           Developer access with code execution and Git operations
guest           7            Read-only access to files and logs
```

### View Role Permissions

```bash
python3 -c "
import sqlite3

conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
cursor = conn.cursor()

role_name = 'developer'  # Change as needed

cursor.execute('''
    SELECT p.permission_name, p.sensitivity_level, p.resource_type, p.action
    FROM security_roles r
    JOIN security_role_permissions rp ON r.role_id = rp.role_id
    JOIN security_permissions p ON rp.permission_id = p.permission_id
    WHERE r.role_name = ?
    ORDER BY p.sensitivity_level DESC, p.permission_name
''', (role_name,))

print(f'Permissions for role: {role_name}')
print(f\"{'Permission':<25} {'Sensitivity':<12} {'Type':<10} {'Action':<10}\")
print('='*60)
for row in cursor.fetchall():
    print(f'{row[0]:<25} {row[1]:<12} {row[2]:<10} {row[3]:<10}')
"
```

### Create Custom Role

```python
# create_role.py
import sqlite3

def create_role(role_name, description, permission_names):
    \"\"\"Create a custom role with specified permissions\"\"\"
    conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
    cursor = conn.cursor()

    try:
        # Create role
        cursor.execute('''
            INSERT INTO security_roles (role_name, description, is_system_role)
            VALUES (?, ?, 0)
        ''', (role_name, description))

        role_id = cursor.lastrowid

        # Get permission IDs
        placeholders = ','.join('?' * len(permission_names))
        cursor.execute(f'''
            SELECT permission_id, permission_name
            FROM security_permissions
            WHERE permission_name IN ({placeholders})
        ''', permission_names)

        permissions = cursor.fetchall()

        # Assign permissions
        for perm_id, perm_name in permissions:
            cursor.execute('''
                INSERT INTO security_role_permissions (role_id, permission_id)
                VALUES (?, ?)
            ''', (role_id, perm_id))

        conn.commit()
        print(f'✓ Role created: {role_name}')
        print(f'  Permissions assigned: {len(permissions)}')
        return True

    except sqlite3.IntegrityError as e:
        print(f'✗ Role creation failed: {e}')
        return False
    finally:
        conn.close()

# Example: Create "analyst" role with read-only + RAG permissions
if __name__ == '__main__':
    create_role(
        role_name='analyst',
        description='Data analyst with RAG and visualization access',
        permission_names=[
            'read_file',
            'list_files',
            'rag_search',
            'ai_chat',
            'git_status',
            'git_log',
            'git_diff',
            'web_screenshot',
            'web_scrape'
        ]
    )
```

---

## Permission Management

### Tool Permission Matrix

| Tool | Sensitivity | Guest | Developer | Admin | Description |
|------|------------|-------|-----------|-------|-------------|
| read_file | MEDIUM | ✓ | ✓ | ✓ | Read file contents |
| write_file | HIGH | ✗ | ✓ | ✓ | Modify files (approval) |
| list_files | LOW | ✓ | ✓ | ✓ | Browse directories |
| execute_python | CRITICAL | ✗ | ✓ | ✓ | Run Python code (approval) |
| execute_bash | CRITICAL | ✗ | ✓ | ✓ | Run shell commands (approval) |
| rag_search | LOW | ✓ | ✓ | ✓ | Search documents |
| ai_chat | LOW | ✓ | ✓ | ✓ | AI chat interactions |
| git_status | LOW | ✓ | ✓ | ✓ | View repository status |
| git_log | LOW | ✓ | ✓ | ✓ | View commit history |
| git_diff | MEDIUM | ✓ | ✓ | ✓ | View code changes |
| git_add | MEDIUM | ✗ | ✓ | ✓ | Stage changes |
| git_commit | HIGH | ✗ | ✗ | ✓ | Create commits (approval) |
| web_screenshot | LOW | ✗ | ✓ | ✓ | Capture web pages |
| web_scrape | MEDIUM | ✗ | ✓ | ✓ | Extract web content |
| web_analyze_ui | LOW | ✗ | ✓ | ✓ | Analyze UI elements |
| web_automate | HIGH | ✗ | ✗ | ✓ | Web automation (approval) |
| notion_create_page | MEDIUM | ✗ | ✗ | ✓ | Create Notion pages |
| notion_search | LOW | ✗ | ✗ | ✓ | Search Notion workspace |
| web_to_notion | MEDIUM | ✗ | ✗ | ✓ | Save web content to Notion |
| switch_model | HIGH | ✗ | ✗ | ✓ | Change AI model (approval) |
| get_current_model | LOW | ✗ | ✓ | ✓ | View active AI model |

### Add Permission to Role

```bash
python3 -c "
import sqlite3

conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
cursor = conn.cursor()

role_name = 'developer'
permission_name = 'web_automate'

# Get role_id and permission_id
cursor.execute('SELECT role_id FROM security_roles WHERE role_name = ?', (role_name,))
role_id = cursor.fetchone()[0]

cursor.execute('SELECT permission_id FROM security_permissions WHERE permission_name = ?', (permission_name,))
permission_id = cursor.fetchone()[0]

# Add permission
cursor.execute('''
    INSERT OR IGNORE INTO security_role_permissions (role_id, permission_id)
    VALUES (?, ?)
''', (role_id, permission_id))

conn.commit()
print(f'✓ Permission added: {permission_name} → {role_name}')
"
```

### Remove Permission from Role

```bash
python3 -c "
import sqlite3

conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
cursor = conn.cursor()

role_name = 'developer'
permission_name = 'web_automate'

# Get role_id and permission_id
cursor.execute('SELECT role_id FROM security_roles WHERE role_name = ?', (role_name,))
role_id = cursor.fetchone()[0]

cursor.execute('SELECT permission_id FROM security_permissions WHERE permission_name = ?', (permission_name,))
permission_id = cursor.fetchone()[0]

# Remove permission
cursor.execute('''
    DELETE FROM security_role_permissions
    WHERE role_id = ? AND permission_id = ?
''', (role_id, permission_id))

conn.commit()
print(f'✓ Permission removed: {permission_name} from {role_name}')
"
```

---

## Approval Workflow

### Enable/Disable Workflow

**Enable for production**:
```bash
# Update .env
echo "APPROVAL_WORKFLOW_ENABLED=true" >> .env
echo "APPROVAL_TIMEOUT=300" >> .env  # 5 minutes

# Restart server
docker compose -f docker/compose.p3.yml restart mcp-server
```

**Disable for development**:
```bash
# Update .env
echo "APPROVAL_WORKFLOW_ENABLED=false" >> .env

# Restart server
docker compose -f docker/compose.p3.yml restart mcp-server
```

### List Pending Approvals

```bash
python scripts/approval_cli.py list

# Or via SQL:
python3 -c "
import sqlite3
from datetime import datetime

conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
cursor = conn.cursor()

cursor.execute('''
    SELECT request_id, tool_name, user_id, role, requested_at, expires_at
    FROM approval_requests
    WHERE status = 'pending'
      AND datetime(expires_at) > datetime('now')
    ORDER BY requested_at ASC
''')

print('Pending Approval Requests:')
print('='*80)
for row in cursor.fetchall():
    print(f'Request ID: {row[0]}')
    print(f'Tool: {row[1]}')
    print(f'User: {row[2]} ({row[3]})')
    print(f'Requested: {row[4]}')
    print(f'Expires: {row[5]}')
    print('-'*80)
"
```

### Approve Request

```bash
python scripts/approval_cli.py approve <request_id> \
  --reason "Authorized by security team - ticket #1234"

# Or via SQL:
python3 -c "
import sqlite3

conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
cursor = conn.cursor()

request_id = 'a1b2c3d4-...'
responder_id = 'admin_user'
reason = 'Authorized by security team'

cursor.execute('''
    UPDATE approval_requests
    SET status = 'approved',
        responded_at = datetime('now'),
        responder_id = ?,
        response_reason = ?
    WHERE request_id = ?
      AND status = 'pending'
''', (responder_id, reason, request_id))

conn.commit()
print(f'✓ Approved: {request_id} ({cursor.rowcount} rows)')
"
```

### Reject Request

```bash
python scripts/approval_cli.py reject <request_id> \
  --reason "Policy violation: unapproved code execution"

# Or via SQL:
python3 -c "
import sqlite3

conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
cursor = conn.cursor()

request_id = 'a1b2c3d4-...'
responder_id = 'admin_user'
reason = 'Policy violation'

cursor.execute('''
    UPDATE approval_requests
    SET status = 'rejected',
        responded_at = datetime('now'),
        responder_id = ?,
        response_reason = ?
    WHERE request_id = ?
      AND status = 'pending'
''', (responder_id, reason, request_id))

conn.commit()
print(f'✓ Rejected: {request_id} ({cursor.rowcount} rows)')
"
```

### Cleanup Expired Requests

```bash
python3 -c "
import sqlite3

conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
cursor = conn.cursor()

# Mark expired requests as timeout
cursor.execute('''
    UPDATE approval_requests
    SET status = 'timeout'
    WHERE status = 'pending'
      AND datetime(expires_at) < datetime('now')
''')

conn.commit()
print(f'✓ Cleaned up expired requests: {cursor.rowcount}')
"
```

---

## Testing

### Unit Tests

```bash
# Integration tests
docker exec -it mcp-server pytest tests/integration/test_rbac_integration.py -v

# Approval workflow tests
docker exec -it mcp-server pytest tests/test_approval_workflow.py -v

# WAL mode tests
docker exec -it mcp-server pytest tests/security/test_wal_mode.py -v
```

### Performance Benchmark

```bash
# Run 60-second benchmark at 100 RPS
docker exec -it mcp-server python3 tests/benchmark_rbac.py --duration 60 --rps 100

# Quick test (30 seconds, 50 RPS)
docker exec -it mcp-server python3 tests/benchmark_rbac.py --duration 30 --rps 50
```

### Manual API Testing

```bash
# Test 1: Guest denied execute_python
curl -X POST http://localhost:8020/tools/execute_python/call \
  -H "X-User-ID: guest_user" \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"code": "print(2+2)", "timeout": 30}}'

# Expected: 403 {"error": "Permission denied"}

# Test 2: Developer allowed list_files
curl -X POST http://localhost:8020/tools/list_files/call \
  -H "X-User-ID: dev_user" \
  -H "Content-Type: application/json" \
  -d '{"arguments": {}}'

# Expected: 200 OK or 404 (working_dir not set)

# Test 3: Admin approval workflow
curl -X POST http://localhost:8020/tools/git_commit/call \
  -H "X-User-ID: admin_user" \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"message": "test commit"}}'

# Expected: 202 Accepted (approval pending) or 200 OK (if APPROVAL_WORKFLOW_ENABLED=false)
```

---

## Monitoring

### Real-time Activity Monitor

```bash
# Watch audit logs in real-time (Linux/macOS)
watch -n 1 "python3 -c \"
import sqlite3
conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
cursor = conn.cursor()
cursor.execute('''
    SELECT timestamp, user_id, tool_name, status
    FROM security_audit_logs
    ORDER BY timestamp DESC
    LIMIT 10
''')
print('Recent Activity:')
for row in cursor.fetchall():
    print(f'{row[0]} | {row[1]:15} | {row[2]:20} | {row[3]}')
\""
```

### Daily Activity Report

```python
# daily_report.py
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
cursor = conn.cursor()

# Date range (last 24 hours)
end_date = datetime.now()
start_date = end_date - timedelta(days=1)

# Total requests
cursor.execute('''
    SELECT COUNT(*) FROM security_audit_logs
    WHERE timestamp >= ?
''', (start_date.isoformat(),))
total = cursor.fetchone()[0]

# By status
cursor.execute('''
    SELECT status, COUNT(*) as count
    FROM security_audit_logs
    WHERE timestamp >= ?
    GROUP BY status
    ORDER BY count DESC
''', (start_date.isoformat(),))
by_status = cursor.fetchall()

# By user
cursor.execute('''
    SELECT user_id, COUNT(*) as count
    FROM security_audit_logs
    WHERE timestamp >= ?
    GROUP BY user_id
    ORDER BY count DESC
''', (start_date.isoformat(),))
by_user = cursor.fetchall()

# Top tools
cursor.execute('''
    SELECT tool_name, COUNT(*) as count
    FROM security_audit_logs
    WHERE timestamp >= ?
    GROUP BY tool_name
    ORDER BY count DESC
    LIMIT 10
''', (start_date.isoformat(),))
top_tools = cursor.fetchall()

# Print report
print(f"\nDaily Activity Report")
print(f"Period: {start_date.strftime('%Y-%m-%d %H:%M')} - {end_date.strftime('%Y-%m-%d %H:%M')}")
print("="*60)
print(f"\nTotal Requests: {total}")

print(f"\nBy Status:")
for status, count in by_status:
    print(f"  {status:20} {count:6} ({count/total*100:.1f}%)")

print(f"\nBy User:")
for user_id, count in by_user:
    print(f"  {user_id:20} {count:6} ({count/total*100:.1f}%)")

print(f"\nTop 10 Tools:")
for tool, count in top_tools:
    print(f"  {tool:25} {count:6} ({count/total*100:.1f}%)")

conn.close()
```

---

## Troubleshooting

### Debug Commands

**Check database integrity**:
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
result = conn.execute('PRAGMA integrity_check').fetchone()[0]
print('Integrity check:', result)
# Expected: 'ok'
"
```

**Show all users and roles**:
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
cursor = conn.cursor()
cursor.execute('''
    SELECT u.user_id, u.username, r.role_name
    FROM security_users u
    JOIN security_roles r ON u.role_id = r.role_id
''')
for row in cursor.fetchall():
    print(f'{row[0]:20} {row[1]:25} ({row[2]})')
"
```

**Count audit logs**:
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('/mnt/e/ai-data/sqlite/security.db')
total = conn.execute('SELECT COUNT(*) FROM security_audit_logs').fetchone()[0]
print(f'Total audit logs: {total:,}')
"
```

**Clear permission cache (restart server)**:
```bash
docker compose -f docker/compose.p3.yml restart mcp-server
```

---

## References

- **Security Guide**: `docs/security/SECURITY.md`
- **Approval Guide**: `docs/security/APPROVAL_GUIDE.md`
- **Implementation Summary**: `docs/security/IMPLEMENTATION_SUMMARY.md`
- **GitHub Issues**: #8 (RBAC), #16 (Approval), #18 (Ops Ready)

---

**Document Version**: 1.0.0
**Last Updated**: 2025-10-10
**Maintained By**: Operations Team
