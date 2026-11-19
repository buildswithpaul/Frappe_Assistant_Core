# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""The client's own chart of accounts (#34422).

``read_chart`` reads the tree from an import session whose columns are mapped to Account fields
(account_name, parent_account, account_number, root_type, account_type, is_group): from Tally, Zoho,
QuickBooks or any sheet. ``classify`` proposes each account's root type and account type, ``problems``
lists what is wrong with the tree before anything is written. Three modes put it on a company: map onto
the accounts it has, add under the right parents, or replace the standard chart of a company that has
no transactions. The client's names and numbers are kept as old IDs, so the opening trial balance
resolves by them.
"""

import re
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

import frappe
from frappe import _
from frappe.utils import cint, cstr

from frappe_assistant_core.utils import compat, import_keys
from frappe_assistant_core.utils import import_dry_run as dry_run

ACCOUNT = "Account"
ROOT_TYPES = ("Asset", "Liability", "Equity", "Income", "Expense")
MAX_ACCOUNTS = 5000
OUTLINE_DEPTH = 2
#: Headings of the column that gives each account's parent by number (ERPNext's importer template), as _key keeps them
PARENT_NUMBER_HEADINGS = ("parent account number", "parent number")


class ChartProblem(Exception):
    """The chart can't be read or put on the company. The message is shown to the user."""


# -- how accounts are classified (C-D3) -------------------------------------------------------------

#: Tally's primary groups (and the groups under them that name a kind of account): root type, account
#: type of the ledgers below ("" for none), and whether the consultant is asked.
TALLY_GROUPS: Dict[str, Tuple[str, str, bool]] = {
    "capital account": ("Equity", "", False),
    "reserves & surplus": ("Equity", "", False),
    "loans (liability)": ("Liability", "", False),
    "secured loans": ("Liability", "", False),
    "unsecured loans": ("Liability", "", False),
    "current liabilities": ("Liability", "", False),
    "duties & taxes": ("Liability", "Tax", False),
    "sundry creditors": ("Liability", "Payable", False),
    "provisions": ("Liability", "", False),
    "fixed assets": ("Asset", "Fixed Asset", False),
    "investments": ("Asset", "", False),
    "current assets": ("Asset", "", False),
    "bank accounts": ("Asset", "Bank", False),
    "cash-in-hand": ("Asset", "Cash", False),
    "sundry debtors": ("Asset", "Receivable", False),
    "stock-in-hand": ("Asset", "Stock", False),
    "deposits (asset)": ("Asset", "", False),
    "loans & advances (asset)": ("Asset", "", False),
    "sales accounts": ("Income", "", False),
    "direct incomes": ("Income", "", False),
    "indirect incomes": ("Income", "", False),
    "purchase accounts": ("Expense", "", False),
    "direct expenses": ("Expense", "", False),
    "indirect expenses": ("Expense", "", False),
    "suspense a/c": ("Liability", "", True),
    "branch / divisions": ("", "", True),
}

#: Words in an account's own name, when nothing above says: root type and account type.
KEYWORDS: Tuple[Tuple[str, str, str], ...] = (
    (r"\b(banks?)\b", "Asset", "Bank"),
    (r"\b(cash|petty cash)\b", "Asset", "Cash"),
    (r"\b(debtors?|receivables?)\b", "Asset", "Receivable"),
    (r"\b(creditors?|payables?)\b", "Liability", "Payable"),
    (r"\b(stock|inventory)\b", "Asset", "Stock"),
    (r"\b(fixed assets?|plant|machinery|furniture|vehicles?|equipment)\b", "Asset", "Fixed Asset"),
    (r"\b(gst|vat|tax|tds|duties)\b", "Liability", "Tax"),
    (r"\b(capital|equity|reserves?|retained earnings|drawings)\b", "Equity", ""),
    (r"\bliabilit(y|ies)\b", "Liability", ""),
    (r"\b(loans?|borrowings?|overdraft)\b", "Liability", ""),
    (r"\b(sales?|revenue|income|turnover|interest received|commission received)\b", "Income", ""),
    (r"\bassets?\b", "Asset", ""),
    (
        r"\b(purchases?|expenses?|salary|salaries|wages|rent|electricity|freight|depreciation|insurance|fees)\b",
        "Expense",
        "",
    ),
)


def _key(text: Any) -> str:
    return re.sub(r"\s+", " ", cstr(text).strip().lower())


# -- reading the tree --------------------------------------------------------------------------------


def _truthy(value: Any) -> Optional[bool]:
    text = _key(value)
    if text in ("1", "yes", "true", "y", "group"):
        return True
    if text in ("0", "no", "false", "n", "ledger"):
        return False
    return None


#: "141600 - State Bank of India": the account number in front of the name, as ERPNext names an account
NUMBER_PREFIX = re.compile(r"^(\d[\d./-]*)\s+-\s+(\S.*)$")
#: "State Bank of India - CCBF": the company's abbreviation after the name, as ERPNext names an account
ABBR = re.compile(r"[A-Za-z0-9&.]{1,10}")
#: ERPNext's longest account name: a longer cell isn't one of its names
NAME_LENGTH = 140


def _abbr_of(name: str) -> Optional[str]:
    """The abbreviation after the last " - " of ``name``, or None (split, not matched: a name is file text)."""
    if len(name) > NAME_LENGTH or " - " not in name:
        return None
    head, tail = name.rsplit(" - ", 1)
    tail = tail.strip()
    return tail if head.strip() and ABBR.fullmatch(tail) else None


#: Share of the file's names that must end in one abbreviation for it to be the other company's
ABBR_SHARE = 0.6


def _split_name(text: Any, abbr: Optional[str], numbered: bool) -> Tuple[str, str]:
    """``text`` without the other company's abbreviation at its end and, when ``numbered``, without the
    account number in front: (name, number)."""
    text = cstr(text).strip()
    if len(text) > NAME_LENGTH:
        return text, ""
    if abbr and text.endswith(f" - {abbr}"):
        text = text[: -len(abbr) - 3].strip()
    found = NUMBER_PREFIX.match(text) if numbered else None
    if found:
        return found.group(2).strip(), found.group(1)
    return text, ""


def name_pattern(nodes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Whether the file's names are as another ERPNext company writes them, "141600 - State Bank of India -
    CCBF": its account number in front, its abbreviation behind. Put on this company as they are, ERPNext
    adds this company's number and abbreviation again ("141600 - 141600 - State Bank of India - CCBF - P").
    None when the names aren't so; else the abbreviation, how many names have it and the number, and three
    names as they are and as they would be."""
    names = [n["raw_name"] for n in nodes]
    tails: Dict[str, int] = {}
    for name in names:
        tail = _abbr_of(name)
        if tail:
            tails[tail] = tails.get(tail, 0) + 1
    abbr, with_abbr = max(tails.items(), key=lambda kv: kv[1]) if tails else (None, 0)
    if with_abbr < max(2, len(names) * ABBR_SHARE):
        abbr, with_abbr = None, 0
    with_number = sum(1 for name in names if _split_name(name, abbr, True)[1])
    if with_number < 2:
        with_number = 0
    if not abbr and not with_number:
        return None
    return {
        "abbreviation": abbr,
        "names_with_abbreviation": with_abbr,
        "names_with_number": with_number,
        "examples": [
            {"in_the_file": n, "cleaned": _split_name(n, abbr, bool(with_number))[0]}
            for n in names
            if _split_name(n, abbr, bool(with_number))[0] != n
        ][:3],
    }


def clean_names(nodes: List[Dict[str, Any]], pattern: Optional[Dict[str, Any]]) -> None:
    """Take the other company's number and abbreviation off the names and parents (name_pattern); a number
    taken off becomes the account's number when the file gives none. The nodes are changed."""
    if not pattern:
        return
    abbr, numbered = pattern["abbreviation"], bool(pattern["names_with_number"])
    for node in nodes:
        name, number = _split_name(node["raw_name"], abbr, numbered)
        node["name"] = name
        if number and not node["number"]:
            node["number"] = number
        parent, parent_number = _split_name(node["raw_parent"], abbr, numbered)
        node["parent_name"] = parent
        if parent_number and not node["parent_number"]:
            node["parent_number"] = parent_number


def read_chart(
    session, root_type_column: Optional[str] = None, clean: Optional[bool] = None
) -> List[Dict[str, Any]]:
    """The accounts of the session's file as nodes, in file order. Raises ChartProblem when the file
    isn't a chart (no column mapped to Account Name) or has too many accounts. Root Type is read-only on
    Account, so a column that holds it can't be mapped: ``root_type_column`` names it by its heading.
    ``clean``: take another ERPNext company's account numbers and abbreviation off the names
    (name_pattern); the user decides."""
    mapping = {
        field: int(position)
        for position, field in dry_run.column_to_field_map(session).items()
        if str(position).isdigit() and field and field != "Don't Import"
    }
    if "account_name" not in mapping:
        raise ChartProblem(_("Map a column to Account Name first (set_column_mapping, DocType Account)."))
    if not root_type_column:
        # FACO left it out though the file has the column (live, 2026-11-19): the root types were then
        # guessed from the tree, and the check warned of 9 other accounts than the file's own 14
        from frappe_assistant_core.utils.import_mapping import session_headers

        root_type_column = next((h for h in session_headers(session) if _key(h) == "root type"), None)
    if root_type_column:
        from frappe_assistant_core.utils.import_mapping import session_headers

        wanted = _key(root_type_column)
        found = next((i for i, h in enumerate(session_headers(session)) if _key(h) == wanted), None)
        if found is None:
            raise ChartProblem(_("The file has no column {0}.").format(root_type_column))
        mapping["root_type"] = found
    # ERPNext's own Chart of Accounts Importer template names each account's parent by number as well, in a
    # column no Account field holds: read by its heading, it says which parent is meant when names repeat.
    if "parent_number" not in mapping:
        from frappe_assistant_core.utils.import_mapping import session_headers

        found = next(
            (i for i, h in enumerate(session_headers(session)) if _key(h) in PARENT_NUMBER_HEADINGS), None
        )
        if found is not None:
            mapping["parent_number"] = found
    rows = dry_run.read_sheet_rows(dry_run.readable_session_file(session), session.sheet or None)

    def cell(row, field) -> str:
        position = mapping.get(field)
        return cstr(row[position]).strip() if position is not None and position < len(row) else ""

    nodes: List[Dict[str, Any]] = []
    for number, row in enumerate(rows[1:], start=2):  # row 1 is the header
        name = cell(row, "account_name")
        if not name:
            continue
        nodes.append(
            {
                "row": number,
                "name": name,
                "raw_name": name,
                "number": cell(row, "account_number"),
                "parent_name": cell(row, "parent_account"),
                "raw_parent": cell(row, "parent_account"),
                "parent_number": cell(row, "parent_number"),
                "root_type": cell(row, "root_type"),
                "account_type": cell(row, "account_type"),
                "account_category": cell(row, "account_category"),
                "explicit_group": _truthy(cell(row, "is_group")),
            }
        )
    if len(nodes) > MAX_ACCOUNTS:
        raise ChartProblem(_("A chart has at most {0} accounts.").format(MAX_ACCOUNTS))
    if not nodes:
        raise ChartProblem(_("The file has no accounts."))
    if clean:
        clean_names(nodes, name_pattern(nodes))
    _link(nodes)
    return nodes


def _link(nodes: List[Dict[str, Any]]) -> None:
    """Give each node its parent (by the parent's number when the file gives it, else by name, else by
    number), its children and whether it is a group. A sub-account may repeat its parent's name under its
    own number, so the parent's number is the one sure link."""
    by_name: Dict[str, List[int]] = {}
    by_number: Dict[str, int] = {}
    for index, node in enumerate(nodes):
        by_name.setdefault(_key(node["name"]), []).append(index)
        if node["number"]:
            by_number.setdefault(_key(node["number"]), index)
        node["index"] = index
        node["children"] = []
        node["parent"] = None
        node["outside_parent"] = None
    for node in nodes:
        wanted = node["parent_name"]
        if not wanted:
            continue
        by_parent_number = _key(node.get("parent_number"))
        if by_parent_number and by_parent_number in by_number:
            found = [by_number[by_parent_number]]
        else:
            found = by_name.get(_key(wanted)) or (
                [by_number[_key(wanted)]] if _key(wanted) in by_number else []
            )
        found = [i for i in found if i != node["index"]]
        if found:
            node["parent"] = found[0]
            nodes[found[0]]["children"].append(node["index"])
        else:
            node["outside_parent"] = wanted
    for node in nodes:
        node["is_group"] = (
            bool(node["children"]) if node["explicit_group"] is None else node["explicit_group"]
        )


def _depth(nodes: List[Dict[str, Any]], node: Dict[str, Any]) -> int:
    depth, seen = 0, {node["index"]}
    while node["parent"] is not None and node["parent"] not in seen:
        seen.add(node["parent"])
        node = nodes[node["parent"]]
        depth += 1
    return depth


def problems(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """What is wrong with the tree, each with its rows, before anything is written (CA-8): a cycle, an
    account under a ledger, two accounts with one name or number."""
    out: List[Dict[str, Any]] = []
    in_cycle = set()
    for node in nodes:
        seen, current = {node["index"]}, node["parent"]
        while current is not None:
            if current in seen:
                in_cycle.add(node["index"])
                break
            seen.add(current)
            current = nodes[current]["parent"]
    if in_cycle:
        out.append(
            {
                "kind": "cycle",
                "rows": sorted(nodes[i]["row"] for i in in_cycle),
                "message": _("These accounts are each other's parents: {0}.").format(
                    ", ".join(nodes[i]["name"] for i in sorted(in_cycle))
                ),
            }
        )
    for node in nodes:
        if node["children"] and node["explicit_group"] is False:
            out.append(
                {
                    "kind": "under_ledger",
                    "rows": [node["row"]],
                    "message": _("{0} is marked as a ledger but has accounts under it.").format(node["name"]),
                }
            )
    for label, key in (("name", "name"), ("number", "number")):
        seen: Dict[Any, Dict[str, Any]] = {}
        for node in nodes:
            value = _key(node[key])
            if not value:
                continue
            if label == "name":
                # ERPNext names an account "<number> - <name> - <abbr>": one name under two numbers is two
                # accounts. Only the same name with the same number, or with none, is one twice.
                value = (value, _key(node["number"]))
            if value in seen:
                out.append(
                    {
                        "kind": f"duplicate_{label}",
                        "rows": [seen[value]["row"], node["row"]],
                        "message": _("Account {0} {1} is in the file twice (rows {2} and {3}).").format(
                            label, node[key], seen[value]["row"], node["row"]
                        ),
                    }
                )
            else:
                seen[value] = node
    return out


# -- classification ----------------------------------------------------------------------------------


def _account_types() -> List[str]:
    df = frappe.get_meta(ACCOUNT).get_field("account_type")
    return [o for o in (df.options or "").split("\n") if o] if df else []


def _from_name(name: str) -> Optional[Tuple[str, str]]:
    for pattern, root, account_type in KEYWORDS:
        if re.search(pattern, _key(name)):
            return root, account_type
    return None


def classify(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Each account's proposed root type and account type, and where it came from, in the order of C-D3:
    the file's own columns, Tally's primary groups (the nearest of the account and its parents), words in
    the name unless they say another root type than the parent's, then the parent's root type. An account none of these places is ``unclassified``. An
    account type goes on ledgers only. The nodes are not changed."""
    valid_types = set(_account_types())
    out: Dict[int, Dict[str, Any]] = {}
    raw: Dict[int, Dict[str, Any]] = {}  # what each account is before a group gives up its account type

    def own(node) -> Optional[Dict[str, Any]]:
        root = next((r for r in ROOT_TYPES if _key(r) == _key(node["root_type"])), None)
        account_type = node["account_type"] if node["account_type"] in valid_types else ""
        if root:
            return {"root_type": root, "account_type": account_type, "source": "column"}
        if account_type:
            guess = _from_name(account_type) or ()
            if guess:
                return {"root_type": guess[0], "account_type": account_type, "source": "column"}
        return None

    def tally(node) -> Optional[Dict[str, Any]]:
        current, seen = node, set()
        while current is not None and current["index"] not in seen:
            seen.add(current["index"])
            found = TALLY_GROUPS.get(_key(current["name"]))
            if found:
                root, account_type, ask = found
                if ask or not root:
                    return None
                return {"root_type": root, "account_type": account_type, "source": "tally group"}
            current = nodes[current["parent"]] if current["parent"] is not None else None
        return None

    def resolve(node, seen=()) -> Dict[str, Any]:
        if node["index"] in out:
            return out[node["index"]]
        found = own(node) or tally(node)
        above = None
        if node["parent"] is not None and node["parent"] not in seen:
            above = resolve(nodes[node["parent"]], (*seen, node["index"]))
        if not found:
            guess = _from_name(node["name"])
            # a word in the name never outranks the parent's root type: "Bank Fees" under Expenses is an
            # expense, not a bank
            if guess and not (above and above["root_type"] and above["root_type"] != guess[0]):
                found = {"root_type": guess[0], "account_type": guess[1], "source": "name"}
        if not found and above:
            if above["root_type"]:
                # a ledger under "Bank Accounts" is a bank; a group below it only carries the root type
                kind = raw[node["parent"]]["account_type"] if not node["is_group"] else ""
                found = {"root_type": above["root_type"], "account_type": kind, "source": "parent"}
        found = found or {"root_type": "", "account_type": "", "source": "unclassified"}
        raw[node["index"]] = found
        if node["is_group"]:
            found = {**found, "account_type": ""}
        elif found["account_type"] and found["account_type"] not in valid_types:
            found = {**found, "account_type": ""}
        out[node["index"]] = found
        return found

    classes = [{**resolve(node), "index": node["index"]} for node in nodes]
    if categories_supported():
        categorize(nodes, classes)
    return classes


# -- account categories (ERPNext v16) ----------------------------------------------------------------
# v16's Schedule III and IFRS statements place an account by its Account Category and read it from
# ledgers only (financial_report_engine). Live, 2026-11-19: none of a client's 1,043 imported accounts had
# one. v15 has no categories: nothing here runs there.

#: Categories ERPNext ships without a root type: the root type each belongs under
CATEGORY_ROOTS = {
    "Capital Work in Progress": "Asset",
    "Intangible Assets Under Development": "Asset",
    "Long-term Loans and Advances": "Asset",
    "Deferred Tax Assets": "Asset",
    "Deferred Tax Liabilities": "Liability",
    "Deferred Tax Expense": "Expense",
    "Share Application Money Pending Allotment": "Equity",
    "Money Received Against Share Warrants": "Equity",
}

#: A name of the account or a group above it saying it is due after a year, or within one
LONG_TERM = r"\bnon[ -]?current\b|\blong[ -]?term\b|\b(greater|more) than (1|one) years?\b|>\s?1 years?"
SHORT_TERM = r"\bcurrent\b|\bshort[ -]?term\b"

_TAX = r"\b(gst|igst|cgst|sgst|utgst|tds|tcs|vat|tax|taxes|cenvat|cess|duties)\b"

#: Words in an account's own name: its root type, its category, and the category when due after a year.
#: The first that fits wins: a fixed deposit is an investment though the file types it "Fixed Asset", and
#: interest accrued on one is a current asset.
CATEGORY_WORDS: Tuple[Tuple[str, str, str, Optional[str]], ...] = (
    (r"\bdeferred tax", "Asset", "Deferred Tax Assets", None),
    (
        r"\bcapital work[ -]in[ -]progress\b|\bcwip\b|\bcapital w\.?i\.?p\b",
        "Asset",
        "Capital Work in Progress",
        None,
    ),
    (r"\bintangible assets? under development\b", "Asset", "Intangible Assets Under Development", None),
    (
        r"\bintangible|\bgoodwill\b|\bsoftware\b|\bpatents?\b|\btrade ?marks?\b",
        "Asset",
        "Intangible Assets",
        None,
    ),
    (_TAX + r"|\binput credit\b", "Asset", "Other Current Assets", None),
    (
        r"\binterest\b|\baccrued\b|\bprepaid\b|\bunbilled\b",
        "Asset",
        "Other Current Assets",
        "Other Non-current Assets",
    ),
    (
        r"\binvestments?\b|\bfixed deposits?\b|\bmutual funds?\b|\bbonds?\b",
        "Asset",
        "Short-term Investments",
        "Long-term Investments",
    ),
    (r"\binter[ -]?(company|unit|branch)\b", "Asset", "Other Receivables", None),
    (r"\b(loans?|advances?)\b", "Asset", "Other Current Assets", "Long-term Loans and Advances"),
    (r"\b(debtors?|receivables?)\b", "Asset", "Trade Receivables", None),
    (r"\b(cash|banks?|petty cash)\b", "Asset", "Cash and Cash Equivalents", None),
    (
        r"\b(stocks?|inventor(y|ies)|raw materials?|finished goods|work[ -]in[ -]progress)\b",
        "Asset",
        "Stock Assets",
        None,
    ),
    (
        r"\b(fixed assets?|tangible|depreciation|plant|machinery|furniture|fixtures|vehicles?|equipments?|"
        r"computers?|buildings?|land)\b",
        "Asset",
        "Tangible Assets",
        None,
    ),
    (r"\bdeposits?\b", "Asset", "Other Current Assets", "Other Non-current Assets"),
    (r"\bdeferred tax", "Liability", "Deferred Tax Liabilities", None),
    (_TAX, "Liability", "Current Tax Liabilities", None),
    (r"\bprovisions?\b", "Liability", "Short-term Provisions", "Long-term Provisions"),
    # an overdraft is repayable on demand wherever the file puts it
    (r"\b(overdrafts?|od|cash credit)\b", "Liability", "Short-term Borrowings", None),
    # interest owed on a loan is not the loan
    (r"\binterest\b.*\b(payable|accrued|due)\b", "Liability", "Other Current Liabilities", None),
    (
        r"\b(loans?|borrowings?|debentures?)\b",
        "Liability",
        "Short-term Borrowings",
        "Long-term Borrowings",
    ),
    (r"\binter[ -]?(company|unit|branch)\b", "Liability", "Other Payables", None),
    (r"\b(creditors?|suppliers?|vendors?|trade payables?)\b", "Liability", "Trade Payables", None),
    (r"\bpayables?\b", "Liability", "Other Payables", None),
    (r"\bshare application\b", "Equity", "Share Application Money Pending Allotment", None),
    (r"\bshare warrants?\b", "Equity", "Money Received Against Share Warrants", None),
    (
        r"\b(reserves?|surplus|retained|premium|profit (and|&) loss|drawings?)\b",
        "Equity",
        "Reserves and Surplus",
        None,
    ),
    (r"\b(share capital|capital|shares?)\b", "Equity", "Share Capital", None),
    (r"\b(interest|dividends?|investments?|capital gains?)\b", "Income", "Investment Income", None),
    (
        r"\b(other|indirect|misc|miscellaneous|discounts?|commission|scrap|rent)\b",
        "Income",
        "Other Operating Income",
        None,
    ),
    (r"\b(sales?|revenue|turnover|operations)\b", "Income", "Revenue from Operations", None),
    (r"\bdeferred tax", "Expense", "Deferred Tax Expense", None),
    (r"\b(income tax|current tax|tax expenses?|taxation)\b", "Expense", "Tax Expense", None),
    (r"\b(interest|finance (costs?|charges)|bank charges)\b", "Expense", "Finance Costs", None),
    (r"\b(cost of (goods|sales)|cogs|purchases?|consum(ed|ption))\b", "Expense", "Cost of Goods Sold", None),
)

#: A ledger's account type: its category, by root type
CATEGORY_BY_TYPE: Dict[str, Dict[str, str]] = {
    "Bank": {"Asset": "Cash and Cash Equivalents", "Liability": "Short-term Borrowings"},
    "Cash": {"Asset": "Cash and Cash Equivalents"},
    "Receivable": {"Asset": "Trade Receivables"},
    "Payable": {"Liability": "Trade Payables"},
    "Stock": {"Asset": "Stock Assets"},
    "Fixed Asset": {"Asset": "Tangible Assets"},
    "Accumulated Depreciation": {"Asset": "Tangible Assets"},
    "Capital Work in Progress": {"Asset": "Capital Work in Progress"},
    "Tax": {"Asset": "Other Current Assets", "Liability": "Current Tax Liabilities"},
    "Current Asset": {"Asset": "Other Current Assets"},
    "Asset Received But Not Billed": {"Asset": "Other Current Assets"},
    "Current Liability": {"Liability": "Other Current Liabilities"},
    "Stock Received But Not Billed": {"Liability": "Other Current Liabilities"},
    "Service Received But Not Billed": {"Liability": "Other Current Liabilities"},
    "Equity": {"Equity": "Reserves and Surplus"},
    "Cost of Goods Sold": {"Expense": "Cost of Goods Sold"},
    "Direct Expense": {"Expense": "Other Direct Costs"},
    "Indirect Expense": {"Expense": "Operating Expenses"},
    "Expense Account": {"Expense": "Operating Expenses"},
    "Chargeable": {"Expense": "Operating Expenses"},
    "Depreciation": {"Expense": "Operating Expenses"},
    "Direct Income": {"Income": "Revenue from Operations"},
    "Income Account": {"Income": "Revenue from Operations"},
    "Indirect Income": {"Income": "Other Operating Income"},
}

#: A ledger nothing else places: its root type's usual category (and when due after a year), to be checked
CATEGORY_FALLBACK: Dict[str, Tuple[str, Optional[str]]] = {
    "Asset": ("Other Current Assets", "Other Non-current Assets"),
    "Liability": ("Other Current Liabilities", "Other Non-current Liabilities"),
    "Equity": ("Reserves and Surplus", None),
    "Income": ("Revenue from Operations", None),
    "Expense": ("Operating Expenses", None),
}

_standard_categories_cache: Optional[Dict[str, str]] = None


def categories_supported() -> bool:
    """Whether this site's Account has a category (ERPNext v16)."""
    return compat.has_field(ACCOUNT, "account_category") and bool(frappe.db.table_exists("Account Category"))


def site_categories() -> Dict[str, Tuple[str, str]]:
    """{name as _key keeps it: (name, root type)} of the site's Account Categories; "" root type: any."""
    return {
        _key(row.name): (row.name, row.root_type or CATEGORY_ROOTS.get(row.name, ""))
        for row in frappe.get_all("Account Category", fields=["name", "root_type"])
    }


def _standard_categories() -> Dict[str, str]:
    """{account name as _key keeps it: category} of ERPNext's own charts that carry categories, the way
    ERPNext's v16 patch maps a company's accounts (update_account_categories_for_existing_accounts)."""
    global _standard_categories_cache
    if _standard_categories_cache is not None:
        return _standard_categories_cache
    from erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts import get_chart

    found: Dict[str, str] = {}

    def walk(tree: Dict[str, Any]) -> None:
        for name, child in tree.items():
            if name in compat.CHART_NODE_KEYS or not isinstance(child, dict):
                continue
            if child.get("account_category"):
                found.setdefault(_key(name), child["account_category"])
            walk(child)

    for template in ("Standard", "Standard with Numbers", "India - Chart of Accounts"):
        try:
            walk(get_chart(template) or {})
        except Exception:
            continue
    _standard_categories_cache = found
    return found


def _long_term(nodes: List[Dict[str, Any]], node: Dict[str, Any]) -> bool:
    """Whether the account's name, or the nearest group above it that says, makes it due after a year."""
    current, seen = node, set()
    while current is not None and current["index"] not in seen:
        seen.add(current["index"])
        name = _key(current["name"])[:NAME_LENGTH]
        if re.search(LONG_TERM, name):
            return True
        if re.search(SHORT_TERM, name):
            return False
        current = nodes[current["parent"]] if current["parent"] is not None else None
    return False


def categorize(
    nodes: List[Dict[str, Any]], classes: List[Dict[str, Any]], categories: Optional[Dict] = None
) -> None:
    """Put each account's Account Category, and where it came from, on its class (``account_category``,
    ``category_from``). The first that fits the account's root type wins: the file's own category (or the
    user's answer), ERPNext's own chart's account of that name, words in the name, the group above, the
    ledger's account type, and for a ledger nothing places its root type's usual category ("fallback": the
    user checks those). A group gets no fallback: ERPNext reads the category of ledgers only."""
    categories = site_categories() if categories is None else categories
    standard = _standard_categories()
    done: Dict[int, Tuple[str, str]] = {}

    def usable(category: Any, root: str) -> str:
        found = categories.get(_key(category)) if category else None
        if not found:
            return ""
        name, needs = found
        return name if not needs or not root or needs == root else ""

    def by_words(node: Dict[str, Any], root: str) -> str:
        name = _key(node["name"])
        if len(name) > NAME_LENGTH:
            return ""  # file text no account name is: never run the rules on it
        for pattern, wanted, short, long in CATEGORY_WORDS:
            if wanted == root and re.search(pattern, name):
                got = usable(long if long and _long_term(nodes, node) else short, root)
                if got:
                    return got
        return ""

    def resolve(index: int, seen=()) -> Tuple[str, str]:
        if index in done:
            return done[index]
        node, c = nodes[index], classes[index]
        root = c["root_type"] or ""
        found = ("", "")
        if usable(node.get("account_category"), root):
            found = (usable(node["account_category"], root), "column")
        if not found[0] and usable(standard.get(_key(node["name"])), root):
            found = (usable(standard[_key(node["name"])], root), "erpnext name")
        if not found[0]:
            words = by_words(node, root)
            if words:
                found = (words, "name")
        if not found[0] and node["parent"] is not None and node["parent"] not in seen:
            above = resolve(node["parent"], (*seen, index))[0]
            if usable(above, root):
                found = (above, "parent")
        if not found[0] and not node["is_group"]:
            kind = usable(CATEGORY_BY_TYPE.get(c["account_type"] or "", {}).get(root), root)
            if kind:
                found = (kind, "account type")
        if not found[0] and not node["is_group"] and root in CATEGORY_FALLBACK:
            short, long = CATEGORY_FALLBACK[root]
            pick = usable(long if long and _long_term(nodes, node) else short, root)
            if pick:
                found = (pick, "fallback")
        done[index] = found
        return found

    for node in nodes:
        category, source = resolve(node["index"])
        classes[node["index"]]["account_category"] = category
        classes[node["index"]]["category_from"] = source


def categories_not_found(nodes: List[Dict[str, Any]], classes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The file's own categories that weren't used: the site has no such category, or it is of another root
    type than the account."""
    return [
        {"row": n["row"], "account": n["name"], "value": n["account_category"]}
        for n, c in zip(nodes, classes)
        if n.get("account_category") and c.get("category_from") != "column"
    ]


def fill_categories(company: str) -> Dict[str, Any]:
    """Set the Account Category of ``company``'s accounts that have none, by the rules of a chart import,
    reading the tree from its accounts. An account that has one keeps it, and the accounts under it follow
    it. For a company whose chart came in before categories were set (live: 1,043 accounts, none)."""
    rows = frappe.get_all(
        ACCOUNT,
        filters={"company": company},
        fields=[
            "name",
            "account_name",
            "parent_account",
            "is_group",
            "root_type",
            "account_type",
            "account_category",
            "freeze_account",
        ],
        order_by="lft",
    )
    position = {r.name: i for i, r in enumerate(rows)}
    nodes = [
        {
            "index": i,
            "row": None,
            "name": r.account_name or r.name,
            "is_group": bool(r.is_group),
            "parent": position.get(r.parent_account),
            "account_category": r.account_category or "",
        }
        for i, r in enumerate(rows)
    ]
    classes = [{"root_type": r.root_type or "", "account_type": r.account_type or ""} for r in rows]
    categorize(nodes, classes)
    updates: Dict[str, Dict[str, str]] = {}
    by_category: Dict[str, int] = {}
    to_check: List[Dict[str, Any]] = []
    skipped: List[str] = []
    for r, c in zip(rows, classes):
        if r.account_category or not c["account_category"]:
            continue
        # the whole tree is read to follow the groups, but only what the user may edit is written, and
        # never a frozen account (ERPNext keeps those as they are)
        if r.freeze_account == "Yes" or not frappe.has_permission(ACCOUNT, "write", doc=r.name):
            skipped.append(r.name)
            continue
        updates[r.name] = {"account_category": c["account_category"]}
        if not r.is_group:
            by_category[c["account_category"]] = by_category.get(c["account_category"], 0) + 1
            if c["category_from"] == "fallback":
                to_check.append(
                    {"account": r.name, "root_type": r.root_type, "account_category": c["account_category"]}
                )
    if updates:
        frappe.db.bulk_update(ACCOUNT, updates)
    return {
        "categories_set": len(updates),
        "categories_kept": sum(1 for r in rows if r.account_category),
        "not_changed_frozen_or_not_allowed": skipped[:CATEGORIES_SHOWN],
        "by_category": by_category,
        "categories_to_check": to_check[:CATEGORIES_SHOWN],
        "categories_to_check_count": len(to_check),
        "ledgers_without_category": [
            r.name
            for r, c in zip(rows, classes)
            if not r.is_group and not r.account_category and r.name not in updates
        ][:CATEGORIES_SHOWN],
    }


#: The accounts a check lists whose category is only their root type's usual one, at most
CATEGORIES_SHOWN = 100


def apply_outside_parents(nodes: List[Dict[str, Any]], company: str) -> None:
    """An account whose parent isn't in the file but is a group account of ``company`` takes that group's
    root type, and, as a ledger, its account type, unless its own columns say otherwise. The nodes are
    changed: it is what an add does with such an account."""
    for node in nodes:
        wanted = node["outside_parent"]
        if not wanted or node["root_type"]:
            continue
        found = frappe.db.get_value(
            ACCOUNT,
            {"company": company, "account_name": wanted, "is_group": 1},
            ["root_type", "account_type"],
            as_dict=True,
        ) or frappe.db.get_value(
            ACCOUNT,
            {"company": company, "account_number": wanted, "is_group": 1},
            ["root_type", "account_type"],
            as_dict=True,
        )
        if found and found.root_type:
            node["root_type"] = found.root_type
            if not node["account_type"] and not node["is_group"] and found.account_type:
                node["account_type"] = found.account_type


def apply_answers(nodes: List[Dict[str, Any]], answers: Optional[Dict[str, Any]]) -> None:
    """Put the consultant's answers for accounts that couldn't be classified onto the nodes (their own
    columns, the first thing classification reads). ``answers`` is ``{account name: {root_type,
    account_type}}``. Raises ChartProblem for a root type or account type ERPNext doesn't have."""
    if not answers:
        return
    if not isinstance(answers, dict):
        raise ChartProblem(_("classifications is an object: {account name: {root_type, account_type}}."))
    valid = set(_account_types())
    by_name = {_key(n["name"]): n for n in nodes}
    for name, answer in answers.items():
        node = by_name.get(_key(name))
        if not node:
            raise ChartProblem(_("There is no account {0} in the file.").format(name))
        answer = answer if isinstance(answer, dict) else {"root_type": answer}
        category = cstr(answer.get("account_category"))
        if category:
            found = site_categories().get(_key(category)) if categories_supported() else None
            if not found:
                raise ChartProblem(_("{0}: {1} isn't an account category.").format(name, category))
            node["account_category"] = found[0]
            if not answer.get("root_type") and not answer.get("account_type"):
                continue  # the category alone: the account keeps its root and account type
        root = cstr(answer.get("root_type"))
        if root not in ROOT_TYPES:
            raise ChartProblem(_("{0}: root type must be one of {1}.").format(name, ", ".join(ROOT_TYPES)))
        account_type = cstr(answer.get("account_type"))
        if account_type and account_type not in valid:
            raise ChartProblem(_("{0}: {1} isn't an account type.").format(name, account_type))
        node["root_type"], node["account_type"] = root, account_type


def report(session) -> Dict[str, Any]:
    """What FACO shows of a chart (CA-1, CA-2), read from the session."""
    nodes = read_chart(session)
    return summary(nodes, classify(nodes))


#: The root types an account type belongs under, where ERPNext's own charts never put it anywhere else:
#: a "Stock" account is stock in hand to ERPNext (perpetual inventory posts to it), so one under Equity is
#: a mistake in the file, not a choice. Types that sit under more than one root (Bank: an overdraft is a
#: liability; Tax; Chargeable...) are not checked.
EXPECTED_ROOTS = {
    "Receivable": ("Asset",),
    "Payable": ("Liability",),
    "Cash": ("Asset",),
    "Stock": ("Asset",),
    "Fixed Asset": ("Asset",),
    "Accumulated Depreciation": ("Asset",),
    "Current Asset": ("Asset",),
    "Current Liability": ("Liability",),
    "Equity": ("Equity",),
    "Income Account": ("Income",),
    "Direct Income": ("Income",),
    "Indirect Income": ("Income",),
    "Expense Account": ("Expense",),
    "Direct Expense": ("Expense",),
    "Indirect Expense": ("Expense",),
    "Cost of Goods Sold": ("Expense",),
    "Depreciation": ("Expense",),
}


def doubtful(nodes: List[Dict[str, Any]], classes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Accounts whose account type doesn't belong under their root type (EXPECTED_ROOTS), as the file has
    them: ERPNext takes them, and books to them as their type says. Live, 2026-11-18, a client's chart had
    13 "Stock" accounts under Equity and an expense account under Income. The user decides: correct the
    file, or go on."""
    out = []
    for node, c in zip(nodes, classes):
        expected = EXPECTED_ROOTS.get(c["account_type"] or "")
        if expected and c["root_type"] and c["root_type"] not in expected:
            out.append(
                {
                    "row": node["row"],
                    "account": node["name"],
                    "number": node["number"] or None,
                    "account_type": c["account_type"],
                    "root_type": c["root_type"],
                    "expected_root_type": expected[0],
                }
            )
    return out


def summary(nodes: List[Dict[str, Any]], classes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Counts, the tree's top levels with each account's proposed types, every account that couldn't be
    classified in one list, the problems of the tree and the parents the file names that it doesn't hold."""
    sources: Dict[str, int] = {}
    roots: Dict[str, int] = {}
    for c in classes:
        sources[c["source"]] = sources.get(c["source"], 0) + 1
        if c["root_type"]:
            roots[c["root_type"]] = roots.get(c["root_type"], 0) + 1
    outline = []
    for node, c in zip(nodes, classes):
        depth = _depth(nodes, node)
        if depth < OUTLINE_DEPTH:
            outline.append(
                {
                    "row": node["row"],
                    "account": node["name"],
                    "number": node["number"] or None,
                    "level": depth,
                    "group": node["is_group"],
                    "root_type": c["root_type"] or None,
                    "account_type": c["account_type"] or None,
                    **(
                        {"account_category": c["account_category"] or None} if "account_category" in c else {}
                    ),
                    "from": c["source"],
                }
            )
    out = {
        "accounts": len(nodes),
        "groups": sum(1 for n in nodes if n["is_group"]),
        "ledgers": sum(1 for n in nodes if not n["is_group"]),
        "by_root_type": roots,
        "classified_from": sources,
        "outline": outline,
        "unclassified": [
            {"row": n["row"], "account": n["name"], "parent": n["parent_name"] or None}
            for n, c in zip(nodes, classes)
            if not c["root_type"]
        ],
        "problems": problems(nodes),
        "doubtful": doubtful(nodes, classes),
        "parents_not_in_the_file": sorted({n["outside_parent"] for n in nodes if n["outside_parent"]}),
    }
    if classes and "account_category" in classes[0]:
        # v16: the category each ledger gets (ERPNext reads it from ledgers only), and those only their root
        # type's usual category placed, for the user to check
        by_category: Dict[str, int] = {}
        category_from: Dict[str, int] = {}
        to_check = []
        for n, c in zip(nodes, classes):
            if n["is_group"]:
                continue
            if c["account_category"]:
                by_category[c["account_category"]] = by_category.get(c["account_category"], 0) + 1
            category_from[c["category_from"] or "none"] = (
                category_from.get(c["category_from"] or "none", 0) + 1
            )
            if c["category_from"] == "fallback":
                to_check.append(
                    {
                        "row": n["row"],
                        "account": n["name"],
                        "root_type": c["root_type"],
                        "account_category": c["account_category"],
                    }
                )
        out["by_category"] = by_category
        out["category_from"] = category_from
        out["categories_to_check"] = to_check[:CATEGORIES_SHOWN]
        out["categories_to_check_count"] = len(to_check)
        out["categories_not_found"] = categories_not_found(nodes, classes)
    return out


# -- what the company allows (C-D1) ---------------------------------------------------------------------

SUBMITTABLE = (
    "Sales Invoice",
    "Purchase Invoice",
    "Journal Entry",
    "Payment Entry",
    "Stock Entry",
    "Delivery Note",
    "Purchase Receipt",
    "Sales Order",
    "Purchase Order",
    "Stock Reconciliation",
)


def has_transactions(company: str) -> Optional[str]:
    """What stands in the way of replacing the chart: a GL Entry or a submitted document of the company,
    named, or None."""
    if frappe.db.exists("GL Entry", {"company": company, "is_cancelled": 0}):
        return _("{0} has general ledger entries.").format(company)
    for doctype in SUBMITTABLE:
        if frappe.db.exists("DocType", doctype) and frappe.db.exists(
            doctype, {"company": company, "docstatus": 1}
        ):
            return _("{0} has submitted {1}.").format(company, _(doctype))
    return None


def modes(company: str) -> Dict[str, Any]:
    """Which of the three modes the company allows, in the order they are offered (CA-3): map is the
    default when the company has transactions, replace is refused with the reason."""
    blocked = has_transactions(company)
    return {
        "offered": ["map", "add"] + ([] if blocked else ["replace"]),
        "default": "map" if blocked else "add",
        "replace_refused": blocked,
    }


# -- finding the company's accounts --------------------------------------------------------------------


def _existing(company: str, node: Dict[str, Any], c: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """The company's account the node is, by number then by name, or None. With the node's class ``c``,
    only an account of the same kind counts: a group for a group, a ledger for a ledger, of the same root
    type. ERPNext's India chart has a ledger "Reserves and Surplus"; a client's group of that name, with
    accounts under it, isn't that ledger (live, 2026-11-18: add put the client's accounts under the ledger
    and ERPNext refused the whole chart)."""
    same = _same_kind(node, c)
    if node["number"]:
        found = frappe.db.get_value(ACCOUNT, {"company": company, "account_number": node["number"], **same})
        if found:
            return found
    return frappe.db.get_value(ACCOUNT, {"company": company, "account_name": node["name"], **same})


def _same_kind(node: Dict[str, Any], c: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The filters an account of the company must meet to be the node: none without its class."""
    if c is None:
        return {}
    out: Dict[str, Any] = {"is_group": int(node["is_group"])}
    if c.get("root_type"):
        out["root_type"] = c["root_type"]
    return out


def _root_account(company: str, root_type: str) -> Optional[str]:
    return frappe.db.get_value(
        ACCOUNT,
        {"company": company, "root_type": root_type, "is_group": 1, "parent_account": ["is", "not set"]},
    )


def map_proposal(nodes: List[Dict[str, Any]], classes: List[Dict[str, Any]], company: str) -> Dict[str, Any]:
    """For each of the client's accounts, the company's account it is (CA-5): the same name, then the same
    number, then, for a ledger with a type, the one ledger of the company of that account type that no
    other account has been matched to. What matches nothing is listed."""
    matched, unmatched, used = [], [], set()
    for node in nodes:
        # only an account of the same kind (_existing): a client's group isn't the company's ledger
        same = _same_kind(node, classes[node["index"]])
        account = frappe.db.get_value(ACCOUNT, {"company": company, "account_name": node["name"], **same})
        how = "name"
        if not account and node["number"]:
            account = frappe.db.get_value(
                ACCOUNT, {"company": company, "account_number": node["number"], **same}
            )
            how = "number"
        if account:
            used.add(account)
            matched.append({"row": node["row"], "account": node["name"], "matches": account, "how": how})
        else:
            unmatched.append(node)
    still = []
    for node in unmatched:
        c = classes[node["index"]]
        found = []
        if c["account_type"] and not node["is_group"]:
            found = [
                a
                for a in frappe.get_all(
                    ACCOUNT,
                    filters={"company": company, "account_type": c["account_type"], "is_group": 0},
                    pluck="name",
                )
                if a not in used
            ]
        if len(found) == 1:
            used.add(found[0])
            matched.append({"row": node["row"], "account": node["name"], "matches": found[0], "how": "type"})
        else:
            still.append(node)
    return {
        "matched": matched,
        "unmatched": [
            {"row": n["row"], "account": n["name"], "parent": n["parent_name"] or None} for n in still
        ],
    }


def _look(text: Any) -> str:
    """A name with case, punctuation and plural endings left out: "Bank Accounts" and "Bank Account" look alike."""
    words = re.findall(r"[a-z0-9]+", _key(text))
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words)


def add_leaves_beside(
    company: str, nodes: List[Dict[str, Any]], classes: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """What an add keeps of the company's own accounts beside the file's: the ones no account of the file is
    (by name or number), and those that look like one of the file's under another name. Live, 2026-11-19:
    an add on a new company kept ERPNext's 95 accounts, "Bank Accounts" beside the file's "Bank Account",
    and the user then asked for replace."""
    used = set()
    for node in nodes:
        found = _existing(company, node, classes[node["index"]])
        if found:
            used.add(found)
    own = frappe.get_all(
        ACCOUNT, filters={"company": company}, fields=["name", "account_name", "is_group"], order_by="lft"
    )
    kept = [a for a in own if a.name not in used]
    file_looks = {}
    for node in nodes:
        file_looks.setdefault(_look(node["name"]), node["name"])
    look_alikes = []
    for a in kept:
        twin = file_looks.get(_look(a.account_name))
        if twin and _key(twin) != _key(a.account_name):
            look_alikes.append({"company_has": a.account_name, "file_has": twin})
    return {
        "accounts_kept": len(kept),
        "look_alikes": look_alikes[:5],
        "examples": [a.account_name for a in kept if a.is_group][:5],
    }


#: Company default-account fields a chart replace leaves empty, and how to find the account for each: the
#: account types (ledgers), then words in the name
DEFAULT_FIELDS: Tuple[Tuple[str, Tuple[str, ...], str], ...] = (
    ("default_receivable_account", ("Receivable",), r"\b(debtors?|receivables?)\b"),
    ("default_payable_account", ("Payable",), r"\b(creditors?|payables?)\b"),
    ("default_cash_account", ("Cash",), r"\bcash\b"),
    ("default_bank_account", ("Bank",), r"\bbank\b"),
    ("round_off_account", ("Round Off",), r"\bround(ing)?[ -]?off\b|\brounding\b"),
    ("write_off_account", (), r"\bwrite[ -]?off\b"),
    ("exchange_gain_loss_account", (), r"\bexchange (gain|loss)|\bforex\b"),
    ("default_income_account", ("Income Account", "Direct Income"), r"\b(sales|revenue)\b"),
    ("default_expense_account", ("Cost of Goods Sold",), r"\bcost of (goods|sales)\b"),
    ("depreciation_expense_account", ("Depreciation",), r"\bdepreciation\b"),
    ("accumulated_depreciation_account", ("Accumulated Depreciation",), r"\baccumulated depreciation\b"),
    ("stock_received_but_not_billed", ("Stock Received But Not Billed",), r"\breceived but not billed\b"),
    ("default_inventory_account", ("Stock",), r"\b(stock in hand|inventory)\b"),
    ("stock_adjustment_account", ("Stock Adjustment",), r"\bstock adjustment\b"),
)


def default_proposals(company: str) -> List[Dict[str, Any]]:
    """For each empty default-account field of the company that a chart usually has an account for, the
    ledgers that fit (its account types first, then words in the name), the likeliest first. After a replace
    (live: "the default account settings are now empty") FACO puts them on one card for the user to pick."""
    meta = frappe.get_meta("Company")
    ledgers = frappe.get_all(
        ACCOUNT,
        filters={"company": company, "is_group": 0, "disabled": 0},
        fields=["name", "account_name", "account_type", "root_type"],
        order_by="lft",
    )
    out = []
    for field, types, words in DEFAULT_FIELDS:
        df = meta.get_field(field)
        if not df or frappe.db.get_value("Company", company, field):
            continue
        by_type = [a.name for a in ledgers if a.account_type in types]
        by_name = [
            a.name for a in ledgers if re.search(words, _key(a.account_name)) and a.name not in by_type
        ]
        choices = (by_type + by_name)[:5]
        out.append(
            {
                "field": field,
                "label": _(df.label),
                "suggested": choices[0] if choices else None,
                "choices": choices,
            }
        )
    return out


# -- add and map ---------------------------------------------------------------------------------------


def _order(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parents before children, level by level (CA-6)."""
    return sorted(nodes, key=lambda n: (_depth(nodes, n), n["index"]))


def _report_type(root_type: str) -> str:
    return "Balance Sheet" if root_type in ("Asset", "Liability", "Equity") else "Profit and Loss"


def _insert(company: str, node: Dict[str, Any], c: Dict[str, Any], parent: Optional[str]) -> str:
    """Create the node's account under ``parent``; with no parent, as the company's root account of its
    root type, the way ERPNext's chart code creates a root (create_charts: Parent Account is mandatory on
    an Account, so a root is inserted without the mandatory check, with its root and report type set)."""
    doc = frappe.get_doc(
        {
            "doctype": ACCOUNT,
            "company": company,
            "account_name": node["name"],
            "account_number": node["number"] or None,
            "parent_account": parent,
            "is_group": int(node["is_group"]),
            "root_type": c["root_type"],
            "report_type": _report_type(c["root_type"]),
            "account_type": c["account_type"] or None,
            **({"account_category": c["account_category"]} if c.get("account_category") else {}),
        }
    )
    if parent is None:
        doc.flags.ignore_mandatory = True
    try:
        doc.insert()
    except frappe.DuplicateEntryError as e:
        # the company has an account of this name of another kind (_existing), and the file gives no number
        # to tell them apart: ERPNext names an account "<number> - <name> - <abbr>"
        raise ChartProblem(
            _(
                "{0} already has an account named {1} that isn't the file's {1} (a group in one, a ledger in "
                "the other, or another root type). Give the file's {1} an account number or another name."
            ).format(company, node["name"])
        ) from e
    return doc.name


def missing_roots(company: str, nodes, classes) -> List[str]:
    """The root types the file's top accounts have that the company has no root account of: add creates
    those top accounts as the company's roots. ERPNext's "India - Chart of Accounts" has no Equity root
    (live, 2026-11-18: a client's Equity accounts had nowhere to go, and the chat put them under
    Liabilities by hand)."""
    wanted = sorted(
        {classes[n["index"]]["root_type"] for n in nodes if n["parent"] is None and not n["outside_parent"]}
        - {None, ""}
    )
    return [root_type for root_type in wanted if not _root_account(company, root_type)]


def _parent_for(company, nodes, node, c, placed) -> Optional[str]:
    """The account a node goes under: its parent's account (made or found), the company account the file's
    outside parent names, or the company's root account of its root type. None when the company has no
    root of that type and the node is a top group of the file: it becomes that root."""
    if node["parent"] is not None:
        if node["parent"] not in placed:
            raise ChartProblem(
                _("{0}: its parent {1} wasn't placed.").format(node["name"], node["parent_name"])
            )
        return placed[node["parent"]]
    if node["outside_parent"]:
        found = frappe.db.get_value(
            ACCOUNT, {"company": company, "account_name": node["outside_parent"], "is_group": 1}
        ) or frappe.db.get_value(
            ACCOUNT, {"company": company, "account_number": node["outside_parent"], "is_group": 1}
        )
        if not found:
            raise ChartProblem(
                _("{0}: its parent {1} isn't a group account of {2}.").format(
                    node["name"], node["outside_parent"], company
                )
            )
        return found
    root = _root_account(company, c["root_type"])
    if root:
        return root
    if node["is_group"]:
        return None
    raise ChartProblem(
        _(
            "{0} has no top-level {1} account, and {2} is a ledger: the top account of a type must be a "
            "group. Put {2} under a group of the file."
        ).format(company, _(c["root_type"]), node["name"])
    )


@contextmanager
def _tree_built_once():
    """Insert accounts without ERPNext updating the account tree's nested set after each one, then rebuild
    it once, as ERPNext's own chart code does (create_charts). Each update rewrites the tree: a client's
    1,043 accounts took 115 minutes to add one by one (live test, 2026-11-19), far past what a chat waits."""
    from frappe.utils.nestedset import rebuild_tree

    frappe.local.flags.ignore_update_nsm = True
    try:
        yield
    finally:
        frappe.local.flags.ignore_update_nsm = False
    rebuild_tree(ACCOUNT)


def add(company, nodes, classes, only: Optional[set] = None) -> Dict[str, Any]:
    """Put the accounts on the company under the right parents, parents first (C-D1 add). An account the
    company has already (by number or name) is kept as it is. ``only``: node indexes to add, the rest
    are matched. Returns the account each node is, and what was created."""
    placed: Dict[int, str] = {}
    created: List[str] = []
    with _tree_built_once():
        for node in _order(nodes):
            existing = _existing(company, node, classes[node["index"]])
            if existing:
                placed[node["index"]] = existing
                continue
            if only is not None and node["index"] not in only:
                continue
            c = classes[node["index"]]
            placed[node["index"]] = _insert(company, node, c, _parent_for(company, nodes, node, c, placed))
            created.append(placed[node["index"]])
    return {"accounts": placed, "created": created}


def keep_old_ids(
    session_name: Optional[str], system: str, nodes, accounts: Dict[int, str]
) -> Dict[str, List[str]]:
    """Keep the client's account number and name as the old IDs of the accounts they are (C-D5), so the
    opening trial balance resolves by them. Returns ``written``, ``conflicts`` and the ``systems`` used.

    A second company of the same client names its accounts as the first does, and an old ID names one
    record per system: those of this company are kept under a system of its own, "<system> <abbr>". The
    trial balance looks in every system for an account of its company (_by_client_id)."""
    system = import_keys.system_name(system)
    pairs = []
    for index, account in accounts.items():
        node = nodes[index]
        if node["number"]:
            pairs.append((node["number"], account))
        pairs.append((node["name"], account))
    kept = _keep(session_name, system, pairs)
    kept["systems"] = [system] if kept["written"] else []
    if not kept["conflicts"] or not accounts:
        return kept
    company = frappe.db.get_value(ACCOUNT, next(iter(accounts.values())), "company")
    owners = import_keys.resolve(ACCOUNT, system, kept["conflicts"], user="Administrator")
    elsewhere = {
        key
        for key, name in owners.items()
        if name and frappe.db.get_value(ACCOUNT, name, "company") != company
    }
    if not elsewhere:
        return kept
    own = import_keys.system_name(f"{system} {frappe.get_cached_value('Company', company, 'abbr')}")
    again = _keep(session_name, own, [(k, a) for k, a in pairs if import_keys.normalise(k) in elsewhere])
    kept["written"] += again["written"]
    kept["conflicts"] = [k for k in kept["conflicts"] if k not in elsewhere] + again["conflicts"]
    if again["written"]:
        kept["systems"].append(own)
    return kept


def _keep(session_name: Optional[str], system: str, pairs) -> Dict[str, List[str]]:
    if not import_keys.choice(ACCOUNT, system):
        import_keys.set_choice(ACCOUNT, system, "key_map")
    return import_keys.record_pairs(session_name, ACCOUNT, system, pairs)


def apply_map(company, nodes, classes, add_unmatched: bool = False) -> Dict[str, Any]:
    """Map mode: the client's accounts that match the company's become those accounts (kept as old IDs, no
    account is created). With ``add_unmatched`` the others are added under their parents' accounts."""
    proposal = map_proposal(nodes, classes, company)
    by_row = {n["row"]: n for n in nodes}
    accounts = {by_row[m["row"]]["index"]: m["matches"] for m in proposal["matched"]}
    created: List[str] = []
    if add_unmatched and proposal["unmatched"]:
        left = {by_row[u["row"]]["index"] for u in proposal["unmatched"]}
        with _tree_built_once():
            for node in _order(nodes):
                if node["index"] not in left:
                    continue
                c = classes[node["index"]]
                parent = (
                    accounts.get(node["parent"]) if node["parent"] is not None else None
                ) or _parent_for(company, nodes, node, c, accounts)
                accounts[node["index"]] = _insert(company, node, c, parent)
                created.append(accounts[node["index"]])
        proposal["unmatched"] = []
    return {"accounts": accounts, "created": created, **proposal}


# -- replace ---------------------------------------------------------------------------------------------


def cash_links(company: str) -> List[Dict[str, str]]:
    """The modes of payment's rows for ``company`` that use its default cash account. ERPNext adds one to
    every new company (Company.set_mode_of_payment_account, v15 and v16), so a fresh company always has
    it. They don't block a replace: the cash account has a place in any chart, the new chart's cash ledger,
    so the replace moves them there. A row on any other account still blocks: where it should go is the
    user's call."""
    account = frappe.db.get_value("Company", company, "default_cash_account")
    if not account:
        return []
    return frappe.get_all(
        "Mode of Payment Account",
        filters={"parenttype": "Mode of Payment", "company": company, "default_account": account},
        fields=["name", "parent"],
    )


def _relink_cash(company: str, links: List[Dict[str, str]]) -> Optional[str]:
    """Point the modes of payment that used the old cash account at the new chart's default cash account;
    None, and they keep no account for the company, when the client's chart has no cash ledger."""
    account = frappe.db.get_value("Company", company, "default_cash_account")
    if not account:
        return None
    for mode_name in sorted({link["parent"] for link in links}):
        mode = frappe.get_doc("Mode of Payment", mode_name, for_update=True)
        mode.append("accounts", {"company": company, "default_account": account})
        mode.save(ignore_permissions=True)  # as ERPNext saves it for every new company
    return account


#: The company's tax setup, as ERPNext and India Compliance make it for every new company on its standard
#: chart (an Indian company: 4 sales, 4 purchase and 7 item tax templates, a row in each of 127 tax
#: withholding categories and its GST Settings accounts): records of the company's own, made for the chart
#: a replace deletes. Live, 2026-11-18, they blocked the replace of every Indian company, and clearing them
#: in chat took 127 approvals and still failed.
TAX_TEMPLATES = (
    ("Sales Taxes and Charges Template", "Sales Taxes and Charges", "account_head"),
    ("Purchase Taxes and Charges Template", "Purchase Taxes and Charges", "account_head"),
    ("Item Tax Template", "Item Tax Template Detail", "tax_type"),
)
#: Shared records that hold one row per company: only the company's rows go.
TAX_ROWS = (
    ("Tax Withholding Category", "Tax Withholding Account"),
    ("GST Settings", "GST Account"),
)


def tax_setup(company: str) -> Dict[str, Any]:
    """The company's tax setup a replace removes with its chart: ``templates`` by DocType, ``rows`` (the
    company's rows of shared records) by the record's DocType, and ``row_names``, every child row of
    them, which the check for other references leaves out."""
    templates: Dict[str, List[str]] = {}
    rows: Dict[str, List[str]] = {}
    row_names: set = set()
    for doctype, child, _field in TAX_TEMPLATES:
        if not frappe.db.exists("DocType", doctype):
            continue
        names = frappe.get_all(doctype, filters={"company": company}, pluck="name")
        if names:
            templates[doctype] = names
            row_names.update(
                frappe.get_all(child, filters={"parenttype": doctype, "parent": ["in", names]}, pluck="name")
            )
    for parenttype, child in TAX_ROWS:
        if not frappe.db.exists("DocType", child):
            continue
        names = frappe.get_all(child, filters={"parenttype": parenttype, "company": company}, pluck="name")
        if names:
            rows[parenttype] = names
            row_names.update(names)
    return {"templates": templates, "rows": rows, "row_names": row_names}


def tax_setup_counts(setup: Dict[str, Any]) -> Dict[str, int]:
    """What the approval card of a replace shows of the tax setup it removes, in words."""
    labels = {
        "Sales Taxes and Charges Template": _("Sales tax templates"),
        "Purchase Taxes and Charges Template": _("Purchase tax templates"),
        "Item Tax Template": _("Item tax templates"),
        "Tax Withholding Category": _("Tax withholding category rows of the company"),
        "GST Settings": _("GST Settings account rows of the company"),
    }
    out = {labels[d]: len(n) for d, n in setup["templates"].items()}
    out.update({labels[d]: len(n) for d, n in setup["rows"].items()})
    return out


def _clear_tax_setup(company: str, setup: Dict[str, Any]) -> Dict[str, int]:
    """Remove the company's tax setup (tax_setup) before its accounts go. A template is deleted as the
    user, with ERPNext's link check: one an item, a customer or a tax rule uses is the user's setup in
    use, and the replace stops there, all of it rolled back. The company's rows of the shared records
    go; the records stay, with the other companies' rows."""
    for doctype, names in setup["templates"].items():
        for name in names:
            try:
                frappe.delete_doc(doctype, name)
            except frappe.LinkExistsError as e:
                raise ChartProblem(
                    _(
                        "{0} {1} is in use, so it isn't only the company's starting setup: {2} Change what "
                        "uses it, or add instead. Nothing was changed."
                    ).format(_(doctype), name, _text(e))
                ) from e
    for parenttype, names in setup["rows"].items():
        child = dict(TAX_ROWS)[parenttype]
        frappe.db.delete(child, {"name": ["in", names]})
        if frappe.get_meta(parenttype).issingle:
            frappe.clear_document_cache(parenttype, parenttype)
    return tax_setup_counts(setup)


def _text(e: Exception) -> str:
    return frappe.utils.strip_html(str(e)).strip()


def blocking_references(company: str) -> List[str]:
    """What outside the chart points at the company's accounts, so replacing it would break it (C-D2): a
    draft document's row, a mode of payment's, a warehouse's or any other record's account. The company's
    own tax setup is not one of them (tax_setup): the replace removes it, with the user's approval of its
    counts. Nor is a mode of payment's row on the company's default cash account (cash_links)."""
    accounts = set(frappe.get_all(ACCOUNT, filters={"company": company}, pluck="name"))
    moved = {link["name"] for link in cash_links(company)} | tax_setup(company)["row_names"]
    out: List[str] = []
    reported: set = set()

    def rows(child: str, parent_doctype: str, field: str, label: str, extra: Optional[Dict] = None) -> None:
        if not frappe.db.exists("DocType", child):
            return
        meta = frappe.get_meta(child)
        if not meta.has_field(field):
            return
        found = frappe.get_all(
            child,
            filters={field: ["in", list(accounts)] if accounts else [""], **(extra or {})},
            fields=["name", "parent", field],
            limit=500,
        )
        for row in found:
            if row.name in moved:
                continue
            reported.add(row.name)
            out.append(_("{0} {1} uses {2}.").format(_(label), row.parent, row[field]))

    rows(
        "Sales Taxes and Charges",
        "Sales Taxes and Charges Template",
        "account_head",
        "Sales tax template",
        {"parenttype": "Sales Taxes and Charges Template"},
    )
    rows(
        "Purchase Taxes and Charges",
        "Purchase Taxes and Charges Template",
        "account_head",
        "Purchase tax template",
        {"parenttype": "Purchase Taxes and Charges Template"},
    )
    rows("Item Tax Template Detail", "Item Tax Template", "tax_type", "Item tax template")
    rows(
        "Mode of Payment Account",
        "Mode of Payment",
        "default_account",
        "Mode of payment",
        {"company": company},
    )
    if compat.has_india_compliance():
        rows("GST Account", "GST Settings", "cgst_account", "GST Settings", {"company": company})
        rows("GST Account", "GST Settings", "sgst_account", "GST Settings", {"company": company})
        rows("GST Account", "GST Settings", "igst_account", "GST Settings", {"company": company})
    out.extend(_other_links(company, accounts, moved | reported))
    return out


def _other_links(company: str, accounts: set, skip: set) -> List[str]:
    """Every other record that links to one of the company's accounts: the check ERPNext's delete makes for
    each account (frappe.model.delete_doc.get_linked_docs and get_dynamic_linked_docs), made once for the
    whole chart, so the replace can delete without it. The company's own account fields are cleared by
    the replace, the chart's accounts go with it, and ``skip`` holds the rows already named or moved. A
    record the user may not read is named by its doctype only."""
    from frappe.model.dynamic_links import get_dynamic_link_map
    from frappe.model.rename_doc import get_link_fields

    if not accounts:
        return []
    names = list(accounts)
    ignored = set(frappe.get_hooks("ignore_links_on_delete"))
    out: List[str] = []

    def found(doctype: str, name: str, account: str) -> None:
        if (doctype == "Company" and name == company) or (doctype == ACCOUNT and name in accounts):
            return
        try:
            readable = frappe.has_permission(doctype, "read", doc=name)
        except frappe.DoesNotExistError:  # a row whose parent is gone
            readable = False
        if not readable:
            out.append(_("A {0} you can't open uses {1}.").format(_(doctype), account))
            return
        out.append(_("{0} {1} uses {2}.").format(_(doctype), name, account))

    for link in get_link_fields(ACCOUNT):
        doctype, field = link["parent"], link["fieldname"]
        if doctype in ignored or not frappe.db.exists("DocType", doctype):
            continue
        if frappe.get_meta(doctype).is_virtual:
            continue
        if link["issingle"]:
            value = frappe.db.get_single_value(doctype, field)
            if value in accounts:
                found(doctype, doctype, value)
            continue
        table = frappe.get_meta(doctype).istable
        for row in frappe.get_all(
            doctype,
            filters={field: ["in", names]},
            fields=["name", field, *(["parent", "parenttype"] if table else [])],
            limit=20,
        ):
            if row.get("name") in skip or (table and row.parenttype in ignored):
                continue
            found(row.parenttype if table else doctype, row.parent if table else row.name, row[field])
    for df in get_dynamic_link_map().get(ACCOUNT, []):
        if df.parent in ignored or frappe.get_meta(df.parent).issingle:
            continue
        for row in frappe.get_all(
            df.parent,
            filters={df.options: ACCOUNT, df.fieldname: ["in", names]},
            fields=["name", df.fieldname],
            limit=20,
        ):
            found(df.parent, row.name, row[df.fieldname])
    return out


def _company_account_fields() -> List[str]:
    return [
        df.fieldname
        for df in frappe.get_meta("Company").fields
        if df.fieldtype == "Link" and df.options == ACCOUNT
    ]


def defaults_left_empty(company: str) -> List[str]:
    """The company's default-account fields that hold no account."""
    return [f for f in _company_account_fields() if not frappe.db.get_value("Company", company, f)]


def already_in_place(company: str, nodes) -> bool:
    """The company's chart is the file's already: as many accounts, and each of the file's (number,
    name) once. A replace the chat called again after the first had finished (live, 2026-11-18)
    would otherwise delete the accounts it just made and make them again."""
    accounts = frappe.get_all(
        ACCOUNT, filters={"company": company}, fields=["account_name", "account_number"]
    )
    if len(accounts) != len(nodes):
        return False
    have = sorted((_key(a.account_number), _key(a.account_name)) for a in accounts)
    return have == sorted((_key(n["number"]), _key(n["name"])) for n in nodes)


def forest(nodes: List[Dict[str, Any]], classes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The tree as ERPNext's create_charts takes it: nested by account name, a node's own keys beside its
    children. Raises ChartProblem for a root account that has no root type. Each node carries its own
    account_name (create_charts takes it from there for an imported chart), so two siblings of one name,
    told apart by their numbers, get keys of their own instead of one replacing the other."""

    def key(index: int, taken: set) -> str:
        node = nodes[index]
        name = node["name"]
        if name in taken or name in compat.CHART_NODE_KEYS:
            name = f"{node['name']} ({node['number'] or node['row']})"
        taken.add(name)
        return name

    def build(index: int) -> Dict[str, Any]:
        node, c = nodes[index], classes[index]
        out: Dict[str, Any] = {"account_name": node["name"]}
        if node["is_group"]:
            out["is_group"] = 1
        if node["number"]:
            out["account_number"] = node["number"]
        if c["root_type"]:
            out["root_type"] = c["root_type"]
        if c["account_type"]:
            out["account_type"] = c["account_type"]
        if c.get("account_category"):
            out["account_category"] = c["account_category"]  # v16 only: classify sets it there only
        taken: set = set()
        for child in node["children"]:
            out[key(child, taken)] = build(child)
        return out

    roots = [n for n in nodes if n["parent"] is None]
    for root in roots:
        if root["outside_parent"]:
            raise ChartProblem(
                _(
                    "{0} is under {1}, which isn't in the file: a replaced chart has to hold all its accounts."
                ).format(root["name"], root["outside_parent"])
            )
        if not classes[root["index"]]["root_type"]:
            raise ChartProblem(_("{0} has no root type.").format(root["name"]))
        if not root["is_group"]:
            raise ChartProblem(
                _("{0} is at the top of the chart, so it must be a group.").format(root["name"])
            )
    taken: set = set()
    return {key(root["index"], taken): build(root["index"]) for root in roots}


def replace_figures(company: str, nodes) -> Dict[str, Any]:
    """What the approval card of a replace shows: the accounts removed and created, and how many records
    of the company's tax setup go with them (tax_setup_removed, by kind in tax_setup)."""
    counts = tax_setup_counts(tax_setup(company))
    return {
        "company": company,
        "accounts_removed": frappe.db.count(ACCOUNT, {"company": company}),
        "accounts_created": len(nodes),
        "tax_setup_removed": sum(counts.values()),
        "tax_setup": counts,
    }


def replace_problem(company: str) -> Optional[str]:
    """Why the chart of ``company`` can't be replaced, or None: it has transactions, something outside
    the chart points at its accounts, or the user may not create and delete accounts (C-D2)."""
    blocked = has_transactions(company)
    if blocked:
        return _("{0} Replace is only for a company with no transactions: map or add instead.").format(
            blocked
        )
    first = frappe.db.get_value(ACCOUNT, {"company": company})
    doc = frappe.get_doc(ACCOUNT, first) if first else None
    if not frappe.has_permission(ACCOUNT, "create") or (
        doc and not frappe.has_permission(ACCOUNT, "delete", doc=doc)
    ):
        # before the references: who may not replace the chart isn't told what points at it
        return _("You need to be allowed to create and delete accounts of {0} (Accounts Manager).").format(
            company
        )
    setup = tax_setup(company)
    for doctype in setup["templates"]:
        if not frappe.has_permission(doctype, "delete"):
            return _(
                "Replacing the chart removes the company's {0}: you need to be allowed to delete them."
            ).format(_(doctype))
    for parenttype in setup["rows"]:
        if not frappe.has_permission(parenttype, "write"):
            return _(
                "Replacing the chart removes the company's rows of {0}: you need to be allowed to change it."
            ).format(_(parenttype))
    refs = blocking_references(company)
    if refs:
        shown = "; ".join(refs[:10]) + (
            " " + _("and {0} more").format(len(refs) - 10) if len(refs) > 10 else ""
        )
        return _(
            "Replacing the chart would break what points at its accounts: {0}. Remove them, or add instead."
        ).format(shown)
    return None


def replace(company: str, nodes, classes) -> Dict[str, Any]:
    """Replace the company's chart with the client's (C-D2): the company's default accounts are cleared, its
    accounts deleted leaves first as the user, the new chart created through ERPNext's own chart code, and
    the defaults set again. All or nothing: a failure puts the old chart back. Returns the counts and the
    defaults the new chart left empty."""
    problem = replace_problem(company)
    if problem:
        raise ChartProblem(problem)
    tree = forest(nodes, classes)  # before anything is deleted
    removed = frappe.db.count(ACCOUNT, {"company": company})
    setup = tax_setup(company)
    frappe.db.savepoint("fac_chart_replace")
    try:
        # made for the chart that goes: removed first, so nothing is left on a deleted account
        tax_removed = _clear_tax_setup(company, setup)
        # the rows on the old cash account, read before the defaults are cleared, follow it to the new chart
        moved = cash_links(company)
        if moved:
            frappe.db.delete("Mode of Payment Account", {"name": ["in", [link["name"] for link in moved]]})
        fields = _company_account_fields()
        frappe.db.set_value("Company", company, {f: None for f in fields}, update_modified=False)
        existing = frappe.get_all(ACCOUNT, filters={"company": company}, fields=["name", "parent_account"])
        children: Dict[Optional[str], List[str]] = {}
        for row in existing:
            children.setdefault(row.parent_account or None, []).append(row.name)

        def delete_below(name: str) -> None:
            for child in children.get(name, []):
                delete_below(child)
            # replace_problem made ERPNext's link check for the whole chart (_other_links): repeated per
            # account it takes minutes on a full chart, past what a chat waits for a tool
            frappe.delete_doc(ACCOUNT, name, force=True)

        for root in children.get(None, []):
            delete_below(root)
        compat.create_charts(company, tree)
        made = frappe.db.count(ACCOUNT, {"company": company})
        if made != len(nodes):
            # The approval card said how many; fewer, and the chart isn't the client's
            raise ChartProblem(
                _("The chart would have {0} accounts, not the {1} in the file. Nothing was changed.").format(
                    made, len(nodes)
                )
            )
        company_doc = frappe.get_doc("Company", company)
        company_doc.update_default_account = True  # a flag ERPNext sets while validating a company
        company_doc.set_default_accounts()
        for field, account_type in (
            ("default_receivable_account", "Receivable"),
            ("default_payable_account", "Payable"),
        ):
            # ERPNext sets these from its own chart's names: here, the one ledger of that type, if there is one
            found = frappe.get_all(
                ACCOUNT,
                filters={"company": company, "account_type": account_type, "is_group": 0},
                pluck="name",
            )
            if len(found) == 1:
                frappe.db.set_value("Company", company, field, found[0], update_modified=False)
        cash_account = _relink_cash(company, moved) if moved else None
        empty = defaults_left_empty(company)
    except Exception:
        frappe.db.rollback(save_point="fac_chart_replace")
        raise
    created = frappe.db.count(ACCOUNT, {"company": company})
    out = {"company": company, "removed": removed, "created": created, "defaults_left_empty": empty}
    if tax_removed:
        # set up again on the new chart's own tax accounts: which ones is the user's call
        out["tax_setup_removed"] = tax_removed
    if moved:
        # the account the modes of payment now use for this company: the new chart's cash ledger, or none
        out["cash_mode_of_payment_account"] = cash_account
    return out
