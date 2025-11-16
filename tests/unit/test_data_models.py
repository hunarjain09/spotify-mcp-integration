"""Unit tests for core data models."""

import pytest
from models.data_models import (
    SongMetadata,
    SpotifyTrackResult,
    MatchResult,
    WorkflowInput,
    WorkflowResult,
    WorkflowProgress,
    FuzzyMatchScore,
    ActivityRetryPolicy,
)


class TestSongMetadata:
    """Tests for SongMetadata dataclass."""

    def test_create_with_all_fields(self):
        """Test creating SongMetadata with all fields."""
        song = SongMetadata(
            title="Bohemian Rhapsody",
            artist="Queen",
            album="A Night at the Opera",
            duration_ms=354000,
            isrc="GBUM71029604",
        )

        assert song.title == "Bohemian Rhapsody"
        assert song.artist == "Queen"
        assert song.album == "A Night at the Opera"
        assert song.duration_ms == 354000
        assert song.isrc == "GBUM71029604"

    def test_create_with_minimal_fields(self):
        """Test creating SongMetadata with only required fields."""
        song = SongMetadata(title="Test Song", artist="Test Artist")

        assert song.title == "Test Song"
        assert song.artist == "Test Artist"
        assert song.album is None
        assert song.duration_ms is None
        assert song.isrc is None

    def test_to_search_query_with_album(self):
        """Test search query generation with album."""
        song = SongMetadata(
            title="Bohemian Rhapsody",
            artist="Queen",
            album="A Night at the Opera",
        )

        query = song.to_search_query()
        assert query == "track:Bohemian Rhapsody artist:Queen album:A Night at the Opera"

    def test_to_search_query_without_album(self):
        """Test search query generation without album."""
        song = SongMetadata(title="Imagine", artist="John Lennon")

        query = song.to_search_query()
        assert query == "track:Imagine artist:John Lennon"

    def test_str_representation(self):
        """Test string representation of SongMetadata."""
        song = SongMetadata(title="Bohemian Rhapsody", artist="Queen")

        assert str(song) == "'Bohemian Rhapsody' by Queen"

    def test_equality(self):
        """Test equality comparison of SongMetadata instances."""
        song1 = SongMetadata(title="Test", artist="Artist")
        song2 = SongMetadata(title="Test", artist="Artist")
        song3 = SongMetadata(title="Different", artist="Artist")

        assert song1 == song2
        assert song1 != song3


class TestSpotifyTrackResult:
    """Tests for SpotifyTrackResult dataclass."""

    def test_create_with_all_fields(self):
        """Test creating SpotifyTrackResult with all fields."""
        track = SpotifyTrackResult(
            track_id="7tFiyTwD0nx5a1eklYtX2J",
            track_name="Bohemian Rhapsody",
            artist_name="Queen",
            album_name="A Night at the Opera",
            spotify_uri="spotify:track:7tFiyTwD0nx5a1eklYtX2J",
            duration_ms=354000,
            popularity=92,
            release_date="1975-11-21",
            isrc="GBUM71029604",
        )

        assert track.track_id == "7tFiyTwD0nx5a1eklYtX2J"
        assert track.track_name == "Bohemian Rhapsody"
        assert track.artist_name == "Queen"
        assert track.album_name == "A Night at the Opera"
        assert track.spotify_uri == "spotify:track:7tFiyTwD0nx5a1eklYtX2J"
        assert track.duration_ms == 354000
        assert track.popularity == 92
        assert track.release_date == "1975-11-21"
        assert track.isrc == "GBUM71029604"

    def test_create_without_isrc(self):
        """Test creating SpotifyTrackResult without ISRC."""
        track = SpotifyTrackResult(
            track_id="test_id",
            track_name="Test Song",
            artist_name="Test Artist",
            album_name="Test Album",
            spotify_uri="spotify:track:test_id",
            duration_ms=200000,
            popularity=50,
            release_date="2020-01-01",
        )

        assert track.isrc is None

    def test_str_representation(self):
        """Test string representation of SpotifyTrackResult."""
        track = SpotifyTrackResult(
            track_id="test_id",
            track_name="Bohemian Rhapsody",
            artist_name="Queen",
            album_name="A Night at the Opera",
            spotify_uri="spotify:track:test_id",
            duration_ms=354000,
            popularity=92,
            release_date="1975-11-21",
        )

        assert str(track) == "'Bohemian Rhapsody' by Queen on A Night at the Opera"


class TestMatchResult:
    """Tests for MatchResult dataclass."""

    def test_successful_match(self, sample_spotify_track):
        """Test creating a successful match result."""
        result = MatchResult(
            is_match=True,
            confidence_score=0.95,
            matched_track=sample_spotify_track,
            match_method="fuzzy",
            candidates_considered=3,
        )

        assert result.is_match is True
        assert result.confidence_score == 0.95
        assert result.matched_track == sample_spotify_track
        assert result.match_method == "fuzzy"
        assert result.candidates_considered == 3
        assert result.reasoning is None

    def test_failed_match(self):
        """Test creating a failed match result."""
        result = MatchResult(
            is_match=False,
            confidence_score=0.65,
            matched_track=None,
            match_method="none",
            candidates_considered=5,
        )

        assert result.is_match is False
        assert result.confidence_score == 0.65
        assert result.matched_track is None
        assert result.match_method == "none"

    def test_ai_match_with_reasoning(self, sample_spotify_track):
        """Test AI match with reasoning."""
        result = MatchResult(
            is_match=True,
            confidence_score=0.88,
            matched_track=sample_spotify_track,
            match_method="ai",
            candidates_considered=4,
            reasoning="Track matches based on title, artist, and release year analysis.",
        )

        assert result.match_method == "ai"
        assert result.reasoning is not None
        assert "title" in result.reasoning

    def test_str_representation_match(self):
        """Test string representation for successful match."""
        result = MatchResult(
            is_match=True,
            confidence_score=0.95,
            matched_track=None,
            match_method="fuzzy",
            candidates_considered=3,
        )

        assert str(result) == "Match found (confidence: 0.95, method: fuzzy)"

    def test_str_representation_no_match(self):
        """Test string representation for failed match."""
        result = MatchResult(
            is_match=False,
            confidence_score=0.65,
            matched_track=None,
            match_method="none",
            candidates_considered=5,
        )

        assert str(result) == "No match (best: 0.65)"


class TestWorkflowInput:
    """Tests for WorkflowInput dataclass."""

    def test_create_with_valid_input(self, sample_song_metadata):
        """Test creating WorkflowInput with valid parameters."""
        workflow_input = WorkflowInput(
            song_metadata=sample_song_metadata,
            playlist_id="37i9dQZF1DXcBWIGoYBM5M",
            user_id="test_user_123",
            match_threshold=0.85,
            use_ai_disambiguation=True,
        )

        assert workflow_input.song_metadata == sample_song_metadata
        assert workflow_input.playlist_id == "37i9dQZF1DXcBWIGoYBM5M"
        assert workflow_input.user_id == "test_user_123"
        assert workflow_input.match_threshold == 0.85
        assert workflow_input.use_ai_disambiguation is True

    def test_default_values(self, sample_song_metadata):
        """Test default values for optional fields."""
        workflow_input = WorkflowInput(
            song_metadata=sample_song_metadata,
            playlist_id="37i9dQZF1DXcBWIGoYBM5M",
            user_id="test_user",
        )

        assert workflow_input.match_threshold == 0.85
        assert workflow_input.use_ai_disambiguation is True

    def test_invalid_match_threshold_high(self, sample_song_metadata):
        """Test that invalid high threshold raises ValueError."""
        with pytest.raises(ValueError, match="match_threshold must be between 0.0 and 1.0"):
            WorkflowInput(
                song_metadata=sample_song_metadata,
                playlist_id="test_playlist",
                user_id="test_user",
                match_threshold=1.5,
            )

    def test_invalid_match_threshold_low(self, sample_song_metadata):
        """Test that invalid low threshold raises ValueError."""
        with pytest.raises(ValueError, match="match_threshold must be between 0.0 and 1.0"):
            WorkflowInput(
                song_metadata=sample_song_metadata,
                playlist_id="test_playlist",
                user_id="test_user",
                match_threshold=-0.1,
            )

    def test_empty_playlist_id(self, sample_song_metadata):
        """Test that empty playlist_id raises ValueError."""
        with pytest.raises(ValueError, match="playlist_id is required"):
            WorkflowInput(
                song_metadata=sample_song_metadata,
                playlist_id="",
                user_id="test_user",
            )

    def test_boundary_threshold_values(self, sample_song_metadata):
        """Test boundary values for match_threshold."""
        # Test 0.0
        workflow_input_min = WorkflowInput(
            song_metadata=sample_song_metadata,
            playlist_id="test_playlist",
            user_id="test_user",
            match_threshold=0.0,
        )
        assert workflow_input_min.match_threshold == 0.0

        # Test 1.0
        workflow_input_max = WorkflowInput(
            song_metadata=sample_song_metadata,
            playlist_id="test_playlist",
            user_id="test_user",
            match_threshold=1.0,
        )
        assert workflow_input_max.match_threshold == 1.0


class TestWorkflowResult:
    """Tests for WorkflowResult dataclass."""

    def test_successful_result(self):
        """Test creating a successful workflow result."""
        result = WorkflowResult(
            success=True,
            message="Successfully added track to playlist",
            spotify_track_id="7tFiyTwD0nx5a1eklYtX2J",
            spotify_track_uri="spotify:track:7tFiyTwD0nx5a1eklYtX2J",
            confidence_score=0.95,
            execution_time_seconds=4.2,
            retry_count=0,
            match_method="fuzzy",
        )

        assert result.success is True
        assert "Successfully added" in result.message
        assert result.spotify_track_id == "7tFiyTwD0nx5a1eklYtX2J"
        assert result.confidence_score == 0.95
        assert result.execution_time_seconds == 4.2
        assert result.retry_count == 0
        assert result.match_method == "fuzzy"

    def test_failed_result(self):
        """Test creating a failed workflow result."""
        result = WorkflowResult(
            success=False,
            message="No matching track found",
            execution_time_seconds=3.5,
            retry_count=2,
        )

        assert result.success is False
        assert result.spotify_track_id is None
        assert result.spotify_track_uri is None
        assert result.confidence_score == 0.0
        assert result.retry_count == 2

    def test_str_representation_success(self):
        """Test string representation for successful result."""
        result = WorkflowResult(
            success=True,
            message="Track added",
            execution_time_seconds=4.2,
        )

        str_repr = str(result)
        assert "Success" in str_repr
        assert "Track added" in str_repr
        assert "4.2" in str_repr

    def test_str_representation_failure(self):
        """Test string representation for failed result."""
        result = WorkflowResult(
            success=False,
            message="Track not found",
            execution_time_seconds=3.0,
        )

        str_repr = str(result)
        assert "Failed" in str_repr
        assert "Track not found" in str_repr


class TestWorkflowProgress:
    """Tests for WorkflowProgress dataclass."""

    def test_create_progress(self):
        """Test creating workflow progress."""
        progress = WorkflowProgress(
            current_step="Searching Spotify",
            steps_completed=2,
            steps_total=5,
            candidates_found=3,
            elapsed_seconds=2.5,
        )

        assert progress.current_step == "Searching Spotify"
        assert progress.steps_completed == 2
        assert progress.steps_total == 5
        assert progress.candidates_found == 3
        assert progress.elapsed_seconds == 2.5

    def test_progress_percentage(self):
        """Test progress percentage calculation."""
        progress = WorkflowProgress(
            current_step="Processing",
            steps_completed=3,
            steps_total=10,
            candidates_found=0,
            elapsed_seconds=5.0,
        )

        assert progress.progress_percentage == 30.0

    def test_progress_percentage_zero_total(self):
        """Test progress percentage with zero total steps."""
        progress = WorkflowProgress(
            current_step="Starting",
            steps_completed=0,
            steps_total=0,
            candidates_found=0,
            elapsed_seconds=0.0,
        )

        assert progress.progress_percentage == 0.0

    def test_progress_percentage_complete(self):
        """Test progress percentage at completion."""
        progress = WorkflowProgress(
            current_step="Complete",
            steps_completed=5,
            steps_total=5,
            candidates_found=1,
            elapsed_seconds=10.0,
        )

        assert progress.progress_percentage == 100.0

    def test_str_representation(self):
        """Test string representation of progress."""
        progress = WorkflowProgress(
            current_step="Fuzzy Matching",
            steps_completed=3,
            steps_total=5,
            candidates_found=4,
            elapsed_seconds=3.2,
        )

        assert str(progress) == "Fuzzy Matching (3/5)"


class TestFuzzyMatchScore:
    """Tests for FuzzyMatchScore dataclass."""

    def test_create_match_score(self, sample_spotify_track):
        """Test creating fuzzy match score."""
        score = FuzzyMatchScore(
            track=sample_spotify_track,
            combined_score=0.92,
            title_score=0.95,
            artist_score=0.98,
            album_score=0.85,
            isrc_match=True,
        )

        assert score.track == sample_spotify_track
        assert score.combined_score == 0.92
        assert score.title_score == 0.95
        assert score.artist_score == 0.98
        assert score.album_score == 0.85
        assert score.isrc_match is True

    def test_match_score_without_isrc(self, sample_spotify_track):
        """Test match score without ISRC match."""
        score = FuzzyMatchScore(
            track=sample_spotify_track,
            combined_score=0.88,
            title_score=0.90,
            artist_score=0.95,
            album_score=0.80,
        )

        assert score.isrc_match is False

    def test_str_representation(self, sample_spotify_track):
        """Test string representation of match score."""
        score = FuzzyMatchScore(
            track=sample_spotify_track,
            combined_score=0.92,
            title_score=0.95,
            artist_score=0.98,
            album_score=0.85,
        )

        str_repr = str(score)
        assert "Bohemian Rhapsody" in str_repr
        assert "0.92" in str_repr


class TestActivityRetryPolicy:
    """Tests for ActivityRetryPolicy dataclass."""

    def test_create_retry_policy(self):
        """Test creating retry policy."""
        policy = ActivityRetryPolicy(
            initial_interval_seconds=1.0,
            max_interval_seconds=60.0,
            max_attempts=5,
            backoff_coefficient=2.0,
            non_retryable_error_types=["ValueError", "TypeError"],
        )

        assert policy.initial_interval_seconds == 1.0
        assert policy.max_interval_seconds == 60.0
        assert policy.max_attempts == 5
        assert policy.backoff_coefficient == 2.0
        assert policy.non_retryable_error_types == ["ValueError", "TypeError"]

    def test_default_backoff_coefficient(self):
        """Test default backoff coefficient."""
        policy = ActivityRetryPolicy(
            initial_interval_seconds=1.0,
            max_interval_seconds=60.0,
            max_attempts=3,
        )

        assert policy.backoff_coefficient == 2.0

    def test_default_non_retryable_errors(self):
        """Test default non-retryable errors list."""
        policy = ActivityRetryPolicy(
            initial_interval_seconds=1.0,
            max_interval_seconds=60.0,
            max_attempts=3,
        )

        assert policy.non_retryable_error_types == []

    def test_custom_backoff(self):
        """Test custom backoff coefficient."""
        policy = ActivityRetryPolicy(
            initial_interval_seconds=0.5,
            max_interval_seconds=30.0,
            max_attempts=10,
            backoff_coefficient=1.5,
        )

        assert policy.backoff_coefficient == 1.5
