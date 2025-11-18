# Firebase Functions Architecture - Complete Guide

## Table of Contents
1. [Overview](#overview)
2. [The ASGI Bridge Explained](#the-asgi-bridge-explained)
3. [Threading for Background Processing](#threading-for-background-processing)
4. [Complete Request Flow](#complete-request-flow)
5. [Code Walkthrough](#code-walkthrough)
6. [Why This Architecture](#why-this-architecture)
7. [Testing Guide](#testing-guide)

---

## Overview

This project uses **Firebase Functions (2nd Gen)** to deploy a FastAPI application. The main challenge is bridging two different web server protocols:

- **Firebase Functions** → Uses WSGI (synchronous, Flask-based)
- **FastAPI** → Uses ASGI (asynchronous, modern)

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Firebase Functions                        │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  functions/main.py                                  │    │
│  │  ┌──────────────────────────────────────────────┐  │    │
│  │  │ @https_fn.on_request                         │  │    │
│  │  │ def spotify_sync(req):                       │  │    │
│  │  │   ┌──────────────────────────────────────┐   │  │    │
│  │  │   │   ASGI Bridge (Manual)               │   │  │    │
│  │  │   │   - Convert WSGI → ASGI              │   │  │    │
│  │  │   │   - Run FastAPI app                  │   │  │    │
│  │  │   │   - Convert ASGI → WSGI              │   │  │    │
│  │  │   └──────────────────────────────────────┘   │  │    │
│  │  │          ↓                                    │  │    │
│  │  │   ┌──────────────────────────────────────┐   │  │    │
│  │  │   │   FastAPI App                        │   │  │    │
│  │  │   │   (api/app_agent.py)                 │   │  │    │
│  │  │   │                                       │   │  │    │
│  │  │   │   POST /api/v1/sync                  │   │  │    │
│  │  │   │     ↓                                 │   │  │    │
│  │  │   │   Start Background Thread            │   │  │    │
│  │  │   │     ↓                                 │   │  │    │
│  │  │   │   Return HTTP 202 (10ms)             │   │  │    │
│  │  │   └──────────────────────────────────────┘   │  │    │
│  │  └──────────────────────────────────────────────┘  │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  Background Thread (continues after HTTP response)          │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Threading.Thread(daemon=False)                     │    │
│  │    ↓                                                 │    │
│  │  New asyncio event loop                             │    │
│  │    ↓                                                 │    │
│  │  _execute_sync_task()                               │    │
│  │    ↓                                                 │    │
│  │  Agent SDK (Claude)                                 │    │
│  │    ↓                                                 │    │
│  │  Spotify API                                        │    │
│  │    ↓                                                 │    │
│  │  Song added to playlist ✅                          │    │
│  │    ↓                                                 │    │
│  │  Thread exits cleanly                               │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## The ASGI Bridge Explained

### What is ASGI vs WSGI?

**WSGI (Web Server Gateway Interface)**
- Synchronous protocol for Python web apps
- Used by Flask, Django (traditional)
- One request = one thread/process
- Firebase Functions uses WSGI

**ASGI (Asynchronous Server Gateway Interface)**
- Async protocol for modern Python web apps
- Used by FastAPI, Starlette
- Supports async/await, WebSockets, HTTP/2
- More efficient for I/O-bound operations

### The Problem

Firebase Functions expects a WSGI function:
```python
def my_function(request):
    # Synchronous function
    return response
```

But we have a FastAPI app (ASGI):
```python
async def app(scope, receive, send):
    # Asynchronous ASGI app
    pass
```

### The Solution: Manual ASGI Bridge

Located in `functions/main.py`, the bridge does 3 things:

#### 1. Convert Firebase Request → ASGI Format

```python
# Firebase Functions request (WSGI-like)
req: https_fn.Request

# Convert to ASGI scope dictionary
asgi_request = {
    "type": "http",
    "asgi": {"version": "3.0"},
    "http_version": "1.1",
    "method": req.method,              # GET, POST, etc.
    "path": req.path,                  # /api/v1/sync
    "query_string": req.query_string.encode() or b"",
    "headers": [
        (k.lower().encode(), v.encode())
        for k, v in req.headers.items()
    ],
    "server": ("localhost", 8080),
    "client": (req.remote_addr or "unknown", 0),
}
```

**Why this format?**
- ASGI spec requires this exact structure
- `scope` describes the HTTP request
- Headers must be lowercase bytes tuples
- Query string must be bytes

#### 2. Create ASGI Receive/Send Callables

```python
# Request body
body = req.get_data()

# ASGI receive callable
async def receive():
    return {
        "type": "http.request",
        "body": body,
        "more_body": False,  # All data sent at once
    }

# Variables to collect response
response_body = []
response_headers = []
response_status = 200

# ASGI send callable
async def send(message):
    nonlocal response_body, response_headers, response_status

    if message["type"] == "http.response.start":
        # Capture status code and headers
        response_status = message.get("status", 200)
        response_headers = message.get("headers", [])

    elif message["type"] == "http.response.body":
        # Capture response body chunks
        response_body.append(message.get("body", b""))
```

**Why this pattern?**
- ASGI is a streaming protocol
- Response comes in 2+ messages:
  1. `http.response.start` → status + headers
  2. `http.response.body` → body chunks
- We collect all parts to return as single HTTP response

#### 3. Run FastAPI and Convert Response Back

```python
# Run the ASGI app
async def run_asgi():
    await fastapi_app(asgi_request, receive, send)

# Execute in asyncio (from sync context)
asyncio.run(run_asgi())

# Combine response body
full_body = b"".join(response_body)

# Convert headers from bytes tuples to dict
headers_dict = {
    k.decode() if isinstance(k, bytes) else k:
    v.decode() if isinstance(v, bytes) else v
    for k, v in response_headers
}

# Return Firebase Functions response
return https_fn.Response(
    response=full_body,
    status=response_status,
    headers=headers_dict,
)
```

**Why asyncio.run()?**
- FastAPI is async, Firebase Functions are sync
- `asyncio.run()` creates event loop, runs async code, cleans up
- Bridges async/sync worlds

### Complete Bridge Code

Here's the full bridge from `functions/main.py`:

```python
@https_fn.on_request(
    cors=options.CorsOptions(cors_origins="*", cors_methods=["get", "post", "options"]),
    timeout_sec=60,
    memory=options.MemoryOption.GB_1,
    cpu=1,
)
def spotify_sync(req: https_fn.Request) -> https_fn.Response:
    """ASGI Bridge: Firebase Functions → FastAPI"""
    import asyncio
    import json
    import logging

    logger = logging.getLogger(__name__)

    try:
        # STEP 1: Convert Firebase request to ASGI format
        asgi_request = {
            "type": "http",
            "method": req.method,
            "path": req.path,
            "headers": [(k.lower().encode(), v.encode()) for k, v in req.headers.items()],
            "query_string": req.query_string or b"",
            "body": req.get_data() or b"",
        }

        # STEP 2: Create ASGI receive/send callables
        async def receive():
            return {
                "type": "http.request",
                "body": req.get_data() or b"",
                "more_body": False,
            }

        response_body = []
        response_headers = []
        response_status = 200

        async def send(message):
            nonlocal response_body, response_headers, response_status
            if message["type"] == "http.response.start":
                response_status = message.get("status", 200)
                response_headers = message.get("headers", [])
            elif message["type"] == "http.response.body":
                response_body.append(message.get("body", b""))

        # STEP 3: Run FastAPI app
        async def run_asgi():
            await fastapi_app(asgi_request, receive, send)

        asyncio.run(run_asgi())

        # STEP 4: Convert ASGI response to Firebase response
        full_body = b"".join(response_body)
        headers_dict = {
            k.decode() if isinstance(k, bytes) else k:
            v.decode() if isinstance(v, bytes) else v
            for k, v in response_headers
        }

        return https_fn.Response(
            response=full_body,
            status=response_status,
            headers=headers_dict,
        )

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return https_fn.Response(
            response=json.dumps({"error": "Internal Server Error"}),
            status=500,
            headers={"Content-Type": "application/json"},
        )
```

---

## Threading for Background Processing

### The Challenge

Firebase Functions have a critical limitation:
```python
# This DOESN'T work in Firebase Functions
asyncio.create_task(long_running_task())
return response  # ❌ Task gets killed when function returns
```

**Why?** Firebase Functions terminate all background async tasks when HTTP response is sent.

### The Solution: Threading

```python
import threading

def run_sync_in_thread():
    """Wrapper to run async task in thread."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_execute_sync_task(...))
    finally:
        loop.close()

# Start background thread
thread = threading.Thread(target=run_sync_in_thread, daemon=False)
thread.start()

# Return HTTP response immediately
return response  # ✅ Thread continues running!
```

### Why This Works

**Key Points:**
1. **`daemon=False`** → Thread is NOT a daemon
   - Daemon threads get killed when main thread exits
   - Non-daemon threads continue independently
   - Firebase Functions allow non-daemon threads to complete

2. **New Event Loop** → Each thread needs its own
   - `asyncio.new_event_loop()` creates isolated loop
   - Prevents conflicts with main thread
   - Clean separation of concerns

3. **`finally` block** → Always cleans up
   - Ensures event loop is closed
   - Thread exits cleanly after completion
   - No resource leaks

### Thread Lifecycle

```
Time →

0ms     HTTP Request arrives
        │
1ms     FastAPI endpoint called
        │
2ms     Thread created and started
        │
3ms     ┌─ Background Thread ─────────────────────┐
        │  - Create new event loop                 │
9ms     │  - Start agent execution                 │
        │                                           │
10ms    HTTP Response returned (202 Accepted)      │
        ↓                                           │
        Main function exits                        │
                                                    │
        Background thread continues...             │
        │  - Agent searches Spotify                │
        │  - Picks best match with AI              │
        │  - Adds song to playlist                 │
        │  - Verifies addition                     │
        │                                           │
25s     │  - Agent completes                       │
        │  - Event loop closed                     │
        │  - Thread exits cleanly                  │
        └──────────────────────────────────────────┘
```

### Code in `api/app_agent.py`

```python
@app.post("/api/v1/sync", response_model=SyncSongResponse)
async def sync_song(request: SyncSongRequest):
    workflow_id = f"agent-sync-{user_id}-{timestamp}-{random}"

    # Create song metadata
    song_metadata = SongMetadata(
        title=request.track_name,
        artist=request.artist,
        album=request.album
    )

    # Background processing with threading
    import threading

    def run_sync_in_thread():
        """Run async task in separate thread with new event loop."""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Execute agent sync (25-30s operation)
            loop.run_until_complete(_execute_sync_task(
                workflow_id=workflow_id,
                song_metadata=song_metadata,
                playlist_id=request.playlist_id,
                user_id=user_id,
                use_ai_disambiguation=request.use_ai_disambiguation
            ))
        finally:
            loop.close()  # Always cleanup

    # Start non-daemon thread
    thread = threading.Thread(target=run_sync_in_thread, daemon=False)
    thread.start()

    logger.info(f"[{workflow_id}] Background thread started")

    # Return immediately (fire-and-forget)
    return SyncSongResponse(
        workflow_id=workflow_id,
        status="accepted",
        message=f"Agent is searching for '{request.track_name}'...",
        status_url=None  # No status tracking in fire-and-forget mode
    )
```

---

## Complete Request Flow

### Step-by-Step Walkthrough

```
1. User makes HTTP POST to Firebase Function
   ↓
   POST https://us-central1-PROJECT.cloudfunctions.net/spotify_sync/api/v1/sync
   Body: {
     "track_name": "Stairway to Heaven",
     "artist": "Led Zeppelin",
     "playlist_id": "43X1N9GAKwVARreGxSAdZI"
   }

2. Firebase Functions calls spotify_sync() in functions/main.py
   ↓
   def spotify_sync(req: https_fn.Request):

3. ASGI Bridge converts request
   ↓
   asgi_request = {
     "method": "POST",
     "path": "/api/v1/sync",
     "headers": [...],
     "body": b'{"track_name": "Stairway to Heaven", ...}'
   }

4. Bridge runs FastAPI app
   ↓
   asyncio.run(fastapi_app(asgi_request, receive, send))

5. FastAPI routes to sync_song() in api/app_agent.py
   ↓
   @app.post("/api/v1/sync")
   async def sync_song(request: SyncSongRequest):

6. FastAPI validates request with Pydantic
   ↓
   ✓ track_name: str (1-200 chars)
   ✓ artist: str (1-200 chars)
   ✓ playlist_id: matches pattern ^[a-zA-Z0-9]{22}$

7. Generate workflow ID
   ↓
   workflow_id = "agent-sync-anonymous-1763447923-99545"

8. Create background thread
   ↓
   thread = threading.Thread(target=run_sync_in_thread, daemon=False)
   thread.start()

9. Return HTTP 202 Accepted (~10ms)
   ↓
   {
     "workflow_id": "agent-sync-anonymous-1763447923-99545",
     "status": "accepted",
     "message": "Agent is searching for 'Stairway to Heaven'...",
     "status_url": null
   }

10. ASGI Bridge converts response back to Firebase format
    ↓
    https_fn.Response(
      response=b'{"workflow_id": "...", ...}',
      status=202,
      headers={"content-type": "application/json"}
    )

11. HTTP response sent to user
    ↓
    User receives 202 in ~10ms

12. Background thread continues (user disconnected)
    ↓
    New event loop created in thread
    ↓
    _execute_sync_task() called
    ↓
    Agent SDK initialized (Claude)
    ↓
    Agent searches Spotify:
      - Finds 5 matches for "Stairway to Heaven"
      - Analyzes popularity, album, release date
      - Picks: "Stairway to Heaven - Remaster" (80% popularity)
    ↓
    Agent adds to playlist:
      - POST /v1/playlists/{id}/tracks
      - Track URI: spotify:track:xDGK2yZxkXZZV
    ↓
    Agent verifies:
      - GET /v1/playlists/{id}/tracks
      - Confirms track in playlist
    ↓
    Result: {"success": true, "matched_track": "..."}
    ↓
    Event loop closed
    ↓
    Thread exits (~25s after start)
```

### Timing Breakdown

| Event | Time | Who's Active |
|-------|------|--------------|
| Request received | 0ms | Firebase Function |
| ASGI bridge converts | 1ms | Firebase Function |
| FastAPI validates | 2ms | FastAPI (in bridge) |
| Thread started | 3ms | FastAPI |
| **HTTP response returned** | **10ms** | **User receives response** |
| Function exits | 11ms | Thread only |
| Agent searches Spotify | 5s | Thread only |
| Agent picks best match | 15s | Thread only |
| Song added to playlist | 20s | Thread only |
| Agent verifies | 24s | Thread only |
| Thread exits | 25s | Complete |

---

## Code Walkthrough

### File Structure

```
spotify-mcp-integration/
├── functions/
│   ├── main.py              ← Firebase Functions entry point (ASGI bridge)
│   ├── requirements.txt     ← Firebase deployment dependencies
│   ├── .env                 ← Environment variables (credentials)
│   └── venv/                ← Python 3.11 virtual environment
│
├── api/
│   ├── app_agent.py         ← FastAPI app (threading implementation)
│   └── models.py            ← Pydantic models
│
├── agent_executor.py        ← Agent SDK integration (Claude)
│
├── firebase.json            ← Firebase configuration
└── .firebaserc              ← Firebase project ID
```

### Key Files Explained

#### `functions/main.py` - The ASGI Bridge

```python
from firebase_functions import https_fn, options
from firebase_admin import initialize_app
import asyncio

# Initialize Firebase Admin SDK
initialize_app()

# Import FastAPI app
from api.app_agent import app as fastapi_app

@https_fn.on_request(
    cors=options.CorsOptions(cors_origins="*", cors_methods=["get", "post", "options"]),
    timeout_sec=60,      # Max 60s for HTTP functions
    memory=options.MemoryOption.GB_1,  # 1GB for Agent SDK
    cpu=1,
)
def spotify_sync(req: https_fn.Request) -> https_fn.Response:
    """
    ASGI Bridge: Converts Firebase Functions (WSGI) ←→ FastAPI (ASGI)

    Flow:
    1. Convert Firebase request → ASGI format
    2. Run FastAPI app with asyncio
    3. Convert ASGI response → Firebase format
    """
    # [ASGI bridge code shown earlier]
    pass
```

**Why this file exists:**
- Firebase Functions entry point
- MUST be in `functions/` directory
- MUST have `@https_fn.on_request` decorator
- Bridges WSGI ←→ ASGI

#### `api/app_agent.py` - Threading Implementation

```python
from fastapi import FastAPI
import threading
import asyncio

app = FastAPI()

@app.post("/api/v1/sync")
async def sync_song(request: SyncSongRequest):
    """
    Fire-and-forget endpoint with threading

    Returns immediately (~10ms)
    Processing continues in background thread
    """
    workflow_id = generate_id()

    def run_sync_in_thread():
        # Create isolated event loop for thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Run async agent task
            loop.run_until_complete(_execute_sync_task(...))
        finally:
            loop.close()

    # Start non-daemon thread (survives HTTP response)
    thread = threading.Thread(target=run_sync_in_thread, daemon=False)
    thread.start()

    # Return immediately
    return {"workflow_id": workflow_id, "status": "accepted"}
```

**Why threading instead of asyncio.create_task():**
- `create_task()` → Killed when HTTP response sent
- `threading.Thread()` → Continues independently
- `daemon=False` → Thread completes its work

#### `agent_executor.py` - Agent SDK Integration

```python
async def execute_music_sync_with_agent(
    song_metadata: SongMetadata,
    playlist_id: str,
    timeout_seconds: int = 55  # 5s buffer from 60s function limit
):
    """
    Execute agent-based music sync with timeout

    Agent workflow:
    1. Search Spotify for track
    2. Analyze matches with AI reasoning
    3. Pick best match
    4. Add to playlist
    5. Verify addition
    """
    async with AgentContext() as context:
        agent = Agent(
            system_prompt=SYNC_AGENT_PROMPT,
            tools=[search_spotify, add_to_playlist, verify_addition],
            model="claude-3-5-sonnet-20241022"
        )

        # Run with timeout
        result = await asyncio.wait_for(
            agent.run(f"Sync '{song_metadata.title}' by {song_metadata.artist}"),
            timeout=timeout_seconds
        )

        return result
```

**Why 55s timeout:**
- Firebase Functions max: 60s
- 55s agent timeout → 5s buffer
- Prevents function timeout errors

---

## Why This Architecture

### Design Decisions

#### 1. Why Manual ASGI Bridge Instead of Mangum?

**Mangum** is designed for AWS Lambda, not Firebase Functions:

```python
# Mangum approach (doesn't work)
from mangum import Mangum
handler = Mangum(app)

@https_fn.on_request()
def function(req):
    return handler(req)  # ❌ TypeError: missing 'context' argument
```

**Problem:** Mangum expects Lambda event format with context object.

**Our Solution:** Manual ASGI bridge
- Direct control over conversion
- No external dependencies
- Firebase-specific optimizations
- Clear, maintainable code

#### 2. Why Threading Instead of Cloud Tasks?

**Cloud Tasks** approach:
```python
# More complex setup
- Create Cloud Tasks queue
- Configure service account
- Deploy worker function
- Handle retries, dead letters
- Monitor queue health
```

**Threading** approach:
```python
# Simple and direct
thread = threading.Thread(target=work, daemon=False)
thread.start()
```

**Benefits:**
- ✅ Zero additional infrastructure
- ✅ No queue management
- ✅ Instant execution (no queue delay)
- ✅ Stays within 60s limit
- ✅ Firebase Functions allow it

**Tradeoffs:**
- ❌ No built-in retries
- ❌ No visibility into failures
- ❌ Must complete within 60s

For our use case (25s agent execution), threading is perfect.

#### 3. Why USE_FIRESTORE Flag?

Firestore costs money for storage. Many users want zero costs:

```python
# With Firestore (status tracking)
USE_FIRESTORE=true
→ Store results in Firestore
→ GET /status/{id} returns results
→ Costs: $0.06 per 100k document writes

# Without Firestore (fire-and-forget)
USE_FIRESTORE=false
→ No storage
→ GET /status/{id} returns 501
→ Costs: $0
```

The flag gives users explicit control.

#### 4. Why Python 3.11?

Firebase Functions 2nd Gen supports:
- Python 3.10
- Python 3.11 ✅ (we use this)
- Python 3.12

**Why 3.11:**
- Required by `firebase-functions` package (≥0.4.0)
- Stable and well-tested
- Good performance
- All our dependencies support it

---

## Testing Guide

### Local Testing with Emulator

#### 1. Install Firebase CLI

```bash
npm install --save-dev firebase-tools
```

#### 2. Setup Python Environment

```bash
cd functions
python3.11 -m venv venv
source venv/bin/activate
uv pip install -r requirements.txt
```

#### 3. Configure Environment

```bash
# Copy credentials
cp ../.env .env

# Edit firebase.json (already configured)
# Edit .firebaserc (already configured)
```

#### 4. Start Emulator

```bash
npx firebase emulators:start
```

Output:
```
✔  functions: Loaded environment variables from .env
✔  functions[us-central1-spotify_sync]: http function initialized
   http://127.0.0.1:5001/spotify-mcp-test/us-central1/spotify_sync

┌─────────────────────────────────────────────────────────────┐
│ ✔  All emulators ready! It is now safe to connect your app. │
│ i  View Emulator UI at http://127.0.0.1:4000/               │
└─────────────────────────────────────────────────────────────┘
```

#### 5. Test Endpoints

**Health Check:**
```bash
curl http://127.0.0.1:5001/spotify-mcp-test/us-central1/health

Response:
{
  "status": "healthy",
  "service": "spotify-sync-firebase"
}
```

**Sync Song:**
```bash
curl -X POST \
  http://127.0.0.1:5001/spotify-mcp-test/us-central1/spotify_sync/api/v1/sync \
  -H "Content-Type: application/json" \
  -d '{
    "track_name": "Bohemian Rhapsody",
    "artist": "Queen",
    "album": "A Night at the Opera",
    "playlist_id": "43X1N9GAKwVARreGxSAdZI"
  }'

Response (in ~10ms):
{
  "workflow_id": "agent-sync-anonymous-1763447923-99545",
  "status": "accepted",
  "message": "Agent is searching for 'Bohemian Rhapsody' by Queen...",
  "status_url": null
}
```

**Check Logs:**
```
i  functions: Beginning execution of "us-central1-spotify_sync"
>  INFO: Starting agent-based sync for: Bohemian Rhapsody by Queen
>  INFO: Background thread started for agent processing
i  functions: Finished "us-central1-spotify_sync" in 10.5ms
>  INFO: Agent response: I'll search for the track...
>  INFO: Perfect! Found "Bohemian Rhapsody - Remaster" (85% popularity)
>  INFO: Successfully added to playlist
>  INFO: ✅ Success! Matched: Bohemian Rhapsody - Remaster
```

### Production Deployment

```bash
# 1. Update project ID in .firebaserc
{
  "projects": {
    "default": "your-actual-project-id"
  }
}

# 2. Deploy
firebase deploy --only functions

# 3. Your function URL
https://us-central1-your-project.cloudfunctions.net/spotify_sync
```

---

## Troubleshooting

### Common Issues

#### 1. "Process java -version has exited with code 1"

**Problem:** Firebase emulator requires Java

**Solution:**
```bash
brew install openjdk@17
sudo ln -sfn /opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk \
  /Library/Java/JavaVirtualMachines/openjdk-17.jdk
```

#### 2. "firebase_admin not found"

**Problem:** Wrong Python environment

**Solution:**
```bash
cd functions
source venv/bin/activate
uv pip install -r requirements.txt
```

#### 3. "Background task not completing"

**Problem:** Using asyncio.create_task() instead of threading

**Solution:** Use threading as shown in this guide

#### 4. "Function timeout after 60s"

**Problem:** Agent taking too long

**Solution:** Already handled with 55s timeout:
```python
timeout_seconds: int = 55  # 5s buffer
```

---

## Summary

### Key Concepts

1. **ASGI Bridge** = Convert WSGI (Firebase) ←→ ASGI (FastAPI)
   - Manual implementation in `functions/main.py`
   - Handles request/response conversion
   - Uses `asyncio.run()` to bridge sync/async

2. **Threading** = Background processing that survives HTTP response
   - `daemon=False` → Thread completes independently
   - New event loop per thread
   - Clean exit with `finally` block

3. **Fire-and-Forget** = Return immediately, process in background
   - HTTP 202 in ~10ms
   - Thread continues for ~25s
   - No user waiting time

4. **Single Function** = Everything in one Firebase Function
   - No Cloud Tasks
   - No Cloud Run
   - Simple deployment

### Architecture Benefits

✅ **Fast Response** - Users get 202 in ~10ms
✅ **Reliable Processing** - Thread completes work
✅ **Cost Effective** - No extra infrastructure
✅ **Simple Deployment** - One function to deploy
✅ **Easy to Test** - Firebase emulator works perfectly
✅ **Maintainable** - Clear code structure

### Files to Remember

- `functions/main.py` → ASGI bridge
- `api/app_agent.py` → Threading implementation
- `agent_executor.py` → Agent SDK logic
- `firebase.json` → Firebase configuration

---

## Next Steps

1. **Test Locally** - Use Firebase emulator
2. **Deploy** - `firebase deploy --only functions`
3. **Monitor** - Check Firebase console logs
4. **Iterate** - Adjust timeouts, prompts as needed

For questions or issues, see:
- [Firebase Functions Docs](https://firebase.google.com/docs/functions)
- [FastAPI ASGI Spec](https://asgi.readthedocs.io/)
- [Threading Docs](https://docs.python.org/3/library/threading.html)
