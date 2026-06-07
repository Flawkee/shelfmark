"""Audiobookshelf integration settings tab: connection and library sync."""

from __future__ import annotations

from typing import Any

from shelfmark.core.config import config as app_config
from shelfmark.core.logger import setup_logger
from shelfmark.core.request_helpers import coerce_bool
from shelfmark.core.settings_registry import (
    ActionButton,
    CheckboxField,
    HeadingField,
    MultiSelectField,
    PasswordField,
    SettingsField,
    TextField,
    register_on_save,
    register_settings,
)
from shelfmark.integrations.audiobookshelf.client import AbsError, abs_list_libraries
from shelfmark.integrations.audiobookshelf.scheduler import (
    DEFAULT_CRON,
    reschedule,
    validate_cron,
)
from shelfmark.integrations.audiobookshelf.sync import build_abs_config, run_abs_sync

logger = setup_logger(__name__)

_ABS_OPTIONS_CACHE: dict[str, Any] = {"key": None, "options": []}


def _abs_options_from_libraries(libraries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"value": str(lib["id"]), "label": str(lib.get("name") or f"Library {lib['id']}")}
        for lib in libraries
        if lib.get("id") is not None
    ]


def get_abs_library_options() -> list[dict[str, Any]]:
    """Fetch Audiobookshelf libraries as select options.

    Falls back to the last options cached by a successful Test Connection so the
    multiselect populates before the connection details are saved.
    """
    cfg = build_abs_config()
    if not cfg.base_url or not cfg.api_key:
        return _ABS_OPTIONS_CACHE.get("options", [])
    try:
        options = _abs_options_from_libraries(abs_list_libraries(cfg))
    except AbsError:
        logger.debug("Failed to fetch Audiobookshelf libraries for options")
        return _ABS_OPTIONS_CACHE.get("options", [])
    _ABS_OPTIONS_CACHE.update({"key": f"{cfg.base_url}|{cfg.api_key}", "options": options})
    return options


def check_abs_connection(current_values: dict[str, Any] | None = None) -> dict[str, Any]:
    """Test the Audiobookshelf connection using current (possibly unsaved) values."""
    cfg = build_abs_config(current_values or {})
    if not cfg.base_url:
        return {"success": False, "message": "Audiobookshelf URL is required"}
    if not cfg.api_key:
        return {"success": False, "message": "Audiobookshelf API key is required"}
    try:
        libraries = abs_list_libraries(cfg)
    except AbsError as exc:
        return {"success": False, "message": str(exc)}
    _ABS_OPTIONS_CACHE.update(
        {"key": f"{cfg.base_url}|{cfg.api_key}", "options": _abs_options_from_libraries(libraries)}
    )
    return {
        "success": True,
        "message": f"Connected to Audiobookshelf ({len(libraries)} book libraries)",
    }


def trigger_abs_sync_now(current_values: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run an immediate Audiobookshelf sync using current form values."""
    result = run_abs_sync(current_values or {})
    if not result.get("success"):
        return {"success": False, "message": result.get("error", "Sync failed")}
    return {
        "success": True,
        "message": (
            f"Synced {result['books']} audiobooks from {result['libraries']} libraries"
        ),
    }


@register_settings("audiobookshelf", "Audiobookshelf", icon="headphones", order=7)
def audiobookshelf_settings() -> list[SettingsField]:
    """Audiobookshelf connection and library-sync settings."""
    return [
        HeadingField(
            key="abs_connection_heading",
            title="Connection",
            description=(
                "Connect Shelfmark to your Audiobookshelf server. Create an API key in "
                "Audiobookshelf under Settings → Users → (your user) → API Keys."
            ),
        ),
        TextField(
            key="ABS_URL",
            label="Audiobookshelf URL",
            description="Base URL of your Audiobookshelf instance.",
            placeholder="http://audiobookshelf:13378",
        ),
        PasswordField(
            key="ABS_API_KEY",
            label="API Key",
            description="API key used to read your libraries.",
        ),
        ActionButton(
            key="test_abs",
            label="Test Connection",
            description="Verify the Audiobookshelf URL and API key.",
            style="primary",
            callback=check_abs_connection,
        ),
        HeadingField(
            key="abs_sync_heading",
            title="Library Sync",
            description=(
                "Periodically scan Audiobookshelf so Shelfmark can mark audiobooks "
                "already in your library as available."
            ),
        ),
        CheckboxField(
            key="ABS_SYNC_ENABLED",
            label="Enable Scheduled Sync",
            description="Run the Audiobookshelf library sync on the cron schedule below.",
            default=False,
        ),
        TextField(
            key="ABS_SYNC_CRON",
            label="Sync Schedule (cron)",
            description="5-field cron expression. Default '0 * * * *' runs hourly.",
            placeholder=DEFAULT_CRON,
            default=DEFAULT_CRON,
        ),
        CheckboxField(
            key="ABS_SYNC_ON_DOWNLOAD",
            label="Sync After Download Completes",
            description=(
                "In addition to the schedule, trigger a sync shortly after each "
                "download finishes (debounced)."
            ),
            default=False,
        ),
        MultiSelectField(
            key="ABS_SYNC_LIBRARY_IDS",
            label="Libraries to Sync",
            description="Limit the sync to specific libraries. Leave empty to sync all.",
            options=get_abs_library_options,
            variant="dropdown",
            default=[],
        ),
        ActionButton(
            key="abs_sync_now",
            label="Sync Now",
            description="Run a full Audiobookshelf library sync immediately.",
            style="default",
            callback=trigger_abs_sync_now,
        ),
    ]


def _on_save_abs(values: dict[str, Any]) -> dict[str, Any]:
    """Validate the cron expression and apply the new schedule."""
    cron = values.get("ABS_SYNC_CRON")
    if cron is not None and str(cron).strip():
        try:
            validate_cron(str(cron))
        except (ValueError, TypeError):
            return {
                "error": True,
                "message": f"Invalid cron expression: {cron}",
            }

    enabled = values.get("ABS_SYNC_ENABLED")
    if enabled is None:
        enabled = app_config.get("ABS_SYNC_ENABLED", False)
    expression = values.get("ABS_SYNC_CRON") or app_config.get("ABS_SYNC_CRON", DEFAULT_CRON)

    try:
        reschedule(enabled=coerce_bool(enabled), expression=str(expression or DEFAULT_CRON))
    except Exception:  # noqa: BLE001 - never block a settings save on scheduler errors
        logger.exception("Failed to apply Audiobookshelf schedule after save")

    return {"error": False, "values": values}


register_on_save("audiobookshelf", _on_save_abs)
