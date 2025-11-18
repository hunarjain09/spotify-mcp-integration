# Firebase Functions Quick Start

Get your Spotify MCP Integration running on Firebase Functions in 10 minutes.

## Prerequisites

- Node.js and npm installed
- Python 3.11+
- Google account
- Anthropic API key
- Spotify Developer credentials

## Step 1: Install Firebase CLI (2 min)

```bash
npm install -g firebase-tools
```

## Step 2: Create Firebase Project (2 min)

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click "Add project"
3. Name it: `spotify-mcp-sync` (or your choice)
4. Disable Google Analytics (optional)
5. Click "Create project"
6. Note your **Project ID** (e.g., `spotify-mcp-sync-abc123`)

## Step 3: Configure Project (1 min)

```bash
# Login to Firebase
firebase login

# Set your project
firebase use YOUR_PROJECT_ID
```

Update `.firebaserc`:
```json
{
  "projects": {
    "default": "YOUR_PROJECT_ID"
  }
}
```

## Step 4: Enable Firestore (1 min)

1. In Firebase Console → Build → Firestore Database
2. Click "Create database"
3. Choose "Production mode"
4. Select region (e.g., `us-central1`)
5. Click "Enable"

## Step 5: Set Secrets (2 min)

```bash
# Anthropic API key
firebase functions:secrets:set ANTHROPIC_API_KEY
# Paste your key (starts with sk-ant-...)

# Spotify credentials
firebase functions:secrets:set SPOTIFY_CLIENT_ID
# Paste your Spotify client ID

firebase functions:secrets:set SPOTIFY_CLIENT_SECRET
# Paste your Spotify client secret
```

## Step 6: Authenticate Spotify Locally (1 min)

This creates your Spotify OAuth token:

```bash
# Run MCP server to authenticate
python mcp_server/spotify_server.py

# Browser will open → Authorize the app
# Press Ctrl+C after "✓ Spotify MCP server initialized successfully"
```

This creates `.cache-spotify` file.

## Step 7: Upload Spotify Token to Firestore (1 min)

```bash
python scripts/store_spotify_token.py
```

You should see:
```
✅ Spotify OAuth token uploaded to Firestore
```

## Step 8: Deploy! (2 min)

```bash
firebase deploy --only functions
```

Wait for deployment (~1-2 minutes).

## Step 9: Test (1 min)

You'll see your function URL:
```
https://us-central1-YOUR_PROJECT.cloudfunctions.net/spotify_sync
```

**Test health endpoint:**
```bash
curl https://us-central1-YOUR_PROJECT.cloudfunctions.net/spotify_sync/health
```

Should return:
```json
{"status": "healthy", "mode": "agent_sdk"}
```

**Test sync:**
```bash
curl -X POST https://us-central1-YOUR_PROJECT.cloudfunctions.net/spotify_sync/api/v1/sync \
  -H "Content-Type: application/json" \
  -d '{
    "track_name": "Bohemian Rhapsody",
    "artist": "Queen",
    "playlist_id": "YOUR_PLAYLIST_ID"
  }'
```

Should return:
```json
{
  "workflow_id": "agent-sync-anonymous-...",
  "status": "accepted",
  "message": "Agent is searching..."
}
```

## Step 10: Update iOS Shortcut

In your iOS Shortcut, change the URL from:
```
http://192.168.1.100:8000/api/v1/sync
```

To:
```
https://us-central1-YOUR_PROJECT.cloudfunctions.net/spotify_sync/api/v1/sync
```

## Done! 🎉

Your Spotify sync is now running on Firebase Functions!

## View Logs

```bash
firebase functions:log --only spotify_sync
```

## Common Issues

### "Module not found"

All dependencies must be in `functions/requirements.txt`. They are already there.

### "Function timeout"

The function has 60s max. Agent executor uses 55s. If timing out:
- Check logs: `firebase functions:log`
- Reduce complexity in agent executor
- Ensure Spotify token is valid

### "Spotify authentication failed"

Re-run:
```bash
python mcp_server/spotify_server.py
python scripts/store_spotify_token.py
```

### "Firestore permission denied"

Enable Firestore in Firebase Console (Step 4).

## Cost

**Free tier includes:**
- 2M function invocations/month
- 400K GB-seconds/month

**Your usage (~100 syncs/day):**
- ~3,000 invocations/month
- Well within free tier ✅

**Only pay for Anthropic API:**
- ~$0.015 per sync
- 100 syncs/day = ~$45/month

## Next Steps

- Monitor usage in [Firebase Console](https://console.firebase.google.com/)
- Set up billing alerts
- Configure custom domain (optional)
- Add authentication (optional)

## Get Help

- Check logs: `firebase functions:log --only spotify_sync`
- Read full guide: [FIREBASE_DEPLOYMENT_GUIDE.md](./FIREBASE_DEPLOYMENT_GUIDE.md)
- Check [Firebase docs](https://firebase.google.com/docs/functions)
