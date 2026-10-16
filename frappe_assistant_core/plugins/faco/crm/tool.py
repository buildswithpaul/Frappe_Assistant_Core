"""What the Frappe CRM tools share: they load only where CRM is installed, and take a lead or deal."""

from typing import Optional, Tuple

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool

RECORD_ROUTES = {"CRM Lead": "leads", "CRM Deal": "deals"}


def crm_installed() -> bool:
    # Installed on this site, not merely present on the bench.
    return "crm" in frappe.get_installed_apps() and bool(frappe.db.exists("DocType", "CRM Lead"))


def crm_link(doctype: str, name: str) -> str:
    """The record's page in the CRM app — not Desk."""
    return f"/crm/{RECORD_ROUTES[doctype]}/{name}"


def resolve_record(doctype: str, name: str, ptype: str = "read"):
    """The lead or deal the user may ``ptype``, or an error dict.

    A record the user cannot see reads exactly like a missing one, so the answer
    never reveals that it exists.
    """
    if doctype not in RECORD_ROUTES:
        return None, {"success": False, "error": _("Pass a CRM Lead or a CRM Deal, not {0}").format(doctype)}
    name = str(name or "").strip()
    if not name or not frappe.db.exists(doctype, name) or not frappe.has_permission(doctype, ptype, name):
        return None, {"success": False, "error": _("{0} {1} was not found").format(_(doctype), name)}
    return frappe.get_doc(doctype, name), None


RECORD_SCHEMA = {
    "doctype": {"type": "string", "enum": list(RECORD_ROUTES), "description": "CRM Lead or CRM Deal"},
    "name": {"type": "string", "description": "The lead or deal name, e.g. CRM-LEAD-2026-00009"},
}


class CrmTool(BaseTool):
    """Base for the CRM tools. Abstract, so the plugin loader never registers it as a tool."""

    def validate_dependencies(self) -> Tuple[bool, Optional[str]]:
        if not crm_installed():
            return False, _("Frappe CRM is not installed")
        return super().validate_dependencies()
