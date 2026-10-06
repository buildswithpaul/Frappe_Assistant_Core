# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Server-side sign-out state for the FAC mobile app (spec §8.3).

Frappe inserts a new OAuth Bearer Token row on every refresh and never revokes
the previous one, and ``create_web_session`` plants a desk ``sid`` in the app's
WebView. Signing out on the phone alone leaves both alive, so sign-out asks the
server to end every Active token of (user, this device's client) and the desk
sessions minted for that client, never the user's browser sessions.
"""

from contextlib import suppress

import frappe
import redis
from frappe import _
from frappe.sessions import delete_session, get_expiry_in_seconds

from frappe_assistant_core.utils.mcp_caller import presented_bearer_token

MOBILE_APP_NAME = "FACO Mobile"
SIGN_OUT_REASON = "Signed out of the FAC mobile app"


def _web_sessions_key(user: str) -> str:
    return f"fac_mobile_web_sessions:{user}"


def _presented_bearer() -> str:
    token = presented_bearer_token()
    if not token:
        frappe.throw(_("This endpoint requires OAuth Bearer authentication"), frappe.AuthenticationError)
    return token


def mobile_client_of_request(require_active: bool = True) -> str:
    """The FAC mobile OAuth client whose bearer token authenticated this request.

    API keys, session cookies and every other OAuth client are refused, the
    FAC Cloud integration client included. Sign-out passes
    ``require_active=False`` so that a repeat call, made after it revoked the
    presenting token, still resolves the same client and changes nothing.
    """
    token = frappe.db.get_value(
        "OAuth Bearer Token",
        {"access_token": _presented_bearer()},
        ["client", "user", "status"],
        as_dict=True,
    )
    if not token or token.user != frappe.session.user or (require_active and token.status != "Active"):
        frappe.throw(_("Invalid bearer token"), frappe.AuthenticationError)
    if frappe.db.get_value("OAuth Client", token.client, "app_name") != MOBILE_APP_NAME:
        frappe.throw(_("This OAuth client is not allowed to use this endpoint"), frappe.PermissionError)
    return token.client


def record_web_session(user: str, sid: str, client: str) -> None:
    """Remember a desk session ``create_web_session`` minted, tagged with its client.

    The record lives twice the session expiry, because a desk session slides on
    activity; ``end_web_sessions`` only ends sids that still have a live row.
    """
    key = _web_sessions_key(user)
    frappe.cache.hset(key, sid, client)
    # Native EXPIRE on the site-prefixed key hset wrote; Frappe v15 has no expire_key.
    with suppress(redis.exceptions.ConnectionError):
        frappe.cache.expire(frappe.cache.make_key(key), 2 * get_expiry_in_seconds())


def end_web_sessions(user: str, client: str) -> int:
    """End the desk sessions minted for ``client``; returns how many were still live.

    Fails open: when the cache cannot be read it ends nothing and returns 0, so a
    cache outage never costs the caller's token revocation (the device clears its
    own sid). The Error Log gets a fixed message, never a traceback with locals.
    """
    key = _web_sessions_key(user)
    try:
        recorded = frappe.cache.hgetall(key)
    except redis.exceptions.RedisError as exc:
        frappe.log_error(
            title="FAC mobile sign-out: desk sessions not ended (cache unavailable)",
            message=f"{type(exc).__name__} while reading the recorded desk sessions; the tokens were revoked.",
            reference_doctype="OAuth Client",
            reference_name=client,
        )
        return 0
    minted = [frappe.safe_decode(sid) for sid, owner in recorded.items() if owner == client]
    if not minted:
        return 0

    sessions = frappe.qb.DocType("Sessions")
    live = (
        frappe.qb.from_(sessions)
        .select(sessions.sid)
        .where((sessions.user == user) & sessions.sid.isin(minted))
        .run(pluck=True)
    )
    for sid in live:
        delete_session(sid, user=user, reason=SIGN_OUT_REASON)
    # One field per call: Frappe v15's hdel takes a single key. hdel suppresses only
    # ConnectionError, and a timeout here must not roll back the revocation either.
    for sid in minted:
        with suppress(redis.exceptions.RedisError):
            frappe.cache.hdel(key, sid)
    return len(live)


def revoke_client_tokens(user: str, client: str) -> int:
    """Revoke every Active bearer token of (user, client), earlier refreshes included."""
    active = frappe.get_all(
        "OAuth Bearer Token",
        filters={"user": user, "client": client, "status": "Active"},
        pluck="name",
    )
    if active:
        frappe.db.set_value("OAuth Bearer Token", {"name": ("in", active)}, "status", "Revoked")
    return len(active)
