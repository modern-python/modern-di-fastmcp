import dataclasses

import fastmcp
from modern_di import Group, Scope, providers


FINALIZED: list[str] = []


@dataclasses.dataclass(kw_only=True)
class Settings:
    prefix: str = "hello"


@dataclasses.dataclass(kw_only=True)
class Session:
    settings: Settings
    context: fastmcp.Context


def close_session(session: Session) -> None:
    FINALIZED.append(f"session:{id(session)}")


class Dependencies(Group):
    settings = providers.Factory(scope=Scope.APP, creator=Settings, cache=True)
    session = providers.Factory(
        scope=Scope.REQUEST, creator=Session, cache=providers.CacheSettings(finalizer=close_session)
    )
