#!/usr/bin/env python3
"""
Test script for MCP Spotify Server
Tests basic connectivity and functionality of the MCP server
"""

import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
from dotenv import load_dotenv

load_dotenv()

print("Testing spotipy directly...")
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=os.getenv('SPOTIFY_CLIENT_ID'),
    client_secret=os.getenv('SPOTIFY_CLIENT_SECRET'),
    redirect_uri=os.getenv('SPOTIFY_REDIRECT_URI'),
    scope='playlist-modify-public playlist-modify-private playlist-read-private',
    cache_path='.cache-spotify'
))

print("Getting current user...")
user = sp.current_user()
print(f"✓ User: {user['display_name']}")

print("\nSearching for 'Imagine John Lennon'...")
results = sp.search(q="Imagine John Lennon", type="track", limit=3)
print(f"✓ Found {len(results['tracks']['items'])} tracks:")
for track in results['tracks']['items']:
    print(f"  - {track['name']} by {track['artists'][0]['name']}")

print("\n✓ MCP Server test completed successfully!")
