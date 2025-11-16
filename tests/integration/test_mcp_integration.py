"""Integration tests for MCP Client and Server with minimal mocking.

These tests verify the MCP protocol communication between client and server,
mocking only the final Spotify API calls.
"""

import pytest
from unittest.mock import patch, Mock, AsyncMock
import json

from mcp_client.client import SpotifyMCPClient
from models.data_models import SpotifyTrackResult


class TestMCPClientServerIntegration:
    """Integration tests for MCP client-server communication."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_mcp_search_track_integration(self):
        """Test MCP client calling server's search_track tool."""
        # Mock only Spotipy (the Spotify SDK), not the MCP layer
        with patch("mcp_server.spotify_server.spotipy.Spotify") as mock_spotify:
            # Setup Spotify mock
            mock_sp = Mock()
            mock_sp.search.return_value = {
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
            mock_spotify.return_value = mock_sp

            # Create MCP client and test real communication
            client = SpotifyMCPClient()

            # This tests the actual MCP protocol, parsing, and data transformation
            result = await client.search_track("Bohemian Rhapsody Queen", limit=10)

            # Verify the result
            assert "tracks" in result
            assert len(result["tracks"]) == 1

            track = result["tracks"][0]
            assert track["id"] == "7tFiyTwD0nx5a1eklYtX2J"
            assert track["name"] == "Bohemian Rhapsody"
            assert track["artist"] == "Queen"
            assert track["album"] == "A Night at the Opera"
            assert track["isrc"] == "GBUM71029604"

            # Verify Spotify was called correctly
            mock_sp.search.assert_called_once_with(
                q="Bohemian Rhapsody Queen",
                type="track",
                limit=10,
            )

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_mcp_add_track_to_playlist_integration(self):
        """Test MCP client adding track to playlist through server."""
        with patch("mcp_server.spotify_server.spotipy.Spotify") as mock_spotify:
            mock_sp = Mock()
            mock_sp.playlist_add_items.return_value = {
                "snapshot_id": "test_snapshot_123"
            }
            mock_spotify.return_value = mock_sp

            client = SpotifyMCPClient()

            result = await client.add_track_to_playlist(
                track_id="7tFiyTwD0nx5a1eklYtX2J",
                playlist_id="37i9dQZF1DXcBWIGoYBM5M",
            )

            assert result["snapshot_id"] == "test_snapshot_123"

            # Verify the correct Spotify API call was made
            mock_sp.playlist_add_items.assert_called_once_with(
                playlist_id="37i9dQZF1DXcBWIGoYBM5M",
                items=["spotify:track:7tFiyTwD0nx5a1eklYtX2J"],
            )

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_mcp_verify_track_added_integration(self):
        """Test MCP client verifying track was added to playlist."""
        with patch("mcp_server.spotify_server.spotipy.Spotify") as mock_spotify:
            mock_sp = Mock()
            mock_sp.playlist_items.return_value = {
                "items": [
                    {
                        "track": {
                            "id": "7tFiyTwD0nx5a1eklYtX2J",
                            "uri": "spotify:track:7tFiyTwD0nx5a1eklYtX2J",
                        }
                    },
                    {
                        "track": {
                            "id": "other_track",
                            "uri": "spotify:track:other_track",
                        }
                    },
                ]
            }
            mock_spotify.return_value = mock_sp

            client = SpotifyMCPClient()

            result = await client.verify_track_added(
                track_id="7tFiyTwD0nx5a1eklYtX2J",
                playlist_id="37i9dQZF1DXcBWIGoYBM5M",
            )

            assert result is True

            # Verify track not in playlist
            result_not_found = await client.verify_track_added(
                track_id="non_existent_track",
                playlist_id="37i9dQZF1DXcBWIGoYBM5M",
            )

            assert result_not_found is False

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_mcp_search_by_isrc_integration(self):
        """Test MCP client searching by ISRC."""
        with patch("mcp_server.spotify_server.spotipy.Spotify") as mock_spotify:
            mock_sp = Mock()
            mock_sp.search.return_value = {
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
            mock_spotify.return_value = mock_sp

            client = SpotifyMCPClient()

            result = await client.search_by_isrc("GBUM71029604")

            assert result is not None
            assert result["id"] == "7tFiyTwD0nx5a1eklYtX2J"
            assert result["isrc"] == "GBUM71029604"

            # Verify ISRC search query format
            mock_sp.search.assert_called_once_with(
                q="isrc:GBUM71029604",
                type="track",
                limit=1,
            )

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_mcp_get_audio_features_integration(self):
        """Test MCP client retrieving audio features."""
        with patch("mcp_server.spotify_server.spotipy.Spotify") as mock_spotify:
            mock_sp = Mock()
            mock_sp.audio_features.return_value = [
                {
                    "danceability": 0.517,
                    "energy": 0.359,
                    "key": 10,
                    "loudness": -11.840,
                    "mode": 0,
                    "speechiness": 0.0512,
                    "acousticness": 0.364,
                    "instrumentalness": 0.0000802,
                    "liveness": 0.213,
                    "valence": 0.276,
                    "tempo": 144.017,
                    "duration_ms": 354000,
                }
            ]
            mock_spotify.return_value = mock_sp

            client = SpotifyMCPClient()

            result = await client.get_audio_features("7tFiyTwD0nx5a1eklYtX2J")

            assert result is not None
            assert result["danceability"] == 0.517
            assert result["energy"] == 0.359
            assert result["tempo"] == 144.017

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_mcp_error_handling(self):
        """Test MCP client handling of Spotify API errors."""
        with patch("mcp_server.spotify_server.spotipy.Spotify") as mock_spotify:
            mock_sp = Mock()
            mock_sp.search.side_effect = Exception("Spotify API error")
            mock_spotify.return_value = mock_sp

            client = SpotifyMCPClient()

            with pytest.raises(Exception) as exc_info:
                await client.search_track("Test Query")

            assert "Spotify API error" in str(exc_info.value)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_mcp_empty_search_results(self):
        """Test MCP client handling of empty search results."""
        with patch("mcp_server.spotify_server.spotipy.Spotify") as mock_spotify:
            mock_sp = Mock()
            mock_sp.search.return_value = {
                "tracks": {
                    "items": []
                }
            }
            mock_spotify.return_value = mock_sp

            client = SpotifyMCPClient()

            result = await client.search_track("Nonexistent Song That Doesn't Exist")

            assert "tracks" in result
            assert len(result["tracks"]) == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_mcp_handles_missing_isrc(self):
        """Test MCP client handling tracks without ISRC."""
        with patch("mcp_server.spotify_server.spotipy.Spotify") as mock_spotify:
            mock_sp = Mock()
            mock_sp.search.return_value = {
                "tracks": {
                    "items": [
                        {
                            "id": "track_no_isrc",
                            "name": "Indie Track",
                            "artists": [{"name": "Indie Artist"}],
                            "album": {
                                "name": "Indie Album",
                                "release_date": "2023-01-01",
                            },
                            "uri": "spotify:track:track_no_isrc",
                            "duration_ms": 200000,
                            "popularity": 45,
                            "external_ids": {},  # No ISRC
                        }
                    ]
                }
            }
            mock_spotify.return_value = mock_sp

            client = SpotifyMCPClient()

            result = await client.search_track("Indie Track")

            assert len(result["tracks"]) == 1
            track = result["tracks"][0]
            assert track["id"] == "track_no_isrc"
            assert track.get("isrc") is None  # Should handle missing ISRC gracefully

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_mcp_multiple_artists(self):
        """Test MCP client handling tracks with multiple artists."""
        with patch("mcp_server.spotify_server.spotipy.Spotify") as mock_spotify:
            mock_sp = Mock()
            mock_sp.search.return_value = {
                "tracks": {
                    "items": [
                        {
                            "id": "collab_track",
                            "name": "Collaboration Song",
                            "artists": [
                                {"name": "Artist One"},
                                {"name": "Artist Two"},
                                {"name": "Artist Three"},
                            ],
                            "album": {
                                "name": "Collab Album",
                                "release_date": "2023-06-15",
                            },
                            "uri": "spotify:track:collab_track",
                            "duration_ms": 220000,
                            "popularity": 75,
                            "external_ids": {"isrc": "COLLAB123456"},
                        }
                    ]
                }
            }
            mock_spotify.return_value = mock_sp

            client = SpotifyMCPClient()

            result = await client.search_track("Collaboration Song")

            track = result["tracks"][0]
            # MCP client should format multiple artists properly
            assert "Artist One" in track["artist"]  # First artist should be included

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_mcp_pagination_handling(self):
        """Test MCP client with different result limits."""
        with patch("mcp_server.spotify_server.spotipy.Spotify") as mock_spotify:
            mock_sp = Mock()

            # Simulate 5 results
            mock_sp.search.return_value = {
                "tracks": {
                    "items": [
                        {
                            "id": f"track_{i}",
                            "name": f"Track {i}",
                            "artists": [{"name": "Artist"}],
                            "album": {"name": "Album", "release_date": "2023-01-01"},
                            "uri": f"spotify:track:track_{i}",
                            "duration_ms": 200000,
                            "popularity": 70,
                            "external_ids": {},
                        }
                        for i in range(5)
                    ]
                }
            }
            mock_spotify.return_value = mock_sp

            client = SpotifyMCPClient()

            # Test with limit=5
            result = await client.search_track("Test Query", limit=5)
            assert len(result["tracks"]) == 5

            # Verify limit was passed to Spotify API
            mock_sp.search.assert_called_with(
                q="Test Query",
                type="track",
                limit=5,
            )

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_mcp_connection_lifecycle(self):
        """Test MCP client connection and disconnection."""
        with patch("mcp_server.spotify_server.spotipy.Spotify") as mock_spotify:
            mock_sp = Mock()
            mock_sp.search.return_value = {"tracks": {"items": []}}
            mock_spotify.return_value = mock_sp

            client = SpotifyMCPClient()

            # Test connection
            await client.connect()

            # Test operation
            await client.search_track("Test")

            # Test disconnection
            await client.disconnect()

            # Verify client can be used again after reconnection
            await client.connect()
            result = await client.search_track("Test Again")
            assert "tracks" in result
