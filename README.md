[![PyPI version](https://img.shields.io/pypi/v/modern-di-fastmcp.svg)](https://pypi.org/project/modern-di-fastmcp/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/modern-di-fastmcp.svg)](https://pypi.org/project/modern-di-fastmcp/)
[![Downloads](https://static.pepy.tech/badge/modern-di-fastmcp/month)](https://pepy.tech/projects/modern-di-fastmcp)
[![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen.svg)](https://github.com/modern-python/modern-di-fastmcp/actions/workflows/ci.yml)
[![CI](https://github.com/modern-python/modern-di-fastmcp/actions/workflows/ci.yml/badge.svg)](https://github.com/modern-python/modern-di-fastmcp/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/modern-python/modern-di-fastmcp.svg)](https://github.com/modern-python/modern-di-fastmcp/blob/main/LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/modern-python/modern-di-fastmcp)](https://github.com/modern-python/modern-di-fastmcp/stargazers)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)

[modern-di](https://github.com/modern-python/modern-di) integration for [FastMCP](https://gofastmcp.com).

Full guide: [FastMCP integration docs](https://modern-di.modern-python.org/integrations/fastmcp/)

Usage example: [examples/](https://github.com/modern-python/modern-di-fastmcp/tree/main/examples)

## Installation

```bash
uv add modern-di-fastmcp      # or: pip install modern-di-fastmcp
```

## Usage

`setup_di` attaches the root container to the server and adds a middleware that builds a request container for every MCP request. `FromDI`, used as a parameter's default value, resolves a provider (or type) from it and keeps the parameter out of the tool schema.

```python
import dataclasses

import fastmcp
from modern_di import Container, Group, Scope, providers
from modern_di_fastmcp import FromDI, setup_di


@dataclasses.dataclass(kw_only=True)
class Settings:
    greeting: str = "Hello"


@dataclasses.dataclass(kw_only=True)
class GreetingService:
    settings: Settings  # auto-injected by type


class Dependencies(Group):
    settings = providers.Factory(scope=Scope.APP, creator=Settings)
    service = providers.Factory(scope=Scope.REQUEST, creator=GreetingService)


mcp = fastmcp.FastMCP("greeter")
container = Container(groups=[Dependencies])
setup_di(mcp, container)
container.validate()  # optional fail-fast; must come after setup_di registers its providers


@mcp.tool
def greet(name: str, service: GreetingService = FromDI(Dependencies.service)) -> str:  # noqa: B008
    return f"{service.settings.greeting}, {name}!"
```

`FromDI` must be the default value, not `Annotated` metadata: FastMCP keeps an `Annotated` parameter in the schema and asks the client for it. When the parameter's type has no schema, as with a plain class, FastMCP itself refuses the tool when it is defined. When it has one, as with a dataclass, the server raises `TypeError` at startup naming the parameter. The check covers the server's own tools, resources and prompts, not those of a mounted server or ones added after startup.

To stop ruff's B008 from flagging every `FromDI` default, add it to your ruff config:

```toml
[tool.ruff.lint.flake8-bugbear]
extend-immutable-calls = ["modern_di_fastmcp.FromDI"]
```

The current `fastmcp.Context` is resolvable within DI via the pre-built `fastmcp_context_provider` context provider.

### Shutdown order

`setup_di` closes the root container from a provider lifespan it adds to the server. Providers added after `setup_di` tear down before the close and can still resolve from the container. These run after the close and get `ContainerClosedError`:

- the teardown of `FastMCP(lifespan=...)`
- the teardown of providers added before `setup_di`

For these, pass `manage_lifespan=False` and open and close the container in your own server lifespan:

```python
import collections.abc
import contextlib


@contextlib.asynccontextmanager
async def lifespan(server: fastmcp.FastMCP) -> collections.abc.AsyncIterator[None]:
    async with container:
        yield
        ...  # shutdown code that still needs the container


mcp = fastmcp.FastMCP("greeter", lifespan=lifespan)
container = Container(groups=[Dependencies])
setup_di(mcp, container, manage_lifespan=False)
```

## API

| Symbol | Description |
|---|---|
| `setup_di(server, container, *, manage_lifespan=True)` | Attaches the container to the server and adds the DI middleware. The server's lifespan opens the container at startup and closes it with `close_async()` at shutdown. When the server is mounted in another app whose lifespan runs it, let that app own the container and pass `manage_lifespan=False` here (see [Sharing a container with FastAPI](https://modern-di.modern-python.org/integrations/fastmcp/#sharing-a-container-with-fastapi)). When apps that share a container run with separate lifecycles, pass `manage_lifespan=False` to every `setup_di` and open and close the container yourself with `async with container:`, or the first app to stop closes it for the rest. At startup it raises `TypeError` for a `FromDI` used inside `Annotated`. Raises `RuntimeError` when called a second time for the same server. Returns the container |
| `FromDI(dependency)` | Parameter default that resolves a provider (or type) from the request container. Raises `RuntimeError` naming `setup_di` when no request container is active, including in a background task (`task=True`), which FastMCP runs outside middleware |
| `fetch_di_container(server)` | Returns the root container attached to the server. Raises `RuntimeError` when `setup_di` was not called |
| `fastmcp_context_provider` | `ContextProvider` for the current `fastmcp.Context` (`REQUEST` scope) |

## 📦 [PyPI](https://pypi.org/project/modern-di-fastmcp)

## 📝 [License](https://github.com/modern-python/modern-di-fastmcp/blob/main/LICENSE)

## Part of `modern-python`

Built on [`modern-di`](https://github.com/modern-python/modern-di), a dependency-injection framework with an IoC container and scopes.

Browse the full list of templates and libraries in
[`modern-python`](https://github.com/modern-python); the org profile has the categorized index.
