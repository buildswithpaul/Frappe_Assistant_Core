# frappe_assistant_core/plugins/migration/tools/import_opening_invoices.py
# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Import Opening Invoices Tool: create and submit checked opening receivables or payables (#33997)."""

from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool, exception_message, permission_error_result
from frappe_assistant_core.utils import import_opening_invoices as opening_invoices
from frappe_assistant_core.utils import import_plan
from frappe_assistant_core.utils.import_mapping import SESSION_DOCTYPE, load_session
from frappe_assistant_core.utils.import_session import FileProblem


class ImportOpeningInvoices(BaseTool):
    """Create and submit checked opening invoices, or report on them."""

    def __init__(self):
        super().__init__()
        self.name = "import_opening_invoices"
        self.description = (
            "Bring checked opening receivables or payables into ERPNext, once the user approves: one "
            "submitted opening Sales or Purchase Invoice per row, as ERPNext's Opening Invoice Creation "
            "Tool makes them. Only after dry_run_import said the sheet is ready, and only when the user "
            "asks to import. Pass company, invoice_type, rows (the check's 'ready') and total_amount "
            "exactly as the last check reported them: the approval card shows them, and they must "
            "match. Each invoice is all or nothing; one ERPNext refuses doesn't stop the rest. More "
            "than 100 run in the background: call again with the same values to follow the progress "
            "and, at the end, to get the totals against the file's and any row that differs. Calling "
            "again never creates anything twice."
        )
        self.requires_permission = None  # checked on the session and the invoice DocType
        # what the user's file says reaches the model fenced (#34003)
        self.untrusted_fields = ("failed", "left_out", "message", "error")
        self.inputSchema = {
            "type": "object",
            "properties": {
                "session": {"type": "string", "description": "The import session id"},
                "company": {"type": "string"},
                "invoice_type": {"type": "string", "enum": ["Sales", "Purchase"]},
                "rows": {"type": "integer", "description": "The last check's 'ready'"},
                "total_amount": {"type": "number", "description": "The last check's total_amount"},
            },
            "required": ["session", "company", "invoice_type", "rows", "total_amount"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        name = arguments.get("session")
        try:
            session = load_session(name)
        except frappe.DoesNotExistError:
            return {"success": False, "error": _("Import session '{0}' not found.").format(name)}
        except frappe.PermissionError as e:
            return permission_error_result(SESSION_DOCTYPE, exception_message(e), name=name)
        refused = import_plan.imported_by_its_plan(session)
        if refused:
            return {"success": False, "error": refused, "session": session.name}
        if not opening_invoices.is_opening_invoices(session):
            return {
                "success": False,
                "error": _("This session isn't opening invoices. Use start_import."),
                "session": name,
            }
        try:
            opening_invoices.check_card(
                session,
                arguments.get("company"),
                arguments.get("invoice_type"),
                arguments.get("rows"),
                arguments.get("total_amount"),
            )
            if session.status not in opening_invoices.DONE:
                invoices = opening_invoices.settings(session)
                problem = opening_invoices.setup_problem(
                    invoices["company"], invoices["invoice_type"], invoices["cut_off"]
                )
                if problem:
                    raise opening_invoices.OpeningInvoicesProblem(problem)
            opening_invoices.create(session)
        except (opening_invoices.OpeningInvoicesProblem, FileProblem) as e:
            return {"success": False, "error": str(e), "session": name}
        except Exception as e:
            frappe.log_error(title=_("Opening Invoices Import Error"), message=frappe.get_traceback())
            return {"success": False, "error": exception_message(e), "session": name}
        session.reload()
        return {"success": True, "session": session.name, **opening_invoices.report(session)}


# Make sure class name matches file name for discovery
import_opening_invoices = ImportOpeningInvoices
