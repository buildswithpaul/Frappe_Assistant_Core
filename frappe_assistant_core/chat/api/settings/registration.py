# Frappe Assistant Core - Tenant Registration API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Site → AR tenant registration, partner-code validation, plan listing."""

from __future__ import annotations

import frappe
from frappe import _

from ...cloud_url import get_fac_cloud_url
from .._helpers import _not_registered_error, _safe_error
from .._rate_limits import ip_only, rate_limit

# FAC always registers under the "faco" AR Application — the application never
# changes, so it is hardcoded rather than exposed as a settings field.
AR_APPLICATION_ID = "faco"


def _translate_registration_error(raw: str) -> str:
    """Turn an SDK register_tenant error string into something a user can act on.

    The SDK wraps network failures with ``str(requests.HTTPError)`` — e.g.
    ``"429 Client Error: TOO MANY REQUESTS for url: ..."`` — which leaks
    implementation detail into the onboarding UI. This translator inspects
    the raw string and returns a friendly sentence; unknown shapes fall
    through to a generic retry message.
    """
    if not raw:
        return _("Registration failed. Please try again.")

    lowered = raw.lower()

    if "429" in raw or "too many requests" in lowered or "rate limit" in lowered:
        return _(
            "Too many registration attempts from this network. For security, "
            "new sites can only be registered a few times per day — please "
            "wait 24 hours before trying again, or contact support if you "
            "need immediate help."
        )

    if "connection" in lowered or "timed out" in lowered or "timeout" in lowered:
        return _(
            "Couldn't reach the FAC Cloud server. Check your "
            "internet connection and try again in a moment."
        )

    if "500" in raw or "internal server error" in lowered or "502" in raw or "503" in raw:
        return _("The FAC Cloud server is temporarily unavailable. Please try again in a few minutes.")

    if "401" in raw or "403" in raw or "unauthorized" in lowered or "forbidden" in lowered:
        return _("Registration was rejected by the server. Please contact support.")

    return _("Registration failed. Please try again or contact support if the problem persists.")


# Signup precedes tenant credentials, so referral-code validation must work
# pre-auth. Protected by a 20/minute per-IP rate limit; thin proxy to AR.
@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep: guest-whitelisted-method
@rate_limit(ip_only, limit=20, seconds=60)
def validate_partner_code(referral_code: str | None = None) -> dict:
    """
    Validate a partner referral code against AR core.

    Guest-allowed because this is called during signup, before tenant credentials exist.
    Thin proxy to the AR SDK — no FACO-level caching or business logic.

    Returns:
        {"valid": True, "partner_name": str, "referral_code": str} on success,
        {"valid": False, "error": str} on failure.
    """
    if not referral_code or not str(referral_code).strip():
        return {"valid": False, "error": _("Referral code is required")}

    # FACO-M3: validate format before proxying to AR. Rejects oversized or
    # exotic inputs that could amplify AR traffic or probe server behavior.
    import re as _re

    if not _re.fullmatch(r"[A-Za-z0-9_-]{4,32}", str(referral_code).strip()):
        return {"valid": False, "error": _("Invalid referral code format")}

    try:
        from assistant_runtime_sdk.client import validate_referral_code as sdk_validate

        return sdk_validate(ar_url=get_fac_cloud_url(), referral_code=referral_code)
    except Exception as e:
        frappe.log_error(
            title="FAC Partner Validation Error", message=f"Partner code validation failed: {e!s}"
        )
        return {"valid": False, "error": _safe_error(e, "FAC Chat Settings Error")}


@frappe.whitelist(methods=["POST"])
def register_with_ar(
    owner_email: str,
    terms_version: str | None = None,
    promotion_token: str | None = None,
) -> dict:
    """
    Register FACO site with AR (tenant registration only).

    With per-user MCP server architecture, OAuth tokens are no longer required
    at tenant registration. Each user will register separately and add their
    own MCP servers with personal OAuth tokens via connect_fac_mcp_server().

    For new registrations AR sends a verification email to owner_email before
    issuing the tenant_secret. The SPA polls complete_email_verification() after
    the admin clicks the link. Re-registrations of an existing tenant return the
    secret immediately (legacy path).

    Two different identities are in play and must not be conflated:

    * ``owner_email`` is a MAILBOX — where AR sends the verification link, and
      later the billing and rebind notices. It may be a shared address and need
      not be anyone's login. The admin types it.
    * ``accepted_by`` becomes AR's ``owner_user_id``, an IDENTITY — who bypasses
      the seat gate and who may add users. Both gates match it against
      ``_ar_user_id(frappe.session.user)``, so it is derived from the session,
      never accepted from the caller.

    Args:
            owner_email: Mailbox the verification link is sent to. Required for
                new registrations; a re-registration keeps the stored one.
            terms_version: Version of terms being accepted (from get_ar_terms)

    Returns:
            dict: {"success": bool, "message": str}
                  or {"success": True, "verification_pending": True, "message": str}
    """
    frappe.only_for("System Manager")

    from frappe.utils import validate_email_address

    # Imported here, not at module scope: chat.api.auth reaches back into this
    # package and the cycle only resolves lazily.
    from frappe_assistant_core.chat.api.auth import _ar_user_id, _is_placeholder_email

    # A Frappe User's docname is its email for ordinary staff, but not for
    # Administrator — the account most likely to be registering a site.
    # `_ar_user_id` is the canonical resolver: a pass-through for anything
    # already an address, a User.email lookup otherwise. The supplied value
    # goes through it too, because a caller passing frappe.session.user used to
    # *defeat* this recovery rather than use it — a truthy non-address skipped
    # the lookup and fell straight into the validation failure below.
    owner_email = _ar_user_id(owner_email or frappe.session.user)

    if not owner_email or not validate_email_address(owner_email, throw=False):
        return {"success": False, "error": _("A valid owner email is required.")}

    # AR sends the ownership-verification link here and issues no tenant secret
    # until it is clicked. Frappe's `admin@example.com` install fixture can
    # never receive it, so registering with it stalls forever with no error to
    # show for it — and it would become this tenant's owner identity besides.
    if _is_placeholder_email(owner_email):
        return {
            "success": False,
            "error": _(
                "{0} is Frappe's default address and cannot receive the "
                "verification email. Enter a real owner email address."
            ).format(owner_email),
        }

    # The registering login becomes this tenant's owner_user_id, so it has to
    # be an identity that can still be recognised later. `bench new-site` leaves
    # Administrator on `admin@example.com`, which identifies nobody — every
    # Frappe install shares it. Registering under it produces a tenant whose
    # owner never matches, and `_register_user_with_ar` refuses to seat it
    # anyway, so this is that same wall moved earlier: before the tenant exists
    # on AR, while the remedy is still one field on a User.
    registrant = _ar_user_id(frappe.session.user)
    if _is_placeholder_email(registrant) or "@" not in str(registrant):
        return {
            "success": False,
            "error": _(
                "The {0} account has no email address of its own ({1} is "
                "Frappe's default), so it cannot own this workspace. Set a real "
                "email on that user, or sign in as a named user, then register."
            ).format(frappe.session.user, registrant),
        }

    try:
        # Validate terms acceptance
        if not terms_version:
            return {
                "success": False,
                "error": _("Terms version is required. Please accept the Terms and Conditions."),
            }

        settings = frappe.get_single("FAC Chat Settings")
        site_url = frappe.utils.get_url()

        # Derived above, never taken from the caller: a supplied value would
        # let one System Manager nominate somebody else as owner.
        accepted_by = registrant

        # FAC MCP endpoint on this site (for reference - actual OAuth tokens are per-user)
        fac_endpoint = f"{site_url}/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp"

        # Register with AR - NO OAuth tokens (per-user model)
        from frappe_assistant_core.chat.fac_cloud_client import register_tenant

        fac_cloud_url = get_fac_cloud_url()

        # FACO-M16: refuse non-HTTPS FAC Cloud URLs. The register_tenant response
        # carries the tenant_secret that signs every subsequent HMAC request
        # — a MITM on plaintext HTTP can forge it and own the tenant for the
        # lifetime of the install. Localhost is allowed because dev setups
        # legitimately run AR on http://127.0.0.1.
        import urllib.parse as _urlparse

        parsed_ar = _urlparse.urlparse(fac_cloud_url)
        if parsed_ar.scheme != "https" and parsed_ar.hostname not in ("localhost", "127.0.0.1", "::1"):
            frappe.throw(
                _("FAC Cloud URL must use HTTPS (got {0})").format(parsed_ar.scheme or "<none>"),
                frappe.ValidationError,
            )

        referral_code = frappe.form_dict.get("referral_code")
        result = register_tenant(
            fac_cloud_url=fac_cloud_url,
            site_url=site_url,
            owner_email=owner_email,
            application_id=AR_APPLICATION_ID,
            fac_mcp_endpoint=fac_endpoint,
            terms_accepted=True,
            terms_version=terms_version,
            accepted_by=accepted_by,
            referral_code=referral_code,
            promotion_token=promotion_token,
        )

        # Email-verification branch — AR queued a verification email before
        # issuing credentials. No secret yet. Persist registration state so the
        # admin UI can show the "check your email" screen. The admin clicks the
        # link, which redirects to the SPA; the SPA then calls
        # complete_email_verification(verification_token=<token from URL>).
        if result.get("verification_pending"):
            from frappe_assistant_core.chat.tenant_credentials import clear_tenant_secret

            clear_tenant_secret()
            settings.flags.clear_tenant_secret = True
            settings.tenant_id = result["tenant_id"]
            settings.tenant_secret = None
            settings.registration_status = "Pending Email Verification"
            settings.save(ignore_permissions=True)
            return {
                "success": True,
                "verification_pending": True,
                "message": _(
                    "Verification email sent to {0}. Click the link in your email " "to finish registration."
                ).format(owner_email),
            }

        # Waitlist branch — registration is at capacity, so AR queued this
        # applicant instead of registering them. This is NOT a failure: the SPA
        # renders a "you're in the queue" state and the applicant is emailed a
        # promotion link when an admin approves them (see resume_registration).
        if result.get("waitlisted"):
            from frappe_assistant_core.chat.tenant_credentials import clear_tenant_secret

            clear_tenant_secret()
            settings.flags.clear_tenant_secret = True
            settings.tenant_id = None
            settings.tenant_secret = None
            settings.registration_status = "Waitlisted"
            settings.save(ignore_permissions=True)
            return {
                "success": True,
                "waitlisted": True,
                "waitlist_position": result.get("waitlist_position"),
                "message": result.get("message")
                or _(
                    "Registration is currently at capacity. You've been added to "
                    "our waitlist — we'll email you as soon as a slot opens."
                ),
            }

        # FACO-M16: validate the AR response shape strictly before we trust
        # it to populate HMAC credentials. A forged response that only
        # included ``tenant_id`` (without ``tenant_secret``) would previously
        # overwrite ``tenant_id`` and crash on ``result["tenant_secret"]``
        # — the strict assertion makes the rejection explicit and logged.
        tenant_id = result.get("tenant_id")
        tenant_secret = result.get("tenant_secret")
        if tenant_id and not (
            isinstance(tenant_id, str)
            and isinstance(tenant_secret, str)
            and 8 <= len(tenant_id) <= 128
            and 32 <= len(tenant_secret) <= 256
        ):
            frappe.log_error(
                title="FACO Registration Integrity",
                message=f"Malformed AR register_tenant response: keys={list(result.keys())}",
            )
            frappe.throw(
                _("AR returned a malformed registration response"),
                frappe.ValidationError,
            )

        if tenant_id:
            from frappe_assistant_core.chat.tenant_credentials import store_tenant_secret

            # Store AR's response credentials (for HMAC signing). Password field
            # goes through tenant_credentials so __Auth + Singles stay in sync.
            store_tenant_secret(tenant_secret)
            settings.tenant_id = tenant_id
            settings.tenant_secret = "*" * len(tenant_secret)
            settings.registration_status = "Registered"
            settings.save(ignore_permissions=True)

            # Seed quota cache with initial subscription data
            from frappe_assistant_core.chat.quota_cache import update_from_ar

            subscription = result.get("subscription", {})
            update_from_ar(
                {
                    "plan": subscription.get("plan", "Free"),
                    "quota": subscription.get("quota", 50000),
                    "used": 0,
                }
            )

            return {
                "success": True,
                "message": _("Site registration successful. Users can now connect their accounts."),
            }

        raw_error = result.get("error", "")
        settings.registration_status = "Error"
        settings.save(ignore_permissions=True)

        # Log the raw error for debugging, but translate before returning —
        # requests.HTTPError str() messages like "429 Client Error: TOO MANY
        # REQUESTS for url: ..." must never reach the SPA verbatim.
        if raw_error:
            frappe.log_error(
                title="FACO Registration Error", message=f"AR register_tenant returned error: {raw_error}"
            )

        # AR's structured errors are already written for this admin and name
        # the actual problem; the translator only pattern-matches raw HTTP
        # strings and would flatten them into "Registration failed".
        if result.get("error_code"):
            return {
                "success": False,
                "error": raw_error,
                "error_code": result.get("error_code"),
            }

        return {"success": False, "error": _translate_registration_error(raw_error)}

    except Exception as e:
        frappe.log_error(title="FACO Registration Error", message=f"Error registering with AR: {e!s}")
        return {"success": False, "error": _safe_error(e, "FACO Registration Error")}


def _suggested_owner_email() -> str | None:
    """The address to prefill the owner-email field with, or None.

    The mailbox and the owner identity are separate fields and may legitimately
    diverge, but the ordinary case — the admin owning the workspace they are
    registering — should not depend on retyping their own address from memory.
    Suggests nothing when the session account has no real address of its own;
    registration refuses that anyway, and offering a placeholder would invite
    the admin to accept it.
    """
    from frappe_assistant_core.chat.api.auth import _ar_user_id, _is_placeholder_email

    candidate = _ar_user_id(frappe.session.user)
    if not candidate or "@" not in str(candidate) or _is_placeholder_email(candidate):
        return None
    return candidate


@frappe.whitelist(methods=["POST"])
def get_registration_state() -> dict:
    """SPA boot lookup: is this site already a returning AR tenant?

    site_url and tenant_id are resolved server-side (never trusted from the
    browser), matching register_with_ar. Returns AR's classification or a
    safe {"exists": False} on any failure so first-run never breaks.

    Carries `suggested_owner_email` either way — it is resolved locally, so a
    first run with no AR reachable still gets the prefill.
    """
    frappe.only_for("System Manager")
    # Resolved inside the guard: this endpoint promises never to break first
    # run, and that has to hold for the local lookup too.
    suggested = None
    try:
        suggested = _suggested_owner_email()
        settings = frappe.get_single("FAC Chat Settings")
        from frappe_assistant_core.chat.fac_cloud_client import get_registration_state as client_state

        state = client_state(
            site_url=frappe.utils.get_url(),
            tenant_id=settings.tenant_id or None,
        )
        return {
            **(state or {}),
            "suggested_owner_email": suggested,
            "local_status": settings.registration_status or "",
        }
    except Exception as e:
        frappe.log_error(title="FAC get_registration_state", message=str(e))
        return {"exists": False, "suggested_owner_email": suggested}


@frappe.whitelist(methods=["POST"])
def reset_registration() -> dict:
    """Drop this site's tenant credentials. Clear-only, by design.

    Reset does NOT re-register. Registration requires accepting a specific
    Terms and Conditions version, and terms can only be accepted where they
    are displayed — the SPA onboarding screen. Calling register_with_ar() from
    here could only ever pass a terms_version it had not shown anyone, so this
    hands off instead: clear, mark Not Registered, and let onboarding take over.

    The onward path matters because re-registering against a *different*
    FAC Cloud (a UAT → production cutover) mints a brand-new tenant — the old
    subscription, credits and history stay behind on the old server.

    Returns:
            dict: {"success": bool, "message": str, "previous_tenant_id": str | None}
    """
    # FACO-M2: the sibling endpoint in page/faco_admin/faco_admin.py uses
    # only_for("System Manager") — match that here so the two admin entry
    # points converge. `has_permission` could green-light custom roles that
    # were granted FACO Settings write without intending registration-level
    # authority.
    frappe.only_for("System Manager")

    try:
        from frappe_assistant_core.chat.tenant_credentials import clear_tenant_secret

        settings = frappe.get_single("FAC Chat Settings")
        previous_tenant_id = settings.tenant_id or None

        clear_tenant_secret()
        settings.flags.clear_tenant_secret = True
        settings.tenant_id = None
        settings.tenant_secret = None
        settings.registration_status = "Not Registered"
        settings.save(ignore_permissions=True)
        from frappe_assistant_core.chat.quota_cache import clear as clear_quota

        clear_quota()

        # Wiping tenant credentials is a privileged, destructive act and leaves
        # no trace on AR (the credentials that would have signed an audit call
        # are exactly what we just destroyed). Record it locally.
        frappe.logger("faco.registration").info(
            f"Registration reset by {frappe.session.user}; "
            f"cleared tenant_id={previous_tenant_id} pointing at {get_fac_cloud_url()}"
        )

        return {
            "success": True,
            "previous_tenant_id": previous_tenant_id,
            "message": _(
                "Registration cleared. Open FAC Chat to register this site again — "
                "you will be asked to accept the Terms and Conditions."
            ),
        }

    except Exception as e:
        frappe.log_error(
            title="FACO Registration Reset Error", message=f"Error resetting registration: {e!s}"
        )
        return {"success": False, "error": _safe_error(e, "FACO Registration Reset Error")}


@frappe.whitelist(methods=["GET"])
def get_plan_comparison() -> dict:
    """
    Get comparison of available subscription plans from AR.

    Returns:
            dict: Plans with features and pricing
    """
    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            # Return default plans if not connected
            return {
                "plans": [
                    {
                        "name": "Free",
                        "display_name": "Free",
                        "price_usd": 0,
                        "monthly_credits": 500,
                        "features": ["500 credits/month", "Basic AI assistance", "Standard support"],
                    },
                    {
                        "name": "Starter",
                        "display_name": "Starter",
                        "price_usd": 19,
                        "monthly_credits": 5000,
                        "features": ["5K credits/month", "Priority support", "Advanced features"],
                    },
                    {
                        "name": "Pro",
                        "display_name": "Pro",
                        "price_usd": 49,
                        "monthly_credits": 20000,
                        "features": ["20K credits/month", "Premium support", "All features"],
                    },
                ]
            }

        return client.get_plan_comparison() or {"plans": []}

    except Exception as e:
        frappe.log_error(title="FACO Plans Error", message=f"Error getting plan comparison: {e!s}")
        return {"plans": []}


@frappe.whitelist(methods=["POST"])
def complete_email_verification(verification_token: str) -> dict:
    """Called by the SPA after the admin returns to FACO from the email link.

    Drives the two-step AR flow:
    1. Call verify_owner_email(token) — activates the tenant and caches the secret in Redis.
    2. Call get_initial_secret(token) — retrieves the secret one-shot.

    Both calls are guest-allowed on AR's side (the token is the credential).
    If step 1 fails, pending_verification_token is left untouched so the admin
    can retry.
    """
    frappe.only_for("System Manager")

    if not verification_token:
        return {"success": False, "error": _("Missing verification_token")}

    settings = frappe.get_single("FAC Chat Settings")
    fac_cloud_url = get_fac_cloud_url()

    # Step 1: verify — activates the tenant and caches the freshly-minted secret
    import requests as _requests

    try:
        verify_resp = _requests.post(
            f"{fac_cloud_url}/api/method/assistant_runtime.api.verify_owner_email",
            json={"token": verification_token},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        verify_resp.raise_for_status()
        verify_payload = verify_resp.json().get("message", verify_resp.json())
        if not verify_payload.get("verified"):
            return {"success": False, "error": _("Verification failed")}
    except _requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}

    # Step 2: pick up the freshly-minted secret (one-shot; consumed on first call)
    from assistant_runtime_sdk.client import get_initial_secret

    result = get_initial_secret(ar_url=fac_cloud_url, verification_token=verification_token)
    if "tenant_secret" not in result:
        return {"success": False, "error": result.get("error") or _("Secret not yet available")}

    from frappe_assistant_core.chat.tenant_credentials import store_tenant_secret

    try:
        store_tenant_secret(result["tenant_secret"])
    except frappe.ValidationError as e:
        return {"success": False, "error": str(e)}

    settings.tenant_secret = "*" * len(result["tenant_secret"])
    settings.pending_verification_token = None
    settings.registration_status = "Registered"
    settings.save(ignore_permissions=True)
    from frappe_assistant_core.chat.quota_cache import clear as clear_quota

    clear_quota()
    return {"success": True}


@frappe.whitelist(methods=["POST"])
def resend_owner_verification() -> dict:
    """Re-send the pending link. Never clears the secret or marks an error.

    A failure comes back as ``success: False`` so the pending screen can say
    so. An already-verified tenant is reported as such and left alone.
    """
    frappe.only_for("System Manager")
    from frappe_assistant_core.chat.fac_cloud_client import resend_owner_verification as resend

    result = resend(site_url=frappe.utils.get_url()) or {}
    if result.get("error"):
        return {"success": False, "error": result["error"]}
    return result


@frappe.whitelist(methods=["POST"])
def change_pending_owner_email(owner_email: str) -> dict:
    """Correct the address the verification link goes to, while still pending."""
    frappe.only_for("System Manager")
    from frappe_assistant_core.chat.fac_cloud_client import change_pending_owner_email as change

    result = change(site_url=frappe.utils.get_url(), owner_email=owner_email) or {}
    if result.get("error"):
        return {"success": False, "error": result["error"]}
    return result


@frappe.whitelist(methods=["POST"])
def accept_updated_terms(terms_version: str) -> dict:
    """Re-accept AR's Terms and Conditions on behalf of this tenant.

    Acceptance is a TENANT-level act — it binds the whole site, not the
    clicking user — so this is System Manager only. Non-admins hitting the
    terms gate are shown a "ask your administrator" notice instead.

    ``terms_version`` comes from get_ar_terms(); AR re-validates it against the
    active version and rejects a stale one, so a user sitting on an old tab
    cannot accept a version that has since moved.
    """
    frappe.only_for("System Manager")

    if not terms_version:
        return {"success": False, "error": _("Missing terms version")}

    try:
        from frappe_assistant_core.chat.api.auth import _ar_user_id
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"success": False, "error": _not_registered_error()}

        result = client.accept_terms(
            terms_version=terms_version,
            accepted_by=_ar_user_id(frappe.session.user),
        )
        if not result or not result.get("success"):
            return {
                "success": False,
                "error": (result or {}).get("error") or _("Could not record your acceptance."),
            }

        return {"success": True, "version": result.get("version")}

    except Exception as e:
        frappe.log_error(title="FACO Terms Acceptance Error", message=f"Error accepting terms: {e!s}")
        return {"success": False, "error": _safe_error(e, "FACO Terms Acceptance Error")}


@frappe.whitelist(methods=["POST"])
def request_site_rebind(new_site_url: str) -> dict:
    """Request a site rebind — notify AR that this tenant is moving to a new URL.
    AR sends a confirmation email to the owner; on click AR rotates the secret.
    FACO stores the rebind_token for subsequent polling."""
    frappe.only_for("System Manager")
    settings = frappe.get_single("FAC Chat Settings")
    if not settings.tenant_id or not settings.tenant_secret:
        return {"success": False, "error": _("Site is not registered.")}

    from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

    client = get_fac_cloud_client()
    if not client:
        return {"success": False, "error": _("AR client unavailable.")}
    result = client.request_rebind(new_site_url=new_site_url)
    if "rebind_token" in result:
        settings.pending_rebind_token = result["rebind_token"]
        settings.save(ignore_permissions=True)
        return {"success": True, "expires_at": result["expires_at"]}
    return {"success": False, "error": result.get("error") or _("Failed to request rebind.")}


@frappe.whitelist(methods=["POST"])
def poll_for_rotated_secret() -> dict:
    """Called by the SPA after the admin reports having clicked the rebind email link."""
    frappe.only_for("System Manager")
    settings = frappe.get_single("FAC Chat Settings")
    if not settings.pending_rebind_token:
        return {"success": False, "error": _("No pending rebind.")}

    fac_cloud_url = get_fac_cloud_url()
    from assistant_runtime_sdk.client import get_rotated_secret

    result = get_rotated_secret(ar_url=fac_cloud_url, rebind_token=settings.pending_rebind_token)
    if "tenant_secret" not in result:
        return {"success": False, "error": result.get("error") or _("Secret not yet available")}

    from frappe_assistant_core.chat.tenant_credentials import store_tenant_secret

    try:
        store_tenant_secret(result["tenant_secret"])
    except frappe.ValidationError as e:
        return {"success": False, "error": str(e)}

    settings.tenant_secret = "*" * len(result["tenant_secret"])
    settings.pending_rebind_token = None
    settings.registration_status = "Registered"
    settings.save(ignore_permissions=True)
    return {"success": True}


@frappe.whitelist(methods=["POST"])
def run_diagnostics() -> dict:
    """Run AR registration diagnostics for this tenant."""
    frappe.only_for("System Manager")
    from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

    client = get_fac_cloud_client()
    if not client:
        return {"status": "no_client"}
    return client.diagnose_registration()
