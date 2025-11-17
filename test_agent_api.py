"""
Test script for Agent-powered Spotify API.

This demonstrates the full flow:
1. API receives song request
2. Agent (Claude) intelligently uses MCP tools
3. API returns structured results
"""
import asyncio
import httpx
import sys


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

    print("🎵 Testing Agent-Powered Spotify Sync API")
    print("=" * 60)
    print(f"Song: {request_data['track_name']}")
    print(f"Artist: {request_data['artist']}")
    print(f"Playlist: {request_data['playlist_id']}")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=120.0) as client:
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
        print("   (Claude is searching, analyzing, and adding the track)")

        max_attempts = 30
        attempt = 0

        while attempt < max_attempts:
            await asyncio.sleep(2)  # Poll every 2 seconds
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
                    print("\n✅ Step 3: Sync completed successfully!")
                    print("=" * 60)
                    result = status_data.get("result", {})
                    print(f"Success: {result.get('success')}")
                    print(f"Message: {result.get('message')}")
                    print(f"Track ID: {result.get('spotify_track_id')}")
                    print(f"Track URI: {result.get('spotify_track_uri')}")
                    print(f"Confidence: {result.get('confidence_score')}")
                    print(f"Match Method: {result.get('match_method')}")
                    print(f"Execution Time: {result.get('execution_time_seconds', 0):.2f}s")
                    print(f"Retry Count: {result.get('retry_count', 0)}")
                    print("=" * 60)
                    break

                elif current_status == "failed":
                    print("\n❌ Step 3: Sync failed!")
                    print(f"Error: {status_data.get('error')}")
                    break

            except Exception as e:
                print(f"   ⚠️  Error checking status: {e}")

        else:
            print("\n⏱️  Timeout waiting for completion")


async def test_health():
    """Test the health endpoint."""
    print("\n🏥 Testing health endpoint...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://localhost:8000/health")
            response.raise_for_status()
            health = response.json()
            print(f"   Status: {health.get('status')}")
            print(f"   Mode: {health.get('mode')}")
            print(f"   Message: {health.get('message')}")
        except Exception as e:
            print(f"   ❌ Health check failed: {e}")
            print("\n💡 Make sure the API server is running:")
            print("   python3 api/app_agent.py")
            sys.exit(1)


if __name__ == "__main__":
    print("\n🚀 Starting API test...")

    try:
        asyncio.run(test_health())
        asyncio.run(test_agent_sync())
        print("\n🎉 Test completed!")
    except KeyboardInterrupt:
        print("\n\n⏸️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
