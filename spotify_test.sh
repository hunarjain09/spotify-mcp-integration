#!/bin/bash

# Your access token from .cache-spotify
TOKEN="BQCrVuzPC1_mxWLeGEVPMvbfhW5lnNKb8B588CGgjJjAD3POyg1ZAbfD76RtPkGbSXOEQXMAbjKVA2EFKwuo_A3mIGL791FePn9UN3gZcUrPxe5PpEIU7ubAyJ2ykV3WXH53nUUPFgvRXvp5wBx7gkOw2WcIYMhvsudBjaSNsoq6nvGXOM5QVy1RfEE8x6kNdVThWQph83exuOaim92eDuzN-IrCS6e_RTuq50_TOpMYGFdO-fdzgvx0cQvKj0U3AWYHucoTyMaq3m6_4mLs17FjfRe_YigLFepcflfdYHkvPa8g1PziRRCeag"

PLAYLIST_ID="43X1N9GAKwVARreGxSAdZI"

echo "1. Testing User Profile..."
curl -s "https://api.spotify.com/v1/me" -H "Authorization: Bearer $TOKEN" | jq .

echo -e "\n2. Testing Track Search..."
curl -s "https://api.spotify.com/v1/search?q=Imagine%20John%20Lennon&type=track&limit=3" -H "Authorization: Bearer $TOKEN" | jq '.tracks.items[] | {name, artist: .artists[0].name, uri}'

echo -e "\n3. Testing Get Playlists..."
curl -s "https://api.spotify.com/v1/me/playlists?limit=5" -H "Authorization: Bearer $TOKEN" | jq '.items[] | {name, id, tracks: .tracks.total}'

echo -e "\n4. Testing Get Playlist Tracks..."
curl -s "https://api.spotify.com/v1/playlists/$PLAYLIST_ID/tracks?limit=5" -H "Authorization: Bearer $TOKEN" | jq '.items[] | .track.name'

echo -e "\n5. Testing Audio Features..."
TRACK_ID="7pKfPomDEeI4TPT6EOYjn9"  # Imagine by John Lennon
curl -s "https://api.spotify.com/v1/audio-features/$TRACK_ID" -H "Authorization: Bearer $TOKEN" | jq '{tempo, energy, valence, danceability}'

echo -e "\nAll tests complete!"
