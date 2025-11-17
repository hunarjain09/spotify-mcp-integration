"""Test MCP client-server communication with detailed debugging."""
import asyncio
import sys
from mcp_client.client import SpotifyMCPClient

async def test_mcp_communication():
    print("=" * 70)
    print("Testing MCP Client-Server Communication")
    print("=" * 70)
    
    client = SpotifyMCPClient()
    
    try:
        print("\n1. Creating MCP client...")
        print("   ✓ Client created")
        
        print("\n2. Connecting to MCP server subprocess...")
        await asyncio.wait_for(client.connect(), timeout=5.0)
        print("   ✓ Connected (session initialized)")
        
        print("\n3. Testing search_track tool call...")
        print("   Calling: client.search_track('Imagine John Lennon', limit=3)")
        
        # Add timeout to see if it hangs
        result = await asyncio.wait_for(
            client.search_track("Imagine John Lennon", limit=3),
            timeout=15.0
        )
        
        print(f"   ✓ Search completed!")
        print(f"   Found {len(result.get('tracks', []))} tracks:")
        for track in result.get('tracks', [])[:3]:
            print(f"     - {track['name']} by {track['artist']}")
        
        print("\n4. Closing connection...")
        await client.close()
        print("   ✓ Connection closed")
        
        print("\n" + "=" * 70)
        print("✅ All tests passed!")
        print("=" * 70)
        
    except asyncio.TimeoutError as e:
        print(f"\n❌ TIMEOUT: {e}")
        print("\nThe MCP server subprocess is hanging during tool call.")
        print("This suggests an issue with JSON-RPC communication.")
        print("\nDebugging steps:")
        print("1. Check if MCP SDK versions match between client and server")
        print("2. Check for any blocking I/O in the MCP server")
        print("3. Verify stdio streams are properly configured")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_mcp_communication())
