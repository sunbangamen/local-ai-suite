-- ============================================================================
-- Security Database Schema for RBAC System
-- SQLite 3.37+ with WAL Mode
-- Created: 2025-10-01
-- Issue: #8 - MCP 보안 강화
-- ============================================================================

-- Enable WAL mode for concurrent access
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=-64000;  -- 64MB cache
PRAGMA temp_store=MEMORY;

-- ============================================================================
-- Table 1: security_users
-- Purpose: Store user information and role assignments
-- ============================================================================

CREATE TABLE IF NOT EXISTS security_users (
    user_id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    role_id INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    is_active INTEGER DEFAULT 1,  -- 1 = active, 0 = disabled
    FOREIGN KEY (role_id) REFERENCES security_roles(role_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_users_role ON security_users(role_id);
CREATE INDEX IF NOT EXISTS idx_users_active ON security_users(is_active);

-- ============================================================================
-- Table 2: security_roles
-- Purpose: Define available roles (guest, developer, admin)
-- ============================================================================

CREATE TABLE IF NOT EXISTS security_roles (
    role_id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    is_system_role INTEGER DEFAULT 0  -- 1 = system role (cannot delete)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_roles_name ON security_roles(role_name);

-- ============================================================================
-- Table 3: security_permissions
-- Purpose: Define granular permissions for MCP tools
-- ============================================================================

CREATE TABLE IF NOT EXISTS security_permissions (
    permission_id INTEGER PRIMARY KEY AUTOINCREMENT,
    permission_name TEXT NOT NULL UNIQUE,
    resource_type TEXT,  -- tool, file, system
    action TEXT,         -- read, write, execute
    description TEXT,
    sensitivity_level TEXT DEFAULT 'MEDIUM',  -- LOW, MEDIUM, HIGH, CRITICAL
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_permissions_name ON security_permissions(permission_name);
CREATE INDEX IF NOT EXISTS idx_permissions_type ON security_permissions(resource_type);
CREATE INDEX IF NOT EXISTS idx_permissions_sensitivity ON security_permissions(sensitivity_level);

-- ============================================================================
-- Table 4: security_role_permissions
-- Purpose: Map roles to permissions (many-to-many)
-- ============================================================================

CREATE TABLE IF NOT EXISTS security_role_permissions (
    role_id INTEGER NOT NULL,
    permission_id INTEGER NOT NULL,
    granted_at TEXT DEFAULT (datetime('now')),
    granted_by TEXT DEFAULT 'system',
    PRIMARY KEY (role_id, permission_id),
    FOREIGN KEY (role_id) REFERENCES security_roles(role_id) ON DELETE CASCADE,
    FOREIGN KEY (permission_id) REFERENCES security_permissions(permission_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_role_perms_role ON security_role_permissions(role_id);
CREATE INDEX IF NOT EXISTS idx_role_perms_perm ON security_role_permissions(permission_id);

-- ============================================================================
-- Table 5: security_audit_logs
-- Purpose: Record all tool invocations and security events
-- ============================================================================

CREATE TABLE IF NOT EXISTS security_audit_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    tool_name TEXT,
    action TEXT,
    status TEXT,  -- success, denied, error, timeout
    error_message TEXT,
    request_data TEXT,  -- JSON string of request parameters
    timestamp TEXT DEFAULT (datetime('now')),
    execution_time_ms INTEGER,
    ip_address TEXT,
    session_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_user ON security_audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_tool ON security_audit_logs(tool_name);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON security_audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_status ON security_audit_logs(status);

-- ============================================================================
-- Table 6: security_sessions
-- Purpose: Track active user sessions and rate limiting
-- ============================================================================

CREATE TABLE IF NOT EXISTS security_sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    last_activity TEXT DEFAULT (datetime('now')),
    expires_at TEXT,
    ip_address TEXT,
    user_agent TEXT,
    is_active INTEGER DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES security_users(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON security_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_active ON security_sessions(is_active);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON security_sessions(expires_at);

-- ============================================================================
-- Views for Common Queries
-- ============================================================================

-- View: User Permissions (denormalized for fast lookup)
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
WHERE u.is_active = 1;

-- View: Recent Audit Logs (last 24 hours)
CREATE VIEW IF NOT EXISTS v_recent_audit_logs AS
SELECT
    log_id,
    user_id,
    tool_name,
    action,
    status,
    timestamp,
    execution_time_ms
FROM security_audit_logs
WHERE timestamp >= datetime('now', '-1 day')
ORDER BY timestamp DESC;

-- View: Permission Denials Summary
CREATE VIEW IF NOT EXISTS v_permission_denials AS
SELECT
    user_id,
    tool_name,
    COUNT(*) as denial_count,
    MAX(timestamp) as last_denial
FROM security_audit_logs
WHERE status = 'denied'
GROUP BY user_id, tool_name
ORDER BY denial_count DESC;

-- ============================================================================
-- Triggers for Data Integrity
-- ============================================================================

-- Trigger: Update updated_at on user modification
CREATE TRIGGER IF NOT EXISTS trg_users_update_timestamp
AFTER UPDATE ON security_users
FOR EACH ROW
BEGIN
    UPDATE security_users
    SET updated_at = datetime('now')
    WHERE user_id = NEW.user_id;
END;

-- Trigger: Update last_activity on session access
CREATE TRIGGER IF NOT EXISTS trg_sessions_update_activity
AFTER UPDATE ON security_sessions
FOR EACH ROW
WHEN NEW.is_active = 1
BEGIN
    UPDATE security_sessions
    SET last_activity = datetime('now')
    WHERE session_id = NEW.session_id;
END;

-- Trigger: Prevent deletion of system roles
CREATE TRIGGER IF NOT EXISTS trg_roles_prevent_system_delete
BEFORE DELETE ON security_roles
FOR EACH ROW
WHEN OLD.is_system_role = 1
BEGIN
    SELECT RAISE(ABORT, 'Cannot delete system role');
END;

-- ============================================================================
-- Functions (Simulated with queries for SQLite)
-- ============================================================================

-- Note: SQLite doesn't support stored procedures, but we can document
-- common queries here for the Python layer to use

-- Check if user has permission:
-- SELECT COUNT(*) > 0 AS has_permission
-- FROM v_user_permissions
-- WHERE user_id = ? AND permission_name = ?;

-- Get user's role:
-- SELECT role_name
-- FROM security_users u
-- JOIN security_roles r ON u.role_id = r.role_id
-- WHERE u.user_id = ?;

-- Get all permissions for role:
-- SELECT p.permission_name
-- FROM security_role_permissions rp
-- JOIN security_permissions p ON rp.permission_id = p.permission_id
-- WHERE rp.role_id = ?;

-- Log audit entry (parameterized):
-- INSERT INTO security_audit_logs (user_id, tool_name, action, status, execution_time_ms)
-- VALUES (?, ?, ?, ?, ?);

-- ============================================================================
-- Schema Version Tracking
-- ============================================================================

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT DEFAULT (datetime('now')),
    description TEXT
);

INSERT OR IGNORE INTO schema_version (version, description)
VALUES (1, 'Initial RBAC schema with 6 tables and views');

-- ============================================================================
-- Performance Optimization Settings
-- ============================================================================

-- Analyze tables for query optimizer
ANALYZE;

-- ============================================================================
-- Schema Complete
-- ============================================================================

SELECT 'Security database schema created successfully' AS status;
