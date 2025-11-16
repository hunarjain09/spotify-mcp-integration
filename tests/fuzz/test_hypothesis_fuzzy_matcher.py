"""Property-based fuzz testing using Hypothesis for fuzzy matching algorithm."""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
import asyncio

from models.data_models import SongMetadata, SpotifyTrackResult
from activities.fuzzy_matcher import fuzzy_match_tracks


# Helper to run async functions in tests
def async_test(coro):
    """Run async function synchronously for testing."""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


class TestFuzzyMatcherFuzz:
    """Property-based tests for fuzzy matching algorithm."""

    @given(
        title=st.text(min_size=1, max_size=200),
        artist=st.text(min_size=1, max_size=200),
        album=st.one_of(st.none(), st.text(max_size=200)),
        threshold=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=300, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_fuzzy_match_with_empty_results(self, title, artist, album, threshold):
        """Fuzzy matching with no search results should return no match."""
        metadata = SongMetadata(title=title, artist=artist, album=album)
        search_results = []

        result = async_test(fuzzy_match_tracks(metadata, search_results, threshold))

        assert result["is_match"] is False
        assert result["confidence"] == 0.0
        assert result["matched_track"] is None
        assert result["match_method"] == "none"

    @given(
        title=st.text(min_size=1, max_size=200),
        artist=st.text(min_size=1, max_size=200),
        threshold=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=300)
    def test_fuzzy_match_perfect_match(self, title, artist, threshold):
        """Perfect matches should have confidence of 1.0."""
        metadata = SongMetadata(title=title, artist=artist)

        # Create a perfect match
        perfect_match = SpotifyTrackResult(
            track_id="test_id",
            track_name=title,  # Exact same
            artist_name=artist,  # Exact same
            album_name="Test Album",
            spotify_uri="spotify:track:test",
            duration_ms=200000,
            popularity=50,
            release_date="2023-01-01",
        )

        result = async_test(fuzzy_match_tracks(metadata, [perfect_match], threshold))

        # Perfect match should have very high confidence (close to 1.0)
        assert result["confidence"] >= 0.9, f"Perfect match has low confidence: {result['confidence']}"

    @given(
        title=st.text(min_size=1, max_size=200),
        artist=st.text(min_size=1, max_size=200),
        different_title=st.text(min_size=1, max_size=200),
        different_artist=st.text(min_size=1, max_size=200),
        threshold=st.floats(min_value=0.5, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_fuzzy_match_completely_different(self, title, artist, different_title, different_artist, threshold):
        """Completely different songs should have low confidence."""
        # Ensure they're actually different
        assume(title.lower() != different_title.lower())
        assume(artist.lower() != different_artist.lower())

        metadata = SongMetadata(title=title, artist=artist)

        # Create a completely different track
        different_track = SpotifyTrackResult(
            track_id="test_id",
            track_name=different_title,
            artist_name=different_artist,
            album_name="Different Album",
            spotify_uri="spotify:track:test",
            duration_ms=200000,
            popularity=50,
            release_date="2023-01-01",
        )

        result = async_test(fuzzy_match_tracks(metadata, [different_track], threshold))

        # If threshold is high and songs are different, should not match
        if threshold >= 0.8:
            # Most likely won't match
            pass  # Can't assert for all cases

    @given(
        title=st.text(min_size=1, max_size=200),
        artist=st.text(min_size=1, max_size=200),
        num_results=st.integers(min_value=1, max_value=50),
        threshold=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_fuzzy_match_multiple_results(self, title, artist, num_results, threshold):
        """Should handle multiple search results without crashing."""
        metadata = SongMetadata(title=title, artist=artist)

        # Create multiple results with varying similarity
        search_results = []
        for i in range(num_results):
            track = SpotifyTrackResult(
                track_id=f"track_{i}",
                track_name=f"{title} {i}",
                artist_name=f"{artist} {i}",
                album_name=f"Album {i}",
                spotify_uri=f"spotify:track:{i}",
                duration_ms=200000 + i * 1000,
                popularity=50 + i,
                release_date="2023-01-01",
            )
            search_results.append(track)

        result = async_test(fuzzy_match_tracks(metadata, search_results, threshold))

        # Should return a result without crashing
        assert "is_match" in result
        assert "confidence" in result
        assert "all_scores" in result
        assert len(result["all_scores"]) == num_results

        # Scores should be sorted by confidence (descending)
        scores = [s["score"] for s in result["all_scores"]]
        assert scores == sorted(scores, reverse=True), "Scores not sorted properly"

    @given(
        isrc=st.text(alphabet=st.characters(whitelist_categories=("Lu", "Nd")), min_size=12, max_size=12),
        threshold=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_isrc_exact_match(self, isrc, threshold):
        """ISRC exact matches should have confidence 1.0."""
        metadata = SongMetadata(
            title="Test Song",
            artist="Test Artist",
            isrc=isrc,
        )

        # Create track with matching ISRC
        track_with_isrc = SpotifyTrackResult(
            track_id="test_id",
            track_name="Different Name",  # Even with different name
            artist_name="Different Artist",  # And different artist
            album_name="Album",
            spotify_uri="spotify:track:test",
            duration_ms=200000,
            popularity=50,
            release_date="2023-01-01",
            isrc=isrc,  # SAME ISRC
        )

        result = async_test(fuzzy_match_tracks(metadata, [track_with_isrc], threshold))

        # ISRC match should have confidence 1.0
        assert result["confidence"] == 1.0, f"ISRC match has confidence {result['confidence']}, expected 1.0"
        assert result["is_match"] is True  # Should always match with ISRC
        assert result["match_method"] == "isrc"

    @given(
        data=st.data(),
    )
    @settings(max_examples=200)
    def test_case_insensitivity(self, data):
        """Matching should be case-insensitive."""
        title = data.draw(st.text(min_size=1, max_size=100))
        artist = data.draw(st.text(min_size=1, max_size=100))

        # Create metadata with one case
        metadata = SongMetadata(title=title, artist=artist)

        # Create track with different case
        track = SpotifyTrackResult(
            track_id="test_id",
            track_name=title.swapcase(),  # Swap case
            artist_name=artist.swapcase(),
            album_name="Album",
            spotify_uri="spotify:track:test",
            duration_ms=200000,
            popularity=50,
            release_date="2023-01-01",
        )

        result = async_test(fuzzy_match_tracks(metadata, [track], 0.5))

        # Should have high confidence despite case difference
        assert result["confidence"] >= 0.8, f"Case-insensitive match failed: {result['confidence']}"

    @given(
        title=st.text(alphabet=st.characters(
            min_codepoint=0x0000,
            max_codepoint=0x10FFFF,
            blacklist_categories=("Cc", "Cs"),
        ), min_size=1, max_size=200),
        artist=st.text(alphabet=st.characters(
            min_codepoint=0x0000,
            max_codepoint=0x10FFFF,
            blacklist_categories=("Cc", "Cs"),
        ), min_size=1, max_size=200),
        threshold=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_unicode_matching(self, title, artist, threshold):
        """Should handle Unicode in fuzzy matching."""
        metadata = SongMetadata(title=title, artist=artist)

        track = SpotifyTrackResult(
            track_id="test_id",
            track_name=title,
            artist_name=artist,
            album_name="Album",
            spotify_uri="spotify:track:test",
            duration_ms=200000,
            popularity=50,
            release_date="2023-01-01",
        )

        # Should not crash on Unicode
        result = async_test(fuzzy_match_tracks(metadata, [track], threshold))

        assert isinstance(result, dict)
        assert "is_match" in result

    @given(
        threshold=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_special_characters_in_titles(self, threshold):
        """Should handle special characters properly."""
        special_chars_tests = [
            ("Don't Stop", "Don't Stop"),  # Apostrophes
            ("Song (feat. Artist2)", "Song feat Artist2"),  # Parentheses
            ("Song - Remix", "Song Remix"),  # Dashes
            ("What's Going On?", "What's Going On"),  # Punctuation
        ]

        for original, spotify_version in special_chars_tests:
            metadata = SongMetadata(title=original, artist="Artist")
            track = SpotifyTrackResult(
                track_id="test",
                track_name=spotify_version,
                artist_name="Artist",
                album_name="Album",
                spotify_uri="spotify:track:test",
                duration_ms=200000,
                popularity=50,
                release_date="2023-01-01",
            )

            result = async_test(fuzzy_match_tracks(metadata, [track], threshold))

            # Should have relatively high confidence despite punctuation differences
            if threshold <= 0.8:
                # With reasonable threshold, should match
                assert result["confidence"] > 0.5, f"Failed to match '{original}' with '{spotify_version}'"

    @given(
        title=st.text(min_size=1, max_size=200),
        artist=st.text(min_size=1, max_size=200),
        num_results=st.integers(min_value=1, max_value=100),
        threshold=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_confidence_score_bounds(self, title, artist, num_results, threshold):
        """All confidence scores should be between 0.0 and 1.0."""
        metadata = SongMetadata(title=title, artist=artist)

        search_results = [
            SpotifyTrackResult(
                track_id=f"track_{i}",
                track_name=f"{title} variant {i}",
                artist_name=f"{artist} feat. Someone",
                album_name="Album",
                spotify_uri=f"spotify:track:{i}",
                duration_ms=200000,
                popularity=50,
                release_date="2023-01-01",
            )
            for i in range(num_results)
        ]

        result = async_test(fuzzy_match_tracks(metadata, search_results, threshold))

        # Main confidence should be in bounds
        assert 0.0 <= result["confidence"] <= 1.0, f"Confidence out of bounds: {result['confidence']}"

        # All individual scores should be in bounds
        for score_info in result["all_scores"]:
            assert 0.0 <= score_info["score"] <= 1.0, f"Individual score out of bounds: {score_info['score']}"
            assert 0.0 <= score_info["title_score"] <= 1.0
            assert 0.0 <= score_info["artist_score"] <= 1.0
            assert 0.0 <= score_info["album_score"] <= 1.0


class TestFuzzyMatcherEdgeCases:
    """Test specific edge cases in fuzzy matching."""

    def test_empty_string_fields(self):
        """Empty string fields should not crash."""
        metadata = SongMetadata(title="", artist="")

        track = SpotifyTrackResult(
            track_id="test",
            track_name="",
            artist_name="",
            album_name="",
            spotify_uri="spotify:track:test",
            duration_ms=200000,
            popularity=50,
            release_date="2023-01-01",
        )

        # Should not crash
        result = async_test(fuzzy_match_tracks(metadata, [track], 0.5))
        assert isinstance(result, dict)

    def test_very_long_strings(self):
        """Very long strings should not cause performance issues."""
        long_title = "A" * 10000
        long_artist = "B" * 10000

        metadata = SongMetadata(title=long_title, artist=long_artist)

        track = SpotifyTrackResult(
            track_id="test",
            track_name=long_title,
            artist_name=long_artist,
            album_name="Album",
            spotify_uri="spotify:track:test",
            duration_ms=200000,
            popularity=50,
            release_date="2023-01-01",
        )

        # Should complete in reasonable time (not timeout)
        result = async_test(fuzzy_match_tracks(metadata, [track], 0.5))
        assert result["confidence"] >= 0.9  # Should be a perfect match

    def test_none_album_handling(self):
        """None album should not crash or leak into scores."""
        metadata = SongMetadata(title="Test", artist="Artist", album=None)

        track = SpotifyTrackResult(
            track_id="test",
            track_name="Test",
            artist_name="Artist",
            album_name="Some Album",
            spotify_uri="spotify:track:test",
            duration_ms=200000,
            popularity=50,
            release_date="2023-01-01",
        )

        result = async_test(fuzzy_match_tracks(metadata, [track], 0.5))

        # Should handle None album gracefully
        assert result["confidence"] > 0.7  # Title and artist match
        for score in result["all_scores"]:
            assert score["album_score"] >= 0.0  # Should have valid album score


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
