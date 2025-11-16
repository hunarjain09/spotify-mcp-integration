"""Unit tests for API request/response models."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from api.models import (
    SyncSongRequest,
    SyncSongResponse,
    WorkflowProgressInfo,
    WorkflowResultInfo,
    WorkflowStatusResponse,
    CancelWorkflowResponse,
    HealthCheckResponse,
    ErrorResponse,
)


class TestSyncSongRequest:
    """Tests for SyncSongRequest model."""

    def test_valid_request_all_fields(self):
        """Test creating a valid request with all fields."""
        request = SyncSongRequest(
            track_name="Bohemian Rhapsody",
            artist="Queen",
            album="A Night at the Opera",
            playlist_id="37i9dQZF1DXcBWIGoYBM5M",
            user_id="user_12345",
            match_threshold=0.9,
            use_ai_disambiguation=False,
        )

        assert request.track_name == "Bohemian Rhapsody"
        assert request.artist == "Queen"
        assert request.album == "A Night at the Opera"
        assert request.playlist_id == "37i9dQZF1DXcBWIGoYBM5M"
        assert request.user_id == "user_12345"
        assert request.match_threshold == 0.9
        assert request.use_ai_disambiguation is False

    def test_valid_request_minimal_fields(self):
        """Test creating a valid request with minimal required fields."""
        request = SyncSongRequest(
            track_name="Test Song",
            artist="Test Artist",
            playlist_id="37i9dQZF1DXcBWIGoYBM5M",
        )

        assert request.track_name == "Test Song"
        assert request.artist == "Test Artist"
        assert request.album is None
        assert request.playlist_id == "37i9dQZF1DXcBWIGoYBM5M"
        assert request.match_threshold == 0.85  # default
        assert request.use_ai_disambiguation is True  # default

    def test_track_name_validation_empty(self):
        """Test that empty track_name is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SyncSongRequest(
                track_name="",
                artist="Test Artist",
                playlist_id="37i9dQZF1DXcBWIGoYBM5M",
            )

        errors = exc_info.value.errors()
        assert any("track_name" in str(err) for err in errors)

    def test_track_name_validation_whitespace(self):
        """Test that whitespace-only track_name is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SyncSongRequest(
                track_name="   ",
                artist="Test Artist",
                playlist_id="37i9dQZF1DXcBWIGoYBM5M",
            )

        errors = exc_info.value.errors()
        assert any("whitespace" in str(err).lower() for err in errors)

    def test_artist_validation_empty(self):
        """Test that empty artist is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SyncSongRequest(
                track_name="Test Song",
                artist="",
                playlist_id="37i9dQZF1DXcBWIGoYBM5M",
            )

        errors = exc_info.value.errors()
        assert any("artist" in str(err) for err in errors)

    def test_artist_validation_whitespace(self):
        """Test that whitespace-only artist is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SyncSongRequest(
                track_name="Test Song",
                artist="   ",
                playlist_id="37i9dQZF1DXcBWIGoYBM5M",
            )

        errors = exc_info.value.errors()
        assert any("whitespace" in str(err).lower() for err in errors)

    def test_playlist_id_validation_invalid_format(self):
        """Test that invalid playlist ID format is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SyncSongRequest(
                track_name="Test Song",
                artist="Test Artist",
                playlist_id="invalid-playlist-id",  # Not 22 alphanumeric chars
            )

        errors = exc_info.value.errors()
        assert any("playlist_id" in str(err) for err in errors)

    def test_playlist_id_validation_wrong_length(self):
        """Test that wrong-length playlist ID is rejected."""
        with pytest.raises(ValidationError):
            SyncSongRequest(
                track_name="Test Song",
                artist="Test Artist",
                playlist_id="abc123",  # Too short
            )

    def test_match_threshold_validation_too_high(self):
        """Test that match_threshold > 1.0 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SyncSongRequest(
                track_name="Test Song",
                artist="Test Artist",
                playlist_id="37i9dQZF1DXcBWIGoYBM5M",
                match_threshold=1.5,
            )

        errors = exc_info.value.errors()
        assert any("match_threshold" in str(err) for err in errors)

    def test_match_threshold_validation_too_low(self):
        """Test that match_threshold < 0.0 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SyncSongRequest(
                track_name="Test Song",
                artist="Test Artist",
                playlist_id="37i9dQZF1DXcBWIGoYBM5M",
                match_threshold=-0.1,
            )

        errors = exc_info.value.errors()
        assert any("match_threshold" in str(err) for err in errors)

    def test_match_threshold_boundary_values(self):
        """Test boundary values for match_threshold."""
        # Test 0.0
        request_min = SyncSongRequest(
            track_name="Test Song",
            artist="Test Artist",
            playlist_id="37i9dQZF1DXcBWIGoYBM5M",
            match_threshold=0.0,
        )
        assert request_min.match_threshold == 0.0

        # Test 1.0
        request_max = SyncSongRequest(
            track_name="Test Song",
            artist="Test Artist",
            playlist_id="37i9dQZF1DXcBWIGoYBM5M",
            match_threshold=1.0,
        )
        assert request_max.match_threshold == 1.0

    def test_track_name_trimmed(self):
        """Test that track_name is trimmed."""
        request = SyncSongRequest(
            track_name="  Test Song  ",
            artist="Test Artist",
            playlist_id="37i9dQZF1DXcBWIGoYBM5M",
        )

        assert request.track_name == "Test Song"

    def test_artist_trimmed(self):
        """Test that artist is trimmed."""
        request = SyncSongRequest(
            track_name="Test Song",
            artist="  Test Artist  ",
            playlist_id="37i9dQZF1DXcBWIGoYBM5M",
        )

        assert request.artist == "Test Artist"

    def test_album_trimmed(self):
        """Test that album is trimmed."""
        request = SyncSongRequest(
            track_name="Test Song",
            artist="Test Artist",
            album="  Test Album  ",
            playlist_id="37i9dQZF1DXcBWIGoYBM5M",
        )

        assert request.album == "Test Album"

    def test_album_empty_becomes_none(self):
        """Test that empty album becomes None."""
        request = SyncSongRequest(
            track_name="Test Song",
            artist="Test Artist",
            album="   ",
            playlist_id="37i9dQZF1DXcBWIGoYBM5M",
        )

        assert request.album is None

    def test_track_name_max_length(self):
        """Test that track_name exceeding max length is rejected."""
        with pytest.raises(ValidationError):
            SyncSongRequest(
                track_name="x" * 201,  # Over 200 characters
                artist="Test Artist",
                playlist_id="37i9dQZF1DXcBWIGoYBM5M",
            )

    def test_artist_max_length(self):
        """Test that artist exceeding max length is rejected."""
        with pytest.raises(ValidationError):
            SyncSongRequest(
                track_name="Test Song",
                artist="x" * 201,  # Over 200 characters
                playlist_id="37i9dQZF1DXcBWIGoYBM5M",
            )


class TestSyncSongResponse:
    """Tests for SyncSongResponse model."""

    def test_valid_response(self):
        """Test creating a valid response."""
        response = SyncSongResponse(
            workflow_id="sync-user_12345-1699564832-a3f9d",
            status="accepted",
            message="Sync started for 'Bohemian Rhapsody' by Queen",
            status_url="/api/v1/sync/sync-user_12345-1699564832-a3f9d",
        )

        assert response.workflow_id == "sync-user_12345-1699564832-a3f9d"
        assert response.status == "accepted"
        assert "Bohemian Rhapsody" in response.message
        assert response.status_url == "/api/v1/sync/sync-user_12345-1699564832-a3f9d"


class TestWorkflowProgressInfo:
    """Tests for WorkflowProgressInfo model."""

    def test_valid_progress_info(self):
        """Test creating valid progress info."""
        progress = WorkflowProgressInfo(
            current_step="Searching Spotify",
            steps_completed=2,
            steps_total=5,
            candidates_found=3,
            elapsed_seconds=2.5,
        )

        assert progress.current_step == "Searching Spotify"
        assert progress.steps_completed == 2
        assert progress.steps_total == 5
        assert progress.candidates_found == 3
        assert progress.elapsed_seconds == 2.5

    def test_default_candidates_found(self):
        """Test default value for candidates_found."""
        progress = WorkflowProgressInfo(
            current_step="Starting",
            steps_completed=0,
            steps_total=5,
            elapsed_seconds=0.0,
        )

        assert progress.candidates_found == 0


class TestWorkflowResultInfo:
    """Tests for WorkflowResultInfo model."""

    def test_successful_result_info(self):
        """Test creating successful result info."""
        result = WorkflowResultInfo(
            success=True,
            message="Successfully added track to playlist",
            spotify_track_id="7tFiyTwD0nx5a1eklYtX2J",
            spotify_track_uri="spotify:track:7tFiyTwD0nx5a1eklYtX2J",
            confidence_score=0.95,
            execution_time_seconds=4.2,
            retry_count=0,
            match_method="fuzzy",
        )

        assert result.success is True
        assert "Successfully added" in result.message
        assert result.spotify_track_id == "7tFiyTwD0nx5a1eklYtX2J"
        assert result.confidence_score == 0.95

    def test_failed_result_info(self):
        """Test creating failed result info."""
        result = WorkflowResultInfo(
            success=False,
            message="No matching track found",
            execution_time_seconds=3.5,
        )

        assert result.success is False
        assert result.spotify_track_id is None
        assert result.spotify_track_uri is None
        assert result.confidence_score == 0.0
        assert result.retry_count == 0


class TestWorkflowStatusResponse:
    """Tests for WorkflowStatusResponse model."""

    def test_running_status(self):
        """Test workflow status response for running workflow."""
        status = WorkflowStatusResponse(
            workflow_id="test-workflow-123",
            status="running",
            progress=WorkflowProgressInfo(
                current_step="Searching Spotify",
                steps_completed=2,
                steps_total=5,
                candidates_found=3,
                elapsed_seconds=2.5,
            ),
            started_at=datetime(2025, 11, 9, 10, 30, 32),
        )

        assert status.workflow_id == "test-workflow-123"
        assert status.status == "running"
        assert status.progress is not None
        assert status.result is None
        assert status.error is None
        assert status.completed_at is None

    def test_completed_status(self):
        """Test workflow status response for completed workflow."""
        status = WorkflowStatusResponse(
            workflow_id="test-workflow-123",
            status="completed",
            result=WorkflowResultInfo(
                success=True,
                message="Track added successfully",
                spotify_track_id="7tFiyTwD0nx5a1eklYtX2J",
                spotify_track_uri="spotify:track:7tFiyTwD0nx5a1eklYtX2J",
                confidence_score=0.95,
                execution_time_seconds=4.2,
                retry_count=0,
                match_method="fuzzy",
            ),
            started_at=datetime(2025, 11, 9, 10, 30, 32),
            completed_at=datetime(2025, 11, 9, 10, 30, 36),
        )

        assert status.status == "completed"
        assert status.result is not None
        assert status.result.success is True
        assert status.progress is None
        assert status.completed_at is not None

    def test_failed_status(self):
        """Test workflow status response for failed workflow."""
        status = WorkflowStatusResponse(
            workflow_id="test-workflow-123",
            status="failed",
            error="Spotify API error",
            started_at=datetime(2025, 11, 9, 10, 30, 32),
            completed_at=datetime(2025, 11, 9, 10, 30, 35),
        )

        assert status.status == "failed"
        assert status.error == "Spotify API error"
        assert status.result is None
        assert status.progress is None


class TestCancelWorkflowResponse:
    """Tests for CancelWorkflowResponse model."""

    def test_valid_cancel_response(self):
        """Test creating valid cancel response."""
        response = CancelWorkflowResponse(
            workflow_id="test-workflow-123",
            status="cancelled",
            message="Workflow cancelled successfully",
        )

        assert response.workflow_id == "test-workflow-123"
        assert response.status == "cancelled"
        assert "cancelled" in response.message.lower()


class TestHealthCheckResponse:
    """Tests for HealthCheckResponse model."""

    def test_healthy_response(self):
        """Test creating healthy response."""
        response = HealthCheckResponse(
            status="healthy",
            timestamp=datetime(2025, 11, 9, 10, 30, 0),
            temporal_connected=True,
            version="1.0.0",
        )

        assert response.status == "healthy"
        assert response.temporal_connected is True
        assert response.version == "1.0.0"

    def test_unhealthy_response(self):
        """Test creating unhealthy response."""
        response = HealthCheckResponse(
            status="unhealthy",
            timestamp=datetime(2025, 11, 9, 10, 30, 0),
            temporal_connected=False,
            version="1.0.0",
        )

        assert response.status == "unhealthy"
        assert response.temporal_connected is False

    def test_default_version(self):
        """Test default version value."""
        response = HealthCheckResponse(
            status="healthy",
            timestamp=datetime(2025, 11, 9, 10, 30, 0),
            temporal_connected=True,
        )

        assert response.version == "1.0.0"


class TestErrorResponse:
    """Tests for ErrorResponse model."""

    def test_error_response_with_detail(self):
        """Test creating error response with detail."""
        response = ErrorResponse(
            error="ValidationError",
            message="Invalid request parameters",
            detail="track_name is required",
            timestamp=datetime(2025, 11, 9, 10, 30, 0),
        )

        assert response.error == "ValidationError"
        assert response.message == "Invalid request parameters"
        assert response.detail == "track_name is required"

    def test_error_response_without_detail(self):
        """Test creating error response without detail."""
        response = ErrorResponse(
            error="InternalError",
            message="An unexpected error occurred",
            timestamp=datetime(2025, 11, 9, 10, 30, 0),
        )

        assert response.error == "InternalError"
        assert response.message == "An unexpected error occurred"
        assert response.detail is None
