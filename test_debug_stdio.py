"""Debug stdio communication to see what's happening."""
import asyncio
import sys
import anyio
from anyio.streams.text import TextReceiveStream
from mcp import StdioServerParameters

async def test():
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["test_minimal_mcp_server.py"]
    )

    print("Starting process...", file=sys.stderr)

    # Start the process directly
    process = await anyio.open_process(
        [server_params.command, *server_params.args],
        stderr=sys.stderr
    )

    print(f"Process started with PID: {process.pid}", file=sys.stderr)

    # Send initialize message
    init_msg = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}\n'
    print(f"Sending: {init_msg.strip()}", file=sys.stderr)

    await process.stdin.send(init_msg.encode())

    # Try to read response with timeout
    print("Waiting for response...", file=sys.stderr)

    try:
        async with anyio.fail_after(2):
            assert process.stdout is not None
            chunk = await process.stdout.receive(1024)
            response = chunk.decode()
            print(f"Received: {response}", file=sys.stderr)
    except TimeoutError:
        print("TIMEOUT - No response from server!", file=sys.stderr)
        print(f"Process still running: {process.returncode is None}", file=sys.stderr)

        # Check if process crashed
        if process.returncode is not None:
            print(f"Process exited with code: {process.returncode}", file=sys.stderr)

    # Clean up
    process.terminate()
    await process.wait()

if __name__ == "__main__":
    asyncio.run(test())
