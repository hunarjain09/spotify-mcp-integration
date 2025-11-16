"""MCP client wrapper for communicating with the Spotify MCP server."""

import json
import asyncio
from typing import Dict, Any, Optional
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class SpotifyMCPClient:
    """Client for communicating with Spotify MCP server."""

    def __init__(self, server_script_path: Optional[Path] = None):
        """Initialize MCP client.

        Args:
            server_script_path: Path to the MCP server script. If None, uses default location.
        """
        self.session: Optional[ClientSession] = None
        self.read_stream = None
        self.write_stream = None

        if server_script_path is None:
            # Default to mcp_server/spotify_server.py
            server_script_path = Path(__file__).parent.parent / "mcp_server" / "spotify_server.py"

        self.server_params = StdioServerParameters(
            command="python", args=[str(server_script_path)], env=None
        )

    async def connect(self):
        """Connect to the MCP server."""
        if self.session is not None:
            raise RuntimeError("Client is already connected")

        self.read_stream, self.write_stream = await stdio_client(self.server_params)
        self.session = ClientSession(self.read_stream, self.write_stream)

        await self.session.initialize()

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool and return the parsed result.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments as a dictionary

        Returns:
            Parsed JSON result from the tool

        Raises:
            RuntimeError: If client is not connected
            ValueError: If tool returns an error
        """
        if self.session is None:
            raise RuntimeError("Client is not connected. Call connect() first.")

        result = await self.session.call_tool(tool_name, arguments)

        # Parse result content
        if result.content and len(result.content) > 0:
            text_content = result.content[0].text
            parsed = json.loads(text_content)

            # Check for errors in response
            if "error" in parsed:
                raise ValueError(f"Tool '{tool_name}' returned error: {parsed['error']}")

            return parsed

        return {}

    async def search_track(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search for tracks on Spotify.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            Dictionary with 'tracks' key containing list of track results
        """
        return await self.call_tool("search_track", {"query": query, "limit": limit})

    async def add_track_to_playlist(self, track_uri: str, playlist_id: str) -> Dict[str, Any]:
        """Add a track to a playlist.

        Args:
            track_uri: Spotify track URI
            playlist_id: Spotify playlist ID

        Returns:
            Snapshot ID of the playlist after modification
        """
        return await self.call_tool(
            "add_track_to_playlist", {"track_uri": track_uri, "playlist_id": playlist_id}
        )

    async def get_audio_features(self, track_id: str) -> Dict[str, Any]:
        """Get audio features for a track.

        Args:
            track_id: Spotify track ID

        Returns:
            Audio features dictionary
        """
        return await self.call_tool("get_audio_features", {"track_id": track_id})

    async def verify_track_added(self, track_uri: str, playlist_id: str) -> bool:
        """Verify if a track is in a playlist.

        Args:
            track_uri: Spotify track URI
            playlist_id: Spotify playlist ID

        Returns:
            True if track is in playlist, False otherwise
        """
        result = await self.call_tool(
            "verify_track_added", {"track_uri": track_uri, "playlist_id": playlist_id}
        )
        return result.get("is_added", False)

    async def get_user_playlists(self, limit: int = 50) -> Dict[str, Any]:
        """Get user's playlists.

        Args:
            limit: Maximum number of playlists to return

        Returns:
            Dictionary with 'playlists' key containing list of playlists
        """
        return await self.call_tool("get_user_playlists", {"limit": limit})

    async def search_by_isrc(self, isrc: str) -> Optional[Dict[str, Any]]:
        """Search for a track by ISRC code.

        Args:
            isrc: International Standard Recording Code

        Returns:
            Track dictionary if found, None otherwise
        """
        result = await self.call_tool("search_by_isrc", {"isrc": isrc})
        return result.get("track") if result.get("found") else None

    async def close(self):
        """Close the MCP connection."""
        if self.session is not None:
            await self.session.close()
            self.session = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# Singleton instance for reuse across activities
_global_client: Optional[SpotifyMCPClient] = None


async def get_spotify_mcp_client() -> SpotifyMCPClient:
    """Get or create a global MCP client instance.

    Returns:
        Connected SpotifyMCPClient instance
    """
    global _global_client

    if _global_client is None:
        _global_client = SpotifyMCPClient()
        await _global_client.connect()

    return _global_client
