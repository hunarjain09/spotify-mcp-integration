"""Property-based fuzz testing using Hypothesis for API models."""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from pydantic import ValidationError

from api.models import SyncSongRequest, WorkflowStatusResponse, WorkflowProgressInfo
from datetime import datetime


# Custom strategies for generating test data
spotify_id_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
    min_size=22,
    max_size=22
)

invalid_spotify_id_strategy = st.one_of(
    st.text(min_size=0, max_size=21),  # Too short
    st.text(min_size=23, max_size=100),  # Too long
    st.text(alphabet=st.characters(blacklist_categories=("Lu", "Ll", "Nd")), min_size=22, max_size=22),  # Invalid chars
)


class TestSyncSongRequestFuzz:
    """Property-based tests for SyncSongRequest."""

    @given(
        track_name=st.text(min_size=1, max_size=200),
        artist=st.text(min_size=1, max_size=200),
        album=st.one_of(st.none(), st.text(max_size=200)),
        playlist_id=spotify_id_strategy,
    )
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
    def test_valid_inputs_should_not_crash(self, track_name, artist, album, playlist_id):
        """Any valid input combination should not crash."""
        # Filter out empty/whitespace inputs which are invalid
        assume(track_name.strip() != "")
        assume(artist.strip() != "")

        try:
            request = SyncSongRequest(
                track_name=track_name,
                artist=artist,
                album=album,
                playlist_id=playlist_id,
            )
            # Should successfully create
            assert isinstance(request.track_name, str)
            assert isinstance(request.artist, str)
            assert len(request.playlist_id) == 22
        except ValidationError as e:
            # If validation fails, it should have a clear error message
            assert len(str(e)) > 0, "ValidationError should have a message"

    @given(
        track_name=st.text(),
        artist=st.text(),
        playlist_id=spotify_id_strategy,
    )
    @settings(max_examples=300)
    def test_empty_strings_rejected(self, track_name, artist, playlist_id):
        """Empty or whitespace-only strings should be rejected."""
        if track_name.strip() == "" or artist.strip() == "":
            with pytest.raises(ValidationError):
                SyncSongRequest(
                    track_name=track_name,
                    artist=artist,
                    playlist_id=playlist_id,
                )

    @given(
        playlist_id=invalid_spotify_id_strategy,
    )
    @settings(max_examples=200)
    def test_invalid_playlist_ids_rejected(self, playlist_id):
        """Invalid Spotify playlist IDs should be rejected."""
        with pytest.raises(ValidationError):
            SyncSongRequest(
                track_name="Test Song",
                artist="Test Artist",
                playlist_id=playlist_id,
            )

    @given(
        threshold=st.one_of(
            st.floats(min_value=-1e10, max_value=-0.001),  # Negative
            st.floats(min_value=1.001, max_value=1e10),    # > 1
            st.floats(allow_nan=True, allow_infinity=True),  # Special values
        )
    )
    @settings(max_examples=200)
    def test_invalid_thresholds_rejected(self, threshold):
        """Threshold values outside [0, 1] should be rejected."""
        assume(not (0.0 <= threshold <= 1.0))  # Only test invalid values

        with pytest.raises(ValidationError):
            SyncSongRequest(
                track_name="Test Song",
                artist="Test Artist",
                playlist_id="37i9dQZF1DXcBWIGoYBM5M",
                match_threshold=threshold,
            )

    @given(
        track_name=st.text(min_size=1, max_size=200),
        artist=st.text(min_size=1, max_size=200),
        playlist_id=spotify_id_strategy,
    )
    @settings(max_examples=200)
    def test_model_serialization_doesnt_crash(self, track_name, artist, playlist_id):
        """Model should always be serializable to JSON."""
        assume(track_name.strip() != "")
        assume(artist.strip() != "")

        try:
            request = SyncSongRequest(
                track_name=track_name,
                artist=artist,
                playlist_id=playlist_id,
            )
            # Should be able to serialize without crashing
            json_str = request.model_dump_json()
            assert isinstance(json_str, str)
            assert len(json_str) > 0
        except ValidationError:
            # Validation failures are OK, but no crashes
            pass

    @given(
        track_name=st.text(alphabet=st.characters(
            blacklist_categories=("Cc", "Cs"),  # Exclude control characters
            min_codepoint=0x0000,
            max_codepoint=0x10FFFF
        ), min_size=1, max_size=200),
        artist=st.text(alphabet=st.characters(
            blacklist_categories=("Cc", "Cs"),
            min_codepoint=0x0000,
            max_codepoint=0x10FFFF
        ), min_size=1, max_size=200),
        playlist_id=spotify_id_strategy,
    )
    @settings(max_examples=300)
    def test_unicode_handling(self, track_name, artist, playlist_id):
        """Should handle all Unicode characters properly."""
        assume(track_name.strip() != "")
        assume(artist.strip() != "")

        try:
            request = SyncSongRequest(
                track_name=track_name,
                artist=artist,
                playlist_id=playlist_id,
            )
            # Ensure we can serialize Unicode properly
            json_str = request.model_dump_json()
            # Should not have replacement characters
            assert "\ufffd" not in json_str, "Unicode replacement character found"
        except ValidationError:
            pass
        except UnicodeError as e:
            pytest.fail(f"Unicode handling failed: {e}")

    @given(
        track_name=st.text(min_size=1, max_size=10000),  # Very long
        artist=st.text(min_size=1, max_size=10000),
        playlist_id=spotify_id_strategy,
    )
    @settings(max_examples=100)
    def test_extremely_long_strings(self, track_name, artist, playlist_id):
        """Extremely long strings should either be rejected or truncated."""
        assume(track_name.strip() != "")
        assume(artist.strip() != "")

        # Should either reject or accept, but not crash
        try:
            request = SyncSongRequest(
                track_name=track_name,
                artist=artist,
                playlist_id=playlist_id,
            )
            # If accepted, should be within limits (200 chars per field spec)
            # But currently no max_length validation on the backend
            # This might be a BUG if lengths > 200 are accepted
            if len(track_name) > 200 or len(artist) > 200:
                pytest.fail(f"Strings longer than 200 chars accepted: track={len(track_name)}, artist={len(artist)}")
        except ValidationError:
            # Expected for very long strings
            pass

    @given(
        data=st.data(),
    )
    @settings(max_examples=200)
    def test_sql_injection_patterns(self, data):
        """SQL injection patterns should not cause issues."""
        sql_patterns = [
            "'; DROP TABLE songs;--",
            "' OR '1'='1",
            "admin'--",
            "1' UNION SELECT NULL--",
            "' OR 1=1--",
        ]

        sql_payload = data.draw(st.sampled_from(sql_patterns))
        playlist_id = data.draw(spotify_id_strategy)

        # These should be handled as normal strings
        request = SyncSongRequest(
            track_name=sql_payload,
            artist=sql_payload,
            playlist_id=playlist_id,
        )

        # Ensure they're stored as-is (not executed)
        assert "DROP" in request.track_name or "UNION" in request.track_name or "OR" in request.track_name

    @given(
        data=st.data(),
    )
    @settings(max_examples=200)
    def test_xss_patterns(self, data):
        """XSS patterns should not cause issues."""
        xss_patterns = [
            "<script>alert('XSS')</script>",
            "javascript:alert(1)",
            "<img src=x onerror=alert(1)>",
            "';alert(String.fromCharCode(88,83,83))//",
        ]

        xss_payload = data.draw(st.sampled_from(xss_patterns))
        playlist_id = data.draw(spotify_id_strategy)

        # Should store these as normal strings
        request = SyncSongRequest(
            track_name=xss_payload,
            artist="Test Artist",
            playlist_id=playlist_id,
        )

        # Ensure they're stored as-is (not sanitized, but that's OK for backend)
        assert "<" in request.track_name or "javascript:" in request.track_name or "alert" in request.track_name


class TestWorkflowStatusResponseFuzz:
    """Property-based tests for WorkflowStatusResponse."""

    @given(
        workflow_id=st.text(min_size=1, max_size=100),
        status=st.sampled_from(["running", "completed", "failed", "cancelled"]),
        started_at=st.datetimes(),
        completed_at=st.one_of(st.none(), st.datetimes()),
    )
    @settings(max_examples=300)
    def test_workflow_status_creation(self, workflow_id, status, started_at, completed_at):
        """WorkflowStatusResponse should handle various datetime combinations."""
        try:
            response = WorkflowStatusResponse(
                workflow_id=workflow_id,
                status=status,
                started_at=started_at,
                completed_at=completed_at,
            )
            assert response.workflow_id == workflow_id
            assert response.status == status
        except ValidationError:
            pass

    @given(
        workflow_id=st.text(min_size=1, max_size=100),
        status=st.text(),  # Any string, including invalid ones
        started_at=st.datetimes(),
    )
    @settings(max_examples=200)
    def test_invalid_status_values(self, workflow_id, status, started_at):
        """Should handle or reject invalid status values."""
        # Valid statuses are: running, completed, failed, cancelled
        valid_statuses = {"running", "completed", "failed", "cancelled"}

        try:
            response = WorkflowStatusResponse(
                workflow_id=workflow_id,
                status=status,
                started_at=started_at,
            )
            # If it accepts the status, it should be stored
            assert response.status == status
            # But there's no validation, so any string is accepted
            # This might be a BUG - should use Literal type
            if status not in valid_statuses:
                pytest.fail(f"Invalid status accepted: {status}")
        except ValidationError:
            # Expected for truly invalid input
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
