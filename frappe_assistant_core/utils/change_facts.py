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
from frappe.utils import cint

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
SYSTEM_MODULES = frozenset({"Core", "Integrations", "Email", "Automation"})
MONEY_OR_STOCK_MODULES = frozenset({"Accounts", "Stock", "Payroll"})
# Doctypes whose records notify someone as soon as they are saved.
MESSAGING_DOCTYPES = frozenset(
    {"ToDo", "Communication", "Email Queue", "Notification Log", "Event", "Comment"}
)
# Doctypes whose records are themselves a message leaving the system.
OUTBOUND_MESSAGE_DOCTYPES = frozenset(
    {
        "Communication",
        "Email Queue",
        "Notification Log",
        "Newsletter",
        "Email Campaign",
        "Appointment",
        "Raven Message",
    }
)
# The inputs of a write to one record. Any other key (documents, records, names, an import
# session, planned masters, or one FAC does not know) makes the call a batch: the facts here
# describe a single record and cannot vouch for what a batch holds.
SINGLE_RECORD_INPUTS = frozenset({"doctype", "name", "data", "edits", "submit", "validate_only"})
CREDENTIAL_FIELDS = frozenset({"api_key", "api_secret"})
# Doctypes whose records other people see as soon as they are saved.
GO_LIVE_DOCTYPES = frozenset(
    {
        "Web Page",
        "Web Form",
        "Workspace",
        "Custom HTML Block",
        "Letter Head",
        "Website Theme",
        "Dashboard",
        "Dashboard Chart",
        "Number Card",
        "Blog Post",
        "Print Format",
        "Help Article",
        "Portal Settings",
    }
)
# Fields that, once set, put a record in front of other people.
GO_LIVE_FIELDS = (
    "published",
    "public",
    "is_public",
    "notify_on_login",
    "notify_on_every_login",
    "is_default",
    "publish",
    "show_in_website",
)


def change_facts(tool_name: str, tool_input: Any) -> Dict[str, Any]:
    """The facts about one write, or ``{}`` when the doctype is unknown or anything goes wrong."""
    try:
        return _facts(tool_name, tool_input)
    except Exception:
        doctype = tool_input.get("doctype") if isinstance(tool_input, dict) else None
        frappe.logger("frappe_assistant_core").warning(f"change_facts failed for doctype {doctype!r}")
        return {}


def _facts(tool_name: str, tool_input: Any) -> Dict[str, Any]:
    if not isinstance(tool_input, dict):
        return {}
    doctype = tool_input.get("doctype")
    if not isinstance(doctype, str) or not doctype:
        return {}
    # The name as stored. The database matches names without regard to case, so "notification
    # log" finds the DocType; the sets below are matched exactly and would miss it.
    doctype = frappe.db.get_value("DocType", doctype, "name")
    if not doctype:
        return {}
    meta = frappe.get_meta(doctype)
    name = tool_input.get("name")
    return {
        "doctype_kind": _doctype_kind(doctype, meta),
        "is_money_or_stock": meta.module in MONEY_OR_STOCK_MODULES,
        "submits": _submits(tool_name, tool_input, doctype),
        "sends_messages": _sends_messages(doctype),
        "custom_doctype": bool(meta.custom),
        "affects_others": _affects_others(doctype, tool_input)
        or _already_live(tool_name, doctype, name, meta),
        "exists": bool(frappe.db.exists(doctype, name)) if name and tool_name != "create_document" else None,
        "bulk": bool(set(tool_input) - SINGLE_RECORD_INPUTS),
        # The two facts auto-approve mode reads: it never runs an edit of a submitted or
        # cancelled record, or a record that is a message going out, without a card.
        "target_submitted": _target_submitted(tool_name, doctype, name, meta),
        "outbound_message": doctype in OUTBOUND_MESSAGE_DOCTYPES,
    }


def _target_submitted(tool_name: str, doctype: str, name: Any, meta) -> bool:
    """Whether the write lands on a record that is already submitted or cancelled."""
    if tool_name == "create_document" or not meta.is_submittable:
        return False
    if not isinstance(name, str) or not name:
        # An update that does not say which record cannot be shown to be a draft.
        return True
    return cint(frappe.db.get_value(doctype, name, "docstatus")) != 0


def _doctype_kind(doctype: str, meta) -> str:
    if doctype in CUSTOMISATION_DOCTYPES:
        return "customisation"
    if doctype in USER_ADMIN_DOCTYPES or any(
        f.fieldname in CREDENTIAL_FIELDS or f.fieldtype == "Password" for f in meta.fields
    ):
        return "user_admin"
    if meta.module in SYSTEM_MODULES or meta.issingle:
        return "system"
    return "business"


def _submits(tool_name: str, tool_input: Dict[str, Any], doctype: str) -> bool:
    if tool_name in ("document_action", "run_workflow"):
        # Submit, cancel, amend and every workflow transition move the document's docstatus.
        return True
    if tool_name == "delete_document":
        return False
    data = tool_input.get("data")
    docstatus = data.get("docstatus") if isinstance(data, dict) else None
    if cint(docstatus) in (1, 2) or bool(tool_input.get("submit")):
        return True
    # Saving a new workflow state is a transition (an approval, a rejection), as run_workflow is.
    return isinstance(data, dict) and any(field in data for field in _workflow_state_fields(doctype))


def _workflow_state_fields(doctype: str) -> list[str]:
    """The field an active workflow of ``doctype`` keeps its state in."""
    return frappe.get_all(
        "Workflow", filters={"document_type": doctype, "is_active": 1}, pluck="workflow_state_field"
    )


def _already_live(tool_name: str, doctype: str, name: Any, meta) -> bool:
    """Whether an edit lands on a record other people already see (published, public, a
    default): changing it changes what they see, whichever fields the edit names."""
    if tool_name != "update_document" or not isinstance(name, str) or not name:
        return False
    fields = [field for field in GO_LIVE_FIELDS if meta.has_field(field)]
    if not fields:
        return False
    stored = frappe.db.get_value(doctype, name, fields, as_dict=True) or {}
    return any(cint(stored.get(field)) for field in fields)


def _affects_others(doctype: str, tool_input: Dict[str, Any]) -> bool:
    if doctype in GO_LIVE_DOCTYPES:
        return True
    field_sets = [tool_input["data"]] if "data" in tool_input else []
    if "records" in tool_input:
        records = tool_input["records"]
        if not isinstance(records, list):
            return True
        # create_document takes field dicts; update_document takes {"name", "data"} entries.
        field_sets += [r.get("data") if isinstance(r, dict) and "data" in r else r for r in records]
    # A shape FAC does not recognise could hide a go-live field, so it counts as going live.
    return any(not isinstance(fields, dict) or _sets_go_live_field(fields) for fields in field_sets)


def _sets_go_live_field(fields: Dict[str, Any]) -> bool:
    return any(cint(fields.get(field)) for field in GO_LIVE_FIELDS)


def _sends_messages(doctype: str) -> bool:
    if doctype in MESSAGING_DOCTYPES:
        return True
    notified = frappe.get_all("Notification", filters={"document_type": doctype, "enabled": 1}, limit=1)
    assigned = frappe.get_all("Assignment Rule", filters={"document_type": doctype, "disabled": 0}, limit=1)
    flowing = frappe.get_all(
        "Workflow", filters={"document_type": doctype, "is_active": 1, "send_email_alert": 1}, limit=1
    )
    hooked = frappe.get_all("Webhook", filters={"webhook_doctype": doctype, "enabled": 1}, limit=1)
    scripted = frappe.get_all(
        "Server Script",
        filters={"reference_doctype": doctype, "script_type": "DocType Event", "disabled": 0},
        limit=1,
    )
    return bool(notified or hooked or assigned or flowing or scripted)
