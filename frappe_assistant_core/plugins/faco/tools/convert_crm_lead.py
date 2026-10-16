import inspect
from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.plugins.faco.crm.tool import CrmTool, crm_link, resolve_record
from frappe_assistant_core.utils.savepoint import open_savepoint, release_savepoint, rollback_to_savepoint

# convert_to_deal writes the contact, organization, deal and the lead's converted flag in
# turn; a conversion CRM refuses partway must leave none of them behind.
_SAVEPOINT = "fac_crm_convert"
# CRM sets these itself; a model-supplied value would unlink the deal from its lead.
_CRM_OWNED = ("name", "lead", "naming_series", "contacts", "organization", "doctype")


class ConvertCrmLead(CrmTool):
    def __init__(self):
        super().__init__()
        self.name = "convert_crm_lead"
        self.description = (
            "Convert a Frappe CRM lead into a deal through CRM's own conversion, as the Convert to Deal "
            "button does: the lead is marked converted, a contact and organization are created or reused, "
            "and the deal carries the lead's history. Converting the same lead again returns its deal. "
            "Never create a CRM Deal by hand to convert a lead."
        )
        self.requires_permission = None
        self.inputSchema = {
            "type": "object",
            "properties": {
                "lead": {"type": "string", "description": "CRM Lead name"},
                "deal_fields": {
                    "type": "object",
                    "description": "Extra deal fields, e.g. expected_deal_value, expected_closure_date, next_step",
                },
            },
            "required": ["lead"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        from crm.fcrm.doctype.crm_lead.crm_lead import convert_to_deal

        doc, error = resolve_record("CRM Lead", arguments.get("lead"), ptype="write")
        if error:
            return error
        # CRM before 1.86 has no if_converted, so a retry would make a second deal.
        if existing := frappe.db.get_value("CRM Deal", {"lead": doc.name}, "name"):
            if not frappe.has_permission("CRM Deal", "read", existing):
                return {"success": True, "already_converted": True}
            return {
                "success": True,
                "deal": existing,
                "link": crm_link("CRM Deal", existing),
                "already_converted": True,
            }

        fields = arguments.get("deal_fields")
        fields = {k: v for k, v in fields.items() if k not in _CRM_OWNED} if isinstance(fields, dict) else {}
        kwargs = {"lead": doc.name, "deal": fields or None}
        if "if_converted" in inspect.signature(convert_to_deal).parameters:
            kwargs["if_converted"] = "Return Existing"
        marks = open_savepoint(_SAVEPOINT)
        try:
            deal = convert_to_deal(**kwargs)
        except Exception as e:
            rollback_to_savepoint(_SAVEPOINT, marks, "CRM Lead", doc.name)
            message = str(e) or frappe.flags.error_message or _("CRM refused to convert {0}").format(doc.name)
            return {"success": False, "error": frappe.utils.strip_html(str(message))}
        release_savepoint(_SAVEPOINT)
        return {"success": True, "deal": deal, "link": crm_link("CRM Deal", deal)}
