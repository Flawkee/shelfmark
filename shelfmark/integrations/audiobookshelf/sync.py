"""Audiobookshelf library sync: pull audiobook inventory into the local snapshot.

Single-flight: concurrent triggers (cron + on-download + manual) coalesce so
only one sync runs at a time.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from shelfmark.core.audiobookshelf_inventory_service import get_abs_inventory_service
from shelfmark.core.config import config
from shelfmark.core.logger import setup_logger
from shelfmark.integrations.audiobookshelf.client import (
    AbsConfig,
    AbsError,
    abs_iter_inventory,
    abs_list_libraries,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = setup_logger(__name__)

_sync_lock = threading.Lock()


def _notify_new_audiobooks(new_books: list[dict[str, Any]]) -> None:
    """Fire an "Audiobook Added to Library" admin notification per new item."""
    if not new_books:
        return
    try:
        from shelfmark.core.notifications import (
            NotificationContext,
            NotificationEvent,
            notify_admin,
        )
    except ImportError:
        logger.debug("Notifications unavailable; skipping audiobook-available alerts")
        return

    for book in new_books:
        try:
            context = NotificationContext(
                event=NotificationEvent.AUDIOBOOK_LIBRARY_AVAILABLE,
                title=str(book.get("title") or book.get("series_name") or "Unknown title"),
                author=str(book.get("author") or "Unknown author"),
                content_type="audiobook",
            )
            notify_admin(NotificationEvent.AUDIOBOOK_LIBRARY_AVAILABLE, context)
        except (RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Failed to send audiobook-available notification: %s", exc)


def _cfg_value(overrides: Mapping[str, Any] | None, key: str, default: Any = "") -> Any:
    if overrides is not None:
        value = overrides.get(key)
        if value not in (None, ""):
            return value
    return config.get(key, default)


def build_abs_config(overrides: Mapping[str, Any] | None = None) -> AbsConfig:
    """Build an AbsConfig from saved config, optionally overridden by form values."""
    base_url = str(_cfg_value(overrides, "ABS_URL", "") or "").strip().rstrip("/")
    api_key = str(_cfg_value(overrides, "ABS_API_KEY", "") or "").strip()
    return AbsConfig(base_url=base_url, api_key=api_key, verify_tls=True)


def _selected_library_ids(overrides: Mapping[str, Any] | None) -> list[str]:
    raw = _cfg_value(overrides, "ABS_SYNC_LIBRARY_IDS", []) or []
    if isinstance(raw, list):
        return [str(value).strip() for value in raw if str(value).strip()]
    return []


def run_abs_sync(overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Run a full Audiobookshelf inventory sync. Returns a summary dict.

    On error returns ``{"success": False, "error": "..."}`` without raising.
    """
    inventory = get_abs_inventory_service()
    if inventory is None:
        return {"success": False, "error": "Inventory store unavailable"}

    cfg = build_abs_config(overrides)
    if not cfg.base_url or not cfg.api_key:
        return {"success": False, "error": "Audiobookshelf URL and API key are required"}

    if not _sync_lock.acquire(blocking=False):
        logger.info("Audiobookshelf sync already running; skipping overlapping trigger")
        return {"success": False, "error": "Sync already in progress"}

    try:
        library_ids = _selected_library_ids(overrides)
        records = list(abs_iter_inventory(cfg, library_ids))
        result = inventory.replace_inventory(records)
        libraries = len(library_ids) if library_ids else len(abs_list_libraries(cfg))
        books = len(records)
        new_books = result.get("new_books") or []
        logger.info(
            "Audiobookshelf sync complete: %d libraries, %d audiobooks (%d rows, %d new)",
            libraries,
            books,
            result.get("rows", 0),
            len(new_books),
        )
        _notify_new_audiobooks(new_books)
        return {
            "success": True,
            "libraries": libraries,
            "books": books,
            "new_books": len(new_books),
        }
    except AbsError as exc:
        logger.warning("Audiobookshelf sync failed: %s", exc)
        return {"success": False, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001 - sync must never crash the caller
        logger.exception("Unexpected error during Audiobookshelf sync")
        return {"success": False, "error": str(exc)}
    finally:
        _sync_lock.release()
