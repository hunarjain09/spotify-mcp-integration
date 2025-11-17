"""
Quick performance test for Agent SDK integration.
Tests direct agent execution (no API server) to measure pure Agent SDK performance.
"""
import asyncio
import time
from agent_executor import execute_music_sync_with_agent
from models.data_models import SongMetadata


async def test_agent_performance():
    """Test agent execution speed."""

    print("🎵 Agent SDK Performance Test")
    print("=" * 60)

    # Test song
    song = SongMetadata(
        title="Never Gonna Give You Up",
        artist="Rick Astley",
        album="Whenever You Need Somebody"
    )

    playlist_id = "43X1N9GAKwVARreGxSAdZI"  # Your Syncer playlist

    print(f"Song: {song.title}")
    print(f"Artist: {song.artist}")
    print(f"Playlist: {playlist_id}")
    print("=" * 60)

    # Measure total time
    print("\n⏱️  Starting execution...")
    start_time = time.time()

    try:
        result = await execute_music_sync_with_agent(
            song_metadata=song,
            playlist_id=playlist_id,
            user_id="perf_test",
            use_ai_disambiguation=True
        )

        end_time = time.time()
        total_time = end_time - start_time

        print(f"\n✅ Execution completed in {total_time:.2f} seconds")
        print("=" * 60)

        if result.success:
            print("✅ SUCCESS")
            print(f"Matched Track: {result.matched_track_name}")
            print(f"Artist: {result.matched_artist}")
            print(f"URI: {result.matched_track_uri}")
            print(f"Confidence: {result.confidence_score}")
            print(f"Match Method: {result.match_method}")
            print(f"Agent Reasoning: {result.agent_reasoning}")
            print(f"Execution Time (reported): {result.execution_time_seconds:.2f}s")
        else:
            print("❌ FAILED")
            print(f"Error: {result.error}")
            print(f"Message: {result.message}")

        print("=" * 60)

        # Performance breakdown
        print("\n📊 Performance Analysis:")
        print(f"Total Wall Time: {total_time:.2f}s")
        print(f"Agent Execution: {result.execution_time_seconds:.2f}s")

        # Estimate breakdown
        overhead = total_time - (result.execution_time_seconds or 0)
        print(f"Overhead: {overhead:.2f}s")

        print("\n🔍 What takes time:")
        print("1. MCP Server startup: ~1-2s")
        print("2. Claude reasoning: ~2-5s")
        print("3. Spotify API calls: ~1-3s")
        print("4. Total typical: ~5-10s")

        return result

    except Exception as e:
        end_time = time.time()
        total_time = end_time - start_time

        print(f"\n❌ Exception after {total_time:.2f} seconds")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    print("\n🚀 Testing Agent SDK performance...\n")

    try:
        result = asyncio.run(test_agent_performance())

        if result and result.success:
            print("\n🎉 Performance test PASSED!")
        else:
            print("\n⚠️  Performance test completed with errors")

    except KeyboardInterrupt:
        print("\n\n⏸️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
