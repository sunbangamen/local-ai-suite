#!/usr/bin/env python3
"""
Approval Workflow Admin CLI (Issue #45 Phase 6.3)

로컬 승인 요청 관리를 위한 CLI 도구입니다.

사용법:
    python approval_admin.py list [--status pending]
    python approval_admin.py approve <request_id> --reason "..."
    python approval_admin.py reject <request_id> --reason "..."
"""

import asyncio
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add services to path
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "mcp-server"))


async def cmd_list(status: Optional[str] = None, limit: int = 50):
    """List pending approval requests"""
    from security_database import get_security_database
    from settings import get_security_settings

    # Initialize
    settings = get_security_settings()
    if not settings.is_rbac_enabled():
        print("❌ RBAC not enabled. Set RBAC_ENABLED=true")
        return False

    await settings.init_database()

    # Query
    db = get_security_database()
    approvals = await db.list_pending_approvals(limit)

    if not approvals:
        print("✅ No pending approvals")
        return True

    # Filter by status
    if status:
        approvals = [a for a in approvals if a.get("status") == status]

    if not approvals:
        print(f"✅ No approvals with status: {status}")
        return True

    # Display
    print(f"\n{'Request ID':<40} {'User':<12} {'Tool':<15} {'Status':<10} {'Created':<20}")
    print("=" * 100)

    for approval in approvals[:limit]:
        request_id = approval.get("request_id", "")[:8]  # Short ID
        user_id = approval.get("user_id", "")[:10]
        tool_name = approval.get("tool_name", "")[:13]
        status_str = approval.get("status", "")[:8]
        requested_at = approval.get("requested_at", "")[:19]

        print(
            f"{request_id:<40} {user_id:<12} {tool_name:<15} {status_str:<10} {requested_at:<20}"
        )

    print(f"\nTotal: {len(approvals)} requests")
    return True


async def cmd_approve(request_id: str, reason: str):
    """Approve a request"""
    from security_database import get_security_database
    from audit_logger import get_audit_logger
    from settings import get_security_settings

    # Initialize
    settings = get_security_settings()
    if not settings.is_rbac_enabled():
        print("❌ RBAC not enabled")
        return False

    await settings.init_database()

    # Get request
    db = get_security_database()
    approval = await db.get_approval_request(request_id)

    if not approval:
        print(f"❌ Request not found: {request_id}")
        return False

    if approval.get("status") != "pending":
        print(f"❌ Request not pending: {approval.get('status')}")
        return False

    # Update status
    success = await db.update_approval_status(
        request_id=request_id,
        status="approved",
        responder_id="admin",
        response_reason=reason,
    )

    if not success:
        print(f"❌ Failed to approve: {request_id}")
        return False

    # Audit log
    audit = get_audit_logger()
    await audit.log_approval_granted(
        user_id=approval["user_id"],
        tool_name=approval["tool_name"],
        request_id=request_id,
        responder_id="admin",
        reason=reason,
    )

    print(f"✅ Approved: {request_id}")
    print(f"   Tool: {approval['tool_name']}")
    print(f"   User: {approval['user_id']}")
    print(f"   Reason: {reason}")

    return True


async def cmd_reject(request_id: str, reason: str):
    """Reject a request"""
    from security_database import get_security_database
    from audit_logger import get_audit_logger
    from settings import get_security_settings

    # Initialize
    settings = get_security_settings()
    if not settings.is_rbac_enabled():
        print("❌ RBAC not enabled")
        return False

    await settings.init_database()

    # Get request
    db = get_security_database()
    approval = await db.get_approval_request(request_id)

    if not approval:
        print(f"❌ Request not found: {request_id}")
        return False

    if approval.get("status") != "pending":
        print(f"❌ Request not pending: {approval.get('status')}")
        return False

    # Update status
    success = await db.update_approval_status(
        request_id=request_id,
        status="rejected",
        responder_id="admin",
        response_reason=reason,
    )

    if not success:
        print(f"❌ Failed to reject: {request_id}")
        return False

    # Audit log
    audit = get_audit_logger()
    await audit.log_approval_rejected(
        user_id=approval["user_id"],
        tool_name=approval["tool_name"],
        request_id=request_id,
        responder_id="admin",
        reason=reason,
    )

    print(f"✅ Rejected: {request_id}")
    print(f"   Tool: {approval['tool_name']}")
    print(f"   User: {approval['user_id']}")
    print(f"   Reason: {reason}")

    return True


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Approval Workflow Admin CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python approval_admin.py list
  python approval_admin.py list --status pending
  python approval_admin.py approve 550e8400 --reason "Approved"
  python approval_admin.py reject abc12345 --reason "Policy violation"
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # List command
    list_cmd = subparsers.add_parser("list", help="List approval requests")
    list_cmd.add_argument(
        "--status",
        choices=["pending", "approved", "rejected", "expired"],
        help="Filter by status",
    )
    list_cmd.add_argument(
        "--limit", type=int, default=50, help="Max results (default: 50)"
    )

    # Approve command
    approve_cmd = subparsers.add_parser("approve", help="Approve a request")
    approve_cmd.add_argument("request_id", help="Request ID (UUID or short ID)")
    approve_cmd.add_argument(
        "--reason", required=True, help="Approval reason/comment"
    )

    # Reject command
    reject_cmd = subparsers.add_parser("reject", help="Reject a request")
    reject_cmd.add_argument("request_id", help="Request ID (UUID or short ID)")
    reject_cmd.add_argument("--reason", required=True, help="Rejection reason/comment")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Execute command
    try:
        if args.command == "list":
            success = asyncio.run(cmd_list(status=args.status, limit=args.limit))
        elif args.command == "approve":
            success = asyncio.run(cmd_approve(args.request_id, args.reason))
        elif args.command == "reject":
            success = asyncio.run(cmd_reject(args.request_id, args.reason))
        else:
            parser.print_help()
            return 1

        return 0 if success else 1

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
