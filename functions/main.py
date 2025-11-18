"""
Firebase Functions entry point for Spotify MCP Integration.

This module wraps the FastAPI app as a single Firebase Function.
"""
import sys
from pathlib import Path

# Add parent directory to path to import from api/
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from firebase_functions import https_fn, options
from firebase_admin import initialize_app, firestore
import google.cloud.firestore

# Initialize Firebase Admin
initialize_app()

# Import the FastAPI app
from api.app_agent import app as fastapi_app

# Create Firestore client
db = firestore.client()


@https_fn.on_request(
    cors=options.CorsOptions(
        cors_origins="*",
        cors_methods=["get", "post", "options"],
    ),
    timeout_sec=60,  # Maximum timeout for Firebase Functions
    memory=options.MemoryOption.GB_1,  # 1GB memory for Agent SDK
    cpu=1,
)
def spotify_sync(req: https_fn.Request) -> https_fn.Response:
    """
    Main Firebase Function for Spotify sync.

    Handles all API routes through FastAPI:
    - POST /api/v1/sync - Start sync
    - GET /api/v1/sync/{workflow_id} - Get status
    - GET /health - Health check
    """
    # Use Mangum to adapt FastAPI to Firebase Functions
    from mangum import Mangum

    handler = Mangum(fastapi_app, lifespan="off")

    # Convert Firebase Functions request to ASGI
    return handler(req)


@https_fn.on_request()
def health(req: https_fn.Request) -> https_fn.Response:
    """Simple health check endpoint."""
    return https_fn.Response(
        response='{"status": "healthy", "service": "spotify-sync-firebase"}',
        status=200,
        headers={"Content-Type": "application/json"}
    )
