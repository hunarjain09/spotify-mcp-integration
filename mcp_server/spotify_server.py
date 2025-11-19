"""MCP server for Spotify API operations.

This server exposes Spotify API functionality as MCP tools that can be used
by activities and AI agents.
"""

import asyncio
import json
import os
import sys
from typing import Any, Dict, List

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import Tool
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# Initialize MCP server
app = Server("spotify-mcp-server")

# Spotify client (will be initialized in main)
spotify_client: spotipy.Spotify = None


@app.list_tools()
async def list_tools() -> List[Tool]:
    """Register available Spotify tools."""
    return [
        Tool(
            name="search_track",
            description="Search Spotify catalog for tracks by query string",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (can use track:, artist:, album: prefixes)",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 10,
                        "description": "Maximum number of results to return (1-50)",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="add_track_to_playlist",
            description="Add a track to a Spotify playlist",
            inputSchema={
                "type": "object",
                "properties": {
                    "track_uri": {
                        "type": "string",
                        "description": "Spotify track URI (spotify:track:xxxxx)",
                    },
                    "playlist_id": {
                        "type": "string",
                        "description": "Spotify playlist ID",
                    },
                },
                "required": ["track_uri", "playlist_id"],
            },
        ),
        Tool(
            name="verify_track_added",
            description="Check if a track exists in a playlist",
            inputSchema={
                "type": "object",
                "properties": {
                    "track_uri": {
                        "type": "string",
                        "description": "Spotify track URI to check",
                    },
                    "playlist_id": {
                        "type": "string",
                        "description": "Spotify playlist ID",
                    },
                },
                "required": ["track_uri", "playlist_id"],
            },
        ),
        Tool(
            name="get_user_playlists",
            description="List user's Spotify playlists",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "default": 50,
                        "description": "Maximum number of playlists to return",
                    }
                },
            },
        ),
        Tool(
            name="search_by_isrc",
            description="Search for exact track match using ISRC code",
            inputSchema={
                "type": "object",
                "properties": {
                    "isrc": {
                        "type": "string",
                        "description": "International Standard Recording Code",
                    }
                },
                "required": ["isrc"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[Dict[str, str]]:
    """Execute tool calls."""
    global spotify_client

    try:
        if name == "search_track":
            results = spotify_client.search(
                q=arguments["query"], type="track", limit=arguments.get("limit", 10)
            )

            tracks = []
            for item in results["tracks"]["items"]:
                tracks.append(
                    {
                        "id": item["id"],
                        "name": item["name"],
                        "artist": item["artists"][0]["name"],
                        "album": item["album"]["name"],
                        "uri": item["uri"],
                        "duration_ms": item["duration_ms"],
                        "popularity": item["popularity"],
                        "release_date": item["album"]["release_date"],
                        "isrc": item.get("external_ids", {}).get("isrc"),
                    }
                )

            return [{"type": "text", "text": json.dumps({"tracks": tracks})}]

        elif name == "add_track_to_playlist":
            result = spotify_client.playlist_add_items(
                arguments["playlist_id"], [arguments["track_uri"]]
            )
            return [{"type": "text", "text": json.dumps(result)}]

        elif name == "verify_track_added":
            # Get playlist tracks (may need pagination for large playlists)
            playlist_tracks = spotify_client.playlist_items(
                arguments["playlist_id"], fields="items.track.uri,next", limit=100
            )

            # Check first batch
            track_uris = [item["track"]["uri"] for item in playlist_tracks["items"] if item["track"]]
            is_added = arguments["track_uri"] in track_uris

            # Handle pagination if not found in first batch
            while not is_added and playlist_tracks["next"]:
                playlist_tracks = spotify_client.next(playlist_tracks)
                track_uris = [item["track"]["uri"] for item in playlist_tracks["items"] if item["track"]]
                is_added = arguments["track_uri"] in track_uris

            return [{"type": "text", "text": json.dumps({"is_added": is_added})}]

        elif name == "get_user_playlists":
            playlists = spotify_client.current_user_playlists(limit=arguments.get("limit", 50))

            playlist_info = []
            for item in playlists["items"]:
                playlist_info.append(
                    {
                        "id": item["id"],
                        "name": item["name"],
                        "description": item.get("description", ""),
                        "tracks_total": item["tracks"]["total"],
                        "public": item["public"],
                    }
                )

            return [{"type": "text", "text": json.dumps({"playlists": playlist_info})}]

        elif name == "search_by_isrc":
            results = spotify_client.search(q=f"isrc:{arguments['isrc']}", type="track", limit=1)

            if results["tracks"]["items"]:
                item = results["tracks"]["items"][0]
                track = {
                    "id": item["id"],
                    "name": item["name"],
                    "artist": item["artists"][0]["name"],
                    "album": item["album"]["name"],
                    "uri": item["uri"],
                    "duration_ms": item["duration_ms"],
                    "popularity": item["popularity"],
                    "release_date": item["album"]["release_date"],
                    "isrc": item.get("external_ids", {}).get("isrc"),
                }
                return [{"type": "text", "text": json.dumps({"track": track, "found": True})}]
            else:
                return [{"type": "text", "text": json.dumps({"track": None, "found": False})}]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        error_response = {"error": str(e), "tool": name, "arguments": arguments}
        return [{"type": "text", "text": json.dumps(error_response)}]


async def main():
    """Run MCP server with Spotify client initialization."""
    global spotify_client

    # Initialize Spotify client with OAuth
    try:
        # Import custom cache handler
        from mcp_server.spotify_cache_handler import get_cache_handler

        # Determine cache handler based on environment
        # USE_FIRESTORE=true -> Firestore-backed (persistent across invocations)
        # USE_FIRESTORE=false -> Environment-based (from SPOTIFY_REFRESH_TOKEN)
        use_firestore = os.getenv("USE_FIRESTORE", "false").lower() == "true"
        cache_handler = get_cache_handler(use_firestore=use_firestore, user_id="default")

        spotify_client = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=os.getenv("SPOTIFY_CLIENT_ID"),
                client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
                redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
                scope="playlist-modify-public playlist-modify-private playlist-read-private",
                cache_handler=cache_handler,
            )
        )

        # Test connection
        spotify_client.current_user()
        print("✓ Spotify MCP server initialized successfully", file=sys.stderr, flush=True)

    except Exception as e:
        print(f"✗ Failed to initialize Spotify client: {e}", file=sys.stderr, flush=True)
        raise

    # Run MCP server
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
