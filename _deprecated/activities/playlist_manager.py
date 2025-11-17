"""Playlist management activities for adding and verifying tracks."""

from typing import Dict

from temporalio import activity

from mcp_client.client import get_spotify_mcp_client


@activity.defn(name="add-to-playlist")
async def add_track_to_playlist(track_uri: str, playlist_id: str, user_id: str) -> Dict:
    """Add track to Spotify playlist (idempotent).

    Args:
        track_uri: Spotify track URI (spotify:track:xxxxx)
        playlist_id: Spotify playlist ID
        user_id: User identifier for logging

    Returns:
        Dictionary with operation status and details
    """
    activity.logger.info(f"Adding track {track_uri} to playlist {playlist_id} for user {user_id}")

    try:
        # Get MCP client
        mcp_client = await get_spotify_mcp_client()

        # First check if track already exists (idempotency)
        exists = await mcp_client.verify_track_added(track_uri, playlist_id)

        if exists:
            activity.logger.info("Track already in playlist, skipping (idempotent)")
            return {"status": "already_exists", "track_uri": track_uri}

        # Add track to playlist
        result = await mcp_client.add_track_to_playlist(track_uri, playlist_id)

        activity.logger.info(f"Successfully added track: {result.get('snapshot_id', 'N/A')}")

        return {"status": "added", "track_uri": track_uri, "snapshot_id": result.get("snapshot_id")}

    except ValueError as e:
        # MCP tool returned an error
        error_msg = str(e).lower()

        # Classify errors for retry behavior
        if "not found" in error_msg:
            activity.logger.error(f"Playlist not found: {playlist_id}")
            raise activity.ApplicationError(
                "Playlist not found", non_retryable=True, type="PlaylistNotFoundError"
            )

        elif "insufficient" in error_msg or "scope" in error_msg:
            activity.logger.error("Insufficient OAuth scopes")
            raise activity.ApplicationError(
                "Insufficient OAuth scopes for playlist modification",
                non_retryable=True,
                type="InsufficientScopeError",
            )

        else:
            # Other MCP errors are retryable
            activity.logger.error(f"MCP error: {e}")
            raise activity.ApplicationError(f"MCP error: {str(e)}", non_retryable=False)

    except Exception as e:
        # Unexpected errors are retryable
        activity.logger.error(f"Failed to add track: {e}")
        raise activity.ApplicationError(f"Failed to add track: {str(e)}", non_retryable=False)


@activity.defn(name="verify-track-added")
async def verify_track_added(track_uri: str, playlist_id: str) -> Dict:
    """Verify that a track was successfully added to a playlist.

    Args:
        track_uri: Spotify track URI
        playlist_id: Spotify playlist ID

    Returns:
        Dictionary with verification result
    """
    activity.logger.info(f"Verifying track {track_uri} in playlist {playlist_id}")

    try:
        # Get MCP client
        mcp_client = await get_spotify_mcp_client()

        # Check if track exists in playlist
        is_added = await mcp_client.verify_track_added(track_uri, playlist_id)

        if is_added:
            activity.logger.info("✓ Track verified in playlist")
        else:
            activity.logger.warning("✗ Track not found in playlist")

        return {"is_added": is_added, "track_uri": track_uri, "playlist_id": playlist_id}

    except Exception as e:
        activity.logger.error(f"Verification failed: {e}")
        # Verification failures are not critical - return False
        return {"is_added": False, "track_uri": track_uri, "playlist_id": playlist_id, "error": str(e)}
