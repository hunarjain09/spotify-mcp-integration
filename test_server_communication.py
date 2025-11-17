"""Test server process and communication directly."""
import subprocess
import json
import sys

# Start the server
print("Starting server...", file=sys.stderr)
proc = subprocess.Popen(
    ["python3", "test_minimal_mcp_server.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=0
)

# Send an initialize request
init_request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {
            "name": "test-client",
            "version": "1.0.0"
        }
    }
}

print(f"Sending: {init_request}", file=sys.stderr)
proc.stdin.write(json.dumps(init_request) + "\n")
proc.stdin.flush()

print("Waiting for response...", file=sys.stderr)
import select
import time

# Wait up to 2 seconds for output
timeout = 2
start = time.time()
while time.time() - start < timeout:
    # Check if there's any output on stdout
    if proc.stdout in select.select([proc.stdout], [], [], 0.1)[0]:
        line = proc.stdout.readline()
        if line:
            print(f"Received: {line}", file=sys.stderr)
            break

    # Check if there's any error output
    if proc.stderr in select.select([proc.stderr], [], [], 0.1)[0]:
        err_line = proc.stderr.readline()
        if err_line:
            print(f"Server stderr: {err_line.strip()}", file=sys.stderr)

    # Check if process died
    if proc.poll() is not None:
        print(f"Server exited with code {proc.returncode}", file=sys.stderr)
        remaining_out = proc.stdout.read()
        remaining_err = proc.stderr.read()
        if remaining_out:
            print(f"Remaining stdout: {remaining_out}", file=sys.stderr)
        if remaining_err:
            print(f"Remaining stderr: {remaining_err}", file=sys.stderr)
        break
else:
    print("Timeout - no response from server", file=sys.stderr)

proc.terminate()
proc.wait()
