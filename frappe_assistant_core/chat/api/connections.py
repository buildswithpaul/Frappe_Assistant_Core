# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Per-user MCP connection management for the FAC Chat SPA."""

import frappe
from frappe import _

from frappe_assistant_core.chat.api.auth import _ar_user_id
from frappe_assistant_core.chat.gate import is_chat_enabled

RESERVED_MANAGED_NAME = "Main Frappe Site"


def _client():
    from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

    client = get_fac_cloud_client()
    if not client:
        frappe.throw(_("Not connected to FAC Cloud"))
    return client


def _assert_chat_access() -> None:
    """Refuse the action outright if FAC Chat is off or the caller isn't a
    FACO member — mirrors voice.py's gate exactly. These are account-
    management actions, not display endpoints, so there is no soft-degrade
    path: an ungated user must not be able to add or remove a connection.
    """
    from frappe_assistant_core.chat.api.settings.access import _is_faco_member

    if not is_chat_enabled():
        frappe.throw(_("FAC Chat is disabled."), frappe.PermissionError)
    if not _is_faco_member(frappe.session.user):
        frappe.throw(_("You are not enabled for FACO."), frappe.PermissionError)


@frappe.whitelist(methods=["GET"])
def list_connections() -> dict:
    """Every MCP connection belonging to the current user, managed one first."""
    _assert_chat_access()
    user_id = _ar_user_id(frappe.session.user)
    payload = _client().get_user_mcp_servers(user_id=user_id) or {}
    rows = payload.get("mcp_servers") or []

    for row in rows:
        row["managed"] = bool(row.get("managed"))

    rows.sort(key=lambda r: (not r["managed"], (r.get("server_name") or "").lower()))
    return {"connections": rows, "ar_unreachable": bool(payload.get("_ar_unreachable"))}


def _assert_removable(server_name: str, action: str = "removed") -> None:
    """The FAC connection is provisioned automatically and cannot be removed
    or disabled.

    AR enforces this too; failing here keeps the round trip cheap and the
    message specific.
    """
    for row in list_connections()["connections"]:
        if row.get("server_name") == server_name and row.get("managed"):
            frappe.throw(
                _("Your Frappe site connection is managed automatically and cannot be {0}.").format(_(action))
            )


@frappe.whitelist(methods=["POST"])
def remove_connection(server_name: str) -> dict:
    _assert_chat_access()
    _assert_removable(server_name)
    _client().remove_user_mcp_server(user_id=_ar_user_id(frappe.session.user), server_name=server_name)
    return {"success": True}


@frappe.whitelist(methods=["POST"])
def set_connection_enabled(server_name: str, enabled: int) -> dict:
    _assert_chat_access()
    if not int(enabled):
        _assert_removable(server_name, "disabled")
    _client().enable_mcp_server(
        user_id=_ar_user_id(frappe.session.user), server_name=server_name, enabled=bool(int(enabled))
    )
    return {"success": True}


@frappe.whitelist(methods=["POST"])
def test_connection(server_name: str) -> dict:
    _assert_chat_access()
    return _client().test_mcp_server(user_id=_ar_user_id(frappe.session.user), server_name=server_name)


@frappe.whitelist(methods=["POST"])
def set_tool_visibility(server_name: str, blocked_tools: list = None) -> dict:
    """Hide tools on one server. Allowed on the managed connection too:
    non-removable does not mean non-configurable."""
    _assert_chat_access()
    _client().set_mcp_server_tools(
        user_id=_ar_user_id(frappe.session.user),
        server_name=server_name,
        blocked_tools=blocked_tools or [],
    )
    return {"success": True}


@frappe.whitelist(methods=["POST"])
def add_connection(
    server_name: str,
    endpoint_url: str,
    auth_type: str = "None",
    api_key: str = None,
    api_key_header: str = None,
) -> dict:
    """Add a bring-your-own MCP server. Never sets managed."""
    _assert_chat_access()
    if server_name == RESERVED_MANAGED_NAME:
        frappe.throw(
            _('"{0}" is reserved for your managed Frappe site connection. Choose a different name.').format(
                RESERVED_MANAGED_NAME
            )
        )
    return _client().add_user_mcp_server(
        user_id=_ar_user_id(frappe.session.user),
        server_name=server_name,
        endpoint_url=endpoint_url,
        auth_type=auth_type,
        api_key=api_key,
        api_key_header=api_key_header,
        transport_type="HTTP",
    )


def _blank_to_none(value: str = None) -> str | None:
    """A blank manual client_id must not reach AR: it would record an empty
    manual registration instead of leaving the DCR path open."""
    cleaned = (value or "").strip()
    return cleaned or None


@frappe.whitelist(methods=["POST"])
def begin_connect(
    endpoint_url: str,
    client_id: str = None,
    client_secret: str = None,
) -> dict:
    """Start a server-side connect attempt and return AR's preflight.

    ``client_id``/``client_secret`` are the no-DCR escape hatch — supplied only
    after the user registered AR's redirect URI with the authorization server
    by hand.
    """
    _assert_chat_access()
    return _client().begin_mcp_connect(
        endpoint_url=endpoint_url,
        user_id=_ar_user_id(frappe.session.user),
        client_id=_blank_to_none(client_id),
        client_secret=_blank_to_none(client_secret),
    )


@frappe.whitelist(methods=["GET"])
def get_connect_session(handle: str) -> dict:
    """Read an in-flight connect session. Drives the wizard's reconstruction
    from the ``?connect=<handle>`` deep link after the OAuth round trip.

    A verbatim passthrough of AR's payload — in particular
    ``reauth_server_name``, which is how the wizard learns the handle belongs
    to a reconnect rather than an add. Do not project a subset of keys here:
    dropping that one sends a reconnect down the add path, where the wizard's
    duplicate-name check refuses a name the user is not changing.
    """
    _assert_chat_access()
    return _client().get_mcp_connect_session(handle=handle, user_id=_ar_user_id(frappe.session.user))


@frappe.whitelist(methods=["POST"])
def commit_connect(handle: str, server_name: str) -> dict:
    """Turn an authorized session into a real connection."""
    _assert_chat_access()
    if server_name == RESERVED_MANAGED_NAME:
        frappe.throw(
            _('"{0}" is reserved for your managed Frappe site connection. Choose a different name.').format(
                RESERVED_MANAGED_NAME
            )
        )
    return _client().commit_mcp_connect(
        handle=handle,
        server_name=server_name,
        user_id=_ar_user_id(frappe.session.user),
    )


@frappe.whitelist(methods=["POST"])
def abandon_connect(handle: str) -> dict:
    """Drop an in-flight session and the credentials escrowed in it."""
    _assert_chat_access()
    return _client().abandon_mcp_connect(handle=handle, user_id=_ar_user_id(frappe.session.user))


@frappe.whitelist(methods=["POST"])
def begin_reauth(server_name: str) -> dict:
    """Re-authorize a connection that already exists.

    Distinct from ``begin_connect``: AR opens the session with ``reauth_target``
    pointing at this row, so ``commit_connect`` refreshes its credentials in
    place and returns it to ``Active`` instead of inserting a second row and
    failing the duplicate-name guard.
    """
    _assert_chat_access()
    if server_name == RESERVED_MANAGED_NAME:
        frappe.throw(
            _('"{0}" is your managed Frappe site connection and reconnects itself.').format(
                RESERVED_MANAGED_NAME
            )
        )
    return _client().begin_mcp_reauth(server_name=server_name, user_id=_ar_user_id(frappe.session.user))
