"""Kavita REST API client: plugin auth, user login, libraries, and inventory.

Modeled on shelfmark.download.outputs.booklore: requests + Bearer token + a
frozen config dataclass. All authenticated calls send ``Authorization: Bearer``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import requests

from shelfmark.core.logger import setup_logger

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = setup_logger(__name__)

KAVITA_DISPLAY_NAME = "Kavita"
DEFAULT_PLUGIN_NAME = "Shelfmark"
_TIMEOUT = 30


class KavitaError(Exception):
    """Raised when a Kavita API interaction fails."""


@dataclass(frozen=True)
class KavitaConfig:
    """Connection settings for the Kavita integration (sync side)."""

    base_url: str
    api_key: str
    verify_tls: bool = True
    plugin_name: str = DEFAULT_PLUGIN_NAME


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
    """Issue a request and translate transport errors into KavitaError."""
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
        msg = f"Could not connect to {KAVITA_DISPLAY_NAME}"
        raise KavitaError(msg) from exc
    except requests.exceptions.Timeout as exc:
        msg = f"{KAVITA_DISPLAY_NAME} connection timed out"
        raise KavitaError(msg) from exc
    except requests.exceptions.RequestException as exc:
        msg = f"{KAVITA_DISPLAY_NAME} {action} failed: {exc}"
        raise KavitaError(msg) from exc
    return response


def _json(response: requests.Response, action: str) -> Any:
    try:
        return response.json()
    except ValueError as exc:
        msg = f"Invalid {KAVITA_DISPLAY_NAME} {action} response"
        raise KavitaError(msg) from exc


def kavita_authenticate_plugin(cfg: KavitaConfig) -> str:
    """Exchange the admin API key for a short-lived JWT (used for sync)."""
    if not cfg.base_url:
        msg = f"{KAVITA_DISPLAY_NAME} URL is required"
        raise KavitaError(msg)
    if not cfg.api_key:
        msg = f"{KAVITA_DISPLAY_NAME} API key is required"
        raise KavitaError(msg)

    url = f"{cfg.base_url}/api/Plugin/authenticate"
    params = {"apiKey": cfg.api_key, "pluginName": cfg.plugin_name}
    response = _request(
        "POST", url, verify_tls=cfg.verify_tls, action="authentication", params=params
    )
    if response.status_code in {401, 403}:
        msg = f"{KAVITA_DISPLAY_NAME} authentication failed (check API key)"
        raise KavitaError(msg)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        msg = f"{KAVITA_DISPLAY_NAME} authentication failed ({response.status_code})"
        raise KavitaError(msg) from exc

    token = _json(response, "authentication").get("token")
    if not token:
        msg = f"{KAVITA_DISPLAY_NAME} did not return a token"
        raise KavitaError(msg)
    return str(token)


def kavita_login_user(
    base_url: str,
    username: str,
    password: str,
    *,
    verify_tls: bool = True,
) -> dict[str, Any]:
    """Validate a user's Kavita credentials (used for SSO).

    Returns a dict with ``token``, ``username``, ``email``, ``is_admin``, ``api_key``.
    Raises KavitaError on bad credentials or transport failure.
    """
    base_url = (base_url or "").strip().rstrip("/")
    if not base_url:
        msg = f"{KAVITA_DISPLAY_NAME} URL is required"
        raise KavitaError(msg)

    url = f"{base_url}/api/Account/login"
    payload = {"username": username, "password": password}
    response = _request(
        "POST", url, verify_tls=verify_tls, action="login", json_body=payload
    )
    if response.status_code in {401, 403}:
        msg = "Invalid Kavita username or password"
        raise KavitaError(msg)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        msg = f"{KAVITA_DISPLAY_NAME} login failed ({response.status_code})"
        raise KavitaError(msg) from exc

    data = _json(response, "login")
    token = data.get("token")
    if not token:
        msg = f"{KAVITA_DISPLAY_NAME} did not return a token"
        raise KavitaError(msg)

    roles = data.get("roles") or []
    is_admin = isinstance(roles, list) and any(
        str(role).strip().lower() == "admin" for role in roles
    )
    return {
        "token": str(token),
        "username": str(data.get("username") or username).strip(),
        "email": (str(data.get("email")).strip() or None) if data.get("email") else None,
        "is_admin": is_admin,
        "api_key": data.get("apiKey"),
    }


def kavita_list_libraries(cfg: KavitaConfig, token: str) -> list[dict[str, Any]]:
    """Return the available Kavita libraries as ``[{id, name, type}, ...]``."""
    url = f"{cfg.base_url}/api/Library/libraries"
    headers = {"Authorization": f"Bearer {token}"}
    response = _request(
        "GET", url, verify_tls=cfg.verify_tls, action="libraries", headers=headers
    )
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        msg = f"Failed to fetch {KAVITA_DISPLAY_NAME} libraries ({response.status_code})"
        raise KavitaError(msg) from exc
    data = _json(response, "libraries")
    return data if isinstance(data, list) else []


def _list_all_series(cfg: KavitaConfig, token: str) -> list[dict[str, Any]]:
    """List every series across all libraries via the all-v2 endpoint (paged).

    Each returned SeriesDto carries its own ``libraryId``, so callers filter
    client-side. This avoids depending on the version-fragile FilterV2Dto enum
    field numbers for server-side library filtering.
    """
    headers = {"Authorization": f"Bearer {token}"}
    series: list[dict[str, Any]] = []
    page = 1
    page_size = 200
    body = {"statements": [], "combination": 0, "limitTo": 0}
    while True:
        url = f"{cfg.base_url}/api/Series/all-v2"
        params = {"PageNumber": page, "PageSize": page_size}
        response = _request(
            "POST",
            url,
            verify_tls=cfg.verify_tls,
            action="series",
            headers=headers,
            params=params,
            json_body=body,
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            msg = f"Failed to fetch {KAVITA_DISPLAY_NAME} series ({response.status_code})"
            raise KavitaError(msg) from exc
        batch = _json(response, "series")
        if not isinstance(batch, list) or not batch:
            break
        series.extend(item for item in batch if isinstance(item, dict))
        if len(batch) < page_size:
            break
        page += 1
    return series


def _series_metadata(cfg: KavitaConfig, token: str, series_id: int) -> dict[str, Any]:
    """Fetch series metadata (writers, etc). Best-effort: returns {} on failure."""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{cfg.base_url}/api/Series/metadata"
    params = {"seriesId": series_id}
    try:
        response = _request(
            "GET",
            url,
            verify_tls=cfg.verify_tls,
            action="series metadata",
            headers=headers,
            params=params,
        )
        response.raise_for_status()
        data = _json(response, "series metadata")
    except KavitaError:
        return {}
    except requests.exceptions.HTTPError:
        return {}
    return data if isinstance(data, dict) else {}


def _series_volumes(cfg: KavitaConfig, token: str, series_id: int) -> list[dict[str, Any]]:
    """Fetch the volumes (each containing chapters) for a series. Best-effort."""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{cfg.base_url}/api/Series/volumes"
    params = {"seriesId": series_id}
    try:
        response = _request(
            "GET",
            url,
            verify_tls=cfg.verify_tls,
            action="series volumes",
            headers=headers,
            params=params,
        )
        response.raise_for_status()
        data = _json(response, "series volumes")
    except KavitaError:
        return []
    except requests.exceptions.HTTPError:
        return []
    return data if isinstance(data, list) else []


def _writer_names(metadata: dict[str, Any]) -> str:
    writers = metadata.get("writers") or []
    names = [
        str(person.get("name")).strip()
        for person in writers
        if isinstance(person, dict) and person.get("name")
    ]
    return ", ".join(names)


def _chapter_isbns(chapter: dict[str, Any]) -> tuple[str | None, str | None]:
    """Extract ISBN-13/10 from a chapter when present (often empty in Kavita)."""
    raw = str(chapter.get("isbn") or "").replace("-", "").strip()
    if len(raw) == 13 and raw.isdigit():
        return raw, None
    if len(raw) == 10:
        return None, raw
    return None, None


_VOLUME_SENTINEL = 90000


def _volume_number(volume: dict[str, Any]) -> float | None:
    """Return a volume's numeric position, or None for loose-leaf/specials."""
    for key in ("minNumber", "number", "name"):
        raw = volume.get(key)
        if raw in (None, ""):
            continue
        try:
            num = float(raw)
        except (TypeError, ValueError):
            continue
        if -_VOLUME_SENTINEL < num < _VOLUME_SENTINEL:
            return num
    return None


def _format_volume_number(num: float) -> str:
    """Render a volume number without a trailing ``.0`` (1.0 -> "1", 1.5 -> "1.5")."""
    return str(int(num)) if num == int(num) else str(num)


def _chapter_author(chapter: dict[str, Any], fallback: str) -> str:
    """Prefer a chapter's own writers; fall back to the series-level author."""
    writers = chapter.get("writers") or []
    names = [
        str(person.get("name")).strip()
        for person in writers
        if isinstance(person, dict) and person.get("name")
    ]
    return ", ".join(names) if names else fallback


def _book_record(
    *,
    library_id: Any,
    series_id: int,
    series_name: str,
    title: str,
    author: str,
    isbn_13: str | None,
    isbn_10: str | None,
    series_index: float | None,
) -> dict[str, Any]:
    return {
        "kind": "book",
        "library_id": library_id,
        "series_id": series_id,
        "series_name": series_name,
        "title": title or series_name,
        "author": author,
        "isbn_13": isbn_13,
        "isbn_10": isbn_10,
        "series_index": series_index,
    }


def kavita_iter_inventory(
    cfg: KavitaConfig,
    token: str,
    library_ids: list[int],
) -> Iterator[dict[str, Any]]:
    """Yield normalized inventory records for the selected libraries.

    Emits one ``kind="series"`` record per series plus ``kind="book"`` records.
    Titled chapters (typical eBooks) yield one book per title; untitled volumes
    (typical manga/comics) yield one book per volume, titled "<series>, Vol. N"
    to align with how metadata providers name volumes. Per-series failures are
    logged and skipped. An empty *library_ids* list means "all libraries".
    """
    wanted = {int(lib) for lib in library_ids} if library_ids else None

    for series in _list_all_series(cfg, token):
        series_id = series.get("id")
        library_id = series.get("libraryId")
        series_name = str(series.get("name") or "").strip()
        if series_id is None or not series_name:
            continue
        if wanted is not None:
            try:
                if int(library_id) not in wanted:
                    continue
            except (TypeError, ValueError):
                continue

        try:
            sid = int(series_id)
        except (TypeError, ValueError):
            continue
        metadata = _series_metadata(cfg, token, sid)
        author = _writer_names(metadata)

        yield {
            "kind": "series",
            "library_id": library_id,
            "series_id": sid,
            "series_name": series_name,
            "title": series_name,
            "author": author,
            "isbn_13": None,
            "isbn_10": None,
            "series_index": None,
        }

        for volume in _series_volumes(cfg, token, sid):
            if not isinstance(volume, dict):
                continue
            vol_num = _volume_number(volume)
            chapters = [c for c in (volume.get("chapters") or []) if isinstance(c, dict)]
            titled = [c for c in chapters if str(c.get("titleName") or "").strip()]

            if titled:
                for chapter in titled:
                    isbn_13, isbn_10 = _chapter_isbns(chapter)
                    yield _book_record(
                        library_id=library_id,
                        series_id=sid,
                        series_name=series_name,
                        title=str(chapter.get("titleName")).strip(),
                        author=_chapter_author(chapter, author),
                        isbn_13=isbn_13,
                        isbn_10=isbn_10,
                        series_index=vol_num,
                    )
            elif vol_num is not None:
                first = chapters[0] if chapters else {}
                isbn_13, isbn_10 = _chapter_isbns(first)
                yield _book_record(
                    library_id=library_id,
                    series_id=sid,
                    series_name=series_name,
                    title=f"{series_name}, Vol. {_format_volume_number(vol_num)}",
                    author=_chapter_author(first, author),
                    isbn_13=isbn_13,
                    isbn_10=isbn_10,
                    series_index=vol_num,
                )
            else:
                for chapter in chapters:
                    isbn_13, isbn_10 = _chapter_isbns(chapter)
                    yield _book_record(
                        library_id=library_id,
                        series_id=sid,
                        series_name=series_name,
                        title=series_name,
                        author=_chapter_author(chapter, author),
                        isbn_13=isbn_13,
                        isbn_10=isbn_10,
                        series_index=None,
                    )
