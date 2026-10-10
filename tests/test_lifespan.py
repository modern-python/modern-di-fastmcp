import fastmcp
from modern_di import Container

from modern_di_fastmcp import setup_di
from tests.test_fastmcp_di import prefix


async def test_root_container_opens_and_closes_with_the_server(mcp: fastmcp.FastMCP, container: Container) -> None:
    container.close_sync()
    assert container.closed

    async with fastmcp.Client(mcp):
        assert not container.closed
    assert container.closed

    async with fastmcp.Client(mcp):
        assert not container.closed
    assert container.closed


async def test_manage_lifespan_false_leaves_the_root_alone(container: Container) -> None:
    server = fastmcp.FastMCP("shared")
    setup_di(server, container, manage_lifespan=False)
    server.tool(prefix)

    async with container:
        async with fastmcp.Client(server) as client:
            result = await client.call_tool("prefix", {})
        assert not container.closed

    assert result.data == "hello"


async def test_two_servers_share_one_container_when_one_owns_its_lifespan(container: Container) -> None:
    owner = fastmcp.FastMCP("owner")
    guest = fastmcp.FastMCP("guest")
    setup_di(owner, container)
    setup_di(guest, container, manage_lifespan=False)
    owner.tool(prefix)
    guest.tool(prefix)

    async with fastmcp.Client(owner) as owner_client:
        async with fastmcp.Client(guest) as guest_client:
            from_guest = await guest_client.call_tool("prefix", {})
        assert not container.closed
        from_owner = await owner_client.call_tool("prefix", {})

    assert (from_guest.data, from_owner.data) == ("hello", "hello")
    assert container.closed
