"""Database bootstrap: engine + session factory."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from mars.storage.orm import Base


class Database:
    """Owns the SQLAlchemy engine and creates the schema on first use.

    ``url`` defaults to a local SQLite file. Pass ``"sqlite:///:memory:"`` for
    ephemeral stores (tests).
    """

    def __init__(self, url: str = "sqlite:///mars.db") -> None:
        if url.startswith("sqlite:///") and ":memory:" not in url:
            path = Path(url.removeprefix("sqlite:///"))
            if path.parent and not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
        self.url = url
        self.engine = create_engine(url, future=True)
        self._session_factory = sessionmaker(bind=self.engine, future=True)
        Base.metadata.create_all(self.engine)

    def session(self) -> Session:
        return self._session_factory()
