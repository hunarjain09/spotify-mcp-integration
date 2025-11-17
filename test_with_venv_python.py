"""Test using the virtual environment Python for both client and server."""
import asyncio
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test():
    # Use the same Python interpreter that's running this script
    python_path = sys.executable

    server_params = StdioServerParameters(
        command=python_path,  # Use the same Python as the client
        args=["test_minimal_mcp_server.py"],
        env=None  # Inherit environment
    )

    print(f"1. Using Python: {python_path}", file=sys.stderr)
    print("2. Starting minimal MCP server...", file=sys.stderr)

    async with stdio_client(server_params) as (read_stream, write_stream):
        print("3. Creating session...", file=sys.stderr)
        session = ClientSession(read_stream, write_stream)

        print("4. Initializing session...", file=sys.stderr)
        await asyncio.wait_for(session.initialize(), timeout=5.0)
        print("   ✓ Session initialized!", file=sys.stderr)

        print("5. Calling echo tool...", file=sys.stderr)
        result = await session.call_tool("echo", {"message": "Hello MCP!"})
        print(f"   ✓ Result: {result.content[0].text}", file=sys.stderr)

        print("\n✅ Minimal MCP server works!", file=sys.stderr)

if __name__ == "__main__":
    asyncio.run(test())
