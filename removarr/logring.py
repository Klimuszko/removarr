from __future__ import annotations
from dataclasses import dataclass
from collections import deque
from typing import Deque, List, Dict, Any
import time

@dataclass
class LogItem:
    ts: float
    source: str
    title: str
    year: int | None
    tmdb_id: int | None
    tvdb_id: int | None
    removed: int
    scanned_accounts: int
    details: list[str]

class LogRing:
    def __init__(self, maxlen: int = 200):
        self._d: Deque[LogItem] = deque(maxlen=maxlen)

    def add(self, item: LogItem) -> None:
        self._d.appendleft(item)

    def list(self) -> list[dict]:
        out: list[dict] = []
        for x in list(self._d):
            out.append({
                "ts": x.ts,
                "source": x.source,
                "title": x.title,
                "year": x.year,
                "tmdb_id": x.tmdb_id,
                "tvdb_id": x.tvdb_id,
                "removed": x.removed,
                "scanned_accounts": x.scanned_accounts,
                "details": x.details,
            })
        return out
