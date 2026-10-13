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

"""FAC Bot: the Raven bot FACO answers through. Raven's own AI stays off for it (is_ai_bot=0),
so Raven never calls OpenAI for it and FACO is the only thing that answers."""

from typing import Literal

import frappe

BOT_NAME = "FAC Bot"
BOT_IMAGE = "/assets/frappe_assistant_core/images/FAC_mark.svg"
_STATE_KEY = "fac_raven_bot_state"


def state() -> Literal["absent", "off", "on"]:
    """Cached: every Raven message asks, so it must not cost a query once warm."""
    return frappe.cache.get_value(_STATE_KEY, generator=_compute_state)


def _compute_state() -> str:
    if "raven" not in frappe.get_installed_apps() or not frappe.db.exists("Raven Bot", BOT_NAME):
        return "absent"
    return "on" if frappe.db.get_single_value("FAC Chat Settings", "enable_raven_bot") else "off"


def clear_state_cache(doc=None, method=None) -> None:
    frappe.cache.delete_value(_STATE_KEY)


def ensure_bot() -> str:
    """Create FAC Bot if missing. Callers check the admin permission first."""
    if not frappe.db.exists("Raven Bot", BOT_NAME):
        frappe.get_doc(
            {
                "doctype": "Raven Bot",
                "bot_name": BOT_NAME,
                "image": BOT_IMAGE,
                "is_ai_bot": 0,
                "description": "FACO, your ERPNext assistant. DM me or @mention me in a channel.",
            }
        ).insert(ignore_permissions=True)
    clear_state_cache()
    return BOT_NAME


def ensure_bot_after_migrate() -> None:
    if "raven" in frappe.get_installed_apps() and frappe.db.get_single_value(
        "FAC Chat Settings", "enable_raven_bot"
    ):
        ensure_bot()
