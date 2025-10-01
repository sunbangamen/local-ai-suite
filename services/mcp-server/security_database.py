#!/usr/bin/env python3
"""
Security Database Manager
SQLite database operations with connection pooling and WAL mode
"""

import asyncio
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

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or SecuritySettings.get_db_path()
        self._connection = None
        self._initialized = False

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
                    with open(schema_path, 'r') as f:
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
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def create_user(
        self,
        user_id: str,
        username: str,
        role_id: int
    ) -> bool:
        """Create new user"""
        try:
            async with self.get_connection() as db:
                await db.execute(
                    """
                    INSERT INTO security_users (user_id, username, role_id)
                    VALUES (?, ?, ?)
                    """,
                    (user_id, username, role_id)
                )
                await db.commit()
                logger.info(f"User created: {user_id} (role_id={role_id})")
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
                    (role_id, user_id)
                )
                await db.commit()
                logger.info(f"User role updated: {user_id} -> role_id={role_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to update user role: {e}")
            return False

    # ========================================================================
    # Role Operations
    # ========================================================================

    async def get_role(self, role_id: int) -> Optional[Dict]:
        """Get role by ID"""
        async with self.get_connection() as db:
            async with db.execute(
                "SELECT * FROM security_roles WHERE role_id = ?",
                (role_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_role_by_name(self, role_name: str) -> Optional[Dict]:
        """Get role by name"""
        async with self.get_connection() as db:
            async with db.execute(
                "SELECT * FROM security_roles WHERE role_name = ?",
                (role_name,)
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
                (permission_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_permission_by_name(self, permission_name: str) -> Optional[Dict]:
        """Get permission by name"""
        async with self.get_connection() as db:
            async with db.execute(
                "SELECT * FROM security_permissions WHERE permission_name = ?",
                (permission_name,)
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
                (role_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def check_permission(
        self,
        user_id: str,
        permission_name: str
    ) -> Tuple[bool, str]:
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
                (user_id, permission_name)
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
        request_data: Optional[str] = None
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
                (user_id, tool_name, action, status, error_message, execution_time_ms, request_data)
            )
            await db.commit()
            return cursor.lastrowid

    async def get_audit_logs(
        self,
        user_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
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
                (f'-{hours} hours',)
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
                (f'-{hours} hours',)
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
                (f'-{hours} hours',)
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
                (f'-{hours} hours',)
            ) as cursor:
                row = await cursor.fetchone()
                error_count = row[0] if row else 0

            return {
                "total_requests": total,
                "success_count": success_count,
                "denied_count": denied_count,
                "error_count": error_count,
                "success_rate": (success_count / total * 100) if total > 0 else 0,
                "hours": hours
            }

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
                "page_size": page_size
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
