import logging

import anyio
import fastmcp
import pytest
from modern_di import Container, Group, Scope, providers

from modern_di_fastmcp import FromDI, main, setup_di


class _First: ...


class _Second: ...


class _SetOnRecord(logging.Handler):
    def __init__(self, event: anyio.Event) -> None:
        super().__init__()
        self.event = event

    def emit(self, record: logging.LogRecord) -> None:  # noqa: ARG002
        self.event.set()


def _server(log: list[str], *, second_finalizer_delay: float, done: anyio.Event | None = None) -> fastmcp.FastMCP:
    async def finalize_first(_: _First) -> None:
        await anyio.sleep(0.01)
        log.append("first")
        if done is not None:
            done.set()

    async def finalize_second(_: _Second) -> None:
        await anyio.sleep(second_finalizer_delay)
        log.append("second")

    class G(Group):
        first = providers.Factory(
            scope=Scope.REQUEST, creator=_First, cache=providers.CacheSettings(finalizer=finalize_first)
        )
        second = providers.Factory(
            scope=Scope.REQUEST, creator=_Second, cache=providers.CacheSettings(finalizer=finalize_second)
        )

    server = fastmcp.FastMCP("test")
    setup_di(server, Container(groups=[G]))

    @server.tool
    async def slow(first: _First = FromDI(_First), second: _Second = FromDI(_Second)) -> None:
        assert isinstance(first, _First)
        assert isinstance(second, _Second)
        await anyio.sleep_forever()

    return server


async def _abandon_a_running_call(server: fastmcp.FastMCP, *, done: anyio.Event) -> None:
    async with fastmcp.Client(server) as client:

        async def call() -> None:
            with anyio.move_on_after(0.05):
                await client.call_tool("slow", {})

        # Its own task keeps the cancellation out of the test's frame, where 3.11 coverage loses a line.
        async with anyio.create_task_group() as task_group:
            task_group.start_soon(call)
        with anyio.fail_after(2):
            await done.wait()


async def test_an_abandoned_call_still_runs_every_request_finalizer() -> None:
    log: list[str] = []
    done = anyio.Event()

    await _abandon_a_running_call(_server(log, second_finalizer_delay=0.01, done=done), done=done)

    assert log == ["second", "first"]


async def test_a_hung_request_finalizer_is_abandoned_after_the_bound(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(main, "_CHILD_CLOSE_TIMEOUT", 0.05)
    caplog.set_level(logging.WARNING, logger=main.__name__)
    warned = anyio.Event()
    monkeypatch.setattr(main._logger, "handlers", [_SetOnRecord(warned)])  # noqa: SLF001
    log: list[str] = []

    await _abandon_a_running_call(_server(log, second_finalizer_delay=10), done=warned)

    assert log == []
    assert [record.getMessage() for record in caplog.records] == [
        "Closing the request container did not finish within 0.05 s; its remaining finalizers did not run"
    ]
