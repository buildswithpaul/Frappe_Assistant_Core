# frappe_assistant_core/utils/import_opening_balances.py
# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Opening account balances (#33998): the old system's closing trial balance becomes one opening
Journal Entry (voucher type Opening Entry) at the cut-off date, with the file's balance checked
first. Receivable, Payable and Stock accounts are left to the opening invoices and opening stock
imports; one balancing line to the Temporary Opening account keeps the entry balanced.

It is the third special engine, after opening stock and opening invoices: the dry run reaches it
through ``import_dry_run.special_engine``. An opening-balances session keeps its settings in
``template_options.opening_balances``. This module holds the setup and its pre-checks; the row
checks, creation and a first report are here; the full report follows.
"""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

import frappe
from frappe import _
from frappe.utils import cstr, flt, getdate

from frappe_assistant_core.utils import import_opening_invoices as opening_invoices
from frappe_assistant_core.utils import import_opening_stock as opening_stock
from frappe_assistant_core.utils.import_mapping import save_mapping, session_headers
from frappe_assistant_core.utils.import_session import read_sheet_rows, readable_session_file

TARGET = "Journal Entry"
VOUCHER_TYPE = "Opening Entry"
IMPORT_TOOL = "import_opening_balances"
ACCOUNT_TABLE = "accounts"
FIELDS = ("account", "debit", "credit", "balance")
REQUIRED_FIELDS = ("account",)
MAPPED = {
    "account": "accounts.account",
    "debit": "accounts.debit_in_account_currency",
    "credit": "accounts.credit_in_account_currency",
}
PL_MODES = ("stop", "retained_earnings")
COVERED_TYPES = ("Receivable", "Payable", "Stock")  # left to the opening invoices / stock imports


def covered_types(company: str) -> tuple:
    """The account types the other opening imports bring in, so left out of the entry. Stock only
    with perpetual inventory: without it, opening stock posts no ledger entry, so the stock
    account's balance comes in with this entry (ERPNext then accepts a stock account in it)."""
    import erpnext

    if erpnext.is_perpetual_inventory_enabled(company):
        return COVERED_TYPES
    return tuple(t for t in COVERED_TYPES if t != "Stock")


class OpeningBalancesProblem(Exception):
    """Opening balances can't be set up, checked or created. The message is shown to the user."""


def settings(session) -> Dict[str, Any]:
    options = frappe.parse_json(session.template_options or "{}") or {}
    return dict(options.get("opening_balances") or {})


def is_opening_balances(session) -> bool:
    return bool(settings(session))


def temporary_account(company: str) -> Optional[str]:
    return opening_invoices.temporary_account(company)


def setup_problem(
    company: str,
    cut_off: str,
    profit_and_loss: str,
    retained_earnings_account: Optional[str],
    session=None,
) -> Optional[str]:
    """Why opening balances can't be set up with these values, or None."""
    if not frappe.has_permission(TARGET, "create") or not frappe.has_permission(TARGET, "submit"):
        return _(
            "Opening balances are created and submitted as a Journal Entry, and you can't do both. "
            "An Accounts Manager can import them."
        )
    if not company or not frappe.db.exists("Company", company):
        return _("Company {0} doesn't exist.").format(company)
    if not cut_off:
        return _("Give the cut-off date (the last day in the old system) as YYYY-MM-DD.")
    try:
        date = getdate(cut_off)
    except Exception:
        frappe.clear_messages()
        return _("'{0}' isn't a date. Give the cut-off date as YYYY-MM-DD.").format(cut_off)
    if not opening_invoices.in_fiscal_year(date, company):
        return _("{0} isn't in any fiscal year of {1}. Create the fiscal year first.").format(date, company)
    if not temporary_account(company):
        return _(
            "{0} has no Temporary Opening account (an account of type Temporary). Add one to the "
            "chart of accounts first."
        ).format(company)
    if frappe.db.exists("Period Closing Voucher", {"company": company, "docstatus": 1}):
        return _(
            "{0} has a submitted Period Closing Voucher, and ERPNext doesn't accept an opening entry "
            "once a period is closed."
        ).format(company)
    own = set((settings(session).get("created") or {}) if session else ())
    # On any date: a second opening entry, on another cut-off, would count the balances twice (#34433)
    existing = [
        entry
        for entry in frappe.get_all(
            "Journal Entry",
            filters={"company": company, "is_opening": "Yes", "docstatus": 1},
            fields=["name", "posting_date"],
            order_by="posting_date",
        )
        if entry.name not in own
    ]
    if existing:
        return _(
            "{0} already has an opening Journal Entry: {1}. Opening balances are entered once: "
            "cancel it first to enter them again."
        ).format(company, ", ".join(f"{entry.name} ({entry.posting_date})" for entry in existing))
    if cstr(profit_and_loss) not in PL_MODES:
        return _(
            "profit_and_loss is stop (leave Profit and Loss rows out until the user decides) or "
            "retained_earnings (roll them into a retained-earnings account)."
        )
    if profit_and_loss == "retained_earnings":
        account = (
            frappe.db.get_value(
                "Account",
                retained_earnings_account,
                ["company", "root_type", "is_group"],
                as_dict=True,
            )
            if retained_earnings_account
            else None
        )
        if not account or account.company != company or account.root_type != "Equity" or account.is_group:
            return _(
                "Name the retained-earnings account: an Equity account of {0} that isn't a group."
            ).format(company)
    return None


def setup(
    session,
    company: str,
    cut_off: str,
    columns: Dict[str, str],
    profit_and_loss: str = "stop",
    retained_earnings_account: Optional[str] = None,
) -> Dict[str, Any]:
    """Store the company, cut-off, Profit and Loss handling and columns on the session, which
    becomes Mapped. Raises OpeningBalancesProblem, listing every wrong column at once."""
    if session.status not in ("File Read", "Mapped", "Dry Run Failed", "Ready to Import"):
        raise OpeningBalancesProblem(
            _("This session is {0}, so it can't be set up again.").format(_(session.status))
        )
    options = frappe.parse_json(session.template_options or "{}") or {}
    if (options.get("opening_stock") or {}).get("created") or (options.get("opening_invoices") or {}).get(
        "created"
    ):
        raise OpeningBalancesProblem(
            _("This session brought in opening stock or invoices. Start a new session for the balances.")
        )
    earlier = settings(session)
    try:
        normal_cut_off = str(getdate(cut_off))
    except Exception:
        frappe.clear_messages()
        normal_cut_off = cstr(cut_off)  # setup_problem below says it isn't a date
    if earlier.get("created") and earlier.get("company") != company:
        raise OpeningBalancesProblem(
            _(
                "This session already made the opening entry for {0}. Start a new session for the "
                "other company."
            ).format(earlier["company"])
        )
    if earlier.get("created") and earlier.get("cut_off") != normal_cut_off:
        raise OpeningBalancesProblem(
            _(
                "This session already made the opening entry at {0}. Start a new session for another "
                "cut-off date."
            ).format(earlier["cut_off"])
        )
    profit_and_loss = profit_and_loss or "stop"
    problem = setup_problem(company, cut_off, profit_and_loss, retained_earnings_account, session)
    if problem:
        raise OpeningBalancesProblem(problem)

    headers = session_headers(session)
    mapping, extra, given, problems = {}, {}, set(), []
    column_of: Dict[str, str] = {}  # field -> the column mapped to it first
    for column, field in (columns or {}).items():
        if column not in headers:
            problems.append(_("There is no column '{0}'. Columns: {1}.").format(column, ", ".join(headers)))
        elif field not in FIELDS:
            problems.append(_("'{0}' can't be mapped. Map columns to: {1}.").format(field, ", ".join(FIELDS)))
        elif field in column_of:
            problems.append(
                _("Two columns are mapped to {0}: {1} and {2}.").format(field, column_of[field], column)
            )
        else:
            column_of[field] = column
            given.add(field)
            if field in MAPPED:
                mapping[str(headers.index(column))] = MAPPED[field]
            else:
                extra[field] = headers.index(column)
    missing = [field for field in REQUIRED_FIELDS if field not in given]
    if missing:
        problems.append(_("Map a column to each of: {0}.").format(", ".join(missing)))
    if not given & {"balance", "debit", "credit"}:
        problems.append(_("Map a column to balance (signed), or to debit and credit."))
    if problems:
        raise OpeningBalancesProblem(" ".join(problems))
    for position in range(len(headers)):
        mapping.setdefault(str(position), "Don't Import")

    balances = {
        "company": company,
        "cut_off": normal_cut_off,
        "profit_and_loss": profit_and_loss,
        "retained_earnings_account": retained_earnings_account
        if profit_and_loss == "retained_earnings"
        else None,
        "temporary_opening_account": temporary_account(company),
        "currency": frappe.get_cached_value("Company", company, "default_currency"),
        "columns": extra,
    }
    if earlier.get("created"):  # what an earlier import made stays on the session
        balances["created"] = earlier["created"]
    for other in ("opening_stock", "opening_invoices"):  # a session is one kind of special import
        if not (options.get(other) or {}).get("created"):
            options.pop(other, None)
    options["opening_balances"] = balances
    session.template_options = frappe.as_json(options)
    session.import_type = "Insert New Records"
    save_mapping(
        session,
        TARGET,
        mapping,
        _("Opening balances for {0}, cut-off {1}, against {2}.").format(
            company, balances["cut_off"], balances["temporary_opening_account"]
        ),
    )
    return {"opening_balances": balances, "column_to_field_map": opening_stock.shown_mapping(mapping, extra)}


def check_can_run(session) -> None:
    from frappe_assistant_core.utils import import_dry_run as dry_run

    dry_run.check_status(session)
    balances = settings(session)
    if balances.get("created"):
        raise dry_run.DryRunProblem(
            _(
                "This session already made the opening entry {0}. Checking again could bring the "
                "balances in twice; import_opening_balances with the same values reports on it."
            ).format(", ".join(balances["created"]))
        )
    problem = setup_problem(
        balances.get("company"),
        balances.get("cut_off"),
        balances.get("profit_and_loss"),
        balances.get("retained_earnings_account"),
        session,
    )
    if problem:
        raise dry_run.DryRunProblem(problem)
    if not session.source_file:
        raise dry_run.DryRunProblem(
            _("The file {0} is only in the chat. Upload it in File Manager and pass its file_id.").format(
                session.file_name
            )
        )


# -- reading the file ------------------------------------------------------------------------


def balance_of(cells: Dict[str, str]) -> Tuple[float, float]:
    """(debit, credit) of a row. From the debit and credit cells when either has a number, else
    from the signed balance (positive is a debit; negative or in parentheses, a credit). A row
    with both a debit and a credit is returned as is: the check reports it. Raises ValueError
    when a number can't be read."""
    debit = opening_stock.number(cells.get("debit"))
    credit = opening_stock.number(cells.get("credit"))
    if debit is None and credit is None:
        balance = opening_stock.number(cells.get("balance"))
        if balance is None:
            return 0, 0
        return (balance, 0) if balance >= 0 else (0, -balance)
    return debit or 0, credit or 0


def is_totals_row(cells: Dict[str, str]) -> bool:
    account = cstr(cells.get("account")).strip()
    has_amount = any(cstr(cells.get(name)).strip() for name in ("debit", "credit", "balance"))
    return has_amount and (not account or bool(opening_stock.TOTALS.match(account)))


def read_lines(session) -> List[opening_stock.Line]:
    """Every non-blank row of the session's sheet, as field -> text, with value maps applied."""
    from frappe_assistant_core.utils.import_dry_run import column_to_field_map
    from frappe_assistant_core.utils.import_fixes import apply_value_maps

    file_doc = readable_session_file(session)
    rows = apply_value_maps(session, read_sheet_rows(file_doc, session.sheet or None))
    fields = {target: field for field, target in MAPPED.items()}
    positions = {
        int(position): fields[target]
        for position, target in column_to_field_map(session).items()
        if str(position).isdigit() and target in fields
    }
    positions.update({int(p): f for f, p in (settings(session).get("columns") or {}).items()})
    lines, typed = [], opening_stock.typed_file(session, file_doc)
    for index, row in enumerate(rows[1:], start=2):
        cells = opening_stock.cell_texts(file_doc, row, positions, typed)
        if any(cells.values()):
            lines.append(opening_stock.Line(index, cells))
    return lines


# -- finding accounts ------------------------------------------------------------------------

ACCOUNT_FIELDS = ["name", "company", "is_group", "disabled", "report_type", "account_type", "root_type"]


def find_account(company: str, abbr: str, text: str) -> Optional[frappe._dict]:
    """The account the file means, in order: the exact account name; '<text> - <abbreviation>';
    the account number; the one ledger account of the company with that account name. None when
    nothing matches or several do."""
    text = cstr(text).strip()
    if not text:
        return None
    found = None
    for name in (text, f"{text} - {abbr}"):
        found = frappe.db.get_value("Account", name, ACCOUNT_FIELDS, as_dict=True)
        if found:
            break
    if not found:
        for field, extra in (("account_number", {}), ("account_name", {"is_group": 0})):
            matches = frappe.get_all(
                "Account", filters={"company": company, field: text, **extra}, fields=ACCOUNT_FIELDS, limit=2
            )
            if len(matches) == 1:
                found = matches[0]
                break
            if matches:  # several: a missing link, not a guess
                return None
    if not found:
        return None
    found = frappe._dict(found)
    found["account_currency"] = frappe.get_cached_value("Account", found.name, "account_currency")
    return found


# -- checking the rows -----------------------------------------------------------------------

CAUSE_NOT_THIS_COMPANY = "Account of another company"
CAUSE_GROUP_ACCOUNT = "Group account"
CAUSE_DISABLED_ACCOUNT = "Disabled account"
CAUSE_PROFIT_AND_LOSS = "Profit and Loss account"
CAUSE_TEMPORARY = "Temporary Opening account"
CAUSE_FOREIGN_CURRENCY = "Account in another currency"
CAUSE_BOTH_SIDES = "Debit and credit both"
CAUSE_NEGATIVE = "Negative amount"
CAUSE_ACCOUNT_TWICE = "Account twice"
CAUSE_NOT_BALANCED = "Debits and credits don't balance"
NEW_CAUSES = (
    CAUSE_NOT_THIS_COMPANY,
    CAUSE_GROUP_ACCOUNT,
    CAUSE_DISABLED_ACCOUNT,
    CAUSE_PROFIT_AND_LOSS,
    CAUSE_TEMPORARY,
    CAUSE_FOREIGN_CURRENCY,
    CAUSE_BOTH_SIDES,
    CAUSE_NEGATIVE,
    CAUSE_ACCOUNT_TWICE,
    CAUSE_NOT_BALANCED,
)
# One group per cause, so "4 rows are Profit and Loss accounts" is one decision. An account that
# can't be used is one group per account, because the fix (an account to map to) depends on which.
BY_VALUE = (CAUSE_NOT_THIS_COMPANY, CAUSE_GROUP_ACCOUNT, CAUSE_DISABLED_ACCOUNT)
CHILD = "Journal Entry Account"
LABELS = {
    "account": "Account",
    "debit_in_account_currency": "Debit",
    "credit_in_account_currency": "Credit",
    "balance": "Balance",
}
AMOUNT_FIELDS = (
    ("debit", "debit_in_account_currency"),
    ("credit", "credit_in_account_currency"),
    ("balance", "balance"),
)


@dataclass
class Ready:
    row: int
    account: str
    debit: float
    credit: float
    covered: bool
    report_type: str = ""
    account_type: str = ""


class _AccountChecker(opening_stock._StockChecker):
    """Groups failures the dry run's way, so its results file, fixes and reply are reused."""

    def __init__(self):
        super().__init__()
        self.doctype = TARGET


def _precision() -> int:
    precision = frappe.get_precision(CHILD, "debit_in_account_currency")
    return 2 if precision is None else int(precision)


def _problem(cause: str, field: str, value: str, message: str):
    from frappe_assistant_core.utils import import_dry_run as dry_run

    by_value = cause in BY_VALUE or cause == dry_run.CAUSE_MISSING_LINK
    key = (cause, CHILD, field) + ((value,) if by_value else ())
    info = {
        "cause": cause,
        "parent": CHILD,
        "field": field,
        "label": _(LABELS[field]),
        "value": value if by_value else None,
        "message": message,
    }
    return key, info


def _line_problem(line: opening_stock.Line, balances: Dict[str, Any], find, seen: Dict[str, int]):
    """The line's problem as (key, info), or the Ready line. ``seen`` holds the accounts of the
    rows before it, as account -> row."""
    from frappe_assistant_core.utils import import_dry_run as dry_run

    cells = line.cells
    if is_totals_row(cells):
        return (opening_stock.CAUSE_TOTALS_ROW,), {
            "cause": opening_stock.CAUSE_TOTALS_ROW,
            "message": _("A totals row, not an account."),
        }
    # the cells balance_of reads: the balance cell only when debit and credit are both blank
    cells_read, fields = ["debit", "credit"], dict(AMOUNT_FIELDS)
    if not cstr(cells.get("debit")).strip() and not cstr(cells.get("credit")).strip():
        cells_read.append("balance")
    for name in cells_read:
        try:
            opening_stock.number(cells.get(name))
        except ValueError:
            return _problem(
                dry_run.CAUSE_BAD_VALUE,
                fields[name],
                cells[name],
                _("'{0}' isn't a number.").format(cells[name]),
            )
    debit, credit = balance_of(cells)
    if debit and credit:
        return _problem(
            CAUSE_BOTH_SIDES,
            "debit_in_account_currency",
            cells.get("debit", ""),
            _("The row has both a debit and a credit."),
        )
    if debit < 0 or credit < 0:
        field = "debit_in_account_currency" if debit < 0 else "credit_in_account_currency"
        return _problem(
            CAUSE_NEGATIVE,
            field,
            cells.get("debit" if debit < 0 else "credit", ""),
            _("A debit or credit can't be negative. Put the amount on the other side."),
        )

    text = cells.get("account", "")
    account = find(balances["company"], frappe.get_cached_value("Company", balances["company"], "abbr"), text)
    if not account:
        return _problem(
            dry_run.CAUSE_MISSING_LINK,
            "account",
            text,
            _("Account '{0}' isn't in the chart of accounts.").format(text),
        )
    name = account.name
    if account.company != balances["company"]:
        return _problem(
            CAUSE_NOT_THIS_COMPANY,
            "account",
            text,
            _("{0} belongs to {1}, not {2}.").format(name, account.company, balances["company"]),
        )
    if account.is_group:
        return _problem(
            CAUSE_GROUP_ACCOUNT,
            "account",
            text,
            _("{0} is a group account. Entries go to ledger accounts.").format(name),
        )
    if account.disabled:
        return _problem(CAUSE_DISABLED_ACCOUNT, "account", text, _("{0} is disabled.").format(name))
    if name == balances.get("temporary_opening_account"):
        return _problem(
            CAUSE_TEMPORARY,
            "account",
            text,
            _(
                "{0} is the Temporary Opening account: it takes the balancing line, not a row of the file."
            ).format(name),
        )
    if (account.account_currency or balances.get("currency")) != balances.get("currency"):
        return _problem(
            CAUSE_FOREIGN_CURRENCY,
            "account",
            text,
            _("{0} is in {1}, not {2}. Foreign-currency accounts aren't brought in here.").format(
                name, account.account_currency, balances.get("currency")
            ),
        )
    if account.report_type == "Profit and Loss" and balances.get("profit_and_loss") != "retained_earnings":
        return _problem(
            CAUSE_PROFIT_AND_LOSS,
            "account",
            text,
            _(
                "{0} is a Profit and Loss account, which ERPNext doesn't take in an opening entry. "
                "To bring these rows in, run set_opening_balances again with "
                'profit_and_loss="retained_earnings" and a retained-earnings account: their net is '
                "then added to that account."
            ).format(name),
        )
    if name in seen:
        return _problem(
            CAUSE_ACCOUNT_TWICE,
            "account",
            text,
            _("{0} is in row {1} too.").format(name, seen[name]),
        )
    return Ready(
        line.row,
        name,
        flt(debit, _precision()),
        flt(credit, _precision()),
        account.account_type in covered_types(balances["company"]),
        account.report_type or "",
        account.account_type or "",
    )


def _check_lines(
    session, checker: _AccountChecker, lines: Optional[List[opening_stock.Line]] = None
) -> List[Ready]:
    from frappe_assistant_core.utils import import_dry_run as dry_run

    balances, excluded = settings(session), dry_run._excluded_rows(session)
    ready, seen = [], {}
    for line in read_lines(session) if lines is None else lines:
        if line.row in excluded:
            checker.mark(line.row, "excluded")
            continue
        outcome = _line_problem(line, balances, find_account, seen)
        if not isinstance(outcome, Ready):
            checker.fail(line.row, *outcome)
            continue
        seen[outcome.account] = line.row
        ready.append(outcome)
    return ready


def ready_lines(session) -> List[Ready]:
    """The lines that pass the row checks now (ERPNext's own validation is not run)."""
    return _check_lines(session, _AccountChecker())


# -- the balance check -----------------------------------------------------------------------


def _file_totals(session, lines: Optional[List[opening_stock.Line]] = None) -> Tuple[float, float, int]:
    """(debit, credit, finer) over every readable row, whatever happens to it later: each row
    rounded to the currency precision first, as the entry posts it (#34433), and how many rows
    had more decimals than that."""
    precision = _precision()
    debit = credit = 0.0
    finer = 0
    for line in read_lines(session) if lines is None else lines:
        if is_totals_row(line.cells):
            continue
        try:
            row_debit, row_credit = balance_of(line.cells)
        except ValueError:
            continue
        rounded_debit, rounded_credit = flt(row_debit, precision), flt(row_credit, precision)
        finer += rounded_debit != flt(row_debit) or rounded_credit != flt(row_credit)
        debit, credit = flt(debit + rounded_debit, precision), flt(credit + rounded_credit, precision)
    return debit, credit, finer


def file_balance(session, lines: Optional[List[opening_stock.Line]] = None) -> Dict[str, float]:
    """Total debit, total credit and their difference over every row of the file that can be
    read: before leave-outs and before the account checks."""
    precision = _precision()
    debit, credit, _rows = _file_totals(session, lines)
    return {
        "debit": flt(debit, precision),
        "credit": flt(credit, precision),
        "difference": flt(debit - credit, precision),
    }


def is_balanced(session, lines: Optional[List[opening_stock.Line]] = None) -> bool:
    """Debits equal credits, each row rounded to the currency precision. Only a row with more
    decimals than that brings rounding: half a unit of the smallest digit each (#34433)."""
    precision = _precision()
    debit, credit, finer = _file_totals(session, lines)
    return abs(flt(debit - credit, precision)) <= flt(0.5 * 10**-precision * finer, precision + 1)


# -- the entry -------------------------------------------------------------------------------


def entry_lines(balances: Dict[str, Any], ready: List[Ready]) -> List[Dict[str, Any]]:
    """The Journal Entry Account rows: each ready row that isn't covered, as the file has it;
    Profit and Loss rows folded into one line on the retained-earnings account when that is
    chosen; then one line to the Temporary Opening account when the others don't balance."""
    precision = _precision()
    fold = balances.get("profit_and_loss") == "retained_earnings"
    lines, folded = [], 0.0
    for row in ready:
        if row.covered:
            continue
        if fold and row.report_type == "Profit and Loss":
            folded += row.debit - row.credit
        elif row.debit or row.credit:
            lines.append(
                {
                    "account": row.account,
                    "debit_in_account_currency": flt(row.debit, precision),
                    "credit_in_account_currency": flt(row.credit, precision),
                }
            )
    folded = flt(folded, precision)
    if folded:
        lines.append(
            {
                "account": balances["retained_earnings_account"],
                "debit_in_account_currency": folded if folded > 0 else 0,
                "credit_in_account_currency": -folded if folded < 0 else 0,
            }
        )
    if not lines:
        return []
    difference = flt(
        sum(line["debit_in_account_currency"] for line in lines)
        - sum(line["credit_in_account_currency"] for line in lines),
        precision,
    )
    if difference:
        lines.append(
            {
                "account": balances["temporary_opening_account"],
                "debit_in_account_currency": -difference if difference < 0 else 0,
                "credit_in_account_currency": difference if difference > 0 else 0,
            }
        )
    return lines


def folded_accounts(balances: Dict[str, Any], ready: List[Ready]) -> Dict[str, float]:
    """The Profit and Loss accounts folded into the retained-earnings line, with the file's net."""
    if balances.get("profit_and_loss") != "retained_earnings":
        return {}
    precision = _precision()
    folded: Dict[str, float] = {}
    for row in ready:
        if not row.covered and row.report_type == "Profit and Loss":
            folded[row.account] = flt(folded.get(row.account, 0) + row.debit - row.credit, precision)
    return folded


# What the approval card shows besides the file's totals, as the last check found it (#34433): the
# balancing line to Temporary Opening (positive a debit, negative a credit), the rows another import
# brings in (covered), and the rows the user left out. Each must match; one left out is 0.
CARD_AMOUNTS = ("balancing_amount", "covered_debit", "covered_credit", "excluded_debit", "excluded_credit")


def card_amounts(
    session,
    balances: Dict[str, Any],
    ready: List[Ready],
    lines: List[opening_stock.Line],
    entry: List[Dict[str, Any]],
) -> Dict[str, float]:
    """CARD_AMOUNTS for the ready rows of ``lines`` and the ``entry`` lines made of them."""
    from frappe_assistant_core.utils import import_dry_run as dry_run

    precision = _precision()
    line = balancing_line(balances, entry)
    excluded_rows = dry_run._excluded_rows(session)
    excluded = [
        line_of for line_of in lines if line_of.row in excluded_rows and not is_totals_row(line_of.cells)
    ]
    excluded_debit = excluded_credit = 0.0
    for left_out in excluded:
        try:
            debit, credit = balance_of(left_out.cells)
        except ValueError:
            continue
        excluded_debit = flt(excluded_debit + flt(debit, precision), precision)
        excluded_credit = flt(excluded_credit + flt(credit, precision), precision)
    covered = [row for row in ready if row.covered]
    return {
        "balancing_amount": flt(line["debit"] - line["credit"], precision) if line else 0,
        "covered_debit": flt(sum(flt(row.debit, precision) for row in covered), precision),
        "covered_credit": flt(sum(flt(row.credit, precision) for row in covered), precision),
        "excluded_debit": excluded_debit,
        "excluded_credit": excluded_credit,
    }


def balancing_line(balances: Dict[str, Any], lines: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The line to the Temporary Opening account among ``lines``, as {account, debit, credit}."""
    if lines and lines[-1]["account"] == balances.get("temporary_opening_account"):
        last = lines[-1]
        return {
            "account": last["account"],
            "debit": last["debit_in_account_currency"],
            "credit": last["credit_in_account_currency"],
        }
    return None


def build_entry(balances: Dict[str, Any], ready: List[Ready]):
    """An unsaved opening Journal Entry of the ready rows."""
    return frappe.get_doc(
        {
            "doctype": TARGET,
            "voucher_type": VOUCHER_TYPE,
            "is_opening": "Yes",
            "company": balances["company"],
            "posting_date": balances["cut_off"],
            "user_remark": _("Opening balances imported from the old system, cut-off {0}.").format(
                balances["cut_off"]
            ),
            "accounts": entry_lines(balances, ready),
        }
    )


SAVEPOINT = "fac_opening_balances_check"


def _submit_now(entry) -> None:
    """Submit in this request, all or nothing. ``submit()`` hands an entry of more than 100
    lines to a background queue and returns with it still a draft, so neither the check nor the
    import could rely on it; ``_submit()`` is the same submission without the queue."""
    entry._submit()
    if entry.docstatus != 1:
        frappe.throw(_("{0} was not submitted.").format(entry.name or _("The entry")))


def _entry_error(balances: Dict[str, Any], ready: List[Ready]) -> Optional[Exception]:
    """None when ERPNext accepts the entry, inserted and submitted, else why not. Rolled back."""
    from frappe_assistant_core.utils import import_dry_run as dry_run

    frappe.clear_messages()
    with dry_run.held_back():
        frappe.db.savepoint(SAVEPOINT)
        try:
            entry = build_entry(balances, ready)
            entry.insert()
            _submit_now(entry)
            return None
        except Exception as e:
            return e
        finally:
            frappe.db.rollback(save_point=SAVEPOINT)
            frappe.clear_messages()


def _erpnext_check(
    session, ready: List[Ready], checker: _AccountChecker, balances: Optional[Dict[str, Any]] = None
) -> List[Ready]:
    """ERPNext's own validation of the entry as a whole, inside a savepoint that is rolled back.
    When it refuses, every ready row fails with its message. With no line to post (only covered
    rows) there is nothing to ask ERPNext."""
    from frappe_assistant_core.utils import import_dry_run as dry_run

    balances = balances or settings(session)
    if not ready or not entry_lines(balances, ready):
        return ready
    error = _entry_error(balances, ready)
    if error is None:
        return ready
    kind, message = dry_run.refusal(error)
    for row in ready:
        checker.fail(
            row.row,
            (dry_run.CAUSE_REJECTED, kind, message),
            {"cause": dry_run.CAUSE_REJECTED, "error": kind, "message": message},
        )
    return []


CHART_HINT = (
    "This company has no transactions yet. If its chart of accounts should be replaced to match the "
    "old system, do it first with ERPNext's Chart of Accounts Importer; it refuses once any "
    "transaction exists."
)


def _has_transactions(company: str) -> bool:
    return bool(frappe.db.exists("GL Entry", {"company": company, "is_cancelled": 0}))


def run(session_name: str, commit_progress: bool = False) -> Dict[str, Any]:
    """The dry run of an opening-balances session: the file's balance, every row checked, ERPNext's
    own validation of the entry, the result stored the dry run's way, with the totals."""
    from frappe_assistant_core.utils import import_dry_run as dry_run

    session = dry_run.engine_session(session_name)
    balances = settings(session)
    file_doc = readable_session_file(session)
    lines = read_lines(session)
    balance = file_balance(session, lines)
    checker = _AccountChecker()
    ready = _check_lines(session, checker, lines)
    precision = _precision()
    balanced = is_balanced(session, lines)
    if not balanced:
        # the file itself is wrong, so nothing is ready: every row that passed fails together
        message = _(
            "Debits total {0} and credits total {1}: they differ by {2}. Nothing can be imported until "
            "the file balances."
        ).format(
            frappe.format_value(balance["debit"], {"fieldtype": "Float", "precision": precision}),
            frappe.format_value(balance["credit"], {"fieldtype": "Float", "precision": precision}),
            frappe.format_value(abs(balance["difference"]), {"fieldtype": "Float", "precision": precision}),
        )
        info = {"cause": CAUSE_NOT_BALANCED, "message": message, "fix_in_file": True}
        for row in ready:
            checker.fail(row.row, (CAUSE_NOT_BALANCED,), info)
        if not ready:
            # no row to fail with it: the group still shows, on the first row that failed
            first = next((r for r in checker.rows if r["status"] == "failed"), None)
            if first:
                payload = SimpleNamespace(rows=[SimpleNamespace(row_number=first["row"])])
                first["groups"].append(checker._group_of(checker, (CAUSE_NOT_BALANCED,), info, payload))
        ready = []
    else:
        ready = _erpnext_check(session, ready, checker, balances)
    for row in ready:
        checker.mark(row.row, "ready")
    checker.rows.sort(key=lambda r: r["row"])
    summary = dry_run._store(session_name, file_doc, checker, len(checker.rows))
    lines_of_entry = entry_lines(balances, ready)
    summary["opening_balances"] = {
        "cut_off": balances["cut_off"],
        "rows": len(ready),
        "lines": len(lines_of_entry),
        "total_debit": balance["debit"],
        "total_credit": balance["credit"],
        "covered": len([row for row in ready if row.covered]),
        "balancing": balancing_line(balances, lines_of_entry),
        "profit_and_loss": balances.get("profit_and_loss", "stop"),
        **card_amounts(session, balances, ready, lines, lines_of_entry),
    }
    summary["balance"] = {**balance, "balanced": balanced}
    if any(key[0] == dry_run.CAUSE_MISSING_LINK for key in checker.groups) and not _has_transactions(
        balances["company"]
    ):
        summary["opening_balances"]["chart_hint"] = CHART_HINT
    frappe.db.set_value(
        dry_run.SESSION_DOCTYPE,
        session_name,
        "validation_summary",
        frappe.as_json(summary),
        update_modified=False,
    )
    return summary


# -- creating --------------------------------------------------------------------------------

CREATE_SAVEPOINT = "fac_opening_balances_create"
DONE = ("Importing", "Completed", "Failed")


def check_card(session, company, cut_off, rows, total_debit, total_credit, amounts=None) -> None:
    """The approval card shows what FACO passed: refuse unless it is what the last check found,
    the balancing line and what is covered or left out (``amounts``, CARD_AMOUNTS) among it."""
    summary = frappe.parse_json(session.validation_summary or "{}") or {}
    totals, balances = summary.get("opening_balances") or {}, settings(session)
    precision = _precision()
    amounts = amounts or {}
    checked = (
        balances.get("company"),
        balances.get("cut_off"),
        summary.get("ready"),
        flt(totals.get("total_debit"), precision),
        flt(totals.get("total_credit"), precision),
        *(flt(totals.get(key), precision) for key in CARD_AMOUNTS),
    )
    try:
        asked = (
            cstr(company).strip(),
            str(getdate(cut_off)),
            int(rows),
            flt(total_debit, precision),
            flt(total_credit, precision),
            *(flt(amounts.get(key), precision) for key in CARD_AMOUNTS),
        )
    except Exception:
        frappe.clear_messages()
        asked = None
    if checked[2] is None:
        raise OpeningBalancesProblem(_("The sheet hasn't been checked. Check it with dry_run_import first."))
    if asked != checked:
        raise OpeningBalancesProblem(
            _(
                "The last check found {2} rows for {0} at {1}, with debits of {3} and credits of {4}; "
                "a balancing line of {5} to Temporary Opening (positive a debit); covered by other "
                "imports, debits {6} and credits {7}; left out, debits {8} and credits {9}. Pass those, "
                "so the approval card shows them."
            ).format(*checked)
        )


def _expected(balances: Dict[str, Any], lines: List[Dict[str, Any]], ready: List[Ready]):
    """Per account, what the file says the books should hold from this import: the entry's lines
    and the covered rows (which the other imports bring in)."""
    precision = _precision()
    expected: Dict[str, Dict[str, float]] = {}

    def add(account: str, debit: float, credit: float) -> None:
        held = expected.setdefault(account, {"debit": 0, "credit": 0})
        held["debit"] = flt(held["debit"] + flt(debit), precision)
        held["credit"] = flt(held["credit"] + flt(credit), precision)

    for line in lines:
        add(line["account"], line["debit_in_account_currency"], line["credit_in_account_currency"])
    for row in ready:
        if row.covered:
            add(row.account, row.debit, row.credit)
    return expected


def create(session) -> None:
    """Create and submit the one opening Journal Entry, all or nothing, in one savepoint. Done
    already (or running): nothing is created and the caller reports. Raises OpeningBalancesProblem
    when it isn't ready, or when ERPNext refuses (the session is then Failed and nothing is left)."""
    from frappe_assistant_core.utils import import_fixes

    if session.status in DONE or settings(session).get("created"):
        return
    if session.status != "Ready to Import" or not import_fixes.checked_as_is(session):
        raise OpeningBalancesProblem(
            _(
                "The sheet isn't ready, or it changed since its last check. Check it with dry_run_import first."
            )
        )
    balances = settings(session)
    ready = ready_lines(session)
    approved = (frappe.parse_json(session.validation_summary or "{}") or {}).get("ready")
    if len(ready) != approved:
        raise OpeningBalancesProblem(
            _(
                "The balances changed since the last check: {0} rows are ready now, not {1}. Check it "
                "again with dry_run_import."
            ).format(len(ready), approved)
        )
    lines = entry_lines(balances, ready)
    if not lines:
        raise OpeningBalancesProblem(
            _(
                "Nothing to import: every row is covered by the opening invoices and stock imports, "
                "or left out."
            )
        )
    problem = setup_problem(
        balances.get("company"),
        balances.get("cut_off"),
        balances.get("profit_and_loss"),
        balances.get("retained_earnings_account"),
        session,
    )
    if problem:
        raise OpeningBalancesProblem(problem)

    # Two calls at once: the row lock makes the second wait, then see Importing and report.
    current = frappe.db.get_value(session.doctype, session.name, "status", for_update=True)
    if current != "Ready to Import":
        return
    session.status = "Importing"
    session.save()

    # A rollback to the savepoint does not undo what the insert or submit registered to run at
    # commit (hooks, queued jobs, webhooks): keep the lists as they are now, to put them back.
    callbacks = {
        name: list(getattr(frappe.db, name)._functions)
        for name in ("before_commit", "after_commit", "before_rollback", "after_rollback")
    }
    webhook_queue = getattr(frappe.local, "_webhook_queue", None)
    webhook_queue = list(webhook_queue) if webhook_queue else None
    frappe.db.savepoint(CREATE_SAVEPOINT)
    try:
        entry = build_entry(balances, ready)
        entry.insert()
        _submit_now(entry)
        session.append("created_records", {"record_doctype": TARGET, "record_name": entry.name})
        options = frappe.parse_json(session.template_options or "{}") or {}
        options["opening_balances"]["created"] = {
            entry.name: {
                "lines": len(lines),
                "rows": len(ready),
                "expected": _expected(balances, lines, ready),
                "balancing": balancing_line(balances, lines),
                "folded": folded_accounts(balances, ready),
            }
        }
        session.template_options = frappe.as_json(options)
        session.status = "Completed"
        session.log_step(
            "Import",
            "Success",
            _("Opening Journal Entry {0} created and submitted: {1} lines from {2} rows.").format(
                entry.name, len(lines), len(ready)
            ),
            rows_ok=len(ready),
            rows_failed=0,
        )
        session.save()
    except Exception as e:
        from frappe_assistant_core.utils import import_dry_run as dry_run

        frappe.db.rollback(save_point=CREATE_SAVEPOINT)
        for name, functions in callbacks.items():
            manager = getattr(frappe.db, name)
            manager._functions.clear()
            manager._functions.extend(functions)
        frappe.local._webhook_queue = webhook_queue
        frappe.clear_messages()
        message = _("ERPNext refused the opening entry: {0}").format(dry_run._message_of(e))
        session.reload()  # drop what the failed attempt put on the document
        if settings(session).get("created"):
            # another call made the entry meanwhile: its status stands
            raise OpeningBalancesProblem(message) from e
        session.status = "Failed"
        session.log_step("Import", "Failed", message, rows_ok=0, rows_failed=len(ready))
        session.save()
        raise OpeningBalancesProblem(message) from e
    finally:
        frappe.clear_messages()


DIFFERENCES_SHOWN = 50
COVERED_SOURCE = "opening invoices / opening stock"


def _erpnext_sums(company: str, cut_off: str, accounts: List[str]) -> Dict[str, Dict[str, float]]:
    """Debit and credit of each account's GL Entries up to the cut-off: one query, read only.
    Summed with frappe.qb: Frappe v16 refuses SQL functions in get_all's fields."""
    from frappe.query_builder.functions import Sum

    if not accounts:
        return {}
    gle = frappe.qb.DocType("GL Entry")
    rows = (
        frappe.qb.from_(gle)
        .select(gle.account, Sum(gle.debit).as_("debit"), Sum(gle.credit).as_("credit"))
        .where(
            (gle.company == company)
            & (gle.is_cancelled == 0)
            & (gle.posting_date <= cut_off)
            & gle.account.isin(accounts)
        )
        .groupby(gle.account)
    ).run(as_dict=True)
    return {row.account: {"debit": flt(row.debit), "credit": flt(row.credit)} for row in rows}


def _not_brought_in(session, precision: int) -> List[Dict[str, Any]]:
    """The rows left out, by reason, with the file's amounts when the sheet can be read."""
    from frappe_assistant_core.utils import import_fixes

    left_out = import_fixes.left_out(session)
    if not left_out:
        return []
    try:
        cells = {line.row: line.cells for line in read_lines(session)}
    except Exception:
        frappe.clear_messages()
        cells = {}
    groups: Dict[str, Dict[str, Any]] = {}
    for entry in left_out:
        reason = entry["reason"] or _("Left out by the user")
        group = groups.setdefault(reason, {"reason": reason, "rows": [], "debit": 0.0, "credit": 0.0})
        group["rows"].append(entry["row"])
        try:
            debit, credit = balance_of(cells.get(entry["row"]) or {})
        except ValueError:
            continue
        group["debit"] += flt(debit)
        group["credit"] += flt(credit)
    return [
        {
            "reason": group["reason"],
            "count": len(group["rows"]),
            "rows": import_fixes.row_ranges(group["rows"]),
            "debit": flt(group["debit"], precision),
            "credit": flt(group["credit"], precision),
        }
        for group in groups.values()
    ]


def report(session) -> Dict[str, Any]:
    """The opening entry against ERPNext's ledger at the cut-off, account by account: each
    account whose balance differs from the file, the covered rows (brought in by the opening
    invoices and stock), the Temporary Opening balance and the rows left out. Read only."""
    balances = settings(session)
    created = balances.get("created") or {}
    name = next(iter(created), None)
    held = created.get(name) or {}
    precision = _precision()
    out: Dict[str, Any] = {
        "status": session.status,
        "journal_entry": name,
        "lines": held.get("lines"),
        "balancing": held.get("balancing"),
        "folded": [],
        "accounts": [],
        "differences_count": 0,
        "covered": [],
        "temporary_opening": None,
        "not_brought_in": [],
        "totals": {"file_debit": 0, "file_credit": 0, "erpnext_debit": 0, "erpnext_credit": 0},
    }
    if not name:
        out["message"] = _("No opening entry was created.")
        return out

    company, cut_off = balances.get("company"), balances.get("cut_off")
    temporary = balances.get("temporary_opening_account")
    expected = held.get("expected") or {}
    found = _erpnext_sums(company, cut_off, list({*expected, temporary} - {None}))
    types = {
        row.name: row.account_type
        for row in frappe.get_all(
            "Account", filters={"name": ["in", list(expected) or [""]]}, fields=["name", "account_type"]
        )
    }

    def net(sums: Dict[str, float]) -> float:
        return flt(flt(sums.get("debit")) - flt(sums.get("credit")), precision)

    differences, covered = [], []
    totals = {"file_debit": 0.0, "file_credit": 0.0, "erpnext_debit": 0.0, "erpnext_credit": 0.0}
    for account in sorted(expected):
        file_sums, sums = expected[account], found.get(account, {})
        file_net, erpnext_net = net(file_sums), net(sums)
        if types.get(account) in covered_types(company):
            covered.append(
                {
                    "account": account,
                    "file_net": file_net,
                    "erpnext_net": erpnext_net,
                    "source": COVERED_SOURCE,
                }
            )
            continue
        if account == temporary:
            continue  # the balancing account is not in the file: reported on its own
        totals["file_debit"] += flt(file_sums.get("debit"))
        totals["file_credit"] += flt(file_sums.get("credit"))
        totals["erpnext_debit"] += flt(sums.get("debit"))
        totals["erpnext_credit"] += flt(sums.get("credit"))
        if erpnext_net != file_net:
            differences.append(
                {
                    "account": account,
                    "file_net": file_net,
                    "erpnext_net": erpnext_net,
                    "difference": flt(erpnext_net - file_net, precision),
                }
            )
    folded = [
        {"account": account, "file_net": flt(value, precision)}
        for account, value in sorted((held.get("folded") or {}).items())
    ]
    temporary_balance = net(found.get(temporary, {}))
    everything_in = all(row["erpnext_net"] == row["file_net"] for row in covered)
    not_brought_in = _not_brought_in(session, precision)

    parts = []
    if differences:
        parts.append(_("{0} accounts differ from the file; they are listed.").format(len(differences)))
        if len(differences) > DIFFERENCES_SHOWN:
            parts.append(_("The first {0} of {1} are shown.").format(DIFFERENCES_SHOWN, len(differences)))
    else:
        parts.append(
            _("ERPNext's trial balance at {0} matches the file, account by account.").format(cut_off)
        )
    if folded:
        parts.append(
            _("{0} Profit and Loss accounts were folded into {1}; they are not compared one by one.").format(
                len(folded), balances.get("retained_earnings_account")
            )
        )
    if temporary_balance:
        if everything_in:
            parts.append(
                _("Temporary Opening does not net to zero: {0} is not accounted for.").format(
                    temporary_balance
                )
            )
        else:
            parts.append(
                _(
                    "Temporary Opening still holds {0}: it clears when the opening invoices and opening "
                    "stock are imported."
                ).format(temporary_balance)
            )
    if not_brought_in:
        parts.append(
            _("Left out of the import: {0} rows (debit {1}, credit {2}).").format(
                sum(group["count"] for group in not_brought_in),
                flt(sum(group["debit"] for group in not_brought_in), precision),
                flt(sum(group["credit"] for group in not_brought_in), precision),
            )
        )
        left_net = flt(
            sum(group["debit"] for group in not_brought_in)
            - sum(group["credit"] for group in not_brought_in),
            precision,
        )
        if left_net:
            parts.append(
                _(
                    "Rows left out (net {0} {1}) were not brought in, so Temporary Opening will not net "
                    "to zero by that amount."
                ).format(
                    f"{abs(left_net):.{precision}f}",
                    _("debit") if left_net > 0 else _("credit"),
                )
            )
    out.update(
        {
            "accounts": differences[:DIFFERENCES_SHOWN],
            "differences_count": len(differences),
            "covered": covered,
            "folded": folded,
            "temporary_opening": {"account": temporary, "balance": temporary_balance},
            "not_brought_in": not_brought_in,
            "totals": {key: flt(value, precision) for key, value in totals.items()},
            "message": " ".join(parts),
        }
    )
    return out


# -- every row, for the sign-off report (reads only) -------------------------------------------

COVERED_REASON = "Brought in by the opening invoices and opening stock imports"


def _entry_status(balances: Dict[str, Any]) -> Tuple[Optional[str], bool]:
    """The session's opening entry, and whether it is still submitted."""
    name = next(iter(balances.get("created") or {}), None)
    return name, bool(name) and frappe.db.get_value(TARGET, name, "docstatus") == 1


def outcomes(session) -> List[Dict[str, Any]]:
    """Every row of the file and where it stands now: imported (its account is in the submitted
    opening entry), left out (by the user, or a Receivable, Payable or Stock account the other
    opening imports bring in), failed (with why) or not imported yet, with its debit and credit
    as the file writes them. Writes nothing."""
    from frappe_assistant_core.utils import import_fixes
    from frappe_assistant_core.utils.import_signoff import NOT_IMPORTED

    balances = settings(session)
    lines = read_lines(session)
    checker = _AccountChecker()
    ready = {row.row: row for row in _check_lines(session, checker, lines)}
    messages = {g["id"]: g.get("message") or _(g["cause"]) for g in checker.groups.values()}
    marked = {entry["row"]: entry for entry in checker.rows}
    left = {entry["row"]: entry["reason"] for entry in import_fixes.left_out(session)}
    name, submitted = _entry_status(balances)
    stopped = opening_stock._last_import_failure(session) if not submitted else None
    unbalanced = not name and not is_balanced(session, lines)
    in_entry = (
        set((balances.get("created") or {}).get(name, {}).get("expected") or {}) if submitted else set()
    )
    abbr = frappe.get_cached_value("Company", balances["company"], "abbr") if in_entry else None
    out = []
    for line in lines:
        entry = marked.get(line.row) or {"status": "ready"}
        status, reason = entry["status"], ""
        if status == "failed" and in_entry:
            # Its account is in the submitted entry: an account disabled since (say) doesn't
            # take its balance out of the books.
            account = find_account(balances["company"], abbr, line.cells.get("account", ""))
            if account and account.name in in_entry:
                status = "imported"
        if status == "imported":
            pass
        elif status == "failed":
            reason = "; ".join(messages.get(g, "") for g in entry.get("groups") or [])
        elif status == "excluded":
            reason = left.get(line.row) or _("Left out by the user")
        elif line.row in ready and ready[line.row].covered:
            status, reason = "excluded", _(COVERED_REASON)
        elif submitted:
            status = "imported"
        elif stopped:
            status, reason = "failed", stopped
        elif unbalanced:
            status, reason = "failed", _(CAUSE_NOT_BALANCED)
        else:
            status, reason = "not_imported", _(NOT_IMPORTED)
        try:
            (debit, credit), unreadable = balance_of(line.cells), False
        except ValueError:
            debit = credit = None
            unreadable = True
        totals_row = is_totals_row(line.cells)
        out.append(
            {
                "row": line.row,
                "status": status,
                "reason": reason,
                "debit": None if totals_row else debit,
                "credit": None if totals_row else credit,
                "unreadable": unreadable,
                "totals_row": totals_row,
                "file_says": debit if totals_row else None,
            }
        )
    return out


def summary(session) -> Dict[str, Any]:
    """The sign-off report's view of this session: its rows, debits and credits per status, and
    ERPNext's ledger at the cut-off against the file, account by account. Writes nothing."""
    from frappe_assistant_core.utils.import_signoff import tally

    balances = settings(session)
    precision = _precision()
    out = tally(outcomes(session), ("debit", "credit"), precision)
    name, submitted = _entry_status(balances)
    erpnext: Dict[str, Any] = {
        "journal_entry": name,
        "no_longer_submitted": int(bool(name) and not submitted),
    }
    if name:
        held = report(session)
        erpnext.update(
            {
                "debit": held["totals"]["erpnext_debit"],
                "credit": held["totals"]["erpnext_credit"],
                "accounts_differing": held["differences_count"],
                "differing": held["accounts"],
                # the Receivable, Payable and Stock accounts the other imports bring in
                "covered_differing": [
                    row for row in held["covered"] if row["erpnext_net"] != row["file_net"]
                ],
                "temporary_opening": (held.get("temporary_opening") or {}).get("balance"),
            }
        )
    out.update(
        {
            "kind": "opening_balances",
            "doctype": TARGET,
            "label": _("Opening Balances"),
            "company": balances["company"],
            "cut_off": balances["cut_off"],
            "balance": "trial_balance",
            "erpnext": erpnext,
        }
    )
    return out
