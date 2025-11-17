import asyncio
from mcp_client.client import SpotifyMCPClient

async def test():
    print("Creating MCP client...")
    client = SpotifyMCPClient()
    
    print("Connecting to MCP server...")
    await client.connect()
    print("✓ Connected")
    
    print("\nSearching for 'Imagine John Lennon'...")
    try:
        result = await asyncio.wait_for(
            client.search_track("Imagine John Lennon", limit=3),
            timeout=10.0
        )
        print(f"✓ Search succeeded: {len(result.get('tracks', []))} tracks found")
        for track in result.get('tracks', [])[:3]:
            print(f"  - {track['name']} by {track['artist']}")
    except asyncio.TimeoutError:
        print("✗ Search timed out after 10 seconds - MCP server is hanging!")
    except Exception as e:
        print(f"✗ Search failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\nClosing connection...")
    await client.close()
    print("✓ Done")

asyncio.run(test())
