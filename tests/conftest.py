import typing

import fastmcp
import pytest
from modern_di import Container

from modern_di_fastmcp import setup_di
from tests.dependencies import FINALIZED, Dependencies


@pytest.fixture(autouse=True)
def _clear_finalized() -> typing.Iterator[None]:
    FINALIZED.clear()
    yield
    FINALIZED.clear()


@pytest.fixture
def container() -> Container:
    return Container(groups=[Dependencies])


@pytest.fixture
def mcp(container: Container) -> fastmcp.FastMCP:
    server = fastmcp.FastMCP("test")
    setup_di(server, container)
    return server
