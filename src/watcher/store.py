"""SQLite durum deposu.

GitHub Actions'ta kalici disk yok; bu dosya her kosu sonunda repoya
commit'leniyor (bkz. .github/workflows/watch.yml). Bu yuzden dosyanin
kucuk kalmasi ve semanin geriye donuk uyumlu olmasi onemli.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone

from .dedupe import ListingGroup
from .score import Evaluation

VALID_STATUSES = {"new", "notified", "contacted", "replied", "viewing", "rejected", "dead"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    fingerprint   TEXT PRIMARY KEY,
    source        TEXT NOT NULL,
    source_id     TEXT NOT NULL,
    url           TEXT NOT NULL,
    all_urls      TEXT NOT NULL,
    title         TEXT,
    price_eur     INTEGER NOT NULL,
    m2            INTEGER,
    municipality  TEXT,
    published_at  TEXT,
    first_seen_at TEXT NOT NULL,
    score         INTEGER NOT NULL,
    commute_min   INTEGER,
    flags         TEXT
);

CREATE TABLE IF NOT EXISTS outreach (
    fingerprint TEXT PRIMARY KEY,
    status      TEXT NOT NULL DEFAULT 'new',
    updated_at  TEXT NOT NULL,
    note        TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: str):
        self.path = path
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def init_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(_SCHEMA)

    def is_first_run(self) -> bool:
        """Ilk kosuda gecmis ilanlarla telefonu bombalamamak icin sessiz mod tetiklenir."""
        return self.count() == 0

    def count(self) -> int:
        with self._connect() as connection:
            return connection.execute("SELECT COUNT(*) FROM listings").fetchone()[0]

    def is_known(self, fingerprint: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM listings WHERE fingerprint = ?", (fingerprint,)
            ).fetchone()
        return row is not None

    def record(self, group: ListingGroup, evaluation: Evaluation) -> None:
        listing = group.primary
        now = _now()
        with self._connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO listings
                   (fingerprint, source, source_id, url, all_urls, title, price_eur,
                    m2, municipality, published_at, first_seen_at, score, commute_min, flags)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    listing.fingerprint, listing.source, listing.source_id, listing.url,
                    json.dumps(group.all_urls), listing.title, listing.price_eur,
                    listing.m2, listing.municipality, listing.published_at.isoformat(),
                    now, evaluation.score, evaluation.commute_minutes,
                    json.dumps(evaluation.flags),
                ),
            )
            connection.execute(
                "INSERT OR IGNORE INTO outreach (fingerprint, status, updated_at) VALUES (?,?,?)",
                (listing.fingerprint, "new", now),
            )

    def get_all_urls(self, fingerprint: str) -> list[str]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT all_urls FROM listings WHERE fingerprint = ?", (fingerprint,)
            ).fetchone()
        return json.loads(row["all_urls"]) if row else []

    def get_status(self, fingerprint: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status FROM outreach WHERE fingerprint = ?", (fingerprint,)
            ).fetchone()
        return row["status"] if row else None

    def set_status(self, fingerprint: str, status: str) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"gecersiz durum: {status}")
        with self._connect() as connection:
            connection.execute(
                "UPDATE outreach SET status = ?, updated_at = ? WHERE fingerprint = ?",
                (status, _now(), fingerprint),
            )

    def mark_notified(self, fingerprint: str) -> None:
        self.set_status(fingerprint, "notified")
