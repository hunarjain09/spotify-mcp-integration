# Temporal Schedules + MCP Integration: The Complete Picture
## How Timing and MCP Quirks Interact

**Date**: 2025-11-17
**Focus**: Understanding the interaction between Temporal schedules/timing and MCP server lifecycles

---

## Executive Summary

Temporal **schedules** and **MCP servers** have unique behaviors that **interact in surprising ways**. This document explores these interactions and how they affect the Spotify MCP integration.

**Key Insight**: Scheduled workflows with MCP servers require special consideration for:
- MCP server lifecycle management
- Connection pooling and reuse
- Timing of OAuth token refresh
- Handling scheduled vs manual triggers

---

## Temporal Schedules: Core Concepts

### What Are Temporal Schedules?

Temporal Schedules allow you to **automate workflow execution** on a recurring basis.

**Example use cases for Spotify sync**:
- Daily playlist sync from Apple Music
- Hourly discovery playlist updates
- Weekly cleanup of duplicate tracks

### Key Timing Behaviors

#### 1. **Schedules Don't Affect Running Workflows**

From Temporal docs:
> "Deleting a Schedule does not affect any Workflows started by the Schedule."

**What this means**:
```
Schedule: Sync playlist daily at 2 AM
  ↓
Day 1, 2 AM: Workflow 1 starts
  ↓
[Schedule deleted at 3 AM]
  ↓
Workflow 1: Still running! ✅
Day 2, 2 AM: No new workflow ❌ (schedule deleted)
```

**Implication for MCP**: If you delete a schedule, in-flight workflows still have MCP connections.

---

#### 2. **Overlap Policies Matter**

Temporal schedules have **overlap policies** that determine what happens when a new scheduled run triggers while the previous one is still running.

**Overlap policies**:
- `SKIP`: Don't start if previous run still running
- `BUFFER_ONE`: Queue one additional run
- `BUFFER_ALL`: Queue all runs
- `CANCEL_OTHER`: Cancel previous run, start new one
- `TERMINATE_OTHER`: Terminate previous run, start new one
- `ALLOW_ALL`: Start concurrent runs

**MCP impact**:

```python
# Scenario: 5-minute schedule with 10-minute workflow

# SKIP policy
2:00 PM: Workflow 1 starts (uses MCP connection 1)
2:05 PM: Workflow 2 skipped (Workflow 1 still running)
2:10 PM: Workflow 1 completes (MCP connection 1 closed)
2:10 PM: Workflow 3 starts (uses MCP connection 2)

# ALLOW_ALL policy
2:00 PM: Workflow 1 starts (uses MCP connection 1)
2:05 PM: Workflow 2 starts (uses MCP connection 2) ← Two MCP servers!
2:10 PM: Workflow 1 completes
2:10 PM: Workflow 3 starts (uses MCP connection 3) ← Three MCP servers!
```

**Critical quirk**: `ALLOW_ALL` can spawn **multiple MCP servers** on the same worker!

---

#### 3. **Manual Triggers Respect Overlap Policy**

From Temporal docs:
> "When triggering immediate actions, the system automatically applies the schedule's overlap policy by default."

**What this means**:

```python
# Schedule with SKIP overlap policy
Schedule: Daily at 2 AM

# Manual trigger at 1 PM
trigger_workflow_manually()  # ← Also respects SKIP policy!

# If scheduled 2 AM workflow still running...
trigger_workflow_manually()  # ← SKIPPED!
```

**For MCP**: Manual triggers can't bypass overlap policy to force MCP usage.

---

## MCP + Schedules: Interaction Quirks

### Quirk #1: MCP Server Lifecycle vs Schedule Lifecycle

**Problem**: MCP servers are tied to **workers**, but schedules trigger **workflows**.

```
┌─────────────────────────────────┐
│   Schedule (Temporal Server)    │ ← Lives in Temporal Cloud
│   - Triggers workflows           │
│   - Manages timing               │
└─────────────────────────────────┘
           │
           │ triggers
           ↓
┌─────────────────────────────────┐
│   Worker (Your Server)          │ ← Lives on your infrastructure
│   - Runs workflows               │
│   - Hosts MCP servers            │
└─────────────────────────────────┘
           │
           │ spawns
           ↓
┌─────────────────────────────────┐
│   MCP Server (Process)          │ ← Lives as long as worker
│   - Spotify API connection       │
│   - OAuth tokens                 │
└─────────────────────────────────┘
```

**Timing mismatch**:
- Schedule lifetime: **Forever** (until deleted)
- Worker lifetime: **Hours/days** (until restart)
- MCP server lifetime: **Same as worker**
- Workflow lifetime: **Seconds/minutes**

**Implication**: MCP servers **restart** when workers restart, **not** when schedules restart.

---

### Quirk #2: First Workflow After Worker Restart Has MCP Startup Overhead

**Scenario**:

```
Worker starts at 1:00 PM
  ↓
Schedule triggers at 2:00 PM
  ↓
Workflow 1 starts
  ↓
First MCP call → MCP server spawns (200-400ms overhead) ← SLOW
  ↓
Workflow 1 completes
  ↓
Schedule triggers at 2:05 PM
  ↓
Workflow 2 starts
  ↓
Second MCP call → MCP already running ← FAST
```

**First workflow is slower!**

**Solution**: Warm up MCP server before first scheduled workflow.

```python
# In worker startup
@app.on_event("startup")
async def startup_event():
    logger.info("Worker starting, warming up MCP...")

    # Make a lightweight MCP call to spawn server
    await mcp.call_tool("get_user_profile", {})

    logger.info("MCP warmed up and ready for scheduled workflows")
```

---

### Quirk #3: OAuth Token Refresh Timing

**Problem**: Spotify OAuth tokens expire after **1 hour**. Scheduled workflows may hit expired tokens.

**Scenario**:

```
Worker starts: 1:00 PM
  ↓
MCP server spawns with OAuth token (expires 2:00 PM)
  ↓
Scheduled workflow at 1:30 PM: ✅ Token valid
Scheduled workflow at 1:45 PM: ✅ Token valid
Scheduled workflow at 2:05 PM: ❌ Token expired!
```

**Complication**: MCP server is **stateless**, so it should refresh tokens automatically. But...

**If token refresh fails** (network error, Spotify downtime):
- All subsequent scheduled workflows fail
- MCP server needs restart to fix
- Manual intervention required

**Solution**: Implement token refresh monitoring.

```python
@activity.defn(name="ensure-spotify-token-fresh")
async def ensure_spotify_token_fresh() -> dict:
    """Verify Spotify OAuth token is fresh before MCP operations."""

    # Check token expiry
    token_info = await mcp.call_tool("get_token_info", {})

    expires_at = datetime.fromisoformat(token_info["expires_at"])
    now = datetime.now()

    # If token expires in < 5 minutes, refresh it
    if (expires_at - now).total_seconds() < 300:
        activity.logger.info("Token expiring soon, refreshing...")
        await mcp.call_tool("refresh_token", {})

    return {"token_fresh": True, "expires_at": expires_at.isoformat()}


# Use in workflow
@workflow.defn
class ScheduledMusicSyncWorkflow:
    @workflow.run
    async def run(self, input_data: WorkflowInput):
        # Ensure token fresh before starting
        await workflow.execute_activity(
            ensure_spotify_token_fresh,
            start_to_close_timeout=timedelta(seconds=10)
        )

        # Now safe to use Spotify MCP
        # ...
```

---

### Quirk #4: Concurrent Schedules Can Overwhelm MCP

**Problem**: Multiple schedules hitting same MCP server can cause rate limiting.

**Scenario**:

```
Schedule A: Sync playlist 1 every 5 minutes
Schedule B: Sync playlist 2 every 5 minutes
Schedule C: Sync playlist 3 every 5 minutes

Worker 1:
  ↓
2:00 PM: Workflow A1, B1, C1 all start ← 3 concurrent MCP calls
  ↓
Spotify rate limit: 429 Too Many Requests ❌
  ↓
All 3 workflows retry → More MCP calls → More rate limiting
```

**Solution**: Coordinate schedules or use activity-level rate limiting.

```python
# Option 1: Stagger schedules
Schedule A: Every 5 minutes starting at :00 (2:00, 2:05, 2:10...)
Schedule B: Every 5 minutes starting at :02 (2:02, 2:07, 2:12...)
Schedule C: Every 5 minutes starting at :04 (2:04, 2:09, 2:14...)

# Option 2: Use semaphore in activities
from asyncio import Semaphore

# Global semaphore (max 2 concurrent Spotify calls)
spotify_semaphore = Semaphore(2)

@activity.defn(name="spotify-api-call")
async def spotify_api_call(tool_name: str, args: dict):
    async with spotify_semaphore:  # ← Only 2 at a time
        return await mcp.call_tool(tool_name, args)
```

---

### Quirk #5: Schedule Backfills Don't Replay MCP Calls

**From Temporal docs**:
> "Backfilling allows you to simulate past time periods as if they occurred in the present."

**What is backfill?**

```python
# You create a schedule today (Nov 17) but want to "run it as if it started Nov 1"
create_schedule(
    id="daily-sync",
    spec=ScheduleSpec(
        calendars=[CalendarSpec(hour=2)],  # Daily at 2 AM
    ),
    backfill=[
        BackfillRequest(
            start_time=datetime(2025, 11, 1),
            end_time=datetime(2025, 11, 17),
            overlap_policy=OverlapPolicy.ALLOW_ALL
        )
    ]
)

# Temporal will run workflows for Nov 1, 2, 3, ..., 17 (17 workflows!)
```

**MCP quirk**: Backfilled workflows **don't actually run in the past**.

```
Backfill creates 17 workflows
  ↓
All 17 run NOW (Nov 17, 2:00 PM)
  ↓
All 17 try to use MCP server NOW
  ↓
Rate limiting! ❌
```

**Key insight**: Backfills create **concurrent workflows** that all hit MCP **simultaneously**.

**Solution**: Use `SKIP` or `BUFFER_ONE` overlap policy for backfills.

```python
backfill=[
    BackfillRequest(
        start_time=datetime(2025, 11, 1),
        end_time=datetime(2025, 11, 17),
        overlap_policy=OverlapPolicy.BUFFER_ONE  # ← Sequential execution
    )
]
```

---

## Practical Patterns

### Pattern 1: Scheduled Playlist Sync

**Use case**: Sync user's Apple Music playlist to Spotify daily at 2 AM.

```python
from temporalio.client import Client, ScheduleSpec, CalendarSpec

async def create_daily_sync_schedule():
    """Create schedule for daily playlist sync."""

    client = await Client.connect(settings.temporal_host)

    schedule = await client.create_schedule(
        id="daily-playlist-sync-user123",
        schedule=Schedule(
            action=ScheduleActionStartWorkflow(
                workflow_type=MusicSyncWorkflow,
                task_queue="music-sync",
                args=[WorkflowInput(
                    song_metadata=...,  # From playlist
                    playlist_id="spotify_playlist_id",
                    user_id="user123"
                )]
            ),
            spec=ScheduleSpec(
                calendars=[CalendarSpec(hour=2, minute=0)]  # 2 AM
            ),
            policy=SchedulePolicy(
                overlap=OverlapPolicy.SKIP,  # ← Don't run if previous still going
                catchup_window=timedelta(minutes=10)  # ← If missed, catch up within 10 min
            )
        )
    )

    return schedule.id
```

**MCP considerations**:
- Worker must be running at 2 AM (or schedule skips)
- MCP server shared across all scheduled workflows
- First workflow after worker restart has startup overhead
- OAuth token may need refresh if worker ran 1+ hours

---

### Pattern 2: High-Frequency Sync with Rate Limiting

**Use case**: Sync new songs every 5 minutes, but handle Spotify rate limits.

```python
# Schedule configuration
schedule_spec = ScheduleSpec(
    intervals=[ScheduleIntervalSpec(every=timedelta(minutes=5))]
)

# Workflow with rate limit handling
@workflow.defn
class RateLimitAwareSyncWorkflow:
    @workflow.run
    async def run(self, input_data: WorkflowInput):
        # Check circuit breaker before starting
        circuit_status = await workflow.execute_activity(
            "check-circuit-breaker",
            "spotify-api",
            start_to_close_timeout=timedelta(seconds=5)
        )

        if circuit_status["is_open"]:
            workflow.logger.warning(
                f"Circuit breaker open, skipping sync. "
                f"Reason: {circuit_status['reason']}"
            )
            return WorkflowResult(
                success=False,
                message="Skipped due to circuit breaker (rate limit protection)"
            )

        # Proceed with normal sync
        # ...
```

**Why this works**:
- Circuit breaker prevents cascading failures
- Skipped workflows don't waste MCP calls
- Rate limit affects future schedules (circuit opens)
- Circuit auto-closes after cooldown
- Scheduled workflows resume automatically

---

### Pattern 3: Multi-User Scheduled Sync

**Use case**: 100 users, each wants daily sync.

**Bad approach** (100 schedules):
```python
# ❌ Don't do this
for user in users:
    await client.create_schedule(
        id=f"daily-sync-{user.id}",
        schedule=...,  # 100 concurrent workflows at 2 AM!
    )
```

**Problem**: All 100 workflows start at 2 AM → MCP overload → Rate limiting.

**Good approach** (1 schedule, batched):
```python
# ✅ Do this
await client.create_schedule(
    id="daily-sync-all-users",
    schedule=Schedule(
        action=ScheduleActionStartWorkflow(
            workflow_type=BatchMusicSyncWorkflow,  # ← Batch workflow
            task_queue="music-sync",
            args=[{
                "user_ids": [user.id for user in users],
                "batch_size": 10,  # Process 10 at a time
                "delay_between_batches": 30  # 30 seconds between batches
            }]
        ),
        spec=ScheduleSpec(calendars=[CalendarSpec(hour=2)])
    )
)

# Batch workflow
@workflow.defn
class BatchMusicSyncWorkflow:
    @workflow.run
    async def run(self, user_ids: list, batch_size: int, delay_between_batches: int):
        results = []

        # Process in batches
        for i in range(0, len(user_ids), batch_size):
            batch = user_ids[i:i+batch_size]

            # Start child workflows for batch (parallel within batch)
            batch_handles = []
            for user_id in batch:
                handle = await workflow.start_child_workflow(
                    MusicSyncWorkflow.run,
                    args=[get_user_sync_input(user_id)],
                    id=f"sync-{user_id}-{workflow.now().isoformat()}"
                )
                batch_handles.append(handle)

            # Wait for batch to complete
            for handle in batch_handles:
                result = await handle
                results.append(result)

            # Delay before next batch (rate limit protection)
            if i + batch_size < len(user_ids):
                await asyncio.sleep(delay_between_batches)

        return {"processed": len(results), "results": results}
```

**Why this works**:
- 1 schedule instead of 100
- Batches of 10 run in parallel (manageable)
- 30-second delay between batches (rate limit protection)
- Total time: ~5 minutes for 100 users (acceptable for daily sync)

---

### Pattern 4: Schedule with MCP Health Check

**Use case**: Ensure MCP is healthy before running scheduled workflow.

```python
@workflow.defn
class HealthAwareSyncWorkflow:
    @workflow.run
    async def run(self, input_data: WorkflowInput):
        # Step 1: Health check MCP
        mcp_health = await workflow.execute_activity(
            "check-mcp-health",
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=1)  # Don't retry health check
        )

        if not mcp_health["is_healthy"]:
            workflow.logger.error(
                f"MCP unhealthy: {mcp_health['error']}. Skipping sync."
            )
            return WorkflowResult(
                success=False,
                message=f"Skipped due to MCP health: {mcp_health['error']}"
            )

        # Step 2: Ensure token fresh
        await workflow.execute_activity(
            "ensure-spotify-token-fresh",
            start_to_close_timeout=timedelta(seconds=10)
        )

        # Step 3: Proceed with sync
        # ... normal workflow logic
```

**MCP health check activity**:
```python
@activity.defn(name="check-mcp-health")
async def check_mcp_health() -> dict:
    """Quick health check for Spotify MCP."""
    try:
        # Lightweight read-only call
        start = time.time()
        profile = await mcp.call_tool("get_user_profile", {})
        latency = time.time() - start

        return {
            "is_healthy": True,
            "latency_ms": latency * 1000,
            "user_id": profile.get("id")
        }

    except Exception as e:
        return {
            "is_healthy": False,
            "error": str(e),
            "error_type": type(e).__name__
        }
```

---

## Recommended Schedule Configurations

### For Spotify Sync Use Cases

#### Daily Playlist Sync
```python
ScheduleSpec(
    calendars=[CalendarSpec(hour=2, minute=0)]  # 2 AM daily
)
overlap_policy = OverlapPolicy.SKIP  # ← Skip if previous still running
```

**Rationale**:
- 2 AM has low Spotify API traffic
- MCP server likely fresh (worker restarted overnight)
- SKIP prevents overlapping syncs

---

#### Hourly Discovery Sync
```python
ScheduleSpec(
    intervals=[ScheduleIntervalSpec(every=timedelta(hours=1))]
)
overlap_policy = OverlapPolicy.CANCEL_OTHER  # ← Cancel old, start new
```

**Rationale**:
- Users want latest discoveries
- Old sync doesn't matter if new one starts
- CANCEL_OTHER ensures fresh data

---

#### High-Frequency (Every 5 Min) with Rate Limiting
```python
ScheduleSpec(
    intervals=[ScheduleIntervalSpec(every=timedelta(minutes=5))]
)
overlap_policy = OverlapPolicy.SKIP  # ← Critical for rate limiting!
catchup_window = timedelta(minutes=2)  # ← Don't catch up old runs
```

**Rationale**:
- SKIP prevents cascading failures
- catchup_window=2min means if workflow takes >5 min, don't queue up missed runs
- Protects MCP from overload

---

## Debugging Scheduled Workflows with MCP

### Common Issues

#### Issue 1: "First workflow fails, rest succeed"

**Symptoms**: Schedule triggers 10 workflows. First one fails, rest succeed.

**Cause**: MCP startup overhead + tight timeout.

**Solution**:
```python
# Increase timeout for first activity
search_results = await workflow.execute_activity(
    "spotify-search",
    ...,
    start_to_close_timeout=timedelta(seconds=30),  # ← More generous
)
```

---

#### Issue 2: "All workflows fail at same time"

**Symptoms**: Schedule works for hours, then all workflows fail.

**Cause**: OAuth token expired, MCP can't refresh.

**Solution**: Add token refresh activity at workflow start (Pattern 4).

---

#### Issue 3: "Random workflows fail with rate limit"

**Symptoms**: Some scheduled workflows hit 429, others don't.

**Cause**: Concurrent schedules or high frequency.

**Solution**: Use circuit breaker (Pattern 2) or batch workflows (Pattern 3).

---

#### Issue 4: "MCP server not found"

**Symptoms**: `KeyError: 'SpotifyMCP'` in workflow.

**Cause**: MCP server name mismatch or worker not configured.

**Solution**:
```python
# Use constant
SPOTIFY_MCP_SERVER_NAME = "SpotifyMCP"

# Worker config
spotify_mcp = StatelessMCPServerProvider(
    server_id=SPOTIFY_MCP_SERVER_NAME,  # ← Must match
    ...
)

# Workflow
server = stateless_mcp_server(SPOTIFY_MCP_SERVER_NAME)  # ← Must match
```

---

## Summary of Quirks

| Quirk | Impact on Schedules | Mitigation |
|-------|---------------------|------------|
| **MCP not durable** | Scheduled workflows may start with stale MCP | Health check before workflow |
| **MCP startup overhead** | First scheduled workflow slower | Warm up MCP on worker startup |
| **OAuth token expiry** | Scheduled workflows fail after 1 hour | Token refresh activity |
| **Concurrent schedules** | Rate limiting across workflows | Stagger schedules or batch |
| **Backfill creates concurrent runs** | Backfills overwhelm MCP | Use BUFFER_ONE for backfills |
| **Schedule deletion doesn't stop workflows** | In-flight workflows keep MCP alive | Normal (no action needed) |
| **Overlap policy affects manual triggers** | Can't manually bypass rate limits | Use circuit breaker |

---

## Conclusion

Temporal schedules + MCP servers have **subtle interactions** that require careful design:

1. **MCP lifecycle** is tied to workers, not schedules
2. **First workflow** after worker restart has MCP startup overhead
3. **OAuth tokens** expire and need refresh for long-running schedules
4. **Concurrent schedules** can overwhelm MCP with rate limits
5. **Backfills** create concurrent workflows (use carefully)
6. **Overlap policies** affect both scheduled and manual triggers

**For Spotify MCP integration**:
- ✅ Use `StatelessMCPServerProvider`
- ✅ Warm up MCP on worker startup
- ✅ Add token refresh activity
- ✅ Use `SKIP` overlap policy for high-frequency schedules
- ✅ Batch multi-user syncs
- ✅ Health check MCP before scheduled workflows

---

**Document Version**: 1.0
**Last Updated**: 2025-11-17
**Related Docs**:
- TEMPORAL_MCP_QUIRKS.md (MCP-specific quirks)
- TEMPORAL_ENHANCEMENT_PLAN.md (Enhancement roadmap)
