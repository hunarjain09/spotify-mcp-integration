# Firebase Functions for Spotify MCP Integration

This directory contains the Firebase Functions deployment for the Spotify MCP Integration.

## What's Inside

- **`main.py`**: Firebase Functions entry point that wraps the FastAPI app
- **`requirements.txt`**: All Python dependencies for the function
- **`.gitignore`**: Files to exclude from deployment

## How It Works

1. **Single Function**: `spotify_sync` handles all HTTP requests via FastAPI
2. **Mangum Adapter**: Converts Firebase HTTP requests to ASGI format for FastAPI
3. **Parent Imports**: Imports FastAPI app and all core logic from parent directory

## Architecture

```
Firebase Function (spotify_sync)
    ↓
Mangum (ASGI Adapter)
    ↓
FastAPI App (from ../api/app_agent.py)
    ↓
Agent Executor (from ../agent_executor.py)
    ↓
MCP Server (subprocess from ../mcp_server/spotify_server.py)
    ↓
Spotify API
```

## Key Features

### Fire-and-Forget Pattern
- POST `/api/v1/sync` returns immediately with `workflow_id`
- Processing happens in background async task
- GET `/api/v1/sync/{workflow_id}` to check status

### Optional Firestore
- **Local dev**: Uses in-memory storage (no Firestore needed)
- **Firebase**: Automatically uses Firestore for persistent storage
- **Graceful fallback**: If Firestore fails, falls back to in-memory

### Timeout Handling
- Function timeout: 60 seconds (Firebase HTTP max)
- Agent executor timeout: 55 seconds (5s buffer)
- If timeout occurs, returns error to user

## Deployment

See [../FIREBASE_DEPLOYMENT_GUIDE.md](../FIREBASE_DEPLOYMENT_GUIDE.md) for full instructions.

**Quick deploy:**
```bash
firebase deploy --only functions
```

## Configuration

### Secrets (via Firebase Secret Manager)
- `ANTHROPIC_API_KEY` - Required for Agent SDK
- `SPOTIFY_CLIENT_ID` - Required for Spotify API
- `SPOTIFY_CLIENT_SECRET` - Required for Spotify API
- `DEFAULT_PLAYLIST_ID` - Optional default playlist

### Function Settings (in main.py)

**Timeout:**
```python
timeout_sec=60  # Maximum for HTTP functions
```

**Memory:**
```python
memory=options.MemoryOption.GB_1  # 1GB recommended
```

**CPU:**
```python
cpu=1  # 1 CPU core
```

**CORS:**
```python
cors_origins="*"  # Allow all origins (adjust for production)
```

## Local Testing

You can test locally without deploying:

```bash
# Install Firebase emulator
firebase init emulators

# Start emulator
firebase emulators:start

# Test function
curl http://localhost:5001/YOUR_PROJECT/us-central1/spotify_sync/health
```

## Environment Variables vs Secrets

**Secrets** (sensitive data):
- Use Firebase Secret Manager
- Not visible in logs
- Access via `firebase functions:secrets:set`

**Environment Variables** (non-sensitive config):
- Set in `firebase.json` or `.env.yaml`
- Visible in logs and console

## Monitoring

**View logs:**
```bash
firebase functions:log --only spotify_sync
```

**Stream logs:**
```bash
firebase functions:log --only spotify_sync --follow
```

## Troubleshooting

### Import Errors

Make sure parent directory is in Python path:

```python
# In main.py
sys.path.insert(0, str(Path(__file__).parent.parent))
```

### Timeout Errors

Reduce agent complexity:
- Lower `max_turns` in agent executor
- Skip verification step
- Use simpler prompts

### Memory Errors

Increase memory allocation:
```python
memory=options.MemoryOption.GB_2
```

## Cost Optimization

- Use minimum necessary memory (currently 1GB)
- Keep timeout as low as possible
- Consider caching search results
- Monitor actual usage in Cloud Console

## Security

- Never commit secrets to git
- Use Secret Manager for all sensitive data
- Configure Firestore security rules
- Consider authentication for production
