import collections.abc
import contextlib
import contextvars
import typing
import weakref

import fastmcp
from fastmcp.dependencies import Dependency
from fastmcp.exceptions import FastMCPError
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.server.providers import Provider
from modern_di import Container, Scope, integrations, providers


T_co = typing.TypeVar("T_co", covariant=True)


fastmcp_context_provider = providers.ContextProvider(scope=Scope.REQUEST, context_type=fastmcp.Context)

_request_container: contextvars.ContextVar[Container | None] = contextvars.ContextVar(
    "modern_di_fastmcp_request_container", default=None
)
_root_containers: "weakref.WeakKeyDictionary[fastmcp.FastMCP, Container]" = weakref.WeakKeyDictionary()

_MISSING_REQUEST_CONTAINER = (
    "No request container for this call, so the DI middleware did not run for it. "
    "Call setup_di(server, container) on the server that clients connect to. "
    "A background task (task=True) runs outside middleware and cannot use FromDI."
)
_MISSING_ROOT_CONTAINER = "No container is attached to this server. Call setup_di(server, container) first."
_ALREADY_SET_UP = "setup_di was already called for this server; call it once per server."


def _annotated_misuse(parameter: str) -> str:
    return (
        f"FromDI on parameter {parameter!r} is inside Annotated, where FastMCP keeps the parameter in the "
        f"schema. Make FromDI the parameter's default value instead: `{parameter}: T = FromDI(T)`."
    )


class _NoRequestContainerError(FastMCPError, RuntimeError):
    """A `FastMCPError`, so FastMCP passes the message to the client instead of masking it."""


class _FromDI(Dependency[T_co]):
    def __init__(self, marker: integrations.Marker[T_co]) -> None:
        self.marker = marker

    async def __aenter__(self) -> T_co:
        request_container = _request_container.get()
        if request_container is None:
            raise _NoRequestContainerError(_MISSING_REQUEST_CONTAINER)
        return self.marker.resolve(request_container)


def _annotated_from_di_parameters(fn: typing.Callable[..., typing.Any]) -> list[str]:
    try:
        hints = typing.get_type_hints(fn, include_extras=True)
    except NameError:
        return []
    return [
        name
        for name, hint in hints.items()
        if typing.get_origin(hint) is typing.Annotated
        and any(isinstance(meta, _FromDI) for meta in typing.get_args(hint)[1:])
    ]


async def _check_components(server: fastmcp.FastMCP) -> None:
    """Reject `FromDI` inside `Annotated`; a mounted server's components are proxies with no `fn`."""
    components = [
        *await server.list_tools(),
        *await server.list_resources(),
        *await server.list_resource_templates(),
        *await server.list_prompts(),
    ]
    problems = [
        f"{component.name}: {_annotated_misuse(parameter)}"
        for component in components
        if (fn := getattr(component, "fn", None)) is not None
        for parameter in _annotated_from_di_parameters(fn)
    ]
    if problems:
        raise TypeError("\n".join(problems))


class _LifespanProvider(Provider):
    def __init__(self, server: fastmcp.FastMCP, container: Container, *, manage_lifespan: bool) -> None:
        super().__init__()
        self._server = server
        self._container = container
        self._manage_lifespan = manage_lifespan

    @contextlib.asynccontextmanager
    async def lifespan(self) -> collections.abc.AsyncGenerator[None]:
        await _check_components(self._server)
        if not self._manage_lifespan:
            yield
            return
        async with self._container:
            yield


class _DIMiddleware(Middleware):
    def __init__(self, container: Container) -> None:
        self._container = container

    async def on_request(
        self, context: MiddlewareContext[typing.Any], call_next: CallNext[typing.Any, typing.Any]
    ) -> typing.Any:  # noqa: ANN401
        connection = context.fastmcp_context
        async with self._container.build_child_container(
            scope=Scope.REQUEST,
            context=None if connection is None else integrations.bind(fastmcp_context_provider, connection).context,
        ) as request_container:
            token = _request_container.set(request_container)
            try:
                return await call_next(context)
            finally:
                _request_container.reset(token)


def setup_di(server: fastmcp.FastMCP, container: Container, *, manage_lifespan: bool = True) -> Container:
    if server in _root_containers:
        raise RuntimeError(_ALREADY_SET_UP)
    if container.find_provider(fastmcp.Context) is None:
        container.add_providers(fastmcp_context_provider)
    _root_containers[server] = container
    server.add_provider(_LifespanProvider(server, container, manage_lifespan=manage_lifespan))
    server.add_middleware(_DIMiddleware(container))
    return container


def fetch_di_container(server: fastmcp.FastMCP) -> Container:
    container = _root_containers.get(server)
    if container is None:
        raise RuntimeError(_MISSING_ROOT_CONTAINER)
    return container


def FromDI(dependency: providers.AbstractProvider[T_co] | type[T_co]) -> T_co:  # noqa: N802
    return typing.cast(T_co, _FromDI(integrations.Marker(dependency)))
