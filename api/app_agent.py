"""
FastAPI application with Agent SDK integration.

This version uses Claude Agent SDK instead of Temporal/standalone executor.
Claude intelligently orchestrates Spotify MCP tools.

Supports both local development (in-memory) and Firebase Functions (Firestore).
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

# Firestore client for persistent storage (initialized lazily)
_firestore_client = None
_firestore_enabled = None

def get_firestore_client():
    """
    Get or create Firestore client.

    Returns Firestore client if USE_FIRESTORE=true, otherwise None.
    This allows explicit control over Firestore usage and storage costs.
    """
    global _firestore_client, _firestore_enabled

    # Check if Firestore is enabled via config flag
    if _firestore_enabled is None:
        from config.settings import settings
        _firestore_enabled = settings.use_firestore

    if not _firestore_enabled:
        logger.info("Firestore disabled (USE_FIRESTORE=false), using in-memory storage")
        return None

    if _firestore_client is None:
        try:
            from firebase_admin import firestore, initialize_app
            import firebase_admin

            # Initialize Firebase Admin if not already initialized
            try:
                initialize_app()
            except ValueError:
                # Already initialized
                pass

            _firestore_client = firestore.client()
            logger.info("✅ Firestore client initialized (USE_FIRESTORE=true)")
        except Exception as e:
            logger.warning(f"Firestore initialization failed, using in-memory storage: {e}")
            # Fallback to in-memory
            _firestore_client = None

    return _firestore_client

# In-memory storage as fallback (for local development)
execution_results: dict[str, AgentExecutionResult] = {}


@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    from config.settings import settings

    logger.info("🚀 Starting FastAPI server with Claude Agent SDK integration")
    logger.info("🎵 Ready to sync songs intelligently using AI!")

    # Log storage mode
    if settings.use_firestore:
        logger.info("📊 Storage: Firestore enabled (persistent across instances)")
    else:
        logger.info("💾 Storage: In-memory only (fire-and-forget mode)")
        logger.info("⚠️  Status endpoint may not find results across different function instances")


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

    # Execute sync task in background thread (continues after HTTP response)
    # Using thread instead of asyncio.create_task() because Firebase Functions
    # may terminate async tasks after HTTP response, but threads continue
    import threading

    def run_sync_in_thread():
        """Wrapper to run async task in thread."""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_execute_sync_task(
                workflow_id=workflow_id,
                song_metadata=song_metadata,
                playlist_id=request.playlist_id,
                user_id=user_id,
                use_ai_disambiguation=request.use_ai_disambiguation
            ))
        finally:
            loop.close()

    # Start background thread
    thread = threading.Thread(target=run_sync_in_thread, daemon=False)
    thread.start()

    logger.info(f"[{workflow_id}] Background thread started for agent processing")

    # Check if Firestore is enabled for status URL
    from config.settings import settings
    status_url = f"/api/v1/sync/{workflow_id}" if settings.use_firestore else None

    return SyncSongResponse(
        workflow_id=workflow_id,
        status="accepted",
        message=f"Agent is searching for '{request.track_name}' by {request.artist}...",
        status_url=status_url,
    )


async def _execute_sync_task(
    workflow_id: str,
    song_metadata: SongMetadata,
    playlist_id: str,
    user_id: str,
    use_ai_disambiguation: bool
):
    """Execute the sync task in background and cache results."""
    db = get_firestore_client()

    try:
        logger.info(f"[{workflow_id}] Calling Agent SDK...")

        result = await execute_music_sync_with_agent(
            song_metadata=song_metadata,
            playlist_id=playlist_id,
            user_id=user_id,
            use_ai_disambiguation=use_ai_disambiguation
        )

        # Store result in Firestore (if available) or in-memory
        if db:
            try:
                db.collection('sync_results').document(workflow_id).set({
                    'workflow_id': workflow_id,
                    'success': result.success,
                    'message': result.message,
                    'matched_track_uri': result.matched_track_uri,
                    'matched_track_name': result.matched_track_name,
                    'matched_artist': result.matched_artist,
                    'confidence_score': result.confidence_score,
                    'match_method': result.match_method,
                    'execution_time_seconds': result.execution_time_seconds,
                    'agent_reasoning': result.agent_reasoning,
                    'error': result.error,
                    'timestamp': firestore.SERVER_TIMESTAMP
                })
                logger.info(f"[{workflow_id}] Stored result in Firestore")
            except Exception as e:
                logger.warning(f"[{workflow_id}] Failed to store in Firestore: {e}")
                execution_results[workflow_id] = result
        else:
            # Fallback to in-memory
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
        error_result = AgentExecutionResult(
            success=False,
            message=f"Exception: {str(e)}",
            error=str(e)
        )

        if db:
            try:
                db.collection('sync_results').document(workflow_id).set({
                    'workflow_id': workflow_id,
                    'success': False,
                    'error': str(e),
                    'message': f"Exception: {str(e)}",
                    'timestamp': firestore.SERVER_TIMESTAMP
                })
            except:
                execution_results[workflow_id] = error_result
        else:
            execution_results[workflow_id] = error_result


@app.get("/api/v1/sync/{workflow_id}", response_model=WorkflowStatusResponse)
async def get_sync_status(workflow_id: str) -> WorkflowStatusResponse:
    """
    Get status of a sync operation.

    Note: This endpoint requires USE_FIRESTORE=true to work reliably in production.
    With USE_FIRESTORE=false, results are only available in the same function instance.

    Args:
        workflow_id: The workflow ID returned from POST /api/v1/sync

    Returns:
        Current workflow status and results
    """
    from datetime import datetime
    from config.settings import settings

    # If Firestore is disabled, return error in production
    if not settings.use_firestore:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail={
                "error": "status_endpoint_disabled",
                "message": "Status endpoint is disabled when USE_FIRESTORE=false. "
                          "This is a fire-and-forget deployment with no persistent storage. "
                          "Enable USE_FIRESTORE=true to use status checks.",
                "workflow_id": workflow_id
            }
        )

    db = get_firestore_client()

    # Try to get result from Firestore first
    result = None
    if db:
        try:
            doc = db.collection('sync_results').document(workflow_id).get()
            if doc.exists:
                data = doc.to_dict()
                result = AgentExecutionResult(
                    success=data.get('success', False),
                    message=data.get('message', ''),
                    matched_track_uri=data.get('matched_track_uri'),
                    matched_track_name=data.get('matched_track_name'),
                    matched_artist=data.get('matched_artist'),
                    confidence_score=data.get('confidence_score'),
                    match_method=data.get('match_method'),
                    execution_time_seconds=data.get('execution_time_seconds'),
                    agent_reasoning=data.get('agent_reasoning'),
                    error=data.get('error')
                )
        except Exception as e:
            logger.warning(f"Failed to read from Firestore: {e}")

    # Fallback to in-memory storage
    if result is None and workflow_id in execution_results:
        result = execution_results[workflow_id]

    # If no result found, return running status
    if result is None:
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
