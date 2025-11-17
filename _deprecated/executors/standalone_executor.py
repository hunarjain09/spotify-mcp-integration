"""
⚠️ DEPRECATED - DO NOT USE ⚠️

This file has been DEPRECATED as of November 17, 2025.

USE INSTEAD: agent_executor.py (Agent SDK implementation)

REASON FOR DEPRECATION:
- Standalone executor still requires manual orchestration
- Agent SDK provides better AI integration and automatic orchestration
- Simpler code with fewer lines
- See MIGRATION_GUIDE.md for migration instructions
- See _deprecated/README.md for more details

---

Standalone workflow executor for non-Temporal deployments.

REASONING FOR THIS MODULE:
--------------------------
This executor provides an alternative to Temporal-based workflow orchestration
for simpler deployment scenarios. While Temporal offers excellent features like
durable execution, automatic retries, and distributed processing, it requires:

1. Running a Temporal server (docker-compose or cloud)
2. PostgreSQL for state persistence
3. Additional infrastructure complexity
4. More operational overhead

USE CASES FOR STANDALONE MODE:
- Development and testing environments
- Single-server deployments with low traffic
- Scenarios where fire-and-forget execution is acceptable
- Budget-constrained deployments
- Prototyping and demos

TRADE-OFFS:
-----------
TEMPORAL MODE (use_temporal=true):
✓ Durable execution (survives server restarts)
✓ Automatic retry with exponential backoff
✓ Distributed execution across multiple workers
✓ Real-time progress tracking via queries
✓ Workflow history and replay capabilities
✗ Requires additional infrastructure
✗ More complex deployment

STANDALONE MODE (use_temporal=false):
✓ Simple deployment (just FastAPI + Spotify)
✓ No additional infrastructure needed
✓ Lower resource usage
✓ Faster startup time
✗ No durability (in-progress workflows lost on restart)
✗ Basic retry logic only
✗ Single-server execution only
✗ Limited progress tracking

IMPLEMENTATION NOTES:
- Uses the same activity functions as Temporal mode
- Implements basic retry logic with exponential backoff
- Stores execution state in-memory (workflow status tracking)
- Claude SDK integration works identically in both modes
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

from models.data_models import (
    SongMetadata,
    SpotifyTrackResult,
    WorkflowInput,
    WorkflowResult,
    WorkflowProgress,
)
from mcp_client.client import get_spotify_mcp_client
from rapidfuzz import fuzz
from config.settings import settings

# Import AI disambiguation logic
from anthropic import AsyncAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)


# In-memory storage for workflow status
# In production, this could be Redis or a database
# For now, we keep it simple with a dict
workflow_status_store: Dict[str, Dict] = {}


@dataclass
class StandaloneWorkflowState:
    """State tracking for standalone workflow execution."""

    workflow_id: str
    current_step: str
    candidates_found: int
    start_time: float
    status: str  # running, completed, failed
    result: Optional[WorkflowResult] = None
    error: Optional[str] = None


async def execute_with_retry(
    func, *args, max_attempts: int = 3, initial_delay: float = 1.0, backoff: float = 2.0, **kwargs
):
    """
    Execute an async function with exponential backoff retry logic.

    This mimics Temporal's retry policy but in a simpler, standalone way.

    Args:
        func: Async function to execute
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay in seconds before first retry
        backoff: Backoff multiplier for exponential backoff
        *args, **kwargs: Arguments to pass to the function

    Returns:
        Function result

    Raises:
        Last exception if all retries fail
    """
    last_exception = None
    delay = initial_delay

    for attempt in range(1, max_attempts + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            logger.warning(
                f"Attempt {attempt}/{max_attempts} failed: {str(e)[:100]}",
                exc_info=attempt == max_attempts,  # Full traceback on last attempt
            )

            if attempt < max_attempts:
                logger.info(f"Retrying in {delay:.1f}s...")
                await asyncio.sleep(delay)
                delay *= backoff
            else:
                logger.error(f"All {max_attempts} attempts failed")

    raise last_exception


async def search_spotify_standalone(metadata: SongMetadata) -> List[SpotifyTrackResult]:
    """
    Search Spotify catalog (standalone version without Temporal).

    This function replicates the logic from activities/spotify_search.py
    but without Temporal activity decorators.
    """
    logger.info(f"Searching Spotify for: {metadata}")

    mcp_client = await get_spotify_mcp_client()
    search_query = metadata.to_search_query()
    logger.info(f"Search query: {search_query}")

    results = await mcp_client.search_track(search_query, limit=10)

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

    logger.info(f"Found {len(tracks)} candidates")
    return tracks


async def fuzzy_match_standalone(
    original_metadata: SongMetadata, search_results: List[SpotifyTrackResult], threshold: float
) -> Dict:
    """
    Fuzzy string matching (standalone version without Temporal).

    This function replicates the logic from activities/fuzzy_matcher.py
    but without Temporal activity decorators.
    """
    logger.info(f"Fuzzy matching {len(search_results)} candidates")

    if not search_results:
        return {
            "is_match": False,
            "confidence": 0.0,
            "matched_track": None,
            "match_method": "none",
            "all_scores": [],
        }

    best_match = None
    best_score = 0.0
    all_scores = []

    for result in search_results:
        # Calculate component scores (same logic as Temporal version)
        title_score = fuzz.ratio(original_metadata.title.lower(), result.track_name.lower()) / 100.0
        artist_score = (
            fuzz.ratio(original_metadata.artist.lower(), result.artist_name.lower()) / 100.0
        )

        album_score = 0.0
        if original_metadata.album and result.album_name:
            album_score = (
                fuzz.ratio(original_metadata.album.lower(), result.album_name.lower()) / 100.0
            )

        # Check for ISRC exact match
        isrc_match = False
        if original_metadata.isrc and result.isrc and original_metadata.isrc == result.isrc:
            isrc_match = True
            combined_score = 1.0
        else:
            # Weighted combination: title 50%, artist 35%, album 15%
            combined_score = title_score * 0.5 + artist_score * 0.35 + album_score * 0.15

        all_scores.append(
            {
                "track": result,
                "score": combined_score,
                "title_score": title_score,
                "artist_score": artist_score,
                "album_score": album_score,
                "isrc_match": isrc_match,
            }
        )

        if combined_score > best_score:
            best_score = combined_score
            best_match = result

    # Sort by score descending
    all_scores.sort(key=lambda x: x["score"], reverse=True)

    is_match = best_score >= threshold

    # Determine match method
    match_method = "none"
    if is_match:
        match_method = "isrc" if all_scores[0]["isrc_match"] else "fuzzy"

    logger.info(f"Best match score: {best_score:.2f}, threshold: {threshold}, method: {match_method}")

    return {
        "is_match": is_match,
        "confidence": best_score,
        "matched_track": best_match if is_match else None,
        "match_method": match_method,
        "all_scores": all_scores,
    }


async def ai_disambiguate_standalone(
    original_metadata: SongMetadata, candidates: List[SpotifyTrackResult], fuzzy_scores: List[Dict]
) -> Dict:
    """
    AI-powered disambiguation (standalone version).

    This function replicates the logic from activities/ai_disambiguator.py
    but without Temporal activity decorators. Supports both Claude and Langchain.
    """
    logger.info(f"AI disambiguating {len(candidates)} candidates using {settings.ai_provider}")

    if not candidates:
        return {
            "is_match": False,
            "confidence": 0.0,
            "matched_track": None,
            "match_method": "ai_failed",
            "reasoning": "No candidates provided",
        }

    # Format candidates for AI
    candidates_text = ""
    for idx, candidate in enumerate(candidates, 1):
        fuzzy_info = next(
            (s for s in fuzzy_scores if s.get("track") == candidate), {"score": 0}
        )
        candidates_text += f"""
{idx}. "{candidate.track_name}" by {candidate.artist_name}
   Album: {candidate.album_name}
   Release Date: {candidate.release_date}
   Fuzzy Match Score: {fuzzy_info.get('score', 0):.2f}
   Popularity: {candidate.popularity}
   URI: {candidate.spotify_uri}
"""

    if settings.ai_provider == "claude":
        return await _ai_disambiguate_claude(original_metadata, candidates, candidates_text)
    elif settings.ai_provider == "langchain":
        return await _ai_disambiguate_langchain(original_metadata, candidates, candidates_text)
    else:
        raise ValueError(f"Unknown AI provider: {settings.ai_provider}")


async def _ai_disambiguate_claude(
    original_metadata: SongMetadata, candidates: List[SpotifyTrackResult], candidates_text: str
) -> Dict:
    """Claude SDK disambiguation logic."""
    system_prompt = """You are an expert music librarian helping match songs from Apple Music to Spotify.
Given an original song and multiple Spotify candidates, select the best match.

Consider these factors:
- Artist name variations (e.g., "The Beatles" vs "Beatles")
- Album names and release dates
- Remaster vs original versions
- Live vs studio recordings
- Featured artists
- Single vs album versions

Respond with ONLY the URI of the best match and a brief reason (one sentence).
If none of the candidates is a good match, respond with "NONE" as the URI.

Format your response EXACTLY like this:
URI: spotify:track:xxxxx (or NONE)
REASON: Brief explanation in one sentence"""

    user_prompt = f"""Original Song:
Title: {original_metadata.title}
Artist: {original_metadata.artist}
Album: {original_metadata.album or "Unknown"}

Spotify Candidates:
{candidates_text}

Which is the best match?"""

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    logger.info(f"Invoking Claude with model: {settings.claude_model}")

    response = await client.messages.create(
        model=settings.claude_model,
        max_tokens=1024,
        temperature=0,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    content = response.content[0].text
    logger.debug(f"Claude response: {content}")

    # Parse response
    lines = content.strip().split("\n")
    uri_line = next((l for l in lines if l.startswith("URI:")), None)
    reason_line = next((l for l in lines if l.startswith("REASON:")), None)

    if not uri_line or not reason_line:
        raise ValueError("Claude response missing URI or REASON")

    selected_uri = uri_line.replace("URI:", "").strip()
    reasoning = reason_line.replace("REASON:", "").strip()

    if selected_uri.upper() == "NONE":
        return {
            "is_match": False,
            "confidence": 0.0,
            "matched_track": None,
            "match_method": "ai_claude",
            "reasoning": reasoning,
        }

    matched_track = next((c for c in candidates if c.spotify_uri == selected_uri), None)

    if matched_track:
        logger.info(f"Claude selected: {matched_track.track_name} - {reasoning}")
        return {
            "is_match": True,
            "confidence": 0.90,
            "matched_track": matched_track,
            "match_method": "ai_claude",
            "reasoning": reasoning,
        }
    else:
        return {
            "is_match": False,
            "confidence": 0.0,
            "matched_track": None,
            "match_method": "ai_failed",
            "reasoning": f"Claude returned invalid URI: {selected_uri}",
        }


async def _ai_disambiguate_langchain(
    original_metadata: SongMetadata, candidates: List[SpotifyTrackResult], candidates_text: str
) -> Dict:
    """Langchain (OpenAI) disambiguation logic."""
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are an expert music librarian helping match songs from Apple Music to Spotify.
Given an original song and multiple Spotify candidates, select the best match.

Consider these factors:
- Artist name variations (e.g., "The Beatles" vs "Beatles")
- Album names and release dates
- Remaster vs original versions
- Live vs studio recordings
- Featured artists
- Single vs album versions

Respond with ONLY the URI of the best match and a brief reason (one sentence).
If none of the candidates is a good match, respond with "NONE" as the URI.

Format your response EXACTLY like this:
URI: spotify:track:xxxxx (or NONE)
REASON: Brief explanation in one sentence""",
            ),
            (
                "user",
                """Original Song:
Title: {title}
Artist: {artist}
Album: {album}

Spotify Candidates:
{candidates}

Which is the best match?""",
            ),
        ]
    )

    llm = ChatOpenAI(model=settings.ai_model, temperature=0, api_key=settings.openai_api_key)
    chain = prompt | llm

    logger.info(f"Invoking AI with model: {settings.ai_model}")

    response = await chain.ainvoke(
        {
            "title": original_metadata.title,
            "artist": original_metadata.artist,
            "album": original_metadata.album or "Unknown",
            "candidates": candidates_text,
        }
    )

    content = response.content
    logger.debug(f"AI response: {content}")

    # Parse response (same logic as Claude)
    lines = content.strip().split("\n")
    uri_line = next((l for l in lines if l.startswith("URI:")), None)
    reason_line = next((l for l in lines if l.startswith("REASON:")), None)

    if not uri_line or not reason_line:
        raise ValueError("AI response missing URI or REASON")

    selected_uri = uri_line.replace("URI:", "").strip()
    reasoning = reason_line.replace("REASON:", "").strip()

    if selected_uri.upper() == "NONE":
        return {
            "is_match": False,
            "confidence": 0.0,
            "matched_track": None,
            "match_method": "ai",
            "reasoning": reasoning,
        }

    matched_track = next((c for c in candidates if c.spotify_uri == selected_uri), None)

    if matched_track:
        logger.info(f"AI selected: {matched_track.track_name} - {reasoning}")
        return {
            "is_match": True,
            "confidence": 0.90,
            "matched_track": matched_track,
            "match_method": "ai",
            "reasoning": reasoning,
        }
    else:
        return {
            "is_match": False,
            "confidence": 0.0,
            "matched_track": None,
            "match_method": "ai_failed",
            "reasoning": f"AI returned invalid URI: {selected_uri}",
        }


async def add_to_playlist_standalone(track_uri: str, playlist_id: str, user_id: str) -> Dict:
    """Add track to playlist (standalone version)."""
    logger.info(f"Adding track {track_uri} to playlist {playlist_id}")

    mcp_client = await get_spotify_mcp_client()

    # Check if already exists (idempotent)
    exists = await mcp_client.verify_track_added(track_uri, playlist_id)
    if exists:
        logger.info("Track already in playlist, skipping")
        return {"status": "already_exists", "track_uri": track_uri}

    # Add track
    result = await mcp_client.add_track_to_playlist(track_uri, playlist_id)
    logger.info(f"Successfully added track")

    return {"status": "added", "track_uri": track_uri, "snapshot_id": result.get("snapshot_id")}


async def verify_track_standalone(track_uri: str, playlist_id: str) -> Dict:
    """Verify track was added (standalone version)."""
    logger.info(f"Verifying track {track_uri} in playlist {playlist_id}")

    try:
        mcp_client = await get_spotify_mcp_client()
        is_added = await mcp_client.verify_track_added(track_uri, playlist_id)

        return {"is_added": is_added, "track_uri": track_uri, "playlist_id": playlist_id}
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        return {"is_added": False, "track_uri": track_uri, "playlist_id": playlist_id, "error": str(e)}


async def run_standalone_workflow(workflow_id: str, input_data: WorkflowInput) -> WorkflowResult:
    """
    Execute the music sync workflow without Temporal.

    This function replicates the workflow logic from workflows/music_sync_workflow.py
    but executes directly without Temporal orchestration.

    Args:
        workflow_id: Unique identifier for this workflow execution
        input_data: Workflow input parameters

    Returns:
        WorkflowResult with execution details
    """
    start_time = time.time()

    # Initialize workflow state
    state = StandaloneWorkflowState(
        workflow_id=workflow_id,
        current_step="initializing",
        candidates_found=0,
        start_time=start_time,
        status="running",
    )
    workflow_status_store[workflow_id] = state

    try:
        logger.info(
            f"[{workflow_id}] Starting sync: {input_data.song_metadata.title} "
            f"by {input_data.song_metadata.artist}"
        )

        # Step 1: Search Spotify (with retry)
        state.current_step = "searching"
        search_results = await execute_with_retry(
            search_spotify_standalone,
            input_data.song_metadata,
            max_attempts=3,
            initial_delay=1.0,
        )

        state.candidates_found = len(search_results)

        if not search_results:
            logger.info(f"[{workflow_id}] No tracks found on Spotify")
            result = WorkflowResult(
                success=False,
                message=f"No tracks found on Spotify for '{input_data.song_metadata.title}'",
                execution_time_seconds=time.time() - start_time,
            )
            state.status = "completed"
            state.result = result
            return result

        # Step 2: Fuzzy Matching
        state.current_step = "matching"
        match_result = await fuzzy_match_standalone(
            input_data.song_metadata, search_results, input_data.match_threshold
        )

        # Step 2.5: AI Disambiguation (if needed)
        if not match_result["is_match"] and input_data.use_ai_disambiguation:
            state.current_step = "ai_disambiguation"
            logger.info(
                f"[{workflow_id}] Fuzzy match below threshold, trying AI disambiguation"
            )

            ai_match_result = await execute_with_retry(
                ai_disambiguate_standalone,
                input_data.song_metadata,
                search_results[:5],
                match_result.get("all_scores", []),
                max_attempts=3,
                initial_delay=2.0,
            )

            if ai_match_result["is_match"]:
                logger.info(
                    f"[{workflow_id}] AI found match: {ai_match_result.get('reasoning', 'N/A')}"
                )
                match_result = ai_match_result

        # Check if we have a match
        if not match_result["is_match"]:
            logger.info(
                f"[{workflow_id}] No match found above threshold "
                f"(best: {match_result['confidence']:.2f})"
            )
            result = WorkflowResult(
                success=False,
                message=f"No match above threshold {input_data.match_threshold} "
                f"(best match: {match_result['confidence']:.2f})",
                confidence_score=match_result["confidence"],
                execution_time_seconds=time.time() - start_time,
                match_method=match_result.get("match_method"),
            )
            state.status = "completed"
            state.result = result
            return result

        matched_track = match_result["matched_track"]
        logger.info(
            f"[{workflow_id}] Match found: '{matched_track.track_name}' "
            f"(confidence: {match_result['confidence']:.2f})"
        )

        # Step 3: Add to Playlist (with retry)
        state.current_step = "adding"
        await execute_with_retry(
            add_to_playlist_standalone,
            matched_track.spotify_uri,
            input_data.playlist_id,
            input_data.user_id,
            max_attempts=10,
            initial_delay=2.0,
        )

        # Step 4: Verify Addition
        state.current_step = "verifying"
        verification_result = await verify_track_standalone(
            matched_track.spotify_uri, input_data.playlist_id
        )

        if not verification_result.get("is_added", False):
            logger.warning(f"[{workflow_id}] Track verification failed, but operation may have succeeded")

        # Success!
        state.current_step = "completed"
        execution_time = time.time() - start_time

        logger.info(
            f"[{workflow_id}] Successfully synced '{matched_track.track_name}' in {execution_time:.2f}s"
        )

        result = WorkflowResult(
            success=True,
            message=f"Successfully added '{matched_track.track_name}' by {matched_track.artist_name} to playlist",
            spotify_track_id=matched_track.track_id,
            spotify_track_uri=matched_track.spotify_uri,
            confidence_score=match_result["confidence"],
            execution_time_seconds=execution_time,
            match_method=match_result.get("match_method"),
        )

        state.status = "completed"
        state.result = result
        return result

    except Exception as e:
        logger.error(f"[{workflow_id}] Workflow failed: {e}", exc_info=True)
        state.status = "failed"
        state.error = str(e)

        result = WorkflowResult(
            success=False,
            message=f"Workflow failed: {str(e)}",
            execution_time_seconds=time.time() - start_time,
        )
        state.result = result
        return result


def get_workflow_progress(workflow_id: str) -> Optional[WorkflowProgress]:
    """
    Get progress for a running standalone workflow.

    Note: This is a simplified version compared to Temporal's query mechanism.
    It returns the last known state from in-memory storage.
    """
    state = workflow_status_store.get(workflow_id)
    if not state:
        return None

    steps_map = {
        "initializing": 0,
        "searching": 1,
        "matching": 2,
        "ai_disambiguation": 2,
        "adding": 3,
        "verifying": 3,
        "completed": 4,
    }

    return WorkflowProgress(
        current_step=state.current_step,
        steps_completed=steps_map.get(state.current_step, 0),
        steps_total=4,
        candidates_found=state.candidates_found,
        elapsed_seconds=time.time() - state.start_time,
    )


def get_workflow_state(workflow_id: str) -> Optional[StandaloneWorkflowState]:
    """Get the full workflow state."""
    return workflow_status_store.get(workflow_id)
