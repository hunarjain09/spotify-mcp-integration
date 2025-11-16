#!/usr/bin/env python3
"""Manual Spotify OAuth flow for headless/remote environments.

This script generates an authorization URL that you can visit in your browser,
then accepts the callback URL to complete authentication.
"""

import os
import json
import sys
import time
from urllib.parse import urlencode, urlparse, parse_qs
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get credentials from environment
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")
SCOPE = "playlist-modify-public playlist-modify-private playlist-read-private"

if not CLIENT_ID or not CLIENT_SECRET:
    print("❌ Error: SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set in .env")
    sys.exit(1)

print("=" * 70)
print("🎵 Spotify Manual OAuth Authentication")
print("=" * 70)
print()

# Step 1: Generate authorization URL
auth_params = {
    "client_id": CLIENT_ID,
    "response_type": "code",
    "redirect_uri": REDIRECT_URI,
    "scope": SCOPE,
    "show_dialog": "true",
}

auth_url = f"https://accounts.spotify.com/authorize?{urlencode(auth_params)}"

print("Step 1: Visit this URL in your browser to authorize the app:")
print()
print(auth_url)
print()
print("-" * 70)
print()
print("Step 2: After authorizing, you'll be redirected to a URL that looks like:")
print(f"  {REDIRECT_URI}?code=AQD...")
print()
print("Copy the ENTIRE URL from your browser's address bar and paste it below.")
print()

# Step 2: Get callback URL from user
callback_url = input("Paste the full callback URL here: ").strip()

if not callback_url:
    print("❌ No URL provided. Exiting.")
    sys.exit(1)

# Step 3: Parse the authorization code
try:
    parsed_url = urlparse(callback_url)
    query_params = parse_qs(parsed_url.query)

    if "code" not in query_params:
        print("❌ Error: No authorization code found in the URL.")
        print("Make sure you copied the complete URL after authorizing.")
        sys.exit(1)

    auth_code = query_params["code"][0]
    print()
    print("✓ Authorization code extracted successfully")

except Exception as e:
    print(f"❌ Error parsing URL: {e}")
    sys.exit(1)

# Step 4: Exchange code for access token
print("✓ Exchanging code for access token...")

token_url = "https://accounts.spotify.com/api/token"
token_data = {
    "grant_type": "authorization_code",
    "code": auth_code,
    "redirect_uri": REDIRECT_URI,
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
}

try:
    response = requests.post(token_url, data=token_data)
    response.raise_for_status()
    token_info = response.json()

    # Add expires_at timestamp (required by spotipy)
    if "expires_in" in token_info:
        token_info["expires_at"] = int(time.time()) + token_info["expires_in"]

    print("✓ Access token received")

except requests.exceptions.RequestException as e:
    print(f"❌ Error getting access token: {e}")
    if hasattr(e.response, 'text'):
        print(f"Response: {e.response.text}")
    sys.exit(1)

# Step 5: Save token info to cache file (same format as spotipy)
cache_path = ".cache-spotify"
try:
    with open(cache_path, "w") as f:
        json.dump(token_info, f, indent=2)

    print(f"✓ Token saved to {cache_path}")
    print()
    print("=" * 70)
    print("✅ Authentication successful!")
    print("=" * 70)
    print()
    print("You can now start the API server:")
    print("  uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload")
    print()

except Exception as e:
    print(f"❌ Error saving token: {e}")
    sys.exit(1)

# Step 6: Verify by getting user info
print("Verifying authentication...")
try:
    headers = {"Authorization": f"Bearer {token_info['access_token']}"}
    user_response = requests.get("https://api.spotify.com/v1/me", headers=headers)
    user_response.raise_for_status()
    user_info = user_response.json()

    print(f"✓ Logged in as: {user_info.get('display_name', 'Unknown')} ({user_info.get('id')})")
    print(f"✓ Email: {user_info.get('email', 'N/A')}")
    print()

except Exception as e:
    print(f"⚠️  Warning: Could not verify user info: {e}")
    print("   (Token may still be valid)")
    print()
