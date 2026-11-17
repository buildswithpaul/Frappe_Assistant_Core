# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Import Chart Of Accounts Tool for Core Plugin (#34422): map or add."""

from typing import Any, Dict, Optional

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool, exception_message, permission_error_result
from frappe_assistant_core.utils import import_chart, import_keys
from frappe_assistant_core.utils.import_mapping import SESSION_DOCTYPE, load_session

#: The client's accounts a check lists that match none of the company's, at most
SHOWN = 100


def prepared(session, arguments: Dict[str, Any], company: Optional[str] = None):
    """The nodes and classes of the chart with the user's answers, or raises ChartProblem saying what to
    fix first: the tree's problems, and any account no rule could classify (all of them, in one list)."""
    nodes = import_chart.read_chart(session, arguments.get("root_type_column"))
    if company:
        import_chart.apply_outside_parents(nodes, company)
    import_chart.apply_answers(nodes, arguments.get("classifications"))
    found = import_chart.problems(nodes)
    if found:
        raise import_chart.ChartProblem(
            _("Fix the file first: {0}").format(" ".join(p["message"] for p in found[:10]))
        )
    classes = import_chart.classify(nodes)
    unclassified = [n["name"] for n, c in zip(nodes, classes) if not c["root_type"]]
    if unclassified:
        raise import_chart.ChartProblem(
            _(
                "These accounts need a root type (Asset, Liability, Equity, Income or Expense), and an account "
                "type if one fits: {0}. Ask the user for all of them at once and pass classifications."
            ).format(", ".join(unclassified[:50]))
        )
    return nodes, classes


def source_system(session, arguments: Dict[str, Any]) -> str:
    """The system the client's account names and numbers are kept under as old IDs."""
    given = (arguments.get("source_system") or "").strip()
    marked = import_keys.source_key(session)
    return import_keys.system_name(given or (marked or {}).get("system") or "chart")


class ImportChartOfAccounts(BaseTool):
    """Put the client's chart on a company by mapping onto its accounts or adding to them."""

    def __init__(self):
        super().__init__()
        self.name = "import_chart_of_accounts"
        self.description = (
            "Put the client's own chart of accounts (an import session of a sheet from Tally, Zoho, "
            "QuickBooks or any export, columns mapped to Account fields with set_column_mapping: Account "
            "Name, Parent Account, and where the file has them Account Number, Root Type, Account Type, Is "
            "Group) on a company. Check it first with dry_run_import(session, chart: {company}), which writes nothing and asks no approval: the tree's top levels with "
            "counts, each account's proposed root type and account type, ALL the accounts it couldn't "
            "classify in one list (ask the user about them together; pass the answers as "
            "classifications), the tree's problems (a cycle, an account under a ledger, an account twice) "
            "and, with company, the modes the company allows and which accounts match the company's. "
            "mode 'map': the client's accounts that match the company's (same name, then number, "
            "then the one ledger of that account type) become those accounts and nothing is created; the "
            "ones that match nothing are listed, and passing add_unmatched adds them under their parents' "
            "accounts. mode 'add': the client's accounts are created under the right parents, parents first, "
            "an account the company has already is kept as it is. Either way the client's account names and "
            "numbers are kept as old IDs so the opening trial balance finds its accounts by them. To replace "
            "the standard chart of a company with no transactions use replace_chart_of_accounts. Every "
            "account needs a root type: answer the unclassified list of the check first."
        )
        self.requires_permission = None  # the session, and Account create, are checked
        self.untrusted_fields = (
            "unmatched",
            "created",
            "message",
            "error",
            "outline",
            "unclassified",
            "problems",
            "parents_not_in_the_file",
            "map",
        )
        self.inputSchema = {
            "type": "object",
            "properties": {
                "session": {"type": "string", "description": "The import session of the chart file."},
                "company": {"type": "string", "description": "The company to put the chart on."},
                "mode": {
                    "type": "string",
                    "enum": ["map", "add"],
                    "description": "map or add.",
                },
                "root_type_column": {
                    "type": "string",
                    "description": "The heading of the column that holds each account's root type (Asset, Liability, Equity, Income, Expense), when the file has one: it can't be mapped, Root Type being read-only on Account.",
                },
                "classifications": {
                    "type": "object",
                    "description": "{account name: {root_type, account_type}}.",
                },
                "add_unmatched": {"type": "boolean", "description": "Map mode: add what matched nothing."},
                "source_system": {
                    "type": "string",
                    "description": "The system the chart comes from (odoo, tally, ...): the old IDs are kept under it.",
                },
            },
            "required": ["session", "mode"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        name, company, mode = (
            arguments.get("session"),
            (arguments.get("company") or "").strip(),
            arguments.get("mode"),
        )
        if mode not in ("map", "add"):
            return {"success": False, "error": _("mode is map or add.")}
        if not frappe.db.exists("Company", company):
            return {"success": False, "error": _("Company {0} doesn't exist.").format(company)}
        try:
            session = load_session(name)
            if not frappe.has_permission("Account", "create"):
                raise frappe.PermissionError(_("You can't create accounts."))
            nodes, classes = prepared(session, arguments, company)
            system = source_system(session, arguments)
            frappe.db.savepoint("fac_chart_import")
            try:
                if mode == "add":
                    done = import_chart.add(company, nodes, classes)
                    result = {"created": done["created"], "accounts": done["accounts"]}
                else:
                    done = import_chart.apply_map(
                        company, nodes, classes, bool(arguments.get("add_unmatched"))
                    )
                    result = {
                        "created": done["created"],
                        "accounts": done["accounts"],
                        "matched": len(done["matched"]),
                        "unmatched": done["unmatched"],
                    }
                kept = import_chart.keep_old_ids(name, system, nodes, result.pop("accounts"))
            except Exception:
                frappe.db.rollback(save_point="fac_chart_import")
                raise
        except frappe.DoesNotExistError:
            return {"success": False, "error": _("Import session '{0}' not found.").format(name)}
        except frappe.PermissionError as e:
            return permission_error_result(SESSION_DOCTYPE, exception_message(e), name=name)
        except import_chart.ChartProblem as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            frappe.log_error(title=_("Import Chart Of Accounts Error"), message=frappe.get_traceback())
            return {"success": False, "error": exception_message(e)}
        return {
            "success": True,
            "company": company,
            "mode": mode,
            "source_system": system,
            **result,
            "old_ids_kept": len(kept["written"]),
            "old_id_conflicts": kept["conflicts"],
            "old_id_systems": kept["systems"],
            "message": _old_ids_message(len(result["created"]), system, kept),
        }


def _old_ids_message(created: int, system: str, kept: Dict[str, Any]) -> str:
    """What the reply says of the old IDs: what was kept, under which system, and what wasn't."""
    text = _("{0} accounts created.").format(created)
    if kept["written"]:
        text += " " + _("{0} of the client's account names and numbers are kept as old IDs ({1}).").format(
            len(kept["written"]), ", ".join(kept["systems"])
        )
    if len(kept["systems"]) > 1 or (kept["systems"] and kept["systems"][0] != system):
        text += " " + _(
            "Another company keeps the same names under {0}, so this company's are kept under {1}."
        ).format(system, kept["systems"][-1])
    if kept["conflicts"]:
        text += " " + _(
            "{0} were not kept: each already names another account of this company ({1})."
        ).format(len(kept["conflicts"]), ", ".join(kept["conflicts"][:10]))
    return text


def check_chart(name: str, company: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """What the chart would become: read from the session, nothing written. dry_run_import's chart
    check."""
    if not company:
        # nothing to ask on a site of one company
        only = frappe.get_list("Company", pluck="name", limit=2)
        company = only[0] if len(only) == 1 else ""
    try:
        session = load_session(name)
        nodes = import_chart.read_chart(session, arguments.get("root_type_column"))
        if company and frappe.db.exists("Company", company):
            import_chart.apply_outside_parents(nodes, company)
        import_chart.apply_answers(nodes, arguments.get("classifications"))
        classes = import_chart.classify(nodes)
        out: Dict[str, Any] = {"success": True, "session": name, **import_chart.summary(nodes, classes)}
        if company:
            if not frappe.db.exists("Company", company):
                return {"success": False, "error": _("Company {0} doesn't exist.").format(company)}
            out["company"] = company
            out["modes"] = import_chart.modes(company)
            proposal = import_chart.map_proposal(nodes, classes, company)
            out["map"] = {
                "matched": len(proposal["matched"]),
                "unmatched": len(proposal["unmatched"]),
                "unmatched_accounts": proposal["unmatched"][:SHOWN],
            }
        return out
    except frappe.DoesNotExistError:
        return {"success": False, "error": _("Import session '{0}' not found.").format(name)}
    except frappe.PermissionError as e:
        return permission_error_result(SESSION_DOCTYPE, exception_message(e), name=name)
    except import_chart.ChartProblem as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        frappe.log_error(title=_("Check Chart Of Accounts Error"), message=frappe.get_traceback())
        return {"success": False, "error": exception_message(e)}


# Make sure class name matches file name for discovery
import_chart_of_accounts = ImportChartOfAccounts
