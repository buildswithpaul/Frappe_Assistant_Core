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

"""FAC Admin endpoints for the "FAC Bot in Raven" switch."""

import frappe
from frappe import _
from frappe.utils import sbool

from frappe_assistant_core.integrations.raven import bot


def _require_chat_admin() -> None:
    if not frappe.has_permission("Assistant Core Settings", "write"):
        frappe.throw(_("You do not have permission to manage FAC Chat."), frappe.PermissionError)


@frappe.whitelist(methods=["GET"])
def get_raven_bot() -> dict:
    """Whether Raven is installed here, and whether FAC Bot answers in it."""
    _require_chat_admin()
    return {
        "available": "raven" in frappe.get_installed_apps(),
        "enabled": bool(frappe.db.get_single_value("FAC Chat Settings", "enable_raven_bot")),
    }


@frappe.whitelist(methods=["POST"])
def set_raven_bot_enabled(enabled: bool) -> dict:
    """Switch FAC Bot on or off. Switching on creates the bot; switching off keeps it."""
    _require_chat_admin()
    if "raven" not in frappe.get_installed_apps():
        frappe.throw(_("Raven is not installed on this site."))
    enabled = sbool(enabled)
    frappe.db.set_single_value("FAC Chat Settings", "enable_raven_bot", int(enabled))
    if enabled:
        bot.ensure_bot()
    bot.clear_state_cache()
    return {"enabled": enabled}
