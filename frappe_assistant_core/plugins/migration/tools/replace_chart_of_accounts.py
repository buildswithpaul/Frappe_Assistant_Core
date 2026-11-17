# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Replace Chart Of Accounts Tool for Core Plugin (#34422)."""

from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool, exception_message, permission_error_result
from frappe_assistant_core.plugins.migration.tools.import_chart_of_accounts import prepared, source_system
from frappe_assistant_core.utils import import_chart
from frappe_assistant_core.utils.import_mapping import SESSION_DOCTYPE, load_session


class ReplaceChartOfAccounts(BaseTool):
    """Replace the standard chart of a company that has no transactions with the client's own."""

    def __init__(self):
        super().__init__()
        self.name = "replace_chart_of_accounts"
        self.description = (
            "Replace a company's chart of accounts with the client's (an import session read with "
            "dry_run_import with chart). Only for a company with no general ledger entries and no submitted "
            "documents, and only while no tax template, item tax template, mode of payment or GST Settings "
            "points at its accounts: otherwise it is refused with the list, and map or add are the way. It "
            "DELETES the company's accounts and creates the client's through ERPNext's own chart code, as "
            "the user (who needs to be allowed to create and delete accounts), all or nothing, then sets the "
            "company's default accounts again and lists the ones the new chart has no account for. Pass "
            "accounts_removed and accounts_created as the check shows them, so the approval card shows the "
            "user how many accounts go and come; a call without them is refused with the figures. The "
            "client's account names and numbers are kept as old IDs."
        )
        self.requires_permission = None  # the session, and Account create and delete, are checked
        self.untrusted_fields = ("defaults_left_empty", "message", "error")
        self.inputSchema = {
            "type": "object",
            "properties": {
                "session": {"type": "string", "description": "The import session of the chart file."},
                "company": {"type": "string", "description": "The company whose chart is replaced."},
                "accounts_removed": {
                    "type": "integer",
                    "description": "How many accounts of the company are deleted.",
                },
                "accounts_created": {
                    "type": "integer",
                    "description": "How many accounts the client's chart creates.",
                },
                "root_type_column": {
                    "type": "string",
                    "description": "The heading of the column that holds each account's root type (Asset, Liability, Equity, Income, Expense), when the file has one: it can't be mapped, Root Type being read-only on Account.",
                },
                "classifications": {
                    "type": "object",
                    "description": "{account name: {root_type, account_type}}.",
                },
                "source_system": {"type": "string", "description": "The system the chart comes from."},
            },
            "required": ["session", "company", "accounts_removed", "accounts_created"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        name, company = arguments.get("session"), (arguments.get("company") or "").strip()
        if not frappe.db.exists("Company", company):
            return {"success": False, "error": _("Company {0} doesn't exist.").format(company)}
        try:
            session = load_session(name)
            nodes, classes = prepared(session, arguments)  # a replaced chart has no outside parents
            problem = import_chart.replace_problem(company)
            if problem:
                return {"success": False, "error": problem, "company": company}
            figures = import_chart.replace_figures(company, nodes)
            asked = {k: arguments.get(k) for k in ("accounts_removed", "accounts_created")}
            if asked != {k: figures[k] for k in asked}:
                return {
                    "success": False,
                    "error": _(
                        "This deletes {accounts_removed} accounts of {company} and creates {accounts_created}. Pass "
                        "those figures, so the approval card shows the user what goes."
                    ).format(**figures),
                    "approval": figures,
                }
            system = source_system(session, arguments)
            done = import_chart.replace(company, nodes, classes)
            accounts = {n["index"]: self._account(company, n) for n in nodes}
            kept = import_chart.keep_old_ids(name, system, nodes, {i: a for i, a in accounts.items() if a})
        except frappe.DoesNotExistError:
            return {"success": False, "error": _("Import session '{0}' not found.").format(name)}
        except frappe.PermissionError as e:
            return permission_error_result(SESSION_DOCTYPE, exception_message(e), name=name)
        except import_chart.ChartProblem as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            frappe.log_error(title=_("Replace Chart Of Accounts Error"), message=frappe.get_traceback())
            return {"success": False, "error": exception_message(e)}
        return {
            "success": True,
            **done,
            "source_system": system,
            "old_ids_kept": len(kept["written"]),
            "message": _(
                "{0} accounts removed, {1} created. Set the default accounts listed in defaults_left_empty."
            ).format(done["removed"], done["created"]),
        }

    @staticmethod
    def _account(company: str, node: Dict[str, Any]):
        return import_chart._existing(company, node)


# Make sure class name matches file name for discovery
replace_chart_of_accounts = ReplaceChartOfAccounts
