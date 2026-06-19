"""Persistence for Mars (SQLAlchemy + SQLite, repository pattern).

The engine and CLI depend on :class:`~mars.storage.repository.Repository`, never
on SQLAlchemy directly, so the backing store can change without touching callers.
"""

from mars.storage.db import Database
from mars.storage.repository import Repository

__all__ = ["Database", "Repository"]
