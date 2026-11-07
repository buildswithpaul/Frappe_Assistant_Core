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

"""Content-free facts about a managed write, for FAC Cloud to pick an approval level.

Booleans and enums only: no field values and no record names ever leave this module. FAC Cloud
treats a missing key, or an empty dict, as "FAC cannot say" and asks the user.
"""

from typing import Any, Dict

import frappe

from frappe_assistant_core.utils.customisation import CUSTOMISATION_DOCTYPES

USER_ADMIN_DOCTYPES = frozenset(
    {
        "User",
        "Role Profile",
        "Module Profile",
        "User Permission",
        "Has Role",
        "OAuth Client",
        "OAuth Bearer Token",
        "API Key",
    }
)
SYSTEM_MODULES = frozenset({"Core", "Integrations", "Email"})
MONEY_OR_STOCK_MODULES = frozenset({"Accounts", "Stock", "Payroll"})
# Doctypes whose records notify someone as soon as they are saved.
MESSAGING_DOCTYPES = frozenset(
    {"ToDo", "Communication", "Email Queue", "Notification Log", "Event", "Comment"}
)
CREDENTIAL_FIELDS = frozenset({"api_key", "api_secret"})


def change_facts(tool_name: str, tool_input: Any) -> Dict[str, Any]:
    """The facts about one write, or ``{}`` when the doctype is unknown or anything goes wrong."""
    try:
        return _facts(tool_name, tool_input)
    except Exception:
        return {}


def _facts(tool_name: str, tool_input: Any) -> Dict[str, Any]:
    if not isinstance(tool_input, dict):
        return {}
    doctype = tool_input.get("doctype")
    if not isinstance(doctype, str) or not doctype or not frappe.db.exists("DocType", doctype):
        return {}
    meta = frappe.get_meta(doctype)
    name = tool_input.get("name")
    return {
        "doctype_kind": _doctype_kind(doctype, meta),
        "is_money_or_stock": meta.module in MONEY_OR_STOCK_MODULES,
        "submits": _submits(tool_name, tool_input),
        "sends_messages": _sends_messages(doctype),
        "exists": bool(frappe.db.exists(doctype, name)) if name else None,
        "bulk": "records" in tool_input or "names" in tool_input,
    }


def _doctype_kind(doctype: str, meta) -> str:
    if doctype in CUSTOMISATION_DOCTYPES:
        return "customisation"
    if doctype in USER_ADMIN_DOCTYPES or any(f.fieldname in CREDENTIAL_FIELDS for f in meta.fields):
        return "user_admin"
    if meta.module in SYSTEM_MODULES or meta.issingle:
        return "system"
    return "business"


def _submits(tool_name: str, tool_input: Dict[str, Any]) -> bool:
    if tool_name == "delete_document":
        return False
    data = tool_input.get("data")
    docstatus = data.get("docstatus") if isinstance(data, dict) else None
    return docstatus in (1, 2) or bool(tool_input.get("submit"))


def _sends_messages(doctype: str) -> bool:
    if doctype in MESSAGING_DOCTYPES:
        return True
    notified = frappe.get_all("Notification", filters={"document_type": doctype, "enabled": 1}, limit=1)
    hooked = frappe.get_all("Webhook", filters={"webhook_doctype": doctype, "enabled": 1}, limit=1)
    return bool(notified or hooked)
