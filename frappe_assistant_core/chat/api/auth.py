# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Registration, OAuth, and MCP Server management APIs."""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit

from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client
from frappe_assistant_core.chat.gate import is_chat_enabled

from ._helpers import _safe_error


def _get_or_create_ar_oauth_client():
    """
    Get or create an OAuth Client for FAC Cloud to use when calling this site.

    This OAuth client allows FAC Cloud to authenticate when calling our MCP endpoint.
    Follows the same pattern as standard Frappe OAuth clients (e.g., Postman).

    Returns:
            OAuth Client document
    """
    # Dedupe on a stable client_id — NOT on a phantom field. The core OAuth
    # Client doctype has no `client_name` column, so the old
    # exists(... {"client_name": ...}) filter never matched and minted a fresh
    # client on every call, orphaning the per-user OAuth Bearer Tokens that key
    # on the client's docname (a FALSE NEGATIVE in the FACO membership gate).
    #
    # The controller forces `client_id = name` (client_id is read-only) on every
    # validate() and the doctype names by random hash, so a stable client_id
    # requires pinning the DOCNAME. We pin it with insert(set_name=...) so
    # `name == client_id == CLIENT_ID` in a SINGLE write, and the dedup below
    # then matches on every subsequent call. Pre-fix "FAC Cloud" rows (random
    # names) are left inert — they still own any tokens issued against them and
    # self-heal as those tokens roll over; they can be cleaned up manually. We
    # never auto-delete live rows.
    CLIENT_ID = "fac-cloud-integration"

    existing = frappe.db.get_value("OAuth Client", {"client_id": CLIENT_ID}, "name")
    if existing:
        return frappe.get_doc("OAuth Client", existing)

    settings = frappe.get_single("FAC Chat Settings")
    fac_cloud_url = settings.fac_cloud_url
    if not fac_cloud_url:
        frappe.throw(_("FAC Cloud URL not configured in FAC Chat Settings"), title=_("Configuration Error"))
    callback_uri = f"{fac_cloud_url}/api/oauth/callback"

    client = frappe.get_doc(
        {
            "doctype": "OAuth Client",
            "app_name": "FAC Cloud",
            "scopes": "all openid",
            "redirect_uris": callback_uri,
            "default_redirect_uri": callback_uri,
            "grant_type": "Authorization Code",
            "response_type": "Code",
            "skip_authorization": 1,
            "token_endpoint_auth_method": "Client Secret Post",
            "allowed_roles": [{"role": "All"}],
        }
    )
    # OAuth Client names by random hash and forces client_id = name (read-only
    # in validate()). Pin the docname so the client_id is stable and this
    # get-or-create is idempotent — set_name does this in a single insert,
    # avoiding an insert→rename→save round-trip and its half-named failure window.
    try:
        client.insert(set_name=CLIENT_ID, ignore_permissions=True)
    except frappe.DuplicateEntryError:
        # Lost a cold-start race (concurrent first-time mint) or a row already
        # holds the canonical name — converge on the existing canonical client.
        pass
    return frappe.get_doc("OAuth Client", CLIENT_ID)


def _generate_oauth_tokens_for_user(oauth_client, user=None):
    """
    Generate OAuth Bearer Token for a specific user.

    Creates an OAuth Bearer Token document directly, bypassing the redirect flow.
    Used for per-user MCP server authentication.

    Args:
            oauth_client: The OAuth Client document
            user: User ID to generate tokens for (defaults to current user)

    Returns:
            dict with access_token, refresh_token, expires_in plus client credentials for refresh
    """
    import secrets

    from frappe.utils import add_to_date, now_datetime

    site_url = frappe.utils.get_url()
    if not user:
        user = frappe.session.user

    # Generate secure token values
    access_token = secrets.token_urlsafe(64)
    refresh_token = secrets.token_urlsafe(64)
    # FACO-M14: tighten bearer TTL from 30 days to 1 hour. AR already knows
    # how to refresh via refresh_token (returned below), so a leaked access
    # token is useful for at most 60 minutes instead of a month.
    expires_in = 3600

    # Delete any existing tokens for this client/user to avoid conflicts
    existing_tokens = frappe.get_all(
        "OAuth Bearer Token", filters={"client": oauth_client.name, "user": user}, pluck="name"
    )
    for token_name in existing_tokens:
        frappe.delete_doc("OAuth Bearer Token", token_name, ignore_permissions=True)

    # Create OAuth Bearer Token document
    token_doc = frappe.get_doc(
        {
            "doctype": "OAuth Bearer Token",
            "client": oauth_client.name,
            "user": user,
            "scopes": oauth_client.scopes or "all openid",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": expires_in,
            "expiration_time": add_to_date(now_datetime(), seconds=expires_in),
        }
    )
    token_doc.insert(ignore_permissions=True)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": expires_in,
        "scope": oauth_client.scopes or "all openid",
        # Include client credentials for AR to refresh tokens
        "client_id": oauth_client.client_id,
        "client_secret": oauth_client.get_password("client_secret"),
        "token_url": f"{site_url}/api/method/frappe.integrations.oauth2.get_token",
    }


# Keep legacy alias for backwards compatibility
def _generate_oauth_tokens_for_ar(oauth_client):
    """Legacy alias - use _generate_oauth_tokens_for_user instead."""
    return _generate_oauth_tokens_for_user(oauth_client)


# ============================================================================
# User Context Helpers
# ============================================================================


_FRAPPE_PLACEHOLDER_EMAILS = frozenset({"admin@example.com", "guest@example.com"})


def _is_placeholder_email(email) -> bool:
    """True for the addresses Frappe stamps on every site at install.

    `frappe/utils/install.py` gives User "Administrator" the email
    `admin@example.com` and "Guest" `guest@example.com`, and `bench new-site`
    has no option to set a real one. They are shared by every Frappe install
    in existence and, being under an RFC 2606 reserved domain, can never
    receive mail — so they identify nobody. Frappe treats the same pair as
    non-addresses in `core/doctype/role/role.py`.
    """
    return str(email or "").strip().lower() in _FRAPPE_PLACEHOLDER_EMAILS


def _ar_user_id(user=None):
    """Resolve a Frappe user to the email AR keys its AR Tenant User by.

    AR identifies tenant users by email. For ordinary staff the Frappe username
    already IS their email, so this is a pass-through. The account that differs
    is Administrator (username "Administrator"), which must resolve to its
    User.email so the site owner is recognized as the tenant owner on AR rather
    than orphaned under a non-email username. Falls back to the raw username
    only if the User carries no email (should not happen for a real login).

    This deliberately still returns Frappe's `admin@example.com` placeholder
    when that is what the User carries. Resolution has to stay total: every AR
    read path goes through here (membership, boot, privacy, streaming), and
    tenants already registered under the placeholder would lose their seat
    match — and their chat — the moment it resolved to anything else. The
    placeholder is rejected where it would become *durable*, at seat creation
    in `_register_user_with_ar`, not here.

    Note this is the AR-facing identity ONLY. Local OAuth Bearer Tokens still
    key on the Frappe username (the User docname) — see _register_user_with_ar.
    """
    user = user or frappe.session.user
    if "@" in str(user):
        return user
    email = frappe.db.get_value("User", user, "email")
    return email or user


def _is_tenant_owner(ar_user_id):
    """True if `ar_user_id` is this tenant's owner per AR.

    AR is the source of truth for ownership; FAC reads it from get_tenant_info
    and compares. Used to break the connect chicken-and-egg: the owner may
    self-provision before any seat exists, whereas a plain non-member must be
    added by an admin first.

    Match on `owner_user_id` — the FRAPPE identity of who registered, which is
    exactly what the connect flow sends (`_ar_user_id(session.user)`) and what
    AR's own authority check compares (`registered_by == owner_user_id`, see
    assistant_runtime .../users/registration.py). `owner_email` is a separate
    field — the billing/verification address the admin typed, which frequently
    differs from the account identity — so it is only a legacy fallback, never
    the primary key. Preferring owner_email here was a bug: it locked out the
    real owner whenever the two diverged.

    Fails CLOSED — no client, missing owner, or an AR error all return False.
    This only ever widens access (owner bypasses the seat gate), so an
    uncertain answer must not grant ownership.
    """
    try:
        client = get_fac_cloud_client()
        if not client:
            return False
        info = client.get_tenant_info() or {}
    except Exception:
        return False

    # owner_user_id is authoritative (mirrors AR's registered_by check).
    # owner_email is billing metadata, not a login identity — fall back to it
    # ONLY for a legacy tenant that has no owner_user_id at all.
    owner = info.get("owner_user_id") or info.get("owner_email")
    return bool(owner) and owner == ar_user_id


def _get_user_context(user_id):
    """
    Gather user context from Frappe to send to AR during registration.

    Extracts locale, timezone, role, and email from the Frappe User record.
    Zero user friction — uses data already available in Frappe.

    Args:
            user_id: a Frappe User docname OR the user's email (callers pass the
                    AR identity, which is the email; for staff that IS the
                    docname, but for Administrator it is not).

    Returns:
            dict with locale, timezone, user_role, email keys
    """
    # Resolve the User whether user_id is the docname or the email — registration
    # now passes the email, which is NOT the docname for the Administrator account.
    user = frappe.db.get_value(
        "User",
        user_id,
        ["name", "full_name", "language", "time_zone", "email"],
        as_dict=True,
    )
    if not user:
        user = frappe.db.get_value(
            "User",
            {"email": user_id},
            ["name", "full_name", "language", "time_zone", "email"],
            as_dict=True,
        )

    if not user:
        return {}

    roles = frappe.get_roles(user.name)
    user_role = "Admin" if "System Manager" in roles else "User"

    return {
        "display_name": user.full_name or user_id,
        "locale": user.language or frappe.local.lang,
        "timezone": user.time_zone or frappe.utils.get_time_zone(),
        "user_role": user_role,
        "email": user.email or (user_id if "@" in str(user_id) else None),
    }


# ============================================================================
# Auto-Recovery Helpers
# ============================================================================
# These functions transparently re-register users and refresh tokens when AR
# doesn't recognize a previously working user (e.g., after data cleanup).


def _ensure_user_registered(client, user_id):
    """
    Check if user is registered with AR and recover existing registrations.

    Only auto-recovers users who already exist in AR (e.g., expired tokens,
    missing MCP server). Never auto-registers new users — that requires
    admin action via add_user().

    Args:
            client: Configured AssistantRuntimeClient instance
            user_id: Frappe User docname (e.g. "Administrator" or an email).
                    The AR status check normalizes it to the user's email;
                    recovery helpers receive the docname and normalize
                    internally (OAuth tokens key on the docname).

    Returns:
            dict: {"registered": True} if user is ready,
                  {"registered": False, "needs_admin": True} if not registered
            bool: True/False for backwards compatibility in edge cases
    """
    try:
        status = client.get_user_auth_status(user_id=_ar_user_id(user_id))

        if not status:
            # No status at all — user not registered, needs admin
            return {"registered": False, "needs_admin": True}

        # Transient AR failure: don't claim "needs_admin" — we just don't
        # know right now. Returning False signals "couldn't determine".
        if status.get("_ar_unreachable"):
            return False

        user_exists = status.get("user_exists", False)

        if not user_exists:
            # User not registered in AR — don't auto-register
            return {"registered": False, "needs_admin": True}

        has_mcp = status.get("has_mcp_servers", False)
        ready = status.get("ready_for_streaming", False)

        if not has_mcp:
            # User exists but MCP server missing — auto-recover
            _do_user_recovery(client, user_id)
            return {"registered": True}

        expired = status.get("servers_with_expired_tokens", [])
        if expired:
            _do_token_refresh(client, user_id)
            return {"registered": True}

        return {"registered": True} if ready else {"registered": False, "needs_admin": True}

    except Exception as e:
        frappe.log_error(
            title="FACO Auto-Recovery", message=f"Auto-recovery check failed for {user_id}: {e!s}"
        )
        return False


def _do_user_recovery(client, user_id):
    """
    Recover an EXISTING user's MCP server and tokens.

    Only recovers users who already exist in AR (expired tokens, missing MCP).
    Never creates new users — that requires admin action via add_user().

    Args:
            client: Configured AssistantRuntimeClient instance
            user_id: Frappe User docname (e.g. "Administrator" or an email)

    Raises:
            frappe.AuthenticationError: If user doesn't exist in AR
    """
    ar_user_id = _ar_user_id(user_id)

    # Guard: only recover existing users, never create new ones.
    # If AR is briefly unreachable, throw a transient-error message rather
    # than the misleading "your account has not been set up" — we genuinely
    # don't know whether the user exists.
    status = client.get_user_auth_status(user_id=ar_user_id)
    if status and status.get("_ar_unreachable"):
        frappe.throw(
            _("Couldn't reach FAC Cloud to verify your account. Please try again in a moment."),
        )
    if not status or not status.get("user_exists"):
        frappe.logger("faco.debug").info(
            f"_do_user_recovery: user {ar_user_id} does not exist in AR, skipping recovery"
        )
        frappe.throw(
            _(
                "Your account has not been set up yet. Please ask your administrator to add you from Settings > Users."
            ),
            frappe.AuthenticationError,
        )

    site_url = frappe.utils.get_url()
    fac_endpoint = f"{site_url}/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp"

    # Step 1: Re-register user with full context (idempotent — reactivates existing)
    context = _get_user_context(ar_user_id)
    client.register_user(user_id=ar_user_id, **context)

    # Step 2: Create OAuth tokens (keyed by Frappe docname) and register MCP
    # server (keyed by email).
    oauth_client = _get_or_create_ar_oauth_client()
    tokens = _generate_oauth_tokens_for_user(oauth_client, user_id)

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
    )

    frappe.logger("faco").info(f"Auto-recovered user {ar_user_id}: re-registered + MCP server created")


def _do_token_refresh(client, user_id):
    """
    Refresh expired OAuth tokens for the user's MCP server.

    Args:
            client: Configured AssistantRuntimeClient instance
            user_id: Frappe User docname (e.g. "Administrator" or an email)
    """
    # OAuth Bearer Token keyed by Frappe docname; AR tokens keyed by email.
    oauth_client = _get_or_create_ar_oauth_client()
    tokens = _generate_oauth_tokens_for_user(oauth_client, user_id)

    client.update_mcp_server_tokens(
        user_id=_ar_user_id(user_id),
        server_name="Main Frappe Site",
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_expires_in=tokens["expires_in"],
    )

    frappe.logger("faco").info(f"Auto-refreshed tokens for user {_ar_user_id(user_id)}")


# OAuth callback must accept guest requests by definition; returns a static
# 200 with no state side effects, so it cannot leak anything.
@frappe.whitelist(allow_guest=True, methods=["GET"])  # nosemgrep: guest-whitelisted-method
def oauth_callback() -> dict:
    """
    Placeholder OAuth callback endpoint.
    Not actually used for client_credentials flow, but required by OAuth Client doctype.
    """
    return {"status": "ok"}


@frappe.whitelist(methods=["GET"])
def get_user_auth_status() -> dict:
    """
    Check if current user is ready to use FACO.

    Returns user registration status and MCP server connection status.
    Used by frontend to determine if user needs to complete setup.

    Returns:
            dict: {
                    "success": bool,
                    "ready": bool (true if can use FACO streaming),
                    "site_registered": bool,
                    "user_registered": bool,
                    "has_mcp_servers": bool,
                    "active_server_count": int,
                    "servers_with_expired_tokens": int,
                    "needs_reconnect": bool (true if tokens expired)
            }
    """
    try:
        settings = frappe.get_single("FAC Chat Settings")

        # Check site registration first
        if settings.registration_status != "Registered":
            return {
                "success": True,
                "ready": False,
                "site_registered": False,
                "user_registered": False,
                "has_mcp_servers": False,
                "message": _("Site not registered with FAC Cloud"),
            }

        client = get_fac_cloud_client()
        if not client:
            return {
                "success": False,
                "ready": False,
                "site_registered": False,
                "error": _("Cannot connect to FAC Cloud"),
            }

        # Check user auth status with AR (keyed by email)
        result = client.get_user_auth_status(user_id=_ar_user_id(frappe.session.user))

        if not result:
            return {
                "success": True,
                "ready": False,
                "site_registered": True,
                "user_registered": False,
                "has_mcp_servers": False,
                "message": _("Please connect your account to use FACO"),
            }

        # Transient AR failure (network/timeout/5xx). Trust the prior session
        # rather than bouncing a logged-in user to the connect-account screen.
        if result.get("_ar_unreachable"):
            return {
                "success": True,
                "ready": True,
                "site_registered": True,
                "user_registered": True,
                "has_mcp_servers": False,
                "ar_unreachable": True,
                "ar_error": result.get("error"),
            }

        user_exists = result.get("user_exists", False)
        has_mcp_servers = result.get("has_mcp_servers", False)
        active_server_count = result.get("active_server_count", 0)
        # servers_with_expired_tokens is a list of server names from AR
        expired_servers = result.get("servers_with_expired_tokens", [])
        expired_count = len(expired_servers) if isinstance(expired_servers, list) else 0
        ready_for_streaming = result.get("ready_for_streaming", False)

        return {
            "success": True,
            "ready": ready_for_streaming,
            "site_registered": True,
            "user_registered": user_exists,
            "user_status": result.get("user_status", "unknown"),
            "has_mcp_servers": has_mcp_servers,
            "active_server_count": active_server_count,
            "servers_with_expired_tokens": expired_count,
            "expired_server_names": expired_servers,
            "needs_reconnect": expired_count > 0,
        }

    except Exception as e:
        frappe.log_error(title="FACO User Auth Error", message=f"Error checking user auth status: {e!s}")
        return {"success": False, "error": _safe_error(e, "FACO User Auth Error")}


def _register_user_with_ar(frappe_user):
    """
    Register a Frappe user with AR: create AR user, OAuth tokens, and MCP server.

    Handles the full registration pipeline:
    1. Get AR client
    2. Register user with AR (idempotent — creates or updates)
    3. Create/get shared OAuth client
    4. Generate per-user OAuth tokens
    5. Register MCP server with AR for the user

    This is a private helper — not whitelisted. Called by connect_fac_mcp_server()
    for member self-provisioning and by users.add_user() for admin-initiated registration.

    Two identities are threaded deliberately:
      * AR (register_user, add_user_mcp_server) is keyed by EMAIL — AR's
        contract for AR Tenant Users.
      * the local OAuth Bearer Token is keyed by the Frappe USER DOCNAME,
        because the MCP endpoint does frappe.set_user(bearer_token.user); an
        email that is not a docname (e.g. Administrator's email) would break
        that. For ordinary staff the two coincide (username == email).

    Args:
            frappe_user: Frappe User docname (e.g. "Administrator" or an email)

    Returns:
            dict: {"success": True, "user_id": <ar email>}

    Raises:
            Exception: If any step fails (AR unavailable, registration rejected, etc.)
    """
    client = get_fac_cloud_client()
    if not client:
        frappe.throw(_("Site not registered with FAC Cloud"))

    ar_user_id = _ar_user_id(frappe_user)

    # A seat is the billed unit and AR keys it by email forever, so this is
    # where a placeholder must not be allowed to become durable.
    # `admin@example.com` is Frappe's install fixture: shared by every site,
    # deliverable to none, and orphaned the moment someone sets a real address
    # — which mints a SECOND billed seat, leaves the first Active, and stops
    # `_is_tenant_owner` matching, locking the real owner out.
    #
    # Existing tenants already seated under the placeholder are untouched:
    # this guards creation, and `_ar_user_id` still resolves them for reads.
    if _is_placeholder_email(ar_user_id) or "@" not in str(ar_user_id):
        frappe.throw(
            _(
                "The {0} account has no real email address ({1} is Frappe's "
                "default), so a FAC Cloud seat cannot be created for it. Set a "
                "real email on that user, or sign in as a named user, then try "
                "again."
            ).format(frappe_user, ar_user_id),
            frappe.ValidationError,
        )

    site_url = frappe.utils.get_url()
    fac_endpoint = f"{site_url}/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp"

    # Step 1: Register user with AR (idempotent — creates or reactivates).
    # Keyed by email; registered_by is the same email so AR recognizes an
    # owner self-provisioning (owner_user_id == registered_by).
    context = _get_user_context(ar_user_id)
    user_result = client.register_user(user_id=ar_user_id, registered_by=ar_user_id, **context)

    if not user_result or not user_result.get("user_id"):
        frappe.throw(_("Failed to register user {0} with FAC Cloud").format(ar_user_id))

    # Step 2: Create/get shared OAuth client
    oauth_client = _get_or_create_ar_oauth_client()

    # Step 3: Generate per-user OAuth tokens. Keyed by the Frappe docname — the
    # MCP endpoint authenticates as bearer_token.user via frappe.set_user().
    tokens = _generate_oauth_tokens_for_user(oauth_client, frappe_user)

    # Step 4: Register MCP server for this user in AR (keyed by email)
    result = client.add_user_mcp_server(
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
    )

    if not result or not result.get("success"):
        frappe.throw(
            _("Failed to connect MCP server for {0}: {1}").format(
                ar_user_id, result.get("error", _("Unknown error")) if result else _("No response")
            )
        )

    frappe.logger("faco").info(f"Registered user {ar_user_id} with AR and connected MCP server")

    return {"success": True, "user_id": ar_user_id}


@frappe.whitelist(methods=["POST"])
def connect_fac_mcp_server() -> dict:
    """
    Register current user with AR and connect MCP server.

    A FACO member (a seated AR Tenant User) may self-provision; so may the
    tenant owner, whose seat does not yet exist on first connect (otherwise a
    chicken-and-egg — membership is created by this very call). A plain
    non-member must be added by an admin via the Users management UI first.

    Returns:
            dict: {
                    "success": bool,
                    "server_name": str,
                    "message": str
            }
    """
    from frappe_assistant_core.chat.api.settings.access import _is_faco_member

    ar_user_id = _ar_user_id(frappe.session.user)
    if not _is_faco_member(frappe.session.user) and not _is_tenant_owner(ar_user_id):
        frappe.throw(
            _(
                "Your administrator needs to add you to FACO. Please ask them to add you from Settings > Users."
            ),
            frappe.PermissionError,
        )

    try:
        _register_user_with_ar(frappe.session.user)
        return {
            "success": True,
            "server_name": "Main Frappe Site",
            "message": _("Successfully connected your account to FACO"),
        }

    except Exception as e:
        frappe.log_error(title="FACO MCP Connection Error", message=f"Error connecting FAC MCP server: {e!s}")
        error_msg = getattr(e, "message", None) or str(e)
        response = {"success": False, "error": error_msg}
        # AR sets tenant_owner_user_id on frappe.local.response when blocking
        # a non-owner; the SDK forwards the raw body via ARAPIError.response_data.
        # Surface it so the SPA can render a "Contact <owner>" mailto link
        # instead of the generic "contact your administrator".
        body = getattr(e, "response_data", None) or {}
        owner = body.get("tenant_owner_user_id")
        if owner:
            response["tenant_owner_user_id"] = owner
        return response


@frappe.whitelist(methods=["GET"])
def get_user_mcp_servers() -> dict:
    """
    Get current user's MCP server configurations.

    Returns list of MCP servers the user has connected, with status info.
    Rows are forwarded from AR verbatim; `status` keeps AR's Title Case
    ("Active" / "Inactive" / "Error" / "Token Expired").

    Returns:
            dict: {
                    "success": bool,
                    "mcp_servers": [
                            {
                                    "server_name": str,
                                    "endpoint_url": str,
                                    "status": str,
                                    "connected_at": str,
                                    "error_message": str | None
                            }
                    ]
            }
    """
    try:
        client = get_fac_cloud_client()
        if not client:
            return {
                "success": False,
                "mcp_servers": [],
                "error": _("Site not registered with FAC Cloud"),
            }

        result = client.get_user_mcp_servers(user_id=_ar_user_id(frappe.session.user))

        if result:
            return {"success": True, "mcp_servers": result.get("mcp_servers", [])}

        return {"success": True, "mcp_servers": []}

    except Exception as e:
        frappe.log_error(title="FACO MCP Error", message=f"Error getting user MCP servers: {e!s}")
        return {"success": False, "mcp_servers": [], "error": _safe_error(e, "FACO MCP Error")}


@frappe.whitelist(methods=["POST"])
def reconnect_mcp_server(server_name: str = "Main Frappe Site") -> dict:
    """
    Refresh OAuth tokens for an existing MCP server.

    Called when tokens have expired and user needs to reconnect.
    Generates new tokens and updates AR.

    Args:
            server_name: Name of the server to reconnect (default: Main Frappe Site)

    Returns:
            dict: {
                    "success": bool,
                    "message": str
            }
    """
    try:
        client = get_fac_cloud_client()
        if not client:
            return {"success": False, "error": _("Site not registered with FAC Cloud")}

        frappe_user = frappe.session.user

        # Get OAuth client
        oauth_client = _get_or_create_ar_oauth_client()

        # Generate new tokens — OAuth Bearer Token keyed by the Frappe docname
        tokens = _generate_oauth_tokens_for_user(oauth_client, frappe_user)

        # Update tokens in AR (keyed by email)
        result = client.update_mcp_server_tokens(
            user_id=_ar_user_id(frappe_user),
            server_name=server_name,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_expires_in=tokens["expires_in"],
        )

        if result and result.get("success"):
            return {"success": True, "message": _("Successfully reconnected to {0}").format(server_name)}

        return {"success": False, "error": result.get("error", _("Failed to update tokens"))}

    except Exception as e:
        frappe.log_error(title="FACO MCP Reconnect Error", message=f"Error reconnecting MCP server: {e!s}")
        return {"success": False, "error": _safe_error(e, "FACO MCP Reconnect Error")}


@frappe.whitelist(methods=["POST"])
def disconnect_mcp_server(server_name: str = "Main Frappe Site") -> dict:
    """
    Disconnect an MCP server for the current user.

    Removes the MCP server registration from AR. User will need to
    reconnect to use FACO again.

    Args:
            server_name: Name of the server to disconnect

    Returns:
            dict: {
                    "success": bool,
                    "message": str
            }
    """
    try:
        client = get_fac_cloud_client()
        if not client:
            return {"success": False, "error": _("Site not registered with FAC Cloud")}

        result = client.remove_user_mcp_server(
            user_id=_ar_user_id(frappe.session.user), server_name=server_name
        )

        if result and result.get("success"):
            return {"success": True, "message": _("Disconnected from {0}").format(server_name)}

        return {"success": False, "error": result.get("error", _("Failed to disconnect server"))}

    except Exception as e:
        frappe.log_error(title="FACO MCP Disconnect Error", message=f"Error disconnecting MCP server: {e!s}")
        return {"success": False, "error": _safe_error(e, "FACO MCP Disconnect Error")}


# ============================================================================
# Mobile App OAuth Support - Dynamic Client Registration (RFC 7591)
# ============================================================================

# Allowed non-http redirect URI schemes for mobile app deep-linking.
# Any scheme not listed here falls back to same-origin https validation.
ALLOWED_REDIRECT_SCHEMES = {"facomobile"}


def _validate_redirect_uri(redirect_uri: str) -> str:
    """
    Validate the redirect_uri supplied by an unauthenticated caller.

    Accepts either a custom-scheme URI from the mobile app allowlist
    (e.g. facomobile://...) or an https URL on the same origin as this
    Frappe site. Anything else is rejected to prevent attacker-controlled
    redirect targets being persisted on an OAuth Client.

    Args:
            redirect_uri: The candidate redirect URI string.

    Returns:
            The validated redirect_uri (unchanged) on success.

    Raises:
            frappe.ValidationError: If the URI fails validation.
    """
    from urllib.parse import urlparse

    parsed = urlparse(redirect_uri or "")
    site_origin = urlparse(frappe.utils.get_url())

    if parsed.scheme in ALLOWED_REDIRECT_SCHEMES:
        return redirect_uri
    if parsed.scheme == "https" and parsed.netloc == site_origin.netloc:
        return redirect_uri

    frappe.throw(
        _("redirect_uri must use facomobile:// or match the site origin"),
        frappe.ValidationError,
    )


def _register_mobile_oauth_client(redirect_uri: str, device_id: str | None = None):
    """
    Dynamically register an OAuth Client for a FACO mobile app instance.

    Follows OAuth 2.0 Dynamic Client Registration (RFC 7591) pattern.
    Each mobile device gets its own client registration for better security.

    Args:
            redirect_uri: The app's OAuth callback URI (e.g., facomobile://oauth/callback)
            device_id: Optional device identifier for unique client per device

    Returns:
            OAuth Client document
    """
    # Generate unique client_id if device_id provided, otherwise use standard
    if device_id:
        client_id = f"faco-mobile-{device_id[:16]}"
    else:
        client_id = "faco-mobile"

    # Check if client already exists
    existing = frappe.db.get_value("OAuth Client", {"client_id": client_id}, "name")
    if existing:
        client = frappe.get_doc("OAuth Client", existing)
        # SECURITY: Never let an unauthenticated caller mutate the stored
        # redirect_uris. Registration is idempotent — if the caller's
        # redirect_uri does not match what we already have on file, refuse.
        existing_uris = (client.redirect_uris or "").split()
        if redirect_uri and redirect_uri not in existing_uris:
            frappe.throw(
                _(
                    "OAuth client already registered for this device with a "
                    "different redirect_uri. Contact an administrator to reset."
                ),
                frappe.ValidationError,
            )
        return client

    # Create new OAuth Client for mobile app
    # Uses Authorization Code flow with PKCE (public client - no secret required)
    client = frappe.get_doc(
        {
            "doctype": "OAuth Client",
            "app_name": "FACO Mobile",
            "scopes": "all openid",
            "redirect_uris": redirect_uri,
            "default_redirect_uri": redirect_uri,
            "grant_type": "Authorization Code",
            "response_type": "Code",
            "skip_authorization": 0,  # User must approve on first login
            "token_endpoint_auth_method": "None",  # PKCE public client - no secret
            "allowed_roles": [{"role": "All"}],
        }
    )

    # OAuth Client names by random hash and forces client_id = name (read-only
    # in validate()), so a plain insert would discard our client_id. Pin the
    # docname via set_name so client_id == name == the stable per-device id,
    # making the dedup above idempotent (one client per device, not one per call).
    try:
        client.insert(set_name=client_id, ignore_permissions=True)
    except frappe.DuplicateEntryError:
        # Lost a cold-start race or the row already exists — converge on it.
        pass
    return frappe.get_doc("OAuth Client", client_id)


@frappe.whitelist(methods=["GET"])
def get_user_info() -> dict:
    """
    Get current user's info for the mobile app.

    Returns user profile data after successful OAuth authentication.

    Returns:
            dict: {
                    "name": str (user id/email),
                    "email": str,
                    "full_name": str,
                    "user_image": str (URL),
                    "roles": list
            }
    """
    user = frappe.session.user

    if user == "Guest":
        frappe.throw(_("Not authenticated"), frappe.AuthenticationError)

    user_doc = frappe.get_doc("User", user)
    roles = frappe.get_roles(user)

    return {
        "name": user,
        "email": user_doc.email or user,
        "full_name": user_doc.full_name or user,
        "user_image": user_doc.user_image,
        "roles": roles,
    }


# RFC 7591 Dynamic Client Registration must be reachable pre-auth (mobile
# first run). Protected by 10/hour per-IP rate limit below.
@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep: guest-whitelisted-method
@rate_limit(key="ip", limit=10, seconds=3600)
def register_mobile_client(redirect_uri: str | None = None, device_id: str | None = None) -> dict:
    """
    Dynamic Client Registration for FACO mobile app.

    Implements OAuth 2.0 Dynamic Client Registration (RFC 7591).
    Called by mobile app to register itself before OAuth flow.

    Rate-limited to 10 registrations per hour per source IP to prevent
    abuse by unauthenticated callers.

    Args:
            redirect_uri: The app's OAuth callback URI (default: facomobile://oauth/callback)
            device_id: Optional unique device identifier

    Returns:
            dict: {
                    "success": bool,
                    "client_id": str,
                    "authorization_endpoint": str,
                    "token_endpoint": str,
                    "revocation_endpoint": str
            }
    """
    try:
        # Check if FAC Chat is enabled first (master gate)
        if not is_chat_enabled():
            return {"success": False, "faco_enabled": False, "error": _("FACO is not enabled on this site")}

        # Default redirect URI for FACO mobile app
        if not redirect_uri:
            redirect_uri = "facomobile://oauth/callback"

        # Validate redirect_uri scheme/origin before touching OAuth Client
        redirect_uri = _validate_redirect_uri(redirect_uri)

        # Dynamically register OAuth client
        client = _register_mobile_oauth_client(redirect_uri, device_id)

        site_url = frappe.utils.get_url()

        return {
            "success": True,
            "faco_enabled": True,
            "client_id": client.client_id,
            "authorization_endpoint": f"{site_url}/api/method/frappe.integrations.oauth2.authorize",
            "token_endpoint": f"{site_url}/api/method/frappe.integrations.oauth2.get_token",
            "revocation_endpoint": f"{site_url}/api/method/frappe.integrations.oauth2.revoke_token",
            "scopes": "all openid",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",  # PKCE public client
        }

    except Exception as e:
        frappe.log_error(
            title="FACO Mobile OAuth Error", message=f"Error registering mobile OAuth client: {e!s}"
        )
        return {"success": False, "error": _safe_error(e, "FACO Mobile OAuth Error")}


# Legacy alias for backwards compatibility — inherits the guest-auth and
# rate-limit rationale from register_mobile_client.
@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep: guest-whitelisted-method
def ensure_mobile_oauth_client() -> dict:
    """Legacy alias - use register_mobile_client instead."""
    return register_mobile_client()
