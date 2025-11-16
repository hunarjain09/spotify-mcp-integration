"""Main Temporal workflow for syncing Apple Music tracks to Spotify."""

from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from models.data_models import WorkflowInput, WorkflowResult, WorkflowProgress


@workflow.defn
class MusicSyncWorkflow:
    """Orchestrates song search, matching, and playlist addition."""

    def __init__(self):
        """Initialize workflow state."""
        self.current_step = "initializing"
        self.candidates_found = 0
        self.start_time = None

    @workflow.run
    async def run(self, input_data: WorkflowInput) -> WorkflowResult:
        """Main workflow execution.

        Args:
            input_data: Workflow input with song metadata and configuration

        Returns:
            WorkflowResult with success status and details
        """
        self.start_time = workflow.now()
        workflow.logger.info(
            f"Starting sync: {input_data.song_metadata.title} "
            f"by {input_data.song_metadata.artist}"
        )

        # Step 1: Search Spotify
        self.current_step = "searching"
        search_results = await workflow.execute_activity(
            "spotify-search",
            input_data.song_metadata,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self._get_search_retry_policy(),
            heartbeat_timeout=timedelta(seconds=10),
        )

        self.candidates_found = len(search_results)

        if not search_results:
            workflow.logger.info("No tracks found on Spotify")
            return WorkflowResult(
                success=False,
                message=f"No tracks found on Spotify for '{input_data.song_metadata.title}'",
                execution_time_seconds=self._get_elapsed_seconds(),
            )

        # Step 2: Fuzzy Matching
        self.current_step = "matching"
        match_result = await workflow.execute_activity(
            "fuzzy-match",
            args=[input_data.song_metadata, search_results, input_data.match_threshold],
            start_to_close_timeout=timedelta(seconds=15),
        )

        # Step 2.5: AI Disambiguation (if needed and enabled)
        if not match_result["is_match"] and input_data.use_ai_disambiguation:
            self.current_step = "ai_disambiguation"

            workflow.logger.info(
                f"Fuzzy match below threshold ({match_result['confidence']:.2f}), "
                "trying AI disambiguation"
            )

            ai_match_result = await workflow.execute_activity(
                "ai-disambiguate",
                args=[
                    input_data.song_metadata,
                    search_results[:5],  # Top 5 candidates only
                    match_result.get("all_scores", []),
                ],
                start_to_close_timeout=timedelta(minutes=2),  # LLM can be slow
                retry_policy=self._get_ai_retry_policy(),
            )

            if ai_match_result["is_match"]:
                workflow.logger.info(
                    f"AI found match: {ai_match_result.get('reasoning', 'No reason provided')}"
                )
                match_result = ai_match_result

        # Check if we have a match
        if not match_result["is_match"]:
            workflow.logger.info(
                f"No match found above threshold (best: {match_result['confidence']:.2f})"
            )
            return WorkflowResult(
                success=False,
                message=f"No match above threshold {input_data.match_threshold} "
                f"(best match: {match_result['confidence']:.2f})",
                confidence_score=match_result["confidence"],
                execution_time_seconds=self._get_elapsed_seconds(),
                match_method=match_result.get("match_method"),
            )

        matched_track = match_result["matched_track"]
        workflow.logger.info(
            f"Match found: '{matched_track.track_name}' by {matched_track.artist_name} "
            f"(confidence: {match_result['confidence']:.2f}, "
            f"method: {match_result.get('match_method')})"
        )

        # Step 3: Add to Playlist
        self.current_step = "adding"
        await workflow.execute_activity(
            "add-to-playlist",
            args=[matched_track.spotify_uri, input_data.playlist_id, input_data.user_id],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self._get_playlist_retry_policy(),
        )

        # Step 4: Verify Addition (optional, for reliability)
        self.current_step = "verifying"
        verification_result = await workflow.execute_activity(
            "verify-track-added",
            args=[matched_track.spotify_uri, input_data.playlist_id],
            start_to_close_timeout=timedelta(seconds=15),
        )

        verification_status = verification_result.get("is_added", False)
        if not verification_status:
            workflow.logger.warning("Track add verification failed, but operation may have succeeded")

        # Success!
        self.current_step = "completed"
        execution_time = self._get_elapsed_seconds()

        workflow.logger.info(
            f"Successfully synced '{matched_track.track_name}' in {execution_time:.2f}s"
        )

        return WorkflowResult(
            success=True,
            message=f"Successfully added '{matched_track.track_name}' by {matched_track.artist_name} to playlist",
            spotify_track_id=matched_track.track_id,
            spotify_track_uri=matched_track.spotify_uri,
            confidence_score=match_result["confidence"],
            execution_time_seconds=execution_time,
            match_method=match_result.get("match_method"),
        )

    @workflow.query
    def get_progress(self) -> WorkflowProgress:
        """Query for real-time progress (non-blocking).

        Returns:
            Current workflow progress information
        """
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
            current_step=self.current_step,
            steps_completed=steps_map.get(self.current_step, 0),
            steps_total=4,
            candidates_found=self.candidates_found,
            elapsed_seconds=self._get_elapsed_seconds(),
        )

    @workflow.signal
    async def request_cancellation(self):
        """Signal to cancel workflow gracefully."""
        workflow.logger.info("Cancellation requested by user")
        # Temporal will handle cancellation propagation to activities

    def _get_search_retry_policy(self) -> RetryPolicy:
        """Retry policy for Spotify search."""
        return RetryPolicy(
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=10),
            maximum_attempts=3,
            non_retryable_error_types=["InvalidCredentialsError", "MCPToolError"],
        )

    def _get_ai_retry_policy(self) -> RetryPolicy:
        """Retry policy for AI disambiguation."""
        return RetryPolicy(
            initial_interval=timedelta(seconds=2),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=3,
            non_retryable_error_types=["InvalidAPIKeyError"],
        )

    def _get_playlist_retry_policy(self) -> RetryPolicy:
        """Retry policy for playlist modification."""
        return RetryPolicy(
            initial_interval=timedelta(seconds=2),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=60),
            maximum_attempts=10,
            non_retryable_error_types=["PlaylistNotFoundError", "InsufficientScopeError"],
        )

    def _get_elapsed_seconds(self) -> float:
        """Calculate elapsed time since workflow start.

        Returns:
            Elapsed seconds as float
        """
        if not self.start_time:
            return 0.0
        return (workflow.now() - self.start_time).total_seconds()
