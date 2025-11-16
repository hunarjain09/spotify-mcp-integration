# Execution Modes: Temporal vs Standalone

This document explains the two execution modes supported by the spotify-mcp-integration system and helps you choose the right mode for your deployment.

## Overview

The system supports two execution modes controlled by the `USE_TEMPORAL` environment variable:

1. **Temporal Mode** (`USE_TEMPORAL=true`) - Durable workflow orchestration
2. **Standalone Mode** (`USE_TEMPORAL=false`) - Direct execution without Temporal

## Mode Comparison

### Temporal Mode (`USE_TEMPORAL=true`)

**When to use:**
- Production deployments requiring high reliability
- Scenarios where durability is critical (server restarts shouldn't lose workflows)
- High-traffic applications with concurrent requests
- Need for distributed processing across multiple workers
- Requiring detailed workflow history and debugging capabilities

**Benefits:**
✅ **Durable Execution** - Workflows survive server restarts and failures
✅ **Advanced Retry Policies** - Exponential backoff, per-activity retry configuration
✅ **Distributed Processing** - Scale across multiple worker instances
✅ **Real-time Progress** - Query workflow state at any time via Temporal queries
✅ **Workflow History** - Complete event history for debugging and replay
✅ **Built-in Monitoring** - Temporal Web UI for workflow visualization
✅ **State Management** - Automatic state persistence in PostgreSQL

**Trade-offs:**
❌ **Infrastructure Complexity** - Requires Temporal server + PostgreSQL
❌ **Resource Usage** - Higher memory and storage requirements
❌ **Deployment Complexity** - More moving parts to manage
❌ **Learning Curve** - Requires understanding Temporal concepts

**Infrastructure Required:**
- Temporal Server (docker-compose or Temporal Cloud)
- PostgreSQL database (for Temporal state)
- Temporal Worker process
- FastAPI server

**Estimated Costs (Production):**
- Temporal Cloud: $200-$400/month (includes managed infrastructure)
- Self-hosted: ~$50-$100/month (EC2/GCP instances + databases)

### Standalone Mode (`USE_TEMPORAL=false`)

**When to use:**
- Development and testing environments
- Personal projects or low-traffic deployments
- Budget-constrained scenarios
- Prototyping and demos
- When fire-and-forget execution is acceptable
- Single-server deployments

**Benefits:**
✅ **Simple Deployment** - Just FastAPI + Spotify (2 components vs 5+)
✅ **Low Resource Usage** - Minimal memory and storage footprint
✅ **Fast Startup** - No infrastructure to initialize
✅ **Easy Development** - No docker-compose setup needed
✅ **Lower Costs** - Single server deployment (~$10-20/month)
✅ **No Learning Curve** - Standard FastAPI patterns

**Trade-offs:**
❌ **No Durability** - In-progress workflows lost on server restart
❌ **Basic Retry Logic** - Simple exponential backoff (no per-activity configuration)
❌ **Single Server Only** - Cannot distribute across multiple instances
❌ **Limited Progress Tracking** - In-memory state only
❌ **No History** - No workflow replay or debugging capabilities

**Infrastructure Required:**
- FastAPI server only (single process)
- Spotify API access

**Estimated Costs (Production):**
- Cloud hosting: $10-20/month (single small instance)

## Configuration

### Enabling Temporal Mode

1. Set environment variable:
```env
USE_TEMPORAL=true
TEMPORAL_HOST=localhost:7233  # or your Temporal Cloud URL
TEMPORAL_NAMESPACE=default
```

2. Start Temporal server:
```bash
docker-compose up -d
```

3. Start worker:
```bash
python workers/music_sync_worker.py
```

4. Start API:
```bash
uvicorn api.app:app --host 0.0.0.0 --port 8000
```

### Enabling Standalone Mode

1. Set environment variable:
```env
USE_TEMPORAL=false
# No other Temporal configuration needed
```

2. Start API only:
```bash
uvicorn api.app:app --host 0.0.0.0 --port 8000
```

That's it! No Temporal server or worker needed.

## Feature Comparison Matrix

| Feature | Temporal Mode | Standalone Mode |
|---------|---------------|-----------------|
| **Durability** | ✅ Persistent across restarts | ❌ In-memory only |
| **Retry Policies** | ✅ Advanced, per-activity | ⚠️ Basic exponential backoff |
| **Distributed Processing** | ✅ Multi-worker support | ❌ Single server only |
| **Progress Tracking** | ✅ Real-time queries | ⚠️ In-memory state |
| **Workflow History** | ✅ Complete event log | ❌ No history |
| **Debugging** | ✅ Temporal Web UI | ⚠️ Logs only |
| **State Storage** | ✅ PostgreSQL | ⚠️ In-memory dict |
| **API Compatibility** | ✅ Identical endpoints | ✅ Identical endpoints |
| **Activity Execution** | ✅ Same code | ✅ Same code |
| **AI Disambiguation** | ✅ Supported | ✅ Supported |
| **Claude SDK** | ✅ Supported | ✅ Supported |
| **Setup Time** | ~10-15 minutes | ~2 minutes |
| **Infrastructure Cost** | $$$ (Temporal + DB) | $ (FastAPI only) |

## Switching Between Modes

The API endpoints remain **identical** in both modes, so you can switch without changing client code:

```bash
# Switch to Temporal mode
echo "USE_TEMPORAL=true" >> .env
docker-compose up -d
python workers/music_sync_worker.py &
uvicorn api.app:app --port 8000

# Switch to Standalone mode
echo "USE_TEMPORAL=false" > .env
# Stop Temporal and worker
uvicorn api.app:app --port 8000
```

## Recommendations by Use Case

### Personal Project
**Use Standalone Mode**
- Simple deployment on Raspberry Pi or cheap VPS
- No need for complex infrastructure
- Fire-and-forget is acceptable

### Startup / Small Team
**Use Standalone Mode initially, migrate to Temporal later**
- Start simple to validate product-market fit
- Migrate to Temporal when reliability becomes critical
- API compatibility ensures smooth migration

### Production SaaS
**Use Temporal Mode**
- High reliability requirements
- Need for observability and debugging
- Scaling across multiple servers
- Worth the infrastructure investment

### Development/Testing
**Use Standalone Mode**
- Faster iteration cycles
- No docker-compose setup overhead
- Easier debugging with direct execution

## Migration Path

### Standalone → Temporal

1. Start Temporal infrastructure:
```bash
docker-compose up -d
```

2. Deploy worker process:
```bash
python workers/music_sync_worker.py
```

3. Update `.env`:
```env
USE_TEMPORAL=true
TEMPORAL_HOST=localhost:7233
```

4. Restart API server (zero API changes needed)

### Temporal → Standalone

1. Update `.env`:
```env
USE_TEMPORAL=false
```

2. Restart API server

3. Shutdown Temporal and worker:
```bash
docker-compose down
# Kill worker process
```

**Note:** In-progress Temporal workflows will be lost. Complete all workflows before migrating.

## Technical Implementation Details

### Code Reuse

Both modes use the **same activity functions**:
- `search_spotify_standalone()` calls same logic as `@activity.defn search_spotify()`
- `fuzzy_match_standalone()` uses identical matching algorithm
- `ai_disambiguate_standalone()` uses same Claude SDK/Langchain integration

This ensures **identical behavior** regardless of mode.

### Retry Logic Comparison

**Temporal Mode:**
```python
RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=10),
    maximum_attempts=3,
    non_retryable_error_types=["InvalidCredentialsError"]
)
```

**Standalone Mode:**
```python
async def execute_with_retry(
    func, max_attempts=3, initial_delay=1.0, backoff=2.0
):
    # Simple exponential backoff
    for attempt in range(max_attempts):
        try:
            return await func()
        except Exception:
            await asyncio.sleep(initial_delay * (backoff ** attempt))
```

### State Storage

**Temporal Mode:**
- State stored in PostgreSQL via Temporal
- Survives server restarts
- Queryable via Temporal client
- History available for replay

**Standalone Mode:**
```python
# In-memory dictionary
workflow_status_store: Dict[str, StandaloneWorkflowState] = {}
```
- Lost on server restart
- Fast access, no database overhead
- No persistence layer needed

## Performance Characteristics

### Latency

| Operation | Temporal Mode | Standalone Mode |
|-----------|---------------|-----------------|
| **Start Workflow** | ~50-100ms | ~5-10ms |
| **Query Status** | ~20-50ms | ~1-5ms |
| **Activity Execution** | Same | Same |

Standalone mode has lower latency for workflow operations, but identical activity execution time.

### Throughput

**Temporal Mode:**
- Limited by Temporal server capacity
- Can scale horizontally with multiple workers
- Recommended: 50-100 concurrent workflows per worker

**Standalone Mode:**
- Limited by FastAPI server capacity
- Single server only (no horizontal scaling)
- Recommended: 20-50 concurrent workflows

## Conclusion

Choose **Standalone Mode** for:
- Development and testing
- Personal projects
- Low-traffic applications
- Budget constraints
- Simple deployments

Choose **Temporal Mode** for:
- Production applications
- High reliability requirements
- Scaling needs
- Advanced monitoring and debugging
- Distributed systems

Both modes provide the **same functionality** and **same API**, making it easy to start simple and scale up when needed.
