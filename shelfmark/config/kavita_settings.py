"""Kavita integration settings tab: connection, SSO note, and library sync."""

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
from shelfmark.integrations.kavita.client import (
    KavitaError,
    kavita_authenticate_plugin,
    kavita_list_libraries,
)
from shelfmark.integrations.kavita.scheduler import (
    DEFAULT_CRON,
    reschedule,
    validate_cron,
)
from shelfmark.integrations.kavita.sync import build_kavita_config, run_kavita_sync

logger = setup_logger(__name__)

_KAVITA_OPTIONS_CACHE: dict[str, Any] = {"key": None, "options": []}


def _kavita_options_from_libraries(libraries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"value": str(lib["id"]), "label": str(lib.get("name") or f"Library {lib['id']}")}
        for lib in libraries
        if lib.get("id") is not None
    ]


def get_kavita_library_options() -> list[dict[str, Any]]:
    """Fetch Kavita libraries as select options.

    Falls back to the last options cached by a successful Test Connection so the
    multiselect populates before the connection details are saved.
    """
    cfg = build_kavita_config()
    if not cfg.base_url or not cfg.api_key:
        return _KAVITA_OPTIONS_CACHE.get("options", [])
    try:
        token = kavita_authenticate_plugin(cfg)
        options = _kavita_options_from_libraries(kavita_list_libraries(cfg, token))
    except KavitaError:
        logger.debug("Failed to fetch Kavita libraries for options")
        return _KAVITA_OPTIONS_CACHE.get("options", [])
    _KAVITA_OPTIONS_CACHE.update({"key": f"{cfg.base_url}|{cfg.api_key}", "options": options})
    return options


def check_kavita_connection(current_values: dict[str, Any] | None = None) -> dict[str, Any]:
    """Test the Kavita connection using current (possibly unsaved) form values."""
    cfg = build_kavita_config(current_values or {})
    if not cfg.base_url:
        return {"success": False, "message": "Kavita URL is required"}
    if not cfg.api_key:
        return {"success": False, "message": "Kavita API key is required"}
    try:
        token = kavita_authenticate_plugin(cfg)
        libraries = kavita_list_libraries(cfg, token)
    except KavitaError as exc:
        return {"success": False, "message": str(exc)}
    _KAVITA_OPTIONS_CACHE.update(
        {"key": f"{cfg.base_url}|{cfg.api_key}", "options": _kavita_options_from_libraries(libraries)}
    )
    return {
        "success": True,
        "message": f"Connected to Kavita ({len(libraries)} libraries)",
    }


def trigger_kavita_sync_now(current_values: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run an immediate Kavita sync using current form values."""
    result = run_kavita_sync(current_values or {})
    if not result.get("success"):
        return {"success": False, "message": result.get("error", "Sync failed")}
    return {
        "success": True,
        "message": (
            f"Synced {result['books']} books across {result['series']} series "
            f"from {result['libraries']} libraries"
        ),
    }


@register_settings("kavita", "Kavita", icon="book-open", order=7)
def kavita_settings() -> list[SettingsField]:
    """Kavita connection and library-sync settings."""
    return [
        HeadingField(
            key="kavita_connection_heading",
            title="Connection",
            description=(
                "Connect Shelfmark to your Kavita server. The API key is found in "
                "Kavita under User Settings → 3rd Party Clients."
            ),
        ),
        TextField(
            key="KAVITA_URL",
            label="Kavita URL",
            description="Base URL of your Kavita instance.",
            placeholder="http://kavita:5000",
        ),
        PasswordField(
            key="KAVITA_API_KEY",
            label="API Key",
            description="Admin API key used for library sync and SSO validation. Get it from Kavita → Settings → Auth Keys / OPDS → New Auth Key.",
        ),
        ActionButton(
            key="test_kavita",
            label="Test Connection",
            description="Verify the Kavita URL and API key.",
            style="primary",
            callback=check_kavita_connection,
        ),
        HeadingField(
            key="kavita_sync_heading",
            title="Library Sync",
            description=(
                "Periodically scan Kavita libraries so Shelfmark can mark books and "
                "series already in your library as available."
            ),
        ),
        CheckboxField(
            key="KAVITA_SYNC_ENABLED",
            label="Enable Scheduled Sync",
            description="Run the Kavita library sync on the cron schedule below.",
            default=False,
        ),
        TextField(
            key="KAVITA_SYNC_CRON",
            label="Sync Schedule (cron)",
            description="5-field cron expression. Default '0 * * * *' runs hourly.",
            placeholder=DEFAULT_CRON,
            default=DEFAULT_CRON,
        ),
        CheckboxField(
            key="KAVITA_SYNC_ON_DOWNLOAD",
            label="Sync After Download Completes",
            description=(
                "In addition to the schedule, trigger a sync shortly after each "
                "download finishes (debounced)."
            ),
            default=False,
        ),
        MultiSelectField(
            key="KAVITA_SYNC_LIBRARY_IDS",
            label="Libraries to Sync",
            description="Limit the sync to specific libraries. Leave empty to sync all.",
            options=get_kavita_library_options,
            variant="dropdown",
            default=[],
        ),
        ActionButton(
            key="sync_now",
            label="Sync Now",
            description="Run a full Kavita library sync immediately.",
            style="default",
            callback=trigger_kavita_sync_now,
        ),
    ]


def _on_save_kavita(values: dict[str, Any]) -> dict[str, Any]:
    """Validate the cron expression and apply the new schedule."""
    cron = values.get("KAVITA_SYNC_CRON")
    if cron is not None and str(cron).strip():
        try:
            validate_cron(str(cron))
        except (ValueError, TypeError):
            return {
                "error": True,
                "message": f"Invalid cron expression: {cron}",
            }

    enabled = values.get("KAVITA_SYNC_ENABLED")
    if enabled is None:
        enabled = app_config.get("KAVITA_SYNC_ENABLED", False)
    expression = values.get("KAVITA_SYNC_CRON") or app_config.get("KAVITA_SYNC_CRON", DEFAULT_CRON)

    try:
        reschedule(enabled=coerce_bool(enabled), expression=str(expression or DEFAULT_CRON))
    except Exception:  # noqa: BLE001 - never block a settings save on scheduler errors
        logger.exception("Failed to apply Kavita schedule after save")

    return {"error": False, "values": values}


register_on_save("kavita", _on_save_kavita)
