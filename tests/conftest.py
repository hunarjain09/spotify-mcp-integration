"""Shared test fixtures and configuration for pytest."""

import os
import pytest
from datetime import datetime
from typing import AsyncGenerator, Dict, Any, List
from unittest.mock import Mock, AsyncMock, MagicMock

# Set test environment variables before importing app modules
os.environ["ENVIRONMENT"] = "test"
os.environ["SPOTIFY_CLIENT_ID"] = "test_client_id"
os.environ["SPOTIFY_CLIENT_SECRET"] = "test_client_secret"
os.environ["OPENAI_API_KEY"] = "test_openai_key"
os.environ["TEMPORAL_HOST"] = "localhost:7233"
os.environ["TEMPORAL_NAMESPACE"] = "test"

from fastapi.testclient import TestClient
from models.data_models import (
    SongMetadata,
    SpotifyTrackResult,
    MatchResult,
    WorkflowInput,
    WorkflowResult,
    WorkflowProgress,
    FuzzyMatchScore,
)
from api.models import (
    SyncSongRequest,
    WorkflowProgressInfo,
    WorkflowResultInfo,
)


# ==================== Sample Data Fixtures ====================


@pytest.fixture
def sample_song_metadata() -> SongMetadata:
    """Sample song metadata for testing."""
    return SongMetadata(
        title="Bohemian Rhapsody",
        artist="Queen",
        album="A Night at the Opera",
        duration_ms=354000,
        isrc="GBUM71029604",
    )


@pytest.fixture
def sample_song_metadata_no_isrc() -> SongMetadata:
    """Sample song metadata without ISRC."""
    return SongMetadata(
        title="Imagine",
        artist="John Lennon",
        album="Imagine",
        duration_ms=183000,
        isrc=None,
    )


@pytest.fixture
def sample_spotify_track() -> SpotifyTrackResult:
    """Sample Spotify track result."""
    return SpotifyTrackResult(
        track_id="7tFiyTwD0nx5a1eklYtX2J",
        track_name="Bohemian Rhapsody",
        artist_name="Queen",
        album_name="A Night at the Opera",
        spotify_uri="spotify:track:7tFiyTwD0nx5a1eklYtX2J",
        duration_ms=354000,
        popularity=92,
        release_date="1975-11-21",
        isrc="GBUM71029604",
    )


@pytest.fixture
def sample_spotify_tracks() -> List[SpotifyTrackResult]:
    """List of sample Spotify track results for testing multiple candidates."""
    return [
        SpotifyTrackResult(
            track_id="7tFiyTwD0nx5a1eklYtX2J",
            track_name="Bohemian Rhapsody",
            artist_name="Queen",
            album_name="A Night at the Opera",
            spotify_uri="spotify:track:7tFiyTwD0nx5a1eklYtX2J",
            duration_ms=354000,
            popularity=92,
            release_date="1975-11-21",
            isrc="GBUM71029604",
        ),
        SpotifyTrackResult(
            track_id="abc123xyz",
            track_name="Bohemian Rhapsody - Remastered",
            artist_name="Queen",
            album_name="A Night at the Opera - 2011 Remaster",
            spotify_uri="spotify:track:abc123xyz",
            duration_ms=354500,
            popularity=88,
            release_date="2011-09-05",
            isrc="GBUM71029605",
        ),
        SpotifyTrackResult(
            track_id="def456uvw",
            track_name="Bohemian Rhapsody",
            artist_name="Queen",
            album_name="Greatest Hits",
            spotify_uri="spotify:track:def456uvw",
            duration_ms=354000,
            popularity=85,
            release_date="1981-11-02",
            isrc="GBUM71029604",
        ),
    ]


@pytest.fixture
def sample_match_result(sample_spotify_track) -> MatchResult:
    """Sample match result."""
    return MatchResult(
        is_match=True,
        confidence_score=0.95,
        matched_track=sample_spotify_track,
        match_method="fuzzy",
        candidates_considered=3,
        reasoning=None,
    )


@pytest.fixture
def sample_workflow_input(sample_song_metadata) -> WorkflowInput:
    """Sample workflow input."""
    return WorkflowInput(
        song_metadata=sample_song_metadata,
        playlist_id="37i9dQZF1DXcBWIGoYBM5M",
        user_id="test_user_123",
        match_threshold=0.85,
        use_ai_disambiguation=True,
    )


@pytest.fixture
def sample_workflow_result() -> WorkflowResult:
    """Sample workflow result."""
    return WorkflowResult(
        success=True,
        message="Successfully added 'Bohemian Rhapsody' by Queen to playlist",
        spotify_track_id="7tFiyTwD0nx5a1eklYtX2J",
        spotify_track_uri="spotify:track:7tFiyTwD0nx5a1eklYtX2J",
        confidence_score=0.95,
        execution_time_seconds=4.2,
        retry_count=0,
        match_method="fuzzy",
    )


@pytest.fixture
def sample_workflow_progress() -> WorkflowProgress:
    """Sample workflow progress."""
    return WorkflowProgress(
        current_step="Searching Spotify",
        steps_completed=2,
        steps_total=5,
        candidates_found=3,
        elapsed_seconds=2.5,
    )


@pytest.fixture
def sample_api_request() -> SyncSongRequest:
    """Sample API request."""
    return SyncSongRequest(
        track_name="Bohemian Rhapsody",
        artist="Queen",
        album="A Night at the Opera",
        playlist_id="37i9dQZF1DXcBWIGoYBM5M",
        user_id="test_user_123",
        match_threshold=0.85,
        use_ai_disambiguation=True,
    )


# ==================== Mock Fixtures ====================


@pytest.fixture
def mock_mcp_client() -> Mock:
    """Mock MCP client."""
    client = AsyncMock()

    # Mock search_track response
    client.call_tool = AsyncMock(return_value={
        "tracks": [
            {
                "id": "7tFiyTwD0nx5a1eklYtX2J",
                "name": "Bohemian Rhapsody",
                "artists": [{"name": "Queen"}],
                "album": {"name": "A Night at the Opera", "release_date": "1975-11-21"},
                "uri": "spotify:track:7tFiyTwD0nx5a1eklYtX2J",
                "duration_ms": 354000,
                "popularity": 92,
                "external_ids": {"isrc": "GBUM71029604"},
            }
        ]
    })

    client.connect = AsyncMock()
    client.disconnect = AsyncMock()

    return client


@pytest.fixture
def mock_spotify_client() -> Mock:
    """Mock Spotipy client."""
    client = Mock()

    # Mock search response
    client.search.return_value = {
        "tracks": {
            "items": [
                {
                    "id": "7tFiyTwD0nx5a1eklYtX2J",
                    "name": "Bohemian Rhapsody",
                    "artists": [{"name": "Queen"}],
                    "album": {
                        "name": "A Night at the Opera",
                        "release_date": "1975-11-21",
                    },
                    "uri": "spotify:track:7tFiyTwD0nx5a1eklYtX2J",
                    "duration_ms": 354000,
                    "popularity": 92,
                    "external_ids": {"isrc": "GBUM71029604"},
                }
            ]
        }
    }

    # Mock playlist operations
    client.playlist_add_items.return_value = {"snapshot_id": "test_snapshot"}
    client.playlist_items.return_value = {
        "items": [
            {
                "track": {
                    "id": "7tFiyTwD0nx5a1eklYtX2J",
                    "uri": "spotify:track:7tFiyTwD0nx5a1eklYtX2J",
                }
            }
        ]
    }

    return client


@pytest.fixture
def mock_openai_client() -> Mock:
    """Mock OpenAI client."""
    client = Mock()

    # Mock chat completion response
    response = Mock()
    response.choices = [
        Mock(
            message=Mock(
                content='{"selected_track_id": "7tFiyTwD0nx5a1eklYtX2J", "reasoning": "Exact match based on title, artist, and album."}'
            )
        )
    ]
    client.chat.completions.create.return_value = response

    return client


@pytest.fixture
def mock_temporal_client() -> AsyncMock:
    """Mock Temporal client."""
    client = AsyncMock()

    # Mock workflow execution
    handle = AsyncMock()
    handle.workflow_id = "sync-test_user_123-1699564832-a3f9d"
    handle.result = AsyncMock(return_value=WorkflowResult(
        success=True,
        message="Successfully added track to playlist",
        spotify_track_id="7tFiyTwD0nx5a1eklYtX2J",
        spotify_track_uri="spotify:track:7tFiyTwD0nx5a1eklYtX2J",
        confidence_score=0.95,
        execution_time_seconds=4.2,
        retry_count=0,
        match_method="fuzzy",
    ))
    handle.query = AsyncMock(return_value=WorkflowProgress(
        current_step="Searching Spotify",
        steps_completed=2,
        steps_total=5,
        candidates_found=3,
        elapsed_seconds=2.5,
    ))
    handle.cancel = AsyncMock()

    client.start_workflow = AsyncMock(return_value=handle)
    client.get_workflow_handle = AsyncMock(return_value=handle)

    return client


@pytest.fixture
def mock_langchain_llm() -> Mock:
    """Mock LangChain LLM."""
    llm = Mock()
    llm.invoke.return_value = Mock(
        content='{"selected_track_id": "7tFiyTwD0nx5a1eklYtX2J", "reasoning": "Exact match"}'
    )
    return llm


# ==================== FastAPI Test Client ====================


@pytest.fixture
async def test_client(mock_temporal_client) -> AsyncGenerator[TestClient, None]:
    """FastAPI test client with mocked dependencies."""
    # Import app here to ensure environment variables are set
    from api.app import app

    # Override temporal client dependency
    app.state.temporal_client = mock_temporal_client

    with TestClient(app) as client:
        yield client


# ==================== Environment Fixtures ====================


@pytest.fixture(autouse=True)
def test_env():
    """Ensure test environment variables are set for all tests."""
    original_env = os.environ.copy()

    os.environ.update({
        "ENVIRONMENT": "test",
        "SPOTIFY_CLIENT_ID": "test_client_id",
        "SPOTIFY_CLIENT_SECRET": "test_client_secret",
        "OPENAI_API_KEY": "test_openai_key",
        "TEMPORAL_HOST": "localhost:7233",
        "TEMPORAL_NAMESPACE": "test",
        "LOG_LEVEL": "ERROR",  # Reduce noise in tests
    })

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def temp_env(monkeypatch):
    """Fixture for temporarily modifying environment variables."""
    def set_env(**kwargs):
        for key, value in kwargs.items():
            monkeypatch.setenv(key, value)

    return set_env


# ==================== Temporal Test Fixtures ====================


@pytest.fixture
def mock_activity_environment():
    """Mock Temporal activity environment."""
    from temporalio import activity

    info = Mock()
    info.activity_id = "test-activity-123"
    info.workflow_id = "test-workflow-456"
    info.attempt = 1

    return info


# ==================== Data Generation Helpers ====================


@pytest.fixture
def make_song_metadata():
    """Factory fixture for creating song metadata."""
    def _make(
        title: str = "Test Song",
        artist: str = "Test Artist",
        album: str = "Test Album",
        duration_ms: int = 200000,
        isrc: str = None,
    ) -> SongMetadata:
        return SongMetadata(
            title=title,
            artist=artist,
            album=album,
            duration_ms=duration_ms,
            isrc=isrc,
        )

    return _make


@pytest.fixture
def make_spotify_track():
    """Factory fixture for creating Spotify track results."""
    def _make(
        track_id: str = "test_track_id",
        track_name: str = "Test Song",
        artist_name: str = "Test Artist",
        album_name: str = "Test Album",
        popularity: int = 50,
    ) -> SpotifyTrackResult:
        return SpotifyTrackResult(
            track_id=track_id,
            track_name=track_name,
            artist_name=artist_name,
            album_name=album_name,
            spotify_uri=f"spotify:track:{track_id}",
            duration_ms=200000,
            popularity=popularity,
            release_date="2020-01-01",
            isrc="TEST12345678",
        )

    return _make


# ==================== Async Test Helpers ====================


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
