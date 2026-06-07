"""Best-effort Audiobookshelf user provisioning triggered by Kavita SSO."""

from __future__ import annotations

from shelfmark.core.config import config
from shelfmark.core.logger import setup_logger
from shelfmark.core.request_helpers import coerce_bool
from shelfmark.integrations.audiobookshelf.client import abs_create_user, abs_user_exists
from shelfmark.integrations.audiobookshelf.sync import build_abs_config

logger = setup_logger(__name__)


def provision_abs_user(username: str, password: str) -> None:
    """Create *username* in Audiobookshelf if missing. Never raises.

    Gated by ``KAVITA_PROVISION_ABS_USERS`` and a configured Audiobookshelf.
    Any failure (unreachable, bad key, API error) is logged and swallowed so it
    can never block the Kavita login.
    """
    if not coerce_bool(config.get("KAVITA_PROVISION_ABS_USERS", False)):
        return
    if not (username or "").strip() or not password:
        return

    try:
        cfg = build_abs_config()
        if not cfg.base_url or not cfg.api_key:
            return
        if abs_user_exists(cfg, username):
            logger.debug("Audiobookshelf user '%s' already exists; skipping provisioning", username)
            return
        abs_create_user(cfg, username, password)
        logger.info("Provisioned Audiobookshelf user '%s' via Kavita SSO", username)
    except Exception as exc:  # noqa: BLE001 - provisioning must never block login
        logger.warning("Audiobookshelf auto-provisioning failed for '%s': %s", username, exc)
