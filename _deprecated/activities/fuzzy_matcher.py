"""Fuzzy matching activity for finding the best Spotify track match."""

from typing import List, Dict, Optional

from temporalio import activity
from rapidfuzz import fuzz

from models.data_models import SongMetadata, SpotifyTrackResult, FuzzyMatchScore


@activity.defn(name="fuzzy-match")
async def fuzzy_match_tracks(
    original_metadata: SongMetadata,
    search_results: List[SpotifyTrackResult],
    threshold: float,
) -> Dict:
    """Fuzzy string matching to find best track match.

    Args:
        original_metadata: Original song from Apple Music
        search_results: List of Spotify search results
        threshold: Minimum confidence score (0.0-1.0)

    Returns:
        Dictionary with match result containing:
        - is_match: bool
        - confidence: float
        - matched_track: SpotifyTrackResult or None
        - match_method: str
        - all_scores: List of FuzzyMatchScore
    """
    activity.logger.info(f"Fuzzy matching {len(search_results)} candidates for: {original_metadata}")

    if not search_results:
        activity.logger.info("No search results to match")
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
        # Calculate individual component scores
        title_score = (
            fuzz.ratio(original_metadata.title.lower(), result.track_name.lower()) / 100.0
        )

        artist_score = (
            fuzz.ratio(original_metadata.artist.lower(), result.artist_name.lower()) / 100.0
        )

        album_score = 0.0
        if original_metadata.album and result.album_name:
            album_score = (
                fuzz.ratio(original_metadata.album.lower(), result.album_name.lower()) / 100.0
            )

        # Check for ISRC exact match (highest priority)
        isrc_match = False
        if original_metadata.isrc and result.isrc:
            if original_metadata.isrc == result.isrc:
                isrc_match = True
                # ISRC match is perfect
                combined_score = 1.0
            else:
                # ISRCs exist but don't match - calculate weighted score
                combined_score = title_score * 0.5 + artist_score * 0.35 + album_score * 0.15
        else:
            # No ISRC available - use weighted combination
            # Title is most important (50%), then artist (35%), then album (15%)
            combined_score = title_score * 0.5 + artist_score * 0.35 + album_score * 0.15

        # Store score details
        score_info = FuzzyMatchScore(
            track=result,
            combined_score=combined_score,
            title_score=title_score,
            artist_score=artist_score,
            album_score=album_score,
            isrc_match=isrc_match,
        )
        all_scores.append(score_info)

        # Track best match
        if combined_score > best_score:
            best_score = combined_score
            best_match = result

    # Sort scores by combined_score descending
    all_scores.sort(key=lambda x: x.combined_score, reverse=True)

    # Determine if we have a match above threshold
    is_match = best_score >= threshold

    # Determine match method
    match_method = "none"
    if is_match:
        if any(score.isrc_match for score in all_scores[:1]):  # Check best match
            match_method = "isrc"
        else:
            match_method = "fuzzy"

    activity.logger.info(
        f"Best match: {best_match.track_name if best_match else 'None'} "
        f"(score: {best_score:.2f}, threshold: {threshold}, method: {match_method})"
    )

    # Log top 3 candidates for debugging
    for idx, score in enumerate(all_scores[:3], 1):
        activity.logger.debug(
            f"  #{idx}: {score.track.track_name} by {score.track.artist_name} "
            f"(score: {score.combined_score:.2f}, "
            f"title: {score.title_score:.2f}, "
            f"artist: {score.artist_score:.2f}, "
            f"album: {score.album_score:.2f})"
        )

    return {
        "is_match": is_match,
        "confidence": best_score,
        "matched_track": best_match if is_match else None,
        "match_method": match_method,
        "all_scores": [
            {
                "track": {
                    "track_id": score.track.track_id,
                    "track_name": score.track.track_name,
                    "artist_name": score.track.artist_name,
                    "album_name": score.track.album_name,
                    "spotify_uri": score.track.spotify_uri,
                },
                "score": score.combined_score,
                "title_score": score.title_score,
                "artist_score": score.artist_score,
                "album_score": score.album_score,
                "isrc_match": score.isrc_match,
            }
            for score in all_scores
        ],
    }
