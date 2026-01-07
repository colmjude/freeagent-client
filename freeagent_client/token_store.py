"""Token storage abstractions for FreeAgent tokens."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional
import sqlite3


TokenDict = Dict[str, Any]


class TokenStore(ABC):
    """Interface for persisting FreeAgent tokens."""

    @abstractmethod
    def load(self) -> Optional[TokenDict]:
        """Return the stored token set or None if unavailable."""

    @abstractmethod
    def save(self, tokens: TokenDict) -> None:
        """Persist the provided token set."""


class FileTokenStore(TokenStore):
    """Simple JSON file-based token store."""

    def __init__(self, path: str | Path = "freeagent_tokens.json") -> None:
        self.path = Path(path)

    def load(self) -> Optional[TokenDict]:
        if not self.path.exists():
            return None
        with self.path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def save(self, tokens: TokenDict) -> None:
        # Normalize to include expires_at for future validity checks.
        stored = dict(tokens)
        if "expires_in" in stored and "expires_at" not in stored:
            stored["expires_at"] = int(time.time()) + int(stored["expires_in"])
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(stored, f, indent=2)


class SQLiteTokenStore(TokenStore):
    """SQLite-backed token store for quick DB-style persistence."""

    def __init__(self, path: str | Path = "freeagent_tokens.db") -> None:
        self.path = Path(path)
        self._ensure_table()

    def _ensure_table(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS tokens (id INTEGER PRIMARY KEY CHECK (id = 1), data TEXT NOT NULL)"
            )
            conn.commit()

    def load(self) -> Optional[TokenDict]:
        with sqlite3.connect(self.path) as conn:
            cur = conn.execute("SELECT data FROM tokens WHERE id = 1")
            row = cur.fetchone()
            if not row:
                return None
            return json.loads(row[0])

    def save(self, tokens: TokenDict) -> None:
        stored = dict(tokens)
        if "expires_in" in stored and "expires_at" not in stored:
            stored["expires_at"] = int(time.time()) + int(stored["expires_in"])
        payload = json.dumps(stored)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT INTO tokens (id, data) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                (payload,),
            )
            conn.commit()
