"""
FastAPI server for Apple Music to Spotify sync system.

DUAL-MODE ARCHITECTURE:
-----------------------
This API supports two execution modes controlled by the USE_TEMPORAL flag:

1. TEMPORAL MODE (use_temporal=true):
   - Uses Temporal for durable workflow orchestration
   - Requires Temporal server running
   - Provides advanced features: durable execution, distributed processing, replay

2. STANDALONE MODE (use_temporal=false):
   - Direct execution without Temporal dependency
   - Simpler deployment: just FastAPI + Spotify MCP
   - Fire-and-forget execution with basic retry logic
   - Ideal for development, testing, or low-traffic deployments

The API endpoints remain identical in both modes, ensuring seamless switching
between modes without client-side changes.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Optional, TYPE_CHECKING, Any
import uuid

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.settings import settings
from api.models import (
    SyncSongRequest,
    SyncSongResponse,
    WorkflowStatusResponse,
    WorkflowProgressInfo,
    WorkflowResultInfo,
    CancelWorkflowResponse,
    HealthCheckResponse,
    ErrorResponse,
)
from models.data_models import SongMetadata, WorkflowInput

# Type-only imports (for type checking, not runtime)
if TYPE_CHECKING:
    from temporalio.client import Client

# Conditional imports based on USE_TEMPORAL flag
if settings.use_temporal:
    from temporalio.client import Client, TLSConfig, WorkflowFailureError, WorkflowHandle
    from temporalio.exceptions import WorkflowAlreadyStartedError
    from workflows.music_sync_workflow import MusicSyncWorkflow
else:
    # Import standalone executor when Temporal is disabled
    from executors.standalone_executor import (
        run_standalone_workflow,
        get_workflow_progress,
        get_workflow_state,
    )


# Configure logging
logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Apple Music to Spotify Sync API",
    description="Sync songs from Apple Music to Spotify playlists",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware for iOS Shortcuts
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for iOS
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Temporal client (only used when use_temporal=true)
# Use Any type when Temporal is not imported to avoid NameError
temporal_client: Optional[Any] = None


@app.on_event("startup")
async def startup_event():
    """
    Initialize on startup.

    Behavior depends on USE_TEMPORAL flag:
    - If True: Connect to Temporal server
    - If False: Skip Temporal connection (standalone mode)
    """
    global temporal_client

    logger.info("Starting FastAPI server...")
    logger.info(f"Execution mode: {'TEMPORAL' if settings.use_temporal else 'STANDALONE'}")

    if settings.use_temporal:
        # TEMPORAL MODE: Connect to Temporal server
        logger.info(f"Connecting to Temporal at {settings.temporal_host}")

        # Prepare connection parameters
        connect_params = {
            "target_host": settings.temporal_host,
            "namespace": settings.temporal_namespace,
        }

        # Add TLS config for Temporal Cloud
        if settings.is_temporal_cloud:
            tls_config = settings.temporal_tls_config
            if tls_config:
                logger.info("Using TLS configuration for Temporal Cloud")
                connect_params["tls"] = TLSConfig(
                    client_cert=tls_config["client_cert"],
                    client_private_key=tls_config["client_private_key"],
                )

        try:
            temporal_client = await Client.connect(**connect_params)
            logger.info("✓ Connected to Temporal")
        except Exception as e:
            logger.error(f"✗ Failed to connect to Temporal: {e}")
            # Continue startup but mark as unhealthy
            temporal_client = None
    else:
        # STANDALONE MODE: No Temporal connection needed
        logger.info("✓ Running in standalone mode (no Temporal required)")
        temporal_client = None  # Explicitly None in standalone mode


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down FastAPI server...")


@app.post("/api/v1/sync", response_model=SyncSongResponse, status_code=status.HTTP_202_ACCEPTED)
async def sync_song(request: SyncSongRequest) -> SyncSongResponse:
    """
    Start a new song sync workflow (fire-and-forget).

    This endpoint works in both Temporal and standalone modes:
    - TEMPORAL MODE: Starts a durable Temporal workflow
    - STANDALONE MODE: Executes workflow directly in background task

    Args:
        request: Song sync request with track metadata

    Returns:
        Workflow ID and status URL

    Raises:
        HTTPException: If service is unavailable or workflow start fails
    """
    # Generate workflow ID
    user_id = request.user_id or "anonymous"
    timestamp = int(time.time())
    random_suffix = uuid.uuid4().hex[:5]
    workflow_id = f"sync-{user_id}-{timestamp}-{random_suffix}"

    # Create workflow input
    song_metadata = SongMetadata(
        title=request.track_name, artist=request.artist, album=request.album
    )

    workflow_input = WorkflowInput(
        song_metadata=song_metadata,
        playlist_id=request.playlist_id,
        user_id=user_id,
        match_threshold=request.match_threshold or 0.85,
        use_ai_disambiguation=request.use_ai_disambiguation,
    )

    if settings.use_temporal:
        # ============================================
        # TEMPORAL MODE: Use Temporal workflow
        # ============================================
        if temporal_client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Temporal client not connected",
            )

        try:
            # Start workflow (fire-and-forget)
            logger.info(f"[TEMPORAL] Starting workflow {workflow_id} for {song_metadata}")

            await temporal_client.start_workflow(
                MusicSyncWorkflow.run,
                workflow_input,
                id=workflow_id,
                task_queue=settings.task_queue_name,
            )

            logger.info(f"✓ Workflow started: {workflow_id}")

            return SyncSongResponse(
                workflow_id=workflow_id,
                status="accepted",
                message=f"Sync started for '{request.track_name}' by {request.artist}",
                status_url=f"/api/v1/sync/{workflow_id}",
            )

        except WorkflowAlreadyStartedError:
            # Idempotency: workflow with this ID already exists
            logger.warning(f"Workflow {workflow_id} already started")
            return SyncSongResponse(
                workflow_id=workflow_id,
                status="accepted",
                message=f"Sync already in progress for '{request.track_name}'",
                status_url=f"/api/v1/sync/{workflow_id}",
            )

        except Exception as e:
            logger.error(f"Failed to start workflow: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to start sync: {str(e)}",
            )

    else:
        # ============================================
        # STANDALONE MODE: Execute directly
        # ============================================
        logger.info(f"[STANDALONE] Starting workflow {workflow_id} for {song_metadata}")

        # Run workflow in background task (fire-and-forget)
        # Note: In production, consider using a task queue like Celery for better reliability
        asyncio.create_task(run_standalone_workflow(workflow_id, workflow_input))

        logger.info(f"✓ Workflow started in standalone mode: {workflow_id}")

        return SyncSongResponse(
            workflow_id=workflow_id,
            status="accepted",
            message=f"Sync started for '{request.track_name}' by {request.artist} (standalone mode)",
            status_url=f"/api/v1/sync/{workflow_id}",
        )


@app.get("/api/v1/sync/{workflow_id}", response_model=WorkflowStatusResponse)
async def get_workflow_status(workflow_id: str) -> WorkflowStatusResponse:
    """
    Get the status of a running or completed workflow.

    Works in both Temporal and standalone modes.

    Args:
        workflow_id: Workflow identifier

    Returns:
        Workflow status with progress or result

    Raises:
        HTTPException: If workflow not found or query fails
    """
    if settings.use_temporal:
        # ============================================
        # TEMPORAL MODE: Query Temporal workflow
        # ============================================
        if temporal_client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Temporal client not connected",
            )

        try:
            # Get workflow handle
            handle: WorkflowHandle = temporal_client.get_workflow_handle(workflow_id)

            # Try to describe workflow
            description = await handle.describe()

            # Determine status
            if description.status.name == "RUNNING":
                # Query for progress
                try:
                    progress = await handle.query(MusicSyncWorkflow.get_progress)
                    return WorkflowStatusResponse(
                        workflow_id=workflow_id,
                        status="running",
                        progress=WorkflowProgressInfo(
                            current_step=progress.current_step,
                            steps_completed=progress.steps_completed,
                            steps_total=progress.steps_total,
                            candidates_found=progress.candidates_found,
                            elapsed_seconds=progress.elapsed_seconds,
                        ),
                        started_at=description.start_time,
                    )
                except Exception as e:
                    logger.warning(f"Failed to query progress: {e}")
                    # Return running status without progress
                    return WorkflowStatusResponse(
                        workflow_id=workflow_id,
                        status="running",
                        started_at=description.start_time,
                    )

            elif description.status.name == "COMPLETED":
                # Get result
                result = await handle.result()
                return WorkflowStatusResponse(
                    workflow_id=workflow_id,
                    status="completed",
                    result=WorkflowResultInfo(
                        success=result.success,
                        message=result.message,
                        spotify_track_id=result.spotify_track_id,
                        spotify_track_uri=result.spotify_track_uri,
                        confidence_score=result.confidence_score,
                        execution_time_seconds=result.execution_time_seconds,
                        retry_count=result.retry_count,
                        match_method=result.match_method,
                    ),
                    started_at=description.start_time,
                    completed_at=description.close_time,
                )

            elif description.status.name == "FAILED":
                # Get failure info
                try:
                    await handle.result()
                except WorkflowFailureError as e:
                    return WorkflowStatusResponse(
                        workflow_id=workflow_id,
                        status="failed",
                        error=str(e.cause),
                        started_at=description.start_time,
                        completed_at=description.close_time,
                    )

            elif description.status.name == "CANCELED":
                return WorkflowStatusResponse(
                    workflow_id=workflow_id,
                    status="cancelled",
                    error="Workflow was cancelled",
                    started_at=description.start_time,
                    completed_at=description.close_time,
                )

            else:
                # Unknown status
                return WorkflowStatusResponse(
                    workflow_id=workflow_id,
                    status=description.status.name.lower(),
                    started_at=description.start_time,
                )

        except Exception as e:
            logger.error(f"Failed to get workflow status: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow {workflow_id} not found or query failed",
            )

    else:
        # ============================================
        # STANDALONE MODE: Query in-memory state
        # ============================================
        state = get_workflow_state(workflow_id)

        if state is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow {workflow_id} not found",
            )

        if state.status == "running":
            # Get progress
            progress = get_workflow_progress(workflow_id)
            return WorkflowStatusResponse(
                workflow_id=workflow_id,
                status="running",
                progress=WorkflowProgressInfo(
                    current_step=progress.current_step,
                    steps_completed=progress.steps_completed,
                    steps_total=progress.steps_total,
                    candidates_found=progress.candidates_found,
                    elapsed_seconds=progress.elapsed_seconds,
                ) if progress else None,
                started_at=datetime.fromtimestamp(state.start_time),
            )

        elif state.status == "completed" and state.result:
            return WorkflowStatusResponse(
                workflow_id=workflow_id,
                status="completed",
                result=WorkflowResultInfo(
                    success=state.result.success,
                    message=state.result.message,
                    spotify_track_id=state.result.spotify_track_id,
                    spotify_track_uri=state.result.spotify_track_uri,
                    confidence_score=state.result.confidence_score,
                    execution_time_seconds=state.result.execution_time_seconds,
                    retry_count=state.result.retry_count,
                    match_method=state.result.match_method,
                ),
                started_at=datetime.fromtimestamp(state.start_time),
                completed_at=datetime.fromtimestamp(state.start_time + state.result.execution_time_seconds) if state.result.execution_time_seconds else None,
            )

        elif state.status == "failed":
            return WorkflowStatusResponse(
                workflow_id=workflow_id,
                status="failed",
                error=state.error or "Workflow failed",
                started_at=datetime.fromtimestamp(state.start_time),
            )

        else:
            # Unknown status
            return WorkflowStatusResponse(
                workflow_id=workflow_id,
                status=state.status,
                started_at=datetime.fromtimestamp(state.start_time),
            )


@app.post("/api/v1/sync/{workflow_id}/cancel", response_model=CancelWorkflowResponse)
async def cancel_workflow(workflow_id: str) -> CancelWorkflowResponse:
    """Cancel a running workflow.

    Args:
        workflow_id: Workflow identifier

    Returns:
        Cancellation confirmation

    Raises:
        HTTPException: If workflow not found or cancellation fails
    """
    if temporal_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Temporal client not connected",
        )

    try:
        handle = temporal_client.get_workflow_handle(workflow_id)
        await handle.cancel()

        logger.info(f"✓ Workflow cancelled: {workflow_id}")

        return CancelWorkflowResponse(
            workflow_id=workflow_id,
            status="cancelled",
            message="Workflow cancellation requested",
        )

    except Exception as e:
        logger.error(f"Failed to cancel workflow: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow {workflow_id} not found or cancellation failed",
        )


@app.get("/api/v1/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """
    Health check endpoint.

    Returns healthy if:
    - TEMPORAL MODE: Temporal client is connected
    - STANDALONE MODE: Always healthy (no dependencies)

    Returns:
        Service health status
    """
    if settings.use_temporal:
        # Temporal mode: check if client is connected
        is_healthy = temporal_client is not None
    else:
        # Standalone mode: always healthy (no external dependencies)
        is_healthy = True

    return HealthCheckResponse(
        status="healthy" if is_healthy else "unhealthy",
        timestamp=datetime.utcnow(),
        temporal_connected=temporal_client is not None if settings.use_temporal else False,
        version="1.0.0",
    )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
            "detail": str(exc) if settings.log_level == "DEBUG" else None,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
    )
