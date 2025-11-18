#!/bin/bash
# Test Firebase Emulator Setup
# This script validates your Firebase emulator configuration

set -e

echo "🧪 Validating Firebase Emulator Setup..."
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Firebase CLI
echo -n "Checking Firebase CLI... "
if command -v firebase &> /dev/null; then
    VERSION=$(firebase --version)
    echo -e "${GREEN}✓${NC} Found: $VERSION"
else
    echo -e "${RED}✗${NC} Not installed"
    echo ""
    echo "Install with:"
    echo "  npm install -g firebase-tools"
    exit 1
fi

# Check Node.js
echo -n "Checking Node.js... "
if command -v node &> /dev/null; then
    VERSION=$(node --version)
    echo -e "${GREEN}✓${NC} Found: $VERSION"
else
    echo -e "${YELLOW}⚠${NC}  Not found (required for Firebase CLI)"
fi

# Check Python
echo -n "Checking Python... "
if command -v python3 &> /dev/null; then
    VERSION=$(python3 --version)
    echo -e "${GREEN}✓${NC} Found: $VERSION"
else
    echo -e "${RED}✗${NC} Not found"
    exit 1
fi

# Check firebase.json
echo -n "Checking firebase.json... "
if [ -f "firebase.json" ]; then
    echo -e "${GREEN}✓${NC} Found"

    # Validate emulator config
    if grep -q '"emulators"' firebase.json; then
        echo -e "  ${GREEN}✓${NC} Emulators configured"
    else
        echo -e "  ${YELLOW}⚠${NC}  No emulator configuration found"
    fi
else
    echo -e "${RED}✗${NC} Not found"
    exit 1
fi

# Check .firebaserc
echo -n "Checking .firebaserc... "
if [ -f ".firebaserc" ]; then
    PROJECT_ID=$(grep -o '"default": "[^"]*"' .firebaserc | cut -d'"' -f4)
    if [ "$PROJECT_ID" == "YOUR_FIREBASE_PROJECT_ID" ]; then
        echo -e "${YELLOW}⚠${NC}  Found but not configured"
        echo "  Update PROJECT_ID in .firebaserc"
    else
        echo -e "${GREEN}✓${NC} Found: $PROJECT_ID"
    fi
else
    echo -e "${RED}✗${NC} Not found"
    exit 1
fi

# Check functions directory
echo -n "Checking functions directory... "
if [ -d "functions" ]; then
    echo -e "${GREEN}✓${NC} Found"

    # Check main.py
    if [ -f "functions/main.py" ]; then
        echo -e "  ${GREEN}✓${NC} main.py exists"
    else
        echo -e "  ${RED}✗${NC} main.py not found"
    fi

    # Check requirements.txt
    if [ -f "functions/requirements.txt" ]; then
        echo -e "  ${GREEN}✓${NC} requirements.txt exists"
    else
        echo -e "  ${RED}✗${NC} requirements.txt not found"
    fi

    # Check .env.yaml
    if [ -f "functions/.env.yaml" ]; then
        echo -e "  ${GREEN}✓${NC} .env.yaml exists (local config)"
    else
        echo -e "  ${YELLOW}⚠${NC}  .env.yaml not found (will use defaults)"
    fi
else
    echo -e "${RED}✗${NC} Not found"
    exit 1
fi

# Check parent dependencies
echo -n "Checking parent directory dependencies... "
PARENT_DEPS_OK=true

for dir in api models config mcp_server agent_executor.py; do
    if [ ! -e "$dir" ]; then
        echo -e "${RED}✗${NC} Missing: $dir"
        PARENT_DEPS_OK=false
    fi
done

if [ "$PARENT_DEPS_OK" = true ]; then
    echo -e "${GREEN}✓${NC} All parent dependencies found"
fi

# Check environment file
echo -n "Checking .env file... "
if [ -f ".env" ]; then
    echo -e "${GREEN}✓${NC} Found"

    # Check for required vars
    if grep -q "ANTHROPIC_API_KEY" .env; then
        echo -e "  ${GREEN}✓${NC} ANTHROPIC_API_KEY configured"
    else
        echo -e "  ${YELLOW}⚠${NC}  ANTHROPIC_API_KEY not found"
    fi

    if grep -q "SPOTIFY_CLIENT_ID" .env; then
        echo -e "  ${GREEN}✓${NC} SPOTIFY_CLIENT_ID configured"
    else
        echo -e "  ${YELLOW}⚠${NC}  SPOTIFY_CLIENT_ID not found"
    fi
else
    echo -e "${YELLOW}⚠${NC}  Not found (create from .env.example)"
fi

echo ""
echo -e "${GREEN}✓ Setup validation complete!${NC}"
echo ""
echo "To start emulators:"
echo "  firebase emulators:start"
echo ""
echo "To run a test sync:"
echo "  ./scripts/test-emulator.sh"
