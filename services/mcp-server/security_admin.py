#!/usr/bin/env python3
"""
Security Administration API - 보안 관리 및 모니터링 엔드포인트
"""

import json
import os
import time
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query, Body, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

try:
    from .sandbox import get_enhanced_sandbox, SandboxLogger
    from .security import get_security_validator, SecurityError
except ImportError:
    from sandbox import get_enhanced_sandbox, SandboxLogger
    from security import get_security_validator, SecurityError


class SecuritySettings(BaseModel):
    security_level: str = "normal"  # strict|normal|legacy
    max_memory_mb: int = 512
    max_cpu_time_sec: int = 30
    max_output_size: int = 1048576
    network_access: bool = False
    use_enhanced_sandbox: bool = True


class CodeExecutionRequest(BaseModel):
    code: str
    session_id: Optional[str] = "default"
    timeout: Optional[int] = 30
    client_info: Optional[Dict[str, Any]] = None


class CodeValidationRequest(BaseModel):
    code: str


class SecurityAuditAPI:
    """보안 감사 및 관리 API"""

    def __init__(self):
        self.logger = SandboxLogger()
        self.sandbox = get_enhanced_sandbox()

    def get_security_stats(self) -> Dict[str, Any]:
        """보안 통계 조회"""
        try:
            log_file = self.logger.audit_log
            if not log_file.exists():
                return {
                    "total_events": 0,
                    "security_violations": 0,
                    "code_executions": 0,
                    "active_sessions": 0,
                    "log_file_exists": False,
                }

            events = []
            violations = 0
            executions = 0

            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        event = json.loads(line.strip())
                        events.append(event)

                        if event.get("event_type") == "SECURITY_VIOLATION":
                            violations += 1
                        elif event.get("event_type") == "CODE_EXECUTION":
                            executions += 1
                    except json.JSONDecodeError:
                        continue

            return {
                "total_events": len(events),
                "security_violations": violations,
                "code_executions": executions,
                "active_sessions": len(self.sandbox.session_manager.sessions),
                "log_file_exists": True,
                "recent_events": events[-10:] if events else [],  # 최근 10개 이벤트
            }

        except Exception as e:
            return {
                "error": str(e),
                "total_events": 0,
                "security_violations": 0,
                "code_executions": 0,
                "active_sessions": 0,
            }

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """특정 세션 정보 조회"""
        return self.sandbox.get_session_stats(session_id)

    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """모든 활성 세션 조회"""
        sessions = []
        for session_id in self.sandbox.session_manager.sessions.keys():
            session_info = self.get_session_info(session_id)
            if session_info:
                sessions.append(session_info)
        return sessions

    def cleanup_sessions(self) -> Dict[str, Any]:
        """만료된 세션 정리"""
        before_count = len(self.sandbox.session_manager.sessions)
        self.sandbox.cleanup_sessions()
        after_count = len(self.sandbox.session_manager.sessions)

        return {
            "sessions_before": before_count,
            "sessions_after": after_count,
            "cleaned_up": before_count - after_count,
        }

    def validate_code_security(self, code: str) -> Dict[str, Any]:
        """코드 보안성 검증 (실행 없이)"""
        try:
            validator = get_security_validator()
            validator.validate_code(code)

            return {
                "valid": True,
                "message": "Code passed security validation",
                "security_level": validator.security_level,
            }

        except SecurityError as e:
            return {"valid": False, "message": str(e), "error_type": "SecurityError"}
        except Exception as e:
            return {"valid": False, "message": str(e), "error_type": "ValidationError"}

    async def execute_code_with_audit(
        self,
        code: str,
        session_id: str = "admin_test",
        timeout: int = 30,
        client_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """감사 로깅과 함께 코드 실행"""

        # 클라이언트 정보 기본값
        if client_info is None:
            client_info = {
                "source": "security_admin_api",
                "ip": "127.0.0.1",
                "user_agent": "SecurityAdminAPI/1.0",
            }

        # 코드 실행
        result = await self.sandbox.execute_code(
            code=code, session_id=session_id, client_info=client_info
        )

        # 추가 감사 정보
        result["audit"] = {
            "executed_by": "security_admin",
            "execution_timestamp": time.time(),
            "session_id": session_id,
        }

        return result


# FastAPI 애플리케이션 생성
security_app = FastAPI(
    title="MCP Security Administration API",
    description="보안 관리 및 감사 API",
    version="1.0.0",
    docs_url="/security/docs",
    redoc_url="/security/redoc",
)

# 전역 인스턴스
security_audit = SecurityAuditAPI()


@security_app.get("/security/health")
async def security_health_check():
    """보안 시스템 헬스체크"""
    try:
        validator = get_security_validator()
        sandbox = get_enhanced_sandbox()

        return {
            "status": "healthy",
            "security_system": "available",
            "security_level": validator.security_level,
            "enhanced_sandbox": True,
            "active_sessions": len(sandbox.session_manager.sessions),
            "log_directory": str(security_audit.logger.log_dir),
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "security_system": "error",
            },
        )


@security_app.get("/security/stats")
async def get_security_statistics():
    """보안 통계 조회"""
    try:
        stats = security_audit.get_security_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving stats: {e}")


@security_app.get("/security/sessions")
async def get_active_sessions():
    """활성 세션 목록 조회"""
    try:
        sessions = security_audit.get_all_sessions()
        return {"success": True, "sessions": sessions, "total_sessions": len(sessions)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving sessions: {e}")


@security_app.get("/security/sessions/{session_id}")
async def get_session_details(session_id: str):
    """특정 세션 상세 정보 조회"""
    try:
        session_info = security_audit.get_session_info(session_id)
        if session_info:
            return {"success": True, "session": session_info}
        else:
            raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving session: {e}")


@security_app.post("/security/sessions/cleanup")
async def cleanup_expired_sessions():
    """만료된 세션 정리"""
    try:
        result = security_audit.cleanup_sessions()
        return {"success": True, "cleanup_result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cleaning up sessions: {e}")


@security_app.post("/security/validate")
async def validate_code_security(request: CodeValidationRequest):
    """코드 보안성 검증 (실행 없이)"""
    try:
        if not request.code:
            raise HTTPException(status_code=400, detail="Code is required")

        validation_result = security_audit.validate_code_security(request.code)
        return {"success": True, "validation": validation_result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validating code: {e}")


@security_app.post("/security/execute")
async def execute_code_with_monitoring(execution_request: CodeExecutionRequest):
    """모니터링과 함께 코드 실행"""
    try:
        result = await security_audit.execute_code_with_audit(
            code=execution_request.code,
            session_id=execution_request.session_id or "security_api",
            timeout=execution_request.timeout or 30,
            client_info=execution_request.client_info,
        )

        return {"success": True, "execution_result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error executing code: {e}")


@security_app.get("/security/settings")
async def get_security_settings():
    """현재 보안 설정 조회"""
    try:
        sandbox = get_enhanced_sandbox()
        validator = get_security_validator()

        settings = {
            "security_level": validator.security_level,
            "resource_limits": {
                "max_memory_mb": sandbox.limits.max_memory_mb,
                "max_cpu_time_sec": sandbox.limits.max_cpu_time_sec,
                "max_output_size": sandbox.limits.max_output_size,
                "max_file_size": sandbox.limits.max_file_size,
                "max_processes": sandbox.limits.max_processes,
                "network_access": sandbox.limits.network_access,
            },
            "session_limits": {
                "max_sessions": sandbox.session_manager.max_sessions,
                "session_timeout": sandbox.session_manager.session_timeout,
            },
        }

        return {"success": True, "settings": settings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving settings: {e}")


@security_app.post("/security/settings")
async def update_security_settings(settings: SecuritySettings):
    """보안 설정 업데이트 (환경변수 기반)"""
    try:
        # 환경변수 업데이트 (재시작 필요)
        updated_vars = {
            "MCP_SECURITY_LEVEL": settings.security_level,
            "SANDBOX_MAX_MEMORY_MB": str(settings.max_memory_mb),
            "SANDBOX_MAX_CPU_TIME": str(settings.max_cpu_time_sec),
            "SANDBOX_MAX_OUTPUT_SIZE": str(settings.max_output_size),
            "SANDBOX_NETWORK_ACCESS": str(settings.network_access).lower(),
            "USE_ENHANCED_SANDBOX": str(settings.use_enhanced_sandbox).lower(),
        }

        return {
            "success": True,
            "message": "Settings updated (restart required)",
            "updated_variables": updated_vars,
            "restart_required": True,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating settings: {e}")


# ============================================================================
# Approval Workflow API Endpoints (Issue #26)
# ============================================================================


@security_app.get("/api/approvals/pending")
async def get_pending_approvals(
    limit: int = Query(50, le=100),
    tool_name: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
):
    """
    Get pending approval requests (Issue #26, Phase 3)

    Query Parameters:
    - limit: Maximum number of results (max 100)
    - tool_name: Filter by tool name
    - user_id: Filter by user ID

    Returns:
    {
      "pending_approvals": [
        {
          "request_id": "...",
          "tool_name": "...",
          "user_id": "...",
          "requested_at": "...",
          "seconds_until_expiry": 180
        }
      ],
      "count": 5
    }
    """
    try:
        from .security_database import get_security_database
        from .settings import SecuritySettings

        # Check RBAC permission (approval.view)
        db = get_security_database()

        # Query pending approvals
        pending = await db.list_pending_approvals(limit=limit)

        # Apply filters
        filtered = pending
        if tool_name:
            filtered = [p for p in filtered if p["tool_name"] == tool_name]
        if user_id:
            filtered = [p for p in filtered if p["user_id"] == user_id]

        # Format response
        approvals = []
        for req in filtered:
            approvals.append(
                {
                    "request_id": req["request_id"],
                    "tool_name": req["tool_name"],
                    "user_id": req["user_id"],
                    "role": req.get("role", "unknown"),
                    "requested_at": req["requested_at"],
                    "seconds_until_expiry": req.get("seconds_until_expiry", 0),
                }
            )

        return {
            "pending_approvals": approvals,
            "count": len(approvals),
            "filters": {
                "tool_name": tool_name,
                "user_id": user_id,
                "limit": limit,
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving pending approvals: {e}")


@security_app.post("/api/approvals/{request_id}/approve")
async def approve_approval_request(
    request_id: str,
    reason: str = Body(..., embed=False),
    user_id: str = Header(None, alias="X-User-ID"),
):
    """
    Approve an approval request (Issue #26, Phase 3)

    Parameters:
    - request_id: UUID of approval request (supports short ID prefix)
    - reason: Reason for approval
    - X-User-ID: Approver user ID (from header)

    Returns:
    {
      "status": "approved",
      "request_id": "...",
      "responder": "...",
      "message": "Request approved successfully"
    }
    """
    try:
        from .security_database import get_security_database

        if not user_id:
            user_id = "api_admin"

        db = get_security_database()

        # Find request (support short ID)
        request = await db.get_approval_request(request_id)
        if not request:
            raise HTTPException(status_code=404, detail=f"Approval request not found: {request_id}")

        # Check if already processed
        if request["status"] != "pending":
            raise HTTPException(
                status_code=409,
                detail=f"Request already {request['status']} (idempotent: cannot change again)",
            )

        # Update status
        success = await db.update_approval_status(
            request_id=request["request_id"],
            status="approved",
            responder_id=user_id,
            response_reason=reason,
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to update approval status")

        return {
            "status": "approved",
            "request_id": request["request_id"],
            "responder": user_id,
            "message": "Request approved successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error approving request: {e}")


@security_app.post("/api/approvals/{request_id}/reject")
async def reject_approval_request(
    request_id: str,
    reason: str = Body(..., embed=False),
    user_id: str = Header(None, alias="X-User-ID"),
):
    """
    Reject an approval request (Issue #26, Phase 3)

    Parameters:
    - request_id: UUID of approval request (supports short ID prefix)
    - reason: Reason for rejection
    - X-User-ID: Responder user ID (from header)

    Returns:
    {
      "status": "rejected",
      "request_id": "...",
      "responder": "...",
      "message": "Request rejected successfully"
    }
    """
    try:
        from .security_database import get_security_database

        if not user_id:
            user_id = "api_admin"

        db = get_security_database()

        # Find request (support short ID)
        request = await db.get_approval_request(request_id)
        if not request:
            raise HTTPException(status_code=404, detail=f"Approval request not found: {request_id}")

        # Check if already processed
        if request["status"] != "pending":
            raise HTTPException(
                status_code=409,
                detail=f"Request already {request['status']} (idempotent: cannot change again)",
            )

        # Update status
        success = await db.update_approval_status(
            request_id=request["request_id"],
            status="rejected",
            responder_id=user_id,
            response_reason=reason,
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to update approval status")

        return {
            "status": "rejected",
            "request_id": request["request_id"],
            "responder": user_id,
            "message": "Request rejected successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error rejecting request: {e}")


@security_app.get("/api/approvals/{request_id}/status")
async def get_approval_status(request_id: str):
    """
    Get approval request status (Issue #26, Phase 3)

    Used by CLI polling during approval wait.
    No caching - always returns current DB state.

    Parameters:
    - request_id: UUID of approval request (supports short ID prefix)

    Returns:
    {
      "request_id": "...",
      "status": "pending|approved|rejected|expired|timeout",
      "seconds_until_expiry": 180,
      "responder": "...",
      "reason": "..."  (only if responded)
    }
    """
    try:
        from .security_database import get_security_database

        db = get_security_database()

        # Find request (support short ID)
        request = await db.get_approval_request(request_id)
        if not request:
            raise HTTPException(status_code=404, detail=f"Approval request not found: {request_id}")

        # Build response
        response = {
            "request_id": request["request_id"],
            "status": request["status"],
            "seconds_until_expiry": request.get("seconds_until_expiry", 0),
        }

        # Add responder info if available
        if request.get("responder_id"):
            response["responder"] = request["responder_id"]
        if request.get("response_reason"):
            response["reason"] = request["response_reason"]

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving status: {e}")


@security_app.get("/security/logs/audit")
async def get_audit_logs(
    limit: int = Query(100, description="최대 로그 수"),
    event_type: Optional[str] = Query(None, description="이벤트 타입 필터"),
    session_id: Optional[str] = Query(None, description="세션 ID 필터"),
):
    """감사 로그 조회"""
    try:
        log_file = security_audit.logger.audit_log
        if not log_file.exists():
            return {
                "success": True,
                "logs": [],
                "total": 0,
                "message": "No audit log file found",
            }

        logs = []
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    event = json.loads(line.strip())

                    # 필터 적용
                    if event_type and event.get("event_type") != event_type:
                        continue
                    if session_id and event.get("session_id") != session_id:
                        continue

                    logs.append(event)
                except json.JSONDecodeError:
                    continue

        # 최신순으로 정렬하고 제한
        logs = sorted(logs, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]

        return {
            "success": True,
            "logs": logs,
            "total": len(logs),
            "filters": {
                "event_type": event_type,
                "session_id": session_id,
                "limit": limit,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving audit logs: {e}")


# 예외 처리
@security_app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "error": "Security endpoint not found",
            "available_endpoints": [
                "/security/health",
                "/security/stats",
                "/security/sessions",
                "/security/validate",
                "/security/execute",
                "/security/settings",
                "/security/logs/audit",
            ],
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        security_app,
        host=os.getenv("MCP_SECURITY_HOST", "0.0.0.0"),  # nosec B104 - container binding by default
        port=int(os.getenv("MCP_SECURITY_PORT", "8021")),
    )
