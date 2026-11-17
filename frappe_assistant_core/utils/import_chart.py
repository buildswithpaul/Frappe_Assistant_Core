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


def read_chart(session, root_type_column: Optional[str] = None) -> List[Dict[str, Any]]:
    """The accounts of the session's file as nodes, in file order. Raises ChartProblem when the file
    isn't a chart (no column mapped to Account Name) or has too many accounts. Root Type is read-only on
    Account, so a column that holds it can't be mapped: ``root_type_column`` names it by its heading."""
    mapping = {
        field: int(position)
        for position, field in dry_run.column_to_field_map(session).items()
        if str(position).isdigit() and field and field != "Don't Import"
    }
    if "account_name" not in mapping:
        raise ChartProblem(_("Map a column to Account Name first (set_column_mapping, DocType Account)."))
    if root_type_column:
        from frappe_assistant_core.utils.import_mapping import session_headers

        wanted = _key(root_type_column)
        found = next((i for i, h in enumerate(session_headers(session)) if _key(h) == wanted), None)
        if found is None:
            raise ChartProblem(_("The file has no column {0}.").format(root_type_column))
        mapping["root_type"] = found
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
                "number": cell(row, "account_number"),
                "parent_name": cell(row, "parent_account"),
                "root_type": cell(row, "root_type"),
                "account_type": cell(row, "account_type"),
                "explicit_group": _truthy(cell(row, "is_group")),
            }
        )
    if len(nodes) > MAX_ACCOUNTS:
        raise ChartProblem(_("A chart has at most {0} accounts.").format(MAX_ACCOUNTS))
    if not nodes:
        raise ChartProblem(_("The file has no accounts."))
    _link(nodes)
    return nodes


def _link(nodes: List[Dict[str, Any]]) -> None:
    """Give each node its parent (by name, else by number), its children and whether it is a group."""
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
        found = by_name.get(_key(wanted)) or ([by_number[_key(wanted)]] if _key(wanted) in by_number else [])
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
        seen: Dict[str, Dict[str, Any]] = {}
        for node in nodes:
            value = _key(node[key])
            if not value:
                continue
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

    return [{**resolve(node), "index": node["index"]} for node in nodes]


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
                    "from": c["source"],
                }
            )
    return {
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
        "parents_not_in_the_file": sorted({n["outside_parent"] for n in nodes if n["outside_parent"]}),
    }


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


def _existing(company: str, node: Dict[str, Any]) -> Optional[str]:
    """The company's account the node is, by number then by name, or None."""
    if node["number"]:
        found = frappe.db.get_value(ACCOUNT, {"company": company, "account_number": node["number"]})
        if found:
            return found
    return frappe.db.get_value(ACCOUNT, {"company": company, "account_name": node["name"]})


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
        account = frappe.db.get_value(ACCOUNT, {"company": company, "account_name": node["name"]})
        how = "name"
        if not account and node["number"]:
            account = frappe.db.get_value(ACCOUNT, {"company": company, "account_number": node["number"]})
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


# -- add and map ---------------------------------------------------------------------------------------


def _order(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parents before children, level by level (CA-6)."""
    return sorted(nodes, key=lambda n: (_depth(nodes, n), n["index"]))


def _insert(company: str, node: Dict[str, Any], c: Dict[str, Any], parent: str) -> str:
    doc = frappe.get_doc(
        {
            "doctype": ACCOUNT,
            "company": company,
            "account_name": node["name"],
            "account_number": node["number"] or None,
            "parent_account": parent,
            "is_group": int(node["is_group"]),
            "root_type": c["root_type"],
            "account_type": c["account_type"] or None,
        }
    )
    doc.insert()
    return doc.name


def _parent_for(company, nodes, node, c, placed) -> str:
    """The account a node goes under: its parent's account (made or found), the company account the file's
    outside parent names, or the company's root account of its root type."""
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
    if not root:
        raise ChartProblem(_("{0} has no root account for {1}.").format(company, c["root_type"]))
    return root


def add(company, nodes, classes, only: Optional[set] = None) -> Dict[str, Any]:
    """Put the accounts on the company under the right parents, parents first (C-D1 add). An account the
    company has already (by number or name) is kept as it is. ``only``: node indexes to add, the rest
    are matched. Returns the account each node is, and what was created."""
    placed: Dict[int, str] = {}
    created: List[str] = []
    for node in _order(nodes):
        existing = _existing(company, node)
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
        for node in _order(nodes):
            if node["index"] not in left:
                continue
            c = classes[node["index"]]
            parent = (accounts.get(node["parent"]) if node["parent"] is not None else None) or _parent_for(
                company, nodes, node, c, accounts
            )
            accounts[node["index"]] = _insert(company, node, c, parent)
            created.append(accounts[node["index"]])
        proposal["unmatched"] = []
    return {"accounts": accounts, "created": created, **proposal}


# -- replace ---------------------------------------------------------------------------------------------


def blocking_references(company: str) -> List[str]:
    """What outside the chart points at the company's accounts, so replacing it would break it (C-D2): tax
    templates, item tax templates, modes of payment and, with India Compliance, GST Settings accounts."""
    accounts = set(frappe.get_all(ACCOUNT, filters={"company": company}, pluck="name"))
    out: List[str] = []

    def rows(child: str, parent_doctype: str, field: str, label: str, extra: Optional[Dict] = None) -> None:
        if not frappe.db.exists("DocType", child):
            return
        meta = frappe.get_meta(child)
        if not meta.has_field(field):
            return
        found = frappe.get_all(
            child,
            filters={field: ["in", list(accounts)] if accounts else [""], **(extra or {})},
            fields=["parent", field],
            limit=500,
        )
        for row in found:
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
    return out


def _company_account_fields() -> List[str]:
    return [
        df.fieldname
        for df in frappe.get_meta("Company").fields
        if df.fieldtype == "Link" and df.options == ACCOUNT
    ]


def forest(nodes: List[Dict[str, Any]], classes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The tree as ERPNext's create_charts takes it: nested by account name, a node's own keys beside its
    children. Raises ChartProblem for a root account that has no root type."""

    def build(index: int) -> Dict[str, Any]:
        node, c = nodes[index], classes[index]
        out: Dict[str, Any] = {}
        if node["is_group"]:
            out["is_group"] = 1
        if node["number"]:
            out["account_number"] = node["number"]
        if c["root_type"]:
            out["root_type"] = c["root_type"]
        if c["account_type"]:
            out["account_type"] = c["account_type"]
        for child in node["children"]:
            out[nodes[child]["name"]] = build(child)
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
    return {root["name"]: build(root["index"]) for root in roots}


def replace_figures(company: str, nodes) -> Dict[str, Any]:
    """What the approval card of a replace shows: the accounts removed and created."""
    return {
        "company": company,
        "accounts_removed": frappe.db.count(ACCOUNT, {"company": company}),
        "accounts_created": len(nodes),
    }


def replace_problem(company: str) -> Optional[str]:
    """Why the chart of ``company`` can't be replaced, or None: it has transactions, something outside
    the chart points at its accounts, or the user may not create and delete accounts (C-D2)."""
    blocked = has_transactions(company)
    if blocked:
        return _("{0} Replace is only for a company with no transactions: map or add instead.").format(
            blocked
        )
    refs = blocking_references(company)
    if refs:
        shown = "; ".join(refs[:10]) + (
            " " + _("and {0} more").format(len(refs) - 10) if len(refs) > 10 else ""
        )
        return _(
            "Replacing the chart would break what points at its accounts: {0}. Remove them, or add instead."
        ).format(shown)
    first = frappe.db.get_value(ACCOUNT, {"company": company})
    doc = frappe.get_doc(ACCOUNT, first) if first else None
    if not frappe.has_permission(ACCOUNT, "create") or (
        doc and not frappe.has_permission(ACCOUNT, "delete", doc=doc)
    ):
        return _("You need to be allowed to create and delete accounts of {0} (Accounts Manager).").format(
            company
        )
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
    frappe.db.savepoint("fac_chart_replace")
    try:
        fields = _company_account_fields()
        frappe.db.set_value("Company", company, {f: None for f in fields}, update_modified=False)
        existing = frappe.get_all(ACCOUNT, filters={"company": company}, fields=["name", "parent_account"])
        children: Dict[Optional[str], List[str]] = {}
        for row in existing:
            children.setdefault(row.parent_account or None, []).append(row.name)

        def delete_below(name: str) -> None:
            for child in children.get(name, []):
                delete_below(child)
            frappe.delete_doc(ACCOUNT, name)

        for root in children.get(None, []):
            delete_below(root)
        compat.create_charts(company, tree)
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
        empty = [f for f in fields if not frappe.db.get_value("Company", company, f)]
    except Exception:
        frappe.db.rollback(save_point="fac_chart_replace")
        raise
    created = frappe.db.count(ACCOUNT, {"company": company})
    return {"company": company, "removed": removed, "created": created, "defaults_left_empty": empty}
