#!/usr/bin/env python3
"""
RBAC Manager
Role-Based Access Control permission checking with caching
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

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

    async def check_permission(
        self,
        user_id: str,
        tool_name: str
    ) -> Tuple[bool, str]:
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

    # TODO: Approval workflow methods not implemented yet
    async def requires_approval(self, tool_name: str) -> bool:
        """
        Check if tool requires approval workflow

        NOTE: This is a placeholder. Actual implementation needed.
        Should query tool_permissions or access_control to check require_approval flag.

        Args:
            tool_name: MCP tool name

        Returns:
            True if approval required, False otherwise
        """
        # Placeholder - always returns False until implemented
        return False

    async def _wait_for_approval(self, user_id: str, tool_name: str) -> bool:
        """
        Wait for approval from admin/approver

        NOTE: This is a placeholder. Actual implementation needed.
        Should implement approval request queue, notification, and response handling.

        Args:
            user_id: User requesting approval
            tool_name: Tool requiring approval

        Returns:
            True if approved, False if denied
        """
        # Placeholder - always returns False until implemented
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
        keys_to_remove = [k for k in self._permission_cache.keys() if k.startswith(f"{user_id}:")]
        for key in keys_to_remove:
            del self._permission_cache[key]

        logger.info(f"Invalidated cache for user: {user_id}")

    async def invalidate_tool_cache(self, tool_name: str) -> None:
        """
        Invalidate cache for a specific tool

        Args:
            tool_name: MCP tool name
        """
        keys_to_remove = [k for k in self._permission_cache.keys() if k.endswith(f":{tool_name}")]
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
            "cache_ttl_seconds": self.cache_ttl
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
            "cached_at": time.time()
        }


# Singleton instance
_rbac_manager: Optional[RBACManager] = None


def get_rbac_manager() -> RBACManager:
    """Get singleton RBACManager instance"""
    global _rbac_manager
    if _rbac_manager is None:
        _rbac_manager = RBACManager()
    return _rbac_manager
