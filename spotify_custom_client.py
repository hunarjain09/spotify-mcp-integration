"""Custom MCP client for Spotify server that bypasses the buggy stdio_client."""
import asyncio
import json
import sys
from typing import Any, Dict, List, Optional

async def main():
    # Start the Spotify server process
    print("🎵 Starting Spotify MCP server...", file=sys.stderr)
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "mcp_server/spotify_server.py",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    request_id = 0

    async def send_request(method: str, params: Dict[str, Any] = None) -> Dict:
        """Send a JSON-RPC request and wait for response."""
        nonlocal request_id
        request_id += 1

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params:
            request["params"] = params

        # Send request
        request_line = json.dumps(request) + "\n"
        print(f"\n📤 Sending: {method}", file=sys.stderr)
        proc.stdin.write(request_line.encode())
        await proc.stdin.drain()

        # Read response
        response_line = await proc.stdout.readline()
        if not response_line:
            raise Exception("Server closed connection")

        response = json.loads(response_line.decode())

        if "error" in response:
            print(f"❌ RPC Error: {response['error']}", file=sys.stderr)
            raise Exception(f"RPC Error: {response['error']}")

        return response.get("result")

    try:
        # Check for server initialization errors
        async def check_stderr():
            """Monitor stderr for server status messages."""
            while True:
                line = await proc.stderr.readline()
                if not line:
                    break
                msg = line.decode().strip()
                if msg:
                    print(f"[Server] {msg}", file=sys.stderr)

        # Start stderr monitor in background
        stderr_task = asyncio.create_task(check_stderr())

        # Give server a moment to initialize
        await asyncio.sleep(1)

        # Initialize session
        print("\n1️⃣  Initializing session...", file=sys.stderr)
        init_result = await send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "spotify-custom-client", "version": "1.0.0"},
            },
        )
        print(f"   ✓ Initialized: {init_result['serverInfo']['name']}", file=sys.stderr)

        # Send initialized notification
        notification = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        proc.stdin.write((json.dumps(notification) + "\n").encode())
        await proc.stdin.drain()

        # List available tools
        print("\n2️⃣  Listing available Spotify tools...", file=sys.stderr)
        tools_result = await send_request("tools/list")
        print(f"   ✓ Found {len(tools_result['tools'])} tools:", file=sys.stderr)
        for tool in tools_result["tools"]:
            print(f"     • {tool['name']}: {tool['description']}", file=sys.stderr)

        # Test 1: Search for a track
        print("\n3️⃣  Testing search_track...", file=sys.stderr)
        search_result = await send_request(
            "tools/call",
            {
                "name": "search_track",
                "arguments": {"query": "Never Gonna Give You Up Rick Astley", "limit": 3}
            },
        )
        tracks_data = json.loads(search_result['content'][0]['text'])
        if tracks_data.get('tracks'):
            print(f"   ✓ Found {len(tracks_data['tracks'])} tracks:", file=sys.stderr)
            for track in tracks_data['tracks'][:3]:
                print(f"     • {track['name']} by {track['artist']}", file=sys.stderr)
                print(f"       URI: {track['uri']}", file=sys.stderr)
        else:
            print(f"   ⚠️  No tracks found", file=sys.stderr)

        # Test 2: Get user playlists
        print("\n4️⃣  Testing get_user_playlists...", file=sys.stderr)
        playlists_result = await send_request(
            "tools/call",
            {"name": "get_user_playlists", "arguments": {"limit": 5}},
        )
        playlists_data = json.loads(playlists_result['content'][0]['text'])
        if playlists_data.get('playlists'):
            print(f"   ✓ Found {len(playlists_data['playlists'])} playlists:", file=sys.stderr)
            for playlist in playlists_data['playlists'][:5]:
                print(f"     • {playlist['name']} ({playlist['tracks_total']} tracks)", file=sys.stderr)
                print(f"       ID: {playlist['id']}", file=sys.stderr)
        else:
            print(f"   ⚠️  No playlists found", file=sys.stderr)

        print("\n✅ All Spotify MCP server tests completed successfully!", file=sys.stderr)
        print("\n💡 You can now use this custom client approach to interact with your Spotify server!", file=sys.stderr)

    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
    finally:
        # Clean up
        print("\n🛑 Shutting down server...", file=sys.stderr)
        proc.stdin.close()
        try:
            await asyncio.wait_for(proc.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            proc.terminate()
            await proc.wait()

if __name__ == "__main__":
    asyncio.run(main())
