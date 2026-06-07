"""Audiobookshelf REST client: libraries and audiobook inventory.

Authenticates with an API key sent as ``Authorization: Bearer``. Mirrors the
Kavita client shape but targets the Audiobookshelf API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import requests

from shelfmark.core.logger import setup_logger

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = setup_logger(__name__)

ABS_DISPLAY_NAME = "Audiobookshelf"
_TIMEOUT = 30
_PAGE_SIZE = 500


class AbsError(Exception):
    """Raised when an Audiobookshelf API interaction fails."""


@dataclass(frozen=True)
class AbsConfig:
    """Connection settings for the Audiobookshelf integration."""

    base_url: str
    api_key: str
    verify_tls: bool = True


def _request(
    method: str,
    url: str,
    *,
    verify_tls: bool,
    action: str,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    json_body: Any = None,
) -> requests.Response:
    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            params=params,
            json=json_body,
            timeout=_TIMEOUT,
            verify=verify_tls,
        )
    except requests.exceptions.ConnectionError as exc:
        msg = f"Could not connect to {ABS_DISPLAY_NAME}"
        raise AbsError(msg) from exc
    except requests.exceptions.Timeout as exc:
        msg = f"{ABS_DISPLAY_NAME} connection timed out"
        raise AbsError(msg) from exc
    except requests.exceptions.RequestException as exc:
        msg = f"{ABS_DISPLAY_NAME} {action} failed: {exc}"
        raise AbsError(msg) from exc
    return response


def _json(response: requests.Response, action: str) -> Any:
    try:
        return response.json()
    except ValueError as exc:
        msg = f"Invalid {ABS_DISPLAY_NAME} {action} response"
        raise AbsError(msg) from exc


def _auth_headers(cfg: AbsConfig) -> dict[str, str]:
    return {"Authorization": f"Bearer {cfg.api_key}"}


def abs_list_libraries(cfg: AbsConfig) -> list[dict[str, Any]]:
    """Return book/audiobook libraries as ``[{id, name, mediaType}, ...]``."""
    if not cfg.base_url:
        msg = f"{ABS_DISPLAY_NAME} URL is required"
        raise AbsError(msg)
    if not cfg.api_key:
        msg = f"{ABS_DISPLAY_NAME} API key is required"
        raise AbsError(msg)

    url = f"{cfg.base_url}/api/libraries"
    response = _request(
        "GET", url, verify_tls=cfg.verify_tls, action="libraries", headers=_auth_headers(cfg)
    )
    if response.status_code in {401, 403}:
        msg = f"{ABS_DISPLAY_NAME} authentication failed (check API key)"
        raise AbsError(msg)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        msg = f"Failed to fetch {ABS_DISPLAY_NAME} libraries ({response.status_code})"
        raise AbsError(msg) from exc

    data = _json(response, "libraries")
    libraries = data.get("libraries") if isinstance(data, dict) else None
    if not isinstance(libraries, list):
        return []
    return [lib for lib in libraries if isinstance(lib, dict) and lib.get("mediaType") == "book"]


def _iter_library_items(cfg: AbsConfig, library_id: Any) -> Iterator[dict[str, Any]]:
    page = 0
    while True:
        url = f"{cfg.base_url}/api/libraries/{library_id}/items"
        params = {"limit": _PAGE_SIZE, "page": page}
        response = _request(
            "GET",
            url,
            verify_tls=cfg.verify_tls,
            action="library items",
            headers=_auth_headers(cfg),
            params=params,
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            msg = f"Failed to fetch {ABS_DISPLAY_NAME} items ({response.status_code})"
            raise AbsError(msg) from exc

        data = _json(response, "library items")
        results = data.get("results") if isinstance(data, dict) else None
        if not isinstance(results, list) or not results:
            break
        for item in results:
            if isinstance(item, dict):
                yield item
        if len(results) < _PAGE_SIZE:
            break
        page += 1


def _parse_isbn(raw: object) -> tuple[str | None, str | None]:
    text = str(raw or "").replace("-", "").strip()
    if len(text) == 13 and text.isdigit():
        return text, None
    if len(text) == 10:
        return None, text
    return None, None


def _first_series(metadata: dict[str, Any]) -> tuple[str | None, float | None]:
    series = metadata.get("series")
    entry: Any = None
    if isinstance(series, list) and series:
        entry = series[0]
    elif isinstance(series, dict):
        entry = series
    if isinstance(entry, dict):
        name = str(entry.get("name") or "").strip() or None
        try:
            index = float(entry.get("sequence")) if entry.get("sequence") not in (None, "") else None
        except (TypeError, ValueError):
            index = None
        return name, index
    if isinstance(entry, str):
        return entry.strip() or None, None
    return None, None


def abs_iter_inventory(cfg: AbsConfig, library_ids: list[int]) -> Iterator[dict[str, Any]]:
    """Yield normalized audiobook records for the selected libraries.

    An empty *library_ids* list means "all book libraries".
    """
    wanted = {str(lib) for lib in library_ids} if library_ids else None

    for library in abs_list_libraries(cfg):
        library_id = library.get("id")
        if library_id is None:
            continue
        if wanted is not None and str(library_id) not in wanted:
            continue

        for item in _iter_library_items(cfg, library_id):
            media = item.get("media")
            metadata = media.get("metadata") if isinstance(media, dict) else None
            if not isinstance(metadata, dict):
                continue
            title = str(metadata.get("title") or "").strip()
            if not title:
                continue
            author = str(metadata.get("authorName") or "").strip()
            isbn_13, isbn_10 = _parse_isbn(metadata.get("isbn"))
            series_name, series_index = _first_series(metadata)
            yield {
                "kind": "book",
                "library_id": library_id,
                "series_id": None,
                "series_name": series_name or title,
                "title": title,
                "author": author,
                "isbn_13": isbn_13,
                "isbn_10": isbn_10,
                "series_index": series_index,
            }


def abs_list_users(cfg: AbsConfig) -> list[dict[str, Any]]:
    """Return Audiobookshelf users (requires an admin API key)."""
    url = f"{cfg.base_url}/api/users"
    response = _request(
        "GET", url, verify_tls=cfg.verify_tls, action="users", headers=_auth_headers(cfg)
    )
    if response.status_code in {401, 403}:
        msg = f"{ABS_DISPLAY_NAME} authentication failed (admin API key required)"
        raise AbsError(msg)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        msg = f"Failed to fetch {ABS_DISPLAY_NAME} users ({response.status_code})"
        raise AbsError(msg) from exc
    data = _json(response, "users")
    users = data.get("users") if isinstance(data, dict) else None
    return [u for u in users if isinstance(u, dict)] if isinstance(users, list) else []


def abs_user_exists(cfg: AbsConfig, username: str) -> bool:
    """Return True if a user with *username* already exists (case-insensitive)."""
    target = (username or "").strip().lower()
    if not target:
        return False
    return any(str(u.get("username") or "").strip().lower() == target for u in abs_list_users(cfg))


def abs_create_user(cfg: AbsConfig, username: str, password: str) -> None:
    """Create a standard Audiobookshelf user with download/library access."""
    url = f"{cfg.base_url}/api/users"
    payload = {
        "username": username,
        "password": password,
        "type": "user",
        "isActive": True,
        "permissions": {
            "download": True,
            "update": False,
            "delete": False,
            "upload": False,
            "accessAllLibraries": True,
            "accessAllTags": True,
            "accessExplicitContent": True,
            "createEreader": False,
        },
    }
    response = _request(
        "POST",
        url,
        verify_tls=cfg.verify_tls,
        action="create user",
        headers=_auth_headers(cfg),
        json_body=payload,
    )
    if response.status_code in {401, 403}:
        msg = f"{ABS_DISPLAY_NAME} authentication failed (admin API key required)"
        raise AbsError(msg)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        msg = f"Failed to create {ABS_DISPLAY_NAME} user ({response.status_code})"
        raise AbsError(msg) from exc
