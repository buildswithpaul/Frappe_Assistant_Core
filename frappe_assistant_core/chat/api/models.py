# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""AI model listing and preference management."""

import frappe
from frappe import _

from ._helpers import (
    _not_registered_error,
    _safe_error,
)


@frappe.whitelist(methods=["GET"])
def get_available_models():
    """
    Get available AI models from AR based on subscription tier.

    Uses the new streaming.list_available_models endpoint which supports
    per-request model selection. Model selection is now handled client-side
    via localStorage instead of server-side preferred model setting.

    Returns:
            dict: {
                    "success": bool,
                    "models": [...],
                    "max_tier_rank": float,
                    "default_model": str,
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

        return {
            "success": True,
            "models": models,
            "models_by_tier": models_by_tier,
            "max_tier_rank": result.get("max_tier_rank", 999),
            "default_model": result.get("default_model"),
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
