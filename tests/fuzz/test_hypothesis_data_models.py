"""Property-based fuzz testing using Hypothesis for data models."""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from datetime import datetime

from models.data_models import (
    SongMetadata,
    SpotifyTrackResult,
    WorkflowInput,
    WorkflowResult,
    WorkflowProgress,
)


class TestSongMetadataFuzz:
    """Property-based tests for SongMetadata."""

    @given(
        title=st.text(min_size=1, max_size=500),
        artist=st.text(min_size=1, max_size=500),
        album=st.one_of(st.none(), st.text(max_size=500)),
        duration_ms=st.one_of(st.none(), st.integers(min_value=0, max_value=7200000)),  # 0-2 hours
        isrc=st.one_of(st.none(), st.text(max_size=50)),
    )
    @settings(max_examples=500)
    def test_song_metadata_creation(self, title, artist, album, duration_ms, isrc):
        """Should handle all valid combinations of song metadata."""
        metadata = SongMetadata(
            title=title,
            artist=artist,
            album=album,
            duration_ms=duration_ms,
            isrc=isrc,
        )
        assert metadata.title == title
        assert metadata.artist == artist
        assert str(metadata)  # __str__ should not crash

    @given(
        title=st.text(min_size=1, max_size=500),
        artist=st.text(min_size=1, max_size=500),
        album=st.one_of(st.none(), st.text(max_size=500)),
    )
    @settings(max_examples=300)
    def test_search_query_generation(self, title, artist, album):
        """Search query generation should never crash."""
        metadata = SongMetadata(title=title, artist=artist, album=album)
        query = metadata.to_search_query()

        assert isinstance(query, str)
        assert "track:" in query
        assert "artist:" in query
        if album:
            assert "album:" in query

        # Ensure no None leaks into query
        assert "None" not in query

    @given(
        title=st.text(alphabet=st.characters(
            min_codepoint=0x0000,
            max_codepoint=0x10FFFF,
            blacklist_categories=("Cc", "Cs"),  # Control chars
        ), min_size=1, max_size=200),
        artist=st.text(alphabet=st.characters(
            min_codepoint=0x0000,
            max_codepoint=0x10FFFF,
            blacklist_categories=("Cc", "Cs"),
        ), min_size=1, max_size=200),
    )
    @settings(max_examples=300)
    def test_unicode_in_metadata(self, title, artist):
        """Should handle all Unicode characters properly."""
        metadata = SongMetadata(title=title, artist=artist)
        query = metadata.to_search_query()

        # Should not have Unicode errors
        assert isinstance(query, str)
        # Should not have replacement characters
        assert "\ufffd" not in query

    @given(
        duration_ms=st.one_of(
            st.integers(min_value=-1000000, max_value=-1),  # Negative
            st.integers(min_value=10800000, max_value=100000000),  # > 3 hours
        )
    )
    @settings(max_examples=100)
    def test_unrealistic_durations(self, duration_ms):
        """Should accept but could validate unrealistic duration values."""
        # Currently no validation - this might be a BUG
        metadata = SongMetadata(
            title="Test",
            artist="Artist",
            duration_ms=duration_ms,
        )
        # Negative durations or extremely long (>3 hours) might be bugs
        if duration_ms < 0 or duration_ms > 7200000:  # 2 hours
            pytest.fail(f"Unrealistic duration accepted: {duration_ms}ms ({duration_ms/1000/60:.1f} minutes)")


class TestSpotifyTrackResultFuzz:
    """Property-based tests for SpotifyTrackResult."""

    @given(
        track_id=st.text(min_size=1, max_size=100),
        track_name=st.text(min_size=1, max_size=500),
        artist_name=st.text(min_size=1, max_size=500),
        album_name=st.text(min_size=1, max_size=500),
        spotify_uri=st.text(min_size=1, max_size=200),
        duration_ms=st.integers(min_value=0, max_value=7200000),
        popularity=st.integers(min_value=0, max_value=100),
        release_date=st.text(min_size=1, max_size=50),
        isrc=st.one_of(st.none(), st.text(max_size=50)),
    )
    @settings(max_examples=400)
    def test_track_result_creation(self, track_id, track_name, artist_name, album_name,
                                    spotify_uri, duration_ms, popularity, release_date, isrc):
        """Should handle all valid track result combinations."""
        track = SpotifyTrackResult(
            track_id=track_id,
            track_name=track_name,
            artist_name=artist_name,
            album_name=album_name,
            spotify_uri=spotify_uri,
            duration_ms=duration_ms,
            popularity=popularity,
            release_date=release_date,
            isrc=isrc,
        )
        assert track.track_id == track_id
        assert str(track)  # Should not crash

    @given(
        popularity=st.one_of(
            st.integers(min_value=-1000, max_value=-1),  # Negative
            st.integers(min_value=101, max_value=10000),  # > 100
        )
    )
    @settings(max_examples=100)
    def test_invalid_popularity_values(self, popularity):
        """Spotify popularity should be 0-100, but no validation exists."""
        # Currently no validation - this is a BUG
        track = SpotifyTrackResult(
            track_id="test",
            track_name="Test",
            artist_name="Artist",
            album_name="Album",
            spotify_uri="spotify:track:test",
            duration_ms=200000,
            popularity=popularity,
            release_date="2023-01-01",
        )
        # Should fail if popularity is out of range
        if popularity < 0 or popularity > 100:
            pytest.fail(f"Invalid popularity accepted: {popularity} (should be 0-100)")


class TestWorkflowInputFuzz:
    """Property-based tests for WorkflowInput."""

    @given(
        title=st.text(min_size=1, max_size=200),
        artist=st.text(min_size=1, max_size=200),
        playlist_id=st.text(min_size=1, max_size=100),
        user_id=st.text(min_size=1, max_size=100),
        match_threshold=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        use_ai=st.booleans(),
    )
    @settings(max_examples=400)
    def test_valid_workflow_input(self, title, artist, playlist_id, user_id, match_threshold, use_ai):
        """Valid workflow inputs should not crash."""
        try:
            workflow_input = WorkflowInput(
                song_metadata=SongMetadata(title=title, artist=artist),
                playlist_id=playlist_id,
                user_id=user_id,
                match_threshold=match_threshold,
                use_ai_disambiguation=use_ai,
            )
            assert 0.0 <= workflow_input.match_threshold <= 1.0
        except ValueError as e:
            # Validation errors are OK for empty playlist_id
            if "playlist_id" in str(e):
                pass
            else:
                raise

    @given(
        match_threshold=st.one_of(
            st.floats(min_value=-1e10, max_value=-0.001),  # Negative
            st.floats(min_value=1.001, max_value=1e10),     # > 1
            st.just(float('inf')),
            st.just(float('-inf')),
            st.just(float('nan')),
        )
    )
    @settings(max_examples=100)
    def test_invalid_match_thresholds(self, match_threshold):
        """Invalid match thresholds should raise ValueError."""
        with pytest.raises(ValueError, match="match_threshold must be between 0.0 and 1.0"):
            WorkflowInput(
                song_metadata=SongMetadata(title="Test", artist="Artist"),
                playlist_id="test_playlist",
                user_id="test_user",
                match_threshold=match_threshold,
            )

    @given(
        playlist_id=st.one_of(
            st.just(""),
            st.just(" " * 10),
            st.just("\t\n"),
        )
    )
    @settings(max_examples=50)
    def test_empty_playlist_id(self, playlist_id):
        """Empty playlist IDs should raise ValueError."""
        with pytest.raises(ValueError, match="playlist_id is required"):
            WorkflowInput(
                song_metadata=SongMetadata(title="Test", artist="Artist"),
                playlist_id=playlist_id,
                user_id="test_user",
            )


class TestWorkflowResultFuzz:
    """Property-based tests for WorkflowResult."""

    @given(
        success=st.booleans(),
        message=st.text(max_size=1000),
        spotify_track_id=st.one_of(st.none(), st.text(max_size=100)),
        spotify_track_uri=st.one_of(st.none(), st.text(max_size=200)),
        confidence_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        execution_time_seconds=st.floats(min_value=0.0, max_value=3600.0, allow_nan=False, allow_infinity=False),
        retry_count=st.integers(min_value=0, max_value=100),
        match_method=st.one_of(st.none(), st.sampled_from(["fuzzy", "ai", "isrc", "none"])),
    )
    @settings(max_examples=300)
    def test_workflow_result_creation(self, success, message, spotify_track_id,
                                       spotify_track_uri, confidence_score,
                                       execution_time_seconds, retry_count, match_method):
        """WorkflowResult should handle all valid combinations."""
        result = WorkflowResult(
            success=success,
            message=message,
            spotify_track_id=spotify_track_id,
            spotify_track_uri=spotify_track_uri,
            confidence_score=confidence_score,
            execution_time_seconds=execution_time_seconds,
            retry_count=retry_count,
            match_method=match_method,
        )
        assert result.success == success
        assert str(result)  # Should not crash

    @given(
        confidence_score=st.one_of(
            st.floats(min_value=-1.0, max_value=-0.001),
            st.floats(min_value=1.001, max_value=10.0),
        )
    )
    @settings(max_examples=50)
    def test_invalid_confidence_scores(self, confidence_score):
        """Confidence scores outside [0, 1] should be rejected or flagged."""
        # Currently no validation - potential BUG
        result = WorkflowResult(
            success=True,
            message="Test",
            confidence_score=confidence_score,
        )
        if confidence_score < 0.0 or confidence_score > 1.0:
            pytest.fail(f"Invalid confidence score accepted: {confidence_score}")


class TestWorkflowProgressFuzz:
    """Property-based tests for WorkflowProgress."""

    @given(
        current_step=st.text(min_size=1, max_size=100),
        steps_completed=st.integers(min_value=0, max_value=100),
        steps_total=st.integers(min_value=1, max_value=100),
        candidates_found=st.integers(min_value=0, max_value=1000),
        elapsed_seconds=st.floats(min_value=0.0, max_value=3600.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=300)
    def test_progress_creation(self, current_step, steps_completed, steps_total, candidates_found, elapsed_seconds):
        """WorkflowProgress should handle all valid combinations."""
        progress = WorkflowProgress(
            current_step=current_step,
            steps_completed=steps_completed,
            steps_total=steps_total,
            candidates_found=candidates_found,
            elapsed_seconds=elapsed_seconds,
        )
        assert str(progress)  # Should not crash
        assert progress.progress_percentage >= 0.0

    @given(
        steps_completed=st.integers(min_value=0, max_value=100),
        steps_total=st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=200)
    def test_progress_percentage_calculation(self, steps_completed, steps_total):
        """Progress percentage should always be between 0 and 100."""
        progress = WorkflowProgress(
            current_step="test",
            steps_completed=steps_completed,
            steps_total=steps_total,
            candidates_found=0,
            elapsed_seconds=0.0,
        )
        percentage = progress.progress_percentage
        assert 0.0 <= percentage <= 100.0

        # If steps_completed > steps_total, this is a BUG
        if steps_completed > steps_total:
            pytest.fail(f"steps_completed ({steps_completed}) > steps_total ({steps_total}) accepted")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
