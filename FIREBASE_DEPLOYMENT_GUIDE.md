# Firebase Functions Deployment Guide

This guide shows you how to deploy the Spotify MCP Integration to Firebase Functions.

## Architecture

```
iOS Shortcuts → Firebase Functions → Agent SDK → MCP Server → Spotify API
                         ↓
                    Firestore (OPTIONAL)
```

**Key Features:**
- **Fire-and-forget**: POST returns workflow_id immediately, processing happens in background
- **Firestore is OPTIONAL**: Works locally without it (in-memory), automatically uses Firestore in Firebase
- **Single Function**: All logic in one Firebase Function (no Cloud Run/Tasks needed)
- **60s timeout**: Agent executor has 55s to complete before function times out

**Components:**
- **Firebase Functions**: Single HTTP function handling all API endpoints
- **Firestore**: Optional persistent storage for results across function invocations (auto-enabled in Firebase)
- **Agent SDK**: Runs within the function with 55-second timeout
- **MCP Server**: Subprocess within the function

## Prerequisites

1. **Firebase CLI**
   ```bash
   npm install -g firebase-tools
   ```

2. **Firebase Project**
   - Create a project at [Firebase Console](https://console.firebase.google.com/)
   - Note your project ID

3. **Google Cloud (for Firestore)**
   - Enable Firestore in your Firebase project
   - Choose Native mode

4. **API Keys**
   - Anthropic API key (from console.anthropic.com)
   - Spotify credentials (from developer.spotify.com)

## Setup

### 1. Login to Firebase

```bash
firebase login
```

### 2. Configure Project

Edit `.firebaserc` and replace `YOUR_FIREBASE_PROJECT_ID` with your actual project ID:

```json
{
  "projects": {
    "default": "your-actual-project-id"
  }
}
```

### 3. Set Environment Secrets

Firebase Functions uses Secret Manager for sensitive data:

```bash
# Set Anthropic API key
firebase functions:secrets:set ANTHROPIC_API_KEY
# Enter your key when prompted

# Set Spotify credentials
firebase functions:secrets:set SPOTIFY_CLIENT_ID
firebase functions:secrets:set SPOTIFY_CLIENT_SECRET

# Optional: Set default playlist ID
firebase functions:secrets:set DEFAULT_PLAYLIST_ID
```

### 4. Spotify OAuth Setup

The Spotify MCP server needs OAuth tokens. Run this locally first:

```bash
# Authenticate with Spotify (creates .cache-spotify)
python mcp_server/spotify_server.py
```

This opens a browser for you to authorize the app. After authorization, you'll have a `.cache-spotify` file.

**Store the token in Firestore:**

```bash
python scripts/store_spotify_token.py
```

This uploads your Spotify OAuth token to Firestore so Firebase Functions can access it.

## Deployment

### Method 1: Quick Deploy

```bash
# Deploy everything
firebase deploy --only functions
```

### Method 2: Deploy Specific Function

```bash
# Deploy only the spotify_sync function
firebase deploy --only functions:spotify_sync
```

## Testing

### 1. Get Function URL

After deployment, Firebase will show your function URL:
```
https://us-central1-YOUR_PROJECT_ID.cloudfunctions.net/spotify_sync
```

### 2. Test Health Endpoint

```bash
curl https://YOUR_FUNCTION_URL/health
```

Expected response:
```json
{
  "status": "healthy",
  "mode": "agent_sdk",
  "message": "Agent-powered Spotify sync is operational"
}
```

### 3. Test Sync

```bash
curl -X POST https://YOUR_FUNCTION_URL/api/v1/sync \
  -H "Content-Type: application/json" \
  -d '{
    "track_name": "Bohemian Rhapsody",
    "artist": "Queen",
    "album": "A Night at the Opera",
    "playlist_id": "YOUR_PLAYLIST_ID"
  }'
```

Expected response:
```json
{
  "workflow_id": "agent-sync-anonymous-1234567890-abc12",
  "status": "accepted",
  "message": "Agent is searching for 'Bohemian Rhapsody' by Queen...",
  "status_url": "/api/v1/sync/agent-sync-anonymous-1234567890-abc12"
}
```

### 4. Check Status

```bash
curl https://YOUR_FUNCTION_URL/api/v1/sync/WORKFLOW_ID
```

## Configuration

### Timeout

The function is configured with a 60-second timeout (maximum for HTTP functions). The agent executor uses 55 seconds to ensure it completes before the function times out.

To adjust:

**functions/main.py:**
```python
@https_fn.on_request(
    timeout_sec=60,  # Max for HTTP functions
    ...
)
```

**agent_executor.py:**
```python
timeout_seconds: int = 55  # 5s buffer
```

### Memory

Default is 1GB. To adjust:

**functions/main.py:**
```python
@https_fn.on_request(
    memory=options.MemoryOption.GB_2,  # Increase to 2GB
    ...
)
```

Options: `MB_256`, `MB_512`, `GB_1`, `GB_2`, `GB_4`, `GB_8`

### Region

Default is `us-central1`. To change:

```bash
# In firebase.json
{
  "functions": {
    "region": "europe-west1"
  }
}
```

## Firestore Setup

### Collection Structure

The app uses one collection:

**`sync_results`**: Stores sync operation results
```javascript
{
  "workflow_id": "agent-sync-...",
  "success": true,
  "message": "Successfully synced...",
  "matched_track_uri": "spotify:track:xxxxx",
  "matched_track_name": "Song Title",
  "matched_artist": "Artist Name",
  "confidence_score": 0.95,
  "match_method": "exact_match",
  "execution_time_seconds": 22.4,
  "agent_reasoning": "Picked this match because...",
  "error": null,
  "timestamp": Timestamp
}
```

### Security Rules

Create Firestore security rules:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Allow Functions to read/write sync_results
    match /sync_results/{document} {
      allow read, write: if request.auth != null || request.auth.token.firebase.sign_in_provider == 'custom';
    }

    // Allow Functions to read config
    match /config/{document} {
      allow read: if request.auth != null;
      allow write: if false;  // Only allow writes via admin SDK
    }
  }
}
```

Deploy rules:
```bash
firebase deploy --only firestore:rules
```

## iOS Shortcuts Integration

### Update Shortcut URL

In your iOS Shortcut, update the API URL:

**Old (local):**
```
http://192.168.1.100:8000/api/v1/sync
```

**New (Firebase):**
```
https://us-central1-YOUR_PROJECT_ID.cloudfunctions.net/spotify_sync/api/v1/sync
```

## Monitoring

### View Logs

```bash
# Real-time logs
firebase functions:log --only spotify_sync

# Recent logs
firebase functions:log --only spotify_sync --lines 100
```

### Cloud Console

View detailed logs in [Google Cloud Console](https://console.cloud.google.com/):
- Logs Explorer: See all function executions
- Metrics: Track invocations, errors, latency
- Traces: Debug slow executions

### Set Up Alerts

In Cloud Console > Monitoring > Alerting:

1. **Error Rate Alert**
   - Metric: Cloud Function execution count
   - Filter: status = "error"
   - Condition: > 5% error rate
   - Notification: Email

2. **Latency Alert**
   - Metric: Cloud Function execution time
   - Condition: 95th percentile > 50s
   - Notification: Email

## Cost Estimation

Firebase Functions pricing (as of 2024):

**Free tier (per month):**
- 2 million invocations
- 400,000 GB-seconds
- 200,000 CPU-seconds
- 5 GB outbound networking

**Paid tier:**
- $0.40 per million invocations
- $0.0000025 per GB-second
- $0.0000100 per GHz-second

**Example costs:**

**100 syncs/day (3,000/month):**
- Invocations: 3,000 × $0.40/million = $0.001
- Compute: 3,000 × 25s × 1GB × $0.0000025 = $0.19
- **Total: ~$0.19/month** (within free tier)

**1,000 syncs/day (30,000/month):**
- Invocations: 30,000 × $0.40/million = $0.01
- Compute: 30,000 × 25s × 1GB × $0.0000025 = $1.88
- **Total: ~$1.89/month**

**Plus Anthropic API costs:**
- ~$0.015 per sync
- 100/day = $45/month
- 1,000/day = $450/month

## Troubleshooting

### "Module not found" Error

Make sure all dependencies are in `functions/requirements.txt` and the parent directory modules are importable.

**Check:**
```python
# In functions/main.py
sys.path.insert(0, str(Path(__file__).parent.parent))
```

### "Function timeout" Error

The function is timing out. Options:

1. **Reduce Agent SDK turns:**
   ```python
   # In agent_executor.py
   max_turns=5,  # Reduce from 10
   ```

2. **Skip verification step:**
   ```python
   allowed_tools=[
       "mcp__spotify__search_track",
       "mcp__spotify__add_track_to_playlist",
       # Skip: "mcp__spotify__verify_track_added",
   ]
   ```

3. **Use simpler prompts** (less reasoning)

### "Spotify authentication failed"

The OAuth token in Firestore is expired or missing.

**Fix:**
```bash
# Re-authenticate locally
python mcp_server/spotify_server.py

# Upload new token
python scripts/store_spotify_token.py
```

### "Firestore permission denied"

Update Firestore security rules to allow function access.

### "MCP server failed to start"

The subprocess can't start the MCP server.

**Check:**
1. Python path is correct
2. MCP server dependencies are installed
3. Logs show actual error

```bash
firebase functions:log --only spotify_sync
```

## Local Testing with Emulator

Test locally before deploying:

```bash
# Install emulator
firebase init emulators

# Start emulators
firebase emulators:start
```

This runs:
- Functions emulator: http://localhost:5001
- Firestore emulator: http://localhost:8080

**Test locally:**
```bash
curl -X POST http://localhost:5001/YOUR_PROJECT_ID/us-central1/spotify_sync/api/v1/sync \
  -H "Content-Type: application/json" \
  -d '{"track_name": "Test", "artist": "Artist", "playlist_id": "abc"}'
```

## Production Checklist

Before going to production:

- [ ] Set all secrets (ANTHROPIC_API_KEY, SPOTIFY_CLIENT_ID, etc.)
- [ ] Upload Spotify OAuth token to Firestore
- [ ] Configure Firestore security rules
- [ ] Test end-to-end with real track
- [ ] Set up monitoring alerts
- [ ] Configure billing alerts in GCP
- [ ] Update iOS Shortcut with production URL
- [ ] Test from iPhone on cellular (not just WiFi)
- [ ] Document any environment-specific configs

## Rollback

If deployment fails or has issues:

```bash
# List previous versions
firebase functions:list

# Rollback to previous version
gcloud functions deploy spotify_sync --source=PREVIOUS_VERSION
```

## Support

- **Firebase Docs**: https://firebase.google.com/docs/functions
- **GitHub Issues**: Create an issue in the repo
- **Logs**: Check `firebase functions:log` for errors

## Next Steps

1. **Set up CI/CD**: Automate deployments with GitHub Actions
2. **Add more endpoints**: Batch sync, playlist management, etc.
3. **Optimize costs**: Cache search results, reduce API calls
4. **Add analytics**: Track success rates, popular songs, etc.
