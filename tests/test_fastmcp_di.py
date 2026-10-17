import contextlib
import typing

import fastmcp
import pytest
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from modern_di import Container

from modern_di_fastmcp import FromDI, fetch_di_container, setup_di
from tests.dependencies import FINALIZED, Dependencies, Session, Settings


if typing.TYPE_CHECKING:
    from tests.dependencies import Settings as TypeCheckingOnlySettings


def greet(name: str, settings: Settings = FromDI(Settings)) -> str:
    return f"{settings.prefix} {name}"


def prefix(settings: Settings = FromDI(Settings)) -> str:
    return settings.prefix


def wrong(settings: typing.Annotated[Settings, FromDI(Settings)]) -> str:
    return settings.prefix


def late_annotation(settings: "TypeCheckingOnlySettings" = FromDI(Settings)) -> str:
    return settings.prefix


async def test_tool_resolves_from_di_and_keeps_injected_parameters_out_of_the_schema(mcp: fastmcp.FastMCP) -> None:
    mcp.tool(greet)

    async with fastmcp.Client(mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}
        result = await client.call_tool("greet", {"name": "world"})

    assert sorted(tools["greet"].input_schema["properties"]) == ["name"]
    assert result.data == "hello world"


async def test_client_cannot_supply_an_injected_parameter(mcp: fastmcp.FastMCP) -> None:
    mcp.tool(greet)

    async with fastmcp.Client(mcp) as client:
        with pytest.raises(ToolError, match="Unexpected keyword argument"):
            await client.call_tool("greet", {"name": "world", "settings": {"prefix": "x"}})


async def test_one_request_container_per_call_and_its_finalizers_run(mcp: fastmcp.FastMCP) -> None:
    seen: list[tuple[int, int]] = []

    @mcp.tool
    async def pair(
        first: Session = FromDI(Dependencies.session),
        second: Session = FromDI(Session),
    ) -> bool:
        seen.append((id(first), id(second)))
        return first is second

    async with fastmcp.Client(mcp) as client:
        first_call = await client.call_tool("pair", {})
        second_call = await client.call_tool("pair", {})

    assert first_call.data is True
    assert second_call.data is True
    assert seen[0][0] != seen[1][0]
    assert [f"session:{seen[0][0]}", f"session:{seen[1][0]}"] == FINALIZED


async def test_fastmcp_context_is_resolvable(mcp: fastmcp.FastMCP) -> None:
    @mcp.tool
    async def request_id(session: Session = FromDI(Session)) -> bool:
        return isinstance(session.context, fastmcp.Context)

    async with fastmcp.Client(mcp) as client:
        result = await client.call_tool("request_id", {})

    assert result.data is True


async def test_sync_tool_resolves_before_running_in_a_thread(mcp: fastmcp.FastMCP) -> None:
    @mcp.tool
    def sync_tool(session: Session = FromDI(Session)) -> str:
        return session.settings.prefix

    async with fastmcp.Client(mcp) as client:
        result = await client.call_tool("sync_tool", {})

    assert result.data == "hello"
    assert len(FINALIZED) == 1


async def test_resources_templates_and_prompts_resolve(mcp: fastmcp.FastMCP) -> None:
    @mcp.resource("settings://prefix")
    def prefix(settings: Settings = FromDI(Settings)) -> str:
        return settings.prefix

    @mcp.resource("greeting://{name}")
    def greeting(name: str, settings: Settings = FromDI(Settings)) -> str:
        return f"{settings.prefix} {name}"

    @mcp.prompt
    def ask(topic: str, settings: Settings = FromDI(Settings)) -> str:
        return f"{settings.prefix}, tell me about {topic}"

    async with fastmcp.Client(mcp) as client:
        resource = await client.read_resource("settings://prefix")
        template = await client.read_resource("greeting://world")
        prompt = await client.get_prompt("ask", {"topic": "scopes"})
        prompts = {p.name: p for p in await client.list_prompts()}

    assert resource[0].text == "hello"
    assert template[0].text == "hello world"
    assert "hello, tell me about scopes" in prompt.messages[0].content.text
    assert [argument.name for argument in prompts["ask"].arguments or []] == ["topic"]


async def test_tool_of_a_mounted_server_resolves_through_the_parent(mcp: fastmcp.FastMCP) -> None:
    child = fastmcp.FastMCP("child")

    @child.tool
    def child_tool(settings: Settings = FromDI(Settings)) -> str:
        return settings.prefix

    mcp.mount(child, namespace="child")

    async with fastmcp.Client(mcp) as client:
        result = await client.call_tool("child_child_tool", {})

    assert result.data == "hello"


def test_setup_di_returns_the_container_and_fetch_reads_it_back(container: Container) -> None:
    server = fastmcp.FastMCP("fetch")
    assert setup_di(server, container) is container
    assert fetch_di_container(server) is container


def test_fetch_di_container_raises_without_setup_di() -> None:
    with pytest.raises(RuntimeError, match="setup_di"):
        fetch_di_container(fastmcp.FastMCP("bare"))


async def test_from_di_without_a_request_container_names_setup_di() -> None:
    server = fastmcp.FastMCP("no-di")

    server.tool(prefix)

    async with fastmcp.Client(server) as client:
        with pytest.raises(ToolError, match="setup_di"):
            await client.call_tool("prefix", {})


async def test_from_di_in_annotated_fails_at_startup_naming_the_tool(mcp: fastmcp.FastMCP) -> None:
    mcp.tool(wrong)

    async with contextlib.AsyncExitStack() as stack:
        with pytest.raises(RuntimeError, match=r"wrong: FromDI on parameter 'settings' is inside Annotated") as exc:
            await stack.enter_async_context(fastmcp.Client(mcp))

    assert isinstance(exc.value.__cause__, TypeError)


async def test_startup_check_does_not_see_a_mounted_server_s_components(mcp: fastmcp.FastMCP) -> None:
    child = fastmcp.FastMCP("child")

    child.tool(wrong)
    mcp.mount(child, namespace="child")

    async with fastmcp.Client(mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}
        result = await client.call_tool("child_wrong", {"settings": {"prefix": "from-client"}})

    assert "settings" in tools["child_wrong"].input_schema["properties"]
    assert result.data == "from-client"


async def test_startup_check_tolerates_an_annotation_it_cannot_resolve(mcp: fastmcp.FastMCP) -> None:
    mcp.tool(late_annotation)

    async with fastmcp.Client(mcp) as client:
        result = await client.call_tool("late_annotation", {})

    assert result.data == "hello"


class _RecordClientPresence(Middleware):
    def __init__(self) -> None:
        self.has_client: list[bool] = []

    async def on_request(
        self, context: MiddlewareContext[typing.Any], call_next: CallNext[typing.Any, typing.Any]
    ) -> typing.Any:  # noqa: ANN401
        connection = context.fastmcp_context
        self.has_client.append(connection is not None and connection.request_context is not None)
        return await call_next(context)


async def test_startup_check_does_not_run_the_server_s_middleware(mcp: fastmcp.FastMCP) -> None:
    middleware = _RecordClientPresence()
    mcp.add_middleware(middleware)
    mcp.tool(prefix)

    async with fastmcp.Client(mcp) as client:
        result = await client.call_tool("prefix", {})

    assert result.data == "hello"
    assert middleware.has_client
    assert all(middleware.has_client)


def test_setup_di_twice_on_one_server_raises(container: Container) -> None:
    server = fastmcp.FastMCP("twice")
    setup_di(server, container)
    with pytest.raises(RuntimeError, match="already"):
        setup_di(server, container)


async def test_override_applies_inside_a_tool(mcp: fastmcp.FastMCP, container: Container) -> None:
    mcp.tool(prefix)

    with container.override(Dependencies.settings, Settings(prefix="overridden")):
        async with fastmcp.Client(mcp) as client:
            result = await client.call_tool("prefix", {})

    assert result.data == "overridden"
