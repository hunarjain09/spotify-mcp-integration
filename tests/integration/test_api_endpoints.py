"""Integration tests for FastAPI endpoints."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
from fastapi import status
from fastapi.testclient import TestClient

from api.app import app
from api.models import (
    SyncSongRequest,
    WorkflowProgressInfo,
    WorkflowResultInfo,
)
from models.data_models import (
    WorkflowProgress,
    WorkflowResult,
)


@pytest.fixture
def client(mock_temporal_client):
    """Create test client with mocked Temporal client."""
    # Mock the temporal client on app startup
    app.state.temporal_client = mock_temporal_client

    # Create test client without triggering startup events
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


class TestSyncEndpoint:
    """Tests for POST /api/v1/sync endpoint."""

    def test_sync_song_success(self, client, mock_temporal_client):
        """Test successful song sync initiation."""
        request_data = {
            "track_name": "Bohemian Rhapsody",
            "artist": "Queen",
            "album": "A Night at the Opera",
            "playlist_id": "37i9dQZF1DXcBWIGoYBM5M",
            "user_id": "test_user_123",
        }

        response = client.post("/api/v1/sync", json=request_data)

        assert response.status_code == status.HTTP_202_ACCEPTED

        data = response.json()
        assert data["status"] == "accepted"
        assert "workflow_id" in data
        assert data["workflow_id"].startswith("sync-test_user_123-")
        assert data["status_url"].startswith("/api/v1/sync/")
        assert "Bohemian Rhapsody" in data["message"]

        # Verify temporal client was called
        mock_temporal_client.start_workflow.assert_called_once()

    def test_sync_song_minimal_request(self, client, mock_temporal_client):
        """Test sync with minimal required fields."""
        request_data = {
            "track_name": "Imagine",
            "artist": "John Lennon",
            "playlist_id": "37i9dQZF1DXcBWIGoYBM5M",
        }

        response = client.post("/api/v1/sync", json=request_data)

        assert response.status_code == status.HTTP_202_ACCEPTED

        data = response.json()
        assert data["status"] == "accepted"
        assert "workflow_id" in data
        assert data["workflow_id"].startswith("sync-anonymous-")

    def test_sync_song_missing_required_fields(self, client):
        """Test sync with missing required fields."""
        request_data = {
            "track_name": "Test Song",
            # Missing artist and playlist_id
        }

        response = client.post("/api/v1/sync", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_sync_song_invalid_playlist_id(self, client):
        """Test sync with invalid playlist ID format."""
        request_data = {
            "track_name": "Test Song",
            "artist": "Test Artist",
            "playlist_id": "invalid-id",  # Not 22 chars
        }

        response = client.post("/api/v1/sync", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_sync_song_empty_track_name(self, client):
        """Test sync with empty track name."""
        request_data = {
            "track_name": "",
            "artist": "Test Artist",
            "playlist_id": "37i9dQZF1DXcBWIGoYBM5M",
        }

        response = client.post("/api/v1/sync", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_sync_song_invalid_threshold(self, client):
        """Test sync with invalid match threshold."""
        request_data = {
            "track_name": "Test Song",
            "artist": "Test Artist",
            "playlist_id": "37i9dQZF1DXcBWIGoYBM5M",
            "match_threshold": 1.5,  # > 1.0
        }

        response = client.post("/api/v1/sync", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_sync_song_custom_options(self, client, mock_temporal_client):
        """Test sync with custom match threshold and AI options."""
        request_data = {
            "track_name": "Test Song",
            "artist": "Test Artist",
            "playlist_id": "37i9dQZF1DXcBWIGoYBM5M",
            "match_threshold": 0.9,
            "use_ai_disambiguation": False,
        }

        response = client.post("/api/v1/sync", json=request_data)

        assert response.status_code == status.HTTP_202_ACCEPTED

        # Verify workflow was started with custom options
        call_args = mock_temporal_client.start_workflow.call_args
        workflow_input = call_args[0][1]
        assert workflow_input.match_threshold == 0.9
        assert workflow_input.use_ai_disambiguation is False

    @patch("api.app.temporal_client", None)
    def test_sync_song_temporal_disconnected(self, client):
        """Test sync when Temporal client is not connected."""
        # Override the mock to None
        app.state.temporal_client = None

        request_data = {
            "track_name": "Test Song",
            "artist": "Test Artist",
            "playlist_id": "37i9dQZF1DXcBWIGoYBM5M",
        }

        response = client.post("/api/v1/sync", json=request_data)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "not connected" in response.json()["detail"].lower()

    def test_sync_song_workflow_already_started(self, client, mock_temporal_client):
        """Test sync when workflow with same ID already exists."""
        from temporalio.exceptions import WorkflowAlreadyStartedError

        # Mock start_workflow to raise already started error
        mock_temporal_client.start_workflow.side_effect = WorkflowAlreadyStartedError(
            "workflow_id", "workflow_type", None
        )

        request_data = {
            "track_name": "Test Song",
            "artist": "Test Artist",
            "playlist_id": "37i9dQZF1DXcBWIGoYBM5M",
        }

        response = client.post("/api/v1/sync", json=request_data)

        # Should still return 202 (idempotent)
        assert response.status_code == status.HTTP_202_ACCEPTED

        data = response.json()
        assert "already in progress" in data["message"].lower()


class TestWorkflowStatusEndpoint:
    """Tests for GET /api/v1/sync/{workflow_id} endpoint."""

    def test_get_status_running_workflow(self, client, mock_temporal_client):
        """Test getting status of a running workflow."""
        workflow_id = "sync-test-123"

        # Mock workflow description
        mock_description = Mock()
        mock_description.status.name = "RUNNING"
        mock_description.start_time = datetime(2025, 11, 9, 10, 30, 0)

        # Mock handle
        mock_handle = AsyncMock()
        mock_handle.describe = AsyncMock(return_value=mock_description)
        mock_handle.query = AsyncMock(return_value=WorkflowProgress(
            current_step="Searching Spotify",
            steps_completed=2,
            steps_total=5,
            candidates_found=3,
            elapsed_seconds=2.5,
        ))

        mock_temporal_client.get_workflow_handle.return_value = mock_handle

        response = client.get(f"/api/v1/sync/{workflow_id}")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["workflow_id"] == workflow_id
        assert data["status"] == "running"
        assert data["progress"] is not None
        assert data["progress"]["current_step"] == "Searching Spotify"
        assert data["progress"]["steps_completed"] == 2
        assert data["result"] is None

    def test_get_status_completed_workflow_success(self, client, mock_temporal_client):
        """Test getting status of a successfully completed workflow."""
        workflow_id = "sync-test-456"

        # Mock workflow description
        mock_description = Mock()
        mock_description.status.name = "COMPLETED"
        mock_description.start_time = datetime(2025, 11, 9, 10, 30, 0)
        mock_description.close_time = datetime(2025, 11, 9, 10, 30, 36)

        # Mock handle
        mock_handle = AsyncMock()
        mock_handle.describe = AsyncMock(return_value=mock_description)
        mock_handle.result = AsyncMock(return_value=WorkflowResult(
            success=True,
            message="Successfully added track to playlist",
            spotify_track_id="7tFiyTwD0nx5a1eklYtX2J",
            spotify_track_uri="spotify:track:7tFiyTwD0nx5a1eklYtX2J",
            confidence_score=0.95,
            execution_time_seconds=4.2,
            retry_count=0,
            match_method="fuzzy",
        ))

        mock_temporal_client.get_workflow_handle.return_value = mock_handle

        response = client.get(f"/api/v1/sync/{workflow_id}")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["workflow_id"] == workflow_id
        assert data["status"] == "completed"
        assert data["result"] is not None
        assert data["result"]["success"] is True
        assert data["result"]["spotify_track_id"] == "7tFiyTwD0nx5a1eklYtX2J"
        assert data["result"]["confidence_score"] == 0.95
        assert data["progress"] is None

    def test_get_status_completed_workflow_failure(self, client, mock_temporal_client):
        """Test getting status of a failed completion."""
        workflow_id = "sync-test-789"

        # Mock workflow description
        mock_description = Mock()
        mock_description.status.name = "COMPLETED"
        mock_description.start_time = datetime(2025, 11, 9, 10, 30, 0)
        mock_description.close_time = datetime(2025, 11, 9, 10, 30, 36)

        # Mock handle with failure result
        mock_handle = AsyncMock()
        mock_handle.describe = AsyncMock(return_value=mock_description)
        mock_handle.result = AsyncMock(return_value=WorkflowResult(
            success=False,
            message="No matching track found",
            execution_time_seconds=3.5,
        ))

        mock_temporal_client.get_workflow_handle.return_value = mock_handle

        response = client.get(f"/api/v1/sync/{workflow_id}")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["result"]["success"] is False
        assert data["result"]["message"] == "No matching track found"

    def test_get_status_failed_workflow(self, client, mock_temporal_client):
        """Test getting status of a failed workflow."""
        from temporalio.client import WorkflowFailureError

        workflow_id = "sync-test-failed"

        # Mock workflow description
        mock_description = Mock()
        mock_description.status.name = "FAILED"
        mock_description.start_time = datetime(2025, 11, 9, 10, 30, 0)
        mock_description.close_time = datetime(2025, 11, 9, 10, 30, 5)

        # Mock handle that raises workflow failure
        mock_cause = Mock()
        mock_cause.__str__ = Mock(return_value="Spotify API error")

        mock_handle = AsyncMock()
        mock_handle.describe = AsyncMock(return_value=mock_description)
        mock_handle.result = AsyncMock(side_effect=WorkflowFailureError(
            message="Workflow failed",
            cause=mock_cause,
        ))

        mock_temporal_client.get_workflow_handle.return_value = mock_handle

        response = client.get(f"/api/v1/sync/{workflow_id}")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["status"] == "failed"
        assert data["error"] is not None
        assert "Spotify API error" in data["error"]

    def test_get_status_cancelled_workflow(self, client, mock_temporal_client):
        """Test getting status of a cancelled workflow."""
        workflow_id = "sync-test-cancelled"

        # Mock workflow description
        mock_description = Mock()
        mock_description.status.name = "CANCELED"
        mock_description.start_time = datetime(2025, 11, 9, 10, 30, 0)
        mock_description.close_time = datetime(2025, 11, 9, 10, 30, 2)

        # Mock handle
        mock_handle = AsyncMock()
        mock_handle.describe = AsyncMock(return_value=mock_description)

        mock_temporal_client.get_workflow_handle.return_value = mock_handle

        response = client.get(f"/api/v1/sync/{workflow_id}")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["status"] == "cancelled"
        assert "cancelled" in data["error"].lower()

    def test_get_status_workflow_not_found(self, client, mock_temporal_client):
        """Test getting status of non-existent workflow."""
        workflow_id = "non-existent-workflow"

        # Mock get_workflow_handle to raise exception
        mock_temporal_client.get_workflow_handle.side_effect = Exception("Workflow not found")

        response = client.get(f"/api/v1/sync/{workflow_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    @patch("api.app.temporal_client", None)
    def test_get_status_temporal_disconnected(self, client):
        """Test getting status when Temporal is disconnected."""
        app.state.temporal_client = None

        response = client.get("/api/v1/sync/some-workflow")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


class TestCancelWorkflowEndpoint:
    """Tests for POST /api/v1/sync/{workflow_id}/cancel endpoint."""

    def test_cancel_workflow_success(self, client, mock_temporal_client):
        """Test successful workflow cancellation."""
        workflow_id = "sync-test-cancel-123"

        # Mock handle
        mock_handle = AsyncMock()
        mock_handle.cancel = AsyncMock()

        mock_temporal_client.get_workflow_handle.return_value = mock_handle

        response = client.post(f"/api/v1/sync/{workflow_id}/cancel")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["workflow_id"] == workflow_id
        assert data["status"] == "cancelled"
        assert "cancellation requested" in data["message"].lower()

        # Verify cancel was called
        mock_handle.cancel.assert_called_once()

    def test_cancel_workflow_not_found(self, client, mock_temporal_client):
        """Test cancelling non-existent workflow."""
        workflow_id = "non-existent-workflow"

        # Mock get_workflow_handle to raise exception
        mock_temporal_client.get_workflow_handle.side_effect = Exception("Workflow not found")

        response = client.post(f"/api/v1/sync/{workflow_id}/cancel")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    @patch("api.app.temporal_client", None)
    def test_cancel_workflow_temporal_disconnected(self, client):
        """Test cancelling workflow when Temporal is disconnected."""
        app.state.temporal_client = None

        response = client.post("/api/v1/sync/some-workflow/cancel")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


class TestHealthCheckEndpoint:
    """Tests for GET /api/v1/health endpoint."""

    def test_health_check_healthy(self, client, mock_temporal_client):
        """Test health check when Temporal is connected."""
        app.state.temporal_client = mock_temporal_client

        response = client.get("/api/v1/health")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["status"] == "healthy"
        assert data["temporal_connected"] is True
        assert data["version"] == "1.0.0"
        assert "timestamp" in data

    @patch("api.app.temporal_client", None)
    def test_health_check_unhealthy(self, client):
        """Test health check when Temporal is not connected."""
        app.state.temporal_client = None

        response = client.get("/api/v1/health")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["temporal_connected"] is False
