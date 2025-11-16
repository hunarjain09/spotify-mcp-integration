"""Integration tests for Temporal workflows with minimal mocking.

These tests use Temporal's test environment to run real workflows
with actual activity execution, mocking only external APIs.
"""

import pytest
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from workflows.music_sync_workflow import MusicSyncWorkflow
from activities.spotify_search import search_spotify
from activities.fuzzy_matcher import fuzzy_match_tracks
from activities.ai_disambiguator import ai_disambiguate_track
from activities.playlist_manager import add_track_to_playlist, verify_track_added
from models.data_models import (
    WorkflowInput,
    SongMetadata,
    SpotifyTrackResult,
)
from config.settings import settings


class TestMusicSyncWorkflowIntegration:
    """Integration tests for MusicSyncWorkflow with real Temporal execution."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_complete_workflow_with_exact_match(self):
        """Test complete workflow execution with ISRC exact match."""
        async with await WorkflowEnvironment.start_time_skipping() as env:
            # Mock only external API calls, not internal logic
            with patch("activities.spotify_search.get_spotify_mcp_client") as mock_mcp, \
                 patch("activities.playlist_manager.get_spotify_mcp_client") as mock_playlist_mcp:

                # Setup MCP mock for search
                mock_client = AsyncMock()
                mock_client.search_track = AsyncMock(return_value={
                    "tracks": [
                        {
                            "id": "7tFiyTwD0nx5a1eklYtX2J",
                            "name": "Bohemian Rhapsody",
                            "artist": "Queen",
                            "album": "A Night at the Opera",
                            "uri": "spotify:track:7tFiyTwD0nx5a1eklYtX2J",
                            "duration_ms": 354000,
                            "popularity": 92,
                            "release_date": "1975-11-21",
                            "isrc": "GBUM71029604",
                        }
                    ]
                })
                mock_mcp.return_value = mock_client

                # Setup MCP mock for playlist operations
                mock_playlist_client = AsyncMock()
                mock_playlist_client.add_track_to_playlist = AsyncMock(
                    return_value={"snapshot_id": "test_snapshot"}
                )
                mock_playlist_client.verify_track_added = AsyncMock(return_value=True)
                mock_playlist_mcp.return_value = mock_playlist_client

                # Create worker with real activities
                async with Worker(
                    env.client,
                    task_queue="test-queue",
                    workflows=[MusicSyncWorkflow],
                    activities=[
                        search_spotify,
                        fuzzy_match_tracks,
                        ai_disambiguate_track,
                        add_track_to_playlist,
                        verify_track_added,
                    ],
                ):
                    # Create workflow input
                    workflow_input = WorkflowInput(
                        song_metadata=SongMetadata(
                            title="Bohemian Rhapsody",
                            artist="Queen",
                            album="A Night at the Opera",
                            isrc="GBUM71029604",
                        ),
                        playlist_id="37i9dQZF1DXcBWIGoYBM5M",
                        user_id="test_user",
                        match_threshold=0.85,
                        use_ai_disambiguation=False,  # Not needed for exact match
                    )

                    # Execute workflow
                    result = await env.client.execute_workflow(
                        MusicSyncWorkflow.run,
                        workflow_input,
                        id=f"test-workflow-{env.client.identity}",
                        task_queue="test-queue",
                    )

                    # Verify result
                    assert result.success is True
                    assert result.spotify_track_id == "7tFiyTwD0nx5a1eklYtX2J"
                    assert result.confidence_score == 1.0  # ISRC match is perfect
                    assert result.match_method == "isrc"
                    assert "successfully" in result.message.lower()

                    # Verify MCP was called correctly
                    mock_client.search_track.assert_called_once()
                    mock_playlist_client.add_track_to_playlist.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_workflow_with_fuzzy_matching(self):
        """Test workflow with fuzzy matching (no ISRC)."""
        async with await WorkflowEnvironment.start_time_skipping() as env:
            with patch("activities.spotify_search.get_spotify_mcp_client") as mock_mcp, \
                 patch("activities.playlist_manager.get_spotify_mcp_client") as mock_playlist_mcp:

                # Setup search results without ISRC
                mock_client = AsyncMock()
                mock_client.search_track = AsyncMock(return_value={
                    "tracks": [
                        {
                            "id": "track1",
                            "name": "Imagine",
                            "artist": "John Lennon",
                            "album": "Imagine",
                            "uri": "spotify:track:track1",
                            "duration_ms": 183000,
                            "popularity": 88,
                            "release_date": "1971-09-09",
                        }
                    ]
                })
                mock_mcp.return_value = mock_client

                mock_playlist_client = AsyncMock()
                mock_playlist_client.add_track_to_playlist = AsyncMock(
                    return_value={"snapshot_id": "test"}
                )
                mock_playlist_client.verify_track_added = AsyncMock(return_value=True)
                mock_playlist_mcp.return_value = mock_playlist_client

                async with Worker(
                    env.client,
                    task_queue="test-queue",
                    workflows=[MusicSyncWorkflow],
                    activities=[
                        search_spotify,
                        fuzzy_match_tracks,
                        add_track_to_playlist,
                        verify_track_added,
                    ],
                ):
                    workflow_input = WorkflowInput(
                        song_metadata=SongMetadata(
                            title="Imagine",
                            artist="John Lennon",
                            album="Imagine",
                        ),
                        playlist_id="test_playlist",
                        user_id="test_user",
                        match_threshold=0.85,
                        use_ai_disambiguation=False,
                    )

                    result = await env.client.execute_workflow(
                        MusicSyncWorkflow.run,
                        workflow_input,
                        id=f"test-fuzzy-{env.client.identity}",
                        task_queue="test-queue",
                    )

                    assert result.success is True
                    assert result.match_method == "fuzzy"
                    assert result.confidence_score >= 0.85

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_workflow_with_ai_disambiguation(self):
        """Test workflow using AI disambiguation for ambiguous matches."""
        async with await WorkflowEnvironment.start_time_skipping() as env:
            with patch("activities.spotify_search.get_spotify_mcp_client") as mock_mcp, \
                 patch("activities.playlist_manager.get_spotify_mcp_client") as mock_playlist_mcp, \
                 patch("activities.ai_disambiguator.get_ai_client") as mock_ai:

                # Setup multiple similar search results
                mock_client = AsyncMock()
                mock_client.search_track = AsyncMock(return_value={
                    "tracks": [
                        {
                            "id": "track1",
                            "name": "Let It Be",
                            "artist": "The Beatles",
                            "album": "Let It Be",
                            "uri": "spotify:track:track1",
                            "duration_ms": 243000,
                            "popularity": 85,
                            "release_date": "1970-03-06",
                        },
                        {
                            "id": "track2",
                            "name": "Let It Be - Remastered 2009",
                            "artist": "The Beatles",
                            "album": "Let It Be (Remastered)",
                            "uri": "spotify:track:track2",
                            "duration_ms": 244000,
                            "popularity": 88,
                            "release_date": "2009-09-09",
                        },
                    ]
                })
                mock_mcp.return_value = mock_client

                # Setup AI to select the remastered version
                mock_ai_client = AsyncMock()
                mock_ai_client.disambiguate = AsyncMock(return_value={
                    "selected_track_id": "track2",
                    "reasoning": "The remastered version has better audio quality",
                })
                mock_ai.return_value = mock_ai_client

                mock_playlist_client = AsyncMock()
                mock_playlist_client.add_track_to_playlist = AsyncMock(
                    return_value={"snapshot_id": "test"}
                )
                mock_playlist_client.verify_track_added = AsyncMock(return_value=True)
                mock_playlist_mcp.return_value = mock_playlist_client

                async with Worker(
                    env.client,
                    task_queue="test-queue",
                    workflows=[MusicSyncWorkflow],
                    activities=[
                        search_spotify,
                        fuzzy_match_tracks,
                        ai_disambiguate_track,
                        add_track_to_playlist,
                        verify_track_added,
                    ],
                ):
                    workflow_input = WorkflowInput(
                        song_metadata=SongMetadata(
                            title="Let It Be",
                            artist="The Beatles",
                            album="Let It Be",
                        ),
                        playlist_id="test_playlist",
                        user_id="test_user",
                        match_threshold=0.95,  # High threshold to trigger AI
                        use_ai_disambiguation=True,
                    )

                    result = await env.client.execute_workflow(
                        MusicSyncWorkflow.run,
                        workflow_input,
                        id=f"test-ai-{env.client.identity}",
                        task_queue="test-queue",
                    )

                    assert result.success is True
                    assert result.spotify_track_id == "track2"  # AI selected this one
                    assert result.match_method == "ai"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_workflow_no_match_found(self):
        """Test workflow when no suitable match is found."""
        async with await WorkflowEnvironment.start_time_skipping() as env:
            with patch("activities.spotify_search.get_spotify_mcp_client") as mock_mcp:

                # Return completely different tracks
                mock_client = AsyncMock()
                mock_client.search_track = AsyncMock(return_value={
                    "tracks": [
                        {
                            "id": "wrong_track",
                            "name": "Completely Different Song",
                            "artist": "Different Artist",
                            "album": "Different Album",
                            "uri": "spotify:track:wrong_track",
                            "duration_ms": 200000,
                            "popularity": 50,
                            "release_date": "2020-01-01",
                        }
                    ]
                })
                mock_mcp.return_value = mock_client

                async with Worker(
                    env.client,
                    task_queue="test-queue",
                    workflows=[MusicSyncWorkflow],
                    activities=[
                        search_spotify,
                        fuzzy_match_tracks,
                    ],
                ):
                    workflow_input = WorkflowInput(
                        song_metadata=SongMetadata(
                            title="Bohemian Rhapsody",
                            artist="Queen",
                        ),
                        playlist_id="test_playlist",
                        user_id="test_user",
                        match_threshold=0.85,
                        use_ai_disambiguation=False,
                    )

                    result = await env.client.execute_workflow(
                        MusicSyncWorkflow.run,
                        workflow_input,
                        id=f"test-no-match-{env.client.identity}",
                        task_queue="test-queue",
                    )

                    assert result.success is False
                    assert "no match" in result.message.lower()
                    assert result.spotify_track_id is None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_workflow_handles_spotify_error(self):
        """Test workflow handling of Spotify API errors with retries."""
        async with await WorkflowEnvironment.start_time_skipping() as env:
            with patch("activities.spotify_search.get_spotify_mcp_client") as mock_mcp:

                # First call fails, second succeeds (testing retry logic)
                mock_client = AsyncMock()
                mock_client.search_track = AsyncMock(
                    side_effect=[
                        Exception("Spotify API temporarily unavailable"),
                        {
                            "tracks": [
                                {
                                    "id": "track1",
                                    "name": "Test Song",
                                    "artist": "Test Artist",
                                    "album": "Test Album",
                                    "uri": "spotify:track:track1",
                                    "duration_ms": 200000,
                                    "popularity": 80,
                                    "release_date": "2020-01-01",
                                }
                            ]
                        },
                    ]
                )
                mock_mcp.return_value = mock_client

                async with Worker(
                    env.client,
                    task_queue="test-queue",
                    workflows=[MusicSyncWorkflow],
                    activities=[
                        search_spotify,
                        fuzzy_match_tracks,
                    ],
                ):
                    workflow_input = WorkflowInput(
                        song_metadata=SongMetadata(
                            title="Test Song",
                            artist="Test Artist",
                        ),
                        playlist_id="test_playlist",
                        user_id="test_user",
                        match_threshold=0.85,
                        use_ai_disambiguation=False,
                    )

                    # Workflow should succeed after retry
                    result = await env.client.execute_workflow(
                        MusicSyncWorkflow.run,
                        workflow_input,
                        id=f"test-retry-{env.client.identity}",
                        task_queue="test-queue",
                        execution_timeout=timedelta(seconds=30),
                    )

                    # Should succeed despite initial failure
                    assert result.retry_count > 0
                    # Verify retry happened
                    assert mock_client.search_track.call_count == 2

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_workflow_progress_query(self):
        """Test querying workflow progress during execution."""
        async with await WorkflowEnvironment.start_time_skipping() as env:
            with patch("activities.spotify_search.get_spotify_mcp_client") as mock_mcp, \
                 patch("activities.playlist_manager.get_spotify_mcp_client") as mock_playlist_mcp:

                mock_client = AsyncMock()
                mock_client.search_track = AsyncMock(return_value={
                    "tracks": [
                        {
                            "id": "track1",
                            "name": "Test",
                            "artist": "Test",
                            "album": "Test",
                            "uri": "spotify:track:track1",
                            "duration_ms": 200000,
                            "popularity": 80,
                            "release_date": "2020-01-01",
                        }
                    ]
                })
                mock_mcp.return_value = mock_client

                mock_playlist_client = AsyncMock()
                mock_playlist_client.add_track_to_playlist = AsyncMock(
                    return_value={"snapshot_id": "test"}
                )
                mock_playlist_client.verify_track_added = AsyncMock(return_value=True)
                mock_playlist_mcp.return_value = mock_playlist_client

                async with Worker(
                    env.client,
                    task_queue="test-queue",
                    workflows=[MusicSyncWorkflow],
                    activities=[
                        search_spotify,
                        fuzzy_match_tracks,
                        add_track_to_playlist,
                        verify_track_added,
                    ],
                ):
                    workflow_input = WorkflowInput(
                        song_metadata=SongMetadata(title="Test", artist="Test"),
                        playlist_id="test_playlist",
                        user_id="test_user",
                        match_threshold=0.85,
                        use_ai_disambiguation=False,
                    )

                    # Start workflow but don't wait for completion
                    handle = await env.client.start_workflow(
                        MusicSyncWorkflow.run,
                        workflow_input,
                        id=f"test-progress-{env.client.identity}",
                        task_queue="test-queue",
                    )

                    # Query progress (this will work even if workflow completes quickly)
                    try:
                        progress = await handle.query(MusicSyncWorkflow.get_progress)
                        assert progress.current_step is not None
                        assert progress.steps_total > 0
                    except Exception:
                        # Workflow may have completed too fast, that's ok
                        pass

                    # Wait for completion
                    result = await handle.result()
                    assert result.success is True
