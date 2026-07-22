"""Database package with lazy runtime engine/session imports.

Keeping engine construction lazy allows metadata, migrations, and isolated repository
tests to load without opening or configuring a PostgreSQL driver eagerly.
"""
from trading_ai.database.base import Base

__all__ = ["Base", "engine", "SessionLocal", "get_session"]


def __getattr__(name: str):
    if name == "engine":
        from trading_ai.database.engine import engine
        return engine
    if name in {"SessionLocal", "get_session"}:
        from trading_ai.database.session import SessionLocal, get_session
        return {"SessionLocal": SessionLocal, "get_session": get_session}[name]
    raise AttributeError(name)
