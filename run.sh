#!/bin/bash

# Quick start script for Apple Music to Spotify Sync
# This script starts all necessary components

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Apple Music to Spotify Sync${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Please copy .env.example to .env and configure it:"
    echo "  cp .env.example .env"
    echo "  nano .env  # or use your preferred editor"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -q -r requirements.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    echo "Please start Docker Desktop and try again"
    exit 1
fi

# Start Temporal with Docker Compose
echo -e "${YELLOW}Starting Temporal services...${NC}"
docker-compose up -d

# Wait for Temporal to be healthy
echo -e "${YELLOW}Waiting for Temporal to be ready...${NC}"
sleep 10

# Check if Temporal is accessible
if curl -s http://localhost:7233 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Temporal is running${NC}"
else
    echo -e "${YELLOW}⚠ Temporal may still be starting...${NC}"
fi

# Check if Spotify cache exists (authentication)
if [ ! -f ".cache-spotify" ]; then
    echo -e "${YELLOW}⚠ Spotify not authenticated yet${NC}"
    echo "You'll need to authenticate when you first start the MCP server"
fi

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Services Started Successfully!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo "Next steps:"
echo ""
echo "1. Start the Temporal worker:"
echo -e "   ${YELLOW}python workers/music_sync_worker.py${NC}"
echo ""
echo "2. In a new terminal, start the API server:"
echo -e "   ${YELLOW}python -m uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload${NC}"
echo ""
echo "3. Access services:"
echo "   - API Docs: http://localhost:8000/docs"
echo "   - Temporal UI: http://localhost:8080"
echo "   - Health Check: http://localhost:8000/api/v1/health"
echo ""
echo "4. Get your local IP for iOS Shortcuts:"
echo -e "   ${YELLOW}ifconfig | grep 'inet ' | grep -v 127.0.0.1${NC}"
echo ""
echo -e "${GREEN}Happy syncing! 🎵${NC}"
