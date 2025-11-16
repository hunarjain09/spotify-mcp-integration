"""AI-powered disambiguation activity supporting both LangChain (OpenAI) and Claude SDK."""

from typing import List, Dict, Optional

from temporalio import activity
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from anthropic import AsyncAnthropic

from models.data_models import SongMetadata, SpotifyTrackResult
from config.settings import settings


@activity.defn(name="ai-disambiguate")
async def ai_disambiguate_track(
    original_metadata: SongMetadata,
    candidates: List[SpotifyTrackResult],
    fuzzy_scores: List[Dict],
) -> Dict:
    """Use LLM to choose between ambiguous matches.

    Supports both LangChain (OpenAI) and Claude SDK providers.
    The provider is selected via settings.ai_provider.

    Args:
        original_metadata: Original song from Apple Music
        candidates: List of candidate Spotify tracks
        fuzzy_scores: Fuzzy matching scores for each candidate

    Returns:
        Dictionary with match result containing:
        - is_match: bool
        - confidence: float
        - matched_track: SpotifyTrackResult or None
        - match_method: str
        - reasoning: str (AI's explanation)
    """
    activity.logger.info(
        f"AI disambiguating {len(candidates)} candidates for: {original_metadata} using provider: {settings.ai_provider}"
    )

    # Route to appropriate provider
    if settings.ai_provider == "langchain":
        return await _ai_disambiguate_with_langchain(original_metadata, candidates, fuzzy_scores)
    elif settings.ai_provider == "claude":
        return await _ai_disambiguate_with_claude(original_metadata, candidates, fuzzy_scores)
    else:
        raise ValueError(f"Unknown AI provider: {settings.ai_provider}")


async def _ai_disambiguate_with_langchain(
    original_metadata: SongMetadata,
    candidates: List[SpotifyTrackResult],
    fuzzy_scores: List[Dict],
) -> Dict:
    """Use LangChain (OpenAI) to choose between ambiguous matches.

    Args:
        original_metadata: Original song from Apple Music
        candidates: List of candidate Spotify tracks
        fuzzy_scores: Fuzzy matching scores for each candidate

    Returns:
        Dictionary with match result
    """

    if not candidates:
        return {
            "is_match": False,
            "confidence": 0.0,
            "matched_track": None,
            "match_method": "ai_failed",
            "reasoning": "No candidates provided",
        }

    try:
        # Format candidates for LLM
        candidates_text = ""
        for idx, candidate in enumerate(candidates, 1):
            # Find corresponding fuzzy score
            fuzzy_info = next(
                (
                    s
                    for s in fuzzy_scores
                    if s.get("track", {}).get("track_id") == candidate.track_id
                ),
                {"score": 0},
            )

            candidates_text += f"""
{idx}. "{candidate.track_name}" by {candidate.artist_name}
   Album: {candidate.album_name}
   Release Date: {candidate.release_date}
   Fuzzy Match Score: {fuzzy_info.get('score', 0):.2f}
   Popularity: {candidate.popularity}
   URI: {candidate.spotify_uri}
"""

        # Create LLM prompt
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

        # Initialize LLM
        llm = ChatOpenAI(
            model=settings.ai_model,
            temperature=0,  # Deterministic for consistency
            api_key=settings.openai_api_key,
        )

        # Create chain and invoke
        chain = prompt | llm

        activity.logger.info(f"Invoking AI with model: {settings.ai_model}")

        response = await chain.ainvoke(
            {
                "title": original_metadata.title,
                "artist": original_metadata.artist,
                "album": original_metadata.album or "Unknown",
                "candidates": candidates_text,
            }
        )

        # Parse response
        content = response.content
        activity.logger.debug(f"AI response: {content}")

        # Extract URI and reason
        try:
            lines = content.strip().split("\n")
            uri_line = next((l for l in lines if l.startswith("URI:")), None)
            reason_line = next((l for l in lines if l.startswith("REASON:")), None)

            if not uri_line or not reason_line:
                raise ValueError("AI response missing URI or REASON")

            selected_uri = uri_line.replace("URI:", "").strip()
            reasoning = reason_line.replace("REASON:", "").strip()

            # Check if AI said no match
            if selected_uri.upper() == "NONE":
                activity.logger.info(f"AI determined no match: {reasoning}")
                return {
                    "is_match": False,
                    "confidence": 0.0,
                    "matched_track": None,
                    "match_method": "ai",
                    "reasoning": reasoning,
                }

            # Find matching candidate
            matched_track = next(
                (c for c in candidates if c.spotify_uri == selected_uri), None
            )

            if matched_track:
                activity.logger.info(f"AI selected: {matched_track.track_name} - {reasoning}")
                return {
                    "is_match": True,
                    "confidence": 0.90,  # AI match gets high confidence
                    "matched_track": matched_track,
                    "match_method": "ai",
                    "reasoning": reasoning,
                }
            else:
                # AI returned a URI not in our candidates
                activity.logger.warning(f"AI returned invalid URI: {selected_uri}")
                return {
                    "is_match": False,
                    "confidence": 0.0,
                    "matched_track": None,
                    "match_method": "ai_failed",
                    "reasoning": f"AI returned invalid URI: {selected_uri}",
                }

        except (ValueError, StopIteration) as e:
            activity.logger.error(f"Failed to parse AI response: {e}")
            return {
                "is_match": False,
                "confidence": 0.0,
                "matched_track": None,
                "match_method": "ai_failed",
                "reasoning": f"Failed to parse AI response: {str(e)}",
            }

    except Exception as e:
        # Handle API errors
        activity.logger.error(f"AI disambiguation failed: {e}")

        # Check for API key errors (non-retryable)
        error_str = str(e).lower()
        if "api key" in error_str or "authentication" in error_str:
            raise activity.ApplicationError(
                f"Invalid OpenAI API key: {str(e)}",
                non_retryable=True,
                type="InvalidAPIKeyError",
            )

        # Other errors are retryable
        raise activity.ApplicationError(
            f"AI disambiguation error: {str(e)}", non_retryable=False, type="AIDisambiguationError"
        )


async def _ai_disambiguate_with_claude(
    original_metadata: SongMetadata,
    candidates: List[SpotifyTrackResult],
    fuzzy_scores: List[Dict],
) -> Dict:
    """Use Claude SDK (Anthropic) to choose between ambiguous matches.

    Args:
        original_metadata: Original song from Apple Music
        candidates: List of candidate Spotify tracks
        fuzzy_scores: Fuzzy matching scores for each candidate

    Returns:
        Dictionary with match result
    """

    if not candidates:
        return {
            "is_match": False,
            "confidence": 0.0,
            "matched_track": None,
            "match_method": "ai_failed",
            "reasoning": "No candidates provided",
        }

    try:
        # Format candidates for Claude
        candidates_text = ""
        for idx, candidate in enumerate(candidates, 1):
            # Find corresponding fuzzy score
            fuzzy_info = next(
                (
                    s
                    for s in fuzzy_scores
                    if s.get("track", {}).get("track_id") == candidate.track_id
                ),
                {"score": 0},
            )

            candidates_text += f"""
{idx}. "{candidate.track_name}" by {candidate.artist_name}
   Album: {candidate.album_name}
   Release Date: {candidate.release_date}
   Fuzzy Match Score: {fuzzy_info.get('score', 0):.2f}
   Popularity: {candidate.popularity}
   URI: {candidate.spotify_uri}
"""

        # Create the prompt for Claude
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

        # Initialize Claude client
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)

        activity.logger.info(f"Invoking Claude with model: {settings.claude_model}")

        # Call Claude API
        response = await client.messages.create(
            model=settings.claude_model,
            max_tokens=1024,
            temperature=0,  # Deterministic for consistency
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        # Parse response
        content = response.content[0].text
        activity.logger.debug(f"Claude response: {content}")

        # Extract URI and reason
        try:
            lines = content.strip().split("\n")
            uri_line = next((l for l in lines if l.startswith("URI:")), None)
            reason_line = next((l for l in lines if l.startswith("REASON:")), None)

            if not uri_line or not reason_line:
                raise ValueError("Claude response missing URI or REASON")

            selected_uri = uri_line.replace("URI:", "").strip()
            reasoning = reason_line.replace("REASON:", "").strip()

            # Check if Claude said no match
            if selected_uri.upper() == "NONE":
                activity.logger.info(f"Claude determined no match: {reasoning}")
                return {
                    "is_match": False,
                    "confidence": 0.0,
                    "matched_track": None,
                    "match_method": "ai_claude",
                    "reasoning": reasoning,
                }

            # Find matching candidate
            matched_track = next(
                (c for c in candidates if c.spotify_uri == selected_uri), None
            )

            if matched_track:
                activity.logger.info(f"Claude selected: {matched_track.track_name} - {reasoning}")
                return {
                    "is_match": True,
                    "confidence": 0.90,  # AI match gets high confidence
                    "matched_track": matched_track,
                    "match_method": "ai_claude",
                    "reasoning": reasoning,
                }
            else:
                # Claude returned a URI not in our candidates
                activity.logger.warning(f"Claude returned invalid URI: {selected_uri}")
                return {
                    "is_match": False,
                    "confidence": 0.0,
                    "matched_track": None,
                    "match_method": "ai_failed",
                    "reasoning": f"Claude returned invalid URI: {selected_uri}",
                }

        except (ValueError, StopIteration) as e:
            activity.logger.error(f"Failed to parse Claude response: {e}")
            return {
                "is_match": False,
                "confidence": 0.0,
                "matched_track": None,
                "match_method": "ai_failed",
                "reasoning": f"Failed to parse Claude response: {str(e)}",
            }

    except Exception as e:
        # Handle API errors
        activity.logger.error(f"Claude AI disambiguation failed: {e}")

        # Check for API key errors (non-retryable)
        error_str = str(e).lower()
        if "api key" in error_str or "authentication" in error_str or "unauthorized" in error_str:
            raise activity.ApplicationError(
                f"Invalid Anthropic API key: {str(e)}",
                non_retryable=True,
                type="InvalidAPIKeyError",
            )

        # Other errors are retryable
        raise activity.ApplicationError(
            f"Claude AI disambiguation error: {str(e)}",
            non_retryable=False,
            type="AIDisambiguationError",
        )
