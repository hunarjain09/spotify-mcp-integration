#!/bin/bash

# Firebase Functions Deployment Script
# This script automates the deployment process

set -e  # Exit on error

echo "🚀 Starting Firebase Functions deployment..."

# Check if firebase CLI is installed
if ! command -v firebase &> /dev/null; then
    echo "❌ Firebase CLI not found. Install with: npm install -g firebase-tools"
    exit 1
fi

# Check if logged in
if ! firebase projects:list &> /dev/null; then
    echo "❌ Not logged in to Firebase. Run: firebase login"
    exit 1
fi

# Get current project
PROJECT_ID=$(firebase use | grep "Now using project" | awk '{print $4}' | tr -d '()')

if [ -z "$PROJECT_ID" ]; then
    echo "❌ No Firebase project configured. Run: firebase use <project-id>"
    exit 1
fi

echo "📦 Project: $PROJECT_ID"

# Confirm deployment
read -p "Deploy to $PROJECT_ID? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Deployment cancelled"
    exit 1
fi

# Check if secrets are set
echo "🔐 Checking secrets..."
REQUIRED_SECRETS=("ANTHROPIC_API_KEY" "SPOTIFY_CLIENT_ID" "SPOTIFY_CLIENT_SECRET")

for secret in "${REQUIRED_SECRETS[@]}"; do
    if ! firebase functions:secrets:access $secret &> /dev/null; then
        echo "⚠️  Secret $secret not set. Set with: firebase functions:secrets:set $secret"
    else
        echo "   ✅ $secret"
    fi
done

# Deploy functions
echo "📤 Deploying functions..."
firebase deploy --only functions

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📍 Your function URLs:"
firebase functions:list | grep spotify_sync

echo ""
echo "📊 View logs:"
echo "   firebase functions:log --only spotify_sync"
echo ""
echo "🧪 Test your function:"
echo "   curl https://YOUR_REGION-$PROJECT_ID.cloudfunctions.net/spotify_sync/health"
echo ""
