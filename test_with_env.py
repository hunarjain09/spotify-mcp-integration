"""Test client with explicit environment variables."""
import asyncio
import os
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test():
    # Pass the current environment to the server
    server_params = StdioServerParameters(
        command=sys.executable,  # Use same Python interpreter
        args=["test_minimal_mcp_server.py"],
        env=dict(os.environ)  # Pass ALL environment variables
    )

    print("1. Starting minimal MCP server with full environment...")
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
