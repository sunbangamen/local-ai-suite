#!/usr/bin/env python3
"""
RBAC Middleware
FastAPI middleware for automatic permission checking
"""

import json
import logging
import time

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from audit_logger import get_audit_logger
from rbac_manager import get_rbac_manager
from settings import SecuritySettings

logger = logging.getLogger(__name__)

# Prometheus metrics (imported from app.py)
# NOTE: These are initialized in app.py and accessed here to avoid circular imports
try:
    from prometheus_client import Counter
    rbac_permission_checks_total = None  # Will be set via set_metrics()
except ImportError:
    rbac_permission_checks_total = None


def set_rbac_metrics(checks_counter):
    """Set RBAC metrics from app.py (called during app initialization)"""
    global rbac_permission_checks_total
    rbac_permission_checks_total = checks_counter


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

        # Prometheus 메트릭 기록 (Issue #45 Phase 6.2)
        if rbac_permission_checks_total is not None:
            result = "allowed" if allowed else "denied"
            rbac_permission_checks_total.labels(result=result).inc()

        # Approval workflow integration (Issue #16)
        if allowed and await self.rbac_manager.requires_approval(tool_name):
            logger.info(f"Tool {tool_name} requires approval for user {user_id}")

            # Extract request data for approval context
            request_data = {}
            body_bytes = b""
            try:
                if request.method == "POST":
                    body_bytes = await request.body()
                    if body_bytes:
                        request_data = json.loads(body_bytes.decode())

                        # Restore body for downstream handlers
                        async def receive():
                            return {"type": "http.request", "body": body_bytes}

                        request._receive = receive
            except Exception as e:
                logger.warning(f"Failed to extract request body: {e}")

            # Wait for approval
            approval_granted, approval_context = await self.rbac_manager._wait_for_approval(
                user_id=user_id,
                tool_name=tool_name,
                request_data=request_data,
                timeout=SecuritySettings.get_approval_timeout(),
            )

            if not approval_granted:
                # Approval denied or timed out
                logger.warning(f"Approval denied/timeout: user={user_id}, tool={tool_name}")

                # Audit logging
                try:
                    await self.audit_logger.log_denied(
                        user_id, tool_name, "Approval denied or timed out"
                    )
                except Exception as e:
                    logger.error(f"Failed to log approval denial: {e}")

                request_id = approval_context.get("request_id")
                expires_at = approval_context.get("expires_at")
                status = approval_context.get("status")

                if approval_context.get("reason") == "create_failed":
                    logger.error(
                        "Approval workflow unavailable (failed to create request): "
                        f"user={user_id}, tool={tool_name}"
                    )
                    return JSONResponse(
                        status_code=503,
                        content={
                            "error": "Approval workflow unavailable",
                            "detail": "Failed to create approval request. Please try again later.",
                            "user_id": user_id,
                            "tool_name": tool_name,
                        },
                    )

                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "Approval required",
                        "detail": "Request requires administrator approval but was denied or timed out",
                        "user_id": user_id,
                        "tool_name": tool_name,
                        "approval_required": True,
                        "request_id": request_id,
                        "expires_at": expires_at,
                        "status": status,
                    },
                )

            logger.info(f"Approval granted: user={user_id}, tool={tool_name}")

        if not allowed:
            # Permission denied - log and return 403
            logger.warning(f"Permission denied: user={user_id}, tool={tool_name}, reason={reason}")

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
                    "tool_name": tool_name,
                },
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
                execution_time_ms=execution_time_ms,
            )
        except Exception as e:
            logger.error(f"Failed to log successful access: {e}")

        return response
