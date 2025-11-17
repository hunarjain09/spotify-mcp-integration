"""
Demo: Using Claude Agent SDK to interact with Spotify MCP server.

This shows how Claude can intelligently use your Spotify MCP tools through
natural language commands.
"""
import asyncio
import sys
from pathlib import Path
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions


async def main():
    """Demo: Claude interacting with Spotify via MCP."""

    # Configure Claude to use your Spotify MCP server
    options = ClaudeAgentOptions(
        # Point to your Spotify MCP server
        mcp_servers={
            "spotify": {
                "type": "stdio",
                "command": sys.executable,  # Use same Python as this script
                "args": [str(Path(__file__).parent / "mcp_server" / "spotify_server.py")],
            }
        },
        # Allow Claude to use all Spotify tools
        allowed_tools=[
            "mcp__spotify__search_track",
            "mcp__spotify__add_track_to_playlist",
            "mcp__spotify__verify_track_added",
            "mcp__spotify__get_user_playlists",
            "mcp__spotify__search_by_isrc",
        ],
        # Auto-approve tool usage for demo
        permission_mode="bypassPermissions",
        # Use Claude Code's system prompt
        system_prompt={
            "type": "preset",
            "preset": "claude_code"
        }
    )

    print("🎵 Spotify AI Assistant (powered by Claude Agent SDK)")
    print("=" * 60)
    print("Claude can now intelligently use your Spotify MCP tools!")
    print("Try commands like:")
    print("  - 'Search for Never Gonna Give You Up by Rick Astley'")
    print("  - 'Show me my playlists'")
    print("  - 'Find the song Bohemian Rhapsody and add it to my first playlist'")
    print("  - 'exit' to quit")
    print("=" * 60)

    async with ClaudeSDKClient(options=options) as client:
        # Start conversation session
        turn = 0

        while True:
            # Get user input
            user_input = input(f"\n[Turn {turn + 1}] You: ").strip()

            if user_input.lower() in ['exit', 'quit', 'bye']:
                print("\n👋 Goodbye!")
                break

            if not user_input:
                continue

            # Send to Claude
            await client.query(user_input)
            turn += 1

            # Process Claude's response
            print(f"[Turn {turn}] Claude: ", end="", flush=True)

            response_parts = []
            async for message in client.receive_response():
                # Handle different message types
                if hasattr(message, 'content'):
                    for block in message.content:
                        if hasattr(block, 'text'):
                            response_parts.append(block.text)
                            print(block.text, end="", flush=True)
                        elif hasattr(block, 'name'):
                            # Tool use
                            print(f"\n  [Using tool: {block.name}]", flush=True)

                # Check if this is the final result
                if hasattr(message, 'subtype') and message.subtype in ['success', 'error']:
                    print()  # New line after response
                    if message.subtype == 'error':
                        print(f"\n  ⚠️ Error occurred: {getattr(message, 'result', 'Unknown error')}")
                    break


if __name__ == "__main__":
    print("\n🚀 Starting Spotify AI Assistant...")
    print("⏳ Connecting to Spotify MCP server...\n")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user. Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
