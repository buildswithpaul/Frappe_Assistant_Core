# Frappe Assistant Core - Mobile Usage & Subscription API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Endpoints consumed by the mobile app for the usage dashboard."""

from __future__ import annotations

import frappe

from .._helpers import _safe_error


@frappe.whitelist(methods=["GET"])
def get_usage_stats() -> dict:
    """
    Get current usage statistics for the mobile app.

    Returns:
            dict: Usage statistics including tokens, messages, sessions, workflows
    """
    try:
        from frappe_assistant_core.chat.quota_cache import get_quota_snapshot

        user = frappe.session.user
        snap = get_quota_snapshot()

        tokens_quota = snap.get("quota_total", 0)
        tokens_used = snap.get("quota_used", 0)
        is_unlimited = tokens_quota == -1

        if is_unlimited:
            percentage_used = 0
        else:
            percentage_used = (tokens_used / tokens_quota * 100) if tokens_quota > 0 else 0

        # Get message count for current period
        from frappe.utils import get_first_day, now

        period_start = get_first_day(now())

        messages_sent = frappe.db.count(
            "FAC Chat Message", filters={"user": user, "role": "user", "creation": [">=", period_start]}
        )

        sessions_created = len(
            frappe.get_all(
                "FAC Chat Message",
                filters={"user": user, "creation": [">=", period_start]},
                distinct=True,
                pluck="session_id",
                limit_page_length=0,
            )
        )

        workflows_executed = 0

        return {
            "tokens_used": tokens_used,
            "tokens_quota": tokens_quota,
            "is_unlimited": is_unlimited,
            "percentage_used": round(percentage_used, 1),
            "quota_resets_at": None,
            "messages_sent": messages_sent,
            "sessions_created": sessions_created,
            "workflows_executed": workflows_executed,
        }

    except Exception as e:
        frappe.log_error(title="FACO Usage Stats Error", message=f"Error getting usage stats: {e!s}")
        return {"error": _safe_error(e, "FACO Usage Stats Error")}


@frappe.whitelist(methods=["GET"])
def get_usage_history(days: int = 30) -> list:
    """
    Get usage history for charts.

    Args:
            days: Number of days of history to return

    Returns:
            list: Daily usage data
    """
    try:
        user = frappe.session.user
        days = min(int(days), 90)  # Max 90 days

        from frappe.utils import add_days, nowdate

        # Get daily message counts
        history = frappe.get_all(
            "FAC Chat Message",
            filters={"user": user, "creation": [">=", add_days(nowdate(), -days)]},
            fields=["DATE(creation) as date", "count(name) as messages"],
            group_by="DATE(creation)",
            order_by="date desc",
        )

        # Format response
        result = []
        for row in history:
            result.append(
                {
                    "date": str(row.date),
                    "tokens_used": 0,  # Would need to track per-message tokens
                    "messages": row.messages,
                }
            )

        return result

    except Exception as e:
        frappe.log_error(title="FACO Usage History Error", message=f"Error getting usage history: {e!s}")
        return []


@frappe.whitelist(methods=["GET"])
def get_subscription_info() -> dict:
    """
    Get subscription information for the mobile app.

    Returns:
            dict: Subscription details
    """
    try:
        from frappe_assistant_core.chat.quota_cache import get_quota_snapshot

        settings = frappe.get_single("FAC Chat Settings")
        snap = get_quota_snapshot()

        plan_name = snap.get("plan", "Free")
        tokens_quota = snap.get("quota_total", 0)
        tokens_used = snap.get("quota_used", 0)
        is_unlimited = tokens_quota == -1

        # Determine status
        if settings.registration_status != "Registered":
            status = "expired"
        elif is_unlimited or tokens_used < tokens_quota:
            status = "active"
        else:
            status = "active"  # Still active even if over quota

        # Features based on plan
        features = ["AI Chat", "Tool Execution"]
        if plan_name != "Free":
            features.extend(["Priority Support", "Advanced Models"])
        if plan_name == "Pro" or plan_name == "Enterprise":
            features.extend(["Custom Workflows", "API Access"])

        last_sync = snap.get("last_sync", "")
        return {
            "plan_name": plan_name,
            "status": status,
            "started_at": str(last_sync) if last_sync else None,
            "expires_at": None,
            "tokens_quota": tokens_quota,
            "tokens_used": tokens_used,
            "is_unlimited": is_unlimited,
            "features": features,
        }

    except Exception as e:
        frappe.log_error(title="FACO Subscription Error", message=f"Error getting subscription info: {e!s}")
        return {"error": _safe_error(e, "FACO Subscription Error")}


@frappe.whitelist(methods=["GET"])
def get_model_usage() -> list:
    """
    Get usage breakdown by AI model.

    Returns:
            list: Usage per model
    """
    try:
        user = frappe.session.user

        # Get token usage by model from usage logs
        model_usage = frappe.get_all(
            "FAC Chat Usage Log",
            filters={"user": user},
            fields=["COALESCE(model, 'Unknown') as model_id", "SUM(tokens_total) as tokens_used"],
            group_by="model",
            order_by="tokens_used desc",
            limit_page_length=10,
        )

        if not model_usage:
            return []

        # Calculate percentages
        total_tokens = sum(m.tokens_used or 0 for m in model_usage)

        result = []
        for model in model_usage:
            tokens = model.tokens_used or 0
            percentage = (tokens / total_tokens * 100) if total_tokens > 0 else 0

            # Format model name
            model_id = model.model_id
            model_name = model_id.replace("-", " ").title() if model_id else "Unknown"

            result.append(
                {
                    "model_id": model_id,
                    "model_name": model_name,
                    "tokens_used": tokens,
                    "percentage": round(percentage, 1),
                }
            )

        return result

    except Exception as e:
        frappe.log_error(title="FACO Model Usage Error", message=f"Error getting model usage: {e!s}")
        return []
