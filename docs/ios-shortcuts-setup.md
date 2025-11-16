# iOS Shortcuts Setup Guide

This guide will help you set up the iOS Shortcut to sync songs from Apple Music to Spotify.

## Prerequisites

- iPhone with iOS 14+
- Shortcuts app installed
- Both Apple Music and Spotify apps installed
- Server running and accessible on your network

## Step 1: Get Your Server IP Address

### On Mac (same WiFi network):

```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
```

Look for something like: `inet 192.168.1.100`

### On Linux:

```bash
ip addr show | grep "inet " | grep -v 127.0.0.1
```

### Test Connectivity

On your iPhone, open Safari and visit:
```
http://YOUR_IP:8000/api/v1/health
```

You should see a JSON response with `"status": "healthy"`.

## Step 2: Get Your Spotify Playlist ID

1. Open Spotify on your phone or computer
2. Navigate to the playlist you want to sync to
3. Tap/click the **•••** (three dots) menu
4. Select **Share** → **Copy link to playlist**
5. Extract the ID from the URL

Example URL:
```
https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M
                                  ^^^^^^^^^^^^^^^^^^^^^^
                                  This is your playlist ID
```

## Step 3: Create the Shortcut

### Option A: Manual Setup

1. Open **Shortcuts** app on iPhone
2. Tap **+** (top right) to create new shortcut
3. Tap **Add Action**
4. Follow the action sequence below

### Action Sequence:

#### 1. Receive Input
- Search for **"Receive"** action
- Add it to your shortcut
- Configure:
  - Input Type: **Music**
  - Source: **Share Sheet**

#### 2. Get Track Name
- Add **"Get Details of Music"** action
- Configure:
  - Detail: **Name**
- Tap and hold the result → **Set Variable**
- Name it: `trackName`

#### 3. Get Artist
- Add another **"Get Details of Music"** action
- Configure:
  - Detail: **Artist**
- Set Variable: `artistName`

#### 4. Get Album
- Add another **"Get Details of Music"** action
- Configure:
  - Detail: **Album Name**
- Set Variable: `albumName`

#### 5. Create Dictionary
- Add **"Dictionary"** action
- Configure keys and values:
  - **track_name**: tap → Insert Variable → `trackName`
  - **artist**: tap → Insert Variable → `artistName`
  - **album**: tap → Insert Variable → `albumName`
  - **playlist_id**: `YOUR_PLAYLIST_ID` (paste your actual ID)

#### 6. Make API Request
- Add **"Get Contents of URL"** action
- Configure:
  - URL: `http://YOUR_IP:8000/api/v1/sync`
  - Method: **POST**
  - Headers: Add header
    - Key: `Content-Type`
    - Value: `application/json`
  - Request Body: **JSON**
  - JSON: Insert Variable → **Dictionary** (from step 5)

#### 7. Show Notification (Optional)
- Add **"Show Notification"** action
- Configure:
  - Title: `Added to Spotify`
  - Body: Tap → Insert Variable → `trackName` then type ` by ` then Insert Variable → `artistName`

### Final Configuration:

1. Tap the shortcut name at top
2. Rename to: **Add to Spotify**
3. Tap **Share Sheet Types**
4. Enable: **Music**
5. Tap **Done**

## Step 4: Test the Shortcut

1. Open **Apple Music** app
2. Find any song
3. Tap the **•••** (three dots) menu or **Share** button
4. Scroll down and select **Add to Spotify**
5. You should see a notification that the sync started

## Step 5: Verify the Sync

### Check in Shortcuts App:
- Open Shortcuts app
- Tap on your shortcut
- View the **Last Run** result

### Check API Status:

If you saved the workflow ID, check status:
```bash
curl http://YOUR_IP:8000/api/v1/sync/WORKFLOW_ID
```

### Check Spotify:
- Open Spotify
- Go to your playlist
- The song should appear within a few seconds

## Advanced Configuration

### Custom Matching Threshold

Modify the dictionary in step 5 to add:
- **match_threshold**: `0.85` (adjust between 0.0-1.0)

Higher = stricter matching, Lower = more permissive

### Disable AI Disambiguation

Add to dictionary:
- **use_ai_disambiguation**: `false`

This saves OpenAI API costs but may result in fewer matches for ambiguous songs.

### Multiple Playlists

Create multiple shortcuts with different playlist IDs:
- "Add to Workout Playlist"
- "Add to Chill Playlist"
- "Add to Favorites"

## Troubleshooting

### "The operation couldn't be completed"

**Possible causes:**
1. Server not reachable from iPhone
2. Wrong IP address
3. Server not running

**Solution:**
- Test the health endpoint in Safari first
- Make sure iPhone is on same WiFi network
- Check firewall settings on your Mac

### "Invalid Request"

**Possible causes:**
1. Missing playlist_id
2. Malformed JSON
3. Incorrect playlist ID format

**Solution:**
- Double-check playlist ID is exactly 22 characters
- Verify dictionary structure in step 5
- Test with curl first to confirm server is working

### Sync appears to work but song doesn't show up

**Possible causes:**
1. Song not available on Spotify in your region
2. Match confidence too low
3. Incorrect playlist permissions

**Solution:**
- Check the workflow status via API
- Try the same song manually on Spotify
- Verify playlist is set to public or you have edit permissions

### Shortcut runs slowly

**This is normal:**
- Matching can take 2-10 seconds
- AI disambiguation adds 5-15 seconds
- The notification appears immediately, sync happens in background

## Example Shortcut (Importable)

If you prefer to import a ready-made shortcut, here's the configuration:

### Shortcut Link Format:

```
shortcuts://create-shortcut?name=Add%20to%20Spotify&...
```

Note: Due to iOS limitations, you'll still need to manually enter:
1. Your server IP address
2. Your playlist ID

## Tips & Best Practices

1. **Create a Home Screen widget** for quick access
2. **Use the Today View** for one-swipe access
3. **Create multiple versions** for different playlists
4. **Test with well-known songs** first (e.g., "Bohemian Rhapsody" by Queen)
5. **Check Temporal Web UI** (http://YOUR_IP:8080) to debug failures

## Security Note

This shortcut sends song metadata over HTTP on your local network. If deploying to production:

1. Use HTTPS with valid SSL certificate
2. Implement API authentication
3. Consider using a VPN for remote access

---

**Next Steps:**
- [Deployment Guide](deployment-guide.md) - Deploy to production
- [API Reference](../README.md#api-reference) - Learn about the API
- [Troubleshooting](../README.md#troubleshooting) - Common issues
