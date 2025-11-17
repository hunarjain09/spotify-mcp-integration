"""Debug test to see what's happening with MCP communication."""
import asyncio
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test():
    server_params = StdioServerParameters(
        command="python3",
        args=["test_minimal_mcp_server.py"]
    )

    print("1. Starting minimal MCP server...", file=sys.stderr)
    try:
        async with stdio_client(server_params) as (read_stream, write_stream):
            print("2. Creating session...", file=sys.stderr)
            session = ClientSession(read_stream, write_stream)

            print("3. Initializing session...", file=sys.stderr)

            # Try to read what the server sends
            try:
                result = await asyncio.wait_for(session.initialize(), timeout=5.0)
                print(f"   ✓ Session initialized! Result: {result}", file=sys.stderr)
            except asyncio.TimeoutError:
                print("   ✗ Timeout waiting for initialization", file=sys.stderr)
                raise

            print("4. Calling echo tool...", file=sys.stderr)
            result = await session.call_tool("echo", {"message": "Hello MCP!"})
            print(f"   ✓ Result: {result.content[0].text}", file=sys.stderr)

            print("\n✅ Minimal MCP server works!", file=sys.stderr)
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        raise

if __name__ == "__main__":
    asyncio.run(test())
