"""Minimal MCP server to test JSON-RPC communication."""
import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import Tool

# Create minimal server
app = Server("test-server")

@app.list_tools()
async def list_tools():
    """List available tools."""
    return [
        Tool(
            name="echo",
            description="Echo a message",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string"}
                },
                "required": ["message"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    """Handle tool calls."""
    if name == "echo":
        return [{"type": "text", "text": f"Echo: {arguments['message']}"}]
    return [{"type": "text", "text": "Unknown tool"}]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
