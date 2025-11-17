# Temporal Integration Enhancement Plan
## Inspired by Temporal OpenAI Agents Pattern

**Date**: 2025-11-17
**Project**: Spotify MCP Integration
**Current Branch**: `claude/plan-temporal-integration-01GPQcWwu4ibtFLzAbEXNBh5`

---

## Executive Summary

This plan outlines enhancements to wrap the Spotify MCP integration with Temporal for improved durability, inspired by the [Temporal OpenAI Agents samples](https://github.com/temporalio/samples-python/tree/main/openai_agents).

**Current State**: Already has a solid Temporal foundation with workflows, activities, and retry policies.

**Goal**: Enhance durability, observability, and reliability using patterns from the openai_agents examples, particularly:
- Multi-agent orchestration patterns
- Enhanced error handling and compensation
- Improved observability with search attributes
- Dead letter queues for failed workflows
- Agent-as-tool patterns for composability

---

## Table of Contents

1. [Current Architecture Analysis](#current-architecture-analysis)
2. [OpenAI Agents Pattern Lessons](#openai-agents-pattern-lessons)
3. [Enhancement Opportunities](#enhancement-opportunities)
4. [Detailed Enhancement Plans](#detailed-enhancement-plans)
5. [Implementation Roadmap](#implementation-roadmap)
6. [Code Examples](#code-examples)
7. [Testing Strategy](#testing-strategy)
8. [Metrics and Monitoring](#metrics-and-monitoring)

---

## Current Architecture Analysis

### What's Already Implemented ✅

The codebase has an **excellent Temporal foundation**:

```
Temporal Components:
├── Workflow: MusicSyncWorkflow (workflows/music_sync_workflow.py)
│   ├── 5 Activities orchestrated sequentially
│   ├── Retry policies per activity type
│   ├── Query handler for progress tracking
│   └── Signal handler for cancellation (stub)
│
├── Activities:
│   ├── spotify-search (activities/spotify_search.py)
│   ├── fuzzy-match (activities/fuzzy_matcher.py)
│   ├── ai-disambiguate (activities/ai_disambiguator.py)
│   ├── add-to-playlist (activities/playlist_manager.py)
│   └── verify-track-added (activities/playlist_manager.py)
│
└── Worker: MusicSyncWorker (workers/music_sync_worker.py)
    ├── Thread pool executor for activities
    ├── Concurrent workflow/activity limits
    └── TLS support for Temporal Cloud
```

### Workflow Execution Flow

```
User Request (Apple Music Track)
    ↓
[1. Search Spotify] → 30s timeout, 3 retries
    ↓ (candidates)
[2. Fuzzy Match] → 15s timeout, deterministic
    ↓ (match result)
[3. AI Disambiguation?] → 2min timeout, 3 retries (if fuzzy fails)
    ↓ (best match)
[4. Add to Playlist] → 30s timeout, 10 retries
    ↓ (spotify uri)
[5. Verify Addition] → 15s timeout
    ↓
Success Result
```

**Durability Guarantee**: If the server crashes at any step, Temporal resumes from the last completed activity.

### Current Retry Policies

| Activity | Max Attempts | Initial Interval | Max Interval | Non-Retryable Errors |
|----------|--------------|------------------|--------------|---------------------|
| Search | 3 | 1s | 10s | InvalidCredentialsError, MCPToolError |
| AI Disambiguation | 3 | 2s | 30s | InvalidAPIKeyError |
| Add to Playlist | 10 | 2s | 60s | PlaylistNotFoundError, InsufficientScopeError |

**Backoff Strategy**: Exponential with coefficient 2.0 (1s → 2s → 4s → 8s...)

### Gaps Identified

| Gap | Impact | Temporal Feature Needed |
|-----|--------|------------------------|
| **No search attributes** | Can't filter workflows by user/playlist/track in UI | `workflow.upsert_search_attributes()` |
| **Failed workflows disappear** | No dead letter queue for exhausted retries | Failure handler + DLQ task queue |
| **Cancellation not implemented** | Signal handler exists but does nothing | Compensation activity on cancellation |
| **No batch operations** | One track at a time, no atomicity | Parent-child workflow pattern |
| **Limited observability** | No metrics export | Prometheus/OpenTelemetry integration |
| **Single-purpose workflow** | Can't reuse components | Activity composition patterns |

---

## OpenAI Agents Pattern Lessons

### Key Patterns from temporalio/samples-python/openai_agents

The OpenAI Agents examples demonstrate several patterns highly relevant to this project:

#### 1. **Agent-as-Workflow Pattern**

**Pattern**: Wrap AI agents in Temporal workflows for durability.

```python
# From openai_agents examples
@workflow.defn
class AgentWorkflow:
    @workflow.run
    async def run(self, task: str) -> str:
        # Agent execution wrapped in workflow
        result = await workflow.execute_activity(
            run_agent,
            task,
            start_to_close_timeout=timedelta(minutes=10),
        )
        return result
```

**Application to Spotify Sync**:
- ✅ Already implemented: AI disambiguator is an activity
- 🔄 Could enhance: Make each step a specialized "agent" (search agent, match agent, etc.)

#### 2. **Multi-Agent Orchestration**

**Pattern**: Coordinate multiple specialized agents (planner, searcher, writer, analyst).

```python
# Research bot pattern: multiple specialized agents
@workflow.defn
class ResearchWorkflow:
    async def run(self, query: str) -> Report:
        # Agent 1: Plan research
        plan = await workflow.execute_activity(planner_agent, query)

        # Agent 2: Search for info
        facts = await workflow.execute_activity(searcher_agent, plan)

        # Agent 3: Analyze findings
        analysis = await workflow.execute_activity(analyst_agent, facts)

        # Agent 4: Write report
        report = await workflow.execute_activity(writer_agent, analysis)

        return report
```

**Application to Spotify Sync**:
```python
# Enhanced workflow with specialized agents
@workflow.defn
class EnhancedMusicSyncWorkflow:
    async def run(self, input_data: WorkflowInput) -> WorkflowResult:
        # Agent 1: Search strategy agent (determines best search approach)
        search_strategy = await workflow.execute_activity(
            "search-strategy-agent",
            input_data.song_metadata
        )

        # Agent 2: Search execution agent
        candidates = await workflow.execute_activity(
            "spotify-search",
            search_strategy
        )

        # Agent 3: Matching strategy agent (fuzzy vs AI vs hybrid)
        match_strategy = await workflow.execute_activity(
            "match-strategy-agent",
            args=[input_data.song_metadata, candidates]
        )

        # Agent 4: Matching execution agent
        matched_track = await workflow.execute_activity(
            "execute-match",
            match_strategy
        )

        # Agent 5: Playlist modification agent
        result = await workflow.execute_activity(
            "add-to-playlist",
            matched_track
        )

        return result
```

#### 3. **Agent Handoffs**

**Pattern**: Escalate between agents based on context (e.g., customer service tier 1 → tier 2).

**Application to Spotify Sync**:
- Fuzzy match → AI disambiguation (already implemented)
- Could add: "Manual review queue" for ambiguous matches

#### 4. **Tool Integration via MCP**

**Pattern**: Agents use tools via Model Context Protocol.

**Application to Spotify Sync**:
- ✅ Already using MCP for Spotify API
- Could enhance: Expose workflow activities as MCP tools for other agents

#### 5. **Durable Execution**

**Pattern**: All agent state persisted in Temporal.

**Application to Spotify Sync**:
- ✅ Already durable
- Could enhance: Add search attributes for better querying

#### 6. **Error Handling & Retries**

**Pattern**: Retry policies tuned per agent type.

**Application to Spotify Sync**:
- ✅ Already has excellent retry policies
- Could enhance: Circuit breaker for systemic failures

---

## Enhancement Opportunities

Based on the OpenAI Agents pattern and current gaps, here are prioritized enhancements:

### Priority 1: Observability & Operations (High Impact, Low Effort)

#### E1.1: Search Attributes for Workflow Filtering

**Problem**: Can't filter workflows in Temporal UI by user, playlist, or track name.

**Solution**: Add search attributes.

**Impact**:
- Support can find all syncs for a user
- Debugging becomes much easier
- Can identify problematic playlists/tracks

**Effort**: 1-2 hours

**Code Example**: [See Section: Code Examples](#e11-search-attributes)

---

#### E1.2: Dead Letter Queue for Failed Workflows

**Problem**: Workflows that exhaust retries disappear into logs.

**Solution**: Route failed workflows to a DLQ task queue for manual intervention.

**Impact**:
- Can retry failed syncs after fixing root cause
- Operational visibility into failure patterns
- No lost user requests

**Effort**: 2-3 hours

**Code Example**: [See Section: Code Examples](#e12-dead-letter-queue)

---

#### E1.3: Enhanced Progress Queries with Search Attributes

**Problem**: Progress query only shows current step, not context (which track, which user).

**Solution**: Include search attributes in progress query response.

**Impact**: Better debugging and support

**Effort**: 30 minutes

---

### Priority 2: Reliability & Error Handling (High Impact, Medium Effort)

#### E2.1: Graceful Cancellation with Compensation

**Problem**: Cancellation signal exists but does nothing. Track might already be in playlist.

**Solution**: Implement compensation activity to remove track on cancellation.

**Impact**:
- Consistent state even on cancellation
- Better UX (user can cancel without orphaned tracks)

**Effort**: 2-3 hours

**Code Example**: [See Section: Code Examples](#e21-graceful-cancellation)

---

#### E2.2: Circuit Breaker for Systemic Failures

**Problem**: If Spotify API is down, workflows keep retrying individually.

**Solution**: Implement circuit breaker pattern using workflow state.

**Impact**:
- Prevent thundering herd
- Faster failure detection
- Better resource utilization

**Effort**: 3-4 hours

**Code Example**: [See Section: Code Examples](#e22-circuit-breaker)

---

### Priority 3: Advanced Features (Medium Impact, Higher Effort)

#### E3.1: Batch Sync Workflow (Parent-Child Pattern)

**Problem**: iOS Shortcuts sends one track at a time.

**Solution**: Create parent workflow that spawns child workflows for each track.

**Impact**:
- Atomicity for bulk operations
- Progress tracking for multiple tracks
- Better performance (parallelization)

**Effort**: 4-6 hours

**Code Example**: [See Section: Code Examples](#e31-batch-sync-workflow)

---

#### E3.2: Multi-Agent Architecture (Search Strategy, Match Strategy)

**Problem**: Workflow is monolithic. Hard to experiment with different strategies.

**Solution**: Split into strategy agents (inspired by openai_agents pattern).

**Impact**:
- Easier to A/B test different approaches
- Can swap strategies without changing workflow
- More modular and testable

**Effort**: 6-8 hours

**Code Example**: [See Section: Code Examples](#e32-multi-agent-architecture)

---

#### E3.3: Metrics Export to Prometheus

**Problem**: No quantitative observability (success rate, latency percentiles, error breakdown).

**Solution**: Export Temporal workflow metrics to Prometheus.

**Impact**:
- Production monitoring
- Alerting on degradation
- Capacity planning

**Effort**: 3-4 hours

**Metrics to Export**:
- `temporal_sync_duration_seconds` (histogram)
- `temporal_sync_success_total` (counter)
- `temporal_sync_failure_total` (counter by error type)
- `temporal_activity_duration_seconds` (histogram by activity name)
- `temporal_retry_count` (histogram)
- `temporal_rate_limit_hits_total` (counter)

---

#### E3.4: Activity Versioning for Safe Rollouts

**Problem**: Changing activity code risks breaking in-flight workflows.

**Solution**: Implement activity versioning with backward compatibility.

**Impact**:
- Safe canary deployments
- A/B testing
- Gradual rollouts

**Effort**: 4-6 hours

---

### Priority 4: Advanced Patterns (Future Exploration)

#### E4.1: Scheduled/Cron Syncs

**Problem**: Users have to manually trigger syncs.

**Solution**: Use Temporal schedules for periodic playlist syncing.

**Effort**: 2-3 hours

---

#### E4.2: Manual Review Queue Workflow

**Problem**: Ambiguous matches (confidence 40-60%) have no human-in-the-loop option.

**Solution**: Child workflow that pauses for manual approval.

**Effort**: 4-5 hours

---

## Detailed Enhancement Plans

### E1.1: Search Attributes

**Files to Modify**:
- `workflows/music_sync_workflow.py`
- `workers/music_sync_worker.py`

**Implementation Steps**:

1. **Define search attributes in workflow**:

```python
# In workflows/music_sync_workflow.py
from temporalio import workflow
from temporalio.common import SearchAttributeKey, TypedSearchAttributes

# Define search attribute keys
USER_ID_ATTR = SearchAttributeKey.for_keyword("UserId")
PLAYLIST_ID_ATTR = SearchAttributeKey.for_keyword("PlaylistId")
TRACK_NAME_ATTR = SearchAttributeKey.for_keyword("TrackName")
ARTIST_NAME_ATTR = SearchAttributeKey.for_keyword("ArtistName")

@workflow.defn
class MusicSyncWorkflow:
    @workflow.run
    async def run(self, input_data: WorkflowInput) -> WorkflowResult:
        # Set search attributes at workflow start
        workflow.upsert_search_attributes({
            USER_ID_ATTR: [input_data.user_id],
            PLAYLIST_ID_ATTR: [input_data.playlist_id],
            TRACK_NAME_ATTR: [input_data.song_metadata.title],
            ARTIST_NAME_ATTR: [input_data.song_metadata.artist],
        })

        # ... rest of workflow
```

2. **Update Temporal server with search attributes** (one-time setup):

```bash
# Using tctl for local Temporal
tctl admin cluster add-search-attributes \
    --name UserId --type Keyword \
    --name PlaylistId --type Keyword \
    --name TrackName --type Keyword \
    --name ArtistName --type Keyword

# Or via Temporal Cloud UI
```

3. **Query workflows in Temporal UI**:

```sql
-- Find all syncs for a user
UserId = "user_123"

-- Find all syncs for a specific track
TrackName = "Bohemian Rhapsody" AND ArtistName = "Queen"

-- Find all syncs to a playlist
PlaylistId = "playlist_abc"
```

**Testing**:
- Start workflow with test data
- Query Temporal UI with search attributes
- Verify filtering works

**Rollout Plan**:
- Deploy to dev environment first
- Validate search attributes appear in Temporal UI
- Deploy to production

---

### E1.2: Dead Letter Queue

**Files to Modify**:
- `workflows/music_sync_workflow.py` (add failure handler)
- `workers/music_sync_worker.py` (add DLQ worker)
- `api/app.py` (add DLQ retry endpoint)

**Implementation Steps**:

1. **Create DLQ workflow**:

```python
# In workflows/dlq_workflow.py
from temporalio import workflow
from datetime import timedelta

@workflow.defn
class DeadLetterQueueWorkflow:
    """Workflow for handling failed music syncs."""

    @workflow.run
    async def run(self, failed_workflow_input: WorkflowInput, error_details: dict) -> None:
        """Store failed workflow for manual retry.

        Args:
            failed_workflow_input: Original workflow input that failed
            error_details: Error information from failed workflow
        """
        workflow.logger.error(
            f"Workflow failed after max retries: {failed_workflow_input.song_metadata.title} "
            f"Error: {error_details.get('error_type')}"
        )

        # Store in DLQ (could be database, S3, etc.)
        await workflow.execute_activity(
            "store-in-dlq",
            args=[failed_workflow_input, error_details],
            start_to_close_timeout=timedelta(seconds=30),
        )

        # Optionally: send alert to operations team
        await workflow.execute_activity(
            "send-alert",
            args=[f"Music sync DLQ: {failed_workflow_input.song_metadata.title}"],
            start_to_close_timeout=timedelta(seconds=10),
        )
```

2. **Add failure handler to main workflow**:

```python
# In workflows/music_sync_workflow.py
@workflow.defn
class MusicSyncWorkflow:
    @workflow.run
    async def run(self, input_data: WorkflowInput) -> WorkflowResult:
        try:
            # ... existing workflow logic
            pass
        except Exception as e:
            # Check if this is a final failure (after all retries)
            workflow_info = workflow.info()

            # Start DLQ workflow
            await workflow.start_child_workflow(
                DeadLetterQueueWorkflow.run,
                args=[
                    input_data,
                    {
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "workflow_id": workflow_info.workflow_id,
                        "run_id": workflow_info.run_id,
                    }
                ],
                id=f"dlq-{workflow_info.workflow_id}",
                task_queue="music-sync-dlq",
            )

            # Re-raise to maintain failure status
            raise
```

3. **Create DLQ retry API endpoint**:

```python
# In api/app.py
@app.post("/api/v1/dlq/retry/{workflow_id}")
async def retry_dlq_workflow(workflow_id: str):
    """Retry a failed workflow from DLQ."""
    # Retrieve original input from DLQ storage
    original_input = await retrieve_from_dlq(workflow_id)

    # Start new workflow with same input
    result = await start_music_sync(original_input)

    return {"status": "retried", "new_workflow_id": result.workflow_id}
```

**Testing**:
- Simulate workflow failure (e.g., invalid credentials)
- Verify DLQ workflow starts
- Check DLQ storage for failed workflow
- Test retry endpoint

---

### E2.1: Graceful Cancellation

**Files to Modify**:
- `workflows/music_sync_workflow.py`
- `activities/playlist_manager.py` (add remove activity)

**Implementation Steps**:

1. **Add compensation activity**:

```python
# In activities/playlist_manager.py
@activity.defn(name="remove-from-playlist")
async def remove_track_from_playlist(
    track_uri: str,
    playlist_id: str,
    user_id: Optional[str] = None,
) -> Dict:
    """Remove a track from a Spotify playlist (compensation activity).

    Args:
        track_uri: Spotify URI of the track to remove
        playlist_id: Target playlist ID
        user_id: User ID for authentication

    Returns:
        Dictionary with removal result
    """
    activity.logger.info(f"Removing {track_uri} from playlist {playlist_id}")

    # Use MCP client to remove track
    mcp = await get_mcp_client()

    result = await mcp.call_tool(
        "remove_from_playlist",
        {
            "playlist_id": playlist_id,
            "track_uris": [track_uri],
        }
    )

    return {"removed": True, "track_uri": track_uri}
```

2. **Implement cancellation handler in workflow**:

```python
# In workflows/music_sync_workflow.py
@workflow.defn
class MusicSyncWorkflow:
    def __init__(self):
        self.current_step = "initializing"
        self.added_track_uri = None  # Track what we added
        self.playlist_id = None
        self.user_id = None

    @workflow.run
    async def run(self, input_data: WorkflowInput) -> WorkflowResult:
        self.playlist_id = input_data.playlist_id
        self.user_id = input_data.user_id

        try:
            # ... existing workflow logic

            # After adding to playlist
            self.current_step = "adding"
            await workflow.execute_activity(
                "add-to-playlist",
                args=[matched_track.spotify_uri, input_data.playlist_id, input_data.user_id],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self._get_playlist_retry_policy(),
            )

            # Store what we added for potential compensation
            self.added_track_uri = matched_track.spotify_uri

            # ... rest of workflow

        except asyncio.CancelledError:
            # Workflow was cancelled
            workflow.logger.info("Workflow cancelled, running compensation")

            # If we already added the track, remove it
            if self.added_track_uri:
                await workflow.execute_activity(
                    "remove-from-playlist",
                    args=[self.added_track_uri, self.playlist_id, self.user_id],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(maximum_attempts=3),
                )
                workflow.logger.info(f"Compensated: removed {self.added_track_uri}")

            raise  # Re-raise to maintain cancelled status

    @workflow.signal
    async def request_cancellation(self):
        """Signal to cancel workflow gracefully."""
        workflow.logger.info("Cancellation requested by user")
        # Raise cancellation will trigger CancelledError in run()
        raise asyncio.CancelledError()
```

3. **Add cancellation API endpoint**:

```python
# In api/app.py
@app.post("/api/v1/sync/{workflow_id}/cancel")
async def cancel_sync(workflow_id: str):
    """Cancel a running sync workflow."""
    handle = client.get_workflow_handle(workflow_id)

    # Send cancellation signal
    await handle.signal(MusicSyncWorkflow.request_cancellation)

    # Wait for workflow to complete cancellation
    try:
        await handle.result()
    except WorkflowFailureError as e:
        if isinstance(e.cause, CancelledError):
            return {"status": "cancelled", "compensated": True}
        raise
```

**Testing**:
- Start workflow
- Wait until track is added (query progress)
- Send cancellation signal
- Verify track is removed from playlist
- Check workflow status is "cancelled"

---

### E3.1: Batch Sync Workflow

**Files to Create**:
- `workflows/batch_sync_workflow.py`
- `models/data_models.py` (add BatchWorkflowInput)

**Implementation**:

```python
# In workflows/batch_sync_workflow.py
from temporalio import workflow
from typing import List
from models.data_models import WorkflowInput, BatchWorkflowResult
from workflows.music_sync_workflow import MusicSyncWorkflow

@workflow.defn
class BatchMusicSyncWorkflow:
    """Parent workflow for syncing multiple tracks."""

    @workflow.run
    async def run(self, tracks: List[WorkflowInput]) -> BatchWorkflowResult:
        """Sync multiple tracks in parallel.

        Args:
            tracks: List of track sync inputs

        Returns:
            Batch result with individual track results
        """
        workflow.logger.info(f"Starting batch sync for {len(tracks)} tracks")

        # Start child workflow for each track
        child_handles = []
        for idx, track_input in enumerate(tracks):
            handle = await workflow.start_child_workflow(
                MusicSyncWorkflow.run,
                track_input,
                id=f"{workflow.info().workflow_id}-track-{idx}",
                task_queue="music-sync",
            )
            child_handles.append(handle)

        # Wait for all to complete
        results = []
        for handle in child_handles:
            try:
                result = await handle
                results.append({"success": True, "result": result})
            except Exception as e:
                results.append({"success": False, "error": str(e)})

        # Aggregate results
        success_count = sum(1 for r in results if r["success"])

        return BatchWorkflowResult(
            total_tracks=len(tracks),
            successful_syncs=success_count,
            failed_syncs=len(tracks) - success_count,
            individual_results=results,
        )

    @workflow.query
    def get_batch_progress(self) -> dict:
        """Query batch progress."""
        # Could track progress of child workflows
        pass
```

**API Endpoint**:

```python
# In api/app.py
@app.post("/api/v1/sync/batch")
async def batch_sync_tracks(request: BatchSyncRequest):
    """Sync multiple tracks atomically."""
    workflow_id = f"batch-sync-{uuid.uuid4()}"

    handle = await client.start_workflow(
        BatchMusicSyncWorkflow.run,
        request.tracks,
        id=workflow_id,
        task_queue="music-sync",
    )

    return {"workflow_id": workflow_id, "track_count": len(request.tracks)}
```

---

### E3.2: Multi-Agent Architecture

**Files to Create**:
- `activities/search_strategy_agent.py`
- `activities/match_strategy_agent.py`
- `workflows/enhanced_music_sync_workflow.py`

**Implementation**:

```python
# In activities/search_strategy_agent.py
from temporalio import activity
from anthropic import AsyncAnthropic

@activity.defn(name="search-strategy-agent")
async def determine_search_strategy(song_metadata: SongMetadata) -> dict:
    """AI agent that determines the best search strategy.

    Analyzes the song metadata and decides:
    - Which fields to prioritize (title, artist, album, ISRC)
    - Whether to use exact or fuzzy search
    - What filters to apply (year, popularity, etc.)

    Returns:
        Dictionary with search strategy
    """
    activity.logger.info(f"Determining search strategy for: {song_metadata.title}")

    # Use Claude to analyze metadata quality
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    prompt = f"""Analyze this song metadata and recommend a search strategy:

Song: "{song_metadata.title}"
Artist: "{song_metadata.artist}"
Album: "{song_metadata.album}"
ISRC: "{song_metadata.isrc}"
Year: {song_metadata.year}

Based on the completeness and uniqueness of this data, recommend:
1. Search query (what to search for)
2. Filters to apply (year, album, etc.)
3. Confidence that we'll find the right match

Return JSON with: query, filters, expected_confidence"""

    response = await client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )

    # Parse AI response
    strategy = parse_search_strategy(response.content[0].text)

    activity.logger.info(f"Strategy: {strategy}")
    return strategy


# In activities/match_strategy_agent.py
@activity.defn(name="match-strategy-agent")
async def determine_match_strategy(
    song_metadata: SongMetadata,
    candidates: List[SpotifyTrackResult]
) -> dict:
    """AI agent that determines the best matching approach.

    Analyzes candidates and decides:
    - Use fuzzy matching only
    - Use AI disambiguation
    - Use hybrid approach

    Returns:
        Dictionary with match strategy
    """
    activity.logger.info(
        f"Determining match strategy for {len(candidates)} candidates"
    )

    # Analyze candidate diversity
    if len(candidates) == 1:
        return {"strategy": "single_match", "use_ai": False}

    # Check if candidates are very similar (same artist, similar names)
    similarity_score = calculate_candidate_similarity(candidates)

    if similarity_score > 0.9:
        return {"strategy": "fuzzy_only", "use_ai": False}
    elif similarity_score < 0.5:
        return {"strategy": "ai_required", "use_ai": True}
    else:
        return {"strategy": "hybrid", "use_ai": True}


# In workflows/enhanced_music_sync_workflow.py
@workflow.defn
class EnhancedMusicSyncWorkflow:
    """Enhanced workflow with multi-agent architecture."""

    @workflow.run
    async def run(self, input_data: WorkflowInput) -> WorkflowResult:
        # Agent 1: Determine search strategy
        search_strategy = await workflow.execute_activity(
            "search-strategy-agent",
            input_data.song_metadata,
            start_to_close_timeout=timedelta(seconds=30),
        )

        # Agent 2: Execute search with strategy
        candidates = await workflow.execute_activity(
            "spotify-search",
            args=[input_data.song_metadata, search_strategy],
            start_to_close_timeout=timedelta(seconds=30),
        )

        # Agent 3: Determine match strategy
        match_strategy = await workflow.execute_activity(
            "match-strategy-agent",
            args=[input_data.song_metadata, candidates],
            start_to_close_timeout=timedelta(seconds=15),
        )

        # Agent 4: Execute matching based on strategy
        if match_strategy["use_ai"]:
            match_result = await workflow.execute_activity(
                "ai-disambiguate",
                args=[input_data.song_metadata, candidates, []],
                start_to_close_timeout=timedelta(minutes=2),
            )
        else:
            match_result = await workflow.execute_activity(
                "fuzzy-match",
                args=[input_data.song_metadata, candidates, input_data.match_threshold],
                start_to_close_timeout=timedelta(seconds=15),
            )

        # ... rest of workflow
```

**Benefits of Multi-Agent Architecture**:
- Each agent is independently testable
- Can A/B test different strategies
- Easier to add new strategies
- Better observability (see which strategy was used)

---

## Implementation Roadmap

### Phase 1: Observability Foundation (Week 1-2)

**Goal**: Make workflows observable and debuggable.

| Task | Effort | Priority | Dependencies |
|------|--------|----------|--------------|
| Add search attributes | 2 hours | P0 | None |
| Implement DLQ pattern | 3 hours | P0 | None |
| Enhanced progress queries | 1 hour | P1 | Search attributes |
| Update worker config | 1 hour | P1 | None |

**Deliverables**:
- ✅ Can filter workflows by user/playlist/track in UI
- ✅ Failed workflows go to DLQ for manual retry
- ✅ Progress queries include context

**Testing Checklist**:
- [ ] Search attributes appear in Temporal UI
- [ ] Can filter by UserId, PlaylistId, TrackName
- [ ] Failed workflows appear in DLQ task queue
- [ ] DLQ retry endpoint works

---

### Phase 2: Reliability Enhancements (Week 3-4)

**Goal**: Improve error handling and recovery.

| Task | Effort | Priority | Dependencies |
|------|--------|----------|--------------|
| Graceful cancellation | 3 hours | P0 | None |
| Circuit breaker pattern | 4 hours | P1 | None |
| Enhanced retry policies | 2 hours | P1 | None |
| Activity heartbeats | 2 hours | P2 | None |

**Deliverables**:
- ✅ Cancellation compensates (removes added tracks)
- ✅ Circuit breaker prevents thundering herd
- ✅ Better retry strategies for rate limits

**Testing Checklist**:
- [ ] Cancellation removes track from playlist
- [ ] Circuit breaker opens after N failures
- [ ] Circuit breaker closes after cooldown
- [ ] Rate-limit retries use Retry-After header

---

### Phase 3: Advanced Features (Week 5-8)

**Goal**: Enable batch operations and multi-agent patterns.

| Task | Effort | Priority | Dependencies |
|------|--------|----------|--------------|
| Batch sync workflow | 6 hours | P1 | None |
| Search strategy agent | 4 hours | P2 | None |
| Match strategy agent | 4 hours | P2 | Search strategy agent |
| Enhanced workflow | 3 hours | P2 | Strategy agents |
| Metrics export | 4 hours | P1 | None |

**Deliverables**:
- ✅ Can sync multiple tracks atomically
- ✅ AI determines search/match strategies
- ✅ Prometheus metrics for monitoring

**Testing Checklist**:
- [ ] Batch sync handles 10+ tracks
- [ ] Batch progress tracking works
- [ ] Strategy agents make reasonable decisions
- [ ] Metrics exported to Prometheus

---

### Phase 4: Production Readiness (Week 9-10)

**Goal**: Prepare for production deployment.

| Task | Effort | Priority | Dependencies |
|------|--------|----------|--------------|
| Activity versioning | 5 hours | P1 | None |
| Chaos engineering tests | 4 hours | P1 | None |
| Runbook documentation | 3 hours | P0 | All phases |
| Load testing | 4 hours | P0 | All phases |
| Monitoring dashboard | 3 hours | P0 | Metrics export |

**Deliverables**:
- ✅ Safe deployment process
- ✅ Tested failure scenarios
- ✅ Operations runbook
- ✅ Monitoring dashboard

**Testing Checklist**:
- [ ] Can deploy new activity version without breaking workflows
- [ ] Tested network partition scenarios
- [ ] Tested Temporal server restart
- [ ] Tested high load (1000 concurrent workflows)
- [ ] Grafana dashboard shows key metrics

---

## Code Examples

### E1.1: Search Attributes

**File**: `workflows/music_sync_workflow.py`

```python
from temporalio import workflow
from temporalio.common import SearchAttributeKey

# Define search attribute keys (module level)
USER_ID_ATTR = SearchAttributeKey.for_keyword("UserId")
PLAYLIST_ID_ATTR = SearchAttributeKey.for_keyword("PlaylistId")
TRACK_NAME_ATTR = SearchAttributeKey.for_keyword("TrackName")
ARTIST_NAME_ATTR = SearchAttributeKey.for_keyword("ArtistName")
MATCH_METHOD_ATTR = SearchAttributeKey.for_keyword("MatchMethod")

@workflow.defn
class MusicSyncWorkflow:
    @workflow.run
    async def run(self, input_data: WorkflowInput) -> WorkflowResult:
        self.start_time = workflow.now()

        # ENHANCEMENT: Set search attributes immediately
        workflow.upsert_search_attributes({
            USER_ID_ATTR: [input_data.user_id] if input_data.user_id else [],
            PLAYLIST_ID_ATTR: [input_data.playlist_id],
            TRACK_NAME_ATTR: [input_data.song_metadata.title],
            ARTIST_NAME_ATTR: [input_data.song_metadata.artist],
        })

        workflow.logger.info(
            f"Starting sync with search attributes: "
            f"user={input_data.user_id}, playlist={input_data.playlist_id}, "
            f"track={input_data.song_metadata.title}"
        )

        # ... existing workflow logic

        # ENHANCEMENT: Update match method when determined
        if match_result["is_match"]:
            workflow.upsert_search_attributes({
                MATCH_METHOD_ATTR: [match_result.get("match_method", "unknown")]
            })

        # ... rest of workflow
```

**Temporal Server Setup** (one-time):

```bash
# For local dev server
tctl admin cluster add-search-attributes \
    --name UserId --type Keyword \
    --name PlaylistId --type Keyword \
    --name TrackName --type Keyword \
    --name ArtistName --type Keyword \
    --name MatchMethod --type Keyword

# For Temporal Cloud, use web UI:
# Settings → Namespaces → [your-namespace] → Search Attributes → Add
```

**Querying in Temporal UI**:

```sql
-- All syncs for a user
UserId = "user_12345"

-- Failed syncs for a specific track
TrackName = "Bohemian Rhapsody" AND WorkflowStatus = "Failed"

-- All AI-matched syncs
MatchMethod = "ai"

-- Syncs to a specific playlist in last 24h
PlaylistId = "playlist_abc" AND StartTime > "2025-11-16T00:00:00Z"
```

---

### E1.2: Dead Letter Queue

**File**: `workflows/dlq_workflow.py` (new file)

```python
"""Dead Letter Queue workflow for failed music syncs."""

from temporalio import workflow
from datetime import timedelta
from typing import Dict, Any

with workflow.unsafe.imports_passed_through():
    from models.data_models import WorkflowInput


@workflow.defn
class DeadLetterQueueWorkflow:
    """Workflow for handling failed music syncs after max retries."""

    @workflow.run
    async def run(
        self,
        failed_input: WorkflowInput,
        error_details: Dict[str, Any]
    ) -> None:
        """Process a failed workflow.

        Args:
            failed_input: Original workflow input that failed
            error_details: Error information
        """
        workflow.logger.error(
            f"DLQ: Processing failed sync for '{failed_input.song_metadata.title}' "
            f"Error: {error_details.get('error_type')}: {error_details.get('error_message')}"
        )

        # Store in DLQ storage (database, S3, etc.)
        await workflow.execute_activity(
            "store-in-dlq",
            args=[{
                "original_workflow_id": error_details.get("workflow_id"),
                "run_id": error_details.get("run_id"),
                "input_data": failed_input.model_dump(),
                "error_type": error_details.get("error_type"),
                "error_message": error_details.get("error_message"),
                "failed_at": workflow.now().isoformat(),
            }],
            start_to_close_timeout=timedelta(seconds=30),
        )

        # Send alert to operations
        await workflow.execute_activity(
            "send-alert",
            args=[{
                "title": "Music Sync Failed (DLQ)",
                "message": (
                    f"Track: {failed_input.song_metadata.title} by {failed_input.song_metadata.artist}\n"
                    f"Error: {error_details.get('error_type')}\n"
                    f"Workflow ID: {error_details.get('workflow_id')}"
                ),
                "severity": "warning",
            }],
            start_to_close_timeout=timedelta(seconds=10),
        )

        workflow.logger.info("DLQ processing complete")
```

**File**: `activities/dlq_storage.py` (new file)

```python
"""Activities for DLQ storage and retrieval."""

from temporalio import activity
from typing import Dict, Any
import json
from datetime import datetime

@activity.defn(name="store-in-dlq")
async def store_in_dlq(dlq_entry: Dict[str, Any]) -> None:
    """Store failed workflow in DLQ.

    This could be a database, S3, Redis, etc.
    For this example, we'll use a simple JSON file.
    """
    activity.logger.info(f"Storing in DLQ: {dlq_entry['original_workflow_id']}")

    # In production, use a proper database
    # For now, append to a JSON file
    dlq_file = "/var/lib/music-sync/dlq.jsonl"

    with open(dlq_file, "a") as f:
        f.write(json.dumps(dlq_entry) + "\n")

    activity.logger.info("DLQ entry stored")


@activity.defn(name="send-alert")
async def send_alert(alert_data: Dict[str, Any]) -> None:
    """Send alert to operations team.

    Could be Slack, PagerDuty, email, etc.
    """
    activity.logger.warning(
        f"ALERT: {alert_data['title']} - {alert_data['message']}"
    )

    # In production, integrate with alerting system
    # Example: Slack webhook
    # await send_slack_message(alert_data['message'])
```

**File**: `workflows/music_sync_workflow.py` (modified)

```python
@workflow.defn
class MusicSyncWorkflow:
    @workflow.run
    async def run(self, input_data: WorkflowInput) -> WorkflowResult:
        try:
            # ... existing workflow logic
            pass

        except Exception as e:
            # ENHANCEMENT: Check if this is a final failure
            workflow_info = workflow.info()
            attempt = workflow_info.attempt

            # If we've exhausted retries, send to DLQ
            if attempt >= 3:  # Or check specific error types
                workflow.logger.error(
                    f"Workflow failed after {attempt} attempts, sending to DLQ"
                )

                # Start DLQ workflow (fire-and-forget)
                await workflow.start_child_workflow(
                    "DeadLetterQueueWorkflow",
                    args=[
                        input_data,
                        {
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                            "workflow_id": workflow_info.workflow_id,
                            "run_id": workflow_info.run_id,
                            "attempt": attempt,
                        }
                    ],
                    id=f"dlq-{workflow_info.workflow_id}",
                    task_queue="music-sync-dlq",
                )

            # Re-raise to maintain failure status
            raise
```

**File**: `workers/dlq_worker.py` (new file)

```python
"""Worker for DLQ task queue."""

import asyncio
from temporalio.client import Client
from temporalio.worker import Worker
from workflows.dlq_workflow import DeadLetterQueueWorkflow
from activities.dlq_storage import store_in_dlq, send_alert
from config.settings import settings

async def run_dlq_worker():
    """Run DLQ worker on separate task queue."""
    client = await Client.connect(settings.temporal_host)

    worker = Worker(
        client,
        task_queue="music-sync-dlq",
        workflows=[DeadLetterQueueWorkflow],
        activities=[store_in_dlq, send_alert],
    )

    print("DLQ Worker started on task queue: music-sync-dlq")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(run_dlq_worker())
```

**API Endpoint for DLQ Retry**:

```python
# In api/app.py
@app.get("/api/v1/dlq/list")
async def list_dlq_entries():
    """List all DLQ entries."""
    # Read from DLQ storage
    entries = []
    with open("/var/lib/music-sync/dlq.jsonl", "r") as f:
        for line in f:
            entries.append(json.loads(line))

    return {"total": len(entries), "entries": entries}


@app.post("/api/v1/dlq/retry/{original_workflow_id}")
async def retry_dlq_workflow(original_workflow_id: str):
    """Retry a failed workflow from DLQ."""
    # Find DLQ entry
    dlq_entry = find_dlq_entry(original_workflow_id)

    if not dlq_entry:
        raise HTTPException(status_code=404, detail="DLQ entry not found")

    # Parse original input
    original_input = WorkflowInput(**dlq_entry["input_data"])

    # Start new workflow
    new_workflow_id = f"retry-{original_workflow_id}-{uuid.uuid4()}"
    handle = await client.start_workflow(
        MusicSyncWorkflow.run,
        original_input,
        id=new_workflow_id,
        task_queue="music-sync",
    )

    return {
        "status": "retried",
        "original_workflow_id": original_workflow_id,
        "new_workflow_id": new_workflow_id
    }
```

---

### E2.1: Graceful Cancellation

**File**: `activities/playlist_manager.py` (add compensation activity)

```python
@activity.defn(name="remove-from-playlist")
async def remove_track_from_playlist(
    track_uri: str,
    playlist_id: str,
    user_id: Optional[str] = None,
) -> Dict:
    """Remove a track from playlist (compensation activity).

    This is called when a workflow is cancelled after adding a track.

    Args:
        track_uri: Spotify URI to remove
        playlist_id: Playlist ID
        user_id: User ID

    Returns:
        Removal result
    """
    activity.logger.info(
        f"Compensation: Removing {track_uri} from playlist {playlist_id}"
    )

    mcp_client = await get_mcp_client()

    # Call Spotify API to remove track
    result = await mcp_client.call_tool(
        "remove_from_playlist",
        {
            "playlist_id": playlist_id,
            "track_uris": [track_uri],
        }
    )

    activity.logger.info("Track removed successfully")

    return {
        "removed": True,
        "track_uri": track_uri,
        "playlist_id": playlist_id,
    }
```

**File**: `workflows/music_sync_workflow.py` (enhanced cancellation)

```python
@workflow.defn
class MusicSyncWorkflow:
    def __init__(self):
        self.current_step = "initializing"
        self.candidates_found = 0
        self.start_time = None

        # ENHANCEMENT: Track state for compensation
        self.added_track_uri: Optional[str] = None
        self.playlist_id: Optional[str] = None
        self.user_id: Optional[str] = None

    @workflow.run
    async def run(self, input_data: WorkflowInput) -> WorkflowResult:
        self.start_time = workflow.now()
        self.playlist_id = input_data.playlist_id
        self.user_id = input_data.user_id

        try:
            # ... existing search and matching logic

            # Step 3: Add to Playlist
            self.current_step = "adding"
            await workflow.execute_activity(
                "add-to-playlist",
                args=[matched_track.spotify_uri, input_data.playlist_id, input_data.user_id],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self._get_playlist_retry_policy(),
            )

            # ENHANCEMENT: Track what we added
            self.added_track_uri = matched_track.spotify_uri
            workflow.logger.info(f"Track added, URI stored for potential compensation: {self.added_track_uri}")

            # Step 4: Verify Addition
            self.current_step = "verifying"
            verification_result = await workflow.execute_activity(
                "verify-track-added",
                args=[matched_track.spotify_uri, input_data.playlist_id],
                start_to_close_timeout=timedelta(seconds=15),
            )

            # ... success logic

        except asyncio.CancelledError:
            # ENHANCEMENT: Handle cancellation gracefully
            workflow.logger.warning("Workflow cancellation detected")

            # Run compensation if we added the track
            if self.added_track_uri:
                workflow.logger.info(
                    f"Running compensation: removing {self.added_track_uri} "
                    f"from playlist {self.playlist_id}"
                )

                try:
                    await workflow.execute_activity(
                        "remove-from-playlist",
                        args=[self.added_track_uri, self.playlist_id, self.user_id],
                        start_to_close_timeout=timedelta(seconds=30),
                        retry_policy=RetryPolicy(
                            maximum_attempts=5,  # Retry compensation aggressively
                            initial_interval=timedelta(seconds=1),
                            backoff_coefficient=2.0,
                        ),
                    )
                    workflow.logger.info("Compensation successful: track removed")
                except Exception as comp_error:
                    # Log but don't fail cancellation
                    workflow.logger.error(
                        f"Compensation failed: {comp_error}. "
                        f"Manual cleanup may be required for {self.added_track_uri}"
                    )
            else:
                workflow.logger.info("No compensation needed: track not yet added")

            # Re-raise to maintain cancelled status
            raise

    @workflow.signal
    async def request_cancellation(self):
        """Signal to gracefully cancel workflow.

        When this signal is received, the workflow will:
        1. Stop current execution
        2. Run compensation (remove added track if any)
        3. Complete with cancelled status
        """
        workflow.logger.info("Cancellation signal received")
        # Temporal will propagate cancellation to the run method
```

**API Endpoint for Cancellation**:

```python
# In api/app.py
from temporalio.client import WorkflowFailureError
from temporalio.exceptions import CancelledError

@app.post("/api/v1/sync/{workflow_id}/cancel")
async def cancel_music_sync(workflow_id: str):
    """Cancel a running music sync workflow.

    If the track was already added to the playlist, it will be removed.
    """
    try:
        # Get workflow handle
        handle = client.get_workflow_handle(workflow_id)

        # Send cancellation request
        await handle.cancel()

        # Wait for workflow to complete cancellation
        try:
            result = await handle.result()
            # If it completed successfully before cancellation
            return {
                "status": "completed",
                "message": "Workflow completed before cancellation",
                "result": result
            }
        except WorkflowFailureError as e:
            if isinstance(e.cause, CancelledError):
                return {
                    "status": "cancelled",
                    "message": "Workflow cancelled and compensated (track removed if added)",
                    "compensated": True
                }
            else:
                # Other failure
                raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel workflow: {str(e)}"
        )


@app.get("/api/v1/sync/{workflow_id}/cancellable")
async def check_if_cancellable(workflow_id: str):
    """Check if a workflow can still be cancelled meaningfully."""
    handle = client.get_workflow_handle(workflow_id)

    # Query current progress
    progress = await handle.query(MusicSyncWorkflow.get_progress)

    # Cancellation makes sense if we haven't completed
    can_cancel = progress.current_step != "completed"
    will_compensate = progress.current_step in ["adding", "verifying", "completed"]

    return {
        "can_cancel": can_cancel,
        "will_compensate": will_compensate,
        "current_step": progress.current_step
    }
```

---

### E2.2: Circuit Breaker

**File**: `utils/circuit_breaker.py` (new file)

```python
"""Circuit breaker pattern for Temporal activities."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional
import asyncio

@dataclass
class CircuitState:
    """State of a circuit breaker."""
    is_open: bool = False
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    opened_at: Optional[datetime] = None


class CircuitBreaker:
    """Circuit breaker for preventing cascading failures.

    Pattern:
    - CLOSED: Normal operation, failures increment counter
    - OPEN: After threshold failures, reject requests immediately
    - HALF_OPEN: After cooldown, try one request
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        cooldown_seconds: int = 60,
    ):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.circuits: Dict[str, CircuitState] = {}

    def record_success(self, circuit_name: str):
        """Record successful call."""
        if circuit_name in self.circuits:
            # Reset circuit on success
            self.circuits[circuit_name] = CircuitState()

    def record_failure(self, circuit_name: str):
        """Record failed call."""
        if circuit_name not in self.circuits:
            self.circuits[circuit_name] = CircuitState()

        state = self.circuits[circuit_name]
        state.failure_count += 1
        state.last_failure_time = datetime.now()

        # Open circuit if threshold exceeded
        if state.failure_count >= self.failure_threshold:
            state.is_open = True
            state.opened_at = datetime.now()

    def is_open(self, circuit_name: str) -> bool:
        """Check if circuit is open."""
        if circuit_name not in self.circuits:
            return False

        state = self.circuits[circuit_name]

        # If circuit is open, check if cooldown period has passed
        if state.is_open and state.opened_at:
            cooldown_elapsed = (
                datetime.now() - state.opened_at
            ).total_seconds() >= self.cooldown_seconds

            if cooldown_elapsed:
                # Move to half-open state (try one request)
                state.is_open = False
                state.failure_count = 0
                return False

            return True

        return False

    def get_state(self, circuit_name: str) -> CircuitState:
        """Get circuit state."""
        return self.circuits.get(circuit_name, CircuitState())


# Global circuit breaker instance
circuit_breaker = CircuitBreaker(
    failure_threshold=5,  # Open after 5 failures
    cooldown_seconds=60,   # Try again after 1 minute
)
```

**File**: `activities/spotify_search.py` (with circuit breaker)

```python
from utils.circuit_breaker import circuit_breaker
from temporalio.exceptions import ApplicationError

@activity.defn(name="spotify-search")
async def search_spotify(
    song_metadata: SongMetadata,
) -> List[SpotifyTrackResult]:
    """Search Spotify with circuit breaker protection."""

    circuit_name = "spotify-api"

    # ENHANCEMENT: Check circuit breaker
    if circuit_breaker.is_open(circuit_name):
        activity.logger.warning(
            f"Circuit breaker OPEN for {circuit_name}, rejecting request"
        )
        state = circuit_breaker.get_state(circuit_name)
        raise ApplicationError(
            f"Circuit breaker open for Spotify API "
            f"(failures: {state.failure_count}, "
            f"opened: {state.opened_at})",
            type="CircuitBreakerOpen",
            non_retryable=True,  # Don't retry when circuit is open
        )

    activity.logger.info(f"Searching Spotify for: {song_metadata}")

    try:
        mcp_client = await get_mcp_client()

        # Build search query
        query = build_search_query(song_metadata)

        # Call Spotify API via MCP
        result = await mcp_client.call_tool(
            "search_tracks",
            {"query": query, "limit": 10}
        )

        # Parse results
        tracks = parse_spotify_results(result)

        # ENHANCEMENT: Record success
        circuit_breaker.record_success(circuit_name)

        activity.logger.info(f"Found {len(tracks)} tracks")
        return tracks

    except Exception as e:
        # ENHANCEMENT: Record failure
        circuit_breaker.record_failure(circuit_name)

        state = circuit_breaker.get_state(circuit_name)
        activity.logger.error(
            f"Spotify search failed (failure #{state.failure_count}): {e}"
        )

        # Check if circuit just opened
        if circuit_breaker.is_open(circuit_name):
            activity.logger.error(
                f"Circuit breaker OPENED for {circuit_name} "
                f"after {state.failure_count} failures"
            )

        raise
```

**File**: `api/app.py` (circuit breaker status endpoint)

```python
from utils.circuit_breaker import circuit_breaker

@app.get("/api/v1/health/circuit-breakers")
async def get_circuit_breaker_status():
    """Get status of all circuit breakers."""
    circuits = {}

    for circuit_name, state in circuit_breaker.circuits.items():
        circuits[circuit_name] = {
            "is_open": state.is_open,
            "failure_count": state.failure_count,
            "last_failure": state.last_failure_time.isoformat() if state.last_failure_time else None,
            "opened_at": state.opened_at.isoformat() if state.opened_at else None,
        }

    return {"circuits": circuits}


@app.post("/api/v1/health/circuit-breakers/{circuit_name}/reset")
async def reset_circuit_breaker(circuit_name: str):
    """Manually reset a circuit breaker."""
    if circuit_name in circuit_breaker.circuits:
        circuit_breaker.circuits[circuit_name] = CircuitState()
        return {"status": "reset", "circuit": circuit_name}

    raise HTTPException(status_code=404, detail="Circuit not found")
```

---

## Testing Strategy

### Unit Tests

```python
# tests/unit/test_circuit_breaker.py
import pytest
from utils.circuit_breaker import CircuitBreaker, CircuitState
from datetime import datetime, timedelta

def test_circuit_breaker_opens_after_threshold():
    cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=60)

    # Record failures
    cb.record_failure("test-circuit")
    assert not cb.is_open("test-circuit")

    cb.record_failure("test-circuit")
    assert not cb.is_open("test-circuit")

    cb.record_failure("test-circuit")
    assert cb.is_open("test-circuit")  # Should open after 3 failures


def test_circuit_breaker_closes_after_cooldown():
    cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=1)

    # Open circuit
    cb.record_failure("test-circuit")
    cb.record_failure("test-circuit")
    assert cb.is_open("test-circuit")

    # Wait for cooldown
    import time
    time.sleep(2)

    # Should close
    assert not cb.is_open("test-circuit")


def test_circuit_breaker_resets_on_success():
    cb = CircuitBreaker(failure_threshold=3)

    cb.record_failure("test-circuit")
    cb.record_failure("test-circuit")
    assert cb.get_state("test-circuit").failure_count == 2

    cb.record_success("test-circuit")
    assert cb.get_state("test-circuit").failure_count == 0
```

### Integration Tests

```python
# tests/integration/test_cancellation.py
import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from workflows.music_sync_workflow import MusicSyncWorkflow
from activities import *

@pytest.mark.asyncio
async def test_cancellation_compensates():
    """Test that cancellation removes added track."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        # Setup worker
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[MusicSyncWorkflow],
            activities=[
                search_spotify,
                fuzzy_match_tracks,
                add_track_to_playlist,
                remove_track_from_playlist,
            ],
        ):
            # Start workflow
            handle = await env.client.start_workflow(
                MusicSyncWorkflow.run,
                test_input,
                id="test-cancel",
                task_queue="test-queue",
            )

            # Wait for track to be added
            await asyncio.sleep(5)

            # Cancel workflow
            await handle.cancel()

            # Verify compensation ran
            with pytest.raises(WorkflowFailureError) as exc_info:
                await handle.result()

            assert isinstance(exc_info.value.cause, CancelledError)

            # Verify track was removed (check activity logs or mock)
            # ... verification logic
```

### Chaos Tests

```python
# tests/chaos/test_failure_scenarios.py
import pytest
from temporalio.testing import WorkflowEnvironment

@pytest.mark.asyncio
async def test_workflow_survives_worker_restart():
    """Test that workflow resumes after worker restart."""
    # Start workflow
    # Kill worker mid-execution
    # Restart worker
    # Verify workflow completes
    pass


@pytest.mark.asyncio
async def test_network_partition_recovery():
    """Test recovery from network partition."""
    # Start workflow
    # Simulate network partition to Spotify API
    # Verify retries with backoff
    # Restore network
    # Verify workflow completes
    pass
```

---

## Metrics and Monitoring

### Prometheus Metrics to Export

```python
# utils/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Workflow metrics
workflow_duration = Histogram(
    'temporal_workflow_duration_seconds',
    'Workflow execution duration',
    ['workflow_type', 'status']
)

workflow_count = Counter(
    'temporal_workflow_total',
    'Total workflows started',
    ['workflow_type']
)

workflow_success = Counter(
    'temporal_workflow_success_total',
    'Successful workflows',
    ['workflow_type', 'match_method']
)

workflow_failure = Counter(
    'temporal_workflow_failure_total',
    'Failed workflows',
    ['workflow_type', 'error_type']
)

# Activity metrics
activity_duration = Histogram(
    'temporal_activity_duration_seconds',
    'Activity execution duration',
    ['activity_name', 'status']
)

activity_retry_count = Histogram(
    'temporal_activity_retry_count',
    'Number of retries per activity',
    ['activity_name']
)

# Circuit breaker metrics
circuit_breaker_state = Gauge(
    'circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open)',
    ['circuit_name']
)

circuit_breaker_failures = Counter(
    'circuit_breaker_failures_total',
    'Circuit breaker failures',
    ['circuit_name']
)

# Rate limiting metrics
rate_limit_hits = Counter(
    'spotify_rate_limit_hits_total',
    'Number of rate limit hits',
    ['endpoint']
)
```

### Grafana Dashboard Queries

```promql
# Success rate (last hour)
rate(temporal_workflow_success_total[1h])
/
rate(temporal_workflow_total[1h])

# P95 latency
histogram_quantile(0.95,
    rate(temporal_workflow_duration_seconds_bucket[5m])
)

# Error rate by type
rate(temporal_workflow_failure_total[5m])

# Activity retry rate
rate(temporal_activity_retry_count_sum[5m])
/
rate(temporal_activity_retry_count_count[5m])

# Circuit breaker status
circuit_breaker_state{circuit_name="spotify-api"}
```

---

## Conclusion

This plan provides a comprehensive roadmap for enhancing the Spotify MCP integration with Temporal durability patterns inspired by the OpenAI Agents samples.

**Key Takeaways**:

1. **Current State**: Already has a solid Temporal foundation
2. **Quick Wins**: Search attributes and DLQ (Phase 1) provide immediate value
3. **Reliability**: Cancellation and circuit breaker (Phase 2) improve robustness
4. **Advanced**: Multi-agent and batch operations (Phase 3) enable new capabilities
5. **Production**: Proper monitoring and versioning (Phase 4) ensure safe deployments

**Next Steps**:

1. Review this plan with the team
2. Prioritize phases based on business needs
3. Start with Phase 1 (observability) as foundation
4. Iterate and gather feedback

**Estimated Total Effort**: 8-10 weeks for all phases

---

**Document Version**: 1.0
**Last Updated**: 2025-11-17
**Author**: Claude Code
**Status**: Ready for Review
