"""Integration tests for Spotify search activity."""

import pytest
from unittest.mock import AsyncMock, patch, Mock
from datetime import timedelta
import httpx

from activities.spotify_search import search_spotify
from models.data_models import SongMetadata, SpotifyTrackResult
from temporalio import activity


class TestSpotifySearch:
    """Tests for search_spotify activity."""

    @pytest.mark.asyncio
    @patch("activities.spotify_search.get_spotify_mcp_client")
    async def test_search_success(self, mock_get_client, sample_song_metadata):
        """Test successful Spotify search."""
        # Mock MCP client
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
        mock_get_client.return_value = mock_client

        results = await search_spotify(sample_song_metadata)

        assert len(results) == 1
        assert isinstance(results[0], SpotifyTrackResult)
        assert results[0].track_id == "7tFiyTwD0nx5a1eklYtX2J"
        assert results[0].track_name == "Bohemian Rhapsody"
        assert results[0].artist_name == "Queen"

    @pytest.mark.asyncio
    @patch("activities.spotify_search.get_spotify_mcp_client")
    async def test_search_multiple_results(self, mock_get_client, sample_song_metadata):
        """Test search returning multiple results."""
        # Mock MCP client with multiple tracks
        mock_client = AsyncMock()
        mock_client.search_track = AsyncMock(return_value={
            "tracks": [
                {
                    "id": "track1",
                    "name": "Bohemian Rhapsody",
                    "artist": "Queen",
                    "album": "A Night at the Opera",
                    "uri": "spotify:track:track1",
                    "duration_ms": 354000,
                    "popularity": 92,
                    "release_date": "1975-11-21",
                    "isrc": "GBUM71029604",
                },
                {
                    "id": "track2",
                    "name": "Bohemian Rhapsody - Remastered",
                    "artist": "Queen",
                    "album": "A Night at the Opera - 2011 Remaster",
                    "uri": "spotify:track:track2",
                    "duration_ms": 354500,
                    "popularity": 88,
                    "release_date": "2011-09-05",
                },
            ]
        })
        mock_get_client.return_value = mock_client

        results = await search_spotify(sample_song_metadata)

        assert len(results) == 2
        assert results[0].track_id == "track1"
        assert results[1].track_id == "track2"

    @pytest.mark.asyncio
    @patch("activities.spotify_search.get_spotify_mcp_client")
    async def test_search_no_results(self, mock_get_client, sample_song_metadata):
        """Test search with no results."""
        # Mock MCP client with empty results
        mock_client = AsyncMock()
        mock_client.search_track = AsyncMock(return_value={"tracks": []})
        mock_get_client.return_value = mock_client

        results = await search_spotify(sample_song_metadata)

        assert len(results) == 0

    @pytest.mark.asyncio
    @patch("activities.spotify_search.get_spotify_mcp_client")
    async def test_search_track_without_isrc(self, mock_get_client, sample_song_metadata):
        """Test search result without ISRC."""
        # Mock MCP client
        mock_client = AsyncMock()
        mock_client.search_track = AsyncMock(return_value={
            "tracks": [
                {
                    "id": "track_no_isrc",
                    "name": "Test Song",
                    "artist": "Test Artist",
                    "album": "Test Album",
                    "uri": "spotify:track:track_no_isrc",
                    "duration_ms": 200000,
                    "popularity": 50,
                    "release_date": "2020-01-01",
                    # No ISRC
                }
            ]
        })
        mock_get_client.return_value = mock_client

        results = await search_spotify(sample_song_metadata)

        assert len(results) == 1
        assert results[0].isrc is None

    @pytest.mark.asyncio
    @patch("activities.spotify_search.get_spotify_mcp_client")
    async def test_search_rate_limit_error(self, mock_get_client, sample_song_metadata):
        """Test handling of rate limit errors."""
        # Mock rate limit response
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}

        mock_client = AsyncMock()
        mock_client.search_track = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Rate limit exceeded",
                request=Mock(),
                response=mock_response,
            )
        )
        mock_get_client.return_value = mock_client

        with pytest.raises(activity.ApplicationError) as exc_info:
            await search_spotify(sample_song_metadata)

        error = exc_info.value
        assert "rate limit" in str(error).lower()
        assert error.non_retryable is False

    @pytest.mark.asyncio
    @patch("activities.spotify_search.get_spotify_mcp_client")
    async def test_search_http_error(self, mock_get_client, sample_song_metadata):
        """Test handling of other HTTP errors."""
        # Mock 500 error
        mock_response = Mock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.search_track = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Internal server error",
                request=Mock(),
                response=mock_response,
            )
        )
        mock_get_client.return_value = mock_client

        with pytest.raises(activity.ApplicationError) as exc_info:
            await search_spotify(sample_song_metadata)

        error = exc_info.value
        assert "500" in str(error)
        assert error.non_retryable is False

    @pytest.mark.asyncio
    @patch("activities.spotify_search.get_spotify_mcp_client")
    async def test_search_mcp_error(self, mock_get_client, sample_song_metadata):
        """Test handling of MCP tool errors."""
        mock_client = AsyncMock()
        mock_client.search_track = AsyncMock(side_effect=ValueError("MCP tool error"))
        mock_get_client.return_value = mock_client

        with pytest.raises(activity.ApplicationError) as exc_info:
            await search_spotify(sample_song_metadata)

        error = exc_info.value
        assert "MCP tool error" in str(error)
        assert error.non_retryable is True
        assert error.type == "MCPToolError"

    @pytest.mark.asyncio
    @patch("activities.spotify_search.get_spotify_mcp_client")
    async def test_search_unexpected_error(self, mock_get_client, sample_song_metadata):
        """Test handling of unexpected errors."""
        mock_client = AsyncMock()
        mock_client.search_track = AsyncMock(
            side_effect=Exception("Unexpected error")
        )
        mock_get_client.return_value = mock_client

        with pytest.raises(activity.ApplicationError) as exc_info:
            await search_spotify(sample_song_metadata)

        error = exc_info.value
        assert "Search failed" in str(error)
        assert error.non_retryable is False
