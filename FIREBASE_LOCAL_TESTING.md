# Firebase Local Testing with Emulators

Test your Firebase Functions locally before deploying to production using Firebase Emulators.

## Why Use Emulators?

✅ **Test before deploy** - Catch issues locally
✅ **No cloud costs** - Test without real Firebase usage
✅ **Faster iteration** - No deployment wait time
✅ **Safe testing** - Can't accidentally break production
✅ **Full debugging** - See all logs in real-time

## Quick Start

### 1. Install Firebase Emulators

```bash
firebase init emulators
```

**Select emulators to install:**
- [x] Functions Emulator
- [x] Firestore Emulator (if using USE_FIRESTORE=true)
- [ ] Others (optional)

**Accept defaults or customize:**
- Functions port: `5001` (default)
- Firestore port: `8080` (default)
- Emulator UI port: `4000` (default)

### 2. Configure Environment

Create `functions/.env.yaml` for local testing:

```yaml
# Enable/disable Firestore for testing
USE_FIRESTORE: 'false'  # or 'true' to test with Firestore
```

### 3. Start Emulators

```bash
firebase emulators:start
```

You'll see output like:
```
✔  functions[us-central1-spotify_sync]: http function initialized (http://localhost:5001/YOUR_PROJECT/us-central1/spotify_sync).
┌─────────────────────────────────────────────────────────────┐
│ ✔  All emulators ready! It is now safe to connect your app. │
│ i  View Emulator UI at http://localhost:4000               │
└─────────────────────────────────────────────────────────────┘
```

### 4. Test Your Function

**Health check:**
```bash
curl http://localhost:5001/YOUR_PROJECT/us-central1/spotify_sync/health
```

**Test sync:**
```bash
curl -X POST http://localhost:5001/YOUR_PROJECT/us-central1/spotify_sync/api/v1/sync \
  -H "Content-Type: application/json" \
  -d '{
    "track_name": "Bohemian Rhapsody",
    "artist": "Queen",
    "album": "A Night at the Opera",
    "playlist_id": "37i9dQZF1DXcBWIGoYBM5M"
  }'
```

### 5. View Logs and Data

Open **Emulator UI**: http://localhost:4000

**Functions Logs tab:**
- See all function executions
- View detailed logs
- Debug errors

**Firestore tab** (if USE_FIRESTORE=true):
- Browse `sync_results` collection
- View stored data
- Inspect documents

## Testing Scenarios

### Scenario 1: Test Fire-and-Forget (USE_FIRESTORE=false)

```yaml
# functions/.env.yaml
USE_FIRESTORE: 'false'
```

```bash
# Start emulators
firebase emulators:start

# Test POST (should return workflow_id with no status_url)
curl -X POST http://localhost:5001/YOUR_PROJECT/us-central1/spotify_sync/api/v1/sync \
  -H "Content-Type: application/json" \
  -d '{"track_name": "Test", "artist": "Artist", "playlist_id": "37i9dQZF1DXcBWIGoYBM5M"}'

# Expected response:
# {
#   "workflow_id": "agent-sync-...",
#   "status": "accepted",
#   "message": "Agent is searching...",
#   "status_url": null
# }

# Try GET status (should return 501)
curl http://localhost:5001/YOUR_PROJECT/us-central1/spotify_sync/api/v1/sync/WORKFLOW_ID
# Expected: 501 Not Implemented
```

### Scenario 2: Test with Firestore (USE_FIRESTORE=true)

```yaml
# functions/.env.yaml
USE_FIRESTORE: 'true'
```

```bash
# Start emulators (includes Firestore)
firebase emulators:start

# Test POST
curl -X POST http://localhost:5001/YOUR_PROJECT/us-central1/spotify_sync/api/v1/sync \
  -H "Content-Type: application/json" \
  -d '{"track_name": "Test", "artist": "Artist", "playlist_id": "37i9dQZF1DXcBWIGoYBM5M"}'

# Expected response includes status_url:
# {
#   "workflow_id": "agent-sync-...",
#   "status": "accepted",
#   "message": "...",
#   "status_url": "/api/v1/sync/agent-sync-..."
# }

# Check Firestore Emulator UI
# Go to http://localhost:4000 → Firestore tab
# See sync_results collection with your workflow
```

### Scenario 3: Test Error Handling

```bash
# Invalid playlist ID (wrong format)
curl -X POST http://localhost:5001/YOUR_PROJECT/us-central1/spotify_sync/api/v1/sync \
  -H "Content-Type: application/json" \
  -d '{"track_name": "Test", "artist": "Artist", "playlist_id": "INVALID"}'

# Expected: 422 Validation Error
```

## Configuration Files

### firebase.json

This is already configured correctly:

```json
{
  "functions": [
    {
      "source": "functions",
      "codebase": "spotify-sync",
      "runtime": "python311"
    }
  ],
  "emulators": {
    "functions": {
      "port": 5001
    },
    "firestore": {
      "port": 8080
    },
    "ui": {
      "enabled": true,
      "port": 4000
    }
  }
}
```

### functions/.env.yaml (for local testing)

```yaml
# Firestore Configuration
USE_FIRESTORE: 'false'  # Change to 'true' to test with Firestore

# These are loaded from your .env file automatically
# No need to duplicate secrets here for local testing
```

## Environment Variables in Emulator

**Option 1: Use local .env file** (recommended for development)

The emulator will read from your existing `.env` file:
```bash
# Your .env already has:
ANTHROPIC_API_KEY=sk-ant-...
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
```

**Option 2: Set in functions/.env.yaml** (for emulator-specific config)

```yaml
USE_FIRESTORE: 'false'
# Don't put secrets here - use .env instead
```

## Debugging Tips

### View All Logs

```bash
# Start emulators with verbose logging
firebase emulators:start --inspect-functions

# Or export logs
firebase emulators:export ./emulator-data
```

### Test Specific Scenarios

**Test timeout:**
```bash
# Agent executor has 55s timeout
# Monitor in logs to see if timeout handling works
```

**Test MCP server:**
```bash
# Check logs for MCP server startup
# Should see: "✅ Firestore client initialized" or "💾 Storage: In-memory only"
```

**Test Spotify auth:**
```bash
# Emulator uses your local .cache-spotify file
# Make sure you've authenticated locally first:
python mcp_server/spotify_server.py
```

### Common Issues

**"Function not found"**
- Check project ID in URL matches `.firebaserc`
- Ensure functions are deployed: `firebase emulators:start`

**"Module not found"**
- Dependencies must be in `functions/requirements.txt`
- Emulator installs them automatically

**"Cannot connect to Firestore"**
- Start emulator with: `firebase emulators:start`
- Check port 8080 is not in use

**"Spotify authentication failed"**
- Run `python mcp_server/spotify_server.py` first
- Creates `.cache-spotify` file

## Automated Testing Script

Create a test script:

```bash
#!/bin/bash
# test-local.sh

echo "🧪 Testing Firebase Functions locally..."

# Start emulators in background
firebase emulators:start &
EMULATOR_PID=$!

# Wait for emulators to start
sleep 5

# Get project ID from .firebaserc
PROJECT_ID=$(grep -o '"default": "[^"]*"' .firebaserc | cut -d'"' -f4)
BASE_URL="http://localhost:5001/$PROJECT_ID/us-central1/spotify_sync"

echo "Testing health endpoint..."
curl -s "$BASE_URL/health" | jq .

echo -e "\nTesting sync endpoint..."
curl -s -X POST "$BASE_URL/api/v1/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "track_name": "Bohemian Rhapsody",
    "artist": "Queen",
    "playlist_id": "37i9dQZF1DXcBWIGoYBM5M"
  }' | jq .

# Stop emulators
kill $EMULATOR_PID

echo -e "\n✅ Testing complete!"
```

Make it executable:
```bash
chmod +x test-local.sh
./test-local.sh
```

## Integration with iOS Shortcuts

**While emulators are running**, update your iOS Shortcut URL:

```
# Local emulator (for testing)
http://YOUR_COMPUTER_IP:5001/YOUR_PROJECT/us-central1/spotify_sync/api/v1/sync

# Production (after deployment)
https://us-central1-YOUR_PROJECT.cloudfunctions.net/spotify_sync/api/v1/sync
```

**Note:** iOS device must be on same WiFi network as your computer.

## Best Practices

1. **Always test locally first** before deploying
2. **Test both modes**: USE_FIRESTORE=true and false
3. **Check emulator logs** for errors
4. **Use Firestore UI** to inspect data
5. **Test error cases** (invalid input, timeouts, etc.)
6. **Monitor function execution time** (should be <55s)

## CI/CD Integration

Add to GitHub Actions workflow:

```yaml
name: Test Firebase Functions

on: [push]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install Firebase CLI
        run: npm install -g firebase-tools

      - name: Install dependencies
        run: |
          cd functions
          pip install -r requirements.txt

      - name: Start emulators and test
        run: |
          firebase emulators:exec "python -m pytest tests/"
```

## Next Steps

After local testing succeeds:
1. Deploy to production: `firebase deploy --only functions`
2. Monitor in Firebase Console: https://console.firebase.google.com/
3. Update iOS Shortcut with production URL

## Resources

- [Firebase Emulator Suite](https://firebase.google.com/docs/emulator-suite)
- [Cloud Functions Emulator](https://firebase.google.com/docs/functions/local-emulator)
- [Firestore Emulator](https://firebase.google.com/docs/emulator-suite/connect_firestore)
