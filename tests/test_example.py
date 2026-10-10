import fastmcp

from examples.app import mcp


async def test_example_resolves_and_greets() -> None:
    async with fastmcp.Client(mcp) as client:
        result = await client.call_tool("greet", {"name": "world"})
    assert result.data == "Hello, world!"
