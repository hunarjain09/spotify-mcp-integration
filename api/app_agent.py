"""
FastAPI application with Agent SDK integration.

This version uses Claude Agent SDK instead of Temporal/standalone executor.
Claude intelligently orchestrates Spotify MCP tools.
"""
import asyncio
import logging
import time
import uuid
from typing import Optional, Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from api.models import SyncSongRequest, SyncSongResponse, WorkflowStatusResponse
from models.data_models import SongMetadata
from agent_executor import execute_music_sync_with_agent, AgentExecutionResult

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Spotify Sync API (Agent-Powered)",
    description="Sync songs to Spotify using Claude Agent SDK + MCP",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for execution results (for status endpoint)
execution_results: dict[str, AgentExecutionResult] = {}


@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    logger.info("🚀 Starting FastAPI server with Claude Agent SDK integration")
    logger.info("🎵 Ready to sync songs intelligently using AI!")


@app.post("/api/v1/sync", response_model=SyncSongResponse, status_code=status.HTTP_202_ACCEPTED)
async def sync_song(request: SyncSongRequest) -> SyncSongResponse:
    """
    Sync a song to Spotify playlist using Claude Agent SDK.

    The Agent (Claude) will:
    1. Search Spotify for the track
    2. Intelligently pick the best match (with AI reasoning)
    3. Add to the specified playlist
    4. Verify the addition
    5. Return structured results

    Args:
        request: Song sync request with track metadata

    Returns:
        Workflow ID and status URL
    """
    # Generate workflow ID
    user_id = request.user_id or "anonymous"
    timestamp = int(time.time())
    random_suffix = uuid.uuid4().hex[:5]
    workflow_id = f"agent-sync-{user_id}-{timestamp}-{random_suffix}"

    logger.info(f"[{workflow_id}] Starting agent-based sync for: {request.track_name} by {request.artist}")

    # Create song metadata
    song_metadata = SongMetadata(
        title=request.track_name,
        artist=request.artist,
        album=request.album
    )

    # Execute in background task (fire-and-forget)
    asyncio.create_task(
        _execute_sync_task(
            workflow_id=workflow_id,
            song_metadata=song_metadata,
            playlist_id=request.playlist_id,
            user_id=user_id,
            use_ai_disambiguation=request.use_ai_disambiguation
        )
    )

    return SyncSongResponse(
        workflow_id=workflow_id,
        status="accepted",
        message=f"Agent is searching for '{request.track_name}' by {request.artist}...",
        status_url=f"/api/v1/sync/{workflow_id}",
    )


async def _execute_sync_task(
    workflow_id: str,
    song_metadata: SongMetadata,
    playlist_id: str,
    user_id: str,
    use_ai_disambiguation: bool
):
    """Execute the sync task in background and cache results."""
    try:
        logger.info(f"[{workflow_id}] Calling Agent SDK...")

        result = await execute_music_sync_with_agent(
            song_metadata=song_metadata,
            playlist_id=playlist_id,
            user_id=user_id,
            use_ai_disambiguation=use_ai_disambiguation
        )

        # Cache result for status endpoint
        execution_results[workflow_id] = result

        if result.success:
            logger.info(
                f"[{workflow_id}] ✅ Success! "
                f"Matched: {result.matched_track_name} by {result.matched_artist} "
                f"({result.match_method})"
            )
        else:
            logger.error(f"[{workflow_id}] ❌ Failed: {result.error}")

    except Exception as e:
        logger.error(f"[{workflow_id}] Exception during agent execution: {e}", exc_info=True)
        execution_results[workflow_id] = AgentExecutionResult(
            success=False,
            message=f"Exception: {str(e)}",
            error=str(e)
        )


@app.get("/api/v1/sync/{workflow_id}", response_model=WorkflowStatusResponse)
async def get_sync_status(workflow_id: str) -> WorkflowStatusResponse:
    """
    Get status of a sync operation.

    Args:
        workflow_id: The workflow ID returned from POST /api/v1/sync

    Returns:
        Current workflow status and results
    """
    from datetime import datetime

    # Check if we have results for this workflow
    if workflow_id not in execution_results:
        # Still running or doesn't exist
        from api.models import WorkflowProgressInfo
        return WorkflowStatusResponse(
            workflow_id=workflow_id,
            status="running",
            started_at=datetime.now(),
            progress=WorkflowProgressInfo(
                current_step="agent_processing",
                steps_completed=1,
                steps_total=4,
                candidates_found=0,
                elapsed_seconds=0.0
            )
        )

    result = execution_results[workflow_id]

    if result.success:
        from api.models import WorkflowResultInfo
        # Extract track ID from URI (format: spotify:track:TRACK_ID)
        spotify_track_id = None
        if result.matched_track_uri:
            spotify_track_id = result.matched_track_uri.split(":")[-1]

        return WorkflowStatusResponse(
            workflow_id=workflow_id,
            status="completed",
            started_at=datetime.now(),
            completed_at=datetime.now(),
            result=WorkflowResultInfo(
                success=True,
                message=result.message,
                spotify_track_id=spotify_track_id,
                spotify_track_uri=result.matched_track_uri,
                confidence_score=result.confidence_score or 0.0,
                execution_time_seconds=result.execution_time_seconds or 0.0,
                retry_count=0,
                match_method=result.match_method
            )
        )
    else:
        return WorkflowStatusResponse(
            workflow_id=workflow_id,
            status="failed",
            started_at=datetime.now(),
            completed_at=datetime.now(),
            error=result.error
        )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "mode": "agent_sdk",
        "message": "Agent-powered Spotify sync is operational"
    }


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Spotify Sync API",
        "version": "2.0.0",
        "mode": "agent_sdk",
        "description": "AI-powered music sync using Claude Agent SDK + MCP",
        "endpoints": {
            "docs": "/docs",
            "sync": "POST /api/v1/sync",
            "status": "GET /api/v1/sync/{workflow_id}",
            "health": "/health"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
