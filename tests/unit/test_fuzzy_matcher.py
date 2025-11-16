"""Unit tests for fuzzy matching activity."""

import pytest
from unittest.mock import patch, Mock
from activities.fuzzy_matcher import fuzzy_match_tracks
from models.data_models import SongMetadata, SpotifyTrackResult


class TestFuzzyMatcher:
    """Tests for fuzzy_match_tracks activity."""

    @pytest.mark.asyncio
    async def test_empty_search_results(self, sample_song_metadata):
        """Test fuzzy matching with no search results."""
        result = await fuzzy_match_tracks(
            original_metadata=sample_song_metadata,
            search_results=[],
            threshold=0.85,
        )

        assert result["is_match"] is False
        assert result["confidence"] == 0.0
        assert result["matched_track"] is None
        assert result["match_method"] == "none"
        assert result["all_scores"] == []

    @pytest.mark.asyncio
    async def test_exact_match(self, make_song_metadata, make_spotify_track):
        """Test perfect match with identical track information."""
        song = make_song_metadata(
            title="Bohemian Rhapsody",
            artist="Queen",
            album="A Night at the Opera",
        )

        track = make_spotify_track(
            track_id="7tFiyTwD0nx5a1eklYtX2J",
            track_name="Bohemian Rhapsody",
            artist_name="Queen",
            album_name="A Night at the Opera",
        )

        result = await fuzzy_match_tracks(
            original_metadata=song,
            search_results=[track],
            threshold=0.85,
        )

        assert result["is_match"] is True
        assert result["confidence"] == 1.0
        assert result["matched_track"] == track
        assert result["match_method"] == "fuzzy"
        assert len(result["all_scores"]) == 1

    @pytest.mark.asyncio
    async def test_isrc_exact_match(self, make_song_metadata, make_spotify_track):
        """Test ISRC exact match takes priority."""
        song = make_song_metadata(
            title="Bohemian Rhapsody",
            artist="Queen",
            album="A Night at the Opera",
            isrc="GBUM71029604",
        )

        # Track with different title but same ISRC
        track = make_spotify_track(
            track_id="7tFiyTwD0nx5a1eklYtX2J",
            track_name="Bohemian Rhapsody - Remastered",
            artist_name="Queen",
            album_name="Greatest Hits",
        )
        track.isrc = "GBUM71029604"

        result = await fuzzy_match_tracks(
            original_metadata=song,
            search_results=[track],
            threshold=0.85,
        )

        assert result["is_match"] is True
        assert result["confidence"] == 1.0
        assert result["matched_track"] == track
        assert result["match_method"] == "isrc"

    @pytest.mark.asyncio
    async def test_isrc_mismatch_falls_back_to_fuzzy(
        self, make_song_metadata, make_spotify_track
    ):
        """Test that ISRC mismatch falls back to fuzzy matching."""
        song = make_song_metadata(
            title="Bohemian Rhapsody",
            artist="Queen",
            album="A Night at the Opera",
            isrc="GBUM71029604",
        )

        track = make_spotify_track(
            track_id="different_track",
            track_name="Bohemian Rhapsody",
            artist_name="Queen",
            album_name="A Night at the Opera",
        )
        track.isrc = "DIFFERENT12345"  # Different ISRC

        result = await fuzzy_match_tracks(
            original_metadata=song,
            search_results=[track],
            threshold=0.85,
        )

        # Should still match based on fuzzy matching
        # Even with ISRC mismatch, perfect text match gives confidence = 1.0
        assert result["is_match"] is True
        assert result["confidence"] == 1.0  # Perfect fuzzy match
        assert result["match_method"] == "fuzzy"  # Uses fuzzy, not ISRC

    @pytest.mark.asyncio
    async def test_below_threshold_no_match(self, make_song_metadata, make_spotify_track):
        """Test that low-scoring tracks are rejected."""
        song = make_song_metadata(
            title="Bohemian Rhapsody",
            artist="Queen",
            album="A Night at the Opera",
        )

        # Completely different track
        track = make_spotify_track(
            track_id="different_track",
            track_name="Imagine",
            artist_name="John Lennon",
            album_name="Imagine",
        )

        result = await fuzzy_match_tracks(
            original_metadata=song,
            search_results=[track],
            threshold=0.85,
        )

        assert result["is_match"] is False
        assert result["confidence"] < 0.85
        assert result["matched_track"] is None
        assert result["match_method"] == "none"

    @pytest.mark.asyncio
    async def test_best_match_selection(self, make_song_metadata, make_spotify_track):
        """Test that the best match is selected from multiple candidates."""
        song = make_song_metadata(
            title="Bohemian Rhapsody",
            artist="Queen",
            album="A Night at the Opera",
        )

        # Create multiple candidates with varying match quality
        perfect_match = make_spotify_track(
            track_id="perfect",
            track_name="Bohemian Rhapsody",
            artist_name="Queen",
            album_name="A Night at the Opera",
        )

        good_match = make_spotify_track(
            track_id="good",
            track_name="Bohemian Rhapsody",
            artist_name="Queen",
            album_name="Greatest Hits",
        )

        poor_match = make_spotify_track(
            track_id="poor",
            track_name="Bohemian Rhapsody - Cover",
            artist_name="Various Artists",
            album_name="Rock Covers",
        )

        result = await fuzzy_match_tracks(
            original_metadata=song,
            search_results=[poor_match, perfect_match, good_match],
            threshold=0.85,
        )

        assert result["is_match"] is True
        assert result["matched_track"] == perfect_match
        assert result["confidence"] > 0.95

    @pytest.mark.asyncio
    async def test_scoring_without_album(self, make_song_metadata, make_spotify_track):
        """Test fuzzy matching when album is not provided."""
        song = make_song_metadata(
            title="Imagine",
            artist="John Lennon",
            album=None,  # No album
        )

        track = make_spotify_track(
            track_name="Imagine",
            artist_name="John Lennon",
            album_name="Imagine",
        )

        result = await fuzzy_match_tracks(
            original_metadata=song,
            search_results=[track],
            threshold=0.85,
        )

        # Should still match based on title and artist
        assert result["is_match"] is True
        # Album score should be 0.0
        assert result["all_scores"][0]["album_score"] == 0.0

    @pytest.mark.asyncio
    async def test_case_insensitive_matching(self, make_song_metadata, make_spotify_track):
        """Test that matching is case insensitive."""
        song = make_song_metadata(
            title="bohemian rhapsody",  # lowercase
            artist="QUEEN",  # uppercase
            album="a night at the opera",  # lowercase
        )

        track = make_spotify_track(
            track_name="Bohemian Rhapsody",  # Title case
            artist_name="Queen",  # Title case
            album_name="A Night At The Opera",  # Title case
        )

        result = await fuzzy_match_tracks(
            original_metadata=song,
            search_results=[track],
            threshold=0.85,
        )

        assert result["is_match"] is True
        assert result["confidence"] == 1.0

    @pytest.mark.asyncio
    async def test_partial_title_match(self, make_song_metadata, make_spotify_track):
        """Test fuzzy matching with slightly different titles."""
        song = make_song_metadata(
            title="Bohemian Rhapsody",
            artist="Queen",
        )

        # Track with extra text in title
        track = make_spotify_track(
            track_name="Bohemian Rhapsody - 2011 Remaster",
            artist_name="Queen",
        )

        result = await fuzzy_match_tracks(
            original_metadata=song,
            search_results=[track],
            threshold=0.75,  # Lower threshold for remaster versions
        )

        assert result["is_match"] is True
        assert 0.75 <= result["confidence"] < 1.0

    @pytest.mark.asyncio
    async def test_score_details_included(self, make_song_metadata, make_spotify_track):
        """Test that detailed scoring information is included in results."""
        song = make_song_metadata(
            title="Bohemian Rhapsody",
            artist="Queen",
            album="A Night at the Opera",
        )

        track = make_spotify_track(
            track_name="Bohemian Rhapsody",
            artist_name="Queen",
            album_name="A Night at the Opera",
        )

        result = await fuzzy_match_tracks(
            original_metadata=song,
            search_results=[track],
            threshold=0.85,
        )

        assert len(result["all_scores"]) == 1
        score_details = result["all_scores"][0]

        assert "track" in score_details
        assert "score" in score_details
        assert "title_score" in score_details
        assert "artist_score" in score_details
        assert "album_score" in score_details
        assert "isrc_match" in score_details

    @pytest.mark.asyncio
    async def test_scores_sorted_by_confidence(self, make_song_metadata, make_spotify_track):
        """Test that all_scores are sorted by confidence descending."""
        song = make_song_metadata(
            title="Test Song",
            artist="Test Artist",
        )

        track1 = make_spotify_track(
            track_id="track1",
            track_name="Test Song",
            artist_name="Test Artist",
        )

        track2 = make_spotify_track(
            track_id="track2",
            track_name="Test Song Cover",
            artist_name="Different Artist",
        )

        track3 = make_spotify_track(
            track_id="track3",
            track_name="Test Song Remix",
            artist_name="Test Artist",
        )

        result = await fuzzy_match_tracks(
            original_metadata=song,
            search_results=[track2, track3, track1],  # Not in score order
            threshold=0.5,
        )

        # Scores should be sorted descending
        scores = [s["score"] for s in result["all_scores"]]
        assert scores == sorted(scores, reverse=True)

        # Best match (track1) should be first
        assert result["all_scores"][0]["track"]["track_id"] == "track1"

    @pytest.mark.asyncio
    async def test_weighted_scoring(self, make_song_metadata, make_spotify_track):
        """Test that scoring uses correct weights (title 50%, artist 35%, album 15%)."""
        song = make_song_metadata(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
        )

        track = make_spotify_track(
            track_name="Test Song",  # 100% match
            artist_name="ZZZZZ XXXXX",  # ~0% match - completely different chars
            album_name="Test Album",  # 100% match
        )

        result = await fuzzy_match_tracks(
            original_metadata=song,
            search_results=[track],
            threshold=0.0,
        )

        # Expected score: 1.0 * 0.5 (title) + 0.0 * 0.35 (artist) + 1.0 * 0.15 (album) = 0.65
        score_details = result["all_scores"][0]
        assert score_details["title_score"] == 1.0
        assert score_details["artist_score"] < 0.1  # Very low due to different artist
        assert score_details["album_score"] == 1.0
        # Combined should be around 0.65
        assert 0.60 <= result["confidence"] <= 0.70

    @pytest.mark.asyncio
    async def test_multiple_isrc_matches(self, make_song_metadata, make_spotify_track):
        """Test behavior when multiple tracks have the same ISRC."""
        song = make_song_metadata(
            title="Test Song",
            artist="Test Artist",
            isrc="TEST12345678",
        )

        track1 = make_spotify_track(
            track_id="track1",
            track_name="Test Song",
            artist_name="Test Artist",
        )
        track1.isrc = "TEST12345678"

        track2 = make_spotify_track(
            track_id="track2",
            track_name="Test Song - Deluxe",
            artist_name="Test Artist",
        )
        track2.isrc = "TEST12345678"

        result = await fuzzy_match_tracks(
            original_metadata=song,
            search_results=[track1, track2],
            threshold=0.85,
        )

        # Should match with perfect score
        assert result["is_match"] is True
        assert result["confidence"] == 1.0
        assert result["match_method"] == "isrc"
        # Both should have perfect scores
        assert result["all_scores"][0]["score"] == 1.0
        assert result["all_scores"][1]["score"] == 1.0

    @pytest.mark.asyncio
    async def test_threshold_boundary(self, make_song_metadata, make_spotify_track):
        """Test exact threshold boundary conditions."""
        song = make_song_metadata(
            title="Test Song",
            artist="Test Artist",
        )

        track = make_spotify_track(
            track_name="Test Song",
            artist_name="Test Artist Similar",  # Slightly different
        )

        # Test with threshold exactly at the boundary
        result = await fuzzy_match_tracks(
            original_metadata=song,
            search_results=[track],
            threshold=0.9,
        )

        # Score should be close to but slightly below 1.0
        confidence = result["confidence"]

        # Test that is_match depends on threshold
        if confidence >= 0.9:
            assert result["is_match"] is True
        else:
            assert result["is_match"] is False

    @pytest.mark.asyncio
    async def test_special_characters_in_names(self, make_song_metadata, make_spotify_track):
        """Test fuzzy matching with special characters."""
        song = make_song_metadata(
            title="Don't Stop Believin'",
            artist="Journey",
        )

        track = make_spotify_track(
            track_name="Don't Stop Believin'",
            artist_name="Journey",
        )

        result = await fuzzy_match_tracks(
            original_metadata=song,
            search_results=[track],
            threshold=0.85,
        )

        assert result["is_match"] is True

    @pytest.mark.asyncio
    async def test_unicode_characters(self, make_song_metadata, make_spotify_track):
        """Test fuzzy matching with unicode characters."""
        song = make_song_metadata(
            title="Café del Mar",
            artist="Énergïa",
        )

        track = make_spotify_track(
            track_name="Café del Mar",
            artist_name="Énergïa",
        )

        result = await fuzzy_match_tracks(
            original_metadata=song,
            search_results=[track],
            threshold=0.85,
        )

        assert result["is_match"] is True
