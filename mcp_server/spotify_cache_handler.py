"""
Custom Spotify cache handlers for different deployment environments.

Supports both local development (file-based) and production (environment-based).
"""
import json
import logging
import os
from typing import Optional

from spotipy.cache_handler import CacheHandler

logger = logging.getLogger(__name__)


class EnvironmentCacheHandler(CacheHandler):
    """
    Cache handler that uses environment variables for token storage.

    Perfect for Firebase Functions where:
    - Filesystem is ephemeral (doesn't persist between invocations)
    - Need to provide pre-authenticated tokens
    - Want zero storage costs

    Usage:
        1. Extract refresh_token from local .cache-spotify file
        2. Store in Secret Manager as SPOTIFY_REFRESH_TOKEN
        3. This handler will use it to initialize cache
        4. Access tokens are refreshed automatically as needed
    """

    def __init__(self):
        """Initialize cache from environment variables."""
        self.token_info = None

        # Try to load from environment variable
        refresh_token = os.getenv("SPOTIFY_REFRESH_TOKEN")
        if refresh_token:
            logger.info("Initializing Spotify cache from SPOTIFY_REFRESH_TOKEN environment variable")
            # Create minimal token_info with refresh token
            # SpotifyOAuth will use this to get a fresh access token
            self.token_info = {
                "refresh_token": refresh_token,
                "access_token": None,  # Will be refreshed on first use
                "expires_at": 0,  # Force immediate refresh
            }
        else:
            logger.warning(
                "SPOTIFY_REFRESH_TOKEN not found in environment. "
                "First request will require OAuth flow. "
                "For production, set SPOTIFY_REFRESH_TOKEN in Secret Manager."
            )

    def get_cached_token(self) -> Optional[dict]:
        """
        Get cached token info.

        Returns:
            Token info dict or None if not cached
        """
        return self.token_info

    def save_token_to_cache(self, token_info: dict) -> None:
        """
        Save token info to in-memory cache.

        Note: This is ephemeral - only lasts for the function's lifetime.
        The refresh_token from environment persists across invocations.

        Args:
            token_info: Token info dict from SpotifyOAuth
        """
        # Save to in-memory cache
        self.token_info = token_info
        logger.info("Updated Spotify token cache (in-memory)")

        # Log expiration for debugging (don't log the actual tokens!)
        if "expires_at" in token_info:
            import time
            expires_in = token_info["expires_at"] - time.time()
            logger.info(f"Access token expires in {expires_in:.0f} seconds")


class FirestoreCacheHandler(CacheHandler):
    """
    Cache handler that uses Firestore for token storage.

    Benefits:
    - Tokens persist across all function invocations
    - Shared across multiple function instances
    - No need for environment variables
    - Automatic token refresh

    Costs:
    - Small Firestore read/write costs (~$0.18/million operations)
    - Negligible for personal use (~few operations per hour)
    """

    def __init__(self, user_id: str = "default"):
        """
        Initialize Firestore cache handler.

        Args:
            user_id: User identifier for multi-user support
        """
        self.user_id = user_id
        self.collection_name = "spotify_tokens"
        self.doc_id = f"user_{user_id}"

        # Initialize Firestore client
        try:
            from firebase_admin import firestore, initialize_app
            import firebase_admin

            try:
                initialize_app()
            except ValueError:
                pass  # Already initialized

            self.db = firestore.client()
            logger.info(f"Firestore cache handler initialized for user: {user_id}")
        except Exception as e:
            logger.error(f"Failed to initialize Firestore: {e}")
            raise

    def get_cached_token(self) -> Optional[dict]:
        """
        Get cached token from Firestore.

        Returns:
            Token info dict or None if not cached
        """
        try:
            doc = self.db.collection(self.collection_name).document(self.doc_id).get()
            if doc.exists:
                token_info = doc.to_dict()
                logger.info(f"Retrieved token from Firestore for user: {self.user_id}")
                return token_info
            else:
                logger.info(f"No cached token found in Firestore for user: {self.user_id}")
                return None
        except Exception as e:
            logger.error(f"Failed to read token from Firestore: {e}")
            return None

    def save_token_to_cache(self, token_info: dict) -> None:
        """
        Save token info to Firestore.

        Args:
            token_info: Token info dict from SpotifyOAuth
        """
        try:
            self.db.collection(self.collection_name).document(self.doc_id).set(token_info)
            logger.info(f"Saved token to Firestore for user: {self.user_id}")

            # Log expiration for debugging
            if "expires_at" in token_info:
                import time
                expires_in = token_info["expires_at"] - time.time()
                logger.info(f"Access token expires in {expires_in:.0f} seconds")
        except Exception as e:
            logger.error(f"Failed to save token to Firestore: {e}")


def get_cache_handler(use_firestore: bool = False, user_id: str = "default") -> CacheHandler:
    """
    Factory function to get appropriate cache handler based on environment.

    Args:
        use_firestore: Whether to use Firestore for token storage
        user_id: User identifier for multi-user support

    Returns:
        Appropriate cache handler instance
    """
    if use_firestore:
        logger.info("Using Firestore cache handler for Spotify tokens")
        return FirestoreCacheHandler(user_id=user_id)
    else:
        logger.info("Using environment-based cache handler for Spotify tokens")
        return EnvironmentCacheHandler()
