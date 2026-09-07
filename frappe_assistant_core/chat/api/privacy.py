# FACO - Privacy / GDPR API
# Copyright (C) 2025 Paul Clinton
#
# Proprietary License

"""
Privacy and GDPR Data Subject Rights proxy APIs.

These endpoints are called by the FACO frontend and proxy to the
AR core GDPR API via the SDK. They bridge Frappe session auth
to HMAC-signed AR API calls.
"""

import frappe
from frappe import _

from .auth import _ar_user_id


def _get_client():
    """Get an authenticated AR SDK client."""
    from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

    client = get_fac_cloud_client()
    if not client:
        frappe.throw(_("FAC Cloud is not configured"))
    return client


@frappe.whitelist(methods=["GET"])
def export_my_data() -> dict:
    """
    Export all data for the current user (GDPR Article 20 — Data Portability).

    Returns structured JSON with all user data from AR core and companion apps,
    plus local FACO data.
    """
    user = frappe.session.user
    client = _get_client()

    # AR keys users by email; resolve the docname before every AR call.
    ar_data = client.export_user_data(user_id=_ar_user_id(user))

    # Append local FACO data
    faco_data = {
        "faco_preferences": None,
        "faco_messages_count": 0,
    }

    # User preferences
    prefs = frappe.db.get_value(
        "FAC Chat User Preferences",
        {"user": user},
        ["widget_position", "widget_theme", "keyboard_shortcut", "show_suggested_prompts"],
        as_dict=True,
    )
    if prefs:
        faco_data["faco_preferences"] = {
            "widget_position": prefs.widget_position,
            "widget_theme": prefs.widget_theme,
            "keyboard_shortcut": prefs.keyboard_shortcut,
            "show_suggested_prompts": bool(prefs.show_suggested_prompts),
        }

    # Message count (content already exported from AR side)
    faco_data["faco_messages_count"] = frappe.db.count("FAC Chat Message", {"user": user})

    if ar_data and ar_data.get("data"):
        ar_data["data"]["faco"] = faco_data

    return ar_data or {"status": "success", "data": {"faco": faco_data}}


@frappe.whitelist(methods=["POST"])
def erase_my_data(password: str | None = None) -> dict:
    """
    Delete all data for the current user (GDPR Article 17 — Right to Erasure).

    Requires password confirmation for safety. Deletes data from:
    1. AR core (conversations, messages, streaming events, token usage, profile)
    2. Companion apps via RuntimeGate (memories, documents, billing anonymization)
    3. Local FACO data (messages, preferences)
    """
    user = frappe.session.user

    # Require password confirmation for destructive operation
    if not password:
        frappe.throw(_("Password confirmation is required to delete all data"))

    from frappe.utils.password import check_password

    try:
        check_password(user, password)
    except frappe.AuthenticationError:
        frappe.throw(_("Incorrect password"))

    client = _get_client()

    # 1. Delete AR-side data (AR keys users by email)
    ar_result = client.erase_user_data(user_id=_ar_user_id(user))

    # 2. Collect FACO Message names BEFORE deleting so we can cascade
    #    into attached File docs (FACO-H10 — incomplete GDPR erasure).
    message_names = frappe.get_all(
        "FAC Chat Message",
        filters={"user": user},
        pluck="name",
        limit_page_length=0,
    )
    file_names: list[str] = []
    if message_names:
        file_names = frappe.get_all(
            "File",
            filters={
                "attached_to_doctype": "FAC Chat Message",
                "attached_to_name": ["in", message_names],
            },
            pluck="name",
            limit_page_length=0,
        )

    # 3. Delete user-keyed rows. Use ``frappe.db.delete`` for bulk
    #    integrity — these DocTypes have no on_trash side effects we
    #    need to fire, and this avoids N document loads.
    local_deleted = len(message_names)
    frappe.db.delete("FAC Chat Message", {"user": user})

    prefs_name = frappe.db.get_value("FAC Chat User Preferences", {"user": user}, "name")
    frappe.db.delete("FAC Chat User Preferences", {"user": user})

    # FACO Usage Log — ships with the app; safe no-op if table absent.
    usage_log_deleted = 0
    try:
        usage_log_deleted = frappe.db.count("FAC Chat Usage Log", {"user": user})
        frappe.db.delete("FAC Chat Usage Log", {"user": user})
    except Exception as e:
        frappe.log_error(
            title="FAC GDPR Erasure", message=f"FAC Chat Usage Log cleanup skipped for {user}: {e}"
        )

    # OAuth Bearer Token — invalidates any mobile / SDK session still
    # using the user's tokens. Compatibility note: active mobile
    # sessions will need to re-authenticate after erasure.
    oauth_deleted = 0
    try:
        oauth_deleted = frappe.db.count("OAuth Bearer Token", {"user": user})
        frappe.db.delete("OAuth Bearer Token", {"user": user})
    except Exception as e:
        frappe.log_error(
            title="FACO GDPR Erasure", message=f"OAuth Bearer Token cleanup failed for {user}: {e}"
        )

    # 4. Delete File docs through the ORM so the on_trash hook wipes
    #    the backing bytes from disk. Bulk db.delete would leave files
    #    orphaned on the filesystem.
    files_deleted = 0
    for fname in file_names:
        try:
            frappe.delete_doc("File", fname, force=True, ignore_permissions=True)
            files_deleted += 1
        except Exception as e:
            frappe.log_error(
                title="FACO GDPR Erasure", message=f"Failed to delete File {fname} during erasure: {e}"
            )

    # 5. Audit trail — one summary entry the DPO can grep for.
    frappe.log_error(
        title="FACO GDPR Erasure",
        message=(
            f"Erased FACO data for {user}: "
            f"messages={local_deleted}, files={files_deleted}, "
            f"usage_log={usage_log_deleted}, oauth_tokens={oauth_deleted}, "
            f"preferences={1 if prefs_name else 0}"
        ),
    )

    result = ar_result or {}
    if "deleted" not in result:
        result["deleted"] = {}
    result["deleted"]["faco_messages"] = local_deleted
    result["deleted"]["faco_preferences"] = 1 if prefs_name else 0
    result["deleted"]["faco_usage_log"] = usage_log_deleted
    result["deleted"]["faco_oauth_tokens"] = oauth_deleted
    result["deleted"]["faco_attached_files"] = files_deleted
    result["status"] = "success"

    return result


@frappe.whitelist(methods=["POST"])
def update_my_data(updates: str | None = None) -> dict:
    """
    Update personal data for the current user (GDPR Article 16 — Rectification).

    Updatable fields: display_name, email, timezone, locale, custom_instructions.
    """
    import json

    user = frappe.session.user
    client = _get_client()

    updates_dict = json.loads(updates) if isinstance(updates, str) else updates
    if not updates_dict:
        frappe.throw(_("No updates provided"))

    return client.rectify_user_data(user_id=_ar_user_id(user), updates=updates_dict)


@frappe.whitelist(methods=["POST"])
def restrict_my_processing(restrict: bool = True) -> dict:
    """
    Restrict or unrestrict data processing (GDPR Article 18).

    When restricted: memories excluded from retrieval, memory extraction
    skipped, but chat and billing continue normally.
    """
    user = frappe.session.user
    client = _get_client()

    # Convert string "true"/"false" from form data
    if isinstance(restrict, str):
        restrict = restrict.lower() in ("true", "1", "yes")

    result = client.restrict_user_processing(user_id=_ar_user_id(user), restrict=restrict)

    # FACO-M15: mirror the flag onto FACO User Preferences so
    # ``_log_conversation`` can skip persistence without an AR round-trip on
    # every message. We only flip local state after AR acknowledges.
    # The local mirror is keyed by the Frappe docname (session user).
    try:
        _set_processing_restricted_flag(user, bool(restrict))
    except Exception:
        # AR is source-of-truth; local mirror drift is a P2 concern. Don't
        # fail the user's privacy request if the local write errors.
        frappe.log_error(title="FACO processing_restricted mirror failed", message=frappe.get_traceback())

    return result


def _set_processing_restricted_flag(user: str, restricted: bool) -> None:
    """Write the local mirror of AR's processing_restricted flag."""
    if not frappe.db.exists("FAC Chat User Preferences", user):
        prefs = frappe.get_doc(
            {
                "doctype": "FAC Chat User Preferences",
                "user": user,
                "processing_restricted": 1 if restricted else 0,
            }
        )
        prefs.insert(ignore_permissions=True)
    else:
        frappe.db.set_value(
            "FAC Chat User Preferences",
            user,
            "processing_restricted",
            1 if restricted else 0,
        )


@frappe.whitelist(methods=["POST"])
def update_my_consent(consent_type: str | None = None, granted: bool = True) -> dict:
    """
    Update consent for a specific processing activity.

    Args:
            consent_type: Type of consent (e.g., "memory")
            granted: True to grant, False to withdraw
    """
    user = frappe.session.user
    client = _get_client()

    if not consent_type:
        frappe.throw(_("Consent type is required"))

    # Convert string "true"/"false" from form data
    if isinstance(granted, str):
        granted = granted.lower() in ("true", "1", "yes")

    return client.update_user_consent(user_id=_ar_user_id(user), consent_type=consent_type, granted=granted)


@frappe.whitelist(methods=["GET"])
def get_privacy_config() -> dict:
    """
    Get privacy configuration for the current tenant.

    Returns tenant-level config (for admins) and user-level privacy state.
    """
    user = frappe.session.user
    is_admin = "System Manager" in frappe.get_roles(user)
    client = _get_client()

    result = {"is_admin": is_admin}

    # Tenant-level config (admin only)
    if is_admin:
        try:
            result["tenant"] = client.get_tenant_privacy_config()
        except Exception:
            result["tenant"] = None

    # User-level privacy state (always included)
    try:
        user_data = client.get_user(user_id=_ar_user_id(user))
        if user_data:
            result["user_privacy"] = {
                "memory_consent": user_data.get("memory_consent", False),
                "processing_restricted": user_data.get("processing_restricted", False),
            }
    except Exception:
        result["user_privacy"] = None

    return result


@frappe.whitelist(methods=["POST"])
def update_privacy_config(config: str | None = None) -> dict:
    """
    Update tenant-level privacy configuration. Admin only.

    Updatable: default_memory_consent, conversation_retention_days, privacy_contact_email.
    """
    import json

    if "System Manager" not in frappe.get_roles(frappe.session.user):
        frappe.throw(_("Only administrators can update privacy configuration"))

    if not config:
        frappe.throw(_("No configuration provided"))

    client = _get_client()
    config_dict = json.loads(config) if isinstance(config, str) else config
    return client.update_tenant_privacy_config(config_dict)


@frappe.whitelist(methods=["POST"])
def save_initial_consent(memory_consent: bool = False) -> dict:
    """
    Save initial privacy consent from the onboarding consent screen.

    Records the user's memory consent, marks AR-side onboarding complete, and
    flips the local FACO User Preferences `privacy_consent_complete` flag so
    the feature tour doesn't reappear.
    """
    user = frappe.session.user
    ar_user = _ar_user_id(user)
    client = _get_client()

    # Convert string "true"/"false" from form data
    if isinstance(memory_consent, str):
        memory_consent = memory_consent.lower() in ("true", "1", "yes")

    # Save consent choice via AR. This write is AUTHORITATIVE — do NOT swallow a
    # failure. Swallowing it and then marking the tour complete (below) is what
    # silently locked users into memory_consent=0 while the UI showed consent
    # ON: the flag never landed and the tour never reappeared to retry. Let the
    # exception propagate so the SPA surfaces it and the tour retries next load.
    client.update_user_consent(user_id=ar_user, consent_type="memory", granted=memory_consent)

    # Mark onboarding complete on AR side (replaces the old OnboardingChat flow).
    # Non-critical: a failure here must not undo the consent write above, so it
    # stays best-effort/logged.
    try:
        client.complete_onboarding(user_id=ar_user)
    except Exception as e:
        frappe.log_error(title="Privacy Initial Consent", message=f"Failed to mark onboarding complete: {e}")

    # Mark privacy consent complete locally — only reached when the AR consent
    # write above succeeded. Keyed by the Frappe docname (local mirror).
    prefs_name = frappe.db.get_value("FAC Chat User Preferences", {"user": user}, "name")
    if prefs_name:
        frappe.db.set_value("FAC Chat User Preferences", prefs_name, "privacy_consent_complete", 1)
    else:
        # Create preferences if they don't exist
        doc = frappe.new_doc("FAC Chat User Preferences")
        doc.user = user
        doc.privacy_consent_complete = 1
        doc.insert(ignore_permissions=True)

    return {
        "success": True,
        "memory_consent": memory_consent,
    }
