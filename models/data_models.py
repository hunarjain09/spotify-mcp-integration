"""Core data models for the Apple Music to Spotify sync system."""

from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime


@dataclass
class SongMetadata:
    """Song information from Apple Music."""

    title: str
    artist: str
    album: Optional[str] = None
    duration_ms: Optional[int] = None
    isrc: Optional[str] = None  # International Standard Recording Code

    def to_search_query(self) -> str:
        """Convert to Spotify search query format.

        Returns:
            Formatted search query string
        """
        query = f"track:{self.title} artist:{self.artist}"
        if self.album:
            query += f" album:{self.album}"
        return query

    def __str__(self) -> str:
        return f"'{self.title}' by {self.artist}"


@dataclass
class SpotifyTrackResult:
    """Spotify search result."""

    track_id: str
    track_name: str
    artist_name: str
    album_name: str
    spotify_uri: str
    duration_ms: int
    popularity: int
    release_date: str
    isrc: Optional[str] = None

    def __str__(self) -> str:
        return f"'{self.track_name}' by {self.artist_name} on {self.album_name}"


@dataclass
class MatchResult:
    """Fuzzy matching result."""

    is_match: bool
    confidence_score: float  # 0.0 - 1.0
    matched_track: Optional[SpotifyTrackResult]
    match_method: str  # "fuzzy", "ai", "isrc", "none"
    candidates_considered: int
    reasoning: Optional[str] = None  # AI reasoning if used

    def __str__(self) -> str:
        if self.is_match:
            return f"Match found (confidence: {self.confidence_score:.2f}, method: {self.match_method})"
        return f"No match (best: {self.confidence_score:.2f})"


@dataclass
class WorkflowInput:
    """Input to MusicSyncWorkflow."""

    song_metadata: SongMetadata
    playlist_id: str
    user_id: str
    match_threshold: float = 0.85
    use_ai_disambiguation: bool = True

    def __post_init__(self):
        """Validate input parameters."""
        if not 0.0 <= self.match_threshold <= 1.0:
            raise ValueError("match_threshold must be between 0.0 and 1.0")
        if not self.playlist_id:
            raise ValueError("playlist_id is required")


@dataclass
class WorkflowResult:
    """Output from MusicSyncWorkflow."""

    success: bool
    message: str
    spotify_track_id: Optional[str] = None
    spotify_track_uri: Optional[str] = None
    confidence_score: float = 0.0
    execution_time_seconds: float = 0.0
    retry_count: int = 0
    match_method: Optional[str] = None

    def __str__(self) -> str:
        status = "✓ Success" if self.success else "✗ Failed"
        return f"{status}: {self.message} ({self.execution_time_seconds:.2f}s)"


@dataclass
class WorkflowProgress:
    """Real-time progress information for a running workflow."""

    current_step: str
    steps_completed: int
    steps_total: int
    candidates_found: int
    elapsed_seconds: float

    @property
    def progress_percentage(self) -> float:
        """Calculate progress as percentage."""
        if self.steps_total == 0:
            return 0.0
        return (self.steps_completed / self.steps_total) * 100

    def __str__(self) -> str:
        return f"{self.current_step} ({self.steps_completed}/{self.steps_total})"


@dataclass
class FuzzyMatchScore:
    """Individual fuzzy matching score details."""

    track: SpotifyTrackResult
    combined_score: float
    title_score: float
    artist_score: float
    album_score: float
    isrc_match: bool = False

    def __str__(self) -> str:
        return f"{self.track.track_name} - Score: {self.combined_score:.2f}"


@dataclass
class ActivityRetryPolicy:
    """Retry policy configuration for activities."""

    initial_interval_seconds: float
    max_interval_seconds: float
    max_attempts: int
    backoff_coefficient: float = 2.0
    non_retryable_error_types: List[str] = None

    def __post_init__(self):
        if self.non_retryable_error_types is None:
            self.non_retryable_error_types = []
