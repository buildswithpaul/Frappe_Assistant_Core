# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Set Opening Stock Tool: an import session's file becomes opening stock (#33996)."""

from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool, exception_message, permission_error_result
from frappe_assistant_core.utils import import_opening_stock as opening_stock
from frappe_assistant_core.utils.import_mapping import SESSION_DOCTYPE, load_session


class SetOpeningStock(BaseTool):
    """Make an import session's file the user's opening stock."""

    def __init__(self):
        super().__init__()
        self.name = "set_opening_stock"
        self.description = (
            "Make an import session's file the user's opening stock: closing quantities and values "
            "from the old system, brought in as a Stock Reconciliation with purpose Opening Stock "
            "(never a Stock Entry). Use it instead of set_column_mapping for a stock sheet. Ask the "
            "user for the company and the cut-off date (the last day in the old system; in a migration "
            "plan, plan_migration's opening_setup gives both); the posting "
            "time defaults to the end of that day. The difference account defaults to the company's "
            "Temporary Opening account. Map each column to one of: item_code, warehouse, qty, "
            "valuation_rate, amount (the stock value; the rate is worked out from it), uom (the "
            "file's unit, converted to the item's stock unit), batch_no, serial_no, expiry_date. "
            "Item, warehouse, qty, and a rate or a value, are required. Then check it with "
            "dry_run_import. Writes no business data."
        )
        self.requires_permission = None  # checked on the session and Stock Reconciliation
        # what the user's file says reaches the model fenced (#34003)
        self.untrusted_fields = ("error",)
        self.inputSchema = {
            "type": "object",
            "properties": {
                "session": {"type": "string", "description": "The import session id"},
                "company": {"type": "string", "description": "The company the stock belongs to"},
                "posting_date": {"type": "string", "description": "Cut-off date, YYYY-MM-DD"},
                "posting_time": {"type": "string", "description": "Default 23:59:59"},
                "difference_account": {
                    "type": "string",
                    "description": "Balance Sheet account; default: the company's Temporary Opening",
                },
                "columns": {
                    "type": "object",
                    "description": "File column header → field, e.g. {'Item Name': 'item_code'}",
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["session", "company", "posting_date", "columns"],
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
            result = opening_stock.setup(
                session,
                arguments.get("company"),
                arguments.get("posting_date"),
                arguments.get("columns") or {},
                posting_time=arguments.get("posting_time") or None,
                difference_account=arguments.get("difference_account") or None,
            )
        except opening_stock.OpeningStockProblem as e:
            return {"success": False, "error": str(e), "session": name}
        return {"success": True, "session": session.name, "status": session.status, **result}


# Make sure class name matches file name for discovery
set_opening_stock = SetOpeningStock
