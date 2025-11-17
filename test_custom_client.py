"""Custom MCP client that bypasses the buggy stdio_client."""
import asyncio
import json
import sys
from typing import Any, Dict

async def main():
    # Start the server process
    print("Starting server...", file=sys.stderr)
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "test_minimal_mcp_server.py",
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
        print(f"Sending: {request}", file=sys.stderr)
        proc.stdin.write(request_line.encode())
        await proc.stdin.drain()

        # Read response
        response_line = await proc.stdout.readline()
        if not response_line:
            raise Exception("Server closed connection")

        response = json.loads(response_line.decode())
        print(f"Received: {response}", file=sys.stderr)

        if "error" in response:
            raise Exception(f"RPC Error: {response['error']}")

        return response.get("result")

    try:
        # Initialize
        print("\n1. Initializing session...", file=sys.stderr)
        init_result = await send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "custom-test-client", "version": "1.0.0"},
            },
        )
        print(f"   ✓ Initialized: {init_result['serverInfo']['name']}", file=sys.stderr)

        # Send initialized notification
        notification = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        proc.stdin.write((json.dumps(notification) + "\n").encode())
        await proc.stdin.drain()

        # List tools
        print("\n2. Listing tools...", file=sys.stderr)
        tools_result = await send_request("tools/list")
        print(f"   ✓ Found {len(tools_result['tools'])} tools", file=sys.stderr)
        for tool in tools_result["tools"]:
            print(f"     - {tool['name']}: {tool['description']}", file=sys.stderr)

        # Call echo tool
        print("\n3. Calling echo tool...", file=sys.stderr)
        call_result = await send_request(
            "tools/call",
            {"name": "echo", "arguments": {"message": "Hello from custom client!"}},
        )
        print(f"   ✓ Result: {call_result['content'][0]['text']}", file=sys.stderr)

        print("\n✅ Custom client works!", file=sys.stderr)

    finally:
        # Clean up
        proc.stdin.close()
        await proc.wait()

if __name__ == "__main__":
    asyncio.run(main())
