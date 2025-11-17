# Deprecated Code Archive

**Archived:** November 17, 2025

This directory contains code from previous architectural implementations that have been superseded by the **Agent SDK** approach.

---

## Why Deprecated?

The project has evolved through multiple architectures:

1. **Phase 1: Temporal Workflows** (Initial implementation)
   - Complex workflow orchestration with Temporal
   - Required Docker, PostgreSQL, workers, activities
   - ~500 lines of orchestration code
   - High infrastructure overhead

2. **Phase 2: Standalone Executor** (Simplified)
   - Removed Temporal dependency
   - Still required manual orchestration
   - Separate Claude API calls
   - ~300 lines of code

3. **Phase 3: Agent SDK** (Current - RECOMMENDED)
   - Built-in AI reasoning and tool orchestration
   - Simple MCP-based architecture
   - ~150 lines of clean code
   - No complex infrastructure needed

**See [MIGRATION_GUIDE.md](../MIGRATION_GUIDE.md) for detailed comparison and migration steps.**

---

## Deprecated Components

### `api/app.py`
- **Was:** Temporal-based FastAPI server
- **Replaced by:** `api/app_agent.py` (Agent SDK server)
- **Why:** Agent SDK eliminates need for Temporal workflows

### `workflows/music_sync_workflow.py`
- **Was:** Temporal workflow orchestration
- **Replaced by:** `agent_executor.py` (Agent SDK executor)
- **Why:** Agent SDK handles orchestration automatically

### `workers/music_sync_worker.py`
- **Was:** Temporal worker process
- **Replaced by:** Background tasks in FastAPI
- **Why:** No worker needed with Agent SDK

### `activities/`
- **Was:** Individual Temporal activities
  - `spotify_search.py` - Search Spotify
  - `ai_disambiguator.py` - AI matching
  - `fuzzy_matcher.py` - Fuzzy matching
  - `playlist_manager.py` - Playlist operations
- **Replaced by:** MCP server tools in `mcp_server/spotify_server.py`
- **Why:** MCP provides cleaner tool interface, Agent SDK handles AI automatically

### `executors/standalone_executor.py`
- **Was:** Non-Temporal workflow executor
- **Replaced by:** `agent_executor.py` (Agent SDK executor)
- **Why:** Agent SDK provides better orchestration with less code

---

## Should You Use This Code?

**No.** Use the Agent SDK implementation instead.

### If you're new to this project:
✅ Start with [AGENT_INTEGRATION.md](../AGENT_INTEGRATION.md)
✅ Use `api/app_agent.py` for the API server
✅ Use `agent_executor.py` for agent logic

### If you're migrating from old code:
✅ See [MIGRATION_GUIDE.md](../MIGRATION_GUIDE.md)
✅ Update environment variables (remove Temporal vars)
✅ Test with new Agent SDK approach

### If you need the old behavior:
⚠️ Consider adapting Agent SDK instead (change system prompt)
⚠️ This deprecated code is unmaintained and may have bugs
⚠️ Dependencies may be outdated or incompatible

---

## Code Comparison

### Old (Temporal Workflow)

**Total files:** 10
**Total lines:** ~500
**Infrastructure:** Docker, Temporal, PostgreSQL, Workers
**Complexity:** Very High

```python
# workflows/music_sync_workflow.py
@workflow.defn
class MusicSyncWorkflow:
    @workflow.run
    async def run(self, request: SyncRequest) -> SyncResponse:
        search_result = await workflow.execute_activity(search_track_activity, ...)
        match_result = await workflow.execute_activity(ai_disambiguate_activity, ...)
        add_result = await workflow.execute_activity(add_to_playlist_activity, ...)
        return add_result
```

### New (Agent SDK)

**Total files:** 3
**Total lines:** ~150
**Infrastructure:** Just FastAPI
**Complexity:** Low

```python
# agent_executor.py
def execute_music_sync(track_name, artist, playlist_id):
    agent = Agent(
        model="claude-sonnet-4-5",
        system_prompt="Search track and add to playlist...",
        allowed_tools=["mcp__spotify__search_track", ...]
    )
    return agent.run(f"Add '{track_name}' by {artist}")
```

---

## Performance Comparison

| Metric | Temporal | Standalone | Agent SDK (Current) |
|--------|----------|-----------|---------------------|
| Speed | 10-15s | 8-12s | 20-25s |
| Match Quality | ~80% | ~80% | 99% |
| Code Complexity | Very High | Medium | Low |
| Infrastructure | Docker + Temporal | Minimal | Minimal |
| Maintainability | Low | Medium | High |

**Agent SDK is slower but produces significantly better results with less code.**

---

## When Was This Archived?

- **Date:** November 17, 2025
- **Last working commit:** See git history for `_deprecated/` files
- **Reason:** Agent SDK provides superior architecture

---

## Can I Delete This Directory?

**Yes**, after verifying your Agent SDK implementation works correctly:

1. Test Agent SDK thoroughly:
   ```bash
   python tests/integration/test_agent_performance.py
   python tests/integration/test_agent_api.py
   ```

2. Verify all features work as expected

3. Keep a backup (git history) if needed

4. Delete `_deprecated/`:
   ```bash
   rm -rf _deprecated/
   ```

---

## Need Help Migrating?

- **Architecture Comparison:** [MIGRATION_GUIDE.md](../MIGRATION_GUIDE.md)
- **Agent SDK Guide:** [AGENT_INTEGRATION.md](../AGENT_INTEGRATION.md)
- **Project Structure:** [PROJECT_STRUCTURE.md](../PROJECT_STRUCTURE.md)
- **Performance Analysis:** [PERFORMANCE_TEST_RESULTS.md](../PERFORMANCE_TEST_RESULTS.md)

---

## Historical Context

### Why Temporal Was Chosen Initially

Temporal provided:
- Durable execution
- Advanced retry logic
- Workflow orchestration
- State management

### Why Temporal Was Abandoned

- Too complex for this use case
- Overkill for simple music syncing
- High infrastructure overhead
- Agent SDK provides better AI integration

### Why Agent SDK Is Better

- **Simpler:** No Docker, workers, or activities
- **Smarter:** Built-in AI reasoning (99% confidence vs ~80%)
- **Cleaner:** MCP tools instead of manual activities
- **Maintainable:** Change behavior with prompts, not code

---

**For current implementation, see:**
- `api/app_agent.py` - FastAPI server
- `agent_executor.py` - Agent SDK executor
- `mcp_server/spotify_server.py` - MCP tools

**Last Updated:** November 17, 2025
**Status:** ⚠️ Deprecated - Use Agent SDK instead
