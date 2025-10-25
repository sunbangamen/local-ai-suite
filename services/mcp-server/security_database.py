#!/usr/bin/env python3
"""
Security Database Manager
SQLite database operations with connection pooling and WAL mode
"""

import aiosqlite
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from contextlib import asynccontextmanager

from settings import SecuritySettings

logger = logging.getLogger(__name__)


class SecurityDatabase:
    """
    Manages SQLite database operations for security RBAC system

    Features:
    - WAL mode for concurrent access
    - Connection pooling
    - Async operations
    - Transaction support
    """

    def __init__(self, db_path: Optional[Path] = None, on_role_assigned=None):
        self.db_path = db_path or SecuritySettings.get_db_path()
        self._connection = None
        self._initialized = False
        self._on_role_assigned = on_role_assigned  # Callback for metrics (Issue #45 Phase 6.2)

    async def initialize(self) -> None:
        """Initialize database with schema"""
        if self._initialized:
            logger.warning("Database already initialized")
            return

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create connection and apply schema
        async with aiosqlite.connect(self.db_path) as db:
            # Enable WAL mode
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=NORMAL")
            await db.execute("PRAGMA cache_size=-64000")  # 64MB
            await db.execute("PRAGMA temp_store=MEMORY")

            # Read and execute schema
            schema_path = Path(__file__).parent / "scripts" / "security_schema.sql"
            if schema_path.exists():
                async with aiosqlite.connect(self.db_path) as db:
                    with open(schema_path, "r") as f:
                        schema_sql = f.read()
                    await db.executescript(schema_sql)
                    await db.commit()
                    logger.info(f"Security database initialized: {self.db_path}")
            else:
                logger.error(f"Schema file not found: {schema_path}")
                raise FileNotFoundError(f"Schema file not found: {schema_path}")

        self._initialized = True

    @asynccontextmanager
    async def get_connection(self):
        """Get database connection (context manager)"""
        if self._connection is not None:
            # Reuse supplied connection (tests or externally managed)
            conn = self._connection
            conn.row_factory = aiosqlite.Row
            yield conn
        else:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row  # Enable column access by name
                yield db

    # ========================================================================
    # User Operations
    # ========================================================================

    async def get_user(self, user_id: str) -> Optional[Dict]:
        """Get user by ID"""
        async with self.get_connection() as db:
            async with db.execute(
                "SELECT * FROM security_users WHERE user_id = ? AND is_active = 1",
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def create_user(self, user_id: str, username: str, role_id: int) -> bool:
        """Create new user"""
        try:
            async with self.get_connection() as db:
                await db.execute(
                    """
                    INSERT INTO security_users (user_id, username, role_id)
                    VALUES (?, ?, ?)
                    """,
                    (user_id, username, role_id),
                )
                await db.commit()
                logger.info(f"User created: {user_id} (role_id={role_id})")

                # Record metrics for role assignment (Issue #45 Phase 6.2)
                if self._on_role_assigned:
                    role_name = await self._get_role_name(role_id)
                    if role_name:
                        self._on_role_assigned(role_name)

                return True
        except aiosqlite.IntegrityError as e:
            logger.error(f"Failed to create user {user_id}: {e}")
            return False

    async def update_user_role(self, user_id: str, role_id: int) -> bool:
        """Update user's role"""
        try:
            async with self.get_connection() as db:
                await db.execute(
                    "UPDATE security_users SET role_id = ? WHERE user_id = ?",
                    (role_id, user_id),
                )
                await db.commit()
                logger.info(f"User role updated: {user_id} -> role_id={role_id}")

                # Record metrics for role assignment (Issue #45 Phase 6.2)
                if self._on_role_assigned:
                    role_name = await self._get_role_name(role_id)
                    if role_name:
                        self._on_role_assigned(role_name)

                return True
        except Exception as e:
            logger.error(f"Failed to update user role: {e}")
            return False

    async def _get_role_name(self, role_id: int) -> Optional[str]:
        """Get role name by role_id (Issue #45 Phase 6.2)"""
        try:
            async with self.get_connection() as db:
                async with db.execute(
                    "SELECT role_name FROM security_roles WHERE role_id = ?",
                    (role_id,),
                ) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else None
        except Exception as e:
            logger.error(f"Failed to get role name for role_id {role_id}: {e}")
            return None

    # ========================================================================
    # Role Operations
    # ========================================================================

    async def get_role(self, role_id: int) -> Optional[Dict]:
        """Get role by ID"""
        async with self.get_connection() as db:
            async with db.execute(
                "SELECT * FROM security_roles WHERE role_id = ?", (role_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_role_by_name(self, role_name: str) -> Optional[Dict]:
        """Get role by name"""
        async with self.get_connection() as db:
            async with db.execute(
                "SELECT * FROM security_roles WHERE role_name = ?", (role_name,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_all_roles(self) -> List[Dict]:
        """Get all roles"""
        async with self.get_connection() as db:
            async with db.execute("SELECT * FROM security_roles") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    # ========================================================================
    # Permission Operations
    # ========================================================================

    async def get_permission(self, permission_id: int) -> Optional[Dict]:
        """Get permission by ID"""
        async with self.get_connection() as db:
            async with db.execute(
                "SELECT * FROM security_permissions WHERE permission_id = ?",
                (permission_id,),
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_permission_by_name(self, permission_name: str) -> Optional[Dict]:
        """Get permission by name"""
        async with self.get_connection() as db:
            async with db.execute(
                "SELECT * FROM security_permissions WHERE permission_name = ?",
                (permission_name,),
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_role_permissions(self, role_id: int) -> List[Dict]:
        """Get all permissions for a role"""
        async with self.get_connection() as db:
            async with db.execute(
                """
                SELECT p.*
                FROM security_permissions p
                JOIN security_role_permissions rp ON p.permission_id = rp.permission_id
                WHERE rp.role_id = ?
                """,
                (role_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def check_permission(self, user_id: str, permission_name: str) -> Tuple[bool, str]:
        """
        Check if user has permission

        Returns:
            (allowed, reason)
        """
        async with self.get_connection() as db:
            async with db.execute(
                """
                SELECT COUNT(*) > 0 AS has_permission
                FROM v_user_permissions
                WHERE user_id = ? AND permission_name = ?
                """,
                (user_id, permission_name),
            ) as cursor:
                row = await cursor.fetchone()
                has_permission = bool(row[0]) if row else False

                if has_permission:
                    return (True, "Permission granted")
                else:
                    # Check if user exists
                    user = await self.get_user(user_id)
                    if not user:
                        return (False, f"User not found: {user_id}")
                    else:
                        return (False, f"Permission denied: {permission_name}")

    # ========================================================================
    # Test Helper Methods (for test_approval_workflow.py)
    # ========================================================================

    async def insert_user(self, user_id: str, role: str, attributes: str = "{}") -> bool:
        """
        Insert user for testing (simplified version)

        Args:
            user_id: User identifier
            role: Role name (will look up or create role_id)
            attributes: JSON attributes

        Returns:
            True if successful
        """
        try:
            async with self.get_connection() as db:
                # Get or create role
                role_row = await self.get_role_by_name(role)
                if not role_row:
                    # Create basic role if doesn't exist
                    await db.execute(
                        "INSERT INTO security_roles (role_name, description) VALUES (?, ?)",
                        (role, f"Auto-created role: {role}"),
                    )
                    await db.commit()
                    role_row = await self.get_role_by_name(role)

                role_id = role_row["role_id"]

                # Insert user
                await db.execute(
                    """
                    INSERT INTO security_users (user_id, username, role_id)
                    VALUES (?, ?, ?)
                    """,
                    (user_id, user_id, role_id),
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to insert test user: {e}")
            return False

    async def insert_permission(
        self,
        permission_name: str,
        description: str,
        sensitivity_level: str = "MEDIUM",
        resource_type: str = "tool",
        action: str = "execute",
    ) -> bool:
        """
        Insert permission for testing (matches actual schema)

        Args:
            permission_name: Permission/tool name
            description: Description
            sensitivity_level: LOW/MEDIUM/HIGH/CRITICAL
            resource_type: Resource type (tool, file, system)
            action: Action (read, write, execute)

        Returns:
            True if successful
        """
        try:
            async with self.get_connection() as db:
                await db.execute(
                    """
                    INSERT INTO security_permissions (
                        permission_name, resource_type, action,
                        description, sensitivity_level
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        permission_name,
                        resource_type,
                        action,
                        description,
                        sensitivity_level,
                    ),
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to insert test permission: {e}")
            return False

    async def assign_permission_to_role(self, role_name: str, permission_name: str) -> bool:
        """
        Assign permission to role (for testing)

        Args:
            role_name: Role name
            permission_name: Permission name

        Returns:
            True if successful
        """
        try:
            async with self.get_connection() as db:
                # Get role_id
                role = await self.get_role_by_name(role_name)
                if not role:
                    logger.error(f"Role not found: {role_name}")
                    return False

                # Get permission_id
                permission = await self.get_permission_by_name(permission_name)
                if not permission:
                    logger.error(f"Permission not found: {permission_name}")
                    return False

                # Insert mapping
                await db.execute(
                    """
                    INSERT OR IGNORE INTO security_role_permissions (role_id, permission_id)
                    VALUES (?, ?)
                    """,
                    (role["role_id"], permission["permission_id"]),
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to assign permission to role: {e}")
            return False

    # ========================================================================
    # Audit Log Operations
    # ========================================================================

    async def insert_audit_log(
        self,
        user_id: str,
        tool_name: str,
        action: str,
        status: str,
        error_message: Optional[str] = None,
        execution_time_ms: Optional[int] = None,
        request_data: Optional[str] = None,
    ) -> int:
        """
        Insert audit log entry

        Returns:
            log_id of inserted entry
        """
        async with self.get_connection() as db:
            cursor = await db.execute(
                """
                INSERT INTO security_audit_logs
                (user_id, tool_name, action, status, error_message, execution_time_ms, request_data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    tool_name,
                    action,
                    status,
                    error_message,
                    execution_time_ms,
                    request_data,
                ),
            )
            await db.commit()
            return cursor.lastrowid

    async def get_audit_logs(
        self,
        user_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        """Query audit logs with filters"""
        query = "SELECT * FROM security_audit_logs WHERE 1=1"
        params = []

        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)

        if tool_name:
            query += " AND tool_name = ?"
            params.append(tool_name)

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with self.get_connection() as db:
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def query_audit_logs(
        self,
        user_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        """Alias for get_audit_logs (for test compatibility)"""
        return await self.get_audit_logs(user_id, tool_name, status, limit, offset)

    async def get_audit_stats(self, hours: int = 24) -> Dict:
        """Get audit log statistics for last N hours"""
        async with self.get_connection() as db:
            # Total requests
            async with db.execute(
                """
                SELECT COUNT(*) as total
                FROM security_audit_logs
                WHERE timestamp >= datetime('now', ?)
                """,
                (f"-{hours} hours",),
            ) as cursor:
                row = await cursor.fetchone()
                total = row[0] if row else 0

            # Success count
            async with db.execute(
                """
                SELECT COUNT(*) as success_count
                FROM security_audit_logs
                WHERE timestamp >= datetime('now', ?) AND status = 'success'
                """,
                (f"-{hours} hours",),
            ) as cursor:
                row = await cursor.fetchone()
                success_count = row[0] if row else 0

            # Denied count
            async with db.execute(
                """
                SELECT COUNT(*) as denied_count
                FROM security_audit_logs
                WHERE timestamp >= datetime('now', ?) AND status = 'denied'
                """,
                (f"-{hours} hours",),
            ) as cursor:
                row = await cursor.fetchone()
                denied_count = row[0] if row else 0

            # Error count
            async with db.execute(
                """
                SELECT COUNT(*) as error_count
                FROM security_audit_logs
                WHERE timestamp >= datetime('now', ?) AND status = 'error'
                """,
                (f"-{hours} hours",),
            ) as cursor:
                row = await cursor.fetchone()
                error_count = row[0] if row else 0

            return {
                "total_requests": total,
                "success_count": success_count,
                "denied_count": denied_count,
                "error_count": error_count,
                "success_rate": (success_count / total * 100) if total > 0 else 0,
                "hours": hours,
            }

    # ========================================================================
    # Approval Request Operations (Issue #16)
    # ========================================================================

    async def create_approval_request(
        self,
        request_id: str,
        tool_name: str,
        user_id: str,
        role: str,
        request_data: str,
        timeout_seconds: int,
    ) -> bool:
        """
        Create approval request

        Args:
            request_id: UUID for the request
            tool_name: MCP tool name
            user_id: User requesting approval
            role: User's role
            request_data: JSON serialized tool arguments
            timeout_seconds: Timeout in seconds

        Returns:
            True if created successfully
        """
        try:
            async with self.get_connection() as db:
                await db.execute(
                    """
                    INSERT INTO approval_requests (
                        request_id, tool_name, user_id, role, request_data, expires_at
                    )
                    VALUES (?, ?, ?, ?, ?, datetime('now', ?))
                    """,
                    (
                        request_id,
                        tool_name,
                        user_id,
                        role,
                        request_data,
                        f"+{timeout_seconds} seconds",
                    ),
                )
                await db.commit()
                logger.info(f"Approval request created: {request_id} for {tool_name}")
                return True
        except Exception as e:
            logger.error(f"Failed to create approval request: {e}")
            return False

    async def get_approval_request(self, request_id: str) -> Optional[Dict]:
        """
        Get approval request by ID

        Args:
            request_id: Request UUID (full or short prefix)

        Returns:
            Request dict or None
        """
        async with self.get_connection() as db:
            # Try exact match first
            async with db.execute(
                "SELECT * FROM approval_requests WHERE request_id = ?", (request_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)

            # Try prefix match if exact fails (for short IDs)
            async with db.execute(
                "SELECT * FROM approval_requests WHERE request_id LIKE ?",
                (f"{request_id}%",),
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def update_approval_status(
        self, request_id: str, status: str, responder_id: str, response_reason: str
    ) -> bool:
        """
        Update approval request status

        Args:
            request_id: Request UUID
            status: New status (approved/rejected/timeout/expired)
            responder_id: User who responded
            response_reason: Reason for decision

        Returns:
            True if updated successfully, False if not found or already processed
        """
        try:
            async with self.get_connection() as db:
                # Check if request exists and is still pending
                async with db.execute(
                    "SELECT status FROM approval_requests WHERE request_id = ?",
                    (request_id,),
                ) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        logger.warning(f"Approval request not found: {request_id}")
                        return False
                    if row[0] != "pending":
                        logger.warning(
                            f"Approval request already processed: {request_id} (status={row[0]})"
                        )
                        return False

                # Update status
                await db.execute(
                    """
                    UPDATE approval_requests
                    SET status = ?, responder_id = ?, response_reason = ?, responded_at = datetime('now')
                    WHERE request_id = ? AND status = 'pending'
                    """,
                    (status, responder_id, response_reason, request_id),
                )
                await db.commit()
                logger.info(f"Approval request {status}: {request_id} by {responder_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to update approval status: {e}")
            return False

    async def list_pending_approvals(self, limit: int = 50) -> List[Dict]:
        """
        List pending approval requests

        Args:
            limit: Maximum number of requests to return

        Returns:
            List of pending requests
        """
        async with self.get_connection() as db:
            async with db.execute(
                """
                SELECT * FROM pending_approvals
                LIMIT ?
                """,
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def cleanup_expired_approvals(self) -> int:
        """
        Cleanup expired approval requests

        Returns:
            Number of requests marked as expired
        """
        try:
            async with self.get_connection() as db:
                # Mark expired requests
                cursor = await db.execute(
                    """
                    UPDATE approval_requests
                    SET status = 'expired', responded_at = datetime('now')
                    WHERE status = 'pending' AND datetime('now') >= expires_at
                    """
                )
                count = cursor.rowcount
                await db.commit()

                if count > 0:
                    logger.info(f"Marked {count} approval requests as expired")

                return count
        except Exception as e:
            logger.error(f"Failed to cleanup expired approvals: {e}")
            return 0

    # ========================================================================
    # Maintenance Operations
    # ========================================================================

    async def vacuum(self) -> None:
        """Optimize database (rebuild, reclaim space)"""
        async with self.get_connection() as db:
            await db.execute("VACUUM")
            logger.info("Database vacuumed")

    async def checkpoint(self) -> None:
        """Checkpoint WAL file (flush to main DB)"""
        async with self.get_connection() as db:
            await db.execute("PRAGMA wal_checkpoint(FULL)")
            logger.info("WAL checkpoint completed")

    async def get_db_info(self) -> Dict:
        """Get database information"""
        async with self.get_connection() as db:
            # Page count
            async with db.execute("PRAGMA page_count") as cursor:
                page_count = (await cursor.fetchone())[0]

            # Page size
            async with db.execute("PRAGMA page_size") as cursor:
                page_size = (await cursor.fetchone())[0]

            # Journal mode
            async with db.execute("PRAGMA journal_mode") as cursor:
                journal_mode = (await cursor.fetchone())[0]

            # WAL file size
            wal_path = Path(str(self.db_path) + "-wal")
            wal_size = wal_path.stat().st_size if wal_path.exists() else 0

            return {
                "db_path": str(self.db_path),
                "db_size_bytes": page_count * page_size,
                "db_size_mb": round(page_count * page_size / 1024 / 1024, 2),
                "wal_size_bytes": wal_size,
                "wal_size_mb": round(wal_size / 1024 / 1024, 2),
                "journal_mode": journal_mode,
                "page_count": page_count,
                "page_size": page_size,
            }


# Singleton instance
_security_db: Optional[SecurityDatabase] = None


def get_security_database() -> SecurityDatabase:
    """Get singleton SecurityDatabase instance"""
    global _security_db
    if _security_db is None:
        _security_db = SecurityDatabase()
    return _security_db


def reset_security_database(db_path: Optional[str] = None) -> Optional[str]:
    """
    Reset singleton instance and optionally override DB path

    Args:
        db_path: New database path (if provided, overrides SecuritySettings.SECURITY_DB_PATH)

    Returns:
        Original DB path (for restoration)
    """
    global _security_db

    # Get original path
    original_path = str(SecuritySettings.get_db_path())

    # Reset singleton
    _security_db = None

    # Override path if provided
    if db_path:
        SecuritySettings.SECURITY_DB_PATH = db_path
        logger.info(f"Security DB path overridden: {original_path} -> {db_path}")

    return original_path


async def init_database() -> None:
    """Initialize security database (call at startup)"""
    db = get_security_database()
    await db.initialize()
