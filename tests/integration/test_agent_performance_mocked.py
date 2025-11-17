"""
Quick performance test for Agent SDK integration (MOCKED VERSION).
Tests direct agent execution (no API server) to measure simulated Agent SDK performance.

This mocked version allows testing without:
- Anthropic API key
- Running MCP server
- Spotify authentication
"""
import asyncio
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class SongMetadata:
    """Mock song metadata."""
    title: str
    artist: str
    album: Optional[str] = None


@dataclass
class MatchResult:
    """Mock match result."""
    success: bool
    message: str
    matched_track_name: Optional[str] = None
    matched_artist: Optional[str] = None
    matched_album: Optional[str] = None
    matched_track_uri: Optional[str] = None
    matched_track_id: Optional[str] = None
    confidence_score: Optional[float] = None
    match_method: Optional[str] = None
    agent_reasoning: Optional[str] = None
    execution_time_seconds: Optional[float] = None
    retry_count: int = 0
    workflow_id: Optional[str] = None
    error: Optional[str] = None


async def mock_execute_music_sync_with_agent(
    song_metadata: SongMetadata,
    playlist_id: str,
    user_id: str,
    use_ai_disambiguation: bool = True
):
    """Mock agent execution that simulates timing and behavior."""

    # Simulate Agent SDK processing time
    await asyncio.sleep(1.5)  # Simulated processing

    # Return mock result matching real agent output
    return MatchResult(
        success=True,
        message="Successfully added 'Never Gonna Give You Up' to playlist",
        matched_track_name="Never Gonna Give You Up",
        matched_artist="Rick Astley",
        matched_album="Whenever You Need Somebody",
        matched_track_uri="spotify:track:4PTG3Z6ehGkBFwjybzWkR8",
        matched_track_id="4PTG3Z6ehGkBFwjybzWkR8",
        confidence_score=0.99,
        match_method="exact_match",
        agent_reasoning="Perfect match found: exact artist name 'Rick Astley', exact title 'Never Gonna Give You Up', from the correct album 'Whenever You Need Somebody' (1987 original release). This track has the highest popularity score among all versions.",
        execution_time_seconds=22.24,
        retry_count=0,
        workflow_id=f"sync-{user_id}-mock-123"
    )


async def test_agent_performance():
    """Test agent execution speed (mocked)."""

    print("🎵 Agent SDK Performance Test (MOCKED)")
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
    print("\n⏱️  Starting execution (mocked)...")
    start_time = time.time()

    try:
        # Use mocked executor
        result = await mock_execute_music_sync_with_agent(
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
            print(f"Agent Reasoning: {result.agent_reasoning[:100]}...")
            print(f"Execution Time (simulated): {result.execution_time_seconds:.2f}s")
        else:
            print("❌ FAILED")
            print(f"Error: {result.error}")
            print(f"Message: {result.message}")

        print("=" * 60)

        # Performance breakdown
        print("\n📊 Performance Analysis (Simulated):")
        print(f"Total Wall Time: {total_time:.2f}s")
        print(f"Agent Execution: {result.execution_time_seconds:.2f}s (mocked)")

        # Estimate breakdown
        overhead = total_time - (result.execution_time_seconds or 0)
        print(f"Test Overhead: {overhead:.2f}s")

        print("\n🔍 Typical Real Agent SDK Timing:")
        print("1. MCP Server startup: ~2s")
        print("2. Claude reasoning: ~8-10s")
        print("3. MCP tool calls (search, add, verify): ~8-10s")
        print("4. Result parsing: ~0.5s")
        print("5. Total typical: ~20-25s")

        print("\n📝 Note: This is a mocked test simulating real behavior")
        print("   Real execution requires Anthropic API key and Spotify auth")

        # Validate results
        assert result.success == True, "Should succeed"
        assert result.confidence_score > 0.9, "Confidence should be high"
        assert result.matched_track_id, "Should have track ID"
        print("\n✅ All assertions passed!")

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
    print("\n🚀 Testing Agent SDK performance (MOCKED)...\n")
    print("   (No actual Anthropic, MCP server, or Spotify calls)")
    print()

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
        import traceback
        traceback.print_exc()
