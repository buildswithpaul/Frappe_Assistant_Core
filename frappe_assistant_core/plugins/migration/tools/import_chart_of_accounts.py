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
#: Accounts a reply names of those it created: a chart's 1,000 names made FAC Cloud set the reply aside and
#: the chat read it back three times (live, 2026-11-19: 760 credits)
CREATED_SHOWN = 10


def mark_done(session_name: Optional[str]) -> None:
    """The session of a chart put on a company is done: it said "Mapped" after the chart was in (live)."""
    if session_name and frappe.db.exists(SESSION_DOCTYPE, session_name):
        frappe.db.set_value(SESSION_DOCTYPE, session_name, "status", "Completed", update_modified=False)


def chart_card(out: Dict[str, Any], nodes, classes, company: str, pattern) -> None:
    """Every question of the check, for ONE card the user answers once (live, 2026-11-19: the chat asked
    the company and the mode before checking, then a card, then replace again with its figures). The mode
    is suggested from the company: a company with no transactions gets replace, with what add would leave
    beside the file's accounts; replace's figures are on the card, so the user's answer is the approval."""
    modes = out.get("modes") or {}
    offered = modes.get("offered") or []
    questions = []
    choices = []
    if "replace" in offered:
        figures = modes.get("replace_figures") or {}
        choices.append(
            {
                "mode": "replace",
                "tool": "replace_chart_of_accounts",
                "arguments": {
                    "accounts_removed": figures.get("accounts_removed"),
                    "accounts_created": figures.get("accounts_created"),
                    "tax_setup_removed": figures.get("tax_setup_removed") or 0,
                },
                "label": _("Replace: only the file's accounts"),
                "effect": _(
                    "Deletes the company's {0} accounts and creates the file's {1}; removes {2} tax setup records."
                ).format(
                    figures.get("accounts_removed"),
                    figures.get("accounts_created"),
                    figures.get("tax_setup_removed") or 0,
                ),
            }
        )
    if "add" in offered:
        beside = import_chart.add_leaves_beside(company, nodes, classes)
        out["add_leaves_beside"] = beside
        effect = _("Adds the file's accounts and keeps the company's {0} other accounts beside them.").format(
            beside["accounts_kept"]
        )
        if beside["look_alikes"]:
            pair = beside["look_alikes"][0]
            effect += " " + _("Some look alike, e.g. {0} and {1}.").format(
                pair["company_has"], pair["file_has"]
            )
        choices.append(
            {
                "mode": "add",
                "tool": "import_chart_of_accounts",
                "arguments": {"mode": "add"},
                "label": _("Add: the file's accounts beside the company's"),
                "effect": effect,
            }
        )
    if "map" in offered:
        choices.append(
            {
                "mode": "map",
                "tool": "import_chart_of_accounts",
                "arguments": {"mode": "map"},
                "label": _("Map: use the company's accounts, create nothing"),
                "effect": _("{0} of the file's accounts match the company's; {1} match nothing.").format(
                    (out.get("map") or {}).get("matched"), (out.get("map") or {}).get("unmatched")
                ),
            }
        )
    if choices:
        suggested = "replace" if "replace" in offered else ("map" if modes.get("replace_refused") else "add")
        questions.append(
            {
                "id": "chart:mode",
                "kind": "mode",
                "choices": choices,
                "suggested": suggested,
                "why": _("{0} has no transactions: replace leaves exactly the file's chart.").format(company)
                if suggested == "replace"
                else (modes.get("replace_refused") or ""),
            }
        )
    if out.get("doubtful"):
        questions.append(
            {
                "id": "chart:doubtful",
                "kind": "doubtful",
                "message": _("{0} accounts have an account type that doesn't fit their root type.").format(
                    len(out["doubtful"])
                ),
                "examples": out["doubtful"][:3],
                "choices": [
                    {"answer": "keep", "label": _("Keep them as the file has them")},
                    {"answer": "fix_file", "label": _("Stop: I'll correct the file first")},
                ],
                "suggested": "keep",
            }
        )
    if pattern:
        question = names_question(pattern)
        if question:
            questions.append(question)
    if out.get("categories_to_check_count"):
        questions.append(
            {
                "id": "chart:categories",
                "kind": "categories",
                "message": _(
                    "{0} ledgers only got their root type's usual Account Category (the line of the Schedule "
                    "III / IFRS statements)."
                ).format(out["categories_to_check_count"]),
                "examples": out["categories_to_check"][:3],
                "choices": [
                    {"answer": "accept", "label": _("Use them; they can be changed later on the account")},
                    {"answer": "review", "label": _("Show me the list first")},
                ],
                "suggested": "accept",
            }
        )
    out["questions"] = questions
    out["card_title"] = _("Chart of accounts: {0} accounts to {1}").format(len(nodes), company)


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
        # asked once, on the check's card (names_question), never here
        raise import_chart.ChartProblem(
            _(
                "The file's names carry another ERPNext company's account numbers or abbreviation: the user "
                "answers that on the check's card (dry_run_import, names_question). Pass their answer as "
                "clean_names; nothing was put on the company."
            )
        )
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


def _clean_label(pattern: Dict[str, Any]) -> str:
    """The suggested answer, said as what it does: the number moves to Account Number, ERPNext shows it."""
    if pattern["names_with_number"] and pattern["abbreviation"]:
        return _("Move the number to Account Number and remove {0}").format(pattern["abbreviation"])
    if pattern["names_with_number"]:
        return _("Move the number to Account Number")
    return _("Remove {0}").format(pattern["abbreviation"])


def names_question(pattern: Dict[str, Any]) -> Dict[str, Any]:
    """The check's question when the file's names carry another ERPNext company's account numbers or
    abbreviation, for one single-choice card: removing them is suggested, as ERPNext adds this company's own."""
    said = []
    if pattern["names_with_number"]:
        said.append(_("{0} names start with their account number").format(pattern["names_with_number"]))
    if pattern["abbreviation"]:
        said.append(
            _("{0} names end in another company's abbreviation ({1})").format(
                pattern["names_with_abbreviation"], pattern["abbreviation"]
            )
        )
    return {
        "id": "chart:clean_names",
        "kind": "clean_names",
        "card": "ask_user single_select",
        "message": _(
            "The account names look like another ERPNext company's: {0}. ERPNext adds this company's own "
            "number and abbreviation to every account, so kept as they are they would be doubled."
        ).format("; ".join(said)),
        "examples": pattern["examples"],
        "choices": [
            {"label": _clean_label(pattern), "clean_names": True},
            {"label": _("Keep the names as they are"), "clean_names": False},
        ],
        "suggested": True,
    }


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
            "questions",
            "add_leaves_beside",
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
        if mode == "replace":
            # live, 2026-11-19: the card's "replace" was sent here as a mode, and the user's choice was lost
            return {
                "success": False,
                "error": _(
                    "Replace is its own tool: call replace_chart_of_accounts with session, company and the "
                    "figures of the check (modes.replace_figures: accounts_removed, accounts_created, "
                    "tax_setup_removed). Nothing was changed."
                ),
            }
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
        mark_done(name)
        created = result.pop("created")
        result["created_count"] = len(created)
        result["created"] = created[:CREATED_SHOWN]  # a few names, never the whole chart
        if isinstance(result.get("unmatched"), list):
            result["unmatched_count"] = len(result["unmatched"])
            result["unmatched"] = result["unmatched"][:SHOWN]
        return {
            "success": True,
            "company": company,
            "mode": mode,
            "source_system": system,
            **result,
            "old_ids_kept": len(kept["written"]),
            "old_id_conflicts": kept["conflicts"][:SHOWN],
            "old_id_systems": kept["systems"],
            "message": _repeat_note(company, result)
            + _old_ids_message(result["created_count"], system, kept)
            + " "
            + _(
                "The chart is in place: tell the user, and ask what they want next. Don't start another step."
            ),
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
    if result.get("created_count", len(result.get("created") or [])) or not result.get("already_on_company"):
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


#: What the chart check's reply starts with: the card, then the figures (a long reply is cut from its end)
CARD_FIRST = (
    "success",
    "session",
    "company",
    "card_title",
    "questions",
    "names_question",
    "message",
    "modes",
)


def _card_first(out: Dict[str, Any]) -> Dict[str, Any]:
    return {**{key: out[key] for key in CARD_FIRST if key in out}, **out}


def check_chart(name: str, company: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """What the chart would become: read from the session, nothing written. dry_run_import's chart
    check."""
    companies = frappe.get_list("Company", pluck="name", order_by="name")
    if company and not frappe.db.exists("Company", company):
        # live, 2026-11-19: "(site's only company)" was passed as the name; the check failed, nothing shown
        company = ""
    if not company and len(companies) == 1:
        company = companies[0]  # nothing to ask on a site of one company
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
            else:
                pattern = None  # answered: not asked again
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
            return _card_first(out)
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
            chart_card(out, nodes, classes, company, pattern)
        else:
            # several companies and none named: the check still shows the chart; the card asks the company
            # first, and the next check, with it, gives the rest of the card
            out["questions"] = [
                {
                    "id": "chart:company",
                    "kind": "company",
                    "message": _("Which company is this chart for?"),
                    "choices": companies,
                    "suggested": None,
                }
            ]
            if pattern and arguments.get("clean_names") is None:
                out["questions"].append(names_question(pattern))
            out["card_title"] = _("Chart of accounts: {0} accounts").format(len(nodes))
        return _card_first(out)
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
