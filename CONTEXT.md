# modern-di-fastmcp

A FastMCP adapter over [`modern-di`](https://github.com/modern-python/modern-di): it attaches a
container to a FastMCP server, opens a child container for every MCP request in a middleware, and
resolves every tool, resource and prompt parameter whose default is `FromDI` from that child.

## Language

A term is listed only when there is a synonym to reject, or a meaning subtle enough that code and
docs must agree on it. General programming vocabulary does not belong here, however heavily this
package uses it.

The domain terms are `modern-di`'s: `Container`, `Provider`, `Group`, `Scope`, `Resolution`,
`Override`. That project's `CONTEXT.md` is the authority for all of them; nothing here redefines
one. FastMCP owns `server`, `tool`, `resource`, `prompt`, `middleware` and `Context`, and this
package uses each in FastMCP's sense. The three below are this package's own.

**Root container**:
The `Container` handed to `setup_di`; `fetch_di_container` reads it back. By default it opens when
the server's lifespan starts and closes when it ends. With `manage_lifespan=False` another
application owns that lifetime.
_Avoid_: app container, server container.

**Request container**:
The child container the middleware builds for one MCP request and closes when the request is done.
It is where a `FromDI` parameter resolves.
_Avoid_: call container, session container. A session spans many requests and has no close hook, so
nothing here is scoped to it.

**Request**:
One MCP request from a client: a tool call, a resource read, a prompt render, or a list call.
Notifications are not requests. Its `fastmcp.Context` is the `Connection` in modern-di's sense,
which is why `fastmcp_context_provider` is a `ContextProvider` at `Scope.REQUEST`.
