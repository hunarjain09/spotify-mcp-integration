#!/bin/bash

# Quick start script for Apple Music to Spotify Sync (Agent SDK Edition)
# This script starts the Agent SDK API server

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Apple Music to Spotify Sync${NC}"
echo -e "${GREEN}Agent SDK Edition${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Please copy .env.example to .env and configure it:"
    echo ""
    echo -e "  ${YELLOW}cp .env.example .env${NC}"
    echo -e "  ${YELLOW}nano .env${NC}  # or use your preferred editor"
    echo ""
    echo "Required variables:"
    echo "  - ANTHROPIC_API_KEY (for Agent SDK)"
    echo "  - SPOTIFY_CLIENT_ID"
    echo "  - SPOTIFY_CLIENT_SECRET"
    echo ""
    exit 1
fi

# Check if ANTHROPIC_API_KEY is set
source .env
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo -e "${RED}Error: ANTHROPIC_API_KEY not set in .env${NC}"
    echo "Get your API key from: https://console.anthropic.com/settings/keys"
    exit 1
fi

# Check for Python 3.11+
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
    echo -e "${RED}Error: Python 3.11+ required (found $PYTHON_VERSION)${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python $PYTHON_VERSION${NC}"

# Check if virtual environment exists
if [ ! -d "venv" ] && [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating with UV...${NC}"

    # Check if UV is installed
    if command -v uv &> /dev/null; then
        echo -e "${YELLOW}Using UV for fast dependency installation...${NC}"
        uv sync
        echo -e "${GREEN}✓ Dependencies installed with UV${NC}"
        VENV_PATH=".venv"
    else
        echo -e "${YELLOW}UV not found, using pip...${NC}"
        python3 -m venv venv
        source venv/bin/activate
        pip install -q -r requirements.txt
        echo -e "${GREEN}✓ Dependencies installed with pip${NC}"
        VENV_PATH="venv"
    fi
else
    # Determine which venv exists
    if [ -d ".venv" ]; then
        VENV_PATH=".venv"
    else
        VENV_PATH="venv"
    fi
    echo -e "${GREEN}✓ Virtual environment found${NC}"
fi

# Activate virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source $VENV_PATH/bin/activate
    echo -e "${GREEN}✓ Virtual environment activated${NC}"
fi

# Check if Spotify cache exists (authentication)
if [ ! -f ".cache-spotify" ]; then
    echo ""
    echo -e "${YELLOW}⚠ Spotify not authenticated yet${NC}"
    echo ""
    echo "Before starting the server, please authenticate with Spotify:"
    echo -e "  ${BLUE}python mcp_server/spotify_server.py${NC}"
    echo ""
    echo "This will:"
    echo "  1. Open your browser for Spotify OAuth"
    echo "  2. Create .cache-spotify file with your token"
    echo "  3. Exit (press Ctrl+C after authentication)"
    echo ""
    read -p "Press Enter to continue to server startup..."
fi

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Starting Agent SDK API Server${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""

# Get local IP for iOS Shortcuts
LOCAL_IP=$(ifconfig 2>/dev/null | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -n1)
if [ ! -z "$LOCAL_IP" ]; then
    echo -e "${BLUE}Local IP Address: $LOCAL_IP${NC}"
    echo -e "${BLUE}iOS Shortcuts URL: http://$LOCAL_IP:8000/api/v1/sync${NC}"
    echo ""
fi

echo "Access URLs:"
echo -e "  - API Docs: ${BLUE}http://localhost:8000/docs${NC}"
echo -e "  - Health Check: ${BLUE}http://localhost:8000/api/v1/health${NC}"
echo ""
echo -e "${YELLOW}Starting server...${NC}"
echo ""

# Start the API server
python -m uvicorn api.app_agent:app --host 0.0.0.0 --port 8000 --reload
