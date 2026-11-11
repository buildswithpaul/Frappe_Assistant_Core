# frappe_assistant_core/plugins/migration/tools/set_opening_invoices.py
# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Set Opening Invoices Tool: an import session's file becomes opening receivables or payables (#33997)."""

from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool, exception_message, permission_error_result
from frappe_assistant_core.utils import import_opening_invoices as opening_invoices
from frappe_assistant_core.utils.import_mapping import SESSION_DOCTYPE, load_session


class SetOpeningInvoices(BaseTool):
    """Make an import session's file the user's opening receivables or payables."""

    def __init__(self):
        super().__init__()
        self.name = "set_opening_invoices"
        self.description = (
            "Make an import session's file the user's opening receivables (invoice_type Sales: what "
            "customers still owe) or payables (Purchase: what is still owed to suppliers), brought in "
            "as opening Sales or Purchase Invoices the way ERPNext's Opening Invoice Creation Tool makes "
            "them. Use it instead of set_column_mapping for such a list. Ask the user for the company, "
            "which of the two the file is (one kind per session) and the cut-off date (the last day in "
            "the old system; in a migration plan, plan_migration's opening_setup gives the company and "
            "the date). Map each column to one of: party (the customer or supplier), "
            "outstanding_amount (what is still unpaid, in the company's currency), invoice_number, "
            "posting_date (the invoice date; default the cut-off), due_date (default the invoice "
            "date), item_name (a description). party and outstanding_amount are required. Then check "
            "it with dry_run_import. Writes no business data."
        )
        self.requires_permission = None  # checked on the session and the invoice DocType
        # what the user's file says reaches the model fenced (#34003)
        self.untrusted_fields = ("error",)
        self.inputSchema = {
            "type": "object",
            "properties": {
                "session": {"type": "string", "description": "The import session id"},
                "company": {"type": "string", "description": "The company the invoices belong to"},
                "invoice_type": {"type": "string", "enum": ["Sales", "Purchase"]},
                "cut_off": {"type": "string", "description": "Cut-off date, YYYY-MM-DD"},
                "columns": {
                    "type": "object",
                    "description": "File column header → field, e.g. {'Customer Name': 'party'}",
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["session", "company", "invoice_type", "cut_off", "columns"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        name = arguments.get("session")
        try:
            session = load_session(name)
        except frappe.DoesNotExistError:
            return {"success": False, "error": _("Import session '{0}' not found.").format(name)}
        except frappe.PermissionError as e:
            return permission_error_result(SESSION_DOCTYPE, exception_message(e), name=name)
        try:
            result = opening_invoices.setup(
                session,
                arguments.get("company"),
                arguments.get("invoice_type"),
                arguments.get("cut_off"),
                arguments.get("columns") or {},
            )
        except opening_invoices.OpeningInvoicesProblem as e:
            return {"success": False, "error": str(e), "session": name}
        return {"success": True, "session": session.name, "status": session.status, **result}


# Make sure class name matches file name for discovery
set_opening_invoices = SetOpeningInvoices
