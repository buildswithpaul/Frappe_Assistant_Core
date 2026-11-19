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
from frappe_assistant_core.utils.one_at_a_time import StillRunning, one_at_a_time

#: The client's accounts a check lists that match none of the company's, at most
SHOWN = 100


def company_refusal(company: str) -> Optional[Dict[str, Any]]:
    """The reply when ``company`` can't have a chart put on it by this user, else None. A User Permission
    that limits someone to another company keeps them off this one's accounts, as Desk does: the check
    would list its accounts and the modes it allows, and an import would map onto them."""
    if not frappe.db.exists("Company", company):
        return {"success": False, "error": _("Company {0} doesn't exist.").format(company)}
    if not frappe.has_permission("Company", "read", doc=company):
        return {"success": False, "error": _("You can't work on the accounts of {0}.").format(company)}
    return None


def prepared(session, arguments: Dict[str, Any], company: Optional[str] = None):
    """The nodes and classes of the chart with the user's answers, or raises ChartProblem saying what to
    fix first: the tree's problems, and any account no rule could classify (all of them, in one list)."""
    nodes = import_chart.read_chart(session, arguments.get("root_type_column"), arguments.get("clean_names"))
    pattern = import_chart.name_pattern(nodes)
    if pattern and arguments.get("clean_names") is None:
        raise import_chart.ChartProblem(names_question(pattern))
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


def names_question(pattern: Dict[str, Any]) -> str:
    """What FACO asks when the file's names carry another ERPNext company's account numbers or abbreviation."""
    said = []
    if pattern["names_with_number"]:
        said.append(_("{0} names start with their account number").format(pattern["names_with_number"]))
    if pattern["abbreviation"]:
        said.append(
            _("{0} names end in another company's abbreviation ({1})").format(
                pattern["names_with_abbreviation"], pattern["abbreviation"]
            )
        )
    example = pattern["examples"][0] if pattern["examples"] else None
    return _(
        "The file's account names look like another ERPNext company's ({0}{1}). ERPNext adds this company's "
        "number and abbreviation to every account itself, so kept as they are they would be doubled. Ask the "
        "user once: remove them (clean_names true; a number taken off becomes the account number) or keep "
        "the names as they are (clean_names false)."
    ).format(
        "; ".join(said),
        _(', e.g. "{0}" becomes "{1}"').format(example["in_the_file"], example["cleaned"]) if example else "",
    )


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
            "Group, and on ERPNext v16 Account Category) on a company. Check it first with dry_run_import(session, chart: {company}), which writes nothing and asks no approval: the tree's top levels with "
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
            "account needs a root type: answer the unclassified list of the check first.  "
            "On ERPNext v16 each account also gets an Account Category (the line of the Schedule III / IFRS "
            "statements it goes on): the check shows how many go on each and lists the ledgers that only got "
            "their root type's usual one (categories_to_check) for the user to confirm or correct with "
            "classifications. mode 'categories' sets the category of a company's accounts that have none "
            "(a chart imported before), without a session. When the check reports names_from_another_company "
            "(names like '141600 - State Bank of India - CCBF'), ask the user and pass clean_names. "
            "A top group of the file whose root type the company has no top-level account of (ERPNext's India chart has "
            "no Equity) becomes the company's top-level account of that type. If this tool refuses or "
            "fails, tell the user why and stop: never create or move accounts by hand with "
            "create_document or update_document to get round it."
        )
        self.requires_permission = None  # the session, and Account create, are checked
        self.untrusted_fields = (
            "unmatched",
            "created",
            "message",
            "error",
            "outline",
            "unclassified",
            "doubtful",
            "problems",
            "parents_not_in_the_file",
            "map",
            "categories_to_check",
            "categories_not_found",
            "ledgers_without_category",
            "names_from_another_company",
            # named by the user or the file, not by FAC
            "source_system",
            "old_id_conflicts",
            "old_id_systems",
            "modes.replace_refused",  # names the records that point at the accounts
        )
        self.inputSchema = {
            "type": "object",
            "properties": {
                "session": {"type": "string", "description": "The import session of the chart file."},
                "company": {"type": "string", "description": "The company to put the chart on."},
                "mode": {
                    "type": "string",
                    "enum": ["map", "add", "categories"],
                    "description": "map or add; categories: set the Account Category (ERPNext v16) of the "
                    "company's accounts that have none, by the same rules, no session needed.",
                },
                "root_type_column": {
                    "type": "string",
                    "description": "The heading of the column that holds each account's root type (Asset, Liability, Equity, Income, Expense), when the file has one: it can't be mapped, Root Type being read-only on Account.",
                },
                "classifications": {
                    "type": "object",
                    "description": "{account name: {root_type, account_type, account_category}}; "
                    "account_category alone changes only the category.",
                },
                "clean_names": {
                    "type": "boolean",
                    "description": "When the check says the names carry another ERPNext company's account "
                    "numbers or abbreviation (names_from_another_company): the user's answer, true to "
                    "remove them, false to keep the names as they are.",
                },
                "add_unmatched": {"type": "boolean", "description": "Map mode: add what matched nothing."},
                "source_system": {
                    "type": "string",
                    "description": "The system the chart comes from (odoo, tally, ...): the old IDs are kept under it.",
                },
            },
            "required": ["mode"],  # map and add need the session; categories doesn't
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        name, company, mode = (
            arguments.get("session"),
            (arguments.get("company") or "").strip(),
            arguments.get("mode"),
        )
        if mode not in ("map", "add", "categories"):
            return {"success": False, "error": _("mode is map, add or categories.")}
        refused = company_refusal(company)
        if refused:
            return refused
        if mode == "categories":
            return self._categories(company)
        try:
            session = load_session(name)
            if not frappe.has_permission("Account", "create"):
                raise frappe.PermissionError(_("You can't create accounts."))
            nodes, classes = prepared(session, arguments, company)
            system = source_system(session, arguments)
            with one_at_a_time("chart", company):
                result, kept = self._apply(name, company, mode, arguments, nodes, classes, system)
        except StillRunning as e:
            return e.result()
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
            "message": _repeat_note(company, result) + _old_ids_message(len(result["created"]), system, kept),
        }

    @staticmethod
    def _categories(company: str) -> Dict[str, Any]:
        """Set the Account Category of the company's accounts that have none (ERPNext v16)."""
        if not import_chart.categories_supported():
            return {
                "success": False,
                "error": _(
                    "This site's ERPNext has no Account Category (it came with v16): there is nothing to set."
                ),
            }
        if not frappe.has_permission("Account", "write"):
            return {"success": False, "error": _("You can't change accounts.")}
        try:
            with one_at_a_time("chart", company):
                result = import_chart.fill_categories(company)
        except StillRunning as e:
            return e.result()
        except Exception as e:
            frappe.log_error(title=_("Account Categories Error"), message=frappe.get_traceback())
            return {"success": False, "error": exception_message(e)}
        message = _("{0} accounts got an Account Category; {1} kept the one they had.").format(
            result["categories_set"], result["categories_kept"]
        )
        if result["categories_to_check_count"]:
            message += " " + _(
                "{0} ledgers only got their root type's usual category (categories_to_check): show them to "
                "the user to confirm or correct."
            ).format(result["categories_to_check_count"])
        return {"success": True, "company": company, "mode": "categories", **result, "message": message}

    @staticmethod
    def _apply(name, company, mode, arguments, nodes, classes, system):
        frappe.db.savepoint("fac_chart_import")
        try:
            if mode == "add":
                done = import_chart.add(company, nodes, classes)
                result = {"created": done["created"], "accounts": done["accounts"]}
            else:
                done = import_chart.apply_map(company, nodes, classes, bool(arguments.get("add_unmatched")))
                result = {
                    "created": done["created"],
                    "accounts": done["accounts"],
                    "matched": len(done["matched"]),
                    "unmatched": done["unmatched"],
                }
            if mode == "add":
                result["already_on_company"] = len(result["accounts"]) - len(result["created"])
            kept = import_chart.keep_old_ids(name, system, nodes, result.pop("accounts"))
        except Exception:
            frappe.db.rollback(save_point="fac_chart_import")
            raise
        return result, kept


def _repeat_note(company: str, result: Dict[str, Any]) -> str:
    """Said when nothing was created because the file's accounts are on the company already: the chat
    called the tool again after an earlier call had added them (live, 2026-11-19: "0 created")."""
    if result["created"] or not result.get("already_on_company"):
        return ""
    return (
        _(
            "All {0} accounts of the file are already on {1}, so none was created now: an earlier call "
            "added them. Tell the user the chart is in place, not that nothing was added."
        ).format(result["already_on_company"], company)
        + " "
    )


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
    refused = company_refusal(company) if company else None
    if refused:
        return refused
    try:
        session = load_session(name)
        nodes = import_chart.read_chart(
            session, arguments.get("root_type_column"), arguments.get("clean_names")
        )
        if company:
            import_chart.apply_outside_parents(nodes, company)
        import_chart.apply_answers(nodes, arguments.get("classifications"))
        classes = import_chart.classify(nodes)
        out: Dict[str, Any] = {"success": True, "session": name, **import_chart.summary(nodes, classes)}
        pattern = import_chart.name_pattern(nodes)
        if pattern:
            # "141600 - State Bank of India - CCBF": the user decides before anything is put on the company
            out["names_from_another_company"] = {**pattern, "cleaned": bool(arguments.get("clean_names"))}
            if arguments.get("clean_names") is None:
                out["names_question"] = names_question(pattern)
        if company and import_chart.already_in_place(company, nodes):
            # Live, 2026-11-18: a chart the company already had was offered replace and add again
            out.update(
                company=company,
                already_in_place=True,
                modes={"offered": []},
                message=_(
                    "{0} already has this chart ({1} accounts): there is nothing to put on it. Don't "
                    "offer replace or add."
                ).format(company, len(nodes)),
            )
            return out
        if company:
            out["company"] = company
            out["modes"] = import_chart.modes(company)
            if "replace" in out["modes"]["offered"]:
                problem = import_chart.replace_problem(company)
                if problem:
                    # said before the user picks replace (live, 2026-11-18: picked, then refused)
                    out["modes"]["offered"].remove("replace")
                    out["modes"]["replace_refused"] = problem
                else:
                    # What replace_chart_of_accounts' approval card shows: sent with the first call, the
                    # user approves once, with the figures (live, a call without them was a second card)
                    out["modes"]["replace_figures"] = import_chart.replace_figures(company, nodes)
            roots = import_chart.missing_roots(company, nodes, classes)
            if roots:
                # add and map make the file's top account of that type the company's root: shown first
                out["add_creates_top_level"] = roots
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
