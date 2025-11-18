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
    import asyncio
    import json
    import logging

    logger = logging.getLogger(__name__)

    try:
        # Create ASGI request
        asgi_request = {
            "type": "http",
            "method": req.method,
            "path": req.path,
            "headers": [
                (k.lower().encode(), v.encode()) for k, v in req.headers.items()
            ],
            "query_string": req.query_string or b"",
            "body": req.get_data() or b"",
        }

        # Async function to receive request body
        async def receive():
            return {
                "type": "http.request",
                "body": req.get_data() or b"",
                "more_body": False,
            }

        # Variables to collect response data
        response_body = []
        response_headers = []
        response_status = 200

        # Async function to send response
        async def send(message):
            nonlocal response_body, response_headers, response_status
            if message["type"] == "http.response.start":
                response_status = message.get("status", 200)
                response_headers = message.get("headers", [])
            elif message["type"] == "http.response.body":
                response_body.append(message.get("body", b""))

        # Run the ASGI app in an asyncio loop
        async def run_asgi():
            await fastapi_app(asgi_request, receive, send)

        asyncio.run(run_asgi())

        # Combine response body
        full_body = b"".join(response_body)

        # Convert headers to dict for `https_fn.Response`
        headers_dict = {
            k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v
            for k, v in response_headers
        }

        # Create Firebase Functions response
        return https_fn.Response(
            response=full_body,
            status=response_status,
            headers=headers_dict,
        )

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return https_fn.Response(
            response=json.dumps({"error": "Internal Server Error"}),
            status=500,
            headers={"Content-Type": "application/json"},
        )


@https_fn.on_request()
def health(req: https_fn.Request) -> https_fn.Response:
    """Simple health check endpoint."""
    return https_fn.Response(
        response='{"status": "healthy", "service": "spotify-sync-firebase"}',
        status=200,
        headers={"Content-Type": "application/json"}
    )
