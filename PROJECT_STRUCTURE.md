# Project Structure

**Last Updated:** November 17, 2025

This document provides a complete overview of the project's directory structure, explaining the purpose of each component and which files are current vs deprecated.

---

## 📊 Quick Reference

| Status | Meaning | Color |
|--------|---------|-------|
| ✅ **CURRENT** | Primary implementation (Agent SDK) | Green |
| ⚠️ **DEPRECATED** | Legacy code (Temporal/Standalone) | Yellow |
| 🧪 **TEST** | Testing files | Blue |
| 📚 **DOCS** | Documentation | Purple |

---

## 🗂️ Directory Structure

```
spotify-mcp-integration/
├── 📁 api/                          ✅ API server implementations
│   ├── __init__.py
│   ├── app_agent.py                 ✅ CURRENT: Agent SDK FastAPI server
│   ├── app.py                       ⚠️ DEPRECATED: Temporal-based API
│   └── models.py                    ✅ Shared API models (SyncRequest, SyncResponse)
│
├── 📁 mcp_server/                   ✅ MCP server implementation
│   ├── __init__.py
│   └── spotify_server.py            ✅ Spotify MCP server (tools: search, add, verify)
│
├── 📁 mcp_client/                   ✅ MCP client library
│   ├── __init__.py
│   └── client.py                    ✅ Custom MCP client (used by test files)
│
├── 📁 config/                       ✅ Configuration management
│   ├── __init__.py
│   └── settings.py                  ✅ Pydantic settings (loads .env)
│
├── 📁 models/                       ✅ Data models
│   ├── __init__.py
│   └── data_models.py               ✅ TrackMatch, SpotifyTrack, MatchResult
│
├── 📁 activities/                   ⚠️ DEPRECATED: Temporal activities
│   ├── __init__.py
│   ├── ai_disambiguator.py          ⚠️ Legacy AI matching logic
│   ├── fuzzy_matcher.py             ⚠️ Legacy fuzzy matching
│   ├── playlist_manager.py          ⚠️ Legacy playlist management
│   └── spotify_search.py            ⚠️ Legacy Spotify search
│
├── 📁 workflows/                    ⚠️ DEPRECATED: Temporal workflows
│   ├── __init__.py
│   └── music_sync_workflow.py       ⚠️ Legacy Temporal workflow
│
├── 📁 workers/                      ⚠️ DEPRECATED: Temporal workers
│   ├── __init__.py
│   └── music_sync_worker.py         ⚠️ Legacy Temporal worker
│
├── 📁 executors/                    ⚠️ DEPRECATED: Standalone executor
│   ├── __init__.py
│   └── standalone_executor.py       ⚠️ Legacy non-Temporal executor
│
├── 📁 tests/                        🧪 Production test suite
│   ├── __init__.py
│   ├── conftest.py                  🧪 Pytest configuration
│   ├── integration/                 🧪 Integration tests
│   │   ├── test_api_endpoints.py
│   │   ├── test_mcp_integration.py
│   │   ├── test_spotify_search.py
│   │   └── test_workflow_integration.py
│   └── unit/                        🧪 Unit tests
│       ├── test_api_models.py
│       ├── test_data_models.py
│       ├── test_fuzzy_matcher.py
│       └── test_settings.py
│
├── 📁 scripts/                      ✅ Utility scripts
│   └── manual_spotify_auth.py       ✅ Manual Spotify OAuth flow
│
├── 📁 docs/                         📚 Additional documentation
│   ├── EXECUTION_MODES.md           📚 Explanation of execution modes
│   └── ios-shortcuts-setup.md       📚 iOS Shortcuts integration guide
│
├── 📄 Root Level Files
│   ├── agent_executor.py            ✅ CURRENT: Agent SDK executor (core logic)
│   ├── agent_spotify_demo.py        ✅ Demo script for Agent SDK
│   ├── spotify_custom_client.py     ✅ Direct MCP client (no Agent, fast)
│   ├── run.sh                       ✅ Main startup script
│   ├── .env.example                 ✅ Environment variables template
│   ├── requirements.txt             ✅ Python dependencies
│   ├── pyproject.toml               ✅ Project metadata and dependencies
│   ├── pytest.ini                   ✅ Pytest configuration
│   ├── docker-compose.yml           ✅ Docker setup (Temporal)
│   ├── prometheus.yml               ✅ Prometheus monitoring config
│   └── .gitignore                   ✅ Git ignore rules
│
├── 📚 Documentation Files
│   ├── README.md                    📚 Main project overview
│   ├── SETUP.md                     📚 Installation and setup guide
│   ├── AGENT_INTEGRATION.md         📚 Agent SDK integration guide (PRIMARY)
│   ├── ARCHITECTURE.md              📚 System architecture overview
│   ├── TESTING.md                   📚 Testing guide
│   ├── TEST_RESULTS.md              📚 Legacy test results
│   ├── PERFORMANCE_TEST_RESULTS.md  📚 Agent SDK performance results
│   └── PROJECT_STRUCTURE.md         📚 This file
│
└── 🧪 Root Level Test Files (Debugging)
    ├── test_agent_api.py            🧪 PRODUCTION: Full Agent SDK API test
    ├── test_agent_performance.py    🧪 PRODUCTION: Agent SDK performance test
    ├── test_custom_client.py        🧪 DEBUGGING: Test custom MCP client
    ├── test_debug.py                🧪 DEBUGGING: General debugging
    ├── test_debug_stdio.py          🧪 DEBUGGING: STDIO debugging
    ├── test_mcp_communication.py    🧪 DEBUGGING: MCP communication test
    ├── test_mcp_debug.py            🧪 DEBUGGING: MCP debugging
    ├── test_mcp_direct.py           🧪 DEBUGGING: Direct MCP test
    ├── test_mcp_server.py           🧪 DEBUGGING: MCP server test
    ├── test_minimal_client.py       🧪 DEBUGGING: Minimal MCP client test
    ├── test_minimal_mcp_server.py   🧪 DEBUGGING: Minimal MCP server test
    ├── test_server_communication.py 🧪 DEBUGGING: Server communication test
    ├── test_with_env.py             🧪 DEBUGGING: Test with environment
    ├── test_with_venv_python.py     🧪 DEBUGGING: Test with venv Python
    └── spotify_test.sh              🧪 DEBUGGING: Shell-based Spotify test

```

---

## 📋 Component Details

### ✅ Current Implementation (Agent SDK)

These are the **primary files** you should use and modify:

#### Core Files
- **`agent_executor.py`** - Main Agent SDK orchestration logic
  - Initializes Agent SDK with Claude
  - Connects to MCP server
  - Handles tool execution and result parsing
  - Returns structured `MatchResult` objects

- **`api/app_agent.py`** - FastAPI server with Agent SDK
  - HTTP endpoint: `POST /api/v1/sync`
  - Fire-and-forget background task execution
  - Status polling: `GET /api/v1/sync/{workflow_id}`
  - **Use this for production**

- **`mcp_server/spotify_server.py`** - Spotify MCP server
  - Implements 3 tools: `search_track`, `add_track_to_playlist`, `verify_track_added`
  - Handles Spotify API authentication
  - Runs as subprocess managed by Agent SDK

#### Supporting Files
- **`config/settings.py`** - Loads `.env` configuration
- **`models/data_models.py`** - Pydantic models for track matching
- **`api/models.py`** - FastAPI request/response models

#### Utility Files
- **`spotify_custom_client.py`** - Direct MCP client without Agent SDK
  - Use when you need speed (<5s) over intelligence
  - No AI reasoning, manual disambiguation
  - Good for testing MCP server directly

- **`agent_spotify_demo.py`** - Simple demo of Agent SDK
  - Shows basic usage
  - Good starting point for understanding Agent SDK

---

### ⚠️ Deprecated Implementation (Temporal/Standalone)

These files are **no longer actively used** but kept for reference:

#### Why Deprecated?
- Temporal adds complexity (Docker, workers, activities)
- Standalone executor requires separate API calls to Claude
- Agent SDK is simpler and more maintainable
- See `MIGRATION_GUIDE.md` for migration details

#### Deprecated Files
- **`api/app.py`** - Old Temporal-based API
  - Uses Temporal workflows instead of Agent SDK
  - More complex setup required

- **`workflows/music_sync_workflow.py`** - Temporal workflow
  - Orchestrates activities in Temporal
  - Replaced by `agent_executor.py`

- **`workers/music_sync_worker.py`** - Temporal worker
  - Polls Temporal for tasks
  - No longer needed with Agent SDK

- **`activities/*`** - Temporal activity functions
  - `ai_disambiguator.py` - AI matching logic
  - `fuzzy_matcher.py` - Fuzzy matching
  - `playlist_manager.py` - Playlist operations
  - `spotify_search.py` - Spotify API calls
  - **All replaced by MCP server tools + Agent SDK**

- **`executors/standalone_executor.py`** - Non-Temporal executor
  - Used before Temporal was introduced
  - Also deprecated in favor of Agent SDK

---

### 🧪 Test Files

#### Production Tests (Keep These)
- **`test_agent_api.py`** - Full Agent SDK API test
  - Tests complete end-to-end workflow
  - Validates API responses and timing
  - **Should be moved to `tests/integration/`**

- **`test_agent_performance.py`** - Agent SDK performance test
  - Measures execution time
  - Tests direct agent execution (no HTTP)
  - **Should be moved to `tests/integration/`**

#### Debugging Tests (Can Be Deleted)
These 13 files were created during development for debugging:
- `test_mcp_communication.py`
- `test_mcp_debug.py`
- `test_debug_stdio.py`
- `test_debug.py`
- `test_mcp_direct.py`
- `test_mcp_server.py`
- `test_server_communication.py`
- `test_custom_client.py`
- `test_minimal_mcp_server.py`
- `test_minimal_client.py`
- `test_with_env.py`
- `test_with_venv_python.py`
- `spotify_test.sh`

**Purpose:** Helped debug MCP server communication issues during development
**Status:** No longer needed, can be safely deleted
**See:** Phase 3 of cleanup plan

---

## 🚀 Execution Modes

### 1. Agent SDK API Server (Recommended)

**File:** `api/app_agent.py`

**Start:**
```bash
./run.sh
# or
python3 -m uvicorn api.app_agent:app --host 0.0.0.0 --port 8000
```

**Use Case:**
- iOS Shortcuts integration
- Fire-and-forget background tasks
- AI-powered track matching

**Performance:** ~22 seconds per sync

---

### 2. Direct MCP Client (Fast, No AI)

**File:** `spotify_custom_client.py`

**Start:**
```bash
python3 spotify_custom_client.py
```

**Use Case:**
- Quick testing
- When speed matters more than intelligence
- Direct MCP server testing

**Performance:** ~5-8 seconds per sync

---

### 3. Legacy Modes (Deprecated)

#### Temporal Workflow
**File:** `api/app.py`
**Requires:** Docker, Temporal server
**Status:** ⚠️ Deprecated, use Agent SDK instead

#### Standalone Executor
**File:** `executors/standalone_executor.py`
**Status:** ⚠️ Deprecated, use Agent SDK instead

---

## 📚 Documentation Files

### Primary Documentation
1. **`AGENT_INTEGRATION.md`** - **START HERE**
   - Complete Agent SDK integration guide
   - System architecture with Agent SDK
   - Setup instructions
   - Testing examples

2. **`README.md`** - Project overview
   - Quick start guide
   - Feature list
   - Basic setup

3. **`SETUP.md`** - Detailed setup instructions
   - Environment variables
   - Spotify app configuration
   - Authentication setup

### Architecture & Testing
4. **`ARCHITECTURE.md`** - System architecture
   - Component diagrams
   - Data flow
   - Technology stack

5. **`TESTING.md`** - Testing guide
   - How to run tests
   - Test structure
   - Coverage requirements

6. **`PERFORMANCE_TEST_RESULTS.md`** - Agent SDK performance
   - Timing breakdown
   - Performance comparisons
   - Optimization options

### Additional Docs
7. **`docs/EXECUTION_MODES.md`** - Execution mode comparison
8. **`docs/ios-shortcuts-setup.md`** - iOS Shortcuts integration
9. **`PROJECT_STRUCTURE.md`** - This file
10. **`MIGRATION_GUIDE.md`** - Migration from old architecture (coming soon)

---

## 🔧 Configuration Files

### Environment Configuration
- **`.env.example`** - Template for environment variables
  - Copy to `.env` and fill in values
  - Contains Spotify API credentials
  - Anthropic API key for Agent SDK

### Python Configuration
- **`requirements.txt`** - Python dependencies (pip)
- **`pyproject.toml`** - Project metadata (Poetry/uv)
- **`pytest.ini`** - Pytest configuration
- **`uv.lock`** - Dependency lock file (uv package manager)

### Docker & Monitoring
- **`docker-compose.yml`** - Temporal stack (deprecated)
- **`prometheus.yml`** - Prometheus monitoring

---

## 📊 File Count Summary

| Category | Count | Status |
|----------|-------|--------|
| **Current Implementation** | 8 | ✅ Active |
| **Deprecated Implementation** | 10 | ⚠️ Legacy |
| **Production Tests** | 2 | 🧪 Keep |
| **Debugging Tests** | 13 | 🧪 Delete |
| **Test Suite (tests/ dir)** | 8 | 🧪 Keep |
| **Documentation** | 10 | 📚 Active |
| **Configuration** | 8 | ✅ Active |

---

## 🗺️ Navigation Guide

### "I want to..."

#### Use the Project
- **Start the API server** → `./run.sh` or `python3 -m uvicorn api.app_agent:app`
- **Test manually** → `python3 agent_spotify_demo.py`
- **Fast testing (no AI)** → `python3 spotify_custom_client.py`

#### Understand the Project
- **Learn how it works** → `AGENT_INTEGRATION.md`
- **See architecture** → `ARCHITECTURE.md`
- **Setup from scratch** → `SETUP.md`
- **Understand structure** → `PROJECT_STRUCTURE.md` (this file)

#### Modify the Code
- **Change API behavior** → `api/app_agent.py`
- **Modify agent logic** → `agent_executor.py`
- **Add MCP tools** → `mcp_server/spotify_server.py`
- **Update models** → `models/data_models.py` or `api/models.py`

#### Run Tests
- **Test agent performance** → `python3 test_agent_performance.py`
- **Test full API** → `python3 test_agent_api.py`
- **Run test suite** → `pytest tests/`

#### Migrate from Old Code
- **Understand changes** → `MIGRATION_GUIDE.md` (coming soon)
- **Compare architectures** → `ARCHITECTURE.md`

---

## 🔄 Planned Cleanup

See main cleanup plan for details. Summary:

1. ✅ **Phase 1:** Update performance documentation
2. 🔄 **Phase 2:** Create missing documentation (in progress)
3. 📋 **Phase 3:** Clean up test files
   - Delete 13 debugging test files
   - Move production tests to `tests/integration/`
4. 📋 **Phase 4:** Archive old architecture
   - Create `_deprecated/` directory
   - Move Temporal/Standalone files
   - Add deprecation notices
5. 📋 **Phase 5:** Update startup scripts
   - Update `run.sh` for Agent SDK
   - Create `run-agent.sh`

---

## 📞 Quick Reference

| Need | File/Command |
|------|-------------|
| Start API | `./run.sh` |
| Agent SDK code | `agent_executor.py` |
| API server | `api/app_agent.py` |
| MCP server | `mcp_server/spotify_server.py` |
| Configuration | `.env` (copy from `.env.example`) |
| Documentation | `AGENT_INTEGRATION.md` |
| Tests | `pytest tests/` |

---

**Last Updated:** November 17, 2025
**Primary Architecture:** Agent SDK + MCP Server
**Deprecated:** Temporal Workflows, Standalone Executor
