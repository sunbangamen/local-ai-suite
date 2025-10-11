#!/usr/bin/env python3
"""
Memory API Router for API Gateway
메모리 시스템 REST API 엔드포인트 구현
"""

import os
import sys
import time
import uuid
import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query, Body, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import asyncio

# 기본 로거 먼저 초기화 (다른 임포트보다 우선)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("memory-api")

# Prometheus 메트릭 라이브러리 (logger 초기화 후)
try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )

    PROMETHEUS_AVAILABLE = True

    # 메트릭 정의
    REQUEST_COUNT = Counter(
        "memory_api_requests_total", "Total requests", ["method", "endpoint", "status"]
    )
    REQUEST_DURATION = Histogram(
        "memory_api_request_duration_seconds",
        "Request duration",
        ["method", "endpoint"],
    )
    ACTIVE_CONVERSATIONS = Gauge(
        "memory_api_active_conversations",
        "Number of active conversations",
        ["project_id"],
    )
    VECTOR_SEARCH_ENABLED = Gauge(
        "memory_api_vector_search_enabled", "Vector search availability"
    )

except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("Prometheus client not available, metrics disabled")

# 공통 로깅 시스템 업그레이드 시도 (선택적)
try:
    sys.path.append("/app")
    from shared.logging_config import create_service_logger

    logger = create_service_logger("memory-api")
    logger.info("Using enhanced logging system")
except ImportError:
    logger.info("Using basic logging system")

# 메모리 시스템 임포트를 위한 경로 추가 (Docker 볼륨 마운트를 통해 접근)
sys.path.append("/app/scripts")

try:
    from memory_system import MemorySystem, get_memory_system
except ImportError:
    print("⚠️ Warning: memory_system module not found")

    # Mock 클래스 (fallback)
    class MemorySystem:
        def __init__(self):
            pass

        def get_project_id(self, path=None):
            return "mock-project"

        def save_conversation(self, *args, **kwargs):
            return 1

        def search_conversations(self, *args, **kwargs):
            return []

        def get_conversation_stats(self, *args, **kwargs):
            return {}


# Pydantic 모델들
class ConversationSave(BaseModel):
    user_query: str
    ai_response: str
    model_used: Optional[str] = None
    session_id: Optional[str] = None
    token_count: Optional[int] = None
    response_time_ms: Optional[int] = None
    tags: Optional[List[str]] = None
    context: Optional[Dict[str, Any]] = None
    project_path: Optional[str] = None


class ConversationSearch(BaseModel):
    query: Optional[str] = None
    importance_min: Optional[int] = None
    limit: int = 10
    offset: int = 0
    use_vector_search: bool = False
    project_id: Optional[str] = None


class MemoryBackup(BaseModel):
    backup_type: str = "json"  # "json" or "sql"


class MemorySync(BaseModel):
    sync_type: str = "qdrant"  # "qdrant" only for now
    batch_size: int = 64


# FastAPI 앱 생성
memory_app = FastAPI(
    title="AI Memory API",
    description="프로젝트별 장기 기억 시스템 API",
    version="1.0.0",
    docs_url="/v1/memory/docs",
    redoc_url="/v1/memory/redoc",
)

# CORS 미들웨어
memory_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 로깅 미들웨어
@memory_app.middleware("http")
async def logging_middleware(request: Request, call_next):
    # 요청 ID 생성
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    # 요청 로그
    logger.info(f"[{request_id}] 요청 시작: {request.method} {request.url.path}")

    try:
        # 실제 요청 처리
        response = await call_next(request)

        # 처리 시간 계산
        duration_ms = (time.time() - start_time) * 1000

        # 응답 로깅
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} "
            f"-> {response.status_code} ({duration_ms:.2f}ms)"
        )

        # Prometheus 메트릭 수집
        if PROMETHEUS_AVAILABLE:
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=str(request.url.path),
                status=response.status_code,
            ).inc()
            REQUEST_DURATION.labels(
                method=request.method, endpoint=str(request.url.path)
            ).observe(
                duration_ms / 1000
            )  # seconds

        return response

    except Exception as e:
        # 에러 로깅
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"[{request_id}] {request.method} {request.url.path} "
            f"-> 500 ({duration_ms:.2f}ms) Error: {str(e)}"
        )
        raise


# 메모리 시스템 인스턴스
memory_system = get_memory_system()
logger.info("메모리 시스템 초기화 완료")


@memory_app.get("/v1/memory/health")
async def health_check():
    """메모리 시스템 헬스체크"""
    try:
        # 간단한 동작 테스트
        test_project_id = memory_system.get_project_id()
        stats = memory_system.get_conversation_stats(test_project_id)

        # 벡터 기능 복구 시도 (비활성화 상태인 경우)
        if not memory_system._vector_enabled:
            recovery_attempted = memory_system.try_vector_recovery(test_project_id)
            recovery_status = "attempted" if recovery_attempted else "failed"
        else:
            recovery_status = "not_needed"

        return {
            "status": "healthy",
            "memory_system": "available",
            "storage_available": memory_system._storage_available,
            "vector_enabled": memory_system._vector_enabled,
            "vector_recovery": recovery_status,
            "test_project_id": test_project_id,
            "test_stats": stats,
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e), "memory_system": "error"},
        )


@memory_app.post("/v1/memory/conversations")
async def save_conversation(conversation: ConversationSave):
    """대화 저장"""
    try:
        # 프로젝트 ID 결정 (Docker 환경에서는 환경변수 우선)
        project_id = os.getenv("DEFAULT_PROJECT_ID") or memory_system.get_project_id(
            conversation.project_path
        )

        # 대화 저장
        conversation_id = memory_system.save_conversation(
            project_id=project_id,
            user_query=conversation.user_query,
            ai_response=conversation.ai_response,
            model_used=conversation.model_used,
            session_id=conversation.session_id,
            token_count=conversation.token_count,
            response_time_ms=conversation.response_time_ms,
            context=conversation.context,
            tags=conversation.tags,
        )

        if conversation_id is None:
            raise HTTPException(status_code=500, detail="Failed to save conversation")

        return {
            "success": True,
            "conversation_id": conversation_id,
            "project_id": project_id,
            "message": "Conversation saved successfully",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving conversation: {e}")


@memory_app.post("/v1/memory/conversations/search")
async def search_conversations(search: ConversationSearch):
    """대화 검색"""
    try:
        # 프로젝트 ID 결정
        project_id = search.project_id or memory_system.get_project_id()

        if search.use_vector_search and search.query:
            # 벡터 검색 (비동기)
            results = await memory_system.vector_search_conversations(
                project_id=project_id, query=search.query, limit=search.limit
            )
        else:
            # FTS5 검색
            results = memory_system.search_conversations(
                project_id=project_id,
                query=search.query,
                importance_min=search.importance_min,
                limit=search.limit,
                offset=search.offset,
            )

        return {
            "success": True,
            "project_id": project_id,
            "results": results,
            "total_results": len(results),
            "search_type": "vector" if search.use_vector_search else "fts5",
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error searching conversations: {e}"
        )


@memory_app.get("/v1/memory/projects/{project_id}/stats")
async def get_project_stats(project_id: str):
    """프로젝트 메모리 통계"""
    try:
        stats = memory_system.get_conversation_stats(project_id)

        return {"success": True, "project_id": project_id, "stats": stats}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting stats: {e}")


@memory_app.post("/v1/memory/projects/{project_id}/cleanup")
async def cleanup_project_memory(project_id: str):
    """프로젝트 메모리 TTL 정리"""
    try:
        deleted_count = memory_system.cleanup_expired_conversations(project_id)

        return {
            "success": True,
            "project_id": project_id,
            "deleted_conversations": deleted_count,
            "message": f"Cleaned up {deleted_count} expired conversations",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cleaning up memory: {e}")


@memory_app.post("/v1/memory/projects/{project_id}/backup")
async def create_memory_backup(project_id: str, backup: MemoryBackup):
    """메모리 백업 생성"""
    try:
        backup_path = memory_system.export_memory_backup(project_id)

        if backup_path:
            return {
                "success": True,
                "project_id": project_id,
                "backup_path": str(backup_path),
                "backup_type": backup.backup_type,
                "message": "Backup created successfully",
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to create backup")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating backup: {e}")


@memory_app.post("/v1/memory/projects/{project_id}/sync")
async def sync_project_vectors(project_id: str, sync_config: MemorySync):
    """프로젝트 벡터 동기화"""
    try:
        if sync_config.sync_type == "qdrant":
            # Qdrant 동기화
            sync_stats = memory_system.batch_sync_to_qdrant(
                project_id=project_id, batch_size=sync_config.batch_size
            )

            return {
                "success": True,
                "project_id": project_id,
                "sync_stats": sync_stats,
                "message": f"Synchronized {sync_stats['synced']} conversations to Qdrant",
            }
        else:
            raise HTTPException(status_code=400, detail="Unsupported sync type")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error syncing vectors: {e}")


@memory_app.post("/v1/memory/projects/{project_id}/sync/retry")
async def retry_failed_syncs(project_id: str):
    """실패한 동기화 재시도"""
    try:
        retry_stats = memory_system.retry_failed_syncs(project_id)

        return {
            "success": True,
            "project_id": project_id,
            "retry_stats": retry_stats,
            "message": f"Retried {retry_stats['retried']} failed syncs, {retry_stats['succeeded']} succeeded",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrying syncs: {e}")


@memory_app.get("/v1/memory/projects/{project_id}/sync/queue")
async def get_sync_queue(project_id: str, include_failed: bool = Query(False)):
    """동기화 대기열 조회"""
    try:
        queue = memory_system.get_qdrant_sync_queue(
            project_id=project_id, limit=100, include_failed=include_failed
        )

        return {
            "success": True,
            "project_id": project_id,
            "queue_size": len(queue),
            "queue": queue,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting sync queue: {e}")


@memory_app.post("/v1/memory/projects/{project_id}/optimize")
async def optimize_project_database(project_id: str):
    """데이터베이스 최적화"""
    try:
        success = memory_system.optimize_database(project_id)

        if success:
            return {
                "success": True,
                "project_id": project_id,
                "message": "Database optimized successfully",
            }
        else:
            raise HTTPException(status_code=500, detail="Database optimization failed")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error optimizing database: {e}")


@memory_app.post("/v1/memory/projects/{project_id}/fts/rebuild")
async def rebuild_fts_index(project_id: str):
    """FTS5 인덱스 재구축"""
    try:
        success = memory_system.rebuild_fts_index(project_id)

        if success:
            return {
                "success": True,
                "project_id": project_id,
                "message": "FTS5 index rebuilt successfully",
            }
        else:
            raise HTTPException(status_code=500, detail="FTS5 index rebuild failed")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error rebuilding FTS index: {e}")


@memory_app.post("/v1/memory/vector/recovery")
async def recover_vector_functionality():
    """벡터 기능 수동 복구 시도"""
    try:
        # 기본 프로젝트 ID로 복구 시도
        test_project_id = memory_system.get_project_id()
        recovery_success = memory_system.try_vector_recovery(test_project_id)

        if recovery_success:
            return {
                "success": True,
                "vector_enabled": memory_system._vector_enabled,
                "message": "Vector functionality recovered successfully",
            }
        else:
            return {
                "success": False,
                "vector_enabled": memory_system._vector_enabled,
                "message": "Vector recovery failed - Qdrant may still be unavailable",
            }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error recovering vector functionality: {e}"
        )


# Prometheus 메트릭 엔드포인트
@memory_app.get("/metrics")
async def metrics():
    """Prometheus 메트릭 노출"""
    if not PROMETHEUS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Prometheus metrics not available")

    try:
        # 실시간 메트릭 업데이트
        if hasattr(memory_system, "_vector_enabled"):
            VECTOR_SEARCH_ENABLED.set(1 if memory_system._vector_enabled else 0)

        # 프로젝트별 대화 수 업데이트 (기본 프로젝트만)
        try:
            project_id = memory_system.get_project_id()
            stats = memory_system.get_conversation_stats(project_id)
            if stats and "total_conversations" in stats:
                ACTIVE_CONVERSATIONS.labels(project_id=project_id).set(
                    stats["total_conversations"]
                )
        except Exception:
            pass  # 메트릭 업데이트 실패는 무시

        # Prometheus 형식으로 메트릭 반환
        return JSONResponse(
            content=generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST
        )

    except Exception as e:
        logger.error(f"메트릭 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating metrics: {e}")


# 애플리케이션 시작 시 초기 메트릭 설정
def initialize_metrics():
    """애플리케이션 시작 시 메트릭 초기화"""
    if PROMETHEUS_AVAILABLE:
        logger.info("Prometheus 메트릭 초기화됨")
        # 벡터 검색 상태 초기화
        try:
            if hasattr(memory_system, "_vector_enabled"):
                VECTOR_SEARCH_ENABLED.set(1 if memory_system._vector_enabled else 0)
        except Exception:
            VECTOR_SEARCH_ENABLED.set(0)


# 초기화 실행
initialize_metrics()


@memory_app.get("/v1/memory/projects")
async def list_projects():
    """모든 프로젝트 목록"""
    try:
        # 프로젝트 디렉토리 스캔
        projects_dir = memory_system.projects_dir
        projects = []

        if projects_dir.exists():
            for project_dir in projects_dir.iterdir():
                if project_dir.is_dir():
                    project_id = project_dir.name
                    memory_db = project_dir / "memory.db"

                    if memory_db.exists():
                        stats = memory_system.get_conversation_stats(project_id)
                        projects.append(
                            {
                                "project_id": project_id,
                                "database_path": str(memory_db),
                                "total_conversations": stats.get(
                                    "total_conversations", 0
                                ),
                                "avg_importance": stats.get("avg_importance", 0),
                                "latest_conversation": stats.get("latest_conversation"),
                            }
                        )

        return {"success": True, "total_projects": len(projects), "projects": projects}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing projects: {e}")


# 예외 처리
@memory_app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "error": "Endpoint not found",
            "available_endpoints": [
                "/v1/memory/health",
                "/v1/memory/conversations",
                "/v1/memory/conversations/search",
                "/v1/memory/projects",
                "/v1/memory/projects/{project_id}/stats",
                "/v1/memory/projects/{project_id}/cleanup",
                "/v1/memory/projects/{project_id}/backup",
                "/v1/memory/projects/{project_id}/sync",
                "/v1/memory/projects/{project_id}/optimize",
                "/v1/memory/vector/recovery",
            ],
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(memory_app, host="0.0.0.0", port=8005)
