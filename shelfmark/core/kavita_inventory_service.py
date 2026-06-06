"""Persisted snapshot of Kavita library contents for availability matching.

A full-replace snapshot written by the Kavita sync and read (cheaply) during
metadata search to flag books/series already present in the user's library.
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
    """Best-effort float coercion; None on failure."""
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
    """Stable identity for a book row, used to diff scans for new arrivals.

    Mirrors the lookup precedence so the same physical book keeps one identity
    across syncs even if some fields are sparse. Returns None when nothing
    distinctive is present (such rows are ignored for new-arrival detection).
    """
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
CREATE TABLE IF NOT EXISTS kavita_inventory (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    kind            TEXT NOT NULL,
    library_id      INTEGER,
    kavita_series_id INTEGER,
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

CREATE INDEX IF NOT EXISTS idx_kavita_inventory_isbn13 ON kavita_inventory (isbn_13);
CREATE INDEX IF NOT EXISTS idx_kavita_inventory_isbn10 ON kavita_inventory (isbn_10);
CREATE INDEX IF NOT EXISTS idx_kavita_inventory_title_author
ON kavita_inventory (norm_title, norm_author);
CREATE INDEX IF NOT EXISTS idx_kavita_inventory_series ON kavita_inventory (norm_series);
"""

_POST_MIGRATION_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_kavita_inventory_series_index "
    "ON kavita_inventory (norm_series, series_index);"
    "CREATE INDEX IF NOT EXISTS idx_kavita_inventory_series_full "
    "ON kavita_inventory (norm_series_full, series_index);"
)

_ADDED_COLUMNS = {
    "series_index": "REAL",
    "norm_series_full": "TEXT",
}


class KavitaInventoryService:
    """Read/write access to the persisted Kavita inventory snapshot."""

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
            cols = {row[1] for row in conn.execute("PRAGMA table_info(kavita_inventory)")}
            for name, decl in _ADDED_COLUMNS.items():
                if name not in cols:
                    conn.execute(f"ALTER TABLE kavita_inventory ADD COLUMN {name} {decl}")
            conn.executescript(_POST_MIGRATION_INDEX_SQL)

    def replace_inventory(self, records: Iterable[dict[str, Any]]) -> dict[str, Any]:
        """Atomically replace the entire snapshot with *records*.

        Records removed from Kavita disappear because the table is fully rebuilt
        in one transaction. Returns ``{"rows", "new_books", "baseline"}`` where
        ``new_books`` are book records (title/author/series_name) whose identity
        was absent from the prior snapshot, and ``baseline`` is True on the very
        first populate (no prior books → no new-arrival notifications).
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
                    rec.get("series_id"),
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
                    "norm_title, norm_author FROM kavita_inventory WHERE kind = 'book'"
                )
            }
            existing.discard(None)
            had_existing = bool(existing)
            conn.execute("DELETE FROM kavita_inventory")
            conn.executemany(
                """
                INSERT INTO kavita_inventory
                    (kind, library_id, kavita_series_id, series_name, title, author,
                     isbn_13, isbn_10, norm_title, norm_author, norm_series,
                     norm_series_full, series_index)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            "Kavita inventory snapshot replaced: %d rows (%d new books%s)",
            len(rows),
            len(new_books),
            "" if had_existing else ", baseline",
        )
        return {"rows": len(rows), "new_books": new_books, "baseline": not had_existing}

    def count(self) -> int:
        """Return the total number of inventory rows."""
        try:
            with self._lock, self._connect() as conn:
                cur = conn.execute("SELECT COUNT(*) FROM kavita_inventory")
                return int(cur.fetchone()[0])
        except sqlite3.Error:
            return 0

    def lookup_book(
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
        """Return True if a specific book exists in the snapshot.

        Match order, most to least precise:
        1. ISBN-13 / ISBN-10 exact.
        2. Normalized title + author.
        3. Series name + volume index (provider series position, or the
           "<series>, Vol. N" parsed from the raw title — handles manga whose
           titles carry a colon subtitle that breaks plain title matching).
        4. Title-only against authorless volume rows (manga/comics, whose
           chapters carry no writer in Kavita) — gated to ``series_index`` rows
           so generic single-title series can't false-match.
        """
        try:
            with self._lock, self._connect() as conn:
                clean_13 = str(isbn_13).replace("-", "").strip() if isbn_13 else ""
                if clean_13:
                    cur = conn.execute(
                        "SELECT 1 FROM kavita_inventory WHERE isbn_13 = ? LIMIT 1",
                        (clean_13,),
                    )
                    if cur.fetchone():
                        return True

                clean_10 = str(isbn_10).replace("-", "").strip() if isbn_10 else ""
                if clean_10:
                    cur = conn.execute(
                        "SELECT 1 FROM kavita_inventory WHERE isbn_10 = ? LIMIT 1",
                        (clean_10,),
                    )
                    if cur.fetchone():
                        return True

                norm_t = normalize_title(title)
                norm_a = normalize_author(author)
                if norm_t and norm_a:
                    cur = conn.execute(
                        """
                        SELECT 1 FROM kavita_inventory
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
                        SELECT 1 FROM kavita_inventory
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
                        SELECT 1 FROM kavita_inventory
                        WHERE norm_series_full = ? AND series_index = ? AND kind = 'book'
                        LIMIT 1
                        """,
                        (full_s, vol),
                    )
                    if cur.fetchone():
                        return True

                if norm_t:
                    cur = conn.execute(
                        """
                        SELECT 1 FROM kavita_inventory
                        WHERE norm_title = ? AND series_index IS NOT NULL
                          AND (norm_author IS NULL OR norm_author = '')
                        LIMIT 1
                        """,
                        (norm_t,),
                    )
                    if cur.fetchone():
                        return True
                return False
        except sqlite3.Error as exc:
            logger.debug("Kavita inventory lookup failed: %s", exc)
            return False

    def series_coverage(self, series_name: object) -> int:
        """Return the count of distinct owned books for a series (kind='book')."""
        norm_s = series_key(series_name)
        if not norm_s:
            return 0
        try:
            with self._lock, self._connect() as conn:
                cur = conn.execute(
                    """
                    SELECT COUNT(DISTINCT COALESCE(NULLIF(norm_title, ''), id))
                    FROM kavita_inventory
                    WHERE norm_series = ? AND kind = 'book'
                    """,
                    (norm_s,),
                )
                return int(cur.fetchone()[0])
        except sqlite3.Error as exc:
            logger.debug("Kavita series coverage failed: %s", exc)
            return 0


_service: KavitaInventoryService | None = None
_service_lock = threading.Lock()


def init_inventory_service(db_path: str) -> KavitaInventoryService:
    """Create (once) and return the process-wide inventory service singleton."""
    global _service  # noqa: PLW0603
    with _service_lock:
        if _service is None:
            _service = KavitaInventoryService(db_path)
            _service.initialize()
        return _service


def get_inventory_service() -> KavitaInventoryService | None:
    """Return the inventory service if it has been initialized, else None."""
    return _service
