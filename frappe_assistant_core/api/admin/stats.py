# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# AGPL-3.0-or-later — see <https://www.gnu.org/licenses/>.

import frappe
from frappe import _


@frappe.whitelist(methods=["GET", "POST"])
def get_usage_statistics() -> dict:
    """Get usage statistics for the assistant."""
    from frappe_assistant_core.utils.logger import api_logger
    from frappe_assistant_core.utils.permissions import check_assistant_admin_permission

    if not check_assistant_admin_permission(frappe.session.user):
        api_logger.warning(
            f"Usage statistics denied for non-admin user: {frappe.session.user} "
            f"with roles: {frappe.get_roles(frappe.session.user)}"
        )

    frappe.only_for(["System Manager", "Assistant Admin"])

    try:
        api_logger.info(f"Usage statistics requested by user: {frappe.session.user}")

        today = frappe.utils.today()
        week_start = frappe.utils.add_days(today, -7)

        # Audit log statistics
        try:
            total_audit = frappe.db.count("Assistant Audit Log") or 0
            today_audit = frappe.db.count("Assistant Audit Log", {"creation": (">=", today)}) or 0
            week_audit = frappe.db.count("Assistant Audit Log", {"creation": (">=", week_start)}) or 0
        except Exception as e:
            api_logger.warning(f"Audit stats error: {e}")
            total_audit = today_audit = week_audit = 0

        # Tool statistics
        try:
            from frappe_assistant_core.utils.plugin_manager import get_plugin_manager

            plugin_manager = get_plugin_manager()
            all_tools = plugin_manager.get_all_tools()
            total_tools = len(all_tools)
            enabled_tools = len(all_tools)
            api_logger.debug(f"Tool stats: total={total_tools}, enabled={enabled_tools}")
        except Exception as e:
            api_logger.warning(f"Tool stats error: {e}")
            total_tools = enabled_tools = 0

        # Recent activity
        try:
            recent_activity = (
                frappe.db.get_list(
                    "Assistant Audit Log",
                    fields=["action", "tool_name", "user", "status", "timestamp"],
                    order_by="timestamp desc",
                    limit=10,
                )
                or []
            )
        except Exception as e:
            api_logger.warning(f"Recent activity error: {e}")
            recent_activity = []

        return {
            "success": True,
            "data": {
                "connections": {"total": total_audit, "today": today_audit, "this_week": week_audit},
                "audit_logs": {"total": total_audit, "today": today_audit, "this_week": week_audit},
                "tools": {"total": total_tools, "enabled": enabled_tools},
                "recent_activity": recent_activity,
            },
        }

    except Exception as e:
        api_logger.error(f"Error getting usage statistics: {e}")
        return {"success": False, "error": str(e)}


@frappe.whitelist(methods=["GET", "POST"])
def ping() -> dict:
    """Ping endpoint for testing connectivity."""
    from frappe_assistant_core.utils.logger import api_logger
    from frappe_assistant_core.utils.permissions import check_assistant_permission

    try:
        if not check_assistant_permission(frappe.session.user):
            frappe.throw(_("Access denied"))

        return {
            "success": True,
            "message": "pong",
            "timestamp": frappe.utils.now(),
            "user": frappe.session.user,
        }

    except Exception as e:
        api_logger.error(f"Error in ping: {e}")
        return {"success": False, "message": f"Ping failed: {str(e)}"}
