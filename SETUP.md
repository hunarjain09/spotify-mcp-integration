# Local Development Setup Guide

This guide will walk you through setting up the Spotify MCP Integration project on your local machine for development and testing.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [System Requirements](#system-requirements)
3. [Installation Steps](#installation-steps)
4. [Configuration](#configuration)
5. [Running Services](#running-services)
6. [Verification](#verification)
7. [Troubleshooting](#troubleshooting)
8. [Development Workflow](#development-workflow)

## Prerequisites

Before you begin, ensure you have the following installed on your system:

### Required Software

- **Python 3.11+** - [Download](https://www.python.org/downloads/)
- **Docker & Docker Compose** - [Download](https://www.docker.com/get-started)
- **Git** - [Download](https://git-scm.com/downloads)

### API Credentials

You'll need to obtain API credentials from the following services:

1. **Spotify Developer Account**
   - Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
   - Create a new app
   - Note your `Client ID` and `Client Secret`
   - Add `http://localhost:8888/callback` to the Redirect URIs

2. **OpenAI API Account**
   - Go to [OpenAI Platform](https://platform.openai.com/)
   - Create an API key
   - Note your API key

## System Requirements

### Minimum Requirements

- **CPU**: 2 cores
- **RAM**: 4 GB
- **Disk**: 2 GB free space
- **OS**: macOS, Linux, or Windows (with WSL2)

### Recommended Requirements

- **CPU**: 4+ cores
- **RAM**: 8+ GB
- **Disk**: 5+ GB free space

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/spotify-mcp-integration.git
cd spotify-mcp-integration
```

### 2. Create a Virtual Environment

**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**On Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Python Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This will install all required packages including:
- FastAPI and Uvicorn (API server)
- Temporal SDK (workflow orchestration)
- Spotipy (Spotify API client)
- LangChain & OpenAI (AI disambiguation)
- RapidFuzz (fuzzy matching)
- MCP (Model Context Protocol)
- Testing tools (pytest, pytest-asyncio, pytest-cov)

### 4. Set Up Infrastructure with Docker

Start the required services (Temporal Server, PostgreSQL, etc.):

```bash
docker-compose up -d
```

This will start:
- **Temporal Server** (workflow engine) - Port 7233
- **Temporal UI** (web interface) - [http://localhost:8080](http://localhost:8080)
- **PostgreSQL** (Temporal database) - Port 5432

Verify services are running:
```bash
docker-compose ps
```

All services should show status as `Up`.

### 5. Configure Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```bash
# Spotify API Credentials
SPOTIFY_CLIENT_ID=your_spotify_client_id_here
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret_here
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
AI_MODEL=gpt-4

# Temporal Configuration (use defaults for local development)
TEMPORAL_HOST=localhost:7233
TEMPORAL_NAMESPACE=default

# API Server Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Matching Configuration
FUZZY_MATCH_THRESHOLD=0.85
USE_AI_DISAMBIGUATION=true

# Worker Configuration
MAX_CONCURRENT_ACTIVITIES=100
MAX_CONCURRENT_WORKFLOWS=50
MAX_ACTIVITIES_PER_SECOND=10.0

# Logging
LOG_LEVEL=INFO

# Task Queue
TASK_QUEUE_NAME=music-sync-queue
```

### 6. Authenticate with Spotify

Run the authentication script to get Spotify access tokens:

```bash
python scripts/spotify_auth.py
```

This will:
1. Open your browser
2. Ask you to log in to Spotify
3. Request necessary permissions
4. Save your access token locally

## Configuration

### Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SPOTIFY_CLIENT_ID` | Yes | - | Spotify app client ID |
| `SPOTIFY_CLIENT_SECRET` | Yes | - | Spotify app client secret |
| `SPOTIFY_REDIRECT_URI` | No | `http://localhost:8888/callback` | OAuth redirect URI |
| `OPENAI_API_KEY` | Yes | - | OpenAI API key |
| `AI_MODEL` | No | `gpt-4` | OpenAI model to use |
| `TEMPORAL_HOST` | No | `localhost:7233` | Temporal server address |
| `TEMPORAL_NAMESPACE` | No | `default` | Temporal namespace |
| `API_HOST` | No | `0.0.0.0` | FastAPI host |
| `API_PORT` | No | `8000` | FastAPI port |
| `FUZZY_MATCH_THRESHOLD` | No | `0.85` | Matching confidence threshold (0.0-1.0) |
| `USE_AI_DISAMBIGUATION` | No | `true` | Enable AI for ambiguous matches |
| `LOG_LEVEL` | No | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

### Temporal Cloud Configuration (Optional)

If using Temporal Cloud instead of local Temporal:

```bash
TEMPORAL_HOST=your-namespace.your-account.tmprl.cloud:7233
TEMPORAL_NAMESPACE=your-namespace
TEMPORAL_TLS_CERT_PATH=/path/to/client.pem
TEMPORAL_TLS_KEY_PATH=/path/to/client.key
```

## Running Services

### Start All Services

Use the provided run script:

```bash
chmod +x run.sh
./run.sh
```

Or start services manually:

### 1. Start the Temporal Worker

In one terminal:

```bash
python workers/music_sync_worker.py
```

You should see:
```
✓ Worker started successfully
✓ Listening on task queue: music-sync-queue
```

### 2. Start the FastAPI Server

In another terminal:

```bash
python api/app.py
```

Or using uvicorn directly:

```bash
uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload
```

You should see:
```
✓ Connected to Temporal
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 3. Start the MCP Server (Optional)

If you want to run the MCP server separately:

```bash
python mcp_server/spotify_server.py
```

## Verification

### 1. Check API Health

```bash
curl http://localhost:8000/api/v1/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-16T10:30:00Z",
  "temporal_connected": true,
  "version": "1.0.0"
}
```

### 2. Check Temporal UI

Open [http://localhost:8080](http://localhost:8080) in your browser.

You should see the Temporal Web UI with the `default` namespace.

### 3. Test a Sync Request

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

Expected response:
```json
{
  "workflow_id": "sync-anonymous-1699564832-a3f9d",
  "status": "accepted",
  "message": "Sync started for 'Bohemian Rhapsody' by Queen",
  "status_url": "/api/v1/sync/sync-anonymous-1699564832-a3f9d"
}
```

### 4. Check Workflow Status

```bash
curl http://localhost:8000/api/v1/sync/{workflow_id}
```

Replace `{workflow_id}` with the ID from the previous response.

## Troubleshooting

### Common Issues

#### 1. "Temporal client not connected"

**Problem**: FastAPI can't connect to Temporal server.

**Solutions**:
```bash
# Check if Temporal is running
docker-compose ps

# Restart Temporal
docker-compose restart temporal

# Check Temporal logs
docker-compose logs temporal
```

#### 2. "Module not found" errors

**Problem**: Missing Python dependencies.

**Solution**:
```bash
# Make sure virtual environment is activated
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate  # Windows

# Reinstall dependencies
pip install -r requirements.txt
```

#### 3. "Spotify API authentication failed"

**Problem**: Invalid Spotify credentials or tokens.

**Solutions**:
```bash
# Verify credentials in .env
cat .env | grep SPOTIFY

# Re-authenticate
python scripts/spotify_auth.py

# Check Spotify app settings at
# https://developer.spotify.com/dashboard
```

#### 4. Port already in use

**Problem**: Port 8000 or 7233 already in use.

**Solutions**:
```bash
# Find process using port 8000
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Kill the process or change port in .env
API_PORT=8001
```

#### 5. Docker services won't start

**Problem**: Docker containers failing to start.

**Solutions**:
```bash
# Stop all containers
docker-compose down

# Remove volumes and restart
docker-compose down -v
docker-compose up -d

# Check Docker daemon is running
docker info
```

### Debug Mode

Enable debug logging for more information:

```bash
# In .env
LOG_LEVEL=DEBUG

# Restart services
```

### Logs Location

- **API Server**: Console output
- **Temporal Worker**: Console output
- **Temporal Server**: `docker-compose logs temporal`
- **Docker Compose**: `docker-compose logs`

## Development Workflow

### Making Changes

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Edit code in your IDE
   - Add tests for new features

3. **Run tests**
   ```bash
   pytest
   ```

4. **Format code**
   ```bash
   black .
   ruff check .
   ```

5. **Commit changes**
   ```bash
   git add .
   git commit -m "Add: your feature description"
   ```

### Hot Reload

The API server supports hot reload when using `--reload` flag:

```bash
uvicorn api.app:app --reload
```

Changes to Python files will automatically restart the server.

### Database Access

Access PostgreSQL (Temporal's database):

```bash
docker-compose exec postgresql psql -U temporal
```

### Resetting Everything

To start fresh:

```bash
# Stop all services
docker-compose down -v

# Remove Python cache
find . -type d -name __pycache__ -exec rm -r {} +
find . -type f -name "*.pyc" -delete

# Reinstall dependencies
pip install -r requirements.txt

# Restart services
docker-compose up -d
python workers/music_sync_worker.py &
python api/app.py
```

## Next Steps

- Read [TESTING.md](./TESTING.md) for information on running tests
- See [README.md](./README.md) for API documentation
- Check [docs/ios-shortcuts-setup.md](./docs/ios-shortcuts-setup.md) for iOS integration

## Getting Help

If you encounter issues not covered in this guide:

1. Check the [GitHub Issues](https://github.com/yourusername/spotify-mcp-integration/issues)
2. Review Temporal documentation at [docs.temporal.io](https://docs.temporal.io)
3. Check Spotify API docs at [developer.spotify.com](https://developer.spotify.com)
4. Open a new issue with detailed error messages and logs
