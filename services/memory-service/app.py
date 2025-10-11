"""
Memory Service - RESTful API for AI Memory System
Provides OpenAI-compatible memory endpoints for conversation storage and retrieval
"""

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import sys
import os
from pathlib import Path
from datetime import datetime

# Add parent directories to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from memory_system import MemorySystem

# Initialize FastAPI
app = FastAPI(
    title="AI Memory Service",
    description="Long-term conversation memory storage and retrieval",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize memory system
memory_system = MemorySystem(data_dir=os.getenv("MEMORY_DATA_DIR", "/mnt/e/ai-data/memory"))


# Pydantic models
class ConversationCreate(BaseModel):
    user_query: str = Field(..., description="User's question or prompt")
    ai_response: str = Field(..., description="AI's response")
    model_used: Optional[str] = Field(None, description="Model used for response")
    session_id: Optional[str] = Field(None, description="Session ID for grouping")
    response_time_ms: Optional[int] = Field(None, description="Response time in milliseconds")
    token_count: Optional[int] = Field(None, description="Token count")
    project_path: Optional[str] = Field(None, description="Project path for project ID")
    tags: Optional[List[str]] = Field(None, description="Tags for categorization")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class ConversationResponse(BaseModel):
    conversation_id: int
    project_id: str
    importance_score: int
    success: bool = True


class SearchQuery(BaseModel):
    query: str = Field(..., description="Search query")
    project_path: Optional[str] = Field(None, description="Project path for project ID")
    importance_min: Optional[int] = Field(None, ge=1, le=10, description="Minimum importance score")
    limit: int = Field(10, ge=1, le=100, description="Maximum results")
    offset: int = Field(0, ge=0, description="Result offset for pagination")
    use_vector: bool = Field(False, description="Use vector search (hybrid mode)")


class MemoryStats(BaseModel):
    project_id: str
    total_conversations: int
    avg_importance: float
    oldest_conversation: Optional[str]
    latest_conversation: Optional[str]
    importance_distribution: Dict[int, int]
    model_usage: Dict[str, int]
    vector_enabled: bool
    storage_available: bool


class HealthResponse(BaseModel):
    status: str
    storage_available: bool
    vector_enabled: bool
    timestamp: str


# Background task for vector embedding
async def process_embeddings_background(project_id: str):
    """Background task to process pending embeddings"""
    try:
        processed = await memory_system.process_pending_embeddings(project_id, batch_size=10)
        if processed > 0:
            print(f"✅ Processed {processed} embeddings for project {project_id}")
    except Exception as e:
        print(f"⚠️ Embedding background task failed: {e}")


# Routes
@app.get("/", response_model=Dict[str, str])
async def root():
    """Service information"""
    return {"service": "AI Memory Service", "version": "1.0.0", "status": "running"}


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        storage_available=memory_system._storage_available,
        vector_enabled=memory_system._vector_enabled,
        timestamp=datetime.now().isoformat(),
    )


@app.post("/v1/memory/conversations", response_model=ConversationResponse)
async def create_conversation(conversation: ConversationCreate, background_tasks: BackgroundTasks):
    """
    Save a conversation to memory
    OpenAI-compatible endpoint
    """
    try:
        # Determine project ID
        if conversation.project_path:
            project_id = memory_system.get_project_id(conversation.project_path)
        else:
            project_id = memory_system.get_project_id()

        # Save conversation
        conversation_id = memory_system.save_conversation(
            project_id=project_id,
            user_query=conversation.user_query,
            ai_response=conversation.ai_response,
            model_used=conversation.model_used,
            session_id=conversation.session_id,
            response_time_ms=conversation.response_time_ms,
            token_count=conversation.token_count,
            context=conversation.context,
            tags=conversation.tags,
        )

        if conversation_id is None:
            raise HTTPException(status_code=500, detail="Failed to save conversation")

        # Get importance score
        with memory_system.transaction(project_id) as conn:
            cursor = conn.execute(
                "SELECT importance_score FROM conversations WHERE id = ?",
                (conversation_id,),
            )
            row = cursor.fetchone()
            importance_score = row["importance_score"] if row else 5

        # Schedule background embedding processing
        background_tasks.add_task(process_embeddings_background, project_id)

        return ConversationResponse(
            conversation_id=conversation_id,
            project_id=project_id,
            importance_score=importance_score,
            success=True,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving conversation: {str(e)}")


@app.post("/v1/memory/search")
async def search_conversations(search: SearchQuery):
    """
    Search conversations in memory
    Supports both text (FTS5) and vector search
    """
    try:
        # Determine project ID
        if search.project_path:
            project_id = memory_system.get_project_id(search.project_path)
        else:
            project_id = memory_system.get_project_id()

        if search.use_vector and memory_system._vector_enabled:
            # Hybrid search (FTS5 + vector)
            results = await memory_system.hybrid_search_conversations(
                project_id=project_id, query=search.query, limit=search.limit
            )
        else:
            # Text-only search (FTS5)
            results = memory_system.search_conversations(
                project_id=project_id,
                query=search.query,
                importance_min=search.importance_min,
                limit=search.limit,
                offset=search.offset,
            )

        return {
            "query": search.query,
            "project_id": project_id,
            "results": results,
            "total": len(results),
            "search_type": "hybrid" if search.use_vector else "text",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")


@app.get("/v1/memory/stats")
async def get_stats(project_path: Optional[str] = Query(None)):
    """Get memory system statistics for a project"""
    try:
        if project_path:
            project_id = memory_system.get_project_id(project_path)
        else:
            project_id = memory_system.get_project_id()

        stats = memory_system.get_conversation_stats(project_id)

        return MemoryStats(
            project_id=project_id,
            total_conversations=stats.get("total_conversations", 0),
            avg_importance=stats.get("avg_importance", 0.0),
            oldest_conversation=stats.get("oldest_conversation"),
            latest_conversation=stats.get("latest_conversation"),
            importance_distribution=stats.get("importance_distribution", {}),
            model_usage=stats.get("model_usage", {}),
            vector_enabled=memory_system._vector_enabled,
            storage_available=memory_system._storage_available,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats error: {str(e)}")


@app.post("/v1/memory/cleanup")
async def cleanup_expired(project_path: Optional[str] = Query(None)):
    """Clean up expired conversations based on TTL"""
    try:
        if project_path:
            project_id = memory_system.get_project_id(project_path)
        else:
            project_id = memory_system.get_project_id()

        deleted_count = memory_system.cleanup_expired_conversations(project_id)

        return {
            "project_id": project_id,
            "deleted_count": deleted_count,
            "success": True,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup error: {str(e)}")


@app.post("/v1/memory/sync-vectors")
async def sync_vectors(
    project_path: Optional[str] = Query(None), batch_size: int = Query(64, ge=1, le=128)
):
    """Manually trigger vector synchronization to Qdrant"""
    try:
        if not memory_system._vector_enabled:
            return {
                "success": False,
                "message": "Vector search is not enabled",
                "synced": 0,
                "failed": 0,
            }

        if project_path:
            project_id = memory_system.get_project_id(project_path)
        else:
            project_id = memory_system.get_project_id()

        stats = memory_system.batch_sync_to_qdrant(project_id, batch_size)

        return {"project_id": project_id, "success": True, **stats}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync error: {str(e)}")


@app.get("/v1/memory/projects")
async def list_projects():
    """List all available memory projects"""
    try:
        projects_dir = memory_system.projects_dir
        if not projects_dir.exists():
            return {"projects": []}

        projects = []
        for project_path in projects_dir.iterdir():
            if project_path.is_dir():
                project_file = project_path / ".ai-memory" / "project.json"
                if not project_file.exists():
                    # Check alternative location
                    project_file = project_path / "project.json"

                if project_file.exists():
                    import json

                    with open(project_file, "r") as f:
                        project_data = json.load(f)
                        projects.append(project_data)

        return {"projects": projects}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"List projects error: {str(e)}")


@app.post("/v1/memory/optimize")
async def optimize_database(project_path: Optional[str] = Query(None)):
    """Optimize database (VACUUM, ANALYZE)"""
    try:
        if project_path:
            project_id = memory_system.get_project_id(project_path)
        else:
            project_id = memory_system.get_project_id()

        success = memory_system.optimize_database(project_id)

        return {
            "project_id": project_id,
            "success": success,
            "message": ("Database optimized successfully" if success else "Optimization failed"),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimization error: {str(e)}")


@app.get("/v1/memory/conversation/{conversation_id}")
async def get_conversation(conversation_id: int, project_path: Optional[str] = Query(None)):
    """Get a specific conversation by ID"""
    try:
        if project_path:
            project_id = memory_system.get_project_id(project_path)
        else:
            project_id = memory_system.get_project_id()

        with memory_system.transaction(project_id) as conn:
            cursor = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
            row = cursor.fetchone()

            if row:
                import json

                result = dict(row)
                result["tags"] = json.loads(result.get("tags", "[]"))
                result["project_context"] = json.loads(result.get("project_context", "{}"))
                return result
            else:
                raise HTTPException(status_code=404, detail="Conversation not found")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Get conversation error: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("MEMORY_SERVICE_PORT", 8005))
    uvicorn.run(app, host="0.0.0.0", port=port)
