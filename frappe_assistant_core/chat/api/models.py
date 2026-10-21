# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""AI model listing and preference management."""

import time

import frappe
from frappe import _

from ._helpers import (
    _not_registered_error,
    _safe_error,
)

PREFERENCES_DOCTYPE = "FAC Chat User Preferences"
MAX_MODEL_ID_LENGTH = 140
AVAILABLE_MODELS_TTL = 300  # seconds a user's available-model ids are trusted
AVAILABLE_MODELS_FAILURE_TTL = 30  # seconds an AR outage is remembered, so turns do not each wait
AVAILABLE_MODELS_TIMEOUT = 3  # a turn waits at most this long for AR's list


def _saved_model() -> str:
    """The session user's saved model choice ("" when none, or before the column is migrated)."""
    if not frappe.db.has_column(PREFERENCES_DOCTYPE, "selected_model"):
        return ""
    return frappe.db.get_value(PREFERENCES_DOCTYPE, frappe.session.user, "selected_model") or ""


def available_models_key() -> str:
    return f"fac_available_models::{frappe.session.user}"


def _remember_available(model_ids: list[str] | None) -> None:
    """Keep the ids for AVAILABLE_MODELS_TTL; None records that AR could not answer."""
    # Aged in code, not by a Redis TTL: a TTL'd key reads back as a miss within the request that
    # set it on Frappe v15.
    frappe.cache.set_value(available_models_key(), {"ids": model_ids, "at": time.time()})


def _available_model_ids() -> list[str] | None:
    """Ids of the models the session user can use now, or None when AR cannot say.

    Served from the copy get_available_models leaves; asks AR (once per AVAILABLE_MODELS_TTL)
    only when there is none.
    """
    cached = frappe.cache.get_value(available_models_key())
    if cached:
        ttl = AVAILABLE_MODELS_TTL if cached["ids"] is not None else AVAILABLE_MODELS_FAILURE_TTL
        if time.time() - cached["at"] < ttl:
            return cached["ids"]
    ids = None
    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        result = client.list_available_models(timeout=AVAILABLE_MODELS_TIMEOUT) if client else None
        if result and not result.get("error_code"):
            ids = [m.get("model_id") for m in result.get("models", [])]
    except Exception:
        pass
    _remember_available(ids)
    return ids


def usable_saved_model() -> str:
    """The saved model, but only when the user can still use it ("" otherwise).

    A turn that defaults to the saved model must never fail because of it: AR refuses a model
    that was retired or that the plan no longer includes, so a stale or unverifiable choice falls
    back to AR's own default. "auto" is a mode, not a model, and always passes.
    """
    saved = _saved_model()
    if not saved or saved == "auto":
        return saved
    ids = _available_model_ids()
    return saved if ids is not None and saved in ids else ""


@frappe.whitelist(methods=["GET"])
def get_available_models():
    """
    Get available AI models from AR based on subscription tier.

    Uses the new streaming.list_available_models endpoint which supports
    per-request model selection. The user's choice is saved on the server
    (``selected_model``) so every browser and the Desk widget share it.

    Returns:
            dict: {
                    "success": bool,
                    "models": [...],
                    "max_tier_rank": float,
                    "default_model": str,
                    "selected_model": str,  # "" when the user has not chosen
                    "auto_mode": {
                            "enabled": bool,
                            "description": str,
                            "model_id": "auto",
                            "fallback_chain_length": int
                    }
            }
    """
    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        result = client.list_available_models(timeout=8)
        if not result:
            return {"error": _("Failed to fetch models")}

        # AR gates this endpoint on terms acceptance and answers with an
        # actionable error_code (TERMS_UPDATE_REQUIRED / TERMS_NOT_ACCEPTED)
        # instead of a model list. Pass the code through so the SPA can open
        # the terms flow rather than rendering an empty model picker.
        if result.get("error_code"):
            return {
                "error": result.get("error") or _("Models are unavailable right now."),
                "error_code": result["error_code"],
                "terms_url": result.get("terms_url"),
                "required_version": result.get("required_version"),
            }

        # Organize models by tier for the UI
        models = result.get("models", [])
        models_by_tier = {}
        for model in models:
            tier = model.get("tier", "Standard")
            if tier not in models_by_tier:
                models_by_tier[tier] = []
            models_by_tier[tier].append(model)

        selected = _saved_model()
        if models:
            model_ids = [m.get("model_id") for m in models]
            _remember_available(model_ids)
            # The stored row stays: a GET's writes are rolled back, and turns skip a stale id anyway.
            if selected != "auto" and selected not in model_ids:
                selected = ""

        return {
            "success": True,
            "models": models,
            "models_by_tier": models_by_tier,
            "max_tier_rank": result.get("max_tier_rank", 999),
            "default_model": result.get("default_model"),
            "selected_model": selected,
            "auto_mode": result.get("auto_mode"),
        }

    except Exception as e:
        frappe.log_error(title="FACO Models Error", message=f"Error getting models: {e!s}")
        return {"error": _safe_error(e, "FACO Models Error")}


@frappe.whitelist(methods=["POST"])
def set_preferred_model(model_id: str | None = None):
    """
    Set the preferred AI model in AR.

    Args:
            model_id: Model ID to set as preferred

    Returns:
            dict: {"success": bool}
    """
    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"success": False, "error": _not_registered_error()}

        success = client.set_preferred_model(model_id)

        if success:
            from frappe_assistant_core.chat.quota_cache import set_field

            set_field("preferred_model", model_id)

        return {"success": success}

    except Exception as e:
        frappe.log_error(title="FACO Model Error", message=f"Error setting model: {e!s}")
        return {"success": False, "error": _safe_error(e, "FACO Model Error")}


@frappe.whitelist(methods=["POST"])
def set_selected_model(model_id: str) -> dict:
    """
    Save the session user's model choice so it follows them across browsers.

    Args:
            model_id: "auto", a model id (at most 140 characters), or "" to clear

    Returns:
            dict: {"success": True, "selected_model": str}
    """
    from frappe_assistant_core.chat.doctype.fac_chat_user_preferences.fac_chat_user_preferences import (
        FACChatUserPreferences,
    )

    model_id = (model_id or "").strip()
    if len(model_id) > MAX_MODEL_ID_LENGTH:
        frappe.throw(
            _("A model id can be at most {0} characters.").format(MAX_MODEL_ID_LENGTH),
            frappe.ValidationError,
        )

    prefs = FACChatUserPreferences.get_or_create_preferences()
    prefs.selected_model = model_id
    prefs.save(ignore_permissions=True)
    frappe.cache.delete_value(available_models_key())
    return {"success": True, "selected_model": model_id}
