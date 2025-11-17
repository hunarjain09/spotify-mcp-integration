"""
Agent-based executor that replaces standalone_executor.py and Temporal workflows.

Uses Claude Agent SDK to intelligently orchestrate Spotify MCP tools.
Claude decides which tools to use, handles disambiguation, and returns structured results.
"""
import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import logging
from dataclasses import dataclass

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from models.data_models import SongMetadata, WorkflowResult

logger = logging.getLogger(__name__)


@dataclass
class AgentExecutionResult:
    """Result from agent execution."""
    success: bool
    message: str
    matched_track_uri: Optional[str] = None
    matched_track_name: Optional[str] = None
    matched_artist: Optional[str] = None
    confidence_score: Optional[float] = None
    match_method: Optional[str] = None
    execution_time_seconds: Optional[float] = None
    agent_reasoning: Optional[str] = None
    error: Optional[str] = None


async def execute_music_sync_with_agent(
    song_metadata: SongMetadata,
    playlist_id: str,
    user_id: str = "anonymous",
    use_ai_disambiguation: bool = True
) -> AgentExecutionResult:
    """
    Execute music sync using Claude Agent SDK.

    Claude intelligently uses Spotify MCP tools to:
    1. Search for the track
    2. Analyze and pick the best match (with AI reasoning)
    3. Add to playlist
    4. Verify addition

    Args:
        song_metadata: Song to search for
        playlist_id: Target Spotify playlist ID
        user_id: User identifier
        use_ai_disambiguation: Whether to use AI for ambiguous matches

    Returns:
        AgentExecutionResult with success status and details
    """
    import time
    start_time = time.time()

    logger.info(f"Starting agent-based sync for: {song_metadata}")

    # Configure Claude Agent SDK
    options = ClaudeAgentOptions(
        # Connect to Spotify MCP server
        mcp_servers={
            "spotify": {
                "type": "stdio",
                "command": sys.executable,
                "args": [str(Path(__file__).parent / "mcp_server" / "spotify_server.py")],
            }
        },
        # Allow all Spotify tools
        allowed_tools=[
            "mcp__spotify__search_track",
            "mcp__spotify__add_track_to_playlist",
            "mcp__spotify__verify_track_added",
            "mcp__spotify__get_user_playlists",
            "mcp__spotify__search_by_isrc",
        ],
        # Auto-approve for automation
        permission_mode="bypassPermissions",
        # Use Claude Code system prompt
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
            "append": """
You are a music matching expert. When asked to sync a song to Spotify:

1. Search for the track using the exact artist and title provided
2. Analyze ALL search results carefully
3. Pick the BEST match considering:
   - Exact artist name match (case-insensitive)
   - Exact title match (case-insensitive)
   - Release date (prefer original over remasters unless specified)
   - Popularity score (higher is usually better)
   - Avoid live versions, remixes, or covers unless explicitly requested

4. Add the matched track to the specified playlist
5. Verify the track was added successfully

IMPORTANT: Return your response in this EXACT JSON format:
{
    "success": true/false,
    "matched_track_uri": "spotify:track:xxxxx",
    "matched_track_name": "Song Title",
    "matched_artist": "Artist Name",
    "confidence_score": 0.95,
    "match_method": "exact_match" or "fuzzy_match" or "ai_disambiguation",
    "reasoning": "Brief explanation of why this match was chosen",
    "error": null or "error description"
}
"""
        },
        max_turns=10,  # Limit conversation length
    )

    # Create the prompt for Claude
    disambiguation_note = "Use your best judgment to pick the most accurate match." if use_ai_disambiguation else "Only pick exact matches."

    prompt = f"""Please sync the following song to my Spotify playlist:

Song: "{song_metadata.title}"
Artist: "{song_metadata.artist}"
Album: "{song_metadata.album or 'Unknown'}"
Playlist ID: {playlist_id}
User ID: {user_id}

Instructions:
1. Search for this exact track on Spotify
2. {disambiguation_note}
3. Add the best match to playlist {playlist_id}
4. Verify it was added successfully
5. Return the result in the JSON format specified in your system prompt

Begin the search now."""

    try:
        async with ClaudeSDKClient(options=options) as client:
            # Send the sync request to Claude
            await client.query(prompt)

            # Collect Claude's response
            full_response = []
            async for message in client.receive_response():
                if hasattr(message, 'content'):
                    for block in message.content:
                        if hasattr(block, 'text'):
                            full_response.append(block.text)

                # Check if done
                if hasattr(message, 'subtype') and message.subtype in ['success', 'error']:
                    if message.subtype == 'error':
                        error_msg = getattr(message, 'result', 'Unknown error')
                        logger.error(f"Agent execution failed: {error_msg}")
                        return AgentExecutionResult(
                            success=False,
                            message=f"Agent error: {error_msg}",
                            error=error_msg,
                            execution_time_seconds=time.time() - start_time
                        )
                    break

            # Parse Claude's response to extract structured data
            response_text = "\n".join(full_response)
            logger.info(f"Agent response: {response_text[:500]}...")

            # Try to extract JSON from response
            result_data = _parse_agent_response(response_text)

            execution_time = time.time() - start_time

            if result_data.get("success"):
                return AgentExecutionResult(
                    success=True,
                    message=f"Successfully synced '{result_data.get('matched_track_name')}' by {result_data.get('matched_artist')}",
                    matched_track_uri=result_data.get("matched_track_uri"),
                    matched_track_name=result_data.get("matched_track_name"),
                    matched_artist=result_data.get("matched_artist"),
                    confidence_score=result_data.get("confidence_score"),
                    match_method=result_data.get("match_method", "agent_based"),
                    agent_reasoning=result_data.get("reasoning"),
                    execution_time_seconds=execution_time
                )
            else:
                return AgentExecutionResult(
                    success=False,
                    message=result_data.get("error", "Failed to sync track"),
                    error=result_data.get("error"),
                    execution_time_seconds=execution_time
                )

    except Exception as e:
        logger.error(f"Agent execution exception: {e}", exc_info=True)
        return AgentExecutionResult(
            success=False,
            message=f"Agent execution failed: {str(e)}",
            error=str(e),
            execution_time_seconds=time.time() - start_time
        )


def _parse_agent_response(response_text: str) -> Dict[str, Any]:
    """
    Parse Claude's response to extract structured data.

    Looks for JSON in the response or extracts key information.
    """
    import json
    import re

    # Try to find JSON block
    json_match = re.search(r'\{[\s\S]*\}', response_text)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    # Fallback: Extract key information from text
    result = {
        "success": False,
        "error": "Could not parse agent response"
    }

    # Check for success indicators
    if "successfully added" in response_text.lower() or "synced" in response_text.lower():
        result["success"] = True
        result["error"] = None

        # Try to extract URI
        uri_match = re.search(r'spotify:track:([a-zA-Z0-9]+)', response_text)
        if uri_match:
            result["matched_track_uri"] = uri_match.group(0)

        # Extract track name
        name_match = re.search(r'"([^"]+)" by ([^"]+)', response_text)
        if name_match:
            result["matched_track_name"] = name_match.group(1)
            result["matched_artist"] = name_match.group(2)

    return result


async def get_agent_workflow_progress(workflow_id: str) -> Dict[str, Any]:
    """
    Get workflow progress (stub for compatibility with API).

    Agent executions are synchronous, so this returns cached results.
    """
    # TODO: Implement caching of agent results if needed
    return {
        "workflow_id": workflow_id,
        "status": "completed",
        "message": "Agent execution completed"
    }
