# Agent SDK + MCP Server Integration

This document explains how the Claude Agent SDK intelligently orchestrates your Spotify MCP server.

## Architecture

```
┌─────────────────┐
│   iOS/User      │
│   Shortcuts     │
└────────┬────────┘
         │ HTTP POST /api/v1/sync
         ↓
┌─────────────────────────────────────────┐
│   FastAPI Server (app_agent.py)         │
│   - Receives song requests              │
│   - Calls Agent SDK                     │
│   - Returns structured results          │
└────────┬────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────────┐
│   Agent Executor (agent_executor.py)    │
│   - Uses Claude Agent SDK               │
│   - Natural language orchestration      │
└────────┬────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────────┐
│   Claude (via Agent SDK)                │
│   - Receives: "Search for X and add    │
│     it to playlist Y"                   │
│   - Decides which MCP tools to use      │
│   - Intelligently picks best match      │
│   - Chains multiple operations          │
└────────┬────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────────┐
│   MCP Server (spotify_server.py)        │
│   - Exposes Spotify tools via MCP       │
│   - search_track                        │
│   - add_track_to_playlist               │
│   - verify_track_added                  │
│   - get_user_playlists                  │
│   - search_by_isrc                      │
└────────┬────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────────┐
│   Spotify API                           │
│   - Actual music operations             │
└─────────────────────────────────────────┘
```

## Why Use Agent SDK Instead of Direct MCP Calls?

### Traditional Approach (Custom Client)
```python
# Manual orchestration - you decide the logic
results = await search_track(query)
best_match = pick_best_match(results)  # Your code
await add_to_playlist(best_match.uri, playlist_id)
```

### Agent SDK Approach (AI Orchestration)
```python
# Claude decides the logic intelligently
result = await execute_music_sync_with_agent(
    song_metadata=song,
    playlist_id=playlist_id
)
# Claude:
# 1. Searches Spotify
# 2. Analyzes ALL results with context
# 3. Picks the BEST match (considering artist, album, year, popularity)
# 4. Adds to playlist
# 5. Verifies success
# 6. Returns structured response
```

### Benefits

**1. Intelligent Disambiguation**
- Claude analyzes multiple candidates
- Considers context (artist name variations, remasters vs originals, live vs studio)
- Uses reasoning to pick the best match
- **Replaces your entire AI disambiguation activity!**

**2. Natural Language Control**
- Change behavior by modifying the system prompt
- No code changes needed for new matching logic
- Easy to add business rules

**3. Error Handling**
- Claude can retry failed operations
- Adapts to API responses
- Provides detailed reasoning for failures

**4. Multi-Step Workflows**
- Claude chains operations automatically
- "Find X and add to playlist Y" = multiple MCP tool calls
- Future: "Create a playlist of similar songs"

## Installation

### 1. Install Dependencies

```bash
# Install Claude Agent SDK
pip install claude-agent-sdk

# Install Claude Code CLI (required by Agent SDK)
npm install -g @anthropic-ai/claude-code

# Install httpx for testing
pip install httpx
```

### 2. Verify Installation

```bash
# Check Claude Code CLI
claude --version

# Check Agent SDK
python3 -c "import claude_agent_sdk; print('Agent SDK installed')"
```

## Usage

### Option 1: Run the Agent-Powered API Server

**Terminal 1: Start API Server**
```bash
python3 api/app_agent.py
```

**Terminal 2: Test the API**
```bash
python3 test_agent_api.py
```

### Option 2: Use Agent Directly (No API)

```python
from agent_executor import execute_music_sync_with_agent
from models.data_models import SongMetadata

song = SongMetadata(
    title="Never Gonna Give You Up",
    artist="Rick Astley",
    album="Whenever You Need Somebody"
)

result = await execute_music_sync_with_agent(
    song_metadata=song,
    playlist_id="YOUR_PLAYLIST_ID",
    use_ai_disambiguation=True
)

print(f"Success: {result.success}")
print(f"Matched: {result.matched_track_name} by {result.matched_artist}")
print(f"Reasoning: {result.agent_reasoning}")
```

### Option 3: Interactive Demo

```bash
python3 agent_spotify_demo.py
```

Then try commands like:
- "Search for Bohemian Rhapsody by Queen"
- "Show me my playlists"
- "Find Hotel California and add it to my first playlist"

## API Endpoints

### POST /api/v1/sync

Start a song sync operation.

**Request:**
```json
{
  "track_name": "Never Gonna Give You Up",
  "artist": "Rick Astley",
  "album": "Whenever You Need Somebody",
  "playlist_id": "43X1N9GAKwVARreGxSAdZI",
  "user_id": "test_user",
  "use_ai_disambiguation": true
}
```

**Response:**
```json
{
  "workflow_id": "agent-sync-test_user-1234567890-abc12",
  "status": "accepted",
  "message": "Agent is searching for 'Never Gonna Give You Up' by Rick Astley...",
  "status_url": "/api/v1/sync/agent-sync-test_user-1234567890-abc12"
}
```

### GET /api/v1/sync/{workflow_id}

Get sync operation status and results.

**Response (Success):**
```json
{
  "workflow_id": "agent-sync-test_user-1234567890-abc12",
  "status": "completed",
  "message": "Successfully synced 'Never Gonna Give You Up' by Rick Astley",
  "result": {
    "matched_track_uri": "spotify:track:4PTG3Z6ehGkBFwjybzWkR8",
    "matched_track_name": "Never Gonna Give You Up",
    "matched_artist": "Rick Astley",
    "confidence_score": 0.98,
    "match_method": "exact_match",
    "agent_reasoning": "This is the original 1987 studio version from the album 'Whenever You Need Somebody', matching all provided metadata exactly."
  },
  "execution_time_seconds": 8.5
}
```

## Configuration

### Customize Agent Behavior

Edit `agent_executor.py` system prompt:

```python
system_prompt={
    "type": "preset",
    "preset": "claude_code",
    "append": """
    Custom instructions:
    - Always prefer the highest quality version
    - Avoid remixes unless explicitly requested
    - Prefer album versions over singles
    """
}
```

### Allowed Tools

Control which MCP tools Claude can use:

```python
allowed_tools=[
    "mcp__spotify__search_track",      # Required
    "mcp__spotify__add_track_to_playlist",  # Required
    "mcp__spotify__verify_track_added",     # Optional
    "mcp__spotify__get_user_playlists",     # Optional
]
```

## Comparison with Previous Approaches

### vs. Standalone Executor (`standalone_executor.py`)

| Feature | Standalone Executor | Agent SDK |
|---------|-------------------|-----------|
| Disambiguation Logic | Hardcoded fuzzy matching | AI reasoning |
| Adding New Rules | Modify Python code | Update system prompt |
| Error Handling | Manual retry logic | Claude adapts |
| Extensibility | Limited | Natural language control |

### vs. Temporal Workflows (`workflows/music_sync_workflow.py`)

| Feature | Temporal | Agent SDK |
|---------|----------|-----------|
| Infrastructure | Requires Temporal server | Just Claude Code CLI |
| Complexity | Complex workflow definitions | Natural language prompts |
| Disambiguation | Separate AI activity | Built into Claude's reasoning |
| Deployment | Docker, PostgreSQL | Single Python process |

## Environment Variables

Same as before:

```bash
# Spotify credentials
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback

# Not needed for Agent approach (Claude is the AI!)
# ANTHROPIC_API_KEY=...  # Not used
# AI_PROVIDER=...         # Not used
```

## Troubleshooting

### "Claude Code not found"

Install the CLI:
```bash
npm install -g @anthropic-ai/claude-code
```

### "ModuleNotFoundError: No module named 'claude_agent_sdk'"

Install the SDK:
```bash
pip install claude-agent-sdk
```

### Agent takes too long

- The first run may be slower (Claude is thinking)
- Subsequent runs are faster
- Adjust `max_turns` in `ClaudeAgentOptions`

### Unexpected matches

- Review the system prompt in `agent_executor.py`
- Add more specific matching criteria
- Check Claude's reasoning in the response

## Next Steps

1. **Test the Agent API**
   ```bash
   python3 api/app_agent.py  # Terminal 1
   python3 test_agent_api.py # Terminal 2
   ```

2. **Try the Interactive Demo**
   ```bash
   python3 agent_spotify_demo.py
   ```

3. **Integrate with iOS Shortcuts**
   - Update your shortcut to use the new API endpoints
   - The response format is compatible

4. **Customize for Your Use Case**
   - Edit system prompts
   - Add new MCP tools
   - Modify response parsing

## Summary

**Before (Manual Orchestration):**
```
API → Standalone Executor → Manual logic → MCP Server → Spotify
```

**After (AI Orchestration):**
```
API → Agent Executor → Claude (decides) → MCP Server → Spotify
```

**Key Benefit:** Claude's intelligence replaces your entire disambiguation, matching, and orchestration logic with natural language reasoning!
