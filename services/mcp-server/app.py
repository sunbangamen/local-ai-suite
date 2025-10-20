#!/usr/bin/env python3
"""
MCP Server for Local AI Suite
포트 8020에서 실행되는 로컬 AI용 Model Context Protocol 서버

핵심 기능:
- Resources: 로컬 파일 시스템 접근
- Tools: 코드 실행, Git 분석, RAG 검색
- Prompts: AI 작업 템플릿 제공
"""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles
import httpx
from fastapi import FastAPI, Request, Header, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator
import base64
import tempfile


def _resolve_host(env_var: str, default: str = "0.0.0.0") -> str:  # nosec B104
    """Resolve host binding with fallback to default for container environments."""
    value = os.getenv(env_var)
    return value if value else default


# 새로운 보안 모듈 임포트
try:
    from .security import get_security_validator, get_secure_executor, SecurityError
    from .safe_api import (
        get_safe_file_api,
        get_safe_command_executor,
        secure_resolve_path,
    )
    from .security_admin import security_app
    from .rate_limiter import get_rate_limiter, get_access_control

    # RBAC 및 감사 로깅 모듈 (Issue #8)
    from .settings import get_security_settings
    from .security_database import init_database
    from .rbac_manager import get_rbac_manager
    from .audit_logger import get_audit_logger
    from .rbac_middleware import RBACMiddleware
except ImportError:
    # 개발/테스트 환경에서의 절대 임포트
    from security import get_secure_executor, SecurityError
    from safe_api import (
        get_safe_file_api,
        get_safe_command_executor,
        secure_resolve_path,
    )
    from security_admin import security_app
    from rate_limiter import get_rate_limiter, get_access_control

    # RBAC 및 감사 로깅 모듈 (Issue #8)
    from settings import get_security_settings
    from security_database import init_database
    from rbac_manager import get_rbac_manager
    from audit_logger import get_audit_logger
    from rbac_middleware import RBACMiddleware

# Playwright와 Notion 임포트 (지연 로딩)
playwright = None
notion_client = None


async def init_playwright():
    """Playwright 초기화"""
    global playwright
    if playwright is None:
        from playwright.async_api import async_playwright

        playwright = await async_playwright().start()
    return playwright


def init_notion():
    """Notion 클라이언트 초기화"""
    global notion_client
    if notion_client is None:
        from notion_client import Client

        notion_token = os.getenv("NOTION_TOKEN")
        if notion_token:
            notion_client = Client(auth=notion_token)
    return notion_client


# 환경 변수 (통일된 기본값)
PROJECT_ROOT = os.getenv("PROJECT_ROOT", os.getenv("WORKSPACE_DIR", "/mnt/workspace"))
# Global filesystem access - NEW: Support for anywhere usage
HOST_ROOT = "/mnt/host"  # Full filesystem mounted here
RAG_URL = os.getenv("RAG_URL", "http://rag:8002")
API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://api-gateway:8000")
EMBEDDING_URL = os.getenv("EMBEDDING_URL", "http://embedding:8003")
GIT_DIR_PATH = os.getenv("GIT_DIR_PATH", "/mnt/workspace/.git-main")

CHAT_MODEL_NAME = os.getenv("API_GATEWAY_CHAT_MODEL", "chat-7b")
CODE_MODEL_NAME = os.getenv("API_GATEWAY_CODE_MODEL", "code-7b")


def resolve_path(path: str, working_dir: Optional[str] = None) -> Path:
    """
    Resolve file path, supporting both project-relative and global filesystem paths
    Handles host path mapping for container environment (/mnt/host prefix)
    """
    # Try secure path resolution first for workspace paths
    try:
        return secure_resolve_path(path, working_dir)
    except SecurityError:
        pass  # Fall through to global filesystem handling

    # Handle global filesystem paths (outside workspace)
    if working_dir:
        working_path = Path(working_dir)

        # Convert host absolute paths to container paths
        if working_path.is_absolute() and not working_path.exists():
            working_path = Path("/mnt/host") / working_path.relative_to("/")

        if path.startswith("/"):
            # Absolute path
            target_path = Path(path)
            if not target_path.exists():
                target_path = Path("/mnt/host") / target_path.relative_to("/")
            return target_path
        else:
            # Relative path
            return working_path / path
    else:
        # No working_dir specified, use PROJECT_ROOT
        return Path(PROJECT_ROOT) / path


def resolve_git_env(work_tree_path: str) -> dict:
    """
    Resolve git environment for worktree support
    Returns git environment variables (GIT_DIR, GIT_WORK_TREE) for subprocess
    """
    work_tree = Path(work_tree_path)
    git_file = work_tree / ".git"

    # Check if .git is a file (worktree) or directory (normal repo)
    if git_file.is_file():
        # Read gitdir path from .git file
        gitdir_content = git_file.read_text().strip()
        if gitdir_content.startswith("gitdir:"):
            gitdir_path = gitdir_content.split(":", 1)[1].strip()
            gitdir_path = Path(gitdir_path)

            # Convert to container path if needed
            if gitdir_path.is_absolute() and not gitdir_path.exists():
                # Try /mnt/host prefix for container
                gitdir_path = Path("/mnt/host") / gitdir_path.relative_to("/")

            return {"GIT_DIR": str(gitdir_path), "GIT_WORK_TREE": str(work_tree)}

    # Normal git repository or .git doesn't exist
    return {}


# MCP 서버 인스턴스
mcp = FastMCP("Local AI MCP Server")

# FastAPI 앱 (헬스체크용)
app = FastAPI(title="Local AI MCP Server", version="1.0.0")

# Prometheus metrics
Instrumentator().instrument(app).expose(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# RBAC 미들웨어 등록 (Issue #8)
# CORS 다음에 등록해야 CORS 헤더가 먼저 처리됨
settings = get_security_settings()
if settings.is_rbac_enabled():
    app.add_middleware(RBACMiddleware)
    import logging

    logger = logging.getLogger(__name__)
    logger.info("RBAC middleware enabled")


@app.middleware("http")
async def ensure_utf8_content_type(request: Request, call_next):
    """모든 응답에 UTF-8 charset 부여"""
    response = await call_next(request)
    if "content-type" not in response.headers:
        response.headers["content-type"] = "application/json; charset=utf-8"
    elif (
        "application/json" in response.headers["content-type"]
        and "charset" not in response.headers["content-type"]
    ):
        response.headers["content-type"] = "application/json; charset=utf-8"
    return response


# ============================================================================
# Background Tasks (Issue #16)
# ============================================================================


async def approval_cleanup_task():
    """
    백그라운드 작업: 만료된 승인 요청 정리
    1분마다 실행되어 타임아웃된 요청을 expired 상태로 변경
    """
    import logging
    from security_database import get_security_database

    logger = logging.getLogger(__name__)
    logger.info("Approval cleanup task started")

    while True:
        try:
            await asyncio.sleep(60)  # 1분 대기

            db = get_security_database()
            count = await db.cleanup_expired_approvals()

            if count > 0:
                logger.info(f"Cleaned up {count} expired approval requests")

        except asyncio.CancelledError:
            logger.info("Approval cleanup task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in approval cleanup task: {e}")
            # 에러 발생 시에도 계속 실행
            await asyncio.sleep(60)


# ============================================================================
# Application Lifecycle Events
# ============================================================================


@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 초기화"""
    import logging

    logger = logging.getLogger(__name__)

    settings = get_security_settings()

    # 설정 검증
    warnings = settings.validate_config()
    for warning in warnings:
        logger.warning(f"Security config warning: {warning}")

    # RBAC 활성화 시 초기화
    if settings.is_rbac_enabled():
        logger.info("Initializing RBAC system...")

        # 1. DB 초기화
        try:
            await init_database()
            logger.info(f"Security DB initialized: {settings.get_db_path()}")
        except Exception as e:
            logger.error(f"Failed to initialize security DB: {e}")
            raise

        # 2. RBAC 캐시 예열
        try:
            rbac_manager = get_rbac_manager()
            await rbac_manager.prewarm_cache()
            cache_stats = rbac_manager.get_cache_stats()
            logger.info(f"RBAC cache prewarmed: {cache_stats}")
        except Exception as e:
            logger.warning(f"Failed to prewarm RBAC cache: {e}")

        # 3. Audit logger 시작
        try:
            audit_logger = get_audit_logger()
            audit_logger.start_async_writer()
            queue_stats = audit_logger.get_queue_stats()
            logger.info(f"Audit logger started: {queue_stats}")
        except Exception as e:
            logger.error(f"Failed to start audit logger: {e}")
            raise

        # 4. Approval workflow cleanup task (Issue #16)
        if settings.is_approval_enabled():
            logger.info("Starting approval workflow cleanup task...")
            asyncio.create_task(approval_cleanup_task())

        logger.info("RBAC system initialized successfully")
    else:
        logger.info("RBAC system disabled (RBAC_ENABLED=false)")


@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료 시 정리"""
    import logging

    logger = logging.getLogger(__name__)

    settings = get_security_settings()

    if settings.is_rbac_enabled():
        logger.info("Shutting down RBAC system...")

        try:
            audit_logger = get_audit_logger()
            await audit_logger.stop_async_writer()
            logger.info("Audit logger stopped")
        except Exception as e:
            logger.error(f"Error stopping audit logger: {e}")

        logger.info("RBAC system shutdown complete")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "mcp-server"}


@app.get("/rate-limits/{tool_name}")
async def get_rate_limit_status(tool_name: str, user_id: str = "default"):
    """특정 도구의 Rate Limit 상태 조회"""
    rate_limiter = get_rate_limiter()
    return rate_limiter.get_current_usage(tool_name, user_id)


@app.get("/tool-info/{tool_name}")
async def get_tool_security_info(tool_name: str):
    """도구의 보안 정보 조회"""
    access_control = get_access_control()
    return access_control.get_tool_info(tool_name)


# ============================================================================
# Approval Workflow API Endpoints (Issue #16)
# ============================================================================


@app.get("/api/approvals/pending")
async def get_pending_approvals(
    limit: int = 50, user_id: str = Header(None, alias="X-User-ID")
):
    """
    대기 중인 승인 요청 목록 조회 (admin only)

    Args:
        limit: 최대 반환 개수
        user_id: 요청 사용자 (X-User-ID 헤더)

    Returns:
        대기 중인 승인 요청 목록
    """
    from security_database import get_security_database
    from rbac_manager import get_rbac_manager

    # Admin 권한 체크
    rbac = get_rbac_manager()
    role = await rbac.get_user_role(user_id or "anonymous")
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    # 대기 중인 승인 요청 조회
    db = get_security_database()
    requests = await db.list_pending_approvals(limit)

    return {"pending_approvals": requests, "count": len(requests)}


@app.post("/api/approvals/{request_id}/approve")
async def approve_request(
    request_id: str,
    reason: str = Body(..., embed=True),
    user_id: str = Header(None, alias="X-User-ID"),
):
    """
    승인 요청 승인

    Args:
        request_id: 승인 요청 ID
        reason: 승인 사유
        user_id: 승인자 ID (X-User-ID 헤더)

    Returns:
        승인 결과
    """
    from security_database import get_security_database
    from rbac_manager import get_rbac_manager
    from audit_logger import get_audit_logger

    # Admin 권한 체크
    rbac = get_rbac_manager()
    role = await rbac.get_user_role(user_id or "anonymous")
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    # 승인 처리
    db = get_security_database()

    # Get original request to extract user_id and tool_name
    original_request = await db.get_approval_request(request_id)
    if not original_request:
        raise HTTPException(status_code=404, detail="Approval request not found")

    success = await db.update_approval_status(
        request_id=request_id,
        status="approved",
        responder_id=user_id or "admin",
        response_reason=reason,
    )

    if not success:
        raise HTTPException(
            status_code=404, detail="Approval request already processed"
        )

    # 감사 로그 기록 (enhanced with specific approval logging)
    audit = get_audit_logger()
    await audit.log_approval_granted(
        user_id=original_request["user_id"],
        tool_name=original_request["tool_name"],
        request_id=request_id,
        responder_id=user_id or "admin",
        reason=reason,
    )

    return {"status": "approved", "request_id": request_id, "responder": user_id}


@app.post("/api/approvals/{request_id}/reject")
async def reject_request(
    request_id: str,
    reason: str = Body(..., embed=True),
    user_id: str = Header(None, alias="X-User-ID"),
):
    """
    승인 요청 거부

    Args:
        request_id: 승인 요청 ID
        reason: 거부 사유
        user_id: 거부자 ID (X-User-ID 헤더)

    Returns:
        거부 결과
    """
    from security_database import get_security_database
    from rbac_manager import get_rbac_manager
    from audit_logger import get_audit_logger

    # Admin 권한 체크
    rbac = get_rbac_manager()
    role = await rbac.get_user_role(user_id or "anonymous")
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    # 거부 처리
    db = get_security_database()

    # Get original request to extract user_id and tool_name
    original_request = await db.get_approval_request(request_id)
    if not original_request:
        raise HTTPException(status_code=404, detail="Approval request not found")

    success = await db.update_approval_status(
        request_id=request_id,
        status="rejected",
        responder_id=user_id or "admin",
        response_reason=reason,
    )

    if not success:
        raise HTTPException(
            status_code=404, detail="Approval request already processed"
        )

    # 감사 로그 기록 (enhanced with specific approval logging)
    audit = get_audit_logger()
    await audit.log_approval_rejected(
        user_id=original_request["user_id"],
        tool_name=original_request["tool_name"],
        request_id=request_id,
        responder_id=user_id or "admin",
        reason=reason,
    )

    return {"status": "rejected", "request_id": request_id, "responder": user_id}


# ============================================================================
# MCP Tools API
# ============================================================================


# MCP 도구 목록 API 엔드포인트 (올바른 FastMCP 사용법)
@app.get("/tools")
async def list_tools():
    """사용 가능한 MCP 도구 목록 반환"""
    try:
        tools_result = await mcp.list_tools()
        # 도구 정보를 간단한 형태로 변환
        tools_info = []
        for tool in tools_result:
            tools_info.append(
                {
                    "name": tool.name,
                    "description": tool.description or "설명 없음",
                    "inputSchema": tool.inputSchema,
                }
            )
        return {"tools": tools_info}
    except Exception as e:
        return {"error": f"도구 목록 조회 실패: {str(e)}"}


@app.post("/tools/{tool_name}/call")
async def call_tool(
    tool_name: str, request: Request, arguments: dict = None, user_id: str = "default"
):
    """MCP 도구 실행 (Rate Limiting 및 Access Control 적용)"""
    try:
        # Extract user_id from header (X-User-ID) or fallback to parameter
        actual_user_id = request.headers.get("X-User-ID", user_id)

        # Rate limiting 체크
        rate_limiter = get_rate_limiter()
        allowed, error_msg = rate_limiter.check_rate_limit(tool_name, actual_user_id)
        if not allowed:
            return {"error": error_msg, "success": False, "error_type": "rate_limit"}

        # Access control 체크
        access_control = get_access_control()
        allowed, error_msg = access_control.check_access(tool_name, actual_user_id)
        if not allowed:
            return {"error": error_msg, "success": False, "error_type": "access_denied"}

        # 도구 실행 시작 (동시 실행 제한 강제 적용)
        allowed, error_msg = rate_limiter.start_execution(
            tool_name, actual_user_id, access_control
        )
        if not allowed:
            return {
                "error": error_msg,
                "success": False,
                "error_type": "concurrent_limit",
            }

        try:
            # FastMCP의 call_tool 메서드 사용
            result = await mcp.call_tool(tool_name, arguments or {})

            # 결과 처리 - FastMCP의 실제 반환 형식에 따라 조정
            if hasattr(result, "content") and result.content:
                # TextContent나 다른 content 타입인 경우
                if hasattr(result.content[0], "text"):
                    return {"result": result.content[0].text, "success": True}
                else:
                    return {"result": str(result.content[0]), "success": True}
            else:
                # 직접 결과인 경우
                return {"result": result, "success": True}
        finally:
            # 도구 실행 종료
            rate_limiter.end_execution(tool_name, actual_user_id)

    except Exception as e:
        return {"error": str(e), "success": False}


# =============================================================================
# Pydantic Models
# =============================================================================


class FileInfo(BaseModel):
    path: str
    content: str
    size: int
    type: str


class ExecutionResult(BaseModel):
    command: str
    stdout: str
    stderr: str
    returncode: int
    success: bool


class RAGResult(BaseModel):
    query: str
    response: str
    sources: List[str] = []


class AIResponse(BaseModel):
    model: str
    message: str
    response: str


class WebScreenshotResult(BaseModel):
    url: str
    screenshot_base64: str
    width: int
    height: int
    timestamp: str


class WebScrapeResult(BaseModel):
    url: str
    selector: str
    data: List[str]
    count: int


class WebUIAnalysis(BaseModel):
    url: str
    title: str
    css_styles: Dict[str, Any]
    layout_info: Dict[str, Any]
    color_scheme: List[str]
    fonts: List[str]


class NotionPageResult(BaseModel):
    page_id: str
    url: str
    title: str
    status: str


# =============================================================================
# MCP Resources - 파일 시스템 접근
# =============================================================================


@mcp.resource("file://{path}")
async def read_file_resource(path: str) -> str:
    """파일 내용을 리소스로 제공"""
    file_path = Path(PROJECT_ROOT) / path

    # 전역 파일시스템 접근 허용 (기본 안전성 검사는 resolve_path에서 처리)

    if not file_path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없음: {file_path}")

    async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
        content = await f.read()
        return content


@mcp.resource("project://files")
async def list_project_files() -> str:
    """프로젝트 파일 목록 제공"""
    project_path = Path(PROJECT_ROOT)
    files = []

    # Python 파일들
    for file_path in project_path.rglob("*.py"):
        if not any(part.startswith(".") for part in file_path.parts):
            files.append(
                {
                    "path": str(file_path.relative_to(project_path)),
                    "type": "python",
                    "size": file_path.stat().st_size if file_path.exists() else 0,
                }
            )

    # 설정 파일들
    for pattern in ["*.yml", "*.yaml", "*.json", "*.md", "*.env*"]:
        for file_path in project_path.rglob(pattern):
            if not any(part.startswith(".") for part in file_path.parts):
                files.append(
                    {
                        "path": str(file_path.relative_to(project_path)),
                        "type": "config",
                        "size": file_path.stat().st_size if file_path.exists() else 0,
                    }
                )

    return json.dumps(files[:50], indent=2)  # 최대 50개 제한


# =============================================================================
# MCP Tools - 코드 실행 및 시스템 도구
# =============================================================================


@mcp.tool()
async def execute_python(code: str, timeout: int = 30) -> ExecutionResult:
    """보안이 강화된 Python 코드 실행"""
    try:
        # 새로운 보안 실행 환경 사용
        secure_executor = get_secure_executor()
        result = secure_executor.execute_python_code(code, timeout)

        return ExecutionResult(
            command=f"python -c '{code[:50]}...'",
            stdout=result["stdout"],
            stderr=result["stderr"],
            returncode=result["returncode"],
            success=result["success"],
        )
    except Exception as e:
        return ExecutionResult(
            command=f"python -c '{code[:50]}...'",
            stdout="",
            stderr=f"보안 실행 환경 오류: {str(e)}",
            returncode=1,
            success=False,
        )


@mcp.tool()
async def execute_bash(
    command: str, timeout: int = 30, working_dir: Optional[str] = None
) -> ExecutionResult:
    """보안이 강화된 Bash 명령어 실행"""
    try:
        # 새로운 안전한 명령어 실행기 사용
        safe_executor = get_safe_command_executor()
        result = await safe_executor.execute_command(command, working_dir, timeout)

        return ExecutionResult(
            command=result["command"],
            stdout=result["stdout"],
            stderr=result["stderr"],
            returncode=result["returncode"],
            success=result["success"],
        )
    except SecurityError as e:
        return ExecutionResult(
            command=command,
            stdout="",
            stderr=f"보안 검증 실패: {str(e)}",
            returncode=1,
            success=False,
        )
    except Exception as e:
        return ExecutionResult(
            command=command,
            stdout="",
            stderr=f"명령어 실행 오류: {str(e)}",
            returncode=1,
            success=False,
        )


@mcp.tool()
async def read_file(path: str, working_dir: Optional[str] = None) -> FileInfo:
    """보안이 강화된 파일 내용 읽기 - 전역 파일시스템 지원"""
    try:
        # 새로운 안전한 파일 API 사용
        safe_file_api = get_safe_file_api()
        content = safe_file_api.read_text(path, working_dir)

        # 실제 경로 정보 가져오기 (보안 검증 후)
        safe_path = secure_resolve_path(path, working_dir)

        return FileInfo(
            path=str(safe_path),
            content=content,
            size=len(content),
            type=safe_path.suffix,
        )
    except SecurityError as e:
        raise ValueError(f"보안 검증 실패: {str(e)}")
    except (FileNotFoundError, IOError) as e:
        raise Exception(f"파일 읽기 오류: {str(e)}")


@mcp.tool()
async def write_file(
    path: str, content: str, working_dir: Optional[str] = None
) -> FileInfo:
    """보안이 강화된 파일 내용 쓰기 - 전역 파일시스템 지원"""
    try:
        # 새로운 안전한 파일 API 사용
        safe_file_api = get_safe_file_api()
        safe_file_api.write_text(path, content, working_dir)

        # 실제 경로 정보 가져오기 (보안 검증 후)
        safe_path = secure_resolve_path(path, working_dir)

        return FileInfo(
            path=str(safe_path),
            content=content,
            size=len(content),
            type=safe_path.suffix,
        )
    except SecurityError as e:
        raise ValueError(f"보안 검증 실패: {str(e)}")
    except IOError as e:
        raise Exception(f"파일 쓰기 오류: {str(e)}")


@mcp.tool()
async def list_files(
    path: str = ".", working_dir: Optional[str] = None
) -> Dict[str, Any]:
    """보안이 강화된 디렉토리 파일 목록 조회"""
    try:
        # 새로운 안전한 파일 API 사용
        safe_file_api = get_safe_file_api()
        file_list = safe_file_api.list_directory(path, working_dir)

        # 실제 경로 정보 가져오기 (보안 검증 후)
        safe_path = secure_resolve_path(path, working_dir)

        return {"path": str(safe_path), "files": file_list, "count": len(file_list)}
    except SecurityError as e:
        raise ValueError(f"보안 검증 실패: {str(e)}")
    except (FileNotFoundError, IOError) as e:
        raise Exception(f"디렉토리 목록 조회 오류: {str(e)}")


@mcp.tool()
async def rag_search(query: str, collection: str = "default") -> RAGResult:
    """RAG 시스템에서 문서 검색"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{RAG_URL}/query",
                json={"query": query, "collection": collection},
                timeout=30.0,
            )
            response.raise_for_status()

            data = response.json()
            return RAGResult(
                query=query,
                response=data.get("response", "응답 없음"),
                sources=data.get("sources", []),
            )
    except Exception as e:
        raise Exception(f"RAG 검색 오류: {str(e)}")


def _detect_model_for_message(message: str) -> str:
    """메시지 내용 분석하여 적절한 모델 선택"""
    code_keywords = [
        "function",
        "class",
        "import",
        "export",
        "const",
        "let",
        "var",
        "def",
        "return",
        "if",
        "for",
        "while",
        "try",
        "catch",
        "async",
        "await",
        "코드",
        "함수",
        "프로그래밍",
        "버그",
        "API",
        "HTML",
        "CSS",
        "JavaScript",
        "Python",
        "React",
        "개발",
        "구현",
        "디버그",
        "스크립트",
        "라이브러리",
        "npm",
        "pip",
        "git",
        "docker",
        "배포",
        "테스트",
        "알고리즘",
        "```",
        "console.log",
        "print(",
        "error",
        "exception",
        "코딩",
        "프로그램",
    ]

    message_lower = message.lower()
    has_code_keywords = any(
        keyword.lower() in message_lower for keyword in code_keywords
    )

    return CODE_MODEL_NAME if has_code_keywords else CHAT_MODEL_NAME


@mcp.tool()
async def ai_chat(message: str, model: str = None) -> AIResponse:
    """로컬 AI 모델과 대화 (자동 모델 선택)"""
    try:
        # 모델이 지정되지 않으면 메시지 내용 분석하여 자동 선택
        if model is None:
            model = _detect_model_for_message(message)

        print(f"[MCP] AI Chat 모델 선택: {model} (메시지: {message[:50]}...)")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_GATEWAY_URL}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": message}],
                    "max_tokens": 512,
                    "temperature": 0.3,
                },
                timeout=60.0,
            )
            response.raise_for_status()

            data = response.json()
            ai_response = data["choices"][0]["message"]["content"]
            return AIResponse(model=model, message=message, response=ai_response)
    except Exception as e:
        raise Exception(f"AI 채팅 오류: {str(e)}")


@mcp.tool()
async def git_status(
    path: str = ".", working_dir: Optional[str] = None
) -> ExecutionResult:
    """Git 저장소 상태 확인 (전역 Git 지원)"""
    # working_dir가 제공되면 해당 디렉토리 사용, 아니면 현재 경로
    if working_dir:
        # 전역 파일시스템 접근을 위한 경로 해결
        repo_path = resolve_path(path, working_dir)
        git_cwd = str(
            repo_path.parent if path != "." else resolve_path(".", working_dir)
        )
    else:
        repo_path = Path(PROJECT_ROOT) / path
        git_cwd = PROJECT_ROOT

    try:
        # Resolve git environment for worktree support
        git_env = resolve_git_env(git_cwd)
        proc_env = {**os.environ, **git_env} if git_env else None

        # 현재 디렉토리의 Git 저장소 자동 감지
        proc = await asyncio.create_subprocess_exec(
            "git",
            "status",
            "--porcelain",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=git_cwd,
            env=proc_env,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            return ExecutionResult(
                command="git status --porcelain",
                stdout="",
                stderr=stderr.decode() if stderr else "Git 명령 실행 실패",
                returncode=proc.returncode or 1,
                success=False,
            )

        status_output = stdout.decode().strip()
        if not status_output:
            status_output = "변경사항 없음 (깨끗함)"

        return ExecutionResult(
            command="git status --porcelain",
            stdout=status_output,
            stderr="",
            returncode=0,
            success=True,
        )
    except Exception as e:
        return ExecutionResult(
            command="git status --porcelain",
            stdout="",
            stderr=f"Git 상태 확인 오류: {str(e)}",
            returncode=1,
            success=False,
        )


@mcp.tool()
async def git_diff(
    file_path: str = "",
    staged: bool = False,
    working_dir: Optional[str] = None,
) -> ExecutionResult:
    """Git 변경사항 차이 확인 (worktree 및 전역 디렉터리 지원)"""
    if working_dir:
        git_cwd = str(resolve_path(".", working_dir))
        cmd_args = ["git", "diff"]
    else:
        git_cwd = PROJECT_ROOT
        cmd_args = [
            "git",
            "--git-dir",
            GIT_DIR_PATH,
            "--work-tree",
            PROJECT_ROOT,
            "diff",
        ]

    try:
        # Resolve git environment for worktree support
        git_env = resolve_git_env(git_cwd)
        proc_env = {**os.environ, **git_env} if git_env else None

        if staged:
            cmd_args.append("--cached")

        if file_path:
            cmd_args.append(file_path)

        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=git_cwd,
            env=proc_env,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            return ExecutionResult(
                command=" ".join(cmd_args),
                stdout="",
                stderr=stderr.decode() if stderr else "Git diff 실행 실패",
                returncode=proc.returncode or 1,
                success=False,
            )

        diff_output = stdout.decode().strip()
        if not diff_output:
            diff_output = "변경사항 없음"

        return ExecutionResult(
            command=" ".join(cmd_args),
            stdout=diff_output,
            stderr="",
            returncode=0,
            success=True,
        )
    except Exception as e:
        return ExecutionResult(
            command="git diff",
            stdout="",
            stderr=f"Git diff 오류: {str(e)}",
            returncode=1,
            success=False,
        )


@mcp.tool()
async def git_log(
    max_count: int = 10, oneline: bool = True, working_dir: Optional[str] = None
) -> ExecutionResult:
    """Git 커밋 히스토리 확인 (전역 Git 지원)"""
    # working_dir가 제공되면 해당 디렉토리 사용
    if working_dir:
        git_cwd = str(resolve_path(".", working_dir))
    else:
        git_cwd = PROJECT_ROOT

    try:
        # Resolve git environment for worktree support
        git_env = resolve_git_env(git_cwd)
        proc_env = {**os.environ, **git_env} if git_env else None

        cmd_args = ["git", "log", f"--max-count={max_count}"]

        if oneline:
            cmd_args.append("--oneline")

        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=git_cwd,
            env=proc_env,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            return ExecutionResult(
                command=" ".join(cmd_args),
                stdout="",
                stderr=stderr.decode() if stderr else "Git log 실행 실패",
                returncode=proc.returncode or 1,
                success=False,
            )

        log_output = stdout.decode().strip()
        if not log_output:
            log_output = "커밋 히스토리 없음"

        return ExecutionResult(
            command=" ".join(cmd_args),
            stdout=log_output,
            stderr="",
            returncode=0,
            success=True,
        )
    except Exception as e:
        return ExecutionResult(
            command="git log",
            stdout="",
            stderr=f"Git log 오류: {str(e)}",
            returncode=1,
            success=False,
        )


@mcp.tool()
async def git_add(
    file_paths: str, working_dir: Optional[str] = None
) -> ExecutionResult:
    """Git 파일 스테이징 (전역 Git 지원)"""
    # working_dir가 제공되면 해당 디렉토리 사용
    if working_dir:
        git_cwd = str(resolve_path(".", working_dir))
    else:
        git_cwd = PROJECT_ROOT

    try:
        # Resolve git environment for worktree support
        git_env = resolve_git_env(git_cwd)
        proc_env = {**os.environ, **git_env} if git_env else None

        # 여러 파일 지원을 위해 공백으로 분리
        files = file_paths.split() if file_paths.strip() else ["."]

        cmd_args = ["git", "add"] + files

        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=git_cwd,
            env=proc_env,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            return ExecutionResult(
                command=" ".join(cmd_args),
                stdout="",
                stderr=stderr.decode() if stderr else "Git add 실행 실패",
                returncode=proc.returncode or 1,
                success=False,
            )

        return ExecutionResult(
            command=" ".join(cmd_args),
            stdout=f"파일 스테이징 완료: {file_paths}",
            stderr="",
            returncode=0,
            success=True,
        )
    except Exception as e:
        return ExecutionResult(
            command="git add",
            stdout="",
            stderr=f"Git add 오류: {str(e)}",
            returncode=1,
            success=False,
        )


@mcp.tool()
async def git_commit(
    message: str, add_all: bool = False, working_dir: Optional[str] = None
) -> ExecutionResult:
    """Git 커밋 생성 (전역 Git 지원, Worktree 지원)"""
    # working_dir가 제공되면 해당 디렉토리 사용
    if working_dir:
        git_cwd = str(resolve_path(".", working_dir))
    else:
        git_cwd = PROJECT_ROOT

    if not message.strip():
        return ExecutionResult(
            command="git commit",
            stdout="",
            stderr="커밋 메시지가 필요합니다",
            returncode=1,
            success=False,
        )

    try:
        # add_all이 True면 먼저 모든 변경사항 스테이징
        if add_all:
            add_result = await git_add(".", working_dir)
            if not add_result.success:
                return add_result

        # Resolve git environment for worktree support
        git_env = resolve_git_env(git_cwd)
        proc_env = {**os.environ, **git_env} if git_env else None

        cmd_args = ["git", "commit", "-m", message]

        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=git_cwd,
            env=proc_env,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            return ExecutionResult(
                command=" ".join(cmd_args[:7]) + " [message]",  # 메시지는 숨김
                stdout="",
                stderr=stderr.decode() if stderr else "Git commit 실행 실패",
                returncode=proc.returncode or 1,
                success=False,
            )

        commit_output = stdout.decode().strip()

        return ExecutionResult(
            command=" ".join(cmd_args[:7]) + " [message]",  # 메시지는 숨김
            stdout=f"커밋 완료: {commit_output}",
            stderr="",
            returncode=0,
            success=True,
        )
    except Exception as e:
        return ExecutionResult(
            command="git commit",
            stdout="",
            stderr=f"Git commit 오류: {str(e)}",
            returncode=1,
            success=False,
        )


# =============================================================================
# Playwright 웹 자동화 도구
# =============================================================================


@mcp.tool()
async def web_screenshot(
    url: str, width: int = 1280, height: int = 720
) -> WebScreenshotResult:
    """웹사이트 스크린샷 촬영"""
    try:
        pw = await init_playwright()
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": width, "height": height})

        await page.goto(url, wait_until="networkidle")
        screenshot_bytes = await page.screenshot(full_page=True)

        # Base64 인코딩
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode()

        await browser.close()

        from datetime import datetime

        return WebScreenshotResult(
            url=url,
            screenshot_base64=screenshot_b64,
            width=width,
            height=height,
            timestamp=datetime.now().isoformat(),
        )

    except Exception as e:
        raise Exception(f"스크린샷 촬영 오류: {str(e)}")


@mcp.tool()
async def web_scrape(
    url: str, selector: str, attribute: str = "textContent"
) -> WebScrapeResult:
    """웹사이트에서 특정 요소 크롤링"""
    try:
        pw = await init_playwright()
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(url, wait_until="networkidle")

        # 요소들 찾기
        elements = await page.query_selector_all(selector)
        data = []

        for element in elements:
            if attribute == "textContent":
                content = await element.text_content()
            elif attribute == "innerHTML":
                content = await element.inner_html()
            elif attribute == "href":
                content = await element.get_attribute("href")
            elif attribute == "src":
                content = await element.get_attribute("src")
            else:
                content = await element.get_attribute(attribute)

            if content and content.strip():
                data.append(content.strip())

        await browser.close()

        return WebScrapeResult(url=url, selector=selector, data=data, count=len(data))

    except Exception as e:
        raise Exception(f"웹 크롤링 오류: {str(e)}")


@mcp.tool()
async def web_analyze_ui(url: str) -> WebUIAnalysis:
    """웹사이트 UI/디자인 분석"""
    try:
        pw = await init_playwright()
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(url, wait_until="networkidle")

        # 제목 가져오기
        title = await page.title()

        # CSS 스타일 분석
        css_analysis = await page.evaluate(
            """
            () => {
                const styles = {};
                const computedStyle = window.getComputedStyle(document.body);

                // 기본 스타일 정보
                styles.backgroundColor = computedStyle.backgroundColor;
                styles.color = computedStyle.color;
                styles.fontFamily = computedStyle.fontFamily;
                styles.fontSize = computedStyle.fontSize;

                // 레이아웃 정보
                const layout = {};
                layout.width = document.body.offsetWidth;
                layout.height = document.body.offsetHeight;
                layout.padding = computedStyle.padding;
                layout.margin = computedStyle.margin;

                // 색상 팔레트 추출
                const colors = new Set();
                const elements = document.querySelectorAll('*');
                for (let i = 0; i < Math.min(elements.length, 100); i++) {
                    const style = window.getComputedStyle(elements[i]);
                    if (style.backgroundColor !== 'rgba(0, 0, 0, 0)') {
                        colors.add(style.backgroundColor);
                    }
                    if (style.color !== 'rgba(0, 0, 0, 0)') {
                        colors.add(style.color);
                    }
                }

                // 폰트 정보
                const fonts = new Set();
                for (let i = 0; i < Math.min(elements.length, 50); i++) {
                    const style = window.getComputedStyle(elements[i]);
                    fonts.add(style.fontFamily);
                }

                return {
                    styles,
                    layout,
                    colors: Array.from(colors).slice(0, 10),
                    fonts: Array.from(fonts).slice(0, 5)
                };
            }
        """
        )

        await browser.close()

        return WebUIAnalysis(
            url=url,
            title=title,
            css_styles=css_analysis["styles"],
            layout_info=css_analysis["layout"],
            color_scheme=css_analysis["colors"],
            fonts=css_analysis["fonts"],
        )

    except Exception as e:
        raise Exception(f"UI 분석 오류: {str(e)}")


@mcp.tool()
async def web_automate(url: str, actions: str) -> ExecutionResult:
    """웹 자동화 실행 (JSON 형태의 액션 리스트)"""
    try:
        import json

        action_list = json.loads(actions)

        pw = await init_playwright()
        browser = await pw.chromium.launch(
            headless=False
        )  # 디버깅을 위해 headless=False
        page = await browser.new_page()

        await page.goto(url, wait_until="networkidle")

        results = []

        for action in action_list:
            action_type = action.get("type")
            selector = action.get("selector")
            value = action.get("value", "")

            if action_type == "click":
                await page.click(selector)
                results.append(f"클릭: {selector}")

            elif action_type == "fill":
                await page.fill(selector, value)
                results.append(f"입력: {selector} = {value}")

            elif action_type == "wait":
                await page.wait_for_timeout(int(value) * 1000)
                results.append(f"대기: {value}초")

            elif action_type == "screenshot":
                screenshot = await page.screenshot()
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    f.write(screenshot)
                    results.append(f"스크린샷: {f.name}")

        await browser.close()

        return ExecutionResult(
            command=f"web_automate({url})",
            stdout="\n".join(results),
            stderr="",
            returncode=0,
            success=True,
        )

    except Exception as e:
        return ExecutionResult(
            command=f"web_automate({url})",
            stdout="",
            stderr=f"웹 자동화 오류: {str(e)}",
            returncode=1,
            success=False,
        )


# =============================================================================
# Notion API 연동 도구
# =============================================================================


@mcp.tool()
async def notion_create_page(
    database_id: str, title: str, properties: str = "{}"
) -> NotionPageResult:
    """Notion 데이터베이스에 새 페이지 생성"""
    try:
        notion = init_notion()
        if not notion:
            raise Exception(
                "Notion 토큰이 설정되지 않았습니다. NOTION_TOKEN 환경변수를 설정하세요."
            )

        import json

        props = json.loads(properties)

        # 기본 속성 설정
        page_properties = {"Name": {"title": [{"text": {"content": title}}]}}

        # 추가 속성 병합
        page_properties.update(props)

        response = notion.pages.create(
            parent={"database_id": database_id}, properties=page_properties
        )

        return NotionPageResult(
            page_id=response["id"], url=response["url"], title=title, status="created"
        )

    except Exception as e:
        raise Exception(f"Notion 페이지 생성 오류: {str(e)}")


@mcp.tool()
async def notion_search(query: str, filter_type: str = "page") -> List[Dict]:
    """Notion에서 페이지 검색"""
    try:
        notion = init_notion()
        if not notion:
            raise Exception(
                "Notion 토큰이 설정되지 않았습니다. NOTION_TOKEN 환경변수를 설정하세요."
            )

        response = notion.search(
            query=query, filter={"value": filter_type, "property": "object"}
        )

        results = []
        for item in response["results"][:10]:  # 최대 10개 결과
            results.append(
                {
                    "id": item["id"],
                    "title": item.get("properties", {})
                    .get("Name", {})
                    .get("title", [{}])[0]
                    .get("text", {})
                    .get("content", "제목 없음"),
                    "url": item["url"],
                    "last_edited": item["last_edited_time"],
                }
            )

        return results

    except Exception as e:
        raise Exception(f"Notion 검색 오류: {str(e)}")


@mcp.tool()
async def web_to_notion(
    url: str, database_id: str, title_selector: str = "h1", content_selector: str = "p"
) -> NotionPageResult:
    """웹 크롤링 결과를 Notion에 저장"""
    try:
        # 웹 크롤링
        title_result = await web_scrape(url, title_selector)
        content_result = await web_scrape(url, content_selector)

        title = title_result.data[0] if title_result.data else f"웹페이지: {url}"
        content = "\n".join(content_result.data[:5])  # 최대 5개 문단

        # Notion 페이지 생성
        properties = json.dumps(
            {
                "URL": {"url": url},
                "Content": {
                    "rich_text": [{"text": {"content": content[:2000]}}]
                },  # 2000자 제한
            }
        )

        result = await notion_create_page(database_id, title, properties)
        return result

    except Exception as e:
        raise Exception(f"웹→Notion 저장 오류: {str(e)}")


# =============================================================================
# 모델 관리 도구
# =============================================================================


class ModelSwitchResult(BaseModel):
    success: bool
    message: str
    current_model: str
    switch_time_seconds: Optional[float] = None


async def _detect_phase() -> tuple[bool, str]:
    """
    docker compose ps 명령으로 실행 중인 서비스를 확인하여 Phase 판별

    Returns:
        (is_phase2, compose_file): Phase 2 여부와 compose 파일 경로
        is_phase2가 None이면 감지 실패
    """
    try:
        # Phase 2 확인 (compose.p2.yml)
        result_p2 = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                "/mnt/workspace/docker/compose.p2.yml",
                "ps",
                "--services",
            ],
            capture_output=True,
            text=True,
            cwd="/mnt/workspace",
        )

        if result_p2.returncode == 0:
            services = set(result_p2.stdout.strip().split("\n"))
            # inference-chat와 inference-code가 모두 있으면 Phase 2
            if "inference-chat" in services and "inference-code" in services:
                return True, "docker/compose.p2.yml"

        # Phase 3 확인 (compose.p3.yml)
        result_p3 = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                "/mnt/workspace/docker/compose.p3.yml",
                "ps",
                "--services",
            ],
            capture_output=True,
            text=True,
            cwd="/mnt/workspace",
        )

        if result_p3.returncode == 0:
            services = set(result_p3.stdout.strip().split("\n"))
            # inference 서비스만 있으면 Phase 3
            if "inference" in services:
                return False, "docker/compose.p3.yml"

        # 둘 다 없으면 감지 실패
        return None, None

    except Exception as e:
        print(f"Phase 감지 중 오류: {e}")
        return None, None


async def _get_model_info(service_url: str) -> tuple[bool, str]:
    """
    서비스의 현재 로드된 모델 정보 조회

    Args:
        service_url: 서비스 URL (예: http://inference-chat:8001)

    Returns:
        (success, model_name): 성공 여부와 모델 파일명
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{service_url}/v1/models", timeout=10)
            if response.status_code == 200:
                models_data = response.json()
                if models_data.get("data"):
                    model_path = models_data["data"][0]["id"]
                    model_name = (
                        model_path.split("/")[-1] if "/" in model_path else model_path
                    )
                    return True, model_name
        return False, "unknown"
    except Exception as e:
        print(f"모델 정보 조회 실패 ({service_url}): {e}")
        return False, "unknown"


async def _restart_service(
    compose_file: str, service_name: str, env_vars: dict = None
) -> tuple[bool, str]:
    """
    Docker Compose 서비스 재시작

    Args:
        compose_file: compose 파일 경로
        service_name: 서비스 이름
        env_vars: 환경변수 딕셔너리 (선택)

    Returns:
        (success, message): 성공 여부와 메시지
    """
    try:
        # 서비스 중지
        stop_cmd = [
            "docker",
            "compose",
            "-f",
            f"/mnt/workspace/{compose_file}",
            "stop",
            service_name,
        ]
        result = subprocess.run(
            stop_cmd, capture_output=True, text=True, cwd="/mnt/workspace"
        )
        if result.returncode != 0:
            return False, f"서비스 중지 실패: {result.stderr}"

        # 환경변수 설정
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)

        # 서비스 재시작
        start_cmd = [
            "docker",
            "compose",
            "-f",
            f"/mnt/workspace/{compose_file}",
            "up",
            "-d",
            service_name,
        ]
        result = subprocess.run(
            start_cmd, capture_output=True, text=True, cwd="/mnt/workspace", env=env
        )
        if result.returncode != 0:
            return False, f"서비스 시작 실패: {result.stderr}"

        return True, "서비스 재시작 성공"

    except Exception as e:
        return False, f"재시작 중 오류: {e}"


async def _wait_for_health(service_url: str, max_wait: int = 30) -> bool:
    """
    서비스 헬스체크 대기

    Args:
        service_url: 서비스 URL (예: http://inference-chat:8001)
        max_wait: 최대 대기 시간 (초)

    Returns:
        bool: 헬스체크 성공 여부
    """
    health_url = f"{service_url}/health"
    for attempt in range(max_wait):
        await asyncio.sleep(1)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(health_url, timeout=5)
                if response.status_code == 200:
                    print(f"✅ 헬스체크 성공 (시도 {attempt + 1}/{max_wait})")
                    return True
        except:
            continue
    return False


@mcp.tool()
async def switch_model(model_type: str) -> ModelSwitchResult:
    """
    AI 모델을 동적으로 교체합니다 (메모리 효율성을 위해)

    Args:
        model_type: 'chat' 또는 'code' 모델 선택

    Returns:
        ModelSwitchResult: 교체 결과와 현재 모델 정보
    """
    import time

    start_time = time.time()

    try:
        # 환경변수에서 모델 파일명 가져오기
        if model_type == "chat":
            target_model = os.getenv("CHAT_MODEL", "Qwen2.5-7B-Instruct-Q4_K_M.gguf")
        elif model_type == "code":
            target_model = os.getenv(
                "CODE_MODEL", "qwen2.5-coder-7b-instruct-q4_k_m.gguf"
            )
        else:
            return ModelSwitchResult(
                success=False,
                message=f"지원하지 않는 모델 타입: {model_type}",
                current_model="unknown",
            )

        # Phase 감지: docker compose ps 기반으로 실제 실행 중인 서비스 확인
        # Phase 2: inference-chat + inference-code (이중화)
        # Phase 3: inference (단일)
        is_phase2, compose_file = await _detect_phase()
        if is_phase2 is None:
            return ModelSwitchResult(
                success=False,
                message="Phase 감지 실패: docker compose 서비스 목록을 확인할 수 없습니다.",
                current_model="unknown",
            )

        if is_phase2:
            # Phase 2: 이중화 구조
            # inference-chat (chat 모델), inference-code (code 모델)
            service_name = (
                "inference-chat" if model_type == "chat" else "inference-code"
            )
            service_url = f"http://{service_name}:8001"

            # 1. 현재 모델 확인
            success, current_model_name = await _get_model_info(service_url)
            if not success:
                return ModelSwitchResult(
                    success=False,
                    message=f"Phase 2: {service_name} 모델 정보 조회 실패",
                    current_model="unknown",
                )

            # 2. 기대하는 모델과 비교
            # Phase 2에서는 각 서비스가 .env의 환경변수로 지정된 모델을 사용해야 함
            # CHAT_MODEL 또는 CODE_MODEL 환경변수와 일치하는지 확인
            expected_model = target_model

            if expected_model.lower() == current_model_name.lower():
                # 이미 올바른 모델 실행 중
                end_time = time.time()
                return ModelSwitchResult(
                    success=True,
                    message=f"Phase 2: {model_type} 모델은 {service_name}에서 이미 실행 중입니다 ({current_model_name}).",
                    current_model=current_model_name,
                    switch_time_seconds=round(time.time() - start_time, 1),
                )
            else:
                # 모델이 다르면 서비스 재시작 필요
                print(f"⚠️  Phase 2: {service_name}의 모델이 기대값과 다릅니다.")
                print(f"   현재: {current_model_name}, 기대: {expected_model}")
                print(f"🔄 {service_name} 재시작 중...")

                # 환경변수 설정 (필요시)
                env_vars = {}
                if model_type == "chat":
                    env_vars["CHAT_MODEL"] = target_model
                else:
                    env_vars["CODE_MODEL"] = target_model

                # 서비스 재시작
                restart_success, restart_msg = await _restart_service(
                    compose_file, service_name, env_vars
                )
                if not restart_success:
                    return ModelSwitchResult(
                        success=False,
                        message=f"Phase 2: {service_name} 재시작 실패 - {restart_msg}",
                        current_model=current_model_name,
                    )

                # 헬스체크 대기
                print(f"⏳ {service_name} 헬스체크 대기 중...")
                if not await _wait_for_health(service_url, max_wait=30):
                    return ModelSwitchResult(
                        success=False,
                        message=f"Phase 2: {service_name} 헬스체크 타임아웃 (30초)",
                        current_model="unknown",
                    )

                # 재시작 후 모델 확인
                success, new_model_name = await _get_model_info(service_url)
                end_time = time.time()

                if success and new_model_name.lower() == expected_model.lower():
                    return ModelSwitchResult(
                        success=True,
                        message=f"Phase 2: {service_name} 재시작 완료, {model_type} 모델({new_model_name}) 로드됨",
                        current_model=new_model_name,
                        switch_time_seconds=round(end_time - start_time, 1),
                    )
                else:
                    return ModelSwitchResult(
                        success=False,
                        message=f"Phase 2: 재시작 후 모델 검증 실패 (현재: {new_model_name}, 기대: {expected_model})",
                        current_model=new_model_name,
                    )

        else:
            # Phase 3: 단일 inference 컨테이너 - 재시작으로 모델 교체
            service_name = "inference"
            service_url = "http://inference:8001"

            # 1. 현재 로드된 모델 확인
            success, current_model_name = await _get_model_info(service_url)

            # 이미 원하는 모델이 로드된 경우
            if success and target_model.lower() == current_model_name.lower():
                return ModelSwitchResult(
                    success=True,
                    message=f"Phase 3: 이미 {model_type} 모델({target_model})이 로드되어 있습니다.",
                    current_model=target_model,
                    switch_time_seconds=round(time.time() - start_time, 1),
                )

            # 2. 모델이 다르면 컨테이너 재시작
            print(f"🔄 Phase 3: {current_model_name} → {target_model} 모델 교체 중...")

            # 환경변수 설정
            env_vars = {"CHAT_MODEL": target_model}

            # 서비스 재시작
            restart_success, restart_msg = await _restart_service(
                compose_file, service_name, env_vars
            )
            if not restart_success:
                return ModelSwitchResult(
                    success=False,
                    message=f"Phase 3: {service_name} 재시작 실패 - {restart_msg}",
                    current_model=current_model_name if success else "unknown",
                )

            # 3. 헬스체크 대기
            print("⏳ Phase 3: 새 모델 로딩 대기 중...")
            if not await _wait_for_health(service_url, max_wait=30):
                return ModelSwitchResult(
                    success=False,
                    message="Phase 3: 모델 교체 후 서버가 응답하지 않습니다 (30초 타임아웃)",
                    current_model="unknown",
                )

            # 4. 재시작 후 모델 검증
            success, new_model_name = await _get_model_info(service_url)
            end_time = time.time()

            if success and new_model_name.lower() == target_model.lower():
                return ModelSwitchResult(
                    success=True,
                    message=f"Phase 3: {model_type} 모델({target_model})로 성공적으로 교체되었습니다.",
                    current_model=new_model_name,
                    switch_time_seconds=round(end_time - start_time, 1),
                )
            else:
                return ModelSwitchResult(
                    success=False,
                    message=f"Phase 3: 재시작 후 모델 검증 실패 (현재: {new_model_name}, 기대: {target_model})",
                    current_model=new_model_name,
                )

    except Exception as e:
        return ModelSwitchResult(
            success=False,
            message=f"모델 교체 중 오류 발생: {str(e)}",
            current_model="unknown",
        )


@mcp.tool()
async def get_current_model() -> Dict[str, Any]:
    """
    현재 로드된 모델 정보를 조회합니다.

    Phase 2: inference-chat (chat 모델), inference-code (code 모델) 모두 조회
    Phase 3: 단일 inference 컨테이너 조회
    """
    try:
        # Phase 감지
        is_phase2, compose_file = await _detect_phase()
        if is_phase2 is None:
            return {
                "error": "Phase 감지 실패: docker compose 서비스 목록을 확인할 수 없습니다."
            }

        if is_phase2:
            # Phase 2: 두 서비스 모두 조회
            chat_success, chat_model = await _get_model_info(
                "http://inference-chat:8001"
            )
            code_success, code_model = await _get_model_info(
                "http://inference-code:8001"
            )

            return {
                "phase": "Phase 2 (Dual LLM)",
                "chat_model": chat_model if chat_success else "unavailable",
                "code_model": code_model if code_success else "unavailable",
                "service_chat": "inference-chat:8001",
                "service_code": "inference-code:8004",
                "compose_file": compose_file,
            }

        else:
            # Phase 3: 단일 inference 컨테이너 조회
            success, model_name = await _get_model_info("http://inference:8001")

            if success:
                # 모델 타입 추정
                model_type = "code" if "coder" in model_name.lower() else "chat"

                return {
                    "phase": "Phase 3 (Single LLM)",
                    "current_model": model_name,
                    "model_type": model_type,
                    "service": "inference:8001",
                    "compose_file": compose_file,
                }
            else:
                return {
                    "phase": "Phase 3",
                    "error": "모델 정보를 가져올 수 없습니다.",
                    "compose_file": compose_file,
                }

    except Exception as e:
        return {"error": f"모델 정보 조회 실패: {str(e)}"}


# =============================================================================
# 서버 실행
# =============================================================================


async def start_security_admin_server():
    """보안 관리 API 서버를 별도 포트에서 실행"""
    import uvicorn

    security_host = _resolve_host("MCP_SECURITY_HOST")
    security_port = int(os.getenv("MCP_SECURITY_PORT", "8021"))
    config = uvicorn.Config(
        security_app,
        host=security_host,
        port=security_port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def start_main_server():
    """메인 MCP 서버 실행"""
    import uvicorn

    mcp_host = _resolve_host("MCP_SERVER_HOST")
    mcp_port = int(os.getenv("MCP_SERVER_PORT", "8020"))
    config = uvicorn.Config(
        app,
        host=mcp_host,
        port=mcp_port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    """메인 서버와 보안 관리 API 서버를 동시 실행"""
    await asyncio.gather(start_main_server(), start_security_admin_server())


if __name__ == "__main__":
    # HTTP 모드: FastAPI + 보안 관리 API 동시 실행
    if len(sys.argv) > 1 and sys.argv[1] == "--http":
        asyncio.run(main())
    else:
        # 기본 모드: HTTP 모드로 실행 (헬스체크 지원)
        asyncio.run(main())
