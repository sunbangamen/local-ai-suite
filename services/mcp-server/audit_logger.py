#!/usr/bin/env python3
"""
Audit Logger
Asynchronous audit logging with queue for non-blocking performance
"""

import asyncio
import json
import logging
import time
from typing import Dict, Optional
from datetime import datetime

from security_database import get_security_database
from settings import SecuritySettings

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Asynchronous audit logger with queue

    Features:
    - Non-blocking async logging (<5ms)
    - Queue-based batch processing
    - Automatic queue overflow handling
    - Background writer task
    """

    def __init__(self, queue_size: Optional[int] = None):
        """
        Initialize audit logger

        Args:
            queue_size: Maximum queue size (default from settings)
        """
        self.queue_size = queue_size or SecuritySettings.SECURITY_QUEUE_SIZE
        self.queue = asyncio.Queue(maxsize=self.queue_size)
        self.db = get_security_database()
        self._writer_task = None
        self._running = False

    def start_async_writer(self) -> None:
        """Start background writer task"""
        if self._writer_task is not None:
            logger.warning("Async writer already running")
            return

        self._running = True
        self._writer_task = asyncio.create_task(self._async_writer())
        logger.info(f"Audit logger started (queue_size={self.queue_size})")

    async def stop_async_writer(self) -> None:
        """Stop background writer task"""
        self._running = False
        if self._writer_task:
            await self._writer_task
            self._writer_task = None
        logger.info("Audit logger stopped")

    async def log_tool_call(
        self,
        user_id: str,
        tool_name: str,
        action: str,
        status: str,
        error_message: Optional[str] = None,
        execution_time_ms: Optional[int] = None,
        request_data: Optional[Dict] = None,
    ) -> None:
        """
        Log tool invocation (non-blocking)

        Args:
            user_id: User identifier
            tool_name: MCP tool name
            action: Action performed
            status: Result status (success/denied/error/timeout)
            error_message: Error details if failed
            execution_time_ms: Execution duration
            request_data: Request parameters
        """
        log_entry = {
            "user_id": user_id,
            "tool_name": tool_name,
            "action": action,
            "status": status,
            "error_message": error_message,
            "execution_time_ms": execution_time_ms,
            "request_data": json.dumps(request_data) if request_data else None,
            "timestamp": datetime.now().isoformat(),
        }

        try:
            # Non-blocking put (immediate return)
            self.queue.put_nowait(log_entry)
        except asyncio.QueueFull:
            # Queue full - log warning and drop entry
            logger.warning(
                f"Audit log queue full ({self.queue_size}), dropping entry: "
                f"user={user_id}, tool={tool_name}"
            )

    async def log_denied(self, user_id: str, tool_name: str, reason: str) -> None:
        """
        Log permission denied event

        Args:
            user_id: User identifier
            tool_name: MCP tool name
            reason: Denial reason
        """
        await self.log_tool_call(
            user_id=user_id,
            tool_name=tool_name,
            action="access",
            status="denied",
            error_message=reason,
        )

    async def log_success(
        self,
        user_id: str,
        tool_name: str,
        execution_time_ms: int,
        request_data: Optional[Dict] = None,
    ) -> None:
        """
        Log successful tool execution

        Args:
            user_id: User identifier
            tool_name: MCP tool name
            execution_time_ms: Execution duration
            request_data: Request parameters
        """
        await self.log_tool_call(
            user_id=user_id,
            tool_name=tool_name,
            action="execute",
            status="success",
            execution_time_ms=execution_time_ms,
            request_data=request_data,
        )

    async def log_error(
        self,
        user_id: str,
        tool_name: str,
        error_message: str,
        execution_time_ms: Optional[int] = None,
    ) -> None:
        """
        Log tool execution error

        Args:
            user_id: User identifier
            tool_name: MCP tool name
            error_message: Error details
            execution_time_ms: Execution duration
        """
        await self.log_tool_call(
            user_id=user_id,
            tool_name=tool_name,
            action="execute",
            status="error",
            error_message=error_message,
            execution_time_ms=execution_time_ms,
        )

    # Approval Workflow Logging Methods (Issue #16)

    async def log_approval_requested(
        self,
        user_id: str,
        tool_name: str,
        request_id: str,
        request_data: Optional[Dict] = None,
    ) -> None:
        """
        Log approval request creation

        Args:
            user_id: User requesting approval
            tool_name: MCP tool name
            request_id: Approval request ID
            request_data: Request parameters
        """
        await self.log_tool_call(
            user_id=user_id,
            tool_name=tool_name,
            action="approval_requested",
            status="pending",
            request_data={"request_id": request_id, **(request_data or {})},
        )

    async def log_approval_granted(
        self,
        user_id: str,
        tool_name: str,
        request_id: str,
        responder_id: str,
        reason: Optional[str] = None,
    ) -> None:
        """
        Log approval granted event

        Args:
            user_id: User who made the request
            tool_name: MCP tool name
            request_id: Approval request ID
            responder_id: Admin who approved
            reason: Approval reason
        """
        await self.log_tool_call(
            user_id=user_id,
            tool_name=tool_name,
            action="approval_granted",
            status="approved",
            request_data={
                "request_id": request_id,
                "responder_id": responder_id,
                "reason": reason,
            },
        )

    async def log_approval_rejected(
        self,
        user_id: str,
        tool_name: str,
        request_id: str,
        responder_id: str,
        reason: Optional[str] = None,
    ) -> None:
        """
        Log approval rejected event

        Args:
            user_id: User who made the request
            tool_name: MCP tool name
            request_id: Approval request ID
            responder_id: Admin who rejected
            reason: Rejection reason
        """
        await self.log_tool_call(
            user_id=user_id,
            tool_name=tool_name,
            action="approval_rejected",
            status="rejected",
            error_message=reason,
            request_data={"request_id": request_id, "responder_id": responder_id},
        )

    async def log_approval_timeout(
        self, user_id: str, tool_name: str, request_id: str, timeout_seconds: int
    ) -> None:
        """
        Log approval timeout event

        Args:
            user_id: User who made the request
            tool_name: MCP tool name
            request_id: Approval request ID
            timeout_seconds: Timeout duration
        """
        await self.log_tool_call(
            user_id=user_id,
            tool_name=tool_name,
            action="approval_timeout",
            status="timeout",
            error_message=f"Approval request timed out after {timeout_seconds}s",
            request_data={"request_id": request_id},
        )

    async def _async_writer(self) -> None:
        """Background task for writing audit logs to database"""
        logger.info("Audit logger writer task started")

        while self._running or not self.queue.empty():
            try:
                # Get log entry from queue (with timeout)
                log_entry = await asyncio.wait_for(self.queue.get(), timeout=1.0)

                # Write to database
                await self.db.insert_audit_log(
                    user_id=log_entry["user_id"],
                    tool_name=log_entry["tool_name"],
                    action=log_entry["action"],
                    status=log_entry["status"],
                    error_message=log_entry.get("error_message"),
                    execution_time_ms=log_entry.get("execution_time_ms"),
                    request_data=log_entry.get("request_data"),
                )

                self.queue.task_done()

            except asyncio.TimeoutError:
                # No entries in queue, continue
                continue
            except Exception as e:
                logger.error(f"Error writing audit log: {e}")

        logger.info("Audit logger writer task stopped")

    def get_queue_stats(self) -> Dict:
        """Get queue statistics"""
        return {
            "queue_size": self.queue.qsize(),
            "queue_max_size": self.queue_size,
            "queue_full": self.queue.full(),
            "running": self._running,
        }


# Singleton instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get singleton AuditLogger instance"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
