#!/usr/bin/env python3
"""
Approval Workflow REST API v1 (Issue #45 Phase 6.3)

Endpoints:
- GET /api/v1/approvals - List approval requests
- POST /api/v1/approvals - Create approval request
- GET /api/v1/approvals/{id} - Get approval request details
- PUT /api/v1/approvals/{id} - Approve or reject request
- DELETE /api/v1/approvals/{id} - Cancel approval request
- GET /api/v1/approvals/stats - Get approval statistics
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Header
from typing import Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# This will be imported into app.py
router = APIRouter(prefix="/api/v1", tags=["approvals_v1"])


# API Key authentication dependency
def get_api_key(x_api_key: str = Header(...)) -> str:
    """
    Extract and validate API Key from X-API-Key header

    Raises HTTPException 401 if missing or invalid
    """
    from api.auth import APIKeyAuth

    try:
        user = APIKeyAuth.authenticate(x_api_key)
        return user["api_key_id"]
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid API key")


# ============================================================================
# GET /api/v1/approvals - List approval requests
# ============================================================================


@router.get("/approvals")
async def list_approvals(
    status: Optional[str] = Query(None, description="Filter by status"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    tool_name: Optional[str] = Query(None, description="Filter by tool name"),
    limit: int = Query(50, ge=1, le=1000, description="Max results"),
    offset: int = Query(0, ge=0, description="Results offset"),
    api_key_id: str = Depends(get_api_key),
):
    """
    List approval requests with optional filtering.

    Requires: approval:view permission (API Key auth required)
    """
    from api.auth import APIKeyAuth
    from security_database import get_security_database

    # Verify permission
    APIKeyAuth.check_permission(
        {"api_key_id": api_key_id, "permissions": ["approval:view"]},
        "approval:view",
    )

    # Query database with full listing
    db = get_security_database()
    approvals, total = await db.list_all_approvals(
        status=status, user_id=user_id, tool_name=tool_name, limit=limit, offset=offset
    )

    return {
        "approvals": approvals,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ============================================================================
# POST /api/v1/approvals - Create approval request
# ============================================================================


@router.post("/approvals", status_code=201)
async def create_approval(
    body: dict = Body(...),
    api_key_id: str = Depends(get_api_key),
):
    """
    Create approval request manually.

    Requires: approval:create permission (API Key auth required)
    """
    from api.auth import APIKeyAuth
    from security_database import get_security_database
    import uuid

    # Verify permission
    APIKeyAuth.check_permission(
        {"api_key_id": api_key_id, "permissions": ["approval:create"]},
        "approval:create",
    )

    # Validate input
    tool_name = body.get("tool_name")
    if not tool_name:
        raise HTTPException(status_code=400, detail="tool_name is required")

    user_id = body.get("user_id", "system")
    request_context = body.get("request_context", {})

    # Create request
    db = get_security_database()
    request_id = str(uuid.uuid4())
    expires_at = datetime.now() + timedelta(minutes=5)

    # Insert into database
    await db.create_approval_request(
        request_id=request_id,
        user_id=user_id,
        tool_name=tool_name,
        request_context=request_context,
        expires_at=expires_at.isoformat(),
    )

    return {
        "request_id": request_id,
        "status": "pending",
        "expires_in_seconds": 300,
    }


# ============================================================================
# GET /api/v1/approvals/{request_id} - Get details
# ============================================================================


@router.get("/approvals/{request_id}")
async def get_approval(
    request_id: str,
    api_key_id: str = Depends(get_api_key),
):
    """
    Get approval request details.

    Supports both full UUID and short ID (first 8 chars).

    Requires: approval:view permission (API Key auth required)
    """
    from api.auth import APIKeyAuth
    from security_database import get_security_database

    # Verify permission
    APIKeyAuth.check_permission(
        {"api_key_id": api_key_id, "permissions": ["approval:view"]},
        "approval:view",
    )

    # Query database
    db = get_security_database()
    approval = await db.get_approval_request(request_id)

    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")

    return approval


# ============================================================================
# PUT /api/v1/approvals/{request_id} - Approve or reject
# ============================================================================


@router.put("/approvals/{request_id}")
async def respond_approval(
    request_id: str,
    body: dict = Body(...),
    api_key_id: str = Depends(get_api_key),
):
    """
    Process approval request (approve or reject).

    Requires: approval:approve permission (API Key auth required)
    """
    from api.auth import APIKeyAuth
    from security_database import get_security_database
    from audit_logger import get_audit_logger

    # Verify permission
    APIKeyAuth.check_permission(
        {"api_key_id": api_key_id, "permissions": ["approval:approve"]},
        "approval:approve",
    )

    # Validate input
    action = body.get("action")
    reason = body.get("reason", "")

    if action not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")

    # Get request
    db = get_security_database()
    approval = await db.get_approval_request(request_id)

    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")

    if approval.get("status") != "pending":
        raise HTTPException(status_code=409, detail="Request already processed or expired")

    # Process
    status = "approved" if action == "approve" else "rejected"
    success = await db.update_approval_status(
        request_id=request_id,
        status=status,
        responder_id=f"api-{api_key_id.split('-')[1] if '-' in api_key_id else 'caller'}",
        response_reason=reason,
    )

    if not success:
        raise HTTPException(status_code=409, detail="Failed to process request")

    # Audit log
    audit = get_audit_logger()
    if status == "approved":
        await audit.log_approval_granted(
            user_id=approval["user_id"],
            tool_name=approval["tool_name"],
            request_id=request_id,
            responder_id=f"api-{api_key_id.split('-')[1] if '-' in api_key_id else 'caller'}",
            reason=reason,
        )
    else:
        await audit.log_approval_rejected(
            user_id=approval["user_id"],
            tool_name=approval["tool_name"],
            request_id=request_id,
            responder_id=f"api-{api_key_id.split('-')[1] if '-' in api_key_id else 'caller'}",
            reason=reason,
        )

    # Record metrics
    from app import approval_requests_total
    approval_requests_total.labels(status=status).inc()

    return {
        "status": status,
        "request_id": request_id,
        "responder": api_key_id,
    }


# ============================================================================
# DELETE /api/v1/approvals/{request_id} - Cancel request
# ============================================================================


@router.delete("/approvals/{request_id}", status_code=204)
async def cancel_approval(
    request_id: str,
    api_key_id: str = Depends(get_api_key),
):
    """
    Cancel pending approval request.

    Requires: approval:cancel permission (API Key auth required)
    """
    from api.auth import APIKeyAuth
    from security_database import get_security_database

    # Verify permission
    APIKeyAuth.check_permission(
        {"api_key_id": api_key_id, "permissions": ["approval:cancel"]},
        "approval:cancel",
    )

    # Get request
    db = get_security_database()
    approval = await db.get_approval_request(request_id)

    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")

    if approval.get("status") != "pending":
        raise HTTPException(status_code=409, detail="Only pending requests can be cancelled")

    # Cancel
    success = await db.update_approval_status(
        request_id=request_id,
        status="cancelled",
        responder_id=f"api-{api_key_id.split('-')[1] if '-' in api_key_id else 'caller'}",
        response_reason="Cancelled via API",
    )

    if not success:
        raise HTTPException(status_code=409, detail="Failed to cancel request")

    return None


# ============================================================================
# GET /api/v1/approvals/stats - Get statistics
# ============================================================================


@router.get("/approvals/stats")
async def get_approval_stats(
    time_range: str = Query("24h", description="Time range for stats"),
    api_key_id: str = Depends(get_api_key),
):
    """
    Get approval statistics.

    Requires: approval:view permission (API Key auth required)
    """
    from api.auth import APIKeyAuth
    from security_database import get_security_database

    # Verify permission
    APIKeyAuth.check_permission(
        {"api_key_id": api_key_id, "permissions": ["approval:view"]},
        "approval:view",
    )

    # Query database - use list_all_approvals to get all records
    db = get_security_database()
    approvals, total = await db.list_all_approvals(limit=10000)

    # Calculate stats
    pending = len([a for a in approvals if a.get("status") == "pending"])
    approved = len([a for a in approvals if a.get("status") == "approved"])
    rejected = len([a for a in approvals if a.get("status") == "rejected"])
    expired = len([a for a in approvals if a.get("status") == "expired"])

    # Approval rate (approved / (approved + rejected))
    approvals_finished = approved + rejected
    approval_rate = approved / approvals_finished if approvals_finished > 0 else 0

    # Average response time
    response_times = []
    for a in approvals:
        if a.get("responded_at"):
            try:
                requested = datetime.fromisoformat(a.get("requested_at", ""))
                responded = datetime.fromisoformat(a.get("responded_at", ""))
                response_times.append((responded - requested).total_seconds())
            except Exception:
                pass

    avg_response_time = sum(response_times) / len(response_times) if response_times else 0

    return {
        "total_requests": total,
        "pending_count": pending,
        "approved_count": approved,
        "rejected_count": rejected,
        "expired_count": expired,
        "approval_rate": round(approval_rate, 4),
        "avg_response_time_seconds": round(avg_response_time, 2),
    }
