"""Debug MCP communication with detailed logging."""
import asyncio
import logging
from mcp_client.client import SpotifyMCPClient

# Enable debug logging for MCP
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test():
    client = SpotifyMCPClient()
    
    try:
        print("\n1. Connecting to MCP server...")
        
        # Manually step through the connection process
        from mcp.client.stdio import stdio_client
        from mcp import ClientSession
        
        print("2. Creating stdio_client...")
        client._stdio_context = stdio_client(client.server_params)
        
        print("3. Entering stdio context (starting subprocess)...")
        client.read_stream, client.write_stream = await client._stdio_context.__aenter__()
        print("   ✓ Subprocess started")
        
        print("4. Creating ClientSession...")
        client.session = ClientSession(client.read_stream, client.write_stream)
        print("   ✓ Session created")
        
        print("5. Initializing session (JSON-RPC handshake)...")
        await asyncio.wait_for(client.session.initialize(), timeout=10.0)
        print("   ✓ Session initialized")
        
        print("\n6. Calling search_track tool...")
        result = await asyncio.wait_for(
            client.call_tool("search_track", {"query": "Imagine John Lennon", "limit": 3}),
            timeout=10.0
        )
        print(f"   ✓ Got result: {len(result.get('tracks', []))} tracks")
        
        await client.close()
        print("\n✅ Success!")
        
    except asyncio.TimeoutError as e:
        print(f"\n❌ Timeout at step: {e}")
        print("The MCP server is not responding to JSON-RPC messages")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test())
