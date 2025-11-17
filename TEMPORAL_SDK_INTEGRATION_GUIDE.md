# Temporal OpenAI Agents SDK Integration Guide
## Using `temporalio.contrib.openai_agents` for Spotify MCP Integration

**Date**: 2025-11-17
**SDK Reference**: [temporalio/sdk-python/contrib/openai_agents](https://github.com/temporalio/sdk-python/blob/main/temporalio/contrib/openai_agents)
**Status**: Experimental (use with caution in production)

---

## Executive Summary

This guide demonstrates how to leverage the official **`temporalio.contrib.openai_agents`** SDK integration to enhance the Spotify MCP integration with:
- **Durable AI agents** that never lose progress
- **Activity-based tools** with automatic retry and failure recovery
- **MCP server integration** for Spotify API calls
- **Production-grade reliability** for long-running workflows

**Key Insight**: The current codebase already uses Temporal workflows but doesn't leverage the official OpenAI Agents SDK integration, which provides higher-level abstractions for AI agent patterns.

---

## Table of Contents

1. [Current vs. Proposed Architecture](#current-vs-proposed-architecture)
2. [SDK Components Overview](#sdk-components-overview)
3. [Migration Path](#migration-path)
4. [Implementation Examples](#implementation-examples)
5. [MCP Server Integration](#mcp-server-integration)
6. [Testing with SDK Utilities](#testing-with-sdk-utilities)
7. [Production Deployment](#production-deployment)

---

## Current vs. Proposed Architecture

### Current Implementation

```
User Request
    ↓
FastAPI Endpoint
    ↓
Temporal Workflow (MusicSyncWorkflow)
    ├─ Activity: spotify-search (manual implementation)
    ├─ Activity: fuzzy-match
    ├─ Activity: ai-disambiguate (LangChain/Claude SDK)
    ├─ Activity: add-to-playlist
    └─ Activity: verify-track-added
```

**Characteristics**:
- ✅ Durable execution via Temporal
- ✅ Custom retry policies per activity
- ⚠️ Manual activity implementations
- ⚠️ No standardized AI agent pattern
- ⚠️ MCP client manually managed
- ⚠️ AI calls not automatically durable

### Proposed Architecture with OpenAI Agents SDK

```
User Request
    ↓
FastAPI Endpoint
    ↓
Temporal Workflow (EnhancedMusicSyncWorkflow)
    ↓
OpenAI Agents Runner (durable execution)
    ├─ Agent: SearchStrategyAgent
    │   └─ Tool: spotify_search (via activity_as_tool)
    │       └─ MCP Server: Spotify API (StatelessMCPServerProvider)
    │
    ├─ Agent: MatchingAgent
    │   ├─ Tool: fuzzy_match (via activity_as_tool)
    │   └─ Tool: ai_disambiguate (built-in model invocation)
    │
    └─ Agent: PlaylistAgent
        ├─ Tool: add_to_playlist (via activity_as_tool)
        └─ Tool: verify_addition (via activity_as_tool)
```

**Characteristics**:
- ✅ Durable execution via Temporal + OpenAI Agents SDK
- ✅ Automatic activity wrapping for tools
- ✅ Built-in model invocation activities
- ✅ Standardized MCP server integration
- ✅ AI calls automatically durable and retryable
- ✅ Agent handoffs and multi-agent patterns
- ✅ OpenAI platform tracing

---

## SDK Components Overview

### 1. OpenAIAgentsPlugin

**Purpose**: Core plugin that bridges OpenAI Agents SDK and Temporal.

**What it does**:
- Ensures proper serialization of Pydantic types
- Propagates context for OpenAI Agents tracing
- Registers activity for invoking model calls
- Configures OpenAI Agents SDK to use Temporal activities

**Usage**:
```python
from temporalio.worker import Worker
from temporalio.contrib.openai_agents import OpenAIAgentsPlugin

worker = Worker(
    client,
    task_queue="music-sync",
    workflows=[EnhancedMusicSyncWorkflow],
    activities=[...],
    plugins=[OpenAIAgentsPlugin()],  # ← Add this
)
```

### 2. activity_as_tool()

**Purpose**: Convert Temporal activities into OpenAI Agents tools.

**Benefits**:
- Tool calls execute as Temporal activities (durable)
- Automatic retry and failure recovery
- Heartbeat support for long-running operations
- Activity-level timeouts and cancellation

**Example**:
```python
from temporalio import activity
from temporalio.contrib.openai_agents import activity_as_tool

@activity.defn(name="spotify-search")
async def spotify_search_activity(query: str, limit: int = 10) -> list:
    """Search Spotify for tracks."""
    # ... implementation
    return tracks

# Convert to tool
spotify_search_tool = activity_as_tool(
    spotify_search_activity,
    description="Search Spotify for tracks by query. Returns list of tracks."
)
```

### 3. MCP Server Providers

**Purpose**: Integrate MCP servers with Temporal workflows.

#### StatelessMCPServerProvider

For MCP servers where each operation is independent (like Spotify API).

```python
from temporalio.contrib.openai_agents import StatelessMCPServerProvider
from mcp import StdioServerParameters

# Define Spotify MCP server
spotify_mcp = StatelessMCPServerProvider(
    server_id="spotify",
    server_params=StdioServerParameters(
        command="python",
        args=["-m", "spotify_mcp.server"],
        env={"SPOTIFY_CLIENT_ID": "...", "SPOTIFY_CLIENT_SECRET": "..."}
    )
)
```

**Behavior**: If server crashes, a new instance is created automatically.

#### StatefulMCPServerProvider

For MCP servers that maintain session state.

```python
from temporalio.contrib.openai_agents import StatefulMCPServerProvider

# For session-dependent servers
stateful_mcp = StatefulMCPServerProvider(
    server_id="session-server",
    server_params=...
)
```

**Behavior**: Raises `ApplicationError` on failure; requires application-level retry logic.

### 4. Runner.run()

**Purpose**: Execute OpenAI Agents within Temporal workflows.

**Usage**:
```python
from openai_agents import Agent, Runner

@workflow.defn
class AgentWorkflow:
    @workflow.run
    async def run(self, prompt: str) -> str:
        agent = Agent(
            name="Assistant",
            instructions="You are a helpful assistant.",
            model="gpt-4o",
            tools=[spotify_search_tool, fuzzy_match_tool]
        )

        result = await Runner.run(agent, input=prompt)
        return result.final_output
```

**What happens**:
- Model invocations execute as Temporal activities (durable)
- Tool calls execute as activities (with retries)
- Agent state is persisted in Temporal
- Can resume from any point after failure

### 5. ModelActivityParameters

**Purpose**: Configure activity-level parameters for model invocations.

```python
from temporalio.contrib.openai_agents import OpenAIAgentsPlugin, ModelActivityParameters

plugin = OpenAIAgentsPlugin(
    model_activity_parameters=ModelActivityParameters(
        start_to_close_timeout=timedelta(minutes=5),  # Max duration
        retry_policy=RetryPolicy(
            maximum_attempts=3,
            initial_interval=timedelta(seconds=2),
            backoff_coefficient=2.0,
        ),
    )
)
```

---

## Migration Path

### Phase 1: Add SDK and Plugin (No Code Changes)

**Goal**: Install SDK and verify compatibility.

**Steps**:

1. **Install dependencies**:
```bash
pip install "temporalio[openai-agents]"
pip install openai-agents
```

2. **Add plugin to worker** (non-breaking):
```python
# In workers/music_sync_worker.py
from temporalio.contrib.openai_agents import OpenAIAgentsPlugin

worker = Worker(
    client,
    task_queue=settings.task_queue_name,
    workflows=[MusicSyncWorkflow],  # Existing workflow still works
    activities=[...],
    plugins=[OpenAIAgentsPlugin()],  # Add plugin
)
```

3. **Test**: Verify existing workflows still work.

**Effort**: 30 minutes
**Risk**: Low (plugin is backward compatible)

---

### Phase 2: Convert One Activity to Tool (Pilot)

**Goal**: Prove the pattern works with one activity.

**Steps**:

1. **Create tool wrapper** for `spotify_search`:

```python
# In activities/spotify_search.py
from temporalio import activity
from temporalio.contrib.openai_agents import activity_as_tool

@activity.defn(name="spotify-search")
async def spotify_search_activity(
    query: str,
    limit: int = 10
) -> list[dict]:
    """Search Spotify for tracks.

    Args:
        query: Search query string
        limit: Maximum results to return

    Returns:
        List of track dictionaries
    """
    # ... existing implementation
    pass

# Convert to tool
spotify_search_tool = activity_as_tool(
    spotify_search_activity,
    description="Search Spotify for tracks by query. Returns list of tracks with metadata."
)
```

2. **Create simple agent workflow** (parallel to existing):

```python
# In workflows/agent_workflow.py
from temporalio import workflow
from openai_agents import Agent, Runner
from activities.spotify_search import spotify_search_tool

@workflow.defn
class SimpleAgentWorkflow:
    """Pilot workflow using OpenAI Agents SDK."""

    @workflow.run
    async def run(self, user_prompt: str) -> str:
        """Run agent with Spotify search tool.

        Args:
            user_prompt: User's natural language request

        Returns:
            Agent's final response
        """
        agent = Agent(
            name="SpotifySearchAgent",
            instructions="""
            You help users search for music on Spotify.
            When given a song title and artist, use the spotify_search tool to find it.
            """,
            model="gpt-4o",
            tools=[spotify_search_tool]
        )

        result = await Runner.run(agent, input=user_prompt)

        return result.final_output
```

3. **Test**:
```python
# Start workflow
handle = await client.start_workflow(
    SimpleAgentWorkflow.run,
    "Find 'Bohemian Rhapsody' by Queen",
    id="test-agent-001",
    task_queue="music-sync"
)

result = await handle.result()
print(result)  # Agent's response with search results
```

4. **Verify in Temporal UI**:
- Check that `spotify-search` executed as activity
- Check model invocations also appear as activities
- Verify retries work

**Effort**: 2-3 hours
**Risk**: Low (runs in parallel to existing workflow)

---

### Phase 3: Full Multi-Agent Migration

**Goal**: Migrate entire workflow to OpenAI Agents pattern.

**Architecture**:

```python
# In workflows/enhanced_music_sync_workflow.py
from temporalio import workflow
from openai_agents import Agent, Runner, Handoff
from activities import (
    spotify_search_tool,
    fuzzy_match_tool,
    add_to_playlist_tool,
    verify_track_tool
)

@workflow.defn
class EnhancedMusicSyncWorkflow:
    """Multi-agent workflow for music sync."""

    @workflow.run
    async def run(self, input_data: WorkflowInput) -> WorkflowResult:
        """Orchestrate multiple agents for music sync.

        Flow:
        1. SearchAgent finds candidates
        2. MatchingAgent finds best match (with AI disambiguation)
        3. PlaylistAgent adds to playlist
        """
        workflow.logger.info(f"Starting multi-agent sync for: {input_data.song_metadata.title}")

        # Agent 1: Search Strategy Agent
        search_agent = Agent(
            name="SearchAgent",
            instructions=f"""
            You help search for music on Spotify.
            User is looking for: "{input_data.song_metadata.title}" by "{input_data.song_metadata.artist}"

            Use the spotify_search tool to find candidates.
            If you find results, hand off to MatchingAgent.
            If no results, inform user.
            """,
            model="gpt-4o",
            tools=[spotify_search_tool],
            handoffs=[
                Handoff(
                    target="MatchingAgent",
                    description="Hand off to MatchingAgent when you've found candidates"
                )
            ]
        )

        # Agent 2: Matching Agent
        matching_agent = Agent(
            name="MatchingAgent",
            instructions=f"""
            You determine the best match from Spotify candidates.

            Use fuzzy_match tool to score candidates.
            If confidence is high (>0.8), hand off to PlaylistAgent.
            If confidence is low, use your AI judgment to pick the best match.
            Consider: artist name, album, release date, popularity.

            Original song:
            - Title: {input_data.song_metadata.title}
            - Artist: {input_data.song_metadata.artist}
            - Album: {input_data.song_metadata.album}
            - Year: {input_data.song_metadata.year}
            """,
            model="gpt-4o",
            tools=[fuzzy_match_tool],
            handoffs=[
                Handoff(
                    target="PlaylistAgent",
                    description="Hand off to PlaylistAgent when you've found the best match"
                )
            ]
        )

        # Agent 3: Playlist Agent
        playlist_agent = Agent(
            name="PlaylistAgent",
            instructions=f"""
            You add tracks to Spotify playlists.

            Use add_to_playlist tool to add the track.
            Then use verify_track tool to confirm it was added.
            Report success or failure.

            Target playlist: {input_data.playlist_id}
            """,
            model="gpt-4o",
            tools=[add_to_playlist_tool, verify_track_tool]
        )

        # Run agent orchestration
        result = await Runner.run(
            search_agent,
            agents=[matching_agent, playlist_agent],
            input=f"Find and add '{input_data.song_metadata.title}' by '{input_data.song_metadata.artist}' to playlist"
        )

        # Parse result
        if "successfully added" in result.final_output.lower():
            return WorkflowResult(
                success=True,
                message=result.final_output,
                execution_time_seconds=self._get_elapsed_seconds()
            )
        else:
            return WorkflowResult(
                success=False,
                message=result.final_output,
                execution_time_seconds=self._get_elapsed_seconds()
            )
```

**Effort**: 1-2 days
**Risk**: Medium (requires testing agent handoffs)

---

### Phase 4: Integrate MCP Server Provider

**Goal**: Replace manual MCP client with SDK's MCP provider.

**Current Implementation**:
```python
# activities/spotify_search.py (current)
from mcp_client.client import MCPClient

mcp_client = MCPClient()  # Manual management
```

**New Implementation**:
```python
# workflows/enhanced_music_sync_workflow.py
from temporalio.contrib.openai_agents import StatelessMCPServerProvider
from mcp import StdioServerParameters

# Define Spotify MCP server
spotify_mcp = StatelessMCPServerProvider(
    server_id="spotify",
    server_params=StdioServerParameters(
        command="python",
        args=["-m", "spotify_mcp.server"],
        env={
            "SPOTIFY_CLIENT_ID": settings.spotify_client_id,
            "SPOTIFY_CLIENT_SECRET": settings.spotify_client_secret,
        }
    )
)

@workflow.defn
class EnhancedMusicSyncWorkflow:
    @workflow.run
    async def run(self, input_data: WorkflowInput) -> WorkflowResult:
        # Use MCP server tools directly
        agent = Agent(
            name="MusicSyncAgent",
            instructions="...",
            model="gpt-4o",
            tools=[
                spotify_mcp.as_tool("search_tracks"),
                spotify_mcp.as_tool("add_to_playlist"),
            ]
        )

        result = await Runner.run(agent, input="...")
        return result
```

**Benefits**:
- Automatic server lifecycle management
- Automatic reconnection on failure
- Built-in error handling
- Standardized MCP integration

**Effort**: 3-4 hours
**Risk**: Low (SDK handles edge cases)

---

## Implementation Examples

### Example 1: Simple Agent with Activity Tools

```python
# activities/spotify_tools.py
from temporalio import activity
from temporalio.contrib.openai_agents import activity_as_tool
from typing import List, Dict

@activity.defn(name="spotify-search")
async def spotify_search_activity(query: str, limit: int = 10) -> List[Dict]:
    """Search Spotify for tracks.

    Args:
        query: Search query
        limit: Max results

    Returns:
        List of track dictionaries
    """
    activity.logger.info(f"Searching Spotify: {query}")

    # Use MCP client (existing code)
    mcp = await get_mcp_client()
    results = await mcp.call_tool("search_tracks", {"query": query, "limit": limit})

    return parse_search_results(results)


@activity.defn(name="add-to-playlist")
async def add_to_playlist_activity(track_uri: str, playlist_id: str) -> Dict:
    """Add track to Spotify playlist.

    Args:
        track_uri: Spotify track URI
        playlist_id: Target playlist ID

    Returns:
        Result dictionary
    """
    activity.logger.info(f"Adding {track_uri} to {playlist_id}")

    mcp = await get_mcp_client()
    result = await mcp.call_tool(
        "add_to_playlist",
        {"playlist_id": playlist_id, "track_uris": [track_uri]}
    )

    return {"success": True, "track_uri": track_uri}


# Convert to tools
spotify_search_tool = activity_as_tool(
    spotify_search_activity,
    description="Search Spotify for tracks. Returns list of tracks with metadata (title, artist, album, URI)."
)

add_to_playlist_tool = activity_as_tool(
    add_to_playlist_activity,
    description="Add a track to a Spotify playlist. Requires track URI and playlist ID."
)
```

```python
# workflows/simple_agent_workflow.py
from temporalio import workflow
from openai_agents import Agent, Runner
from activities.spotify_tools import spotify_search_tool, add_to_playlist_tool

@workflow.defn
class SimpleMusicSyncWorkflow:
    """Single-agent workflow for music sync."""

    @workflow.run
    async def run(self, song_title: str, artist: str, playlist_id: str) -> str:
        """Search and add track to playlist.

        Args:
            song_title: Song title
            artist: Artist name
            playlist_id: Target playlist

        Returns:
            Agent's final message
        """
        workflow.logger.info(f"Agent sync: {song_title} by {artist}")

        agent = Agent(
            name="MusicSyncAgent",
            instructions=f"""
            You help users add music to Spotify playlists.

            Task:
            1. Search for "{song_title}" by "{artist}" using spotify_search
            2. Pick the best match (consider artist match, popularity, release date)
            3. Add the track to playlist using add_to_playlist

            Target playlist: {playlist_id}

            Report what you did and confirm success.
            """,
            model="gpt-4o",
            tools=[spotify_search_tool, add_to_playlist_tool]
        )

        result = await Runner.run(
            agent,
            input=f"Find and add '{song_title}' by '{artist}' to my playlist"
        )

        return result.final_output
```

**Worker Registration**:
```python
# workers/music_sync_worker.py
from temporalio.worker import Worker
from temporalio.contrib.openai_agents import OpenAIAgentsPlugin
from workflows.simple_agent_workflow import SimpleMusicSyncWorkflow
from activities.spotify_tools import spotify_search_activity, add_to_playlist_activity

worker = Worker(
    client,
    task_queue="music-sync",
    workflows=[SimpleMusicSyncWorkflow],
    activities=[
        spotify_search_activity,
        add_to_playlist_activity,
    ],
    plugins=[OpenAIAgentsPlugin()]
)
```

**API Endpoint**:
```python
# api/app.py
@app.post("/api/v1/agent-sync")
async def agent_sync(request: AgentSyncRequest):
    """Sync track using AI agent."""
    workflow_id = f"agent-sync-{uuid.uuid4()}"

    handle = await client.start_workflow(
        SimpleMusicSyncWorkflow.run,
        args=[request.song_title, request.artist, request.playlist_id],
        id=workflow_id,
        task_queue="music-sync"
    )

    return {"workflow_id": workflow_id}
```

---

### Example 2: Multi-Agent with Handoffs

```python
# workflows/multi_agent_workflow.py
from temporalio import workflow
from openai_agents import Agent, Runner, Handoff
from activities.spotify_tools import *

@workflow.defn
class MultiAgentMusicSyncWorkflow:
    """Multi-agent workflow with specialized roles."""

    @workflow.run
    async def run(self, input_data: WorkflowInput) -> WorkflowResult:
        """Orchestrate multiple agents."""

        # Agent 1: Search Specialist
        search_agent = Agent(
            name="SearchAgent",
            instructions=f"""
            You are a Spotify search specialist.

            Your ONLY job is to search for:
            - Title: {input_data.song_metadata.title}
            - Artist: {input_data.song_metadata.artist}

            Use spotify_search and report what you found.
            Then hand off to MatchingAgent.
            """,
            model="gpt-4o",
            tools=[spotify_search_tool],
            handoffs=[Handoff(target="MatchingAgent")]
        )

        # Agent 2: Matching Specialist
        matching_agent = Agent(
            name="MatchingAgent",
            instructions=f"""
            You are a music matching specialist.

            Analyze the search results and pick the BEST match for:
            - Original: {input_data.song_metadata.title} by {input_data.song_metadata.artist}
            - Album: {input_data.song_metadata.album}
            - Year: {input_data.song_metadata.year}

            Use fuzzy_match to score, but also use your judgment.
            Consider: exact artist match, album match, release year proximity, popularity.

            When confident, hand off to PlaylistAgent with the track URI.
            """,
            model="gpt-4o",
            tools=[fuzzy_match_tool],
            handoffs=[Handoff(target="PlaylistAgent")]
        )

        # Agent 3: Playlist Specialist
        playlist_agent = Agent(
            name="PlaylistAgent",
            instructions=f"""
            You are a playlist management specialist.

            Add the track to playlist: {input_data.playlist_id}

            Steps:
            1. Use add_to_playlist with the track URI
            2. Use verify_track to confirm it was added
            3. Report success

            If anything fails, explain what went wrong.
            """,
            model="gpt-4o",
            tools=[add_to_playlist_tool, verify_track_tool]
        )

        # Run agent orchestration
        workflow.logger.info("Starting multi-agent orchestration")

        result = await Runner.run(
            search_agent,
            agents=[matching_agent, playlist_agent],
            input=f"Sync this track to playlist"
        )

        # Parse result and return
        success = "success" in result.final_output.lower()

        return WorkflowResult(
            success=success,
            message=result.final_output,
            execution_time_seconds=self._get_elapsed_seconds()
        )
```

**Benefits of Multi-Agent Pattern**:
- Each agent has focused expertise
- Clear separation of concerns
- Easier to test individual agents
- Can swap out agents (e.g., different matching strategies)
- Better observability (see which agent made decisions)

---

### Example 3: MCP Server Integration

```python
# workflows/mcp_integrated_workflow.py
from temporalio import workflow
from temporalio.contrib.openai_agents import StatelessMCPServerProvider
from openai_agents import Agent, Runner
from mcp import StdioServerParameters
from config.settings import settings

# Define Spotify MCP server
spotify_mcp_server = StatelessMCPServerProvider(
    server_id="spotify",
    server_params=StdioServerParameters(
        command="python",
        args=["-m", "spotify_mcp.server"],
        env={
            "SPOTIFY_CLIENT_ID": settings.spotify_client_id,
            "SPOTIFY_CLIENT_SECRET": settings.spotify_client_secret,
        }
    )
)

@workflow.defn
class MCPIntegratedWorkflow:
    """Workflow using MCP server directly."""

    @workflow.run
    async def run(self, song_title: str, artist: str, playlist_id: str) -> str:
        """Use MCP server tools directly."""

        # Agent uses MCP tools directly
        agent = Agent(
            name="SpotifyAgent",
            instructions=f"""
            Find "{song_title}" by "{artist}" and add to playlist {playlist_id}.

            Steps:
            1. Use search_tracks to find the song
            2. Use add_to_playlist to add it
            3. Confirm success
            """,
            model="gpt-4o",
            # MCP tools are automatically available
            mcp_servers=[spotify_mcp_server]
        )

        result = await Runner.run(
            agent,
            input="Complete the task"
        )

        return result.final_output
```

**Benefits**:
- No manual MCP client management
- Automatic server lifecycle (start, stop, restart)
- Built-in error handling
- Tools automatically registered with agent

---

## MCP Server Integration

### Option 1: Wrap Existing MCP Client as Activity

**Current State**: You have `mcp_client/client.py` that manages MCP connection.

**Approach**: Keep existing client, wrap calls as activities.

```python
# activities/mcp_activities.py
from temporalio import activity
from temporalio.contrib.openai_agents import activity_as_tool
from mcp_client.client import MCPClient

async def get_mcp_client() -> MCPClient:
    """Get or create MCP client."""
    # Existing implementation
    pass

@activity.defn(name="mcp-search-tracks")
async def mcp_search_tracks_activity(query: str, limit: int = 10) -> list:
    """Search tracks via MCP."""
    client = await get_mcp_client()
    result = await client.call_tool("search_tracks", {"query": query, "limit": limit})
    return result

# Convert to tool
mcp_search_tool = activity_as_tool(
    mcp_search_tracks_activity,
    description="Search Spotify via MCP"
)
```

**Pros**:
- Minimal changes to existing code
- Keep current MCP client logic
- Quick migration

**Cons**:
- Manual lifecycle management
- No automatic recovery from MCP server crashes

---

### Option 2: Use SDK's MCP Server Provider (Recommended)

**Approach**: Replace manual MCP client with SDK's provider.

```python
# workflows/mcp_workflow.py
from temporalio import workflow
from temporalio.contrib.openai_agents import StatelessMCPServerProvider
from openai_agents import Agent, Runner
from mcp import StdioServerParameters

@workflow.defn
class MCPMusicSyncWorkflow:
    @workflow.run
    async def run(self, song_title: str, artist: str, playlist_id: str) -> str:
        # Define MCP server inline
        spotify_mcp = StatelessMCPServerProvider(
            server_id="spotify",
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

        # Agent with MCP server
        agent = Agent(
            name="SpotifyAgent",
            instructions=f"""
            Your task: Find and add "{song_title}" by "{artist}" to playlist {playlist_id}.

            Available MCP tools:
            - search_tracks: Search for songs
            - add_to_playlist: Add tracks to playlist
            - get_playlist: Get playlist details

            Complete the task step by step.
            """,
            model="gpt-4o",
            mcp_servers=[spotify_mcp]
        )

        result = await Runner.run(agent, input="Complete the music sync task")
        return result.final_output
```

**Pros**:
- Automatic server lifecycle management
- Auto-restart on crashes
- Standardized error handling
- Better observability

**Cons**:
- Requires refactoring MCP client usage
- Need to verify MCP server is stateless

---

### Determining If MCP Server is Stateless

**Stateless** (use `StatelessMCPServerProvider`):
- Each tool call is independent
- No session state between calls
- Can be restarted without data loss
- Example: Spotify API calls (search, add to playlist)

**Stateful** (use `StatefulMCPServerProvider`):
- Maintains session state
- Tool calls depend on previous calls
- Restart loses session
- Example: Database connections, shopping cart sessions

**For Spotify MCP**: Likely **stateless** if:
- OAuth tokens are refreshed per call
- No conversation state maintained
- Each tool call is independent

**Test**:
```python
# Test if MCP server is stateless
# 1. Call search_tracks
# 2. Restart MCP server
# 3. Call add_to_playlist
# If step 3 works independently → stateless
```

---

## Testing with SDK Utilities

The SDK provides testing utilities in `temporalio.contrib.openai_agents.testing`.

### Testing Agent Workflows

```python
# tests/test_agent_workflows.py
import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from temporalio.contrib.openai_agents import OpenAIAgentsPlugin
from workflows.simple_agent_workflow import SimpleMusicSyncWorkflow
from activities.spotify_tools import *

@pytest.mark.asyncio
async def test_agent_workflow_success():
    """Test agent successfully syncs track."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[SimpleMusicSyncWorkflow],
            activities=[spotify_search_activity, add_to_playlist_activity],
            plugins=[OpenAIAgentsPlugin()]
        ):
            # Start workflow
            result = await env.client.execute_workflow(
                SimpleMusicSyncWorkflow.run,
                args=["Bohemian Rhapsody", "Queen", "playlist_123"],
                id="test-workflow-001",
                task_queue="test-queue"
            )

            # Verify result
            assert "success" in result.lower()
            assert "bohemian rhapsody" in result.lower()


@pytest.mark.asyncio
async def test_agent_handles_no_results():
    """Test agent handles no search results."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        # Mock activity to return empty results
        async def mock_search(query: str, limit: int = 10):
            return []

        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[SimpleMusicSyncWorkflow],
            activities=[mock_search, add_to_playlist_activity],
            plugins=[OpenAIAgentsPlugin()]
        ):
            result = await env.client.execute_workflow(
                SimpleMusicSyncWorkflow.run,
                args=["NonexistentSong123", "UnknownArtist", "playlist_123"],
                id="test-workflow-002",
                task_queue="test-queue"
            )

            # Agent should report no results found
            assert "not found" in result.lower() or "no results" in result.lower()
```

### Testing Activity Tools

```python
# tests/test_activity_tools.py
import pytest
from activities.spotify_tools import spotify_search_activity

@pytest.mark.asyncio
async def test_spotify_search_activity():
    """Test Spotify search activity directly."""
    results = await spotify_search_activity(
        query="Bohemian Rhapsody Queen",
        limit=5
    )

    assert len(results) > 0
    assert any("queen" in r["artist"].lower() for r in results)


@pytest.mark.asyncio
async def test_add_to_playlist_activity():
    """Test add to playlist activity."""
    result = await add_to_playlist_activity(
        track_uri="spotify:track:test123",
        playlist_id="playlist_test"
    )

    assert result["success"] is True
```

### Testing MCP Integration

```python
# tests/test_mcp_integration.py
import pytest
from temporalio.contrib.openai_agents import StatelessMCPServerProvider
from mcp import StdioServerParameters

@pytest.mark.asyncio
async def test_mcp_server_lifecycle():
    """Test MCP server starts and stops correctly."""
    server = StatelessMCPServerProvider(
        server_id="test-spotify",
        server_params=StdioServerParameters(
            command="python",
            args=["-m", "spotify_mcp.server"],
            env={"SPOTIFY_CLIENT_ID": "test", "SPOTIFY_CLIENT_SECRET": "test"}
        )
    )

    # Server starts automatically when tools are accessed
    # (SDK handles lifecycle)

    # Verify server tools are available
    # ... test logic
```

---

## Production Deployment

### 1. Environment Setup

```bash
# Install dependencies
pip install "temporalio[openai-agents]"
pip install openai-agents

# Set environment variables
export OPENAI_API_KEY="..."
export SPOTIFY_CLIENT_ID="..."
export SPOTIFY_CLIENT_SECRET="..."
export TEMPORAL_HOST="..."
export TEMPORAL_NAMESPACE="..."
```

### 2. Worker Configuration

```python
# workers/production_worker.py
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.contrib.openai_agents import (
    OpenAIAgentsPlugin,
    ModelActivityParameters
)
from datetime import timedelta
from temporalio.common import RetryPolicy

async def run_production_worker():
    """Production worker with OpenAI Agents plugin."""
    client = await Client.connect(settings.temporal_host)

    # Configure plugin
    plugin = OpenAIAgentsPlugin(
        model_activity_parameters=ModelActivityParameters(
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=2),
                backoff_coefficient=2.0,
                maximum_interval=timedelta(seconds=30),
            )
        )
    )

    worker = Worker(
        client,
        task_queue="music-sync-prod",
        workflows=[
            SimpleMusicSyncWorkflow,
            MultiAgentMusicSyncWorkflow,
            MCPIntegratedWorkflow,
        ],
        activities=[
            spotify_search_activity,
            fuzzy_match_activity,
            add_to_playlist_activity,
            verify_track_activity,
        ],
        plugins=[plugin],
        max_concurrent_workflow_tasks=100,
        max_concurrent_activities=200,
    )

    print("Production worker starting...")
    await worker.run()

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_production_worker())
```

### 3. Monitoring

```python
# monitoring/agent_metrics.py
from prometheus_client import Counter, Histogram

# Agent-specific metrics
agent_invocations = Counter(
    'openai_agent_invocations_total',
    'Total agent invocations',
    ['agent_name', 'status']
)

agent_duration = Histogram(
    'openai_agent_duration_seconds',
    'Agent execution duration',
    ['agent_name']
)

agent_handoffs = Counter(
    'openai_agent_handoffs_total',
    'Agent handoffs',
    ['from_agent', 'to_agent']
)

model_invocations = Counter(
    'openai_model_invocations_total',
    'Model API calls',
    ['model', 'status']
)

tool_invocations = Counter(
    'openai_tool_invocations_total',
    'Tool invocations',
    ['tool_name', 'status']
)
```

### 4. Error Handling

```python
# Common error patterns
from temporalio.exceptions import ApplicationError

class AgentError(ApplicationError):
    """Base error for agent workflows."""
    def __init__(self, message: str, details: dict = None):
        super().__init__(
            message,
            details=details,
            type="AgentError",
            non_retryable=False
        )


class MCPServerError(ApplicationError):
    """MCP server communication error."""
    def __init__(self, message: str):
        super().__init__(
            message,
            type="MCPServerError",
            non_retryable=False  # Will retry
        )


class NoMatchFoundError(ApplicationError):
    """No suitable match found."""
    def __init__(self, query: str):
        super().__init__(
            f"No match found for: {query}",
            type="NoMatchFoundError",
            non_retryable=True  # Don't retry
        )
```

### 5. Feature Flags

```python
# config/settings.py
class Settings(BaseSettings):
    # Feature flags
    use_agent_sdk: bool = False  # Enable OpenAI Agents SDK
    use_mcp_provider: bool = False  # Use SDK's MCP provider
    use_multi_agent: bool = False  # Use multi-agent pattern

    # Agent configuration
    agent_model: str = "gpt-4o"
    agent_temperature: float = 0.7
    max_agent_iterations: int = 10

    # Rollout percentage (0-100)
    agent_rollout_percentage: int = 0  # Canary rollout
```

```python
# Conditional execution
if settings.use_agent_sdk and random.randint(1, 100) <= settings.agent_rollout_percentage:
    # Use new agent workflow
    workflow_class = MultiAgentMusicSyncWorkflow
else:
    # Use existing workflow
    workflow_class = MusicSyncWorkflow
```

---

## Migration Checklist

### Phase 1: Foundation (Week 1)
- [ ] Install `temporalio[openai-agents]` and `openai-agents`
- [ ] Add `OpenAIAgentsPlugin` to worker
- [ ] Verify existing workflows still work
- [ ] Add feature flags for gradual rollout

### Phase 2: Pilot (Week 2)
- [ ] Convert one activity to tool (`spotify_search`)
- [ ] Create simple agent workflow
- [ ] Test in dev environment
- [ ] Verify Temporal UI shows activities correctly
- [ ] Test retry behavior

### Phase 3: Multi-Agent (Week 3-4)
- [ ] Design multi-agent architecture
- [ ] Implement search agent
- [ ] Implement matching agent
- [ ] Implement playlist agent
- [ ] Test agent handoffs
- [ ] Add monitoring and metrics

### Phase 4: MCP Integration (Week 5)
- [ ] Evaluate if Spotify MCP is stateless
- [ ] Migrate to `StatelessMCPServerProvider`
- [ ] Test MCP server lifecycle
- [ ] Remove manual MCP client code
- [ ] Verify error handling

### Phase 5: Production (Week 6)
- [ ] Canary deployment (5% traffic)
- [ ] Monitor metrics
- [ ] Gradually increase to 25%, 50%, 100%
- [ ] Deprecate old workflow
- [ ] Update documentation

---

## Comparison: Before vs. After

| Aspect | Before (Current) | After (With SDK) |
|--------|------------------|------------------|
| **Architecture** | Manual Temporal workflow | OpenAI Agents SDK + Temporal |
| **AI Calls** | LangChain/Claude SDK in activities | Built-in durable model invocations |
| **Tool Management** | Manual activity definitions | `activity_as_tool()` wrapper |
| **MCP Integration** | Manual client management | `StatelessMCPServerProvider` |
| **Error Handling** | Custom retry policies | Built-in with SDK defaults |
| **Observability** | Logs + Temporal UI | Logs + Temporal UI + OpenAI tracing |
| **Agent Patterns** | Single workflow | Multi-agent with handoffs |
| **Testing** | Manual workflow tests | SDK testing utilities |
| **Code Complexity** | ~500 lines | ~300 lines (SDK abstracts patterns) |

---

## Key Takeaways

1. **SDK provides higher-level abstractions** for common AI agent patterns
2. **activity_as_tool()** makes existing activities durable agent tools
3. **MCP server providers** simplify integration and lifecycle management
4. **Multi-agent patterns** enable specialized agents with clear responsibilities
5. **Built-in durability** for model invocations and tool calls
6. **Gradual migration** is possible (run old and new workflows in parallel)

---

## Next Steps

1. **Review this guide** with the team
2. **Start with Phase 1** (install SDK and plugin)
3. **Pilot with one agent** (Phase 2)
4. **Gather feedback** and iterate
5. **Gradually migrate** to full multi-agent architecture

---

**Document Version**: 1.0
**Last Updated**: 2025-11-17
**Status**: Ready for Implementation
