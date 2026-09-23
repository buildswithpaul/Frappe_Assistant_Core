# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Admin user management -- listing, adding, suspending, and deregistering AR users."""

import frappe
from frappe import _

from ._helpers import _not_registered_error, _require_system_manager, _safe_error
from .auth import _ar_user_id


def _notify_invited_user(user_id: str, user_role: str | None, invited_by: str, *, is_resend: bool = False):
    """Send a Desk (bell) notification to a freshly-invited user.

    Fail-safe: a notification problem must never fail the invite, which has
    already succeeded on the AR backend. If the email has no enabled User on
    this site, Frappe silently skips it (can't notify a non-user).
    """
    try:
        from frappe.desk.doctype.notification_log.notification_log import (
            enqueue_create_notification,
        )

        # Map the wire-role "User" to the human-facing "Member" label used
        # throughout the UI; pass any other role through unchanged.
        role_label = "Member" if (user_role or "User") in ("User", "Member") else user_role
        spa_url = frappe.utils.get_url("/copilot")
        inviter_name = frappe.utils.get_fullname(invited_by) or invited_by

        if is_resend:
            subject = _("Reminder: you've been invited to the assistant team")
        else:
            subject = _("You've been invited to the assistant team")

        body = _(
            "{0} invited you to the assistant workspace as {1}. "
            "Open the assistant and start chatting to join."
        ).format(inviter_name, role_label)

        enqueue_create_notification(
            user_id,
            {
                "type": "Alert",
                "subject": subject,
                "email_content": body,
                "from_user": invited_by,
                "link": spa_url,
            },
        )
    except Exception:
        # No message arg: frappe.log_error captures the active traceback.
        frappe.log_error(title="FACO Invite Notification")


@frappe.whitelist(methods=["GET"])
def list_users(status: str | None = None, limit: int = 50, offset: int = 0):
    """
    List all AR users for this tenant.

    Admin only - returns all registered users with their status and activity.
    Used by Settings > Users tab to manage registered users.

    Args:
            status: Optional filter by status (Active, Suspended, Revoked)
            limit: Maximum results per page (default 50)
            offset: Pagination offset

    Returns:
            dict: {
                    "users": [...],
                    "pagination": {...}
            }
    """
    _require_system_manager()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        result = client.list_users(status=status, limit=int(limit), offset=int(offset))

        return result

    except Exception as e:
        frappe.log_error(title="FACO User Management Error", message=f"Error listing users: {e!s}")
        return {"error": _safe_error(e, "FACO User Management Error")}


@frappe.whitelist(methods=["GET"])
def get_user_limit_status():
    """
    Get user count and limits for the tenant.

    Admin only - returns current user count vs plan limit.
    Used to show user limit card in Settings > Users tab.

    Returns:
            dict: {
                    "plan": "Starter",
                    "max_users": 5,
                    "active_users": 3,
                    "remaining": 2,
                    "is_unlimited": false
            }
    """
    _require_system_manager()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        result = client.get_user_limit_status()

        # Enrich with seat billing info from tenant_info. The AR
        # `get_tenant_info` endpoint returns billing fields nested under
        # `subscription`; older AR builds may put a few flat fields at
        # the top level, so we fall back to the envelope when the
        # subscription dict is absent. `price_per_user` is
        # currency-resolved on the AR side (INR via Razorpay, USD via
        # Stripe); `price_per_user_usd` is the legacy USD-only field.
        try:
            tenant_info = client.get_tenant_info() or {}
            sub = tenant_info.get("subscription") or tenant_info
            result["min_users"] = sub.get("min_users", 1)
            result["price_per_user"] = sub.get("price_per_user") or sub.get("price_per_user_usd") or 0
            result["credits_per_user"] = sub.get("credits_per_user", 0)
            result["currency"] = sub.get("currency") or "USD"
            result["is_per_user"] = bool(sub.get("is_per_user"))
            result["estimated_monthly_bill"] = sub.get("estimated_monthly_bill") or {}
            result["credit_quota"] = sub.get("credit_quota") or 0
        except Exception as e:
            frappe.log_error(
                title="FACO User Management Error",
                message=f"Failed to enrich user limit with tenant info: {e!s}",
            )

        return result

    except Exception as e:
        frappe.log_error(
            title="FACO User Management Error", message=f"Error getting user limit status: {e!s}"
        )
        return {"error": _safe_error(e, "FACO User Management Error")}


@frappe.whitelist(methods=["POST"])
def suspend_user(user_id: str | None = None):
    """
    Suspend a user (disable their access).

    Admin only - temporarily blocks a user from using FACO.
    The user's MCP servers remain configured.
    User will auto-reactivate when they reconnect.

    Args:
            user_id: User identifier to suspend

    Returns:
            dict: {"success": true, "message": "User suspended"}
    """
    _require_system_manager()

    if not user_id:
        return {"error": "user_id is required"}

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        result = client.suspend_user(user_id)

        return result

    except Exception as e:
        frappe.log_error(title="FACO User Management Error", message=f"Error suspending user: {e!s}")
        return {"error": _safe_error(e, "FACO User Management Error")}


@frappe.whitelist(methods=["POST"])
def deregister_user(user_id: str | None = None):
    """
    Permanently delete a user and their MCP server configurations.

    Admin only - IRREVERSIBLE action.
    Removes user record, MCP servers, and OAuth tokens.
    Conversations are retained for audit trail.

    Args:
            user_id: User identifier to delete

    Returns:
            dict: {
                    "success": true,
                    "user_id": "user@example.com",
                    "deleted_mcp_servers": 2,
                    "message": "User deregistered successfully"
            }
    """
    _require_system_manager()

    if not user_id:
        return {"error": "user_id is required"}

    # Prevent self-deletion (compare on the AR email identity, since the target
    # user_id is an email while session.user may be a docname like Administrator)
    if _ar_user_id(user_id) == _ar_user_id(frappe.session.user):
        return {"error": "Cannot delete your own user account"}

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        result = client.deregister_user(user_id)

        return result

    except Exception as e:
        frappe.log_error(title="FACO User Management Error", message=f"Error deregistering user: {e!s}")
        return {"error": _safe_error(e, "FACO User Management Error")}


@frappe.whitelist(methods=["POST"])
def add_user(user_id: str | None = None):
    """
    Admin-only: Register a Frappe user with FACO/AR.

    Creates the AR Tenant User, OAuth tokens, and MCP server connection
    so the user can start using FACO immediately upon next login.

    Args:
            user_id: Frappe user ID (email) to register

    Returns:
            dict: {"success": bool, "user_id": str, "message": str}
    """
    _require_system_manager()

    if not user_id:
        return {"success": False, "error": _("User ID is required")}

    if not frappe.db.exists("User", user_id):
        return {"success": False, "error": _("User {0} does not exist").format(user_id)}

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        from .auth import (
            _generate_oauth_tokens_for_user,
            _get_or_create_ar_oauth_client,
            _get_user_context,
        )

        client = get_fac_cloud_client()
        if not client:
            return {"success": False, "error": _not_registered_error()}

        # AR keys tenant users by email; the OAuth Bearer Token keys by the
        # Frappe docname (the MCP endpoint does frappe.set_user on it).
        ar_user_id = _ar_user_id(user_id)
        registered_by = _ar_user_id(frappe.session.user)

        site_url = frappe.utils.get_url()
        fac_endpoint = f"{site_url}/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp"

        # Step 1: Register user with AR (idempotent)
        context = _get_user_context(ar_user_id)
        user_result = client.register_user(user_id=ar_user_id, registered_by=registered_by, **context)
        if not user_result or not user_result.get("user_id"):
            return {"success": False, "error": "Failed to register user with FAC Cloud"}

        # Step 2: Create OAuth tokens for this user (keyed by Frappe docname)
        oauth_client = _get_or_create_ar_oauth_client()
        tokens = _generate_oauth_tokens_for_user(oauth_client, user_id)

        # Step 3: Register MCP server so user is ready for streaming (keyed by email)
        client.add_user_mcp_server(
            user_id=ar_user_id,
            server_name="Main Frappe Site",
            endpoint_url=fac_endpoint,
            transport_type="HTTP",
            auth_type="OAuth",
            oauth_client_id=tokens["client_id"],
            oauth_client_secret=tokens["client_secret"],
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_expires_in=tokens["expires_in"],
            managed=True,
        )

        return {
            "success": True,
            "user_id": user_id,
            "message": _("User {0} added successfully").format(user_id),
        }

    except Exception as e:
        frappe.log_error(title="FACO Add User", message=f"Failed to add user {user_id}: {e!s}")
        return {"success": False, "error": _safe_error(e, "FACO Add User")}


@frappe.whitelist(methods=["GET"])
def get_available_users():
    """
    Admin-only: List Frappe users not yet registered with FACO/AR.

    Compares active Frappe System Users against AR's registered user list
    to find users eligible for registration.

    Returns:
            dict: {"users": [{"user_id": str, "full_name": str}, ...]}
    """
    _require_system_manager()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"users": []}

        # Get all active Frappe system users (exclude Guest, Administrator)
        frappe_users = frappe.get_all(
            "User",
            filters={
                "enabled": 1,
                "user_type": "System User",
                "name": ["not in", ["Guest", "Administrator"]],
            },
            fields=["name", "full_name", "email"],
            order_by="full_name asc",
        )

        # Get already registered AR users
        registered_ids = set()
        try:
            ar_users_result = client.list_users(limit=500)
            if ar_users_result and ar_users_result.get("users"):
                for u in ar_users_result["users"]:
                    registered_ids.add(u.get("user_id"))
        except Exception:
            registered_ids = set()

        # Filter out already registered users
        available = [
            {"user_id": u.name, "full_name": u.full_name or u.name}
            for u in frappe_users
            if u.name not in registered_ids
        ]

        return {"users": available}

    except Exception as e:
        frappe.log_error(title="FACO User Management Error", message=f"Error getting available users: {e!s}")
        return {"users": []}


@frappe.whitelist(methods=["POST"])
def set_user_credit_limit(user_id: str | None = None, monthly_credit_limit: float | int | None = None):
    """
    Admin-only: Set a per-user monthly credit limit.

    Args:
            user_id: User identifier
            monthly_credit_limit: Credit cap (0 = no limit, shared pool)

    Returns:
            dict: {"success": True, "monthly_credit_limit": ...}
    """
    _require_system_manager()

    if not user_id:
        return {"error": "user_id is required"}

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        return client.set_user_credit_limit(
            user_id,
            float(monthly_credit_limit or 0),
            acted_by=_ar_user_id(frappe.session.user),
        )

    except Exception as e:
        frappe.log_error(
            title="FACO User Management Error", message=f"Error setting credit limit for {user_id}: {e!s}"
        )
        return {"error": _safe_error(e, "FACO User Management Error")}


@frappe.whitelist(methods=["GET"])
def get_my_credit_status():
    """
    Get credit usage status for the current user.

    Available to ALL users (not admin-only). Returns the calling user's
    credit limit and usage within the team pool.

    Returns:
            dict: {"monthly_credit_limit": ..., "credits_used_this_month": ..., ...}
    """
    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        return client.get_my_credit_status(_ar_user_id(frappe.session.user))

    except Exception as e:
        frappe.log_error(title="FACO User Management Error", message=f"Error getting credit status: {e!s}")
        return {"error": _safe_error(e, "FACO User Management Error")}


@frappe.whitelist(methods=["POST"])
def invite_user(user_id: str | None = None, user_role: str | None = None):
    """
    Admin-only: invite an existing site user as a Pending member.

    Reserves a billed seat immediately; the invite auto-activates on the
    user's first activity. The acting admin is recorded as ``invited_by``.

    Args:
            user_id: Frappe user ID (email) to invite
            user_role: Optional role to assign on activation

    Returns:
            dict: {"success": bool, "user_id": str, "status": "Pending"}
    """
    _require_system_manager()

    if not user_id:
        return {"success": False, "error": _("User ID is required")}

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"success": False, "error": _not_registered_error()}

        # AR authority check keys on email; the Desk notification's from_user
        # is a Link to User and needs the Frappe docname.
        result = client.invite_user(user_id, user_role=user_role, invited_by=_ar_user_id(frappe.session.user))
        if result and result.get("success"):
            _notify_invited_user(user_id, user_role, frappe.session.user)
        return result

    except Exception as e:
        frappe.log_error(title="FACO Invite User", message=f"Failed to invite {user_id}: {e!s}")
        return {"success": False, "error": _safe_error(e, "FACO Invite User")}


@frappe.whitelist(methods=["POST"])
def revoke_invite(user_id: str | None = None):
    """
    Admin-only: revoke a Pending invite, freeing its reserved seat.

    Only Pending invites can be revoked; use ``deregister_user`` to remove an
    active member. The acting admin is recorded as ``revoked_by``.

    Args:
            user_id: User identifier whose invite to revoke

    Returns:
            dict: {"success": bool}
    """
    _require_system_manager()

    if not user_id:
        return {"success": False, "error": _("User ID is required")}

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"success": False, "error": _not_registered_error()}

        return client.revoke_invite(user_id, revoked_by=_ar_user_id(frappe.session.user))

    except Exception as e:
        frappe.log_error(title="FACO Revoke Invite", message=f"Failed to revoke invite {user_id}: {e!s}")
        return {"success": False, "error": _safe_error(e, "FACO Revoke Invite")}


@frappe.whitelist(methods=["POST"])
def resend_invite(user_id: str | None = None):
    """
    Admin-only: resend a Pending invite, restarting its expiry window.

    The acting admin is recorded as ``resent_by``.

    Args:
            user_id: User identifier whose invite to resend

    Returns:
            dict: {"success": bool}
    """
    _require_system_manager()

    if not user_id:
        return {"success": False, "error": _("User ID is required")}

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"success": False, "error": _not_registered_error()}

        # AR authority check keys on email; the Desk notification's from_user
        # is a Link to User and needs the Frappe docname.
        result = client.resend_invite(user_id, resent_by=_ar_user_id(frappe.session.user))
        if result and result.get("success"):
            _notify_invited_user(user_id, None, frappe.session.user, is_resend=True)
        return result

    except Exception as e:
        frappe.log_error(title="FACO Resend Invite", message=f"Failed to resend invite {user_id}: {e!s}")
        return {"success": False, "error": _safe_error(e, "FACO Resend Invite")}


@frappe.whitelist(methods=["GET"])
def list_invites():
    """
    Admin-only: list all Pending invites for this tenant.

    Each entry includes the invited-by actor and invite timing.

    Returns:
            dict: {"invites": [...]}
    """
    _require_system_manager()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        return client.list_invites()

    except Exception as e:
        frappe.log_error(title="FACO User Management Error", message=f"Error listing invites: {e!s}")
        return {"error": _safe_error(e, "FACO User Management Error")}


@frappe.whitelist(methods=["GET"])
def get_member_audit_log(limit: int = 100, offset: int = 0):
    """
    Admin-only: get the member-management audit log (newest first, paginated).

    Returns only member-management actions — never GDPR/append-only rows.

    Args:
            limit: Maximum results per page (default 100)
            offset: Pagination offset

    Returns:
            dict: {"entries": [...]}
    """
    _require_system_manager()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        return client.get_member_audit_log(limit=int(limit), offset=int(offset))

    except Exception as e:
        frappe.log_error(title="FACO User Management Error", message=f"Error getting member audit log: {e!s}")
        return {"error": _safe_error(e, "FACO User Management Error")}
