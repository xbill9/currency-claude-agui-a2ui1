import asyncio
import socket
import pytest

from fastmcp import Client


@pytest.mark.asyncio
async def test_server():
    # Check if the MCP server is running; if not, skip the test
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        if s.connect_ex(("localhost", 8080)) != 0:
            pytest.skip("MCP server is not running on port 8080")

    # Test the MCP server using streamable-http transport.
    # Use "/sse" endpoint if using sse transport.
    async with Client("http://localhost:8080/mcp") as client:
        # List available tools
        tools = await client.list_tools()
        for tool in tools:
            print(f"--- 🛠️  Tool found: {tool.name} ---")
        # Call get_exchange_rate tool
        print("--- 🪛  Calling get_exchange_rate tool for USD to EUR ---")
        result = await client.call_tool(
            "get_exchange_rate", {"currency_from": "USD", "currency_to": "EUR"}
        )
        print(f"--- ✅  Success: {result.content[0].text} ---")


if __name__ == "__main__":
    asyncio.run(test_server())
