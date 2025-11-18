"""
Script to upload Spotify OAuth token from .cache-spotify to Firestore.

This allows Firebase Functions to access the Spotify API with your credentials.
"""
import json
from pathlib import Path
from firebase_admin import credentials, firestore, initialize_app

# Initialize Firebase Admin
initialize_app()
db = firestore.client()

# Read local Spotify cache
cache_file = Path(__file__).parent.parent / '.cache-spotify'

if not cache_file.exists():
    print("❌ Error: .cache-spotify file not found")
    print("Run 'python mcp_server/spotify_server.py' first to authenticate with Spotify")
    exit(1)

with open(cache_file) as f:
    token_data = json.load(f)

# Upload to Firestore
doc_ref = db.collection('config').document('spotify_oauth')
doc_ref.set({
    'access_token': token_data.get('access_token'),
    'refresh_token': token_data.get('refresh_token'),
    'expires_at': token_data.get('expires_at'),
    'token_type': token_data.get('token_type', 'Bearer'),
    'scope': token_data.get('scope'),
})

print("✅ Spotify OAuth token uploaded to Firestore")
print(f"   Collection: config")
print(f"   Document: spotify_oauth")
print(f"   Expires at: {token_data.get('expires_at')}")
