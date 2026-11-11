# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Import Opening Stock Tool: create and submit a checked opening-stock sheet (#33996)."""

from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool, exception_message, permission_error_result
from frappe_assistant_core.utils import import_opening_stock as opening_stock
from frappe_assistant_core.utils import import_plan
from frappe_assistant_core.utils.import_mapping import SESSION_DOCTYPE, load_session
from frappe_assistant_core.utils.import_session import FileProblem


class ImportOpeningStock(BaseTool):
    """Create and submit a checked opening-stock sheet, or report on it."""

    def __init__(self):
        super().__init__()
        self.name = "import_opening_stock"
        self.description = (
            "Bring a checked opening-stock sheet into ERPNext, once the user approves: a submitted "
            "Stock Reconciliation (purpose Opening Stock) at the cut-off date, up to 1,000 rows each. "
            "Only after dry_run_import said the sheet is ready, and only when the user asks to import. "
            "Pass company, posting_date, rows (the check's 'ready'), total_qty and total_value exactly "
            "as the last check reported them: the approval card shows them, and they must match. "
            "Calling again with the same values creates nothing more; it reports the documents and "
            "the totals per warehouse against the file's. ERPNext submits more than 100 rows in the "
            "background, and stock values can change until its reposting finishes: say so."
        )
        self.requires_permission = None  # checked on the session and Stock Reconciliation
        # what the user's file says reaches the model fenced (#34003)
        self.untrusted_fields = ("message", "error")
        self.inputSchema = {
            "type": "object",
            "properties": {
                "session": {"type": "string", "description": "The import session id"},
                "company": {"type": "string"},
                "posting_date": {"type": "string", "description": "The cut-off date, as the check said"},
                "rows": {"type": "integer", "description": "The last check's 'ready'"},
                "total_qty": {"type": "number"},
                "total_value": {"type": "number"},
            },
            "required": ["session", "company", "posting_date", "rows", "total_qty", "total_value"],
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
        if not opening_stock.is_opening_stock(session):
            return {
                "success": False,
                "error": _("This session isn't opening stock. Use start_import."),
                "session": name,
            }
        try:
            opening_stock.check_card(
                session,
                arguments.get("company"),
                arguments.get("posting_date"),
                arguments.get("rows"),
                arguments.get("total_qty"),
                arguments.get("total_value"),
            )
            stock = opening_stock.settings(session)
            problem = opening_stock.setup_problem(
                stock["company"], stock["posting_date"], stock["difference_account"]
            )
            if problem:
                raise opening_stock.OpeningStockProblem(problem)
            opening_stock.create(session)
        except (opening_stock.OpeningStockProblem, FileProblem) as e:
            return {"success": False, "error": str(e), "session": name}
        except Exception as e:
            frappe.log_error(title=_("Opening Stock Import Error"), message=frappe.get_traceback())
            return {"success": False, "error": exception_message(e), "session": name}
        session.reload()
        return {"success": True, "session": session.name, **opening_stock.report(session)}


# Make sure class name matches file name for discovery
import_opening_stock = ImportOpeningStock
