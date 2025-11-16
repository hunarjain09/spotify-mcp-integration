# 🧪 Free Local Testing Guide

**Complete guide to testing the Spotify MCP Integration locally without any costs.**

This guide will help you set up and test the entire system on your local machine for **$0/month**. Perfect for development, testing, and learning before deploying to production.

---

## 📋 Table of Contents

- [What You'll Get](#what-youll-get)
- [Prerequisites](#prerequisites)
- [Step-by-Step Setup](#step-by-step-setup)
- [Testing the System](#testing-the-system)
- [Cost Optimization Tips](#cost-optimization-tips)
- [Troubleshooting](#troubleshooting)
- [What's Next](#whats-next)

---

## 🎯 What You'll Get

Running locally gives you access to:

- ✅ **FastAPI Server** - Full REST API (localhost:8000)
- ✅ **Temporal Workflows** - Orchestration engine with Web UI
- ✅ **PostgreSQL Database** - Persistent storage
- ✅ **MCP Spotify Server** - Spotify API integration
- ✅ **Monitoring Stack** - Prometheus + Grafana dashboards
- ✅ **AI Disambiguation** - Smart track matching
- ✅ **iOS Shortcuts Integration** - Test on your iPhone (same WiFi)

**Total Cost: $0/month** 💰

---

## 📦 Prerequisites (All Free!)

### Required Software

1. **Python 3.11+**
   ```bash
   python3 --version  # Should be 3.11 or higher
   ```
   Download: https://www.python.org/downloads/

2. **Docker Desktop**
   - Download: https://www.docker.com/products/docker-desktop/
   - **Cost:** FREE for personal use
   - Required for: Temporal, PostgreSQL, monitoring

3. **Git** (if not already installed)
   ```bash
   git --version
   ```

### Free API Accounts

You'll need **3 free accounts**:

#### 1. Spotify Developer Account (FREE)

1. Go to: https://developer.spotify.com/dashboard
2. Log in with your Spotify account (free tier is fine)
3. Click **"Create an App"**
4. Fill in:
   - **App Name:** "Music Sync Test"
   - **App Description:** "Testing local sync"
   - **Website:** http://localhost
   - **Redirect URI:** `http://localhost:8888/callback`
5. Click **"Create"**
6. Copy your **Client ID** and **Client Secret**

**Cost: FREE Forever** ✅
**Limits:** 25,000 API calls/day (more than enough for testing)

#### 2. AI Provider Account (Pick One)

**Option A: Anthropic Claude (Recommended)**

1. Go to: https://console.anthropic.com
2. Sign up with email
3. **New users get $5 free credit** 🎁
4. Go to: Settings → API Keys
5. Click "Create Key"
6. Copy your API key

**Free Credit: $5** - Good for ~1,000-2,000 track disambiguations
**Claude Model:** claude-3-5-sonnet-20241022

**Option B: OpenAI**

1. Go to: https://platform.openai.com
2. Sign up with email
3. **New users get $5 free credit** 🎁
4. Go to: API Keys
5. Click "Create new secret key"
6. Copy your API key

**Free Credit: $5** - Good for ~1,000-2,000 track disambiguations
**Models:** GPT-4 or GPT-3.5-turbo

> **Tip:** Anthropic's Claude is recommended for better music matching decisions.

#### 3. Spotify Playlist (FREE)

1. Open Spotify (web or app)
2. Create a new playlist: **"Sync Test"**
3. Right-click playlist → Share → Copy link
4. Extract ID from URL:
   ```
   https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M
                                   ^^^^^^^^^^^^^^^^^^^^^^^^
                                   This is your playlist ID
   ```

---

## 🚀 Step-by-Step Setup

### Step 1: Configure Environment

```bash
# Navigate to project directory
cd spotify-mcp-integration

# Copy environment template
cp .env.example .env

# Edit with your favorite editor
nano .env  # or: vim .env, code .env, etc.
```

**Minimal .env configuration for free testing:**

```env
# ===== SPOTIFY CREDENTIALS =====
# From: https://developer.spotify.com/dashboard
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback

# Your test playlist ID (from Spotify)
DEFAULT_PLAYLIST_ID=your_playlist_id_here

# ===== AI PROVIDER (Choose ONE) =====
# Recommended: "claude" for better matching
AI_PROVIDER=claude

# If using AI_PROVIDER=claude (Recommended)
ANTHROPIC_API_KEY=your_anthropic_key_here

# If using AI_PROVIDER=langchain (Alternative)
# OPENAI_API_KEY=your_openai_key_here

# ===== TEMPORAL (Local - FREE) =====
TEMPORAL_HOST=localhost:7233
TEMPORAL_NAMESPACE=default

# ===== MATCHING CONFIGURATION =====
# Higher threshold = less AI usage = save free credits
FUZZY_MATCH_THRESHOLD=0.90
USE_AI_DISAMBIGUATION=true

# ===== AI MODEL SELECTION =====
# For Claude provider
CLAUDE_MODEL=claude-3-5-sonnet-20241022

# For Langchain provider (if using OpenAI)
# AI_MODEL=gpt-3.5-turbo  # Cheaper option
# AI_MODEL=gpt-4          # Better quality

# ===== WORKER CONFIGURATION =====
MAX_CONCURRENT_ACTIVITIES=100
MAX_CONCURRENT_WORKFLOWS=50
MAX_ACTIVITIES_PER_SECOND=10.0

# ===== LOGGING =====
LOG_LEVEL=INFO
```

**Save and exit** (Ctrl+X, then Y in nano)

### Step 2: Install Dependencies

**Option A: Using UV (Recommended - Faster)**

```bash
# Install UV if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate
```

**Option B: Using pip (Alternative)**

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**Verify installation:**
```bash
python -c "import fastapi, temporalio, spotipy; print('✓ All dependencies installed')"
```

### Step 3: Start Local Infrastructure

```bash
# Make sure Docker Desktop is running first!

# Start all services
docker-compose up -d

# Wait for services to initialize
echo "Waiting for services to start..."
sleep 10

# Verify all services are running
docker-compose ps
```

**Expected output:**
```
NAME                     STATUS
temporal                 Up (healthy)
postgresql               Up (healthy)
temporal-ui              Up
prometheus               Up
grafana                  Up
```

**Services now available:**
- 🔧 Temporal Server: localhost:7233
- 🌐 Temporal Web UI: http://localhost:8080
- 📊 Prometheus: http://localhost:9090
- 📈 Grafana: http://localhost:3000
- 🗄️ PostgreSQL: localhost:5432

### Step 4: Authenticate with Spotify (One-time)

```bash
# Run the MCP server to trigger OAuth flow
python mcp_server/spotify_server.py
```

**What happens:**
1. Browser opens automatically
2. Spotify login page appears (if not logged in)
3. Permission consent screen shows
4. Click **"Agree"** to grant access
5. Terminal shows: `Authentication successful!`
6. Token saved to `.cache-spotify` file
7. Press **Ctrl+C** to exit

**You only need to do this once!** The token is cached and auto-refreshed.

### Step 5: Start the Worker

Open a **new terminal window/tab**:

```bash
cd spotify-mcp-integration

# Activate virtual environment
source .venv/bin/activate  # or: source venv/bin/activate

# Start the worker
python workers/music_sync_worker.py
```

**Expected output:**
```
INFO: Connected to Temporal server at localhost:7233
INFO: Starting worker on task queue 'music-sync-queue'
INFO: Worker started successfully
INFO: Polling for tasks...
```

**Keep this terminal running!** ✨

### Step 6: Start the API Server

Open **another new terminal window/tab**:

```bash
cd spotify-mcp-integration

# Activate virtual environment
source .venv/bin/activate  # or: source venv/bin/activate

# Start the API server
python -m uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload
```

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**Keep this terminal running!** ✨

---

## 🧪 Testing the System

### Test 1: Health Check

```bash
curl http://localhost:8000/api/v1/health
```

**Expected:**
```json
{"status": "healthy"}
```

✅ **If you see this, your API is working!**

### Test 2: Access API Documentation

Open browser: **http://localhost:8000/docs**

You'll see interactive Swagger UI with all endpoints:
- `POST /api/v1/sync` - Start sync workflow
- `GET /api/v1/sync/{workflow_id}` - Check status
- `GET /api/v1/health` - Health check

### Test 3: Sync Your First Song

**Using curl:**
```bash
curl -X POST http://localhost:8000/api/v1/sync \
  -H "Content-Type: application/json" \
  -d '{
    "track_name": "Bohemian Rhapsody",
    "artist": "Queen",
    "album": "A Night at the Opera",
    "playlist_id": "YOUR_PLAYLIST_ID"
  }'
```

**Or using the Swagger UI:**
1. Go to http://localhost:8000/docs
2. Click `POST /api/v1/sync`
3. Click **"Try it out"**
4. Fill in:
   ```json
   {
     "track_name": "Bohemian Rhapsody",
     "artist": "Queen",
     "album": "A Night at the Opera",
     "playlist_id": "YOUR_PLAYLIST_ID"
   }
   ```
5. Click **"Execute"**

**Expected response:**
```json
{
  "workflow_id": "sync-anonymous-1731734521-abc123",
  "status": "accepted",
  "message": "Sync started for 'Bohemian Rhapsody' by Queen",
  "status_url": "/api/v1/sync/sync-anonymous-1731734521-abc123"
}
```

### Test 4: Check Sync Status

```bash
# Replace with your actual workflow_id from previous response
curl http://localhost:8000/api/v1/sync/sync-anonymous-1731734521-abc123
```

**While running:**
```json
{
  "workflow_id": "sync-anonymous-1731734521-abc123",
  "status": "running",
  "progress": {
    "current_step": "matching",
    "steps_completed": 2,
    "steps_total": 4,
    "candidates_found": 8,
    "elapsed_seconds": 1.2
  },
  "started_at": "2025-11-16T10:30:00Z"
}
```

**When completed:**
```json
{
  "workflow_id": "sync-anonymous-1731734521-abc123",
  "status": "completed",
  "result": {
    "success": true,
    "message": "Successfully added 'Bohemian Rhapsody' to playlist",
    "spotify_track_id": "7tFiyTwD0nx5a1eklYtX2J",
    "spotify_track_uri": "spotify:track:7tFiyTwD0nx5a1eklYtX2J",
    "confidence_score": 0.98,
    "execution_time_seconds": 2.4,
    "match_method": "fuzzy"
  },
  "started_at": "2025-11-16T10:30:00Z",
  "completed_at": "2025-11-16T10:30:02Z"
}
```

### Test 5: Verify in Spotify

1. Open Spotify (web or app)
2. Navigate to your test playlist
3. **Verify "Bohemian Rhapsody" was added!** 🎉

### Test 6: Monitor Workflows in Temporal UI

1. Open browser: **http://localhost:8080**
2. Click **"Workflows"** in sidebar
3. See your workflow executing in real-time!
4. Click on a workflow to see:
   - Event history
   - Current status
   - Activity executions
   - Retry attempts

### Test 7: Test More Songs

**Songs that match without AI (saves free credits):**

```bash
# Well-known songs with clear matches
curl -X POST http://localhost:8000/api/v1/sync \
  -H "Content-Type: application/json" \
  -d '{
    "track_name": "Billie Jean",
    "artist": "Michael Jackson",
    "playlist_id": "YOUR_PLAYLIST_ID"
  }'
```

**More test songs (no AI needed):**
- "Stairway to Heaven" by Led Zeppelin
- "Smells Like Teen Spirit" by Nirvana
- "Hotel California" by Eagles
- "Imagine" by John Lennon
- "Sweet Child O Mine" by Guns N Roses

**Songs that might trigger AI disambiguation:**
- "Yesterday" by The Beatles *(multiple remasters)*
- "All I Want for Christmas Is You" by Mariah Carey *(remasters)*
- "Wonderwall" by Oasis *(remastered versions)*

### Test 8: iOS Shortcuts (Optional)

If you have an iPhone on the **same WiFi network**:

**Get your local IP:**
```bash
# On macOS/Linux
ifconfig | grep "inet " | grep -v 127.0.0.1

# On Windows
ipconfig | findstr IPv4
```

**Example output:**
```
inet 192.168.1.100 netmask 0xffffff00
     ^^^^^^^^^^^^ This is your local IP
```

**Setup iOS Shortcut:**

Follow the detailed guide in the main README.md under "iOS Shortcuts Setup" section. Use your local IP (e.g., `http://192.168.1.100:8000`) instead of a public URL.

**Test from iPhone:**
1. Play any song in Apple Music
2. Tap Share button
3. Select your "Add to Spotify" shortcut
4. Song syncs instantly! 📱

---

## 💰 Cost Optimization Tips

### Minimize AI API Usage (Stay Free Longer)

**1. Increase Fuzzy Match Threshold**

In `.env`:
```env
# Higher threshold = less AI calls
FUZZY_MATCH_THRESHOLD=0.95  # vs default 0.85
```

**Impact:**
- `0.85`: ~20-30% of songs trigger AI (~$0.02 per 100 songs)
- `0.90`: ~10-15% of songs trigger AI (~$0.01 per 100 songs)
- `0.95`: ~5-10% of songs trigger AI (~$0.005 per 100 songs)

**2. Disable AI for Testing**

```env
USE_AI_DISAMBIGUATION=false
```

Only exact/fuzzy matches will work. Good for testing infrastructure without using AI credits.

**3. Use GPT-3.5 Instead of GPT-4 (if using OpenAI)**

```env
AI_PROVIDER=langchain
AI_MODEL=gpt-3.5-turbo  # 10x cheaper than GPT-4
```

**Cost comparison:**
- GPT-4: ~$0.05 per disambiguation
- GPT-3.5: ~$0.005 per disambiguation
- Claude 3.5 Sonnet: ~$0.03 per disambiguation

### Monitor Your Free API Usage

**Anthropic Dashboard:**
- URL: https://console.anthropic.com/settings/usage
- Shows: Credits used, credits remaining, daily usage

**OpenAI Dashboard:**
- URL: https://platform.openai.com/usage
- Shows: Total usage, API calls, costs

**Check regularly to avoid surprises!**

### Estimated Free Testing Capacity

With **$5 free credit**:

| AI Provider | Disambiguations | Typical Test Songs |
|-------------|-----------------|-------------------|
| Claude 3.5 Sonnet | ~170-200 | 500-1,000 songs |
| GPT-4 | ~100-120 | 300-500 songs |
| GPT-3.5 Turbo | ~1,000-1,500 | 3,000-7,000 songs |

> **Note:** Most songs (70-80%) match via fuzzy logic without AI, so your free credit goes a long way!

---

## 🔧 Troubleshooting

### Issue: "Docker is not running"

**Solution:**
```bash
# Start Docker Desktop application
# On macOS: Open Docker Desktop from Applications
# On Windows: Open Docker Desktop from Start Menu

# Verify Docker is running
docker info
```

### Issue: "Temporal client not connected"

**Check services:**
```bash
docker-compose ps
```

**Restart Temporal:**
```bash
docker-compose restart temporal
sleep 5
docker-compose logs temporal
```

**Verify connectivity:**
```bash
curl http://localhost:7233
```

### Issue: "Insufficient OAuth scopes"

**Re-authenticate:**
```bash
# Delete cached token
rm .cache-spotify

# Re-run authentication
python mcp_server/spotify_server.py
```

Make sure your Spotify app has redirect URI: `http://localhost:8888/callback`

### Issue: "No tracks found on Spotify"

**Possible causes:**
1. Song not available in your region
2. Typo in song name
3. Artist name mismatch

**Test manually:**
1. Go to https://open.spotify.com
2. Search for the song
3. Verify it exists

**Try with ISRC (if available):**
```json
{
  "track_name": "Song Name",
  "artist": "Artist",
  "isrc": "USRC17607839"
}
```

### Issue: Worker not processing workflows

**Check worker is running:**
```bash
# Should see "Worker started successfully"
python workers/music_sync_worker.py
```

**Check task queue name matches:**

In `.env`:
```env
TASK_QUEUE_NAME=music-sync-queue
```

Must match in both worker and API server.

**Check Temporal UI:**
1. Go to http://localhost:8080
2. Click "Task Queues"
3. Verify worker is registered

### Issue: iOS Shortcut fails

**Test server is reachable:**

On iPhone, open Safari and visit:
```
http://YOUR_LOCAL_IP:8000/api/v1/health
```

**Common issues:**
- ❌ Firewall blocking port 8000
- ❌ iPhone on different WiFi network
- ❌ Server not running
- ❌ Wrong IP address

**Solution:**
```bash
# On macOS, allow port 8000
sudo ufw allow 8000

# Or temporarily disable firewall for testing
```

### Issue: "API key invalid" for AI provider

**Anthropic:**
1. Go to https://console.anthropic.com/settings/keys
2. Verify key is active
3. Check you have credits remaining

**OpenAI:**
1. Go to https://platform.openai.com/api-keys
2. Verify key is active
3. Check usage limits

**Test API key:**
```bash
# For Anthropic
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: YOUR_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-3-5-sonnet-20241022","max_tokens":10,"messages":[{"role":"user","content":"Hi"}]}'

# For OpenAI
curl https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-3.5-turbo","messages":[{"role":"user","content":"Hi"}],"max_tokens":10}'
```

### Getting Help

**View logs:**
```bash
# Worker logs
python workers/music_sync_worker.py

# API server logs
python -m uvicorn api.app:app --log-level debug

# Docker logs
docker-compose logs -f temporal
```

**Check Temporal workflows:**
- http://localhost:8080

**API Documentation:**
- http://localhost:8000/docs

---

## 📊 What's Running (All Free!)

| Component | URL | Purpose | Cost |
|-----------|-----|---------|------|
| FastAPI Server | http://localhost:8000 | REST API endpoints | FREE |
| API Documentation | http://localhost:8000/docs | Interactive API docs | FREE |
| Temporal Server | localhost:7233 | Workflow orchestration | FREE |
| Temporal Web UI | http://localhost:8080 | Workflow monitoring | FREE |
| PostgreSQL | localhost:5432 | Workflow state storage | FREE |
| Prometheus | http://localhost:9090 | Metrics collection | FREE |
| Grafana | http://localhost:3000 | Dashboards | FREE |
| Spotify API | - | Music data | FREE |
| AI API (Anthropic/OpenAI) | - | Smart matching | FREE ($5 credit) |

**Total Monthly Cost: $0** 🎉

---

## 🎓 Learning Resources

### Understanding the Architecture

**Read these files to learn how it works:**
- `workflows/music_sync_workflow.py` - Main workflow logic
- `activities/spotify_search.py` - Spotify search integration
- `activities/fuzzy_matcher.py` - Fuzzy matching algorithm
- `activities/ai_disambiguator.py` - AI-powered disambiguation
- `api/app.py` - FastAPI REST endpoints
- `mcp_server/spotify_server.py` - MCP Spotify server

### Key Concepts

**Temporal Workflows:**
- Durable execution (survives crashes)
- Automatic retries with exponential backoff
- Event sourcing for debugging
- Learn more: https://docs.temporal.io

**Model Context Protocol (MCP):**
- Tool-based API abstraction
- Stdio communication
- Learn more: https://modelcontextprotocol.io

**Fuzzy Matching:**
- RapidFuzz library
- Multi-field scoring (title, artist, album)
- Confidence thresholds

---

## 🚀 What's Next?

### After Testing Locally

Once you're comfortable with local testing:

1. **📖 Read:** [Payment & Deployment Planning](./PAYMENT_DEPLOYMENT_PLAN.md)
   - Understand costs for web deployment
   - Choose hosting options
   - Scale considerations

2. **🌍 Deploy to Web:**
   - See main README.md → "Production Deployment" section
   - Set up domain and SSL
   - Deploy to cloud provider

3. **📈 Monitor in Production:**
   - Set up alerts
   - Track API usage
   - Optimize costs

### Experiment Locally

**Try these experiments:**

1. **Load Testing:**
   ```bash
   # Sync 100 songs in parallel
   for i in {1..100}; do
     curl -X POST http://localhost:8000/api/v1/sync \
       -H "Content-Type: application/json" \
       -d '{"track_name":"Test Song '$i'","artist":"Test Artist","playlist_id":"YOUR_ID"}' &
   done
   ```

2. **Adjust Matching Thresholds:**
   - Change `FUZZY_MATCH_THRESHOLD` in `.env`
   - Test how it affects matching accuracy

3. **Compare AI Providers:**
   - Switch between `AI_PROVIDER=claude` and `AI_PROVIDER=langchain`
   - Compare accuracy and cost

4. **Monitor Performance:**
   - Watch Prometheus metrics: http://localhost:9090
   - View Grafana dashboards: http://localhost:3000

---

## 🎯 Quick Reference

### Start Everything

```bash
# Terminal 1: Start infrastructure
docker-compose up -d

# Terminal 2: Start worker
source .venv/bin/activate
python workers/music_sync_worker.py

# Terminal 3: Start API
source .venv/bin/activate
python -m uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload
```

### Stop Everything

```bash
# Stop API: Ctrl+C in Terminal 3
# Stop worker: Ctrl+C in Terminal 2
# Stop infrastructure:
docker-compose down
```

### Reset Everything

```bash
# Stop all services
docker-compose down -v

# Clear Spotify cache
rm .cache-spotify

# Start fresh
docker-compose up -d
```

### Quick Test

```bash
curl -X POST http://localhost:8000/api/v1/sync \
  -H "Content-Type: application/json" \
  -d '{"track_name":"Bohemian Rhapsody","artist":"Queen","playlist_id":"YOUR_ID"}'
```

---

## 💡 Pro Tips

1. **Keep Worker Running:** The worker must be running to process workflows
2. **Check Logs:** Always check terminal logs for errors
3. **Use Temporal UI:** Great for debugging workflow issues
4. **Start Simple:** Test with well-known songs first
5. **Save Free Credits:** Increase fuzzy threshold to use less AI
6. **Monitor Usage:** Check AI API dashboard regularly
7. **Test on WiFi:** iOS Shortcuts only work on same network
8. **Use Version Control:** Commit your `.env` changes (but don't push secrets!)

---

## 📞 Support

- **Main Documentation:** [README.md](./README.md)
- **iOS Shortcuts Setup:** [docs/ios-shortcuts-setup.md](./docs/ios-shortcuts-setup.md)
- **Temporal Docs:** https://docs.temporal.io
- **MCP Docs:** https://modelcontextprotocol.io
- **Spotify API Docs:** https://developer.spotify.com/documentation/web-api

---

**Happy Testing! 🎵**

If you encounter any issues, check the Troubleshooting section above or refer to the main README.md.
