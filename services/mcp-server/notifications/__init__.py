"""
Notification module for Approval Workflow (Phase 6.4)

Provides email-based notifications for approval events:
- approval_requested: New approval request
- approval_timeout: Approval timeout
- approval_approved: Approval granted
- approval_rejected: Approval rejected
"""

from .queue import ApprovalEventQueue, ApprovalEventType, get_approval_event_queue
from .email import EmailNotifier, get_email_notifier

__all__ = [
    "ApprovalEventQueue",
    "ApprovalEventType",
    "get_approval_event_queue",
    "EmailNotifier",
    "get_email_notifier",
]
