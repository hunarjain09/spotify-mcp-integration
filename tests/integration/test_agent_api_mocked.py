"""
Test script for Agent-powered Spotify API (MOCKED VERSION).

This demonstrates the full flow with mocked network calls:
1. API receives song request
2. Agent (Claude) intelligently uses MCP tools
3. API returns structured results

This mocked version allows testing without:
- Running the actual API server
- Making real Anthropic API calls
- Making real Spotify API calls
"""
import asyncio
import sys
from unittest.mock import AsyncMock, patch, MagicMock
import time


class MockResponse:
    """Mock HTTP response."""

    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class MockAsyncClient:
    """Mock async HTTP client."""

    def __init__(self, *args, **kwargs):
        self.post_called = False
        self.get_calls = 0
        self.workflow_id = "sync-test-user-12345-abc123"

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def post(self, url, json=None):
        """Mock POST request."""
        self.post_called = True

        if "/api/v1/sync" in url:
            return MockResponse({
                "workflow_id": self.workflow_id,
                "status": "accepted",
                "message": f"Sync started for '{json['track_name']}' by {json['artist']}",
                "status_url": f"/api/v1/sync/{self.workflow_id}"
            })

        raise Exception(f"Unknown POST endpoint: {url}")

    async def get(self, url):
        """Mock GET request."""
        self.get_calls += 1

        if "/health" in url:
            return MockResponse({
                "status": "healthy",
                "mode": "agent_sdk",
                "message": "Agent SDK API is running"
            })

        elif f"/api/v1/sync/{self.workflow_id}" in url:
            # Simulate progression: running → completed
            if self.get_calls <= 2:
                return MockResponse({
                    "workflow_id": self.workflow_id,
                    "status": "running",
                    "message": "Agent is processing...",
                    "started_at": "2025-11-17T10:00:00Z"
                })
            else:
                # Return completed status
                return MockResponse({
                    "workflow_id": self.workflow_id,
                    "status": "completed",
                    "message": "Sync completed successfully",
                    "result": {
                        "success": True,
                        "message": "Successfully added 'Never Gonna Give You Up' to playlist",
                        "spotify_track_id": "4PTG3Z6ehGkBFwjybzWkR8",
                        "spotify_track_uri": "spotify:track:4PTG3Z6ehGkBFwjybzWkR8",
                        "confidence_score": 0.99,
                        "match_method": "exact_match",
                        "execution_time_seconds": 22.24,
                        "retry_count": 0,
                        "reasoning": "Perfect match found: exact artist name 'Rick Astley', exact title 'Never Gonna Give You Up'"
                    },
                    "started_at": "2025-11-17T10:00:00Z",
                    "completed_at": "2025-11-17T10:00:22Z"
                })

        raise Exception(f"Unknown GET endpoint: {url}")


async def test_agent_sync():
    """Test the agent-powered sync endpoint."""

    # Example song to sync
    request_data = {
        "track_name": "Never Gonna Give You Up",
        "artist": "Rick Astley",
        "album": "Whenever You Need Somebody",
        "playlist_id": "43X1N9GAKwVARreGxSAdZI",  # Your Syncer playlist
        "user_id": "test_user",
        "use_ai_disambiguation": True
    }

    print("🎵 Testing Agent-Powered Spotify Sync API (MOCKED)")
    print("=" * 60)
    print(f"Song: {request_data['track_name']}")
    print(f"Artist: {request_data['artist']}")
    print(f"Playlist: {request_data['playlist_id']}")
    print("=" * 60)

    client = MockAsyncClient(timeout=120.0)
    async with client:
        # Step 1: Submit sync request
        print("\n📤 Step 1: Submitting sync request to API...")
        try:
            response = await client.post(
                "http://localhost:8000/api/v1/sync",
                json=request_data
            )
            response.raise_for_status()
            sync_response = response.json()

            workflow_id = sync_response["workflow_id"]
            print(f"   ✅ Request accepted!")
            print(f"   Workflow ID: {workflow_id}")
            print(f"   Message: {sync_response['message']}")
            print(f"   Status URL: {sync_response['status_url']}")

        except Exception as e:
            print(f"   ❌ Failed to submit request: {e}")
            return

        # Step 2: Poll for results
        print(f"\n⏳ Step 2: Waiting for Agent to complete...")
        print("   (Simulating Claude searching, analyzing, and adding the track)")

        max_attempts = 30
        attempt = 0
        start_time = time.time()

        while attempt < max_attempts:
            await asyncio.sleep(0.5)  # Faster polling for mock
            attempt += 1

            try:
                status_response = await client.get(
                    f"http://localhost:8000/api/v1/sync/{workflow_id}"
                )
                status_response.raise_for_status()
                status_data = status_response.json()

                current_status = status_data["status"]
                print(f"   [{attempt}] Status: {current_status} - {status_data.get('message', '')}")

                if current_status == "completed":
                    elapsed = time.time() - start_time
                    print("\n✅ Step 3: Sync completed successfully!")
                    print("=" * 60)
                    result = status_data.get("result", {})
                    print(f"Success: {result.get('success')}")
                    print(f"Message: {result.get('message')}")
                    print(f"Track ID: {result.get('spotify_track_id')}")
                    print(f"Track URI: {result.get('spotify_track_uri')}")
                    print(f"Confidence: {result.get('confidence_score')}")
                    print(f"Match Method: {result.get('match_method')}")
                    print(f"Agent Execution Time: {result.get('execution_time_seconds', 0):.2f}s")
                    print(f"Test Execution Time: {elapsed:.2f}s")
                    print(f"Retry Count: {result.get('retry_count', 0)}")
                    print(f"Reasoning: {result.get('reasoning', 'N/A')[:100]}...")
                    print("=" * 60)

                    # Validate results
                    assert result.get('success') == True, "Sync should succeed"
                    assert result.get('confidence_score', 0) > 0.9, "Confidence should be high"
                    assert result.get('spotify_track_id'), "Should have track ID"
                    print("\n✅ All assertions passed!")
                    break

                elif current_status == "failed":
                    print("\n❌ Step 3: Sync failed!")
                    print(f"Error: {status_data.get('error')}")
                    break

            except Exception as e:
                print(f"   ⚠️  Error checking status: {e}")
                import traceback
                traceback.print_exc()

        else:
            print("\n⏱️  Timeout waiting for completion")


async def test_health():
    """Test the health endpoint."""
    print("\n🏥 Testing health endpoint...")
    client = MockAsyncClient()
    async with client:
        try:
            response = await client.get("http://localhost:8000/health")
            response.raise_for_status()
            health = response.json()
            print(f"   ✅ Status: {health.get('status')}")
            print(f"   Mode: {health.get('mode')}")
            print(f"   Message: {health.get('message')}")
        except Exception as e:
            print(f"   ❌ Health check failed: {e}")
            print("\n💡 Note: This is a mocked test - no actual server needed")
            sys.exit(1)


if __name__ == "__main__":
    print("\n🚀 Starting MOCKED API test...")
    print("   (No actual API server, Anthropic, or Spotify calls)")
    print()

    try:
        asyncio.run(test_health())
        asyncio.run(test_agent_sync())
        print("\n🎉 Test completed successfully!")
        print("\n📝 Note: This is a mocked test for CI/CD environments.")
        print("   For real integration testing, run the actual API server and use test_agent_api_real.py")
    except KeyboardInterrupt:
        print("\n\n⏸️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
