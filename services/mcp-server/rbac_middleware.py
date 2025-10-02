#!/usr/bin/env python3
"""
RBAC Middleware
FastAPI middleware for automatic permission checking
"""

import json
import logging
import time
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from rbac_manager import get_rbac_manager
from audit_logger import get_audit_logger
from settings import SecuritySettings

logger = logging.getLogger(__name__)


class RBACMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for RBAC permission checking

    Features:
    - Automatic permission checking for /tools/* endpoints
    - User identification from headers
    - Audit logging integration
    - HTTP 403 responses for denied requests
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.rbac_manager = get_rbac_manager()
        self.audit_logger = get_audit_logger()

    async def dispatch(self, request: Request, call_next):
        """Process request with RBAC checking"""

        # Skip RBAC if disabled
        if not SecuritySettings.is_rbac_enabled():
            return await call_next(request)

        # Only check /tools/* endpoints
        if not request.url.path.startswith("/tools/"):
            return await call_next(request)

        # Extract user_id from header (default to "default" if not provided)
        user_id = request.headers.get("X-User-ID", "default")

        # Extract tool_name from URL path
        # Format: /tools/{tool_name}/call or /tools/{tool_name}
        path_parts = request.url.path.split("/")
        if len(path_parts) < 3:
            # Invalid path, let it pass to normal handler
            return await call_next(request)

        tool_name = path_parts[2]

        # Check RBAC permission
        start_time = time.time()
        allowed, reason = await self.rbac_manager.check_permission(user_id, tool_name)
        check_time = (time.time() - start_time) * 1000  # Convert to ms

        logger.debug(
            f"RBAC check: user={user_id}, tool={tool_name}, "
            f"allowed={allowed}, time={check_time:.2f}ms"
        )

        # TODO: Approval workflow not implemented yet
        # If allowed and require_approval=True, should wait for approval here
        # Example:
        #   if allowed and await self.rbac_manager.requires_approval(tool_name):
        #       approval_status = await self._wait_for_approval(user_id, tool_name)
        #       if not approval_status:
        #           return JSONResponse(status_code=403, content={"error": "Approval denied"})

        if not allowed:
            # Permission denied - log and return 403
            logger.warning(
                f"Permission denied: user={user_id}, tool={tool_name}, reason={reason}"
            )

            # Audit logging (non-blocking)
            try:
                await self.audit_logger.log_denied(user_id, tool_name, reason)
            except Exception as e:
                logger.error(f"Failed to log denied access: {e}")

            return JSONResponse(
                status_code=403,
                content={
                    "error": "Permission denied",
                    "detail": reason,
                    "user_id": user_id,
                    "tool_name": tool_name
                }
            )

        # Permission granted - continue to handler
        request_start = time.time()
        response = await call_next(request)
        execution_time_ms = int((time.time() - request_start) * 1000)

        # Log successful access (non-blocking)
        try:
            await self.audit_logger.log_success(
                user_id=user_id,
                tool_name=tool_name,
                execution_time_ms=execution_time_ms
            )
        except Exception as e:
            logger.error(f"Failed to log successful access: {e}")

        return response
