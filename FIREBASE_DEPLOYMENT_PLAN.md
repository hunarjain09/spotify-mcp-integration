# Firebase Functions Deployment Tech Plan

## Executive Summary

This document outlines three approaches for deploying the Spotify MCP Integration to Firebase Functions, with **Option 2 (Hybrid Architecture)** recommended as the optimal solution balancing cost, reliability, and maintainability.

## Current Architecture Analysis

### Stack
- **FastAPI server** with background async tasks
- **Claude Agent SDK** orchestrating MCP tools
- **MCP Spotify server** running as subprocess (stdio protocol)
- **In-memory result storage** (Python dict)
- **Execution time**: ~22-25 seconds per sync
- **Dependencies**: Agent SDK, Spotipy, FastAPI, MCP server

### Key Constraints
1. **Long execution time** (~22-25s) - near Firebase Functions timeout limits
2. **Stateful MCP server** - subprocess management needed
3. **In-memory storage** - doesn't persist across invocations
4. **OAuth tokens** - need persistent storage
5. **Heavy dependencies** - larger deployment package

---

## Option 1: Direct Migration to Firebase Functions (2nd Gen)

### Overview
Deploy the FastAPI app directly to Firebase Functions with minimal changes.

### Architecture
```
iOS Shortcuts → Firebase Functions (FastAPI) → Agent SDK → MCP Server → Spotify API
                         ↓
                    Firestore (results)
```

### Changes Required

#### 1. Replace in-memory storage with Firestore
```python
# api/app_agent.py
from google.cloud import firestore
from firebase_admin import initialize_app

initialize_app()
db = firestore.Client()

# Replace execution_results dict
async def _execute_sync_task(...):
    result = await execute_music_sync_with_agent(...)

    # Store in Firestore
    db.collection('sync_results').document(workflow_id).set({
        'result': result.dict(),
        'timestamp': firestore.SERVER_TIMESTAMP
    })

@app.get("/api/v1/sync/{workflow_id}")
async def get_sync_status(workflow_id: str):
    doc = db.collection('sync_results').document(workflow_id).get()
    if not doc.exists:
        return {"status": "running"}
    return doc.to_dict()
```

#### 2. Add Firebase dependencies
```python
# requirements.txt additions
firebase-admin>=6.0.0
google-cloud-firestore>=2.14.0
google-cloud-secret-manager>=2.18.0
mangum>=0.17.0  # ASGI adapter for Firebase Functions
```

#### 3. Create Firebase Functions entry point
```python
# main.py (Firebase Functions entry point)
from firebase_functions import https_fn, options
from mangum import Mangum
from api.app_agent import app

@https_fn.on_request(
    region="us-central1",
    timeout_sec=60,
    memory=options.MemoryOption.MB_512,
)
def spotify_sync(req: https_fn.Request) -> https_fn.Response:
    """Firebase Function that wraps FastAPI app."""
    handler = Mangum(app, lifespan="off")
    return handler(req, None, None)
```

#### 4. Deployment Configuration

**firebase.json**
```json
{
  "functions": [
    {
      "source": ".",
      "codebase": "spotify-sync",
      "runtime": "python311",
      "timeout": "60s",
      "minInstances": 0,
      "maxInstances": 100,
      "memory": "512MB",
      "cpu": 1
    }
  ]
}
```

#### 5. Environment variable management
```bash
# Store secrets
firebase functions:secrets:set ANTHROPIC_API_KEY
firebase functions:secrets:set SPOTIFY_CLIENT_ID
firebase functions:secrets:set SPOTIFY_CLIENT_SECRET

# Store Spotify OAuth tokens in Firestore
db.collection('config').document('spotify_oauth').set({
    'access_token': token,
    'refresh_token': refresh_token,
    'expires_at': expires_at
})
```

### Deployment Steps
```bash
# 1. Initialize Firebase
firebase init functions

# 2. Configure secrets
firebase functions:secrets:set ANTHROPIC_API_KEY
firebase functions:secrets:set SPOTIFY_CLIENT_ID
firebase functions:secrets:set SPOTIFY_CLIENT_SECRET

# 3. Deploy
firebase deploy --only functions
```

### Pros & Cons

**Pros:**
- ✅ Minimal code changes
- ✅ Quick migration (1-2 days)
- ✅ Familiar architecture
- ✅ Easy to test locally

**Cons:**
- ❌ May hit 60s timeout for slow operations
- ❌ Expensive for long-running tasks (~$0.40 per 100 invocations)
- ❌ Cold starts add latency (~2-5s)
- ❌ Subprocess management (MCP server) may be unreliable

**Estimated Costs:**
- 100 syncs/day: ~$12/month (Functions + Firestore)
- 1000 syncs/day: ~$120/month

---

## Option 2: Hybrid Architecture ⭐ RECOMMENDED

### Overview
Use Firebase Functions for HTTP endpoints only, Cloud Tasks for queueing, and Cloud Run for long-running agent execution.

### Architecture
```
iOS Shortcuts → Firebase Functions (HTTP) → Cloud Tasks → Cloud Run (Agent Executor)
                         ↓                                      ↓
                    Firestore (status)              Firestore (results) + Spotify
```

### Why This is Best
1. **Optimal cost**: Functions idle after HTTP response (~0.1s), Cloud Run handles expensive processing
2. **No timeout issues**: Cloud Run supports up to 60 minutes
3. **Better reliability**: Cloud Tasks provides automatic retry with exponential backoff
4. **Preserves Agent SDK**: Keep intelligent AI orchestration
5. **Scalable**: Each component scales independently

### Changes Required

#### 1. Firebase Function (Fast HTTP endpoint)
```python
# functions/main.py
from firebase_functions import https_fn
from google.cloud import tasks_v2, firestore
import json
import uuid
import time

db = firestore.Client()
tasks_client = tasks_v2.CloudTasksClient()

PROJECT_ID = "your-project-id"
LOCATION = "us-central1"
CLOUD_RUN_URL = "https://spotify-agent-xxxxx.run.app"

@https_fn.on_request()
def sync_song(req: https_fn.Request):
    """Accept sync request and queue background task."""
    data = req.get_json()

    # Generate workflow ID
    workflow_id = f"agent-sync-{data.get('user_id', 'anonymous')}-{int(time.time())}-{uuid.uuid4().hex[:5]}"

    # Store initial status in Firestore
    db.collection('sync_results').document(workflow_id).set({
        'status': 'queued',
        'created_at': firestore.SERVER_TIMESTAMP,
        'track_name': data['track_name'],
        'artist': data['artist'],
        'album': data.get('album'),
        'playlist_id': data['playlist_id']
    })

    # Create Cloud Task to execute on Cloud Run
    task = {
        'http_request': {
            'http_method': tasks_v2.HttpMethod.POST,
            'url': f'{CLOUD_RUN_URL}/execute',
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'workflow_id': workflow_id,
                'track_name': data['track_name'],
                'artist': data['artist'],
                'album': data.get('album'),
                'playlist_id': data['playlist_id'],
                'user_id': data.get('user_id', 'anonymous'),
                'use_ai_disambiguation': data.get('use_ai_disambiguation', True)
            }).encode()
        }
    }

    # Create task in queue
    parent = tasks_client.queue_path(PROJECT_ID, LOCATION, 'spotify-sync-queue')
    tasks_client.create_task(request={'parent': parent, 'task': task})

    return {
        'workflow_id': workflow_id,
        'status': 'accepted',
        'message': f"Agent is searching for '{data['track_name']}' by {data['artist']}...",
        'status_url': f'/api/v1/sync/{workflow_id}'
    }

@https_fn.on_request()
def get_sync_status(req: https_fn.Request):
    """Get sync status from Firestore."""
    # Extract workflow_id from path
    workflow_id = req.path.split('/')[-1]

    doc = db.collection('sync_results').document(workflow_id).get()

    if not doc.exists:
        return {'status': 'not_found', 'workflow_id': workflow_id}

    return doc.to_dict()

@https_fn.on_request()
def health_check(req: https_fn.Request):
    """Health check endpoint."""
    return {
        'status': 'healthy',
        'mode': 'hybrid_firebase_cloudrun',
        'message': 'Firebase Functions + Cloud Run architecture'
    }
```

#### 2. Cloud Run Service (Agent executor)
```python
# cloudrun/main.py
from fastapi import FastAPI, HTTPException
from google.cloud import firestore
from pydantic import BaseModel
import logging

# Import existing agent executor
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from agent_executor import execute_music_sync_with_agent
from models.data_models import SongMetadata

app = FastAPI(title="Spotify Agent Executor")
db = firestore.Client()

logger = logging.getLogger(__name__)

class ExecuteRequest(BaseModel):
    workflow_id: str
    track_name: str
    artist: str
    album: str | None = None
    playlist_id: str
    user_id: str = "anonymous"
    use_ai_disambiguation: bool = True

@app.post("/execute")
async def execute_sync(request: ExecuteRequest):
    """Execute agent-based sync (long-running)."""
    workflow_id = request.workflow_id

    logger.info(f"[{workflow_id}] Starting agent execution")

    # Update status to running
    db.collection('sync_results').document(workflow_id).update({
        'status': 'running',
        'started_at': firestore.SERVER_TIMESTAMP
    })

    try:
        # Create song metadata
        song_metadata = SongMetadata(
            title=request.track_name,
            artist=request.artist,
            album=request.album
        )

        # Execute agent
        result = await execute_music_sync_with_agent(
            song_metadata=song_metadata,
            playlist_id=request.playlist_id,
            user_id=request.user_id,
            use_ai_disambiguation=request.use_ai_disambiguation
        )

        # Store results in Firestore
        db.collection('sync_results').document(workflow_id).update({
            'status': 'completed',
            'completed_at': firestore.SERVER_TIMESTAMP,
            'result': {
                'success': result.success,
                'message': result.message,
                'matched_track_uri': result.matched_track_uri,
                'matched_track_name': result.matched_track_name,
                'matched_artist': result.matched_artist,
                'confidence_score': result.confidence_score,
                'match_method': result.match_method,
                'execution_time_seconds': result.execution_time_seconds,
                'agent_reasoning': result.agent_reasoning
            }
        })

        logger.info(f"[{workflow_id}] ✅ Success: {result.message}")

        return {'success': True, 'workflow_id': workflow_id}

    except Exception as e:
        logger.error(f"[{workflow_id}] ❌ Failed: {str(e)}", exc_info=True)

        db.collection('sync_results').document(workflow_id).update({
            'status': 'failed',
            'completed_at': firestore.SERVER_TIMESTAMP,
            'error': str(e)
        })

        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        'status': 'healthy',
        'service': 'spotify-agent-executor',
        'mode': 'cloud_run'
    }
```

#### 3. Cloud Run Dockerfile
```dockerfile
# cloudrun/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Run with gunicorn for production
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 300 --worker-class uvicorn.workers.UvicornWorker cloudrun.main:app
```

#### 4. Cloud Run requirements.txt
```txt
# Web Framework
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
gunicorn>=21.2.0

# Google Cloud
google-cloud-firestore>=2.14.0
google-cloud-secret-manager>=2.18.0

# Agent SDK & Spotify
claude-agent-sdk>=0.1.0
anthropic>=0.39.0
spotipy>=2.24.0
mcp>=1.0.0

# Other dependencies
python-dotenv>=1.0.0
pydantic>=2.10.0
```

#### 5. Project Structure
```
spotify-mcp-integration/
├── functions/              # Firebase Functions (lightweight)
│   ├── main.py            # HTTP endpoints only
│   ├── requirements.txt   # Minimal dependencies
│   └── .env.yaml          # Config
│
├── cloudrun/              # Cloud Run service (heavy processing)
│   ├── main.py           # Agent executor service
│   ├── Dockerfile        # Container definition
│   ├── requirements.txt  # Full dependencies
│   └── .dockerignore     # Ignore unnecessary files
│
├── shared/               # Shared code (symlinked or copied)
│   ├── agent_executor.py
│   ├── models/
│   └── mcp_server/
│
├── firebase.json         # Firebase config
├── .firebaserc          # Firebase project config
└── README.md
```

### Deployment Steps

```bash
# 1. Set up GCP project
export PROJECT_ID="your-project-id"
export REGION="us-central1"

gcloud config set project $PROJECT_ID

# 2. Enable APIs
gcloud services enable \
  cloudfunctions.googleapis.com \
  cloudtasks.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  firestore.googleapis.com

# 3. Create secrets
echo -n "your-anthropic-api-key" | gcloud secrets create anthropic-api-key --data-file=-
echo -n "your-spotify-client-id" | gcloud secrets create spotify-client-id --data-file=-
echo -n "your-spotify-client-secret" | gcloud secrets create spotify-client-secret --data-file=-

# 4. Create Cloud Tasks queue
gcloud tasks queues create spotify-sync-queue \
  --location=$REGION \
  --max-concurrent-dispatches=10 \
  --max-attempts=3 \
  --min-backoff=60s \
  --max-backoff=3600s

# 5. Build and deploy Cloud Run service
cd cloudrun

# Copy shared code
cp -r ../agent_executor.py .
cp -r ../models .
cp -r ../mcp_server .

# Deploy
gcloud run deploy spotify-agent \
  --source . \
  --region $REGION \
  --timeout 300 \
  --memory 1Gi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 100 \
  --set-secrets="ANTHROPIC_API_KEY=anthropic-api-key:latest,SPOTIFY_CLIENT_ID=spotify-client-id:latest,SPOTIFY_CLIENT_SECRET=spotify-client-secret:latest" \
  --allow-unauthenticated

# Save Cloud Run URL
export CLOUD_RUN_URL=$(gcloud run services describe spotify-agent --region $REGION --format='value(status.url)')

# 6. Deploy Firebase Functions
cd ../functions

# Update main.py with CLOUD_RUN_URL
sed -i "s|CLOUD_RUN_URL = .*|CLOUD_RUN_URL = \"$CLOUD_RUN_URL\"|" main.py

firebase deploy --only functions

# 7. Store Spotify OAuth token in Firestore
# Run this locally after authenticating
python ../scripts/store_spotify_token_firestore.py
```

### Pros & Cons

**Pros:**
- ✅ Optimal cost (Functions ~$0.01/100 requests, Cloud Run ~$0.05/100 executions)
- ✅ No timeout issues (Cloud Run allows up to 60min)
- ✅ Better reliability with Cloud Tasks retry
- ✅ Scalable architecture
- ✅ Separate concerns (HTTP vs processing)
- ✅ Preserves Agent SDK intelligence
- ✅ Can handle concurrent requests efficiently
- ✅ Firebase Functions cold start doesn't affect processing time

**Cons:**
- ⚠️ More complex architecture
- ⚠️ Requires Cloud Run + Cloud Tasks setup
- ⚠️ More deployment steps
- ⚠️ Need to manage two services

**Estimated Costs:**
- 100 syncs/day: ~$3-5/month
- 1000 syncs/day: ~$30-40/month

**Breakdown:**
- Firebase Functions: $0.01/100 invocations (HTTP only, <100ms)
- Cloud Run: $0.05/100 executions (22-25s each)
- Cloud Tasks: $0.40/million operations
- Firestore: ~$1-2/month for reads/writes

---

## Option 3: Serverless-First Redesign

### Overview
Break agent execution into smaller steps, each as a separate Firebase Function.

### Architecture
```
Firebase Functions:
1. sync_song() → Queue task, return immediately
2. search_track() → Search Spotify, store candidates in Firestore
3. match_track() → AI disambiguation, pick best match
4. add_to_playlist() → Add track to playlist
5. verify_sync() → Confirm addition

Orchestration: Cloud Tasks + Firestore (state machine)
```

### Changes Required

#### 1. Split into discrete functions
```python
# functions/main.py
from firebase_functions import https_fn, tasks_fn
from google.cloud import tasks_v2, firestore
import anthropic

db = firestore.Client()
tasks_client = tasks_v2.CloudTasksClient()

@https_fn.on_request()
def sync_song(req: https_fn.Request):
    """Accept sync request and start workflow."""
    data = req.get_json()
    workflow_id = generate_workflow_id()

    # Initialize workflow in Firestore
    db.collection('sync_workflows').document(workflow_id).set({
        'status': 'searching',
        'step': 1,
        'total_steps': 4,
        'track_name': data['track_name'],
        'artist': data['artist'],
        'playlist_id': data['playlist_id'],
        'created_at': firestore.SERVER_TIMESTAMP
    })

    # Trigger search step
    enqueue_task('search_track', {'workflow_id': workflow_id})

    return {'workflow_id': workflow_id, 'status': 'accepted'}

@https_fn.on_request()
def search_track(req: https_fn.Request):
    """Step 1: Search Spotify for candidates."""
    data = req.get_json()
    workflow_id = data['workflow_id']

    # Get workflow data
    doc = db.collection('sync_workflows').document(workflow_id).get()
    workflow = doc.to_dict()

    # Search Spotify using MCP (direct call, not via Agent SDK)
    from mcp_server.spotify_server import search_tracks_direct

    candidates = search_tracks_direct(
        track=workflow['track_name'],
        artist=workflow['artist']
    )

    # Update Firestore
    db.collection('sync_workflows').document(workflow_id).update({
        'status': 'matching',
        'step': 2,
        'candidates': [c.dict() for c in candidates]
    })

    # Trigger next step
    enqueue_task('match_track', {'workflow_id': workflow_id})

    return {'success': True}

@https_fn.on_request()
def match_track(req: https_fn.Request):
    """Step 2: Use Claude API to pick best match."""
    data = req.get_json()
    workflow_id = data['workflow_id']

    doc = db.collection('sync_workflows').document(workflow_id).get()
    workflow = doc.to_dict()
    candidates = workflow['candidates']

    # Call Claude API directly for disambiguation
    client = anthropic.Anthropic()

    prompt = f"""Given these Spotify search results for "{workflow['track_name']}" by {workflow['artist']},
    pick the best match. Return only the index (0-based) of the best match.

    Candidates:
    {json.dumps(candidates, indent=2)}
    """

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}]
    )

    best_index = int(response.content[0].text.strip())
    best_match = candidates[best_index]

    # Update Firestore
    db.collection('sync_workflows').document(workflow_id).update({
        'status': 'adding',
        'step': 3,
        'best_match': best_match
    })

    # Trigger next step
    enqueue_task('add_to_playlist', {'workflow_id': workflow_id})

    return {'success': True}

@https_fn.on_request()
def add_to_playlist(req: https_fn.Request):
    """Step 3: Add track to playlist."""
    data = req.get_json()
    workflow_id = data['workflow_id']

    doc = db.collection('sync_workflows').document(workflow_id).get()
    workflow = doc.to_dict()

    # Add to playlist using Spotify API
    from mcp_server.spotify_server import add_track_to_playlist_direct

    add_track_to_playlist_direct(
        track_uri=workflow['best_match']['uri'],
        playlist_id=workflow['playlist_id']
    )

    # Update Firestore
    db.collection('sync_workflows').document(workflow_id).update({
        'status': 'completed',
        'step': 4,
        'result': {
            'success': True,
            'matched_track': workflow['best_match']
        },
        'completed_at': firestore.SERVER_TIMESTAMP
    })

    return {'success': True}

def enqueue_task(function_name: str, data: dict):
    """Helper to enqueue Cloud Task."""
    task = {
        'http_request': {
            'http_method': tasks_v2.HttpMethod.POST,
            'url': f'https://{PROJECT_ID}.cloudfunctions.net/{function_name}',
            'body': json.dumps(data).encode()
        }
    }
    parent = tasks_client.queue_path(PROJECT_ID, LOCATION, 'spotify-sync-queue')
    tasks_client.create_task(request={'parent': parent, 'task': task})
```

#### 2. State machine in Firestore
```javascript
// Firestore document structure
{
  "workflow_id": "...",
  "status": "matching",  // queued → searching → matching → adding → completed
  "step": 2,
  "total_steps": 4,
  "song_metadata": {
    "track_name": "...",
    "artist": "...",
    "album": "..."
  },
  "candidates": [...],      // Stored after step 1
  "best_match": {...},      // Stored after step 2
  "result": {...},          // Stored after step 3
  "created_at": timestamp,
  "completed_at": timestamp
}
```

### Pros & Cons

**Pros:**
- ✅ Each function is fast (<10s), no timeout risk
- ✅ Fine-grained control over each step
- ✅ Easy to retry individual steps
- ✅ Can optimize each step independently
- ✅ Lowest costs (shorter execution times)
- ✅ All in Firebase ecosystem

**Cons:**
- ❌ Significant refactoring required (3-4 weeks)
- ❌ More complex state management
- ❌ Loss of Agent SDK benefits (automatic tool orchestration)
- ❌ More functions to maintain (4-5 instead of 2)
- ❌ Harder to debug (distributed traces needed)
- ❌ Need to handle partial failures manually

**Estimated Costs:**
- 100 syncs/day: ~$2-3/month
- 1000 syncs/day: ~$20-25/month

---

## Comparison Matrix

| Aspect | Option 1: Direct | Option 2: Hybrid ⭐ | Option 3: Serverless |
|--------|------------------|---------------------|----------------------|
| **Implementation Time** | 1-2 days | 1-2 weeks | 3-4 weeks |
| **Code Changes** | Minimal | Moderate | Extensive |
| **Complexity** | Low | Medium | High |
| **Cost (100/day)** | $12/month | $3-5/month | $2-3/month |
| **Cost (1000/day)** | $120/month | $30-40/month | $20-25/month |
| **Timeout Risk** | ⚠️ High | ✅ None | ✅ None |
| **Agent SDK** | ✅ Preserved | ✅ Preserved | ❌ Lost |
| **Scalability** | ⚠️ Limited | ✅ Excellent | ✅ Excellent |
| **Reliability** | ⚠️ Medium | ✅ High (Tasks retry) | ✅ High (Tasks retry) |
| **Debugging** | ✅ Easy | ⚠️ Medium | ❌ Hard |
| **Maintenance** | ✅ Low | ⚠️ Medium | ❌ High |
| **Cold Start Impact** | ❌ Affects total time | ✅ Only HTTP response | ✅ Only HTTP response |
| **Recommended For** | Quick POC | **Production use** | Cost-sensitive at scale |

---

## Recommendation: Option 2 (Hybrid Architecture)

### Why Option 2 is Best

1. **Cost-Performance Balance**
   - Functions respond in <100ms (cheap)
   - Cloud Run handles expensive processing
   - 10x cheaper than Option 1 at scale

2. **Reliability**
   - Cloud Tasks automatic retry with exponential backoff
   - No timeout issues (Cloud Run supports 60min)
   - Firestore ensures no lost results

3. **Preserves Intelligence**
   - Keeps Agent SDK's automatic tool orchestration
   - Claude's reasoning capabilities intact
   - No need to rewrite AI logic

4. **Production Ready**
   - Battle-tested GCP services
   - Easy monitoring with Cloud Logging
   - Simple to scale

5. **Moderate Complexity**
   - More work than Option 1, but manageable
   - Much simpler than Option 3
   - Clear separation of concerns

### When to Consider Alternatives

**Choose Option 1 if:**
- You need to ship in <2 days
- Budget is not a concern
- Traffic is very low (<10 syncs/day)

**Choose Option 3 if:**
- You need extreme cost optimization
- You have 3-4 weeks for implementation
- You're comfortable with distributed systems
- You want to move away from Agent SDK

---

## Migration Roadmap for Option 2 (Recommended)

### Phase 1: Preparation (3-4 days)

**Day 1: GCP Setup**
- [ ] Create GCP project
- [ ] Enable required APIs
  - Cloud Functions
  - Cloud Run
  - Cloud Tasks
  - Firestore
  - Secret Manager
- [ ] Set up billing alerts
- [ ] Install gcloud CLI and Firebase CLI

**Day 2: Environment Migration**
- [ ] Create secrets in Secret Manager
  - `ANTHROPIC_API_KEY`
  - `SPOTIFY_CLIENT_ID`
  - `SPOTIFY_CLIENT_SECRET`
- [ ] Set up Firestore database
  - Create collections: `sync_results`, `config`
- [ ] Test Firestore locally with emulator

**Day 3: Dependencies**
- [ ] Split requirements.txt into:
  - `functions/requirements.txt` (minimal)
  - `cloudrun/requirements.txt` (full)
- [ ] Add Firebase dependencies
- [ ] Test builds locally

**Day 4: Spotify OAuth**
- [ ] Create script to store OAuth token in Firestore
- [ ] Update `mcp_server/spotify_server.py` to read from Firestore
- [ ] Test token refresh logic

### Phase 2: Code Migration (4-5 days)

**Day 5-6: Firebase Functions**
- [ ] Create `functions/main.py`
- [ ] Implement HTTP endpoints:
  - `sync_song()` - Accept request, queue task
  - `get_sync_status()` - Read from Firestore
  - `health_check()` - Health endpoint
- [ ] Test locally with Functions emulator

**Day 7-8: Cloud Run Service**
- [ ] Create `cloudrun/main.py`
- [ ] Implement `/execute` endpoint
- [ ] Integrate with existing `agent_executor.py`
- [ ] Add Firestore result storage
- [ ] Create Dockerfile
- [ ] Test locally with Docker

**Day 9: Cloud Tasks Integration**
- [ ] Create Cloud Tasks queue
- [ ] Update Firebase Functions to enqueue tasks
- [ ] Test end-to-end locally

### Phase 3: Deployment & Testing (3-4 days)

**Day 10: Initial Deployment**
- [ ] Deploy Cloud Run service to staging
- [ ] Deploy Firebase Functions to staging
- [ ] Verify secrets are accessible
- [ ] Test health endpoints

**Day 11: Integration Testing**
- [ ] Test sync flow end-to-end
- [ ] Verify Firestore updates
- [ ] Test error handling and retries
- [ ] Check Cloud Logging

**Day 12: Performance Testing**
- [ ] Load test with 10, 50, 100 concurrent requests
- [ ] Measure cold start impact
- [ ] Optimize memory/CPU settings
- [ ] Tune Cloud Tasks queue settings

**Day 13: Production Deployment**
- [ ] Deploy to production
- [ ] Update iOS Shortcut with new URL
- [ ] Monitor first few syncs
- [ ] Set up alerts

### Phase 4: Monitoring & Optimization (Ongoing)

**Week 3:**
- [ ] Set up Cloud Monitoring dashboards
- [ ] Configure alerting policies
  - Error rate > 5%
  - Latency > 30s
  - Cost spike
- [ ] Enable Cloud Trace for debugging
- [ ] Create runbook for common issues

**Week 4:**
- [ ] Optimize based on production metrics
- [ ] Fine-tune timeout and retry settings
- [ ] Document operational procedures
- [ ] Train team on new architecture

---

## Key Files to Create/Modify

### CREATE (New Files)

```
functions/
  main.py                    # Firebase Functions HTTP endpoints
  requirements.txt           # Minimal dependencies
  .env.yaml                  # Environment config

cloudrun/
  main.py                    # Cloud Run agent executor
  Dockerfile                 # Container definition
  requirements.txt           # Full dependencies
  .dockerignore             # Ignore patterns

scripts/
  store_spotify_token_firestore.py  # OAuth token migration
  deploy.sh                  # Deployment automation

firebase.json                # Firebase configuration
.firebaserc                 # Firebase project settings
```

### MODIFY (Existing Files)

```
agent_executor.py
  - Add Firestore result storage
  - Handle GCP Secret Manager for API keys

mcp_server/spotify_server.py
  - Read OAuth tokens from Firestore
  - Implement token refresh logic with Firestore update

.env.example
  - Add GCP_PROJECT_ID
  - Add FIRESTORE_COLLECTION
  - Add CLOUD_TASKS_QUEUE
```

### KEEP UNCHANGED

```
models/                      # Data models work as-is
api/models.py               # Request/response models
iOS Shortcuts               # Only URL change needed
```

---

## Cost Analysis

### Option 2 Detailed Cost Breakdown

**Assumptions:**
- 100 syncs/day = 3,000/month
- 1,000 syncs/day = 30,000/month
- Avg execution time: 22s
- Firebase Functions response time: 100ms

**Firebase Functions (HTTP endpoints)**
- Invocations: 3,000/month (100/day)
  - Cost: $0.40 per million = $0.001
- Compute time: 3,000 × 0.1s = 300s
  - Cost: $0.0000025 per GB-second × 256MB = negligible
- **Total: < $0.01/month**

**Cloud Run (Agent execution)**
- Invocations: 3,000/month
  - Cost: $0.40 per million = $0.001
- Compute time: 3,000 × 22s = 66,000s = 18.3 hours
  - CPU: 1 vCPU × 18.3 hours × $0.00002400/vCPU-second
  - Memory: 1 GiB × 18.3 hours × $0.00000250/GiB-second
  - Cost: ~$1.60 + $0.17 = ~$1.77
- **Total: ~$1.78/month**

**Cloud Tasks**
- Operations: 3,000/month
  - Cost: $0.40 per million = $0.001
- **Total: < $0.01/month**

**Firestore**
- Documents written: 9,000 (3 per sync)
  - Cost: $0.18 per 100k writes = $0.016
- Documents read: 3,000
  - Cost: $0.06 per 100k reads = $0.002
- Storage: < 1 GB
  - Cost: $0.18/GB = negligible
- **Total: ~$0.02/month**

**Anthropic API (external)**
- Claude API calls: 3,000 × $0.015 = $45/month
- **Total: $45/month** (same as current)

**GRAND TOTAL: ~$47/month for 100 syncs/day**

Scaling to 1,000 syncs/day:
- Firebase Functions: < $0.01
- Cloud Run: ~$17.80
- Cloud Tasks: < $0.01
- Firestore: ~$0.20
- Anthropic API: $450
- **GRAND TOTAL: ~$468/month**

### Cost Comparison

| Traffic | Option 1 | Option 2 ⭐ | Option 3 |
|---------|----------|-------------|----------|
| **100/day** | ~$60/month | ~$47/month | ~$45/month |
| **1,000/day** | ~$570/month | ~$468/month | ~$452/month |
| **10,000/day** | ~$5,700/month | ~$4,680/month | ~$4,520/month |

*Note: Anthropic API costs ($45/100 syncs) dominate at scale - same across all options*

---

## Next Steps

### Ready to Proceed?

To implement **Option 2 (Hybrid Architecture)**, I can:

1. **Create the Firebase Functions setup**
   - `functions/main.py` with HTTP endpoints
   - `functions/requirements.txt`
   - `firebase.json` configuration

2. **Create the Cloud Run service**
   - `cloudrun/main.py` with agent executor
   - `cloudrun/Dockerfile`
   - `cloudrun/requirements.txt`

3. **Migration scripts**
   - Spotify OAuth token migration to Firestore
   - Deployment automation script
   - Local testing setup

4. **Documentation**
   - Deployment guide
   - Troubleshooting guide
   - Architecture diagrams

**Would you like me to start implementing Option 2?**

Or would you prefer to:
- Discuss any of the options further?
- Explore a different approach?
- See code examples for specific components?
