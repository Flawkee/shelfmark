"""Persisted snapshot of Audiobookshelf library contents for availability matching.

A full-replace snapshot written by the Audiobookshelf sync and read (cheaply)
during metadata search to flag audiobooks already present in the user's library.
"""

from __future__ import annotations

import sqlite3
import threading
from typing import TYPE_CHECKING, Any

from shelfmark.core.logger import setup_logger
from shelfmark.core.text_match import (
    fold_series,
    normalize_author,
    normalize_title,
    parse_volume_title,
    series_key,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

logger = setup_logger(__name__)


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _book_identity(
    isbn_13: object,
    isbn_10: object,
    norm_series_full: object,
    series_index: object,
    norm_title: object,
    norm_author: object,
) -> tuple[Any, ...] | None:
    if isbn_13:
        return ("i13", str(isbn_13))
    if isbn_10:
        return ("i10", str(isbn_10))
    if series_index is not None and norm_series_full:
        return ("vol", str(norm_series_full), float(series_index))
    if norm_title and norm_author:
        return ("ta", str(norm_title), str(norm_author))
    if norm_title:
        return ("t", str(norm_title))
    return None


_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS audiobookshelf_inventory (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    kind            TEXT NOT NULL,
    library_id      TEXT,
    series_name     TEXT,
    title           TEXT,
    author          TEXT,
    isbn_13         TEXT,
    isbn_10         TEXT,
    norm_title      TEXT,
    norm_author     TEXT,
    norm_series     TEXT,
    norm_series_full TEXT,
    series_index    REAL,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_abs_inventory_isbn13 ON audiobookshelf_inventory (isbn_13);
CREATE INDEX IF NOT EXISTS idx_abs_inventory_isbn10 ON audiobookshelf_inventory (isbn_10);
CREATE INDEX IF NOT EXISTS idx_abs_inventory_title_author
ON audiobookshelf_inventory (norm_title, norm_author);
CREATE INDEX IF NOT EXISTS idx_abs_inventory_series ON audiobookshelf_inventory (norm_series);
CREATE INDEX IF NOT EXISTS idx_abs_inventory_series_index
ON audiobookshelf_inventory (norm_series, series_index);
CREATE INDEX IF NOT EXISTS idx_abs_inventory_series_full
ON audiobookshelf_inventory (norm_series_full, series_index);
"""


class AudiobookshelfInventoryService:
    """Read/write access to the persisted Audiobookshelf inventory snapshot."""

    def __init__(self, db_path: str) -> None:
        """Initialize with the SQLite database path (shared users.db)."""
        self._db_path = db_path
        self._lock = threading.Lock()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        """Create the inventory table and indexes if missing."""
        with self._lock, self._connect() as conn:
            conn.executescript(_CREATE_SQL)

    def replace_inventory(self, records: Iterable[dict[str, Any]]) -> dict[str, Any]:
        """Atomically replace the entire snapshot with *records*.

        Returns ``{"rows", "new_books", "baseline"}`` where ``new_books`` are
        records whose identity was absent from the prior snapshot, and
        ``baseline`` is True on the very first populate.
        """
        rows: list[Sequence[Any]] = []
        book_metas: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        for rec in records:
            isbn_13 = (str(rec.get("isbn_13")).strip() or None) if rec.get("isbn_13") else None
            isbn_10 = (str(rec.get("isbn_10")).strip() or None) if rec.get("isbn_10") else None
            series_index = rec.get("series_index")
            try:
                series_index = float(series_index) if series_index is not None else None
            except (TypeError, ValueError):
                series_index = None
            kind = rec.get("kind", "book")
            norm_t = normalize_title(rec.get("title"))
            norm_a = normalize_author(rec.get("author"))
            norm_sf = fold_series(rec.get("series_name"))
            rows.append(
                (
                    kind,
                    rec.get("library_id"),
                    rec.get("series_name"),
                    rec.get("title"),
                    rec.get("author"),
                    isbn_13,
                    isbn_10,
                    norm_t,
                    norm_a,
                    series_key(rec.get("series_name")),
                    norm_sf,
                    series_index,
                )
            )
            if kind == "book":
                ident = _book_identity(isbn_13, isbn_10, norm_sf, series_index, norm_t, norm_a)
                if ident is not None:
                    book_metas.append(
                        (
                            ident,
                            {
                                "title": rec.get("title"),
                                "author": rec.get("author"),
                                "series_name": rec.get("series_name"),
                            },
                        )
                    )

        with self._lock, self._connect() as conn:
            existing = {
                _book_identity(*row)
                for row in conn.execute(
                    "SELECT isbn_13, isbn_10, norm_series_full, series_index, "
                    "norm_title, norm_author FROM audiobookshelf_inventory WHERE kind = 'book'"
                )
            }
            existing.discard(None)
            had_existing = bool(existing)
            conn.execute("DELETE FROM audiobookshelf_inventory")
            conn.executemany(
                """
                INSERT INTO audiobookshelf_inventory
                    (kind, library_id, series_name, title, author,
                     isbn_13, isbn_10, norm_title, norm_author, norm_series,
                     norm_series_full, series_index)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

        new_books: list[dict[str, Any]] = []
        if had_existing:
            seen: set[tuple[Any, ...]] = set()
            for ident, display in book_metas:
                if ident in existing or ident in seen:
                    continue
                seen.add(ident)
                new_books.append(display)

        logger.info(
            "Audiobookshelf inventory snapshot replaced: %d rows (%d new%s)",
            len(rows),
            len(new_books),
            "" if had_existing else ", baseline",
        )
        return {"rows": len(rows), "new_books": new_books, "baseline": not had_existing}

    def count(self) -> int:
        """Return the total number of inventory rows."""
        try:
            with self._lock, self._connect() as conn:
                cur = conn.execute("SELECT COUNT(*) FROM audiobookshelf_inventory")
                return int(cur.fetchone()[0])
        except sqlite3.Error:
            return 0

    def lookup_audiobook(
        self,
        *,
        isbn_13: object = None,
        isbn_10: object = None,
        title: object = None,
        author: object = None,
        series_name: object = None,
        series_index: object = None,
        raw_title: object = None,
    ) -> bool:
        """Return True if a matching audiobook exists in the snapshot.

        Match order: ISBN-13/10 exact, then title+author, then series+index
        (provider position or parsed "<series>, Vol. N").
        """
        try:
            with self._lock, self._connect() as conn:
                clean_13 = str(isbn_13).replace("-", "").strip() if isbn_13 else ""
                if clean_13:
                    cur = conn.execute(
                        "SELECT 1 FROM audiobookshelf_inventory WHERE isbn_13 = ? LIMIT 1",
                        (clean_13,),
                    )
                    if cur.fetchone():
                        return True

                clean_10 = str(isbn_10).replace("-", "").strip() if isbn_10 else ""
                if clean_10:
                    cur = conn.execute(
                        "SELECT 1 FROM audiobookshelf_inventory WHERE isbn_10 = ? LIMIT 1",
                        (clean_10,),
                    )
                    if cur.fetchone():
                        return True

                norm_t = normalize_title(title)
                norm_a = normalize_author(author)
                if norm_t and norm_a:
                    cur = conn.execute(
                        """
                        SELECT 1 FROM audiobookshelf_inventory
                        WHERE norm_title = ? AND norm_author = ? LIMIT 1
                        """,
                        (norm_t, norm_a),
                    )
                    if cur.fetchone():
                        return True

                norm_s = series_key(series_name)
                idx = _to_float(series_index)
                if norm_s and idx is not None:
                    cur = conn.execute(
                        """
                        SELECT 1 FROM audiobookshelf_inventory
                        WHERE norm_series = ? AND series_index = ? AND kind = 'book'
                        LIMIT 1
                        """,
                        (norm_s, idx),
                    )
                    if cur.fetchone():
                        return True

                series_part, vol = parse_volume_title(raw_title if raw_title else title)
                full_s = fold_series(series_part) if series_part else ""
                if full_s and vol is not None:
                    cur = conn.execute(
                        """
                        SELECT 1 FROM audiobookshelf_inventory
                        WHERE norm_series_full = ? AND series_index = ? AND kind = 'book'
                        LIMIT 1
                        """,
                        (full_s, vol),
                    )
                    if cur.fetchone():
                        return True
                return False
        except sqlite3.Error as exc:
            logger.debug("Audiobookshelf inventory lookup failed: %s", exc)
            return False

    def series_coverage(self, series_name: object) -> int:
        """Return the count of distinct owned audiobooks for a series."""
        norm_s = series_key(series_name)
        if not norm_s:
            return 0
        try:
            with self._lock, self._connect() as conn:
                cur = conn.execute(
                    """
                    SELECT COUNT(DISTINCT COALESCE(NULLIF(norm_title, ''), id))
                    FROM audiobookshelf_inventory
                    WHERE norm_series = ? AND kind = 'book'
                    """,
                    (norm_s,),
                )
                return int(cur.fetchone()[0])
        except sqlite3.Error as exc:
            logger.debug("Audiobookshelf series coverage failed: %s", exc)
            return 0


_service: AudiobookshelfInventoryService | None = None
_service_lock = threading.Lock()


def init_abs_inventory_service(db_path: str) -> AudiobookshelfInventoryService:
    """Create (once) and return the process-wide ABS inventory singleton."""
    global _service  # noqa: PLW0603
    with _service_lock:
        if _service is None:
            _service = AudiobookshelfInventoryService(db_path)
            _service.initialize()
        return _service


def get_abs_inventory_service() -> AudiobookshelfInventoryService | None:
    """Return the ABS inventory service if initialized, else None."""
    return _service
