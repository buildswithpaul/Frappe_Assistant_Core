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
from frappe_assistant_core.plugins.migration.tools.import_chart_of_accounts import (
    company_refusal,
    prepared,
    source_system,
)
from frappe_assistant_core.utils import import_chart
from frappe_assistant_core.utils.import_mapping import SESSION_DOCTYPE, load_session
from frappe_assistant_core.utils.one_at_a_time import StillRunning, one_at_a_time


class ReplaceChartOfAccounts(BaseTool):
    """Replace the standard chart of a company that has no transactions with the client's own."""

    def __init__(self):
        super().__init__()
        self.name = "replace_chart_of_accounts"
        self.description = (
            "Replace a company's chart of accounts with the client's (an import session read with "
            "dry_run_import with chart). Only for a company with no general ledger entries and no submitted "
            "documents, and only while no record outside the chart (a draft document, a mode of payment, a "
            "warehouse, a customer's account...) points at its accounts: otherwise it is refused with the "
            "list, and map or add are the way. The company's own tax setup, made for the chart that goes "
            "(its sales, purchase and item tax templates, and its rows in the tax withholding categories "
            "and GST Settings), is removed with it, in the same approval: pass tax_setup_removed as the "
            "check shows it, and after the replace help the user set them up on the new chart's tax "
            "accounts. A template something uses (an item, a customer, a tax rule) stops the replace. It "
            "DELETES the company's accounts and creates the client's through ERPNext's own chart code, as "
            "the user (who needs to be allowed to create and delete accounts), all or nothing, then sets the "
            "company's default accounts again and lists the ones the new chart has no account for. Pass "
            "accounts_removed, accounts_created and tax_setup_removed as the check shows them "
            "(modes.replace_figures of dry_run_import with chart), so the one approval card shows the user "
            "how many accounts and tax setup records go and come; a call without them is refused with the "
            "figures. Never clear the tax setup, or anything else in the way, yourself first with "
            "delete_document or update_document. A company that already has this "
            "chart is left as it is (already_in_place), so a repeated call deletes nothing. The "
            "client's account names and numbers are kept as old IDs."
        )
        self.requires_permission = None  # the session, and Account create and delete, are checked
        self.untrusted_fields = (
            "defaults_left_empty",
            "message",
            "error",
            "source_system",
            "cash_mode_of_payment_account",  # an account named by the client's chart
            "defaults_proposed",
            "card",  # account names from the client's chart
        )
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
                "tax_setup_removed": {
                    "type": "integer",
                    "description": "How many records of the company's tax setup are removed with the chart "
                    "(modes.replace_figures.tax_setup_removed of the check; 0 when it has none).",
                },
                "root_type_column": {
                    "type": "string",
                    "description": "The heading of the column that holds each account's root type (Asset, Liability, Equity, Income, Expense), when the file has one: it can't be mapped, Root Type being read-only on Account.",
                },
                "classifications": {
                    "type": "object",
                    "description": "{account name: {root_type, account_type, account_category}}.",
                },
                "clean_names": {
                    "type": "boolean",
                    "description": "The user's answer when the check reports names_from_another_company: "
                    "true removes the other company's account numbers and abbreviation from the names.",
                },
                "source_system": {"type": "string", "description": "The system the chart comes from."},
            },
            "required": ["session", "company"],  # a call without the figures is answered with them
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        name, company = arguments.get("session"), (arguments.get("company") or "").strip()
        refused = company_refusal(company)
        if refused:
            return refused
        try:
            session = load_session(name)
            nodes, classes = prepared(session, arguments)  # a replaced chart has no outside parents
            if import_chart.already_in_place(company, nodes):
                return {
                    "success": True,
                    "company": company,
                    "already_in_place": True,
                    "removed": 0,
                    "created": 0,
                    "defaults_left_empty": import_chart.defaults_left_empty(company),
                    "message": _(
                        "{0} already has this chart ({1} accounts): nothing was changed. Set the default "
                        "accounts listed in defaults_left_empty."
                    ).format(company, len(nodes)),
                }
            problem = import_chart.replace_problem(company)
            if problem:
                return {"success": False, "error": problem, "company": company}
            figures = import_chart.replace_figures(company, nodes)
            asked = {k: arguments.get(k) for k in ("accounts_removed", "accounts_created")}
            asked["tax_setup_removed"] = arguments.get("tax_setup_removed") or 0
            if asked != {k: figures[k] for k in asked}:
                return {
                    "success": False,
                    "error": _(
                        "This deletes {accounts_removed} accounts of {company} and creates {accounts_created}, "
                        "and removes {tax_setup_removed} records of its tax setup. Pass those figures, so the "
                        "approval card shows the user what goes."
                    ).format(**figures),
                    "approval": figures,
                }
            system = source_system(session, arguments)
            with one_at_a_time("chart", company):
                done = import_chart.replace(company, nodes, classes)
                accounts = {n["index"]: self._account(company, n) for n in nodes}
                kept = import_chart.keep_old_ids(
                    name, system, nodes, {i: a for i, a in accounts.items() if a}
                )
        except StillRunning as e:
            return e.result()
        except frappe.DoesNotExistError:
            return {"success": False, "error": _("Import session '{0}' not found.").format(name)}
        except frappe.PermissionError as e:
            return permission_error_result(SESSION_DOCTYPE, exception_message(e), name=name)
        except import_chart.ChartProblem as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            frappe.log_error(title=_("Replace Chart Of Accounts Error"), message=frappe.get_traceback())
            return {"success": False, "error": exception_message(e)}
        from frappe_assistant_core.plugins.migration.tools.import_chart_of_accounts import mark_done

        mark_done(name)
        proposals = import_chart.default_proposals(company)
        return {
            "success": True,
            "message": _(
                "{0} accounts removed, {1} created. The chart is in place. The company's default accounts are empty: show card now as ONE ask_user card (every question a single_select, its recommended option selected; card's left_empty as its description). Don't ask them one by one and don't ask again. With the answers: first, for every chosen option with change_type, update_document on that Account's account_type; then, only after their replies (never in the same response: ERPNext refuses a default whose type isn't changed yet), ONE update_document on the Company with every chosen option's set. Then ask what they want next; don't start another step."  # noqa: E501
            ).format(done["removed"], done["created"])
            + (
                " "
                + _(
                    "The company's tax setup was removed with the old chart (tax_setup_removed): set its tax templates, tax withholding accounts and GST Settings accounts up again on the new chart's tax accounts, asking the user which ones."  # noqa: E501
                )
                if done.get("tax_setup_removed")
                else ""
            ),
            "card": import_chart.defaults_card(company, proposals),
            **done,
            "source_system": system,
            "old_ids_kept": len(kept["written"]),
            "defaults_proposed": proposals,
        }

    @staticmethod
    def _account(company: str, node: Dict[str, Any]):
        return import_chart._existing(company, node)


# Make sure class name matches file name for discovery
replace_chart_of_accounts = ReplaceChartOfAccounts
