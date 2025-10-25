#!/usr/bin/env python3
"""
API Key authentication for Approval Workflow API (Issue #45 Phase 6.3)

Features:
- Simple API Key based authentication
- RBAC integration for permission checking
- Audit logging of API access
"""

import logging

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


class APIKeyAuth:
    """API Key authentication handler for approval API endpoints"""

    # Default API key (should be overridden by environment variable or config)
    # Format: {key_id}:{secret}
    VALID_KEYS = {
        "approval-admin-001": {
            "roles": ["admin"],
            "description": "Default admin API key",
            "created_at": "2025-10-25",
        }
    }

    @classmethod
    def authenticate(cls, api_key: str) -> dict:
        """
        Authenticate API key and return user information

        Args:
            api_key: API key from X-API-Key header

        Returns:
            dict with user_id, roles, and permissions

        Raises:
            HTTPException: 401 if invalid key, 403 if insufficient permissions
        """
        if not api_key:
            raise HTTPException(status_code=401, detail="Missing X-API-Key header")

        # Verify key exists and is valid
        if api_key not in cls.VALID_KEYS:
            logger.warning(f"Invalid API key attempt: {api_key[:10]}***")
            raise HTTPException(
                status_code=401,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "ApiKey"},
            )

        key_info = cls.VALID_KEYS[api_key]

        # Return authenticated user info
        return {
            "user_id": f"api-{api_key.split('-')[1]}",  # Extract key type
            "api_key_id": api_key,
            "roles": key_info["roles"],
            "is_api_caller": True,
            "permissions": cls._get_permissions_for_roles(key_info["roles"]),
        }

    @classmethod
    def _get_permissions_for_roles(cls, roles: list) -> list:
        """Get permissions based on roles"""
        role_permissions = {
            "admin": [
                "approval:view",
                "approval:create",
                "approval:approve",
                "approval:reject",
                "approval:cancel",
            ],
            "operator": [
                "approval:view",
                "approval:approve",
                "approval:reject",
            ],
            "viewer": [
                "approval:view",
            ],
        }

        permissions = set()
        for role in roles:
            permissions.update(role_permissions.get(role, []))

        return list(permissions)

    @classmethod
    def check_permission(cls, user: dict, required_permission: str) -> None:
        """
        Check if user has required permission

        Args:
            user: User dict from authenticate()
            required_permission: Permission name (e.g., "approval:approve")

        Raises:
            HTTPException: 403 if permission denied
        """
        if required_permission not in user.get("permissions", []):
            logger.warning(
                f"Permission denied for {user.get('user_id')}: " f"{required_permission}"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: {required_permission}",
            )


async def get_authenticated_user(request: Request) -> dict:
    """
    FastAPI dependency for getting authenticated user from API key

    Usage:
        @app.get("/api/v1/approvals")
        async def list_approvals(user: dict = Depends(get_authenticated_user)):
            ...
    """
    api_key = request.headers.get("X-API-Key")
    user = APIKeyAuth.authenticate(api_key)

    # Audit log API access
    logger.info(
        f"API request: user={user['user_id']}, " f"path={request.url.path}, method={request.method}"
    )

    return user


def require_permission(permission: str):
    """
    FastAPI dependency for checking specific permission

    Usage:
        @app.post("/api/v1/approvals/{id}/approve")
        async def approve(
            request_id: str,
            user: dict = Depends(require_permission("approval:approve"))
        ):
            ...
    """

    async def check_permission(user: dict = Depends(get_authenticated_user)) -> dict:
        APIKeyAuth.check_permission(user, permission)
        return user

    return check_permission
