# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Settings endpoints for showing the FACO widget in other Frappe apps."""

import frappe
from frappe import _
from frappe.utils import sbool

from frappe_assistant_core.chat.embed import apps as embed_apps
from frappe_assistant_core.chat.widget_boot import widget_entry


def _require_chat_admin() -> None:
    if not frappe.has_permission("Assistant Core Settings", "write"):
        frappe.throw(_("You do not have permission to manage FAC Chat."), frappe.PermissionError)


@frappe.whitelist(methods=["GET"])
def get_embed_apps() -> list[dict]:
    """Every app that can show the widget, and whether it does."""
    _require_chat_admin()
    enabled = embed_apps.enabled_app_names()
    return [{**app, "enabled": app["app"] in enabled} for app in embed_apps.discover_spa_apps()]


@frappe.whitelist(methods=["POST"])
def set_embed_app_enabled(app_name: str, enabled: bool) -> dict:
    """Show or hide the widget in one app. Saving FAC Chat Settings clears the route cache."""
    _require_chat_admin()
    enabled = sbool(enabled)
    if app_name not in {app["app"] for app in embed_apps.discover_spa_apps()}:
        frappe.throw(_("{0} is not a Frappe app that can show the widget.").format(app_name))
    settings = frappe.get_single(embed_apps.SETTINGS)
    kept = [row.app_name for row in settings.widget_embed_apps if row.app_name != app_name]
    settings.set("widget_embed_apps", [{"app_name": name} for name in kept])
    if enabled:
        settings.append("widget_embed_apps", {"app_name": app_name})
    settings.save()
    return {"app_name": app_name, "enabled": enabled}


@frappe.whitelist(methods=["GET"])
def get_widget_entry() -> dict | None:
    """The built widget entry for pages without Desk boot info (widget_embed.js)."""
    return widget_entry()
