"""Spotify search activity for Temporal workflows."""

from datetime import timedelta
from typing import List

from temporalio import activity
import httpx

from models.data_models import SongMetadata, SpotifyTrackResult
from mcp_client.client import get_spotify_mcp_client


@activity.defn(name="spotify-search")
async def search_spotify(metadata: SongMetadata) -> List[SpotifyTrackResult]:
    """Search Spotify catalog via MCP.

    Args:
        metadata: Song metadata from Apple Music

    Returns:
        List of Spotify track results

    Raises:
        activity.ApplicationError: On rate limiting or other errors
    """
    activity.logger.info(f"Searching Spotify for: {metadata}")

    try:
        # Get MCP client
        mcp_client = await get_spotify_mcp_client()

        # Build search query
        search_query = metadata.to_search_query()
        activity.logger.info(f"Search query: {search_query}")

        # Use MCP tool for search
        results = await mcp_client.search_track(search_query, limit=10)

        # Parse MCP response
        tracks = []
        for item in results.get("tracks", []):
            tracks.append(
                SpotifyTrackResult(
                    track_id=item["id"],
                    track_name=item["name"],
                    artist_name=item["artist"],
                    album_name=item["album"],
                    spotify_uri=item["uri"],
                    duration_ms=item["duration_ms"],
                    popularity=item["popularity"],
                    release_date=item["release_date"],
                    isrc=item.get("isrc"),
                )
            )

        activity.logger.info(f"Found {len(tracks)} candidates")

        # Send heartbeat to prevent timeout
        activity.heartbeat(f"Found {len(tracks)} candidates")

        return tracks

    except httpx.HTTPStatusError as e:
        # Handle rate limiting
        if e.response.status_code == 429:
            retry_after = int(e.response.headers.get("Retry-After", 60))
            activity.logger.warning(f"Rate limited, retry after {retry_after}s")

            raise activity.ApplicationError(
                f"Spotify rate limit exceeded, retry after {retry_after}s",
                non_retryable=False,
                next_retry_delay=timedelta(seconds=retry_after + 5),
            )

        # Other HTTP errors
        activity.logger.error(f"HTTP error during search: {e}")
        raise activity.ApplicationError(
            f"Spotify API error: {e.response.status_code}",
            non_retryable=False,
        )

    except ValueError as e:
        # MCP tool returned an error
        activity.logger.error(f"MCP error: {e}")
        raise activity.ApplicationError(
            f"MCP tool error: {str(e)}",
            non_retryable=True,
            type="MCPToolError",
        )

    except Exception as e:
        # Unexpected errors
        activity.logger.error(f"Unexpected error during search: {e}")
        raise activity.ApplicationError(
            f"Search failed: {str(e)}",
            non_retryable=False,
        )
