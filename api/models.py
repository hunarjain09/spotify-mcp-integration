"""API request and response models for the FastAPI server."""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class SyncSongRequest(BaseModel):
    """POST /api/v1/sync request body."""

    track_name: str = Field(..., min_length=1, max_length=200, description="Song title")
    artist: str = Field(..., min_length=1, max_length=200, description="Artist name")
    album: Optional[str] = Field(None, max_length=200, description="Album name (optional)")
    playlist_id: str = Field(
        ...,
        pattern=r"^[a-zA-Z0-9]{22}$",
        description="Spotify playlist ID (22 characters)",
    )
    user_id: Optional[str] = Field(None, description="User identifier (optional)")
    match_threshold: Optional[float] = Field(
        0.85, ge=0.0, le=1.0, description="Matching confidence threshold (0.0-1.0)"
    )
    use_ai_disambiguation: Optional[bool] = Field(
        True, description="Use AI for ambiguous matches"
    )

    @field_validator("track_name", "artist")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Ensure fields are not empty or whitespace."""
        if not v.strip():
            raise ValueError("Field cannot be empty or whitespace")
        return v.strip()

    @field_validator("album")
    @classmethod
    def validate_album(cls, v: Optional[str]) -> Optional[str]:
        """Clean album name if provided."""
        if v:
            return v.strip() if v.strip() else None
        return None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "track_name": "Bohemian Rhapsody",
                    "artist": "Queen",
                    "album": "A Night at the Opera",
                    "playlist_id": "37i9dQZF1DXcBWIGoYBM5M",
                    "user_id": "user_12345",
                }
            ]
        }
    }


class SyncSongResponse(BaseModel):
    """POST /api/v1/sync response."""

    workflow_id: str = Field(..., description="Unique workflow identifier")
    status: str = Field(..., description="Workflow status (e.g., 'accepted')")
    message: str = Field(..., description="Human-readable status message")
    status_url: str = Field(..., description="URL to check workflow status")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "workflow_id": "sync-user_12345-1699564832-a3f9d",
                    "status": "accepted",
                    "message": "Sync started for 'Bohemian Rhapsody' by Queen",
                    "status_url": "/api/v1/sync/sync-user_12345-1699564832-a3f9d",
                }
            ]
        }
    }


class WorkflowProgressInfo(BaseModel):
    """Progress information for a running workflow."""

    current_step: str = Field(..., description="Current workflow step")
    steps_completed: int = Field(..., description="Number of completed steps")
    steps_total: int = Field(..., description="Total number of steps")
    candidates_found: int = Field(0, description="Number of candidate tracks found")
    elapsed_seconds: float = Field(..., description="Time elapsed since workflow start")


class WorkflowResultInfo(BaseModel):
    """Result information for a completed workflow."""

    success: bool = Field(..., description="Whether sync was successful")
    message: str = Field(..., description="Result message")
    spotify_track_id: Optional[str] = Field(None, description="Matched Spotify track ID")
    spotify_track_uri: Optional[str] = Field(None, description="Matched Spotify track URI")
    confidence_score: float = Field(0.0, description="Match confidence score (0.0-1.0)")
    execution_time_seconds: float = Field(0.0, description="Total execution time")
    retry_count: int = Field(0, description="Number of retries performed")
    match_method: Optional[str] = Field(None, description="Method used for matching")


class WorkflowStatusResponse(BaseModel):
    """GET /api/v1/sync/{workflow_id} response."""

    workflow_id: str = Field(..., description="Workflow identifier")
    status: str = Field(
        ..., description="Status: 'running', 'completed', 'failed', 'cancelled'"
    )
    progress: Optional[WorkflowProgressInfo] = Field(None, description="Progress info (if running)")
    result: Optional[WorkflowResultInfo] = Field(None, description="Result info (if completed)")
    error: Optional[str] = Field(None, description="Error message (if failed)")
    started_at: datetime = Field(..., description="Workflow start time")
    completed_at: Optional[datetime] = Field(None, description="Workflow completion time")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "workflow_id": "sync-user_12345-1699564832-a3f9d",
                    "status": "completed",
                    "result": {
                        "success": True,
                        "message": "Successfully added 'Bohemian Rhapsody' by Queen to playlist",
                        "spotify_track_id": "7tFiyTwD0nx5a1eklYtX2J",
                        "spotify_track_uri": "spotify:track:7tFiyTwD0nx5a1eklYtX2J",
                        "confidence_score": 0.98,
                        "execution_time_seconds": 4.2,
                        "retry_count": 0,
                        "match_method": "fuzzy",
                    },
                    "started_at": "2025-11-09T10:30:32Z",
                    "completed_at": "2025-11-09T10:30:36Z",
                }
            ]
        }
    }


class CancelWorkflowResponse(BaseModel):
    """POST /api/v1/sync/{workflow_id}/cancel response."""

    workflow_id: str = Field(..., description="Workflow identifier")
    status: str = Field(..., description="Cancellation status")
    message: str = Field(..., description="Cancellation message")


class HealthCheckResponse(BaseModel):
    """GET /api/v1/health response."""

    status: str = Field(..., description="Service health status")
    timestamp: datetime = Field(..., description="Current server time")
    temporal_connected: bool = Field(..., description="Temporal connection status")
    version: str = Field("1.0.0", description="API version")


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")
    timestamp: datetime = Field(..., description="Error occurrence time")
