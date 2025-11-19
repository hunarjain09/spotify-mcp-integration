# Firebase Functions Deployment Guide

Complete guide to deploying the Spotify MCP Integration to Firebase Functions.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Firebase Project Setup](#firebase-project-setup)
3. [Configuration Files](#configuration-files)
4. [Environment Variables](#environment-variables)
5. [Dependencies Installation](#dependencies-installation)
6. [Deployment Steps](#deployment-steps)
7. [Post-Deployment Verification](#post-deployment-verification)
8. [Updating the Deployment](#updating-the-deployment)
9. [Monitoring and Logs](#monitoring-and-logs)
10. [Cost Estimation](#cost-estimation)
11. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Accounts

1. **Google Account**
   - Needed for Firebase Console access
   - Sign up at https://accounts.google.com

2. **Firebase Project**
   - Will be created in this guide
   - Access Firebase Console at https://console.firebase.google.com

3. **Spotify Developer Account**
   - Required for Spotify API credentials
   - Sign up at https://developer.spotify.com

4. **Anthropic API Key**
   - Required for Claude Agent SDK
   - Get API key from https://console.anthropic.com

### Required Software

1. **Node.js** (v18 or later)
   ```bash
   # Check version
   node --version
   # Should show: v18.x.x or v20.x.x

   # Install if needed (macOS)
   brew install node

   # Install if needed (Linux)
   curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
   sudo apt-get install -y nodejs
   ```

2. **Python 3.11**
   ```bash
   # Check version
   python3.11 --version
   # Should show: Python 3.11.x

   # Install if needed (macOS)
   brew install python@3.11

   # Install if needed (Linux)
   sudo apt-get install python3.11 python3.11-venv
   ```

3. **uv** (Python package installer)
   ```bash
   # Install uv
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Verify installation
   uv --version
   ```

4. **Firebase CLI**
   ```bash
   # Install locally (recommended)
   npm install --save-dev firebase-tools

   # Or install globally
   npm install -g firebase-tools

   # Verify installation
   npx firebase --version
   # Should show: 13.x.x or later
   ```

5. **Git** (for version control)
   ```bash
   git --version
   ```

### System Requirements

- **Operating System:** macOS, Linux, or Windows (WSL2)
- **RAM:** Minimum 4GB (8GB recommended)
- **Disk Space:** At least 2GB free
- **Internet:** Stable connection required for deployment

---

## Firebase Project Setup

### Step 1: Create Firebase Project

1. **Go to Firebase Console**
   - Visit https://console.firebase.google.com
   - Sign in with your Google account

2. **Create New Project**
   ```
   Click "Add project"
   ↓
   Enter project name: "spotify-mcp-integration" (or your choice)
   ↓
   Click "Continue"
   ↓
   Disable Google Analytics (optional)
   ↓
   Click "Create project"
   ↓
   Wait for project creation (~30 seconds)
   ↓
   Click "Continue"
   ```

3. **Note Your Project ID**
   - Look at the URL: `console.firebase.google.com/project/YOUR-PROJECT-ID`
   - Save this ID (e.g., `spotify-mcp-integration-abc123`)
   - You'll need it for deployment

### Step 2: Upgrade to Blaze Plan

**Why?** Firebase Functions require the Blaze (pay-as-you-go) plan.

1. **Navigate to Billing**
   ```
   Firebase Console → Click gear icon (⚙️) → Project settings
   ↓
   Click "Usage and billing" tab
   ↓
   Click "Modify plan"
   ↓
   Select "Blaze (Pay as you go)"
   ↓
   Click "Purchase"
   ```

2. **Set Budget Alert (Recommended)**
   ```
   In billing page:
   ↓
   Click "Set budget alert"
   ↓
   Set amount: $10/month (or your preference)
   ↓
   Add your email for alerts
   ↓
   Click "Save"
   ```

   **Note:** With typical usage, costs are usually < $1/month (see [Cost Estimation](#cost-estimation))

### Step 3: Enable Required APIs

Firebase Functions automatically enables most APIs, but verify:

1. **Cloud Functions API**
   - Should be auto-enabled
   - Verify at: https://console.cloud.google.com/apis/library/cloudfunctions.googleapis.com

2. **Cloud Build API**
   - Should be auto-enabled
   - Verify at: https://console.cloud.google.com/apis/library/cloudbuild.googleapis.com

3. **Firestore API** (Optional - if USE_FIRESTORE=true)
   - Enable at: https://console.cloud.google.com/apis/library/firestore.googleapis.com

---

## Configuration Files

### 1. Update `.firebaserc`

This file tells Firebase CLI which project to deploy to.

```bash
# Location: /Users/hunarjain09/Desktop/spotify-mcp-integration/.firebaserc
```

**Update the project ID:**

```json
{
  "projects": {
    "default": "YOUR-ACTUAL-PROJECT-ID"
  }
}
```

**Example:**
```json
{
  "projects": {
    "default": "spotify-mcp-integration-abc123"
  }
}
```

**How to find your project ID:**
- Firebase Console → Project Settings → Project ID
- Or from the console URL

### 2. Review `firebase.json`

This file configures Firebase Functions settings. **Already configured** - no changes needed unless you want to customize.

```json
{
  "functions": [
    {
      "source": "functions",
      "codebase": "spotify-sync",
      "runtime": "python311",
      "ignore": [
        "venv",
        ".git",
        ".gitignore",
        "__pycache__"
      ]
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

**Key Settings Explained:**
- `source: "functions"` → Deploy code from `functions/` directory
- `runtime: "python311"` → Use Python 3.11
- `codebase: "spotify-sync"` → Name for this codebase
- `emulators` → Configuration for local testing (not used in production)

### 3. Review `functions/main.py`

**Already configured** - this is your Firebase Functions entry point.

**Key Configuration:**
```python
@https_fn.on_request(
    cors=options.CorsOptions(
        cors_origins="*",        # Allow all origins (adjust for production)
        cors_methods=["get", "post", "options"],
    ),
    timeout_sec=60,              # Maximum execution time
    memory=options.MemoryOption.GB_1,  # 1GB RAM
    cpu=1,                       # 1 CPU
)
def spotify_sync(req: https_fn.Request) -> https_fn.Response:
    # Your function code
    pass
```

**Production Adjustments (Optional):**

1. **Restrict CORS** (for security):
   ```python
   cors=options.CorsOptions(
       cors_origins=["https://yourdomain.com"],
       cors_methods=["post"],
   ),
   ```

2. **Adjust Resources** (for cost):
   ```python
   memory=options.MemoryOption.MB_512,  # Reduce to 512MB if working
   cpu=1,  # Keep at 1 CPU
   ```

---

## Environment Variables

### Option 1: Using `.env` File (Simple, Less Secure)

1. **Create `functions/.env`**
   ```bash
   cd functions
   cp .env.example .env
   ```

2. **Edit `functions/.env`**
   ```bash
   # Spotify API Credentials
   SPOTIFY_CLIENT_ID=your_spotify_client_id_here
   SPOTIFY_CLIENT_SECRET=your_spotify_client_secret_here
   SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback

   # Spotify OAuth Refresh Token (CRITICAL for Firebase Functions)
   # This allows automatic authentication without manual OAuth flow
   # See "Getting Spotify Refresh Token" section below for instructions
   SPOTIFY_REFRESH_TOKEN=your_refresh_token_here

   # Default playlist for syncing
   DEFAULT_PLAYLIST_ID=your_22_character_playlist_id

   # AI Provider Selection
   AI_PROVIDER=claude

   # Anthropic API Key
   ANTHROPIC_API_KEY=sk-ant-api03-your-key-here

   # Execution Mode
   USE_TEMPORAL=false

   # API Server Configuration
   API_HOST=0.0.0.0
   API_PORT=8000

   # Matching Configuration
   FUZZY_MATCH_THRESHOLD=0.85
   USE_AI_DISAMBIGUATION=true

   # AI Model Configuration
   CLAUDE_MODEL=claude-3-5-sonnet-20241022

   # Logging
   LOG_LEVEL=INFO

   # Firestore Configuration (false for zero storage costs)
   USE_FIRESTORE=false
   ```

3. **Get Your Credentials**

   **Spotify:**
   ```
   1. Go to https://developer.spotify.com/dashboard
   2. Log in with Spotify account
   3. Click "Create app"
   4. Fill in:
      - App name: "Spotify MCP Integration"
      - App description: "Sync songs with Claude AI"
      - Redirect URI: http://127.0.0.1:8888/callback
   5. Click "Create"
   6. Click "Settings"
   7. Copy "Client ID" → SPOTIFY_CLIENT_ID
   8. Click "View client secret" → SPOTIFY_CLIENT_SECRET
   ```

   **Anthropic:**
   ```
   1. Go to https://console.anthropic.com
   2. Sign in or create account
   3. Go to "API Keys"
   4. Click "Create Key"
   5. Copy the key → ANTHROPIC_API_KEY
   ```

   **Playlist ID:**
   ```
   1. Open Spotify
   2. Right-click your playlist → Share → Copy link
   3. Link looks like: https://open.spotify.com/playlist/43X1N9GAKwVARreGxSAdZI
   4. Take the last part: 43X1N9GAKwVARreGxSAdZI
   5. That's your DEFAULT_PLAYLIST_ID
   ```

   **Spotify Refresh Token (CRITICAL for Firebase Functions):**

   Firebase Functions have ephemeral filesystems, so the normal `.cache-spotify` file won't persist.
   You need to extract the refresh token and provide it via environment variable.

   ```bash
   # Step 1: Run local authentication (if you haven't already)
   cd /path/to/spotify-mcp-integration
   source venv/bin/activate
   python mcp_server/spotify_server.py

   # This will open a browser for OAuth authentication
   # After successful authentication, a .cache-spotify file is created

   # Step 2: Extract refresh token from cache file
   cat .cache-spotify | python -m json.tool | grep refresh_token

   # Example output:
   # "refresh_token": "AQAaeB8LyL9at8noI6-cAtbS3S9Ui6138OJhO..."

   # Step 3: Copy the refresh_token value (without quotes)
   # Step 4: Add to functions/.env as SPOTIFY_REFRESH_TOKEN
   ```

   **How it works:**
   - The refresh token is long-lived and doesn't expire (unless revoked)
   - On first request, the custom cache handler uses this token to get a fresh access token
   - Access tokens are cached in-memory for the function's lifetime (~5-15 minutes)
   - When the function goes cold, the next invocation re-authenticates using the refresh token

   **If you lose the refresh token:**
   - Delete `.cache-spotify` in your local repo
   - Run `python mcp_server/spotify_server.py` to re-authenticate
   - Extract the new refresh_token from `.cache-spotify`
   - Update your environment variables

**⚠️ Important:** The `.env` file is deployed with your function. For better security, use Secret Manager (Option 2).

### Option 2: Using Firebase Secret Manager (More Secure, Recommended for Production)

1. **Set secrets via Firebase CLI**
   ```bash
   # Spotify credentials
   npx firebase functions:secrets:set SPOTIFY_CLIENT_ID
   # Paste your client ID when prompted, then Enter

   npx firebase functions:secrets:set SPOTIFY_CLIENT_SECRET
   # Paste your client secret when prompted, then Enter

   # Spotify refresh token (CRITICAL - see above for how to extract)
   npx firebase functions:secrets:set SPOTIFY_REFRESH_TOKEN
   # Paste your refresh token when prompted, then Enter

   # Anthropic API key
   npx firebase functions:secrets:set ANTHROPIC_API_KEY
   # Paste your API key when prompted, then Enter
   ```

2. **Update `functions/main.py` to use secrets**
   ```python
   # Add to imports
   from firebase_functions.params import SecretParam

   # Define secrets
   spotify_client_id = SecretParam("SPOTIFY_CLIENT_ID")
   spotify_client_secret = SecretParam("SPOTIFY_CLIENT_SECRET")
   spotify_refresh_token = SecretParam("SPOTIFY_REFRESH_TOKEN")
   anthropic_api_key = SecretParam("ANTHROPIC_API_KEY")

   # Update function decorator
   @https_fn.on_request(
       secrets=[
           spotify_client_id,
           spotify_client_secret,
           spotify_refresh_token,
           anthropic_api_key
       ],
       # ... other options
   )
   def spotify_sync(req):
       # Access secrets via environment variables
       # They're automatically injected
       pass
   ```

**Advantages:**
- ✅ Secrets encrypted at rest
- ✅ Not in source code
- ✅ Fine-grained access control
- ✅ Audit logging

**Disadvantages:**
- ❌ More setup steps
- ❌ Costs ~$0.06/month per secret

---

## Dependencies Installation

### 1. Install Node.js Dependencies

```bash
# In project root
npm install

# This installs:
# - firebase-tools (Firebase CLI)
```

### 2. Install Python Dependencies (for local testing)

```bash
# Navigate to functions directory
cd functions

# Create virtual environment
python3.11 -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate  # Windows

# Install dependencies with uv (faster)
uv pip install -r requirements.txt

# Or install with pip (slower)
pip install -r requirements.txt
```

**Verify installation:**
```bash
python -c "import firebase_functions; print('✅ Firebase Functions installed')"
python -c "import fastapi; print('✅ FastAPI installed')"
python -c "import anthropic; print('✅ Anthropic SDK installed')"
```

---

## Deployment Steps

### Step 1: Authenticate with Firebase

```bash
# Login to Firebase
npx firebase login

# Follow the browser prompts:
# 1. Select your Google account
# 2. Grant permissions
# 3. Return to terminal
```

**Verify authentication:**
```bash
npx firebase projects:list

# You should see your project:
# ┌────────────────────────────────────┬─────────────────────────────┐
# │ Project Display Name               │ Project ID                  │
# ├────────────────────────────────────┼─────────────────────────────┤
# │ spotify-mcp-integration            │ spotify-mcp-integration-123 │
# └────────────────────────────────────┴─────────────────────────────┘
```

### Step 2: Set Active Project

```bash
# Set the project to deploy to
npx firebase use YOUR-PROJECT-ID

# Example:
npx firebase use spotify-mcp-integration-abc123

# Verify:
npx firebase use
# Should show: Active project: spotify-mcp-integration-abc123 (YOUR-PROJECT-NAME)
```

### Step 3: Review What Will Be Deployed

```bash
# Check deployment configuration
npx firebase deploy --only functions --dry-run

# This shows:
# ✓ What will be deployed
# ✓ Which functions will be created/updated
# ✓ Configuration details
```

### Step 4: Deploy to Firebase

```bash
# Deploy functions
npx firebase deploy --only functions

# You'll see output like:
```

**Expected Output:**
```
=== Deploying to 'spotify-mcp-integration-abc123'...

i  deploying functions
i  functions: ensuring required API cloudfunctions.googleapis.com is enabled...
i  functions: ensuring required API cloudbuild.googleapis.com is enabled...
✔  functions: required API cloudfunctions.googleapis.com is enabled
✔  functions: required API cloudbuild.googleapis.com is enabled
i  functions: preparing codebase spotify-sync for deployment
i  functions: preparing functions directory for uploading...
i  functions: packaged /path/to/functions (52 MB) for uploading
✔  functions: functions folder uploaded successfully

i  functions: creating Python 3.11 (2nd gen) function spotify_sync(us-central1)...
✔  functions[spotify_sync(us-central1)] Successful create operation.
Function URL (spotify_sync(us-central1)): https://us-central1-spotify-mcp-integration-abc123.cloudfunctions.net/spotify_sync

✔  Deploy complete!

Project Console: https://console.firebase.google.com/project/spotify-mcp-integration-abc123/overview
```

**Deployment takes:** 2-5 minutes for first deployment, 1-2 minutes for updates.

### Step 5: Save Your Function URL

**Your function URL format:**
```
https://REGION-PROJECT-ID.cloudfunctions.net/FUNCTION-NAME
```

**Example:**
```
https://us-central1-spotify-mcp-integration-abc123.cloudfunctions.net/spotify_sync
```

**Save this URL** - you'll use it in your iOS Shortcut or API calls.

---

## Post-Deployment Verification

### Test 1: Health Check

```bash
# Test health endpoint
curl https://REGION-PROJECT-ID.cloudfunctions.net/spotify_sync/health

# Expected response:
{
  "status": "healthy",
  "service": "spotify-sync-firebase"
}
```

**If successful:** ✅ Function is deployed and running!

### Test 2: Sync Endpoint

```bash
# Test sync with sample data
curl -X POST https://REGION-PROJECT-ID.cloudfunctions.net/spotify_sync/api/v1/sync \
  -H "Content-Type: application/json" \
  -d '{
    "track_name": "Bohemian Rhapsody",
    "artist": "Queen",
    "album": "A Night at the Opera",
    "playlist_id": "YOUR_PLAYLIST_ID_HERE"
  }'

# Expected response (~10ms):
{
  "workflow_id": "agent-sync-anonymous-1763447923-99545",
  "status": "accepted",
  "message": "Agent is searching for 'Bohemian Rhapsody' by Queen...",
  "status_url": null
}
```

**If successful:** ✅ Full sync workflow is working!

### Test 3: Check Logs

```bash
# View function logs
npx firebase functions:log

# Or view in Firebase Console:
# https://console.firebase.google.com/project/YOUR-PROJECT/functions/logs
```

**Look for:**
```
INFO: Starting agent-based sync for: Bohemian Rhapsody by Queen
INFO: Background thread started for agent processing
INFO: Agent response: I'll search for the track...
INFO: ✅ Success! Matched: Bohemian Rhapsody - Remaster
```

### Test 4: Verify in Spotify

1. Open your Spotify playlist
2. Check if "Bohemian Rhapsody" was added
3. If yes: ✅ Complete end-to-end workflow working!

---

## Updating the Deployment

### Update Code

```bash
# 1. Make changes to your code
# 2. Test locally with emulator (optional but recommended)
npx firebase emulators:start

# 3. Deploy updates
npx firebase deploy --only functions

# The same function will be updated in-place
```

### Update Environment Variables

**If using `.env` file:**
```bash
# 1. Edit functions/.env
nano functions/.env

# 2. Redeploy
npx firebase deploy --only functions
```

**If using Secret Manager:**
```bash
# 1. Update secret
npx firebase functions:secrets:set ANTHROPIC_API_KEY

# 2. Redeploy
npx firebase deploy --only functions
```

### Rollback to Previous Version

```bash
# List recent deployments
npx firebase functions:list

# Rollback is not directly supported
# Instead, deploy previous code:
git checkout <previous-commit>
npx firebase deploy --only functions
git checkout main
```

---

## Monitoring and Logs

### View Logs in Real-Time

```bash
# Stream logs
npx firebase functions:log --only spotify_sync

# Stream with filtering
npx firebase functions:log --only spotify_sync | grep "ERROR"
```

### Firebase Console Logs

1. Go to Firebase Console
2. Navigate to: Functions → Logs
3. Filter by function name: `spotify_sync`
4. View execution history, errors, performance

**Useful filters:**
- Severity: Error
- Time range: Last 1 hour
- Text search: "workflow_id"

### Monitor Performance

1. **Firebase Console → Functions → Dashboard**
   - Invocations per minute
   - Execution time (should be ~10ms for HTTP response)
   - Memory usage (should be < 200MB)
   - Error rate (should be < 1%)

2. **Cloud Monitoring** (more detailed)
   - https://console.cloud.google.com/monitoring
   - Create alerts for errors, high latency, etc.

### Set Up Alerts

```bash
# In Firebase Console:
# Functions → Click your function → Metrics → Create Alert

# Recommended alerts:
# 1. Error rate > 5% in last 5 minutes
# 2. Execution time > 30s (p95)
# 3. Invocation count > 1000/hour (if unexpected)
```

---

## Cost Estimation

### Firebase Functions Pricing (Blaze Plan)

**Compute Time:**
- First 2 million invocations/month: FREE
- First 400,000 GB-seconds: FREE
- After that: $0.40 per million invocations

**Our Usage:**
- Memory: 1GB
- Execution time: ~25s (average for background thread)
- Per request cost: 1GB × 25s = 25 GB-seconds

**Example Costs:**

| Monthly Requests | Compute Cost | Total Cost |
|-----------------|--------------|------------|
| 100 | $0.00 | **$0.00** |
| 1,000 | $0.00 | **$0.00** |
| 10,000 | $0.00 | **$0.00** |
| 100,000 | $0.00 | **$0.00** |
| 1,000,000 | ~$2.00 | **~$2.00** |

**Free tier covers:** 400,000 GB-seconds = 16,000 requests/month @ 25s each

### Firestore Costs (if USE_FIRESTORE=true)

**Storage:**
- First 1 GB: FREE
- After: $0.18/GB/month

**Reads/Writes:**
- First 50,000 reads/day: FREE
- First 20,000 writes/day: FREE
- After: $0.06 per 100,000 reads, $0.18 per 100,000 writes

**Our Usage (if enabled):**
- 1 write per sync request
- Storage: ~1KB per result

**Example Costs:**

| Monthly Requests | Storage | Writes | Total |
|-----------------|---------|--------|-------|
| 1,000 | < 1 MB | $0.00 | **$0.00** |
| 10,000 | < 10 MB | $0.00 | **$0.00** |
| 100,000 | < 100 MB | $0.01 | **$0.01** |

### Secret Manager Costs

- $0.06 per secret/month
- 3 secrets = $0.18/month

### Total Estimated Costs

**Typical usage (1,000 requests/month):**
```
Firebase Functions: $0.00 (within free tier)
Firestore: $0.00 (if disabled) or $0.00 (within free tier if enabled)
Secret Manager: $0.18 (if used) or $0.00 (if using .env)
───────────────────────
Total: $0.00 - $0.18/month
```

**Heavy usage (100,000 requests/month):**
```
Firebase Functions: $0.00 (within free tier)
Firestore: $0.01 (if enabled)
Secret Manager: $0.18 (if used)
───────────────────────
Total: $0.01 - $0.19/month
```

**Note:** These are estimates. Actual costs depend on:
- Request frequency
- Execution time
- Memory usage
- Firestore usage
- Network egress

---

## Troubleshooting

### Issue 1: "Project not found"

**Error:**
```
Error: HTTP Error: 404, Project 'your-project-id' not found
```

**Solution:**
1. Verify project ID in `.firebaserc` matches Firebase Console
2. Ensure you're logged in: `npx firebase login`
3. Verify project access: `npx firebase projects:list`

### Issue 2: "Missing required API"

**Error:**
```
Error: Missing required API cloudfunctions.googleapis.com
```

**Solution:**
```bash
# Enable API manually
gcloud services enable cloudfunctions.googleapis.com --project=YOUR-PROJECT-ID
gcloud services enable cloudbuild.googleapis.com --project=YOUR-PROJECT-ID
```

### Issue 3: "Deployment failed: PERMISSION_DENIED"

**Error:**
```
Error: User does not have permission to access project
```

**Solution:**
1. Ensure you're logged in with correct account
2. Verify you have "Editor" or "Owner" role in Firebase project
3. Check in Firebase Console → Settings → Users and permissions

### Issue 4: "Function timeout"

**Error in logs:**
```
Function execution took 60001 ms, finished with status: timeout
```

**Solution:**
Already handled with 55s timeout, but if still occurring:
1. Check if Spotify API is slow
2. Verify Agent SDK is completing
3. Consider reducing complexity of agent task

### Issue 5: "Environment variables not loaded"

**Symptom:** Function runs but can't access Spotify/Anthropic

**Solution:**
1. Verify `functions/.env` exists
2. Check environment variables are set correctly
3. Redeploy: `npx firebase deploy --only functions`

**Debug:**
```bash
# Add logging to functions/main.py
import os
logger.info(f"SPOTIFY_CLIENT_ID: {os.getenv('SPOTIFY_CLIENT_ID')[:10]}...")
```

### Issue 6: "ModuleNotFoundError"

**Error:**
```
ModuleNotFoundError: No module named 'anthropic'
```

**Solution:**
1. Verify `functions/requirements.txt` includes all dependencies
2. Check Python version is 3.11
3. Redeploy with `--force`:
   ```bash
   npx firebase deploy --only functions --force
   ```

### Issue 7: "Cold start slow"

**Symptom:** First request takes 5-10 seconds

**This is normal!** Firebase Functions have cold starts.

**Mitigation:**
- Use Cloud Scheduler to ping function every 5 minutes (keeps warm)
- Accept cold starts (they decrease with usage)
- Not worth optimizing for most use cases

### Issue 8: "High costs"

**Check:**
1. View billing in Firebase Console
2. Check for excessive invocations
3. Review logs for errors causing retries
4. Verify no infinite loops

**Reduce costs:**
1. Set `USE_FIRESTORE=false` (saves Firestore costs)
2. Reduce memory to 512MB if working
3. Add authentication to prevent abuse
4. Set up budget alerts

---

## Next Steps After Deployment

### 1. Update iOS Shortcut

Replace the webhook URL in your iOS Shortcut with your Firebase Function URL:

```
OLD: http://127.0.0.1:8000/api/v1/sync
NEW: https://us-central1-YOUR-PROJECT.cloudfunctions.net/spotify_sync/api/v1/sync
```

### 2. Set Up Monitoring

- Enable Firebase Performance Monitoring
- Set up error alerts
- Configure budget alerts

### 3. Secure Your Function (Optional but Recommended)

**Add authentication:**
```python
# In functions/main.py
def spotify_sync(req):
    # Check for API key
    api_key = req.headers.get('X-API-Key')
    if api_key != os.getenv('EXPECTED_API_KEY'):
        return https_fn.Response(
            response='{"error": "Unauthorized"}',
            status=401
        )
    # ... rest of function
```

### 4. Configure CORS for Production

```python
# In functions/main.py
cors=options.CorsOptions(
    cors_origins=["https://yourdomain.com"],  # Your domain only
    cors_methods=["post"],  # Only POST
),
```

### 5. Set Up Custom Domain (Optional)

1. Purchase domain (e.g., api.yourdomain.com)
2. Configure in Firebase Hosting
3. Link to Cloud Functions
4. Your URL becomes: https://api.yourdomain.com/sync

---

## Quick Reference

### Essential Commands

```bash
# Deploy
npx firebase deploy --only functions

# View logs
npx firebase functions:log

# List functions
npx firebase functions:list

# Delete function
npx firebase functions:delete spotify_sync

# Open Firebase Console
npx firebase open functions

# Test locally
npx firebase emulators:start
```

### Important URLs

```
Firebase Console:
https://console.firebase.google.com/project/YOUR-PROJECT-ID

Function URL:
https://REGION-PROJECT-ID.cloudfunctions.net/spotify_sync

Logs:
https://console.firebase.google.com/project/YOUR-PROJECT-ID/functions/logs

Billing:
https://console.firebase.google.com/project/YOUR-PROJECT-ID/usage
```

### Configuration Checklist

- [ ] `.firebaserc` updated with your project ID
- [ ] `functions/.env` created with credentials
- [ ] Spotify API credentials obtained
- [ ] Anthropic API key obtained
- [ ] Playlist ID configured
- [ ] Firebase project on Blaze plan
- [ ] Required APIs enabled
- [ ] Firebase CLI installed
- [ ] Python 3.11 installed

---

## Support and Resources

**Official Documentation:**
- Firebase Functions: https://firebase.google.com/docs/functions
- Pricing: https://firebase.google.com/pricing
- Quotas: https://firebase.google.com/docs/functions/quotas

**This Project:**
- Architecture Guide: `docs/FIREBASE_ARCHITECTURE.md`
- Local Testing: `docs/FIREBASE_LOCAL_TESTING.md`
- GitHub Issues: [Your repo issues page]

**Community:**
- Firebase Discord: https://discord.gg/firebase
- Stack Overflow: Tag `firebase-functions` + `python`

---

**Last Updated:** November 2025
**Firebase Functions Version:** 2nd Gen
**Python Version:** 3.11
**Firebase Tools Version:** 13.x
