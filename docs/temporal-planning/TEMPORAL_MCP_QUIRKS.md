# Temporal MCP Integration: Unique Quirks & Timing Considerations
## Critical Insights for Spotify MCP Integration

**Date**: 2025-11-17
**Focus**: Understanding MCP server integration quirks with Temporal workflows
**Reference**: [temporalio/samples-python/openai_agents/mcp](https://github.com/temporalio/samples-python/tree/main/openai_agents/mcp)

---

## Executive Summary

Integrating MCP (Model Context Protocol) servers with Temporal workflows has **critical quirks** that can cause subtle bugs if not understood. This document explores these quirks with specific application to the Spotify MCP integration.

**Key Takeaway**: **MCP servers are NOT covered by Temporal's durability guarantees** — you must design around this limitation.

---

## Table of Contents

1. [The Durability Gap](#the-durability-gap)
2. [Stateless vs Stateful MCP Servers](#stateless-vs-stateful-mcp-servers)
3. [Spotify MCP Server Analysis](#spotify-mcp-server-analysis)
4. [Timing Quirks & Gotchas](#timing-quirks--gotchas)
5. [Error Handling Patterns](#error-handling-patterns)
6. [Best Practices](#best-practices)
7. [Code Examples](#code-examples)

---

## The Durability Gap

### Critical Quirk #1: MCP Servers Live Outside Temporal's Durability

**From Temporal docs**:
> "While Temporal provides durable execution for your workflows, **this durability does not extend to MCP servers**, which operate independently."

**What this means**:

```
┌─────────────────────────────────┐
│   Temporal Workflow (Durable)   │
│                                 │
│  ✅ Activity retries            │
│  ✅ State persistence           │
│  ✅ Crash recovery              │
└─────────────────────────────────┘
           │
           │ calls
           ↓
┌─────────────────────────────────┐
│  MCP Server (NOT Durable)       │
│                                 │
│  ❌ No automatic recovery       │
│  ❌ State lost on crash         │
│  ❌ No replay protection        │
└─────────────────────────────────┘
```

**Implications for Spotify MCP**:

If your Temporal worker crashes:
- ✅ Workflow will resume from last completed activity
- ❌ MCP server connection is **lost**
- ❌ Any MCP server state is **gone**
- ⚠️ You must **reconnect** and **re-authenticate**

**Real-world scenario**:
```python
# Workflow starts
1. Authenticate with Spotify MCP → Success
2. Search for track → Success
3. [WORKER CRASHES]
4. Workflow resumes from step 3
5. Add to playlist → FAILS (MCP connection lost!)
```

**Solution**: Design MCP calls to be **idempotent** and **self-contained**.

---

## Stateless vs Stateful MCP Servers

### The Critical Distinction

#### Stateless MCP Server

**Definition**: Each tool call is **self-contained** with all necessary information.

**Example (Weather API)**:
```python
# Stateless: Each call has everything needed
get_weather(location="San Francisco")  # ✅ Works
get_weather(location="New York")        # ✅ Works independently
```

**Characteristics**:
- ✅ Can reconnect without side effects
- ✅ Tools work in any order
- ✅ No memory between calls
- ✅ Use `StatelessMCPServerProvider`

---

#### Stateful MCP Server

**Definition**: Requires **previous calls** to set up state before working.

**Example (Stateful Weather API)**:
```python
# Stateful: Must set location first
set_location("San Francisco")  # Required setup
get_weather()                   # Uses stored location

# If connection drops after set_location()...
get_weather()                   # ❌ FAILS (state lost!)
```

**Characteristics**:
- ❌ Cannot auto-reconnect (state lost)
- ⚠️ Raises `ApplicationError` on failure
- ⚠️ Requires **custom retry logic**
- ⚠️ Use `StatefulMCPServerProvider` (or custom handling)

---

### Spotify MCP Server: Stateless or Stateful?

**Analysis of your Spotify MCP**:

```python
# From mcp_client/client.py
async def call_tool(self, tool_name: str, arguments: dict):
    """Call a tool exposed by the Spotify MCP server."""
    # Each call is independent
    # OAuth token is passed/refreshed per request
```

**Observed tool patterns**:

```python
# 1. Search tracks (stateless)
search_tracks(query="Bohemian Rhapsody", limit=10)
# ✅ Self-contained, all params included

# 2. Add to playlist (stateless)
add_to_playlist(playlist_id="abc", track_uris=["spotify:track:123"])
# ✅ Self-contained, all params included

# 3. Get playlist (stateless)
get_playlist(playlist_id="abc")
# ✅ Self-contained, all params included
```

**Verdict**: **Spotify MCP is STATELESS** ✅

**Reasoning**:
1. Each tool call includes all necessary parameters
2. OAuth tokens are refreshed automatically per request
3. No sequence dependencies (can call tools in any order)
4. Reconnection doesn't break functionality

**Recommendation**: Use `StatelessMCPServerProvider` for Spotify MCP.

---

## Timing Quirks & Gotchas

### Quirk #1: MCP Server Startup Time

**Problem**: MCP servers take time to initialize.

**Timing**:
```
Worker starts
  ↓
MCP server spawns (stdio process)  ← 100-500ms
  ↓
MCP capabilities negotiation       ← 50-200ms
  ↓
First tool call                    ← Normal latency
```

**Total overhead**: ~150-700ms per MCP server instance

**For Spotify MCP**:
- Spotify MCP is **stdio-based** (subprocess spawn)
- **Estimate**: 200-400ms startup time
- **Impact**: First workflow run slower than subsequent runs

**Mitigation**:
```python
# Set appropriate timeout for first activity
@workflow.run
async def run(self, input_data: WorkflowInput):
    # First call may be slower due to MCP startup
    search_results = await workflow.execute_activity(
        "spotify-search",
        input_data.song_metadata,
        start_to_close_timeout=timedelta(seconds=30),  # ← Extra buffer
        heartbeat_timeout=timedelta(seconds=10),
    )
```

---

### Quirk #2: Stateless Provider Restarts MCP on Every Failure

**From Temporal docs**:
> "Stateless servers are restarted automatically by creating new instances on each reconnection."

**What this means**:

```python
# StatelessMCPServerProvider behavior
1. MCP server starts
2. Tool call fails (network error)
3. Provider KILLS old MCP server
4. Provider SPAWNS new MCP server  ← 200-400ms overhead
5. Retry tool call
```

**Timing impact**:
- **Normal retry**: ~1-2 seconds (backoff)
- **With MCP restart**: ~1.5-2.5 seconds (backoff + startup)

**For Spotify MCP**:
- Network errors → MCP restart → 200-400ms extra per retry
- Rate limit (429) → MCP restart → Wasted time (server wasn't the problem!)

**Optimization**:
```python
# Don't restart MCP for certain errors
@activity.defn(name="spotify-search")
async def spotify_search_activity(song_metadata: SongMetadata):
    try:
        result = await mcp.call_tool("search_tracks", {...})
        return result
    except RateLimitError as e:
        # Don't let activity fail (prevents MCP restart)
        activity.logger.warning(f"Rate limited, backing off: {e}")
        await asyncio.sleep(e.retry_after)
        # Retry within same activity (MCP stays alive)
        return await mcp.call_tool("search_tracks", {...})
```

---

### Quirk #3: No Automatic Request Deduplication

**Problem**: Temporal replays workflows deterministically, but MCP calls are **side effects**.

**Scenario**:
```python
@workflow.defn
class ProblematicWorkflow:
    @workflow.run
    async def run(self):
        # This runs as activity (good)
        await workflow.execute_activity("add-to-playlist", ...)

        # [WORKER CRASHES]
        # [WORKFLOW REPLAYS FROM START]

        # Activity runs AGAIN
        # → Track added to playlist TWICE! (if not idempotent)
```

**For Spotify MCP**:
- `add_to_playlist` called twice → Duplicate tracks in playlist
- `search_tracks` called twice → OK (read-only)
- `remove_from_playlist` called twice → May fail or remove wrong track

**Solution**: Implement idempotency checks.

```python
@activity.defn(name="add-to-playlist")
async def add_to_playlist_activity(track_uri: str, playlist_id: str):
    # Idempotency check
    playlist_tracks = await mcp.call_tool("get_playlist", {"playlist_id": playlist_id})

    if track_uri in playlist_tracks:
        activity.logger.info(f"Track {track_uri} already in playlist, skipping")
        return {"added": False, "reason": "already_exists"}

    # Safe to add
    result = await mcp.call_tool("add_to_playlist", {
        "playlist_id": playlist_id,
        "track_uris": [track_uri]
    })

    return {"added": True}
```

---

### Quirk #4: MCP Server Lifecycle Tied to Worker

**Problem**: MCP servers live as long as the worker process.

**Scenario**:
```
Worker 1 starts → MCP Server 1 spawns
  ↓
Workflow 1 uses MCP Server 1
Workflow 2 uses MCP Server 1  ← SAME instance
Workflow 3 uses MCP Server 1  ← SAME instance
  ↓
Worker 1 shuts down → MCP Server 1 dies
```

**Implication**: MCP server is **shared** across all workflows on a worker.

**For Spotify MCP**:
- ⚠️ OAuth token refresh shared across workflows
- ⚠️ Rate limits affect ALL workflows (429 blocks everyone)
- ✅ Fewer MCP instances = less memory

**Risk**: One workflow's rate limit can block others.

**Mitigation**:
```python
# Circuit breaker pattern (from enhancement plan)
if circuit_breaker.is_open("spotify-api"):
    # Don't start new workflows if Spotify is rate-limiting
    raise ApplicationError("Spotify API circuit breaker open", non_retryable=True)
```

---

### Quirk #5: Timing of MCP Server Name Resolution

**From Temporal docs**:
> "The server name in workflow code must exactly match configuration: `stateless_mcp_server('FileSystemServer')` requires matching MCP instance naming."

**Problem**: Server name lookup happens **at workflow runtime**, not worker startup.

**Scenario**:
```python
# Worker configuration
filesystem_server = StatelessMCPServerProvider(
    lambda: MCPServerStdio(
        name="FileSystemServer",  # ← Name defined here
        ...
    )
)

# Workflow
@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self):
        # Name MUST match exactly (case-sensitive)
        server = openai_agents.workflow.stateless_mcp_server("FileSystemServer")  # ✅
        server = openai_agents.workflow.stateless_mcp_server("filesystemserver")  # ❌ KeyError!
```

**For Spotify MCP**:
- Typo in server name → Runtime error (not startup error)
- Hard to debug (error happens in workflow, not configuration)

**Best Practice**:
```python
# Define as constant
SPOTIFY_MCP_SERVER_NAME = "SpotifyMCP"

# Worker config
spotify_server = StatelessMCPServerProvider(
    lambda: MCPServerStdio(
        name=SPOTIFY_MCP_SERVER_NAME,  # ← Use constant
        ...
    )
)

# Workflow
server = openai_agents.workflow.stateless_mcp_server(SPOTIFY_MCP_SERVER_NAME)  # ← Use constant
```

---

## Error Handling Patterns

### Pattern 1: Transient MCP Errors (Stateless)

**Scenario**: Network hiccup, temporary MCP failure.

**Handling**:
```python
from temporalio.common import RetryPolicy

@workflow.defn
class MusicSyncWorkflow:
    @workflow.run
    async def run(self, input_data: WorkflowInput):
        # Temporal handles retries, StatelessMCPServerProvider restarts MCP
        results = await workflow.execute_activity(
            "spotify-search",
            input_data.song_metadata,
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
                backoff_coefficient=2.0,
                # MCP errors are retryable by default
            )
        )
```

**Automatic behavior**:
1. First call fails → MCP server restarted
2. Retry (2s later) → New MCP instance
3. If successful → Continue
4. If still failing → Next retry (4s later)

---

### Pattern 2: Rate Limiting (Don't Restart MCP)

**Scenario**: Spotify returns 429 (rate limit).

**Problem**: Restarting MCP wastes time (server isn't broken).

**Solution**: Handle within activity.

```python
@activity.defn(name="spotify-search")
async def spotify_search_activity(song_metadata: SongMetadata):
    max_retries = 3

    for attempt in range(max_retries):
        try:
            result = await mcp.call_tool("search_tracks", {...})
            return result

        except RateLimitError as e:
            if attempt == max_retries - 1:
                raise  # Give up

            retry_after = e.retry_after or 2 ** attempt
            activity.logger.warning(
                f"Rate limited, retrying after {retry_after}s (attempt {attempt+1})"
            )

            # Sleep WITHIN activity (MCP stays alive)
            await asyncio.sleep(retry_after)

    raise Exception("Max retries exceeded")
```

**Why this is better**:
- MCP server stays alive (no restart overhead)
- Respects `Retry-After` header from Spotify
- Faster recovery (no 200-400ms MCP restart)

---

### Pattern 3: Authentication Errors (Non-Retryable)

**Scenario**: Invalid OAuth token, scope errors.

**Handling**:
```python
@activity.defn(name="spotify-search")
async def spotify_search_activity(song_metadata: SongMetadata):
    try:
        result = await mcp.call_tool("search_tracks", {...})
        return result

    except AuthenticationError as e:
        # Don't retry auth errors
        raise ApplicationError(
            f"Spotify authentication failed: {e}",
            type="SpotifyAuthError",
            non_retryable=True  # ← Stop retrying
        )

    except InsufficientScopeError as e:
        # User needs to re-authorize
        raise ApplicationError(
            f"Insufficient Spotify permissions: {e}",
            type="SpotifyInsufficientScope",
            non_retryable=True  # ← Stop retrying
        )
```

**Why non-retryable**:
- Auth errors won't fix themselves
- Restarting MCP won't help
- Save time and resources

---

### Pattern 4: Stateful MCP Error (If You Had One)

**Scenario**: MCP server with session state.

**Example** (hypothetical stateful Spotify MCP):
```python
# Hypothetical stateful API
await mcp.call_tool("authenticate", {"user_id": "user_123"})  # Sets session
await mcp.call_tool("get_my_playlists", {})  # Uses session

# If MCP crashes after authenticate...
await mcp.call_tool("get_my_playlists", {})  # ❌ FAILS (session lost)
```

**Handling**:
```python
@workflow.defn
class StatefulWorkflow:
    @workflow.run
    async def run(self):
        try:
            # Use stateful MCP
            result = await workflow.execute_activity(
                "use-stateful-mcp",
                ...
            )
        except ApplicationError as e:
            if e.type == "MCPServerStateError":
                # Custom retry logic: re-initialize state
                await workflow.execute_activity("reinitialize-mcp-state", ...)
                # Retry original call
                result = await workflow.execute_activity("use-stateful-mcp", ...)
```

**Good news**: Spotify MCP is stateless, so you don't need this! ✅

---

## Best Practices

### 1. Always Use Appropriate MCP Provider

**For Spotify MCP** (stateless):
```python
from temporalio.contrib.openai_agents import StatelessMCPServerProvider

spotify_mcp = StatelessMCPServerProvider(
    lambda: MCPServerStdio(
        name="SpotifyMCP",
        params={
            "command": "python",
            "args": ["-m", "spotify_mcp.server"],
            "env": {
                "SPOTIFY_CLIENT_ID": settings.spotify_client_id,
                "SPOTIFY_CLIENT_SECRET": settings.spotify_client_secret,
            }
        }
    )
)
```

**Why lambda?**: Factory function creates fresh MCP instance on each restart.

---

### 2. Design for Idempotency

**Check before mutating**:
```python
@activity.defn(name="add-to-playlist")
async def add_to_playlist_activity(track_uri: str, playlist_id: str):
    # 1. Check if already exists
    playlist = await mcp.call_tool("get_playlist", {"playlist_id": playlist_id})

    existing_uris = [track["uri"] for track in playlist["tracks"]]

    if track_uri in existing_uris:
        return {"added": False, "reason": "already_exists"}

    # 2. Safe to add
    await mcp.call_tool("add_to_playlist", {
        "playlist_id": playlist_id,
        "track_uris": [track_uri]
    })

    return {"added": True}
```

---

### 3. Set Appropriate Timeouts

**Account for MCP startup**:
```python
# First call after MCP restart
search_results = await workflow.execute_activity(
    "spotify-search",
    ...,
    start_to_close_timeout=timedelta(seconds=30),  # ← MCP startup + API call
    heartbeat_timeout=timedelta(seconds=10),       # ← Detect hangs
)

# Subsequent calls (MCP already running)
add_result = await workflow.execute_activity(
    "add-to-playlist",
    ...,
    start_to_close_timeout=timedelta(seconds=15),  # ← Just API call
)
```

---

### 4. Handle Rate Limits Gracefully

**Don't waste retries**:
```python
@activity.defn(name="spotify-tool-call")
async def spotify_tool_call(tool_name: str, args: dict):
    try:
        return await mcp.call_tool(tool_name, args)

    except RateLimitError as e:
        # Extract Retry-After header
        retry_after = int(e.response.headers.get("Retry-After", 5))

        activity.logger.warning(
            f"Spotify rate limit hit, backing off {retry_after}s"
        )

        # Report heartbeat (keep activity alive)
        activity.heartbeat()

        # Sleep and retry within same activity
        await asyncio.sleep(retry_after)

        # Retry
        return await mcp.call_tool(tool_name, args)
```

---

### 5. Use Circuit Breaker for Systemic Failures

**Prevent thundering herd**:
```python
from utils.circuit_breaker import circuit_breaker

@activity.defn(name="spotify-search")
async def spotify_search_activity(song_metadata: SongMetadata):
    # Check circuit breaker
    if circuit_breaker.is_open("spotify-mcp"):
        raise ApplicationError(
            "Spotify MCP circuit breaker open (systemic failure)",
            non_retryable=True  # Don't retry when circuit is open
        )

    try:
        result = await mcp.call_tool("search_tracks", {...})
        circuit_breaker.record_success("spotify-mcp")
        return result

    except Exception as e:
        circuit_breaker.record_failure("spotify-mcp")
        raise
```

---

### 6. Monitor MCP Server Health

**Add health checks**:
```python
@app.get("/health/mcp")
async def mcp_health():
    """Check MCP server health."""
    try:
        # Simple read-only call
        result = await mcp.call_tool("get_user_profile", {})
        return {
            "status": "healthy",
            "mcp_server": "responsive",
            "latency_ms": result.get("latency")
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "mcp_server": "unresponsive",
            "error": str(e)
        }
```

---

## Code Examples

### Example 1: Converting Current Code to StatelessMCPServerProvider

**Current implementation** (manual MCP client):
```python
# mcp_client/client.py
class MCPClient:
    def __init__(self):
        self.process = None
        self.session = None

    async def connect(self):
        # Start MCP server manually
        self.process = await asyncio.create_subprocess_exec(...)
        # ... setup
```

**New implementation** (SDK provider):
```python
# workers/music_sync_worker.py
from temporalio.contrib.openai_agents import (
    StatelessMCPServerProvider,
    OpenAIAgentsPlugin
)
from mcp import StdioServerParameters

# Define Spotify MCP server
spotify_mcp_provider = StatelessMCPServerProvider(
    server_id="SpotifyMCP",
    server_params=StdioServerParameters(
        command="python",
        args=["-m", "spotify_mcp.server"],
        env={
            "SPOTIFY_CLIENT_ID": settings.spotify_client_id,
            "SPOTIFY_CLIENT_SECRET": settings.spotify_client_secret,
            "SPOTIFY_REDIRECT_URI": settings.spotify_redirect_uri,
        }
    )
)

# Worker configuration
worker = Worker(
    client,
    task_queue="music-sync",
    workflows=[MusicSyncWorkflow],
    activities=[...],
    plugins=[
        OpenAIAgentsPlugin(
            mcp_servers=[spotify_mcp_provider],  # ← Register MCP
            model_activity_parameters=ModelActivityParameters(
                start_to_close_timeout=timedelta(seconds=60)
            )
        )
    ]
)
```

**Workflow usage**:
```python
from openai_agents import Agent, Runner
from temporalio.contrib.openai_agents import workflow as agents_workflow

@workflow.defn
class MusicSyncWorkflow:
    @workflow.run
    async def run(self, input_data: WorkflowInput):
        # Get MCP server reference
        spotify_server = agents_workflow.stateless_mcp_server("SpotifyMCP")

        # Create agent with MCP tools
        agent = Agent(
            name="SpotifyAgent",
            instructions=f"Find '{input_data.song_metadata.title}' and add to playlist",
            model="gpt-4o",
            mcp_servers=[spotify_server]  # ← MCP tools auto-available
        )

        # Run agent (MCP calls are durable activities)
        result = await Runner.run(agent, input="Complete the task")

        return result
```

**Benefits**:
- ✅ MCP lifecycle managed automatically
- ✅ Auto-restart on failure
- ✅ No manual connection management
- ✅ MCP calls are durable Temporal activities

---

### Example 2: Idempotent Playlist Operations

```python
@activity.defn(name="idempotent-add-to-playlist")
async def idempotent_add_to_playlist(
    track_uri: str,
    playlist_id: str,
    user_id: Optional[str] = None
) -> dict:
    """Add track to playlist with idempotency guarantee."""

    activity.logger.info(f"Adding {track_uri} to {playlist_id} (idempotent)")

    # Step 1: Get current playlist state
    playlist_data = await mcp.call_tool("get_playlist", {
        "playlist_id": playlist_id
    })

    # Step 2: Check if track already exists
    existing_track_uris = [
        track["uri"] for track in playlist_data.get("tracks", [])
    ]

    if track_uri in existing_track_uris:
        activity.logger.info(f"Track {track_uri} already in playlist")
        return {
            "added": False,
            "reason": "already_exists",
            "track_uri": track_uri,
            "playlist_id": playlist_id
        }

    # Step 3: Safe to add (track not in playlist)
    add_result = await mcp.call_tool("add_to_playlist", {
        "playlist_id": playlist_id,
        "track_uris": [track_uri]
    })

    # Step 4: Verify addition
    verification = await mcp.call_tool("get_playlist", {
        "playlist_id": playlist_id
    })

    updated_uris = [track["uri"] for track in verification.get("tracks", [])]

    if track_uri in updated_uris:
        activity.logger.info(f"Track {track_uri} successfully added")
        return {
            "added": True,
            "verified": True,
            "track_uri": track_uri,
            "playlist_id": playlist_id
        }
    else:
        activity.logger.error(f"Track {track_uri} add verification failed")
        raise ApplicationError(
            "Track added but verification failed",
            type="VerificationError"
        )
```

---

### Example 3: Rate Limit Handling with Retry-After

```python
import asyncio
from typing import Dict, Any

@activity.defn(name="spotify-api-call")
async def spotify_api_call_with_rate_limit_handling(
    tool_name: str,
    arguments: Dict[str, Any],
    max_retries: int = 3
) -> Any:
    """Call Spotify MCP tool with intelligent rate limit handling."""

    for attempt in range(max_retries):
        try:
            activity.logger.info(
                f"Calling {tool_name} (attempt {attempt + 1}/{max_retries})"
            )

            result = await mcp.call_tool(tool_name, arguments)

            activity.logger.info(f"{tool_name} succeeded")
            return result

        except RateLimitError as e:
            # Extract Retry-After from headers (seconds)
            retry_after = int(e.response.headers.get("Retry-After", 5))

            if attempt == max_retries - 1:
                # Last attempt, give up
                activity.logger.error(
                    f"Rate limit persisted after {max_retries} attempts"
                )
                raise ApplicationError(
                    f"Spotify rate limit exceeded: {e}",
                    type="SpotifyRateLimitExceeded",
                    non_retryable=True
                )

            activity.logger.warning(
                f"Rate limited by Spotify. Retry after {retry_after}s "
                f"(attempt {attempt + 1}/{max_retries})"
            )

            # Report heartbeat to keep activity alive during sleep
            activity.heartbeat({"status": f"rate_limited_retry_in_{retry_after}s"})

            # Sleep within activity (keeps MCP alive, no restart)
            await asyncio.sleep(retry_after)

            # Continue to next attempt
            continue

        except (NetworkError, TimeoutError) as e:
            # Transient errors: use exponential backoff
            backoff = 2 ** attempt

            if attempt == max_retries - 1:
                raise

            activity.logger.warning(
                f"Transient error: {e}. Retrying in {backoff}s"
            )

            activity.heartbeat({"status": f"transient_error_retry_in_{backoff}s"})
            await asyncio.sleep(backoff)
            continue

        except (AuthenticationError, InsufficientScopeError) as e:
            # Auth errors: don't retry
            raise ApplicationError(
                f"Authentication error: {e}",
                type="SpotifyAuthError",
                non_retryable=True
            )

    # Should never reach here
    raise Exception(f"Unexpected: exceeded {max_retries} retries")
```

---

## Summary of Key Quirks

| Quirk | Impact | Mitigation |
|-------|--------|------------|
| **MCP not durable** | Connection lost on worker crash | Use stateless provider, design for reconnection |
| **MCP restart overhead** | 200-400ms per restart | Handle rate limits in-activity to avoid restarts |
| **No request deduplication** | Replay can cause duplicates | Implement idempotency checks |
| **MCP shared across workflows** | One workflow's rate limit affects others | Use circuit breaker pattern |
| **Server name must match exactly** | Runtime KeyError if mismatch | Use constants for server names |
| **Startup time on first call** | First workflow run slower | Set appropriate timeouts |
| **No automatic state recovery** | Stateful MCP needs custom logic | Spotify is stateless, no issue ✅ |

---

## Recommendations for Spotify Integration

### High Priority ✅

1. **Use `StatelessMCPServerProvider`** (Spotify MCP is stateless)
2. **Implement idempotency** for `add_to_playlist` and `remove_from_playlist`
3. **Handle rate limits in-activity** (avoid MCP restarts)
4. **Set appropriate timeouts** (30s for first call, 15s for subsequent)

### Medium Priority 📋

5. **Add circuit breaker** for systemic Spotify API failures
6. **Monitor MCP health** with dedicated endpoint
7. **Use constants** for MCP server names (avoid typos)

### Nice to Have 🎯

8. **Metrics** for MCP call latency and failure rates
9. **Graceful degradation** when MCP is unavailable
10. **MCP connection pooling** (if scaling to many workers)

---

## Next Steps

1. **Review current MCP client** (`mcp_client/client.py`)
2. **Determine migration path**:
   - Option A: Keep manual client, add quirk mitigations
   - Option B: Migrate to `StatelessMCPServerProvider` (recommended)
3. **Implement idempotency** for playlist operations
4. **Add rate limit handling** in activities
5. **Test MCP restart scenarios** (kill worker mid-workflow)

---

**Document Version**: 1.0
**Last Updated**: 2025-11-17
**Status**: Ready for Implementation Review
