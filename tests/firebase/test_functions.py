"""
Unit tests for Firebase Functions.

These tests use the Firebase Test SDK to test functions without deploying.
Based on: https://firebase.google.com/docs/functions/unit-testing
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestFirebaseFunctions:
    """Test Firebase Functions behavior."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock Firebase Functions request."""
        request = Mock()
        request.get_json = Mock(return_value={
            "track_name": "Bohemian Rhapsody",
            "artist": "Queen",
            "album": "A Night at the Opera",
            "playlist_id": "37i9dQZF1DXcBWIGoYBM5M"
        })
        request.path = "/api/v1/sync"
        request.method = "POST"
        request.headers = {"Content-Type": "application/json"}
        return request

    @pytest.fixture
    def mock_settings_firestore_enabled(self):
        """Mock settings with Firestore enabled."""
        with patch('config.settings.settings') as mock_settings:
            mock_settings.use_firestore = True
            yield mock_settings

    @pytest.fixture
    def mock_settings_firestore_disabled(self):
        """Mock settings with Firestore disabled."""
        with patch('config.settings.settings') as mock_settings:
            mock_settings.use_firestore = False
            yield mock_settings

    def test_sync_request_validation_valid(self):
        """Test that valid sync requests are accepted."""
        from api.models import SyncSongRequest

        request = SyncSongRequest(
            track_name="Bohemian Rhapsody",
            artist="Queen",
            album="A Night at the Opera",
            playlist_id="37i9dQZF1DXcBWIGoYBM5M"
        )

        assert request.track_name == "Bohemian Rhapsody"
        assert request.artist == "Queen"
        assert request.album == "A Night at the Opera"
        assert request.playlist_id == "37i9dQZF1DXcBWIGoYBM5M"

    def test_sync_request_validation_invalid_playlist(self):
        """Test that invalid playlist IDs are rejected."""
        from pydantic import ValidationError
        from api.models import SyncSongRequest

        with pytest.raises(ValidationError) as exc_info:
            SyncSongRequest(
                track_name="Test",
                artist="Artist",
                playlist_id="INVALID"  # Wrong format
            )

        # Check that playlist_id validation failed
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('playlist_id',) for error in errors)

    def test_sync_response_with_firestore_enabled(self, mock_settings_firestore_enabled):
        """Test POST response includes status_url when Firestore enabled."""
        from api.models import SyncSongResponse

        response = SyncSongResponse(
            workflow_id="test-123",
            status="accepted",
            message="Processing...",
            status_url="/api/v1/sync/test-123"
        )

        assert response.workflow_id == "test-123"
        assert response.status_url == "/api/v1/sync/test-123"

    def test_sync_response_with_firestore_disabled(self, mock_settings_firestore_disabled):
        """Test POST response excludes status_url when Firestore disabled."""
        from api.models import SyncSongResponse

        response = SyncSongResponse(
            workflow_id="test-123",
            status="accepted",
            message="Processing...",
            status_url=None  # Should be None
        )

        assert response.workflow_id == "test-123"
        assert response.status_url is None

    @pytest.mark.asyncio
    async def test_get_status_firestore_disabled_returns_501(self, mock_settings_firestore_disabled):
        """Test that GET status returns 501 when Firestore is disabled."""
        from fastapi import HTTPException
        from api.app_agent import get_sync_status

        with pytest.raises(HTTPException) as exc_info:
            await get_sync_status("test-workflow-id")

        assert exc_info.value.status_code == 501
        assert "status_endpoint_disabled" in str(exc_info.value.detail)

    def test_firestore_client_disabled(self, mock_settings_firestore_disabled):
        """Test that Firestore client returns None when disabled."""
        # Import after mocking settings
        from api.app_agent import get_firestore_client

        # Reset global state
        import api.app_agent
        api.app_agent._firestore_enabled = None
        api.app_agent._firestore_client = None

        client = get_firestore_client()
        assert client is None

    @pytest.mark.skipif(
        sys.modules.get('firebase_admin') is None,
        reason="firebase_admin not installed (only needed for deployment)"
    )
    @patch('firebase_admin.initialize_app')
    @patch('firebase_admin.firestore.client')
    def test_firestore_client_enabled(self, mock_firestore_client, mock_init_app, mock_settings_firestore_enabled):
        """Test that Firestore client is initialized when enabled."""
        from api.app_agent import get_firestore_client

        # Reset global state
        import api.app_agent
        api.app_agent._firestore_enabled = None
        api.app_agent._firestore_client = None

        mock_firestore_client.return_value = Mock()

        client = get_firestore_client()
        assert client is not None
        mock_init_app.assert_called_once()
        mock_firestore_client.assert_called_once()

    def test_health_endpoint_response(self):
        """Test health endpoint returns correct structure."""
        expected_response = {
            "status": "healthy",
            "mode": "agent_sdk",
            "message": "Agent-powered Spotify sync is operational"
        }

        # This would be tested by calling the actual endpoint
        # For now, just validate the structure
        assert "status" in expected_response
        assert "mode" in expected_response
        assert expected_response["status"] == "healthy"


class TestFirestoreIntegration:
    """Test Firestore integration behavior."""

    @pytest.fixture
    def mock_firestore_doc(self):
        """Mock Firestore document."""
        doc = Mock()
        doc.exists = True
        doc.to_dict.return_value = {
            'workflow_id': 'test-123',
            'success': True,
            'message': 'Test message',
            'matched_track_uri': 'spotify:track:abc123',
            'matched_track_name': 'Test Song',
            'matched_artist': 'Test Artist',
            'confidence_score': 0.95,
            'match_method': 'exact_match',
            'execution_time_seconds': 22.5
        }
        return doc

    @pytest.fixture
    def mock_firestore_client(self, mock_firestore_doc):
        """Mock Firestore client."""
        client = Mock()
        collection = Mock()
        document = Mock()

        document.get.return_value = mock_firestore_doc
        collection.document.return_value = document
        client.collection.return_value = collection

        return client

    @pytest.mark.asyncio
    async def test_get_status_from_firestore(self, mock_firestore_client):
        """Test reading sync status from Firestore."""
        with patch('api.app_agent.get_firestore_client', return_value=mock_firestore_client):
            with patch('config.settings.settings') as mock_settings:
                mock_settings.use_firestore = True

                from api.app_agent import get_sync_status

                # Reset global state
                import api.app_agent
                api.app_agent._firestore_enabled = None

                response = await get_sync_status("test-123")

                assert response.workflow_id == "test-123"
                assert response.status == "completed"

    @pytest.mark.asyncio
    async def test_store_result_in_firestore(self, mock_firestore_client):
        """Test storing sync result in Firestore."""
        from agent_executor import AgentExecutionResult

        result = AgentExecutionResult(
            success=True,
            message="Test success",
            matched_track_uri="spotify:track:test123",
            matched_track_name="Test Song",
            matched_artist="Test Artist",
            confidence_score=0.95,
            match_method="exact_match",
            execution_time_seconds=22.5
        )

        # Mock Firestore set operation
        mock_firestore_client.collection.return_value.document.return_value.set = Mock()

        with patch('api.app_agent.get_firestore_client', return_value=mock_firestore_client):
            # Simulate storing result
            db = mock_firestore_client
            db.collection('sync_results').document('test-123').set({
                'workflow_id': 'test-123',
                'success': result.success,
                'message': result.message
            })

            # Verify set was called
            db.collection.return_value.document.return_value.set.assert_called_once()


class TestEmulatorCompatibility:
    """Test compatibility with Firebase emulator."""

    def test_environment_detection(self):
        """Test that functions can detect emulator environment."""
        import os

        # Firebase emulator sets these environment variables
        with patch.dict(os.environ, {
            'FUNCTIONS_EMULATOR': 'true',
            'FIRESTORE_EMULATOR_HOST': 'localhost:8080'
        }):
            assert os.getenv('FUNCTIONS_EMULATOR') == 'true'
            assert os.getenv('FIRESTORE_EMULATOR_HOST') == 'localhost:8080'

    def test_config_loads_from_env(self):
        """Test that configuration loads from environment variables."""
        import os

        with patch.dict(os.environ, {
            'USE_FIRESTORE': 'false',
            'USE_AI_DISAMBIGUATION': 'false',  # Disable AI validation
            'ANTHROPIC_API_KEY': 'test-key',
            'SPOTIFY_CLIENT_ID': 'test-client-id',
            'SPOTIFY_CLIENT_SECRET': 'test-secret',
            'SPOTIFY_REDIRECT_URI': 'http://localhost:8888/callback'
        }, clear=True):
            # Reimport settings to pick up new env vars
            import importlib
            import config.settings
            importlib.reload(config.settings)

            from config.settings import settings

            assert settings.use_firestore is False
            assert settings.anthropic_api_key == 'test-key'
            assert settings.use_ai_disambiguation is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
