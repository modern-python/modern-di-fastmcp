# `FromDI` is a parameter default, checked at startup

The other modern-di integrations mark an injected parameter with `Annotated[T, FromDI(...)]`. Here
`FromDI` must be the parameter's default value, `svc: T = FromDI(T)`, as with FastAPI's `Depends`.
FastMCP builds each tool, resource and prompt schema with `without_injected_parameters`, which drops
a parameter only when its default is a `Dependency`. A `Dependency` in `Annotated` metadata stays in
the schema: the client is asked for the value, and FastMCP's own resolver never reads that metadata,
so the parameter gets whatever the client sends. `FromDI` is therefore a `Dependency` subclass used
as a default, the form FastMCP strips and resolves itself. It resolves before FastMCP moves a sync
function to a worker thread, so the request container, held in a `ContextVar`, is still visible.

The `Annotated` form has to be rejected somewhere, and nothing in this package runs when
`@mcp.tool` decorates a function. The earliest point the package controls is its lifespan
provider, so `setup_di`'s lifespan lists the server's tools, resources, resource templates and
prompts and raises `TypeError` naming each misused parameter before the first request. A mounted
server's components are listed as proxies without the original function, and a component added
after startup is never listed, so neither is checked; the docs describe both cases.
