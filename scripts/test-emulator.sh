#!/bin/bash
# Test Firebase Functions with Emulator
# This script starts the emulator and runs test requests

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0;m' # No Color

echo -e "${BLUE}🧪 Testing Firebase Functions with Emulator${NC}"
echo ""

# Get project ID from .firebaserc
PROJECT_ID=$(grep -o '"default": "[^"]*"' .firebaserc | cut -d'"' -f4)

if [ "$PROJECT_ID" == "YOUR_FIREBASE_PROJECT_ID" ]; then
    echo -e "${RED}✗ Error: PROJECT_ID not configured in .firebaserc${NC}"
    echo "Update .firebaserc with your Firebase project ID"
    exit 1
fi

echo "Project ID: $PROJECT_ID"
echo ""

# Start emulators in background
echo "Starting Firebase emulators..."
firebase emulators:start --only functions &
EMULATOR_PID=$!

# Trap to kill emulator on script exit
trap "echo ''; echo 'Stopping emulators...'; kill $EMULATOR_PID 2>/dev/null; wait $EMULATOR_PID 2>/dev/null; exit" INT TERM EXIT

# Wait for emulators to start
echo "Waiting for emulators to initialize..."
sleep 10

BASE_URL="http://localhost:5001/$PROJECT_ID/us-central1/spotify_sync"

echo ""
echo -e "${BLUE}Running Tests...${NC}"
echo ""

# Test 1: Health Check
echo -e "${YELLOW}Test 1: Health Check${NC}"
RESPONSE=$(curl -s "$BASE_URL/health")
echo "Response: $RESPONSE"

if echo "$RESPONSE" | grep -q '"status": "healthy"'; then
    echo -e "${GREEN}✓ Health check passed${NC}"
else
    echo -e "${RED}✗ Health check failed${NC}"
fi
echo ""

# Test 2: POST Sync (Fire-and-Forget Mode)
echo -e "${YELLOW}Test 2: POST Sync Request${NC}"
RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "track_name": "Bohemian Rhapsody",
    "artist": "Queen",
    "album": "A Night at the Opera",
    "playlist_id": "37i9dQZF1DXcBWIGoYBM5M"
  }')

echo "Response: $RESPONSE"

if echo "$RESPONSE" | grep -q '"workflow_id"'; then
    echo -e "${GREEN}✓ Sync request accepted${NC}"
    WORKFLOW_ID=$(echo "$RESPONSE" | grep -o '"workflow_id": "[^"]*"' | cut -d'"' -f4)
    echo "  Workflow ID: $WORKFLOW_ID"

    # Check if status_url is null (expected in fire-and-forget mode)
    if echo "$RESPONSE" | grep -q '"status_url": null'; then
        echo -e "${GREEN}✓ Fire-and-forget mode confirmed (status_url: null)${NC}"
    else
        echo -e "${YELLOW}⚠  Status URL present (Firestore mode?)${NC}"
    fi
else
    echo -e "${RED}✗ Sync request failed${NC}"
fi
echo ""

# Test 3: GET Status (Should return 501 in fire-and-forget mode)
if [ ! -z "$WORKFLOW_ID" ]; then
    echo -e "${YELLOW}Test 3: GET Status (should return 501)${NC}"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/sync/$WORKFLOW_ID")
    echo "HTTP Status Code: $HTTP_CODE"

    if [ "$HTTP_CODE" == "501" ]; then
        echo -e "${GREEN}✓ Correctly returns 501 (Not Implemented)${NC}"
        echo "  Status endpoint disabled in fire-and-forget mode"
    elif [ "$HTTP_CODE" == "200" ]; then
        echo -e "${YELLOW}⚠  Returns 200 (Firestore enabled?)${NC}"
    else
        echo -e "${RED}✗ Unexpected status code${NC}"
    fi
    echo ""
fi

# Test 4: Invalid Request
echo -e "${YELLOW}Test 4: Invalid Request (bad playlist ID)${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/v1/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "track_name": "Test",
    "artist": "Artist",
    "playlist_id": "INVALID"
  }')

echo "HTTP Status Code: $HTTP_CODE"

if [ "$HTTP_CODE" == "422" ]; then
    echo -e "${GREEN}✓ Correctly returns 422 (Validation Error)${NC}"
else
    echo -e "${RED}✗ Expected 422, got $HTTP_CODE${NC}"
fi
echo ""

# Test 5: Missing Required Fields
echo -e "${YELLOW}Test 5: Missing Required Fields${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/v1/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "track_name": "Test"
  }')

echo "HTTP Status Code: $HTTP_CODE"

if [ "$HTTP_CODE" == "422" ]; then
    echo -e "${GREEN}✓ Correctly returns 422 (Validation Error)${NC}"
else
    echo -e "${RED}✗ Expected 422, got $HTTP_CODE${NC}"
fi
echo ""

echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo -e "${GREEN}✓ All tests complete!${NC}"
echo ""
echo "View detailed logs at: http://localhost:4000"
echo "Press Ctrl+C to stop emulators"
echo ""

# Keep script running to keep emulators alive
wait $EMULATOR_PID
