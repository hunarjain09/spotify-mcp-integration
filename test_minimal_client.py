"""Test client for minimal MCP server."""
import asyncio
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test():
    server_params = StdioServerParameters(
        command="python3",
        args=["test_minimal_mcp_server.py"]
    )
    
    print("1. Starting minimal MCP server...")
    async with stdio_client(server_params) as (read_stream, write_stream):
        print("2. Creating session...")
        session = ClientSession(read_stream, write_stream)
        
        print("3. Initializing session...")
        await asyncio.wait_for(session.initialize(), timeout=5.0)
        print("   ✓ Session initialized!")
        
        print("4. Calling echo tool...")
        result = await session.call_tool("echo", {"message": "Hello MCP!"})
        print(f"   ✓ Result: {result.content[0].text}")
        
        print("\n✅ Minimal MCP server works!")

asyncio.run(test())
