"""Kavita library sync: pull inventory into the local snapshot.

Single-flight: concurrent triggers (cron + on-download + manual) coalesce so
only one sync runs at a time.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from shelfmark.core.config import config
from shelfmark.core.kavita_inventory_service import get_inventory_service
from shelfmark.core.logger import setup_logger
from shelfmark.integrations.kavita.client import (
    KavitaConfig,
    KavitaError,
    kavita_authenticate_plugin,
    kavita_iter_inventory,
    kavita_list_libraries,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = setup_logger(__name__)

_sync_lock = threading.Lock()


def _notify_new_library_books(new_books: list[dict[str, Any]]) -> None:
    """Fire an "Available in Library" admin notification per newly-found book."""
    if not new_books:
        return
    try:
        from shelfmark.core.notifications import (
            NotificationContext,
            NotificationEvent,
            notify_admin,
        )
    except ImportError:
        logger.debug("Notifications unavailable; skipping library-available alerts")
        return

    for book in new_books:
        try:
            context = NotificationContext(
                event=NotificationEvent.LIBRARY_AVAILABLE,
                title=str(book.get("title") or book.get("series_name") or "Unknown title"),
                author=str(book.get("author") or "Unknown author"),
            )
            notify_admin(NotificationEvent.LIBRARY_AVAILABLE, context)
        except (RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Failed to send library-available notification: %s", exc)


def _cfg_value(overrides: Mapping[str, Any] | None, key: str, default: Any = "") -> Any:
    if overrides is not None:
        value = overrides.get(key)
        if value not in (None, ""):
            return value
    return config.get(key, default)


def build_kavita_config(overrides: Mapping[str, Any] | None = None) -> KavitaConfig:
    """Build a KavitaConfig from saved config, optionally overridden by form values."""
    base_url = str(_cfg_value(overrides, "KAVITA_URL", "") or "").strip().rstrip("/")
    api_key = str(_cfg_value(overrides, "KAVITA_API_KEY", "") or "").strip()
    return KavitaConfig(base_url=base_url, api_key=api_key, verify_tls=True)


def _selected_library_ids(
    cfg: KavitaConfig, token: str, overrides: Mapping[str, Any] | None
) -> list[int]:
    """Resolve which library IDs to sync (configured subset, or all)."""
    raw = _cfg_value(overrides, "KAVITA_SYNC_LIBRARY_IDS", []) or []
    selected: list[int] = []
    if isinstance(raw, list):
        for value in raw:
            try:
                selected.append(int(value))
            except (TypeError, ValueError):
                continue
    if selected:
        return selected
    return [int(lib["id"]) for lib in kavita_list_libraries(cfg, token) if lib.get("id") is not None]


def run_kavita_sync(overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Run a full Kavita inventory sync. Returns a summary dict.

    On error returns ``{"success": False, "error": "..."}`` without raising.
    """
    inventory = get_inventory_service()
    if inventory is None:
        return {"success": False, "error": "Inventory store unavailable"}

    cfg = build_kavita_config(overrides)
    if not cfg.base_url or not cfg.api_key:
        return {"success": False, "error": "Kavita URL and API key are required"}

    if not _sync_lock.acquire(blocking=False):
        logger.info("Kavita sync already running; skipping overlapping trigger")
        return {"success": False, "error": "Sync already in progress"}

    try:
        token = kavita_authenticate_plugin(cfg)
        library_ids = _selected_library_ids(cfg, token, overrides)
        records = list(kavita_iter_inventory(cfg, token, library_ids))
        result = inventory.replace_inventory(records)
        series = sum(1 for r in records if r.get("kind") == "series")
        books = sum(1 for r in records if r.get("kind") == "book")
        new_books = result.get("new_books") or []
        logger.info(
            "Kavita sync complete: %d libraries, %d series, %d books (%d rows, %d new)",
            len(library_ids),
            series,
            books,
            result.get("rows", 0),
            len(new_books),
        )
        _notify_new_library_books(new_books)
        return {
            "success": True,
            "libraries": len(library_ids),
            "series": series,
            "books": books,
            "new_books": len(new_books),
        }
    except KavitaError as exc:
        logger.warning("Kavita sync failed: %s", exc)
        return {"success": False, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001 - sync must never crash the caller
        logger.exception("Unexpected error during Kavita sync")
        return {"success": False, "error": str(exc)}
    finally:
        _sync_lock.release()
