#!/usr/bin/env python3
"""
RBAC Manager
Role-Based Access Control permission checking with caching
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple

from security_database import get_security_database
from settings import SecuritySettings

logger = logging.getLogger(__name__)


class RBACManager:
    """
    Manages RBAC permission checks with in-memory caching

    Features:
    - Permission caching with TTL
    - User-role lookup optimization
    - Cache invalidation on updates
    """

    def __init__(self, cache_ttl: int = 300):
        """
        Initialize RBAC Manager

        Args:
            cache_ttl: Cache TTL in seconds (default 5 minutes)
        """
        self.cache_ttl = cache_ttl
        self._permission_cache: Dict[str, Dict] = {}
        self._role_cache: Dict[str, int] = {}
        self.db = get_security_database()

    async def check_permission(self, user_id: str, tool_name: str) -> Tuple[bool, str]:
        """
        Check if user has permission to use tool

        Args:
            user_id: User identifier
            tool_name: MCP tool name

        Returns:
            (allowed, reason)
        """
        # Check if RBAC is enabled
        if not SecuritySettings.is_rbac_enabled():
            return (True, "RBAC disabled")

        # Check cache
        cache_key = f"{user_id}:{tool_name}"
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return (cached["allowed"], cached["reason"])

        # Query database
        allowed, reason = await self.db.check_permission(user_id, tool_name)

        # Cache result
        self._add_to_cache(cache_key, allowed, reason)

        return (allowed, reason)

    async def get_user_role(self, user_id: str) -> Optional[str]:
        """
        Get user's role name

        Args:
            user_id: User identifier

        Returns:
            Role name or None
        """
        # Check cache
        if user_id in self._role_cache:
            role_id = self._role_cache[user_id]
            role = await self.db.get_role(role_id)
            return role["role_name"] if role else None

        # Query database
        user = await self.db.get_user(user_id)
        if not user:
            return None

        role_id = user.get("role_id")
        if role_id:
            self._role_cache[user_id] = role_id
            role = await self.db.get_role(role_id)
            return role["role_name"] if role else None

        return None

    async def get_user_permissions(self, user_id: str) -> List[str]:
        """
        Get all permissions for a user

        Args:
            user_id: User identifier

        Returns:
            List of permission names
        """
        user = await self.db.get_user(user_id)
        if not user or not user.get("role_id"):
            return []

        role_id = user["role_id"]
        permissions = await self.db.get_role_permissions(role_id)

        return [p["permission_name"] for p in permissions]

    # ========================================================================
    # Approval Workflow (Issue #16)
    # ========================================================================

    async def requires_approval(self, tool_name: str) -> bool:
        """
        Check if tool requires approval workflow

        Args:
            tool_name: MCP tool name

        Returns:
            True if approval required (HIGH/CRITICAL sensitivity), False otherwise
        """
        from settings import SecuritySettings

        # Check if approval workflow is enabled
        if not SecuritySettings.is_approval_enabled():
            return False

        # Query permission sensitivity level
        permission = await self.db.get_permission_by_name(tool_name)
        if not permission:
            return False

        # Require approval for HIGH and CRITICAL tools
        sensitivity_level = permission.get("sensitivity_level", "MEDIUM")
        return sensitivity_level in ["HIGH", "CRITICAL"]

    async def _wait_for_approval(
        self, user_id: str, tool_name: str, request_data: dict, timeout: int = 300
    ) -> bool:
        """
        Wait for approval from admin/approver

        Args:
            user_id: User requesting approval
            tool_name: Tool requiring approval
            request_data: Tool arguments (for audit trail)
            timeout: Timeout in seconds (default 300 = 5 minutes)

        Returns:
            True if approved, False if rejected/timeout
        """
        import uuid
        import json
        from settings import SecuritySettings

        # Get timeout from settings
        timeout = SecuritySettings.get_approval_timeout()

        # 1. Create approval request
        request_id = str(uuid.uuid4())
        role = await self.get_user_role(user_id) or "unknown"

        success = await self.db.create_approval_request(
            request_id=request_id,
            tool_name=tool_name,
            user_id=user_id,
            role=role,
            request_data=json.dumps(request_data),
            timeout_seconds=timeout,
        )

        if not success:
            logger.error(f"Failed to create approval request for {user_id}:{tool_name}")
            return False

        # Log approval request creation
        from audit_logger import get_audit_logger

        audit_logger = get_audit_logger()
        try:
            await audit_logger.log_approval_requested(
                user_id=user_id,
                tool_name=tool_name,
                request_id=request_id,
                request_data=request_data,
            )
        except Exception as e:
            logger.error(f"Failed to log approval request: {e}")

        # 2. Wait for approval with polling
        approval_event = asyncio.Event()
        poll_interval = SecuritySettings.get_approval_polling_interval()

        async def poll_approval():
            """Poll database for approval status"""
            while not approval_event.is_set():
                request = await self.db.get_approval_request(request_id)
                if not request:
                    logger.error(f"Approval request disappeared: {request_id}")
                    return "error"

                status = request["status"]
                if status in ["approved", "rejected", "expired", "timeout"]:
                    approval_event.set()
                    return status

                await asyncio.sleep(poll_interval)

        # 3. Wait with timeout
        try:
            logger.info(
                f"Waiting for approval: {request_id} ({tool_name}) - timeout={timeout}s"
            )
            status = await asyncio.wait_for(poll_approval(), timeout=timeout)

            if status == "approved":
                logger.info(f"Approval granted: {request_id}")
                return True
            else:
                logger.warning(f"Approval {status}: {request_id}")
                return False

        except asyncio.TimeoutError:
            # Mark as timeout in database
            await self.db.update_approval_status(
                request_id=request_id,
                status="timeout",
                responder_id="system",
                response_reason="Request timed out",
            )
            logger.warning(f"Approval request timed out: {request_id}")

            # Log timeout event
            try:
                await audit_logger.log_approval_timeout(
                    user_id=user_id,
                    tool_name=tool_name,
                    request_id=request_id,
                    timeout_seconds=timeout,
                )
            except Exception as e:
                logger.error(f"Failed to log approval timeout: {e}")

            return False

    async def invalidate_user_cache(self, user_id: str) -> None:
        """
        Invalidate cache for a specific user

        Args:
            user_id: User identifier
        """
        # Remove from role cache
        if user_id in self._role_cache:
            del self._role_cache[user_id]

        # Remove all permission cache entries for this user
        keys_to_remove = [
            k for k in self._permission_cache.keys() if k.startswith(f"{user_id}:")
        ]
        for key in keys_to_remove:
            del self._permission_cache[key]

        logger.info(f"Invalidated cache for user: {user_id}")

    async def invalidate_tool_cache(self, tool_name: str) -> None:
        """
        Invalidate cache for a specific tool

        Args:
            tool_name: MCP tool name
        """
        keys_to_remove = [
            k for k in self._permission_cache.keys() if k.endswith(f":{tool_name}")
        ]
        for key in keys_to_remove:
            del self._permission_cache[key]

        logger.info(f"Invalidated cache for tool: {tool_name}")

    async def invalidate_all_cache(self) -> None:
        """Invalidate entire cache"""
        self._permission_cache.clear()
        self._role_cache.clear()
        logger.info("Invalidated all RBAC cache")

    async def prewarm_cache(self, user_ids: Optional[List[str]] = None) -> None:
        """
        Prewarm cache for common users

        Args:
            user_ids: List of user IDs to prewarm (or None for all)
        """
        if not user_ids:
            # Get all active users
            async with self.db.get_connection() as conn:
                async with conn.execute(
                    "SELECT user_id FROM security_users WHERE is_active = 1"
                ) as cursor:
                    rows = await cursor.fetchall()
                    user_ids = [row[0] for row in rows]

        logger.info(f"Prewarming cache for {len(user_ids)} users...")

        for user_id in user_ids:
            # Get user role
            await self.get_user_role(user_id)

            # Get user permissions
            permissions = await self.get_user_permissions(user_id)

            # Cache common tool checks
            for perm in permissions:
                cache_key = f"{user_id}:{perm}"
                self._add_to_cache(cache_key, True, "Permission granted")

        logger.info(f"Cache prewarmed with {len(self._permission_cache)} entries")

    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            "permission_cache_size": len(self._permission_cache),
            "role_cache_size": len(self._role_cache),
            "cache_ttl_seconds": self.cache_ttl,
        }

    # Private methods

    def _get_from_cache(self, key: str) -> Optional[Dict]:
        """Get entry from cache if not expired"""
        if key not in self._permission_cache:
            return None

        entry = self._permission_cache[key]
        if time.time() - entry["cached_at"] > self.cache_ttl:
            # Expired
            del self._permission_cache[key]
            return None

        return entry

    def _add_to_cache(self, key: str, allowed: bool, reason: str) -> None:
        """Add entry to cache"""
        self._permission_cache[key] = {
            "allowed": allowed,
            "reason": reason,
            "cached_at": time.time(),
        }


# Singleton instance
_rbac_manager: Optional[RBACManager] = None


def get_rbac_manager() -> RBACManager:
    """Get singleton RBACManager instance"""
    global _rbac_manager
    if _rbac_manager is None:
        _rbac_manager = RBACManager()
    return _rbac_manager
