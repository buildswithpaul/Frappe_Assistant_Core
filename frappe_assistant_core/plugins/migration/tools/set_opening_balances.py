# frappe_assistant_core/plugins/migration/tools/set_opening_balances.py
# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Set Opening Balances Tool: an import session's file becomes the opening trial balance (#33998)."""

from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool, exception_message, permission_error_result
from frappe_assistant_core.utils import import_opening_balances as opening_balances
from frappe_assistant_core.utils.import_mapping import SESSION_DOCTYPE, load_session


class SetOpeningBalances(BaseTool):
    """Make an import session's file the user's opening trial balance."""

    def __init__(self):
        super().__init__()
        self.name = "set_opening_balances"
        self.description = (
            "Make an import session's file the old system's closing trial balance, brought in as one "
            "opening Journal Entry (voucher type Opening Entry) at the cut-off date. Use it instead of "
            "set_column_mapping for such a file. Ask the user for the company, the cut-off date (the "
            "last day in the old system; in a migration plan, plan_migration's opening_setup gives "
            "both) and what to do with Profit and Loss rows: stop and say why "
            "(profit_and_loss stop, the default, because ERPNext refuses them in an opening entry), or "
            "roll their net into a retained-earnings account the user names (profit_and_loss "
            "retained_earnings with retained_earnings_account, an Equity account of the company). Map "
            "each column to one of: account, debit, credit, or balance (signed: positive is debit, "
            "negative or in brackets is credit). account is required, with balance or debit and credit. "
            "Receivable and Payable accounts are left for the opening invoices import, and Stock accounts "
            "for the opening stock import when the company has perpetual inventory on (without it, "
            "Stock rows go in the entry); they count in the file's balance check. The chart of "
            "accounts can only be replaced before any transaction, with ERPNext's Chart of Accounts "
            "Importer, which this tool doesn't do. Then check it with dry_run_import. Writes no "
            "business data."
        )
        self.requires_permission = None  # checked on the session and Journal Entry
        # what the user's file says reaches the model fenced (#34003)
        self.untrusted_fields = ("error",)
        self.inputSchema = {
            "type": "object",
            "properties": {
                "session": {"type": "string", "description": "The import session id"},
                "company": {"type": "string", "description": "The company the balances belong to"},
                "cut_off": {"type": "string", "description": "Cut-off date, YYYY-MM-DD"},
                "columns": {
                    "type": "object",
                    "description": "File column header → field, e.g. {'Account Name': 'account'}",
                    "additionalProperties": {"type": "string"},
                },
                "profit_and_loss": {
                    "type": "string",
                    "enum": list(opening_balances.PL_MODES),
                    "default": "stop",
                    "description": "What to do with Profit and Loss rows",
                },
                "retained_earnings_account": {
                    "type": "string",
                    "description": "With retained_earnings: the Equity account their net goes to",
                },
            },
            "required": ["session", "company", "cut_off", "columns"],
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
            result = opening_balances.setup(
                session,
                arguments.get("company"),
                arguments.get("cut_off"),
                arguments.get("columns") or {},
                arguments.get("profit_and_loss") or "stop",
                arguments.get("retained_earnings_account"),
            )
        except opening_balances.OpeningBalancesProblem as e:
            return {"success": False, "error": str(e), "session": name}
        return {"success": True, "session": session.name, "status": session.status, **result}


# Make sure class name matches file name for discovery
set_opening_balances = SetOpeningBalances
