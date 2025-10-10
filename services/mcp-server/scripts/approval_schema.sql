-- ============================================================================
-- Approval Workflow Schema Extension
-- SQLite 3.37+ with WAL Mode
-- Created: 2025-10-10
-- Issue: #16 - MCP 서버 승인 워크플로우 구현
-- ============================================================================

-- ============================================================================
-- Table: approval_requests
-- Purpose: Track approval requests for HIGH/CRITICAL tools
-- ============================================================================

CREATE TABLE IF NOT EXISTS approval_requests (
    request_id TEXT PRIMARY KEY,                -- UUID
    tool_name TEXT NOT NULL,                    -- MCP 도구명
    user_id TEXT NOT NULL,                      -- 요청 사용자
    role TEXT NOT NULL,                         -- 사용자 역할
    request_data TEXT,                          -- JSON 직렬화된 도구 인자
    status TEXT DEFAULT 'pending',              -- pending/approved/rejected/expired/timeout
    requested_at TEXT DEFAULT (datetime('now')),
    responded_at TEXT,                          -- 승인/거부 시각
    responder_id TEXT,                          -- 승인/거부한 관리자
    response_reason TEXT,                       -- 승인/거부 사유
    expires_at TEXT NOT NULL,                   -- 만료 시각 (requested_at + timeout)
    FOREIGN KEY (user_id) REFERENCES security_users(user_id)
);

-- Indexes for performance optimization
CREATE INDEX IF NOT EXISTS idx_approval_status_expires
    ON approval_requests(status, expires_at);

CREATE INDEX IF NOT EXISTS idx_approval_user
    ON approval_requests(user_id);

CREATE INDEX IF NOT EXISTS idx_approval_requested_at
    ON approval_requests(requested_at DESC);

-- View: pending_approvals (for convenience)
CREATE VIEW IF NOT EXISTS pending_approvals AS
SELECT
    request_id,
    tool_name,
    user_id,
    role,
    request_data,
    requested_at,
    expires_at,
    CAST((julianday(expires_at) - julianday('now')) * 86400 AS INTEGER) AS seconds_until_expiry
FROM approval_requests
WHERE status = 'pending'
  AND datetime('now') < expires_at
ORDER BY requested_at ASC;

-- ============================================================================
-- Migration Script
-- Run this to add approval_requests table to existing security.db
-- ============================================================================

-- Check if WAL mode is enabled
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA busy_timeout=5000;  -- 5 seconds wait for locks

-- Verify foreign key constraints are enabled
PRAGMA foreign_keys=ON;

-- Success message (will be ignored by executescript but useful for manual runs)
SELECT 'Approval workflow schema created successfully' AS message;
