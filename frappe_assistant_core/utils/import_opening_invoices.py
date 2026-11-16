# frappe_assistant_core/utils/import_opening_invoices.py
# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Opening receivables and payables (#33997): the old system's unpaid customer invoices and
supplier bills become opening Sales or Purchase Invoices, made the way ERPNext's Opening Invoice
Creation Tool makes them.

That tool is one shared record for the whole site; it creates missing parties without
permission checks and reports failures only to the Error Log. So it isn't run: its own code
builds each invoice (one line of the outstanding amount against the Temporary Opening account),
and each is inserted and submitted here, in a savepoint of its own. An opening-invoices session
keeps its settings in ``template_options.opening_invoices``.
"""

import datetime
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import frappe
from dateutil import parser as date_parser
from frappe import _
from frappe.utils import cstr, flt, getdate

from frappe_assistant_core.utils import import_opening_stock as opening_stock
from frappe_assistant_core.utils.import_mapping import save_mapping, session_headers
from frappe_assistant_core.utils.import_session import read_sheet_rows, readable_session_file
from frappe_assistant_core.utils.savepoint import open_savepoint, rollback_to_savepoint

TOOL = "Opening Invoice Creation Tool"
IMPORT_TOOL = "import_opening_invoices"
INVOICE_DOCTYPES = {"Sales": "Sales Invoice", "Purchase": "Purchase Invoice"}
RECORD_DOCTYPES = tuple(INVOICE_DOCTYPES.values())  # what the file makes (import_failures.created_count)
PARTY_TYPES = {"Sales": "Customer", "Purchase": "Supplier"}
PARTY_FIELDS = {"Customer": "customer", "Supplier": "supplier"}
PARTY_NAME_FIELDS = {"Customer": "customer_name", "Supplier": "supplier_name"}
FIELDS = ("party", "outstanding_amount", "invoice_number", "posting_date", "due_date", "item_name")
MAPPED = ("party", "outstanding_amount", "posting_date", "due_date")  # fields of the invoice itself
REQUIRED_FIELDS = ("party", "outstanding_amount")
REQUEST_LIMIT = 100  # more invoices than this are created by a background job
COMMIT_EVERY = 25  # the job commits this many invoices at a time, with the session's record of them


class OpeningInvoicesProblem(Exception):
    """Opening invoices can't be set up, checked or created. The message is shown to the user."""


def settings(session) -> Dict[str, Any]:
    options = frappe.parse_json(session.template_options or "{}") or {}
    return dict(options.get("opening_invoices") or {})


def is_opening_invoices(session) -> bool:
    return bool(settings(session))


def is_party(session, doctype: str) -> bool:
    """Whether ``doctype`` is the party of an opening-invoices ``session``."""
    return bool(session) and settings(session).get("party_type") == doctype


def temporary_account(company: str) -> Optional[str]:
    """The account the openings balance on: of several Temporary accounts, the company's own, the
    oldest (its chart's "Temporary Opening"), never whichever the database returns first (#34433)."""
    return frappe.db.get_value(
        "Account", {"company": company, "account_type": "Temporary", "is_group": 0}, order_by="creation asc"
    )


def in_fiscal_year(date, company: str) -> bool:
    from erpnext.accounts.utils import get_fiscal_year

    return bool(get_fiscal_year(date, company=company, boolean=True))


def setup_problem(company: str, invoice_type: str, cut_off: str) -> Optional[str]:
    """Why opening invoices can't be set up with these values, or None."""
    doctype = INVOICE_DOCTYPES.get(cstr(invoice_type))
    if not doctype:
        return _("invoice_type is Sales (what customers owe) or Purchase (what is owed to suppliers).")
    if not frappe.has_permission(doctype, "create") or not frappe.has_permission(doctype, "submit"):
        return _(
            "Opening invoices are created and submitted as {0}s, and you can't do both. An Accounts "
            "Manager can import them."
        ).format(_(doctype))
    if not company or not frappe.db.exists("Company", company):
        return _("Company {0} doesn't exist.").format(company)
    if not cut_off:
        return _("Give the cut-off date (the last day in the old system) as YYYY-MM-DD.")
    try:
        date = getdate(cut_off)
    except Exception:
        frappe.clear_messages()
        return _("'{0}' isn't a date. Give the cut-off date as YYYY-MM-DD.").format(cut_off)
    if not in_fiscal_year(date, company):
        return _("{0} isn't in any fiscal year of {1}. Create the fiscal year first.").format(date, company)
    if not temporary_account(company):
        return _(
            "{0} has no Temporary Opening account (an account of type Temporary). Add one to the "
            "chart of accounts first."
        ).format(company)
    if not frappe.get_cached_value("Company", company, "cost_center"):
        return _("{0} has no default cost center. Set it on the company first.").format(company)
    return None


def setup(session, company: str, invoice_type: str, cut_off: str, columns: Dict[str, str]) -> Dict[str, Any]:
    """Store the company, the invoice type, the cut-off and the columns on the session, which
    becomes Mapped. Raises OpeningInvoicesProblem, listing every wrong column at once."""
    if session.status not in ("File Read", "Mapped", "Dry Run Failed", "Ready to Import"):
        raise OpeningInvoicesProblem(
            _("This session is {0}, so it can't be set up again.").format(_(session.status))
        )
    options = frappe.parse_json(session.template_options or "{}") or {}
    if (options.get("opening_stock") or {}).get("created"):
        raise OpeningInvoicesProblem(
            _("This session brought in opening stock. Start a new session for the invoices.")
        )
    if (options.get("opening_balances") or {}).get("created"):
        raise OpeningInvoicesProblem(
            _("This session brought in opening balances. Start a new session for the invoices.")
        )
    earlier = settings(session)
    if earlier.get("created") and earlier.get("invoice_type") != invoice_type:
        raise OpeningInvoicesProblem(
            _("This session already made {0} invoices. Start a new session for the other kind.").format(
                _(earlier["invoice_type"])
            )
        )
    if earlier.get("created") and earlier.get("company") != company:
        raise OpeningInvoicesProblem(
            _(
                "This session already made invoices for {0}. Start a new session for the other company."
            ).format(earlier["company"])
        )
    problem = setup_problem(company, invoice_type, cut_off)
    if problem:
        raise OpeningInvoicesProblem(problem)

    doctype, party_type = INVOICE_DOCTYPES[invoice_type], PARTY_TYPES[invoice_type]
    headers = session_headers(session)
    mapping, extra, given, problems = {}, {}, set(), []
    for column, field in (columns or {}).items():
        if column not in headers:
            problems.append(_("There is no column '{0}'. Columns: {1}.").format(column, ", ".join(headers)))
        elif field not in FIELDS:
            problems.append(_("'{0}' can't be mapped. Map columns to: {1}.").format(field, ", ".join(FIELDS)))
        else:
            given.add(field)
            if field in MAPPED:
                mapping[str(headers.index(column))] = PARTY_FIELDS[party_type] if field == "party" else field
            else:
                extra[field] = headers.index(column)
    missing = [field for field in REQUIRED_FIELDS if field not in given]
    if missing:
        problems.append(_("Map a column to each of: {0}.").format(", ".join(missing)))
    if problems:
        raise OpeningInvoicesProblem(" ".join(problems))
    for position in range(len(headers)):
        mapping.setdefault(str(position), "Don't Import")

    invoices = {
        "company": company,
        "invoice_type": invoice_type,
        "doctype": doctype,
        "party_type": party_type,
        "cut_off": str(getdate(cut_off)),
        "temporary_opening_account": temporary_account(company),
        "currency": frappe.get_cached_value("Company", company, "default_currency"),
        "columns": extra,
    }
    for kept in ("created", "failed"):  # what earlier imports made stays on the session
        if earlier.get(kept):
            invoices[kept] = earlier[kept]
    for other in ("opening_stock", "opening_balances"):  # a session is one kind of special import
        options.pop(other, None)
    options["opening_invoices"] = invoices
    session.template_options = frappe.as_json(options)
    session.import_type = "Insert New Records"
    save_mapping(
        session,
        doctype,
        mapping,
        _("Opening {0} invoices for {1}, cut-off {2}, against {3}.").format(
            _(invoice_type), company, invoices["cut_off"], invoices["temporary_opening_account"]
        ),
    )
    return {"opening_invoices": invoices, "column_to_field_map": opening_stock.shown_mapping(mapping, extra)}


def check_can_run(session) -> None:
    from frappe_assistant_core.utils import import_dry_run as dry_run

    dry_run.check_status(session)
    invoices = settings(session)
    problem = setup_problem(invoices.get("company"), invoices.get("invoice_type"), invoices.get("cut_off"))
    if problem:
        raise dry_run.DryRunProblem(problem)
    if not session.source_file:
        raise dry_run.DryRunProblem(
            _("The file {0} is only in the chat. Upload it in File Manager and pass its file_id.").format(
                session.file_name
            )
        )


def run(session_name: str, commit_progress: bool = False) -> Dict[str, Any]:
    """The dry run of an opening-invoices session: every row checked, ERPNext's own validation of
    the ready rows, the result stored the dry run's way, with the totals."""
    from frappe_assistant_core.utils import import_dry_run as dry_run

    session = dry_run.engine_session(session_name)
    invoices = settings(session)
    file_doc = readable_session_file(session)
    checker = _InvoiceChecker(invoices["doctype"])
    ready = _check_lines(session, checker)
    # ERPNext can't check an invoice whose party an earlier file of the plan brings until it is there.
    waiting = [line for line in ready if line.after_file]
    ready = _erpnext_check(session, [line for line in ready if not line.after_file], checker, commit_progress)
    ready += waiting
    for line in ready:
        waits = {"after_files": [line.after_file], "needs": [line.party]} if line.after_file else {}
        checker.mark(line.row, "ready", **waits)
    checker.rows.sort(key=lambda r: r["row"])
    summary = dry_run._store(session_name, file_doc, checker, len(checker.rows))
    summary["opening_invoices"] = _totals(invoices, ready)
    frappe.db.set_value(
        dry_run.SESSION_DOCTYPE,
        session_name,
        "validation_summary",
        frappe.as_json(summary),
        update_modified=False,
    )
    return summary


# -- reading the file ------------------------------------------------------------------------

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ]|$)")


def date_of(text) -> Optional[str]:
    """A date as the file writes it, as YYYY-MM-DD; None when blank. ISO dates are read as ISO;
    others day first when the site writes dates day first. Raises ValueError otherwise."""
    text = cstr(text).strip()
    if not text:
        return None
    if ISO_DATE.match(text):  # dateutil would read 2026-03-04 as 3 April when day first
        return str(datetime.date.fromisoformat(text[:10]))
    from frappe.utils.data import get_user_date_format

    day_first = get_user_date_format().lower().startswith("dd")
    try:
        return str(date_parser.parse(text, dayfirst=day_first).date())
    except (ValueError, OverflowError) as e:
        raise ValueError(text) from e


def is_totals_row(cells: Dict[str, str]) -> bool:
    party = cstr(cells.get("party")).strip()
    has_amount = bool(cstr(cells.get("outstanding_amount")).strip())
    return has_amount and (not party or bool(opening_stock.TOTALS.match(party)))


def _found_party(party_type: str, value: str):
    """find_party, once per request for a party found: invoice_key asks for every unnumbered row,
    several times a check (#34541). A party not found is asked again, as one may be created."""
    found = getattr(frappe.local, "fac_found_parties", None)
    if found is None:
        found = frappe.local.fac_found_parties = {}
    key = (party_type, value.casefold())
    if key not in found:
        party = find_party(party_type, value)
        if not party:
            return None
        found[key] = party
    return found[key]


def invoice_key(invoices: Dict[str, Any], cells: Dict[str, str]) -> str:
    """What says a row is in, matched against the invoices earlier imports made: the invoice
    number (with the supplier for purchases, as suppliers reuse numbers), or, without one, the
    party, date and amount as they resolve: the party's name, the ISO date and the amount to the
    currency's decimals, so a value map or a date written another way still finds it (#34434).
    Never the row's number: the sheet can change."""
    party = cstr(cells.get("party")).strip().casefold()
    number = cstr(cells.get("invoice_number")).strip().casefold()
    if number:
        return f"{party}|{number}" if invoices.get("invoice_type") == "Purchase" else number
    kind = "Purchase" if invoices.get("invoice_type") == "Purchase" else "Sales"
    party_type = invoices.get("party_type") or ("Supplier" if kind == "Purchase" else "Customer")
    found = _found_party(party_type, cstr(cells.get("party")).strip())
    if found:
        party = found.name.casefold()
    date, amount = cstr(cells.get("posting_date")).strip(), cstr(cells.get("outstanding_amount")).strip()
    try:
        date = date_of(date) or ""
    except ValueError:
        pass  # not a date: the row fails its check, and the key keeps the text
    try:
        precision = (
            frappe.get_precision(invoices.get("doctype") or INVOICE_DOCTYPES[kind], "outstanding_amount") or 2
        )
        amount = f"{flt(opening_stock.number(amount), precision):.{precision}f}"
    except ValueError:
        pass
    return f"{party}|{date}|{amount}"


def read_lines(session) -> List[opening_stock.Line]:
    """Every non-blank row of the session's sheet, as field -> text, with value maps applied."""
    from frappe_assistant_core.utils.import_dry_run import column_to_field_map
    from frappe_assistant_core.utils.import_fixes import apply_value_maps

    invoices = settings(session)
    party_field = PARTY_FIELDS[invoices["party_type"]]
    file_doc = readable_session_file(session)
    rows = apply_value_maps(session, read_sheet_rows(file_doc, session.sheet or None))
    positions = {
        int(position): "party" if target == party_field else target
        for position, target in column_to_field_map(session).items()
        if str(position).isdigit() and target in (party_field, *MAPPED)
    }
    positions.update({int(p): f for f, p in (invoices.get("columns") or {}).items()})
    lines, typed = [], opening_stock.typed_file(session, file_doc)
    for index, row in enumerate(rows[1:], start=2):
        cells = opening_stock.cell_texts(file_doc, row, positions, typed)
        if any(cells.values()):
            lines.append(opening_stock.Line(index, cells))
    return lines


# -- checking the rows -----------------------------------------------------------------------

CAUSE_PARTY_DISABLED = "Party disabled"
CAUSE_FOREIGN_CURRENCY = "Party in another currency"
CAUSE_NOT_POSITIVE = "Not a positive amount"
CAUSE_NO_FISCAL_YEAR = "Date in no fiscal year"
CAUSE_DUE_BEFORE = "Due before the invoice date"
CAUSE_NUMBER_TWICE = "Invoice number twice"
CAUSE_NUMBER_USED = "Invoice number already used"
CAUSE_AFTER_CUTOFF = "Dated after the cut-off"
CAUSE_ALREADY_OPENED = "Opening invoice already in ERPNext"
NEW_CAUSES = (
    CAUSE_PARTY_DISABLED,
    CAUSE_FOREIGN_CURRENCY,
    CAUSE_NOT_POSITIVE,
    CAUSE_NO_FISCAL_YEAR,
    CAUSE_DUE_BEFORE,
    CAUSE_NUMBER_TWICE,
    CAUSE_NUMBER_USED,
    CAUSE_AFTER_CUTOFF,
    CAUSE_ALREADY_OPENED,
)
# One group per cause, so "12 rows are dated in no fiscal year" is one decision. A disabled party is
# one group per party, because the fix (a party to map to) depends on which party it is.
BY_VALUE = (CAUSE_PARTY_DISABLED,)
LABELS = {
    "outstanding_amount": "Outstanding Amount",
    "invoice_number": "Invoice Number",
    "posting_date": "Invoice Date",
    "due_date": "Due Date",
}


@dataclass
class Ready:
    row: int
    party: str
    amount: float
    posting_date: str
    due_date: str
    invoice_number: str = ""
    item_name: str = ""
    original_date: str = ""  # the file's date, when the invoice is posted at the cut-off
    key: str = ""
    after_file: str = ""  # in a migration plan: the earlier file that brings its party


class _InvoiceChecker(opening_stock._StockChecker):
    """Groups failures the dry run's way, so its results file, fixes and reply are reused."""

    def __init__(self, doctype: str):
        super().__init__()
        self.doctype = doctype


def _precision(invoices: Dict[str, Any]) -> int:
    return frappe.get_precision(invoices["doctype"], "outstanding_amount") or 2


def _problem(invoices: Dict[str, Any], cause: str, field: str, value: str, message: str):
    from frappe_assistant_core.utils import import_dry_run as dry_run

    by_value = cause in BY_VALUE or cause == dry_run.CAUSE_MISSING_LINK
    party_type = invoices["party_type"]
    target = PARTY_FIELDS[party_type] if field == "party" else field
    key = (cause, invoices["doctype"], target) + ((value,) if by_value else ())
    info = {
        "cause": cause,
        "parent": invoices["doctype"],
        "field": target,
        "label": _(party_type if field == "party" else LABELS[field]),
        "value": value if by_value else None,
        "message": message,
    }
    return key, info


def find_party(party_type: str, text: str):
    """The party named ``text``, or the only one whose customer or supplier name it is."""
    if not text:
        return None
    fields = ["name", "disabled", "default_currency"]
    found = frappe.db.get_value(party_type, text, fields, as_dict=True)
    if found:
        return found
    matches = frappe.get_all(
        party_type, filters={PARTY_NAME_FIELDS[party_type]: text}, fields=fields, limit=2
    )
    return matches[0] if len(matches) == 1 else None


def _fiscal_years(company: str):
    known: Dict[str, bool] = {}

    def has_year(date: str) -> bool:
        if date not in known:
            known[date] = in_fiscal_year(date, company)
        return known[date]

    return has_year


def _line_problem(
    line: opening_stock.Line, invoices: Dict[str, Any], post_at_cutoff: bool, has_year, coming=None
):
    """The line's problem as (key, info), or the Ready line. ``coming``: in a migration plan, the
    records its earlier files bring (import_plan.planned_names)."""
    from frappe_assistant_core.utils import import_dry_run as dry_run

    cells = line.cells
    if is_totals_row(cells):
        return (opening_stock.CAUSE_TOTALS_ROW,), {
            "cause": opening_stock.CAUSE_TOTALS_ROW,
            "message": _("A totals row, not an invoice."),
        }
    text = cells.get("outstanding_amount", "")
    try:
        amount = flt(opening_stock.number(text), _precision(invoices))
    except ValueError:
        return _problem(
            invoices,
            dry_run.CAUSE_BAD_VALUE,
            "outstanding_amount",
            text,
            _("'{0}' isn't a number.").format(text),
        )
    dates = {}
    for name in ("posting_date", "due_date"):
        try:
            dates[name] = date_of(cells.get(name))
        except ValueError:
            return _problem(
                invoices,
                dry_run.CAUSE_BAD_DATE,
                name,
                cells[name],
                _("'{0}' isn't a date.").format(cells[name]),
            )

    party_type, given = invoices["party_type"], cells.get("party", "")
    party = find_party(party_type, given)
    brought = (
        (coming or {}).get(party_type, {}).get(given.strip().casefold()) if given and not party else None
    )
    if brought:
        # An earlier file of the plan creates it: the line is checked without it now, and again in
        # full just before its file is imported, as the plan checks every file then.
        party = frappe._dict(name=given, brought_by=brought)
    if not party:
        return _problem(
            invoices,
            dry_run.CAUSE_MISSING_LINK,
            "party",
            given,
            _("{0} '{1}' doesn't exist.").format(_(party_type), given),
        )
    if party.disabled:
        return _problem(
            invoices, CAUSE_PARTY_DISABLED, "party", given, _("{0} is disabled.").format(party.name)
        )
    if party.default_currency and party.default_currency != invoices["currency"]:
        return _problem(
            invoices,
            CAUSE_FOREIGN_CURRENCY,
            "party",
            given,
            _("The party's currency isn't {0}; foreign-currency invoices aren't brought in here.").format(
                invoices["currency"]
            ),
        )
    if amount <= 0:
        return _problem(
            invoices,
            CAUSE_NOT_POSITIVE,
            "outstanding_amount",
            text,
            _("Nothing is owed: credit notes and advances aren't brought in here."),
        )

    file_date = dates["posting_date"] or invoices["cut_off"]
    if file_date > invoices["cut_off"]:
        # What was owed at the cut-off can't be dated after it: an invoice after the cut-off is
        # new business, entered in ERPNext itself, and posting it here would count it twice.
        return _problem(
            invoices,
            CAUSE_AFTER_CUTOFF,
            "posting_date",
            cells.get("posting_date", ""),
            _("The invoice is dated after the cut-off ({0}), so it wasn't owed at the cut-off.").format(
                invoices["cut_off"]
            ),
        )
    posting, due, original = file_date, dates["due_date"] or file_date, ""
    if not has_year(posting):
        if not post_at_cutoff:
            return _problem(
                invoices,
                CAUSE_NO_FISCAL_YEAR,
                "posting_date",
                cells.get("posting_date", ""),
                _("The invoice date is in no fiscal year of {0}.").format(invoices["company"]),
            )
        # ERPNext refuses a due date before the posting date, so an earlier one moves up too.
        posting, original = invoices["cut_off"], file_date
        due = max(due, posting)
    if due < posting:
        return _problem(
            invoices,
            CAUSE_DUE_BEFORE,
            "due_date",
            cells.get("due_date", ""),
            _("The due date is before the invoice date."),
        )
    return Ready(
        line.row,
        party.name,
        amount,
        posting,
        due,
        cells.get("invoice_number", ""),
        cells.get("item_name", ""),
        original,
        after_file=party.brought_by or "",
    )


def _number_used(invoices: Dict[str, Any], line: Ready) -> bool:
    if invoices["invoice_type"] == "Sales":
        return bool(frappe.db.exists(invoices["doctype"], line.invoice_number))
    return bool(
        frappe.db.exists(
            invoices["doctype"],
            {"supplier": line.party, "bill_no": line.invoice_number, "docstatus": ["<", 2]},
        )
    )


def _already_opened(invoices: Dict[str, Any], own: set):
    """How many submitted opening invoices ERPNext already has for a party, date and amount,
    leaving out ``own`` (this session's invoices that a row of the file finds by its key): an
    invoice without a number is known only by those, so the same file brought in by another
    session, or a row whose key changed, would otherwise post it twice."""
    known: Dict[tuple, int] = {}
    precision = _precision(invoices)

    def count(line: Ready) -> int:
        key = (line.party, line.posting_date, flt(line.amount, precision))
        if key not in known:
            known[key] = sum(
                1
                for invoice in frappe.get_all(
                    invoices["doctype"],
                    filters={
                        "company": invoices["company"],
                        PARTY_FIELDS[invoices["party_type"]]: line.party,
                        "posting_date": line.posting_date,
                        "is_opening": "Yes",
                        "docstatus": 1,
                    },
                    fields=["name", "grand_total"],
                )
                if invoice.name not in own and flt(invoice.grand_total, precision) == key[2]
            )
        return known[key]

    return count


def _post_at_cutoff(session) -> bool:
    rules = frappe.parse_json(session.transformation_rules or "{}") or {}
    return bool(rules.get("post_at_cutoff"))


def _check_lines(
    session, checker: _InvoiceChecker, lines: Optional[List[opening_stock.Line]] = None
) -> List[Ready]:
    from frappe_assistant_core.utils import import_dry_run as dry_run
    from frappe_assistant_core.utils import import_plan

    invoices, excluded, coming = (
        settings(session),
        dry_run._excluded_rows(session),
        import_plan.planned_names(session),
    )
    post, has_year, imported = (
        _post_at_cutoff(session),
        _fiscal_years(invoices["company"]),
        imported_keys(session),
    )
    lines = read_lines(session) if lines is None else lines
    keys, counts = {}, {}
    for line in lines:
        base = invoice_key(invoices, line.cells)
        counts[base] = counts.get(base, 0) + 1
        # the same invoice twice without numbers
        keys[line.row] = base if line.cells.get("invoice_number") else f"{base}#{counts[base]}"
    # This session's own invoices count too, but for those a row of the file finds by its key: a
    # key that no longer finds its invoice would otherwise post it twice (#34434).
    found = set(keys.values())
    created = invoices.get("created") or {}
    opened = _already_opened(invoices, {name for name, entry in created.items() if entry.get("key") in found})
    ready, first_of, seen = [], {}, {}
    for line in lines:
        numbered = bool(line.cells.get("invoice_number"))
        key = keys[line.row]
        if line.row in excluded:
            checker.mark(line.row, "excluded")
            continue
        if key in imported:
            checker.mark(line.row, "imported")
            continue
        first = first_of.setdefault(key, line.row) if numbered else line.row
        outcome = _line_problem(line, invoices, post, has_year, coming)
        if not isinstance(outcome, Ready):
            checker.fail(line.row, *outcome)
            continue
        outcome.key = key
        if first != line.row:
            checker.fail(
                line.row,
                *_problem(
                    invoices,
                    CAUSE_NUMBER_TWICE,
                    "invoice_number",
                    outcome.invoice_number,
                    _("The same invoice number is in row {0} too.").format(first),
                ),
            )
            continue
        if not numbered:
            same = (outcome.party, outcome.posting_date, outcome.amount)
            seen[same] = seen.get(same, 0) + 1
            if seen[same] <= opened(outcome):
                checker.fail(
                    line.row,
                    *_problem(
                        invoices,
                        CAUSE_ALREADY_OPENED,
                        "outstanding_amount",
                        line.cells.get("outstanding_amount", ""),
                        _("ERPNext already has an opening invoice for this party, date and amount."),
                    ),
                )
                continue
        if numbered and _number_used(invoices, outcome):
            checker.fail(
                line.row,
                *_problem(
                    invoices,
                    CAUSE_NUMBER_USED,
                    "invoice_number",
                    outcome.invoice_number,
                    _("ERPNext already has this invoice number."),
                ),
            )
            continue
        ready.append(outcome)
    return ready


def _totals(invoices: Dict[str, Any], ready: List[Ready]) -> Dict[str, Any]:
    return {
        "invoice_type": invoices["invoice_type"],
        "party_type": invoices["party_type"],
        "rows": len(ready),
        "parties": len({line.party for line in ready}),
        "total_amount": flt(sum(line.amount for line in ready), _precision(invoices)),
    }


def ready_lines(session) -> List[Ready]:
    """The lines that pass the row checks now."""
    return _check_lines(session, _InvoiceChecker(settings(session)["doctype"]))


def imported_keys(session) -> set:
    """The keys of the rows whose invoice an earlier import of this session made and is still
    submitted. Task 6 stores them in ``created``."""
    created = settings(session).get("created") or {}
    if not created:
        return set()
    submitted = set(
        frappe.get_all(
            settings(session)["doctype"],
            filters={"name": ["in", list(created)], "docstatus": 1},
            pluck="name",
        )
    )
    return {entry["key"] for name, entry in created.items() if name in submitted}


# -- the invoice, as ERPNext's tool makes it ---------------------------------------------------


def build_invoice(invoices: Dict[str, Any], line: Ready):
    """An unsaved opening invoice of ``line``, built by ERPNext's Opening Invoice Creation Tool's
    own code: one line of the outstanding amount against the Temporary Opening account, no stock,
    no taxes, rounding off. The tool itself is never saved."""
    tool = frappe.new_doc(TOOL)
    tool.company = invoices["company"]
    tool.invoice_type = invoices["invoice_type"]
    tool.create_missing_party = 0  # parties are created with the user's permissions, by create_document
    tool.append(
        "invoices",
        {
            "party": line.party,
            "qty": 1,
            "outstanding_amount": line.amount,
            "posting_date": line.posting_date,
            "due_date": line.due_date,
            "item_name": line.item_name or None,
            "temporary_opening_account": invoices["temporary_opening_account"],
            "invoice_number": line.invoice_number or None,
        },
    )
    data = tool.get_invoices()[0]
    data.pop("invoice_number", None)  # the tool passes it as the name; it isn't an invoice field
    if invoices["invoice_type"] == "Purchase" and line.invoice_number:
        data["bill_no"] = line.invoice_number
        data["bill_date"] = line.original_date or line.posting_date
    if line.original_date:
        data["remarks"] = _("Opening invoice {0}, dated {1} in the old system.").format(
            line.invoice_number, line.original_date
        )
    doc = frappe.get_doc(data)
    doc.flags.ignore_mandatory = True  # as ERPNext's tool inserts it
    doc.flags.dont_auto_add_taxes = True  # the outstanding amount already includes tax
    return doc


def make_invoice(invoices: Dict[str, Any], line: Ready):
    """Insert and submit the opening invoice of ``line``. The caller holds the savepoint."""
    doc = build_invoice(invoices, line)
    sales_number = line.invoice_number if invoices["invoice_type"] == "Sales" else None
    doc.insert(set_name=sales_number or None)
    doc.submit()
    return doc


SAVEPOINT = "fac_opening_invoice_check"


def _invoice_error(invoices: Dict[str, Any], line: Ready) -> Optional[Exception]:
    """None when ERPNext accepts ``line``'s invoice, inserted and submitted, else why not. Rolled back."""
    from frappe_assistant_core.utils import import_dry_run as dry_run

    frappe.clear_messages()
    with dry_run.held_back():
        frappe.db.savepoint(SAVEPOINT)
        try:
            make_invoice(invoices, line)
            return None
        except Exception as e:
            return e
        finally:
            frappe.db.rollback(save_point=SAVEPOINT)
            frappe.clear_messages()


def _erpnext_check(
    session, ready: List[Ready], checker: _InvoiceChecker, commit_progress: bool = False
) -> List[Ready]:
    """Each ready row's invoice, inserted and submitted inside a savepoint and rolled back:
    ERPNext's own validation, GL entries included. One group per message ERPNext gives."""
    from frappe_assistant_core.utils import import_dry_run as dry_run

    invoices, passed, total = settings(session), [], len(ready)
    for done, line in enumerate(ready, start=1):
        error = _invoice_error(invoices, line)
        if error is None:
            passed.append(line)
        else:
            kind, message = dry_run.refusal(error)
            checker.fail(
                line.row,
                (dry_run.CAUSE_REJECTED, kind, message),
                {"cause": dry_run.CAUSE_REJECTED, "error": kind, "message": message},
            )
        if commit_progress and done % dry_run.PROGRESS_EVERY == 0:
            frappe.db.set_value(
                dry_run.SESSION_DOCTYPE,
                session.name,
                "progress",
                dry_run._progress("running", done, total),
                update_modified=False,
            )
            dry_run.commit_progress_now()
    return passed


# -- missing parties (created by create_document, with import_session) -------------------------

PARTY_LINKS = {
    "Customer": {"customer_group": "Customer Group", "territory": "Territory"},
    "Supplier": {"supplier_group": "Supplier Group"},
}
PARTY_KIND_FIELDS = {"Customer": "customer_type", "Supplier": "supplier_type"}
DEFAULTS = {
    "customer_group": ("Selling Settings", "customer_group"),
    "territory": ("Selling Settings", "territory"),
    "supplier_group": ("Buying Settings", "supplier_group"),
}


def _leaf(doctype: str, name: str) -> bool:
    return bool(name) and bool(frappe.db.exists(doctype, {"name": name, "is_group": 0}))


def party_data(doctype: str, value: str) -> Dict[str, Any]:
    """The missing party as masters_plan proposes it: its name, a company, and the default group
    (and territory) from Selling or Buying Settings when that can hold records."""
    data = {PARTY_NAME_FIELDS[doctype]: value, PARTY_KIND_FIELDS[doctype]: "Company"}
    for field, link in PARTY_LINKS[doctype].items():
        default = frappe.db.get_single_value(*DEFAULTS[field])
        if _leaf(link, default) and frappe.has_permission(link, "read", doc=default):
            data[field] = default
    return data


def party_choices(doctype: str, data: Dict[str, Any]) -> Dict[str, List[str]]:
    """For each group or territory ``data`` lacks (the Settings default is a group node, so
    the plan can't propose it): the leaves the user may pick from, as far as they can read."""
    return {
        field: frappe.get_list(link, filters={"is_group": 0}, pluck="name", limit_page_length=20)
        for field, link in PARTY_LINKS[doctype].items()
        if field not in data
    }


def party_problem(doctype: str, data: Dict[str, Any]) -> Optional[str]:
    """Why ``data`` isn't a party masters_plan could have proposed, or None."""
    name_field, kind_field = PARTY_NAME_FIELDS[doctype], PARTY_KIND_FIELDS[doctype]
    allowed = {name_field, kind_field, *PARTY_LINKS[doctype]}
    others = sorted(set(data) - allowed)
    if others:
        return _("A missing {0} takes {1} only (as masters_plan's data has them), not {2}.").format(
            _(doctype), ", ".join(sorted(allowed)), ", ".join(others)
        )
    if not cstr(data.get(name_field)).strip():
        return _("Give the {0}'s {1}.").format(_(doctype), name_field)
    kinds = [o for o in cstr(frappe.get_meta(doctype).get_field(kind_field).options).split("\n") if o]
    if data.get(kind_field) and data[kind_field] not in kinds:
        return _("{0} is one of: {1}.").format(kind_field, ", ".join(kinds))
    for field, link in PARTY_LINKS[doctype].items():
        value = data.get(field)
        if value and (not _leaf(link, value) or not frappe.has_permission(link, "read", doc=value)):
            leaves = frappe.get_list(link, filters={"is_group": 0}, pluck="name", limit_page_length=20)
            return _("'{0}' isn't a {1} that can hold records. Some that can: {2}.").format(
                value, _(link), ", ".join(leaves)
            )
    return None


# -- creating --------------------------------------------------------------------------------

JOB = "fac_opening_invoices::{0}"
CREATE_SAVEPOINT = "fac_opening_invoice_create"
RECORD_DOCTYPE = "FAC Import Session Record"
DONE = ("Importing", "Completed", "Partially Completed", "Failed")


def check_card(session, company, invoice_type, rows, total_amount) -> None:
    """The approval card shows what FACO passed: refuse unless it is what the last check found."""
    summary = frappe.parse_json(session.validation_summary or "{}") or {}
    totals, invoices = summary.get("opening_invoices") or {}, settings(session)
    precision = _precision(invoices)
    checked = (
        invoices.get("company"),
        invoices.get("invoice_type"),
        summary.get("ready"),
        flt(totals.get("total_amount"), precision),
    )
    try:
        asked = (cstr(company).strip(), cstr(invoice_type).strip(), int(rows), flt(total_amount, precision))
    except (TypeError, ValueError):
        asked = None
    if asked != checked:
        raise OpeningInvoicesProblem(
            _(
                "The last check found {2} {1} invoices for {0}, {3} in all. Pass those, so the approval "
                "card shows them."
            ).format(*checked)
        )


def _message_of_create(e: Exception) -> str:
    from frappe_assistant_core.utils import import_dry_run as dry_run

    return _("ERPNext refused the invoice: {0}").format(dry_run._message_of(e))


def _progress(state: str, done: int, total: int) -> str:
    return frappe.as_json(
        {
            "step": "Import",
            "state": state,
            "done": done,
            "total": total,
            "updated_on": str(frappe.utils.now_datetime()),
        }
    )


def create(session) -> None:
    """Create and submit the ready rows' invoices, each all or nothing: in this request up to
    REQUEST_LIMIT, else in a background job. Rows an earlier import made are already left out by
    the check, so calling again never duplicates."""
    from frappe_assistant_core.utils import import_fixes

    if session.status in DONE:
        return  # running, or done: the caller reports
    if session.status != "Ready to Import" or not import_fixes.checked_as_is(session):
        raise OpeningInvoicesProblem(
            _(
                "The sheet isn't ready, or it changed since its last check. Check it with dry_run_import first."
            )
        )
    lines = ready_lines(session)
    expected = (frappe.parse_json(session.validation_summary or "{}") or {}).get("ready")
    if not lines:
        raise OpeningInvoicesProblem(_("Nothing to import: every row is already imported or left out."))
    if len(lines) != expected:
        raise OpeningInvoicesProblem(
            _(
                "The invoices changed since the last check: {0} rows are ready now, not {1}. Check it "
                "again with dry_run_import."
            ).format(len(lines), expected)
        )
    options = frappe.parse_json(session.template_options or "{}") or {}
    options["opening_invoices"]["failed"] = {}  # this import's failures replace the last one's
    session.template_options = frappe.as_json(options)
    session.status = "Importing"
    session.progress = _progress("queued", 0, len(lines))
    session.save()
    if len(lines) > REQUEST_LIMIT:
        frappe.enqueue(
            f"{__name__}.create_job",
            queue="long",
            timeout=4 * 60 * 60,
            job_id=JOB.format(session.name),
            deduplicate=True,
            enqueue_after_commit=True,
            now=bool(frappe.flags.in_test),
            session_name=session.name,
            user=frappe.session.user,
        )
        return
    _import(session.name, lines, commit=False)  # the request commits when it returns


def _commits() -> bool:
    """Whether the import commits its own batches (not under tests, which roll back at the end)."""
    return not frappe.flags.in_test


def create_job(session_name: str, user: str) -> None:
    """Background job: the invoices, as the user who approved them."""
    from frappe_assistant_core.utils import import_dry_run as dry_run
    from frappe_assistant_core.utils import import_fixes

    frappe.set_user(user)  # nosemgrep: frappe-setuser — the job runs as the user who approved the import
    try:
        session = dry_run.engine_session(session_name)
        lines = ready_lines(session)
        # What the user approved is what the last check found: the same rows, and nothing the
        # check depends on changed since (the fingerprint leaves out the failures create() reset).
        approved = (frappe.parse_json(session.validation_summary or "{}") or {}).get("ready")
        if len(lines) != approved or not import_fixes.checked_as_is(session):
            _stopped(session_name, _("the sheet changed after it was approved; check it again."))
            if _commits():
                frappe.db.commit()  # nosemgrep: frappe-manual-commit — a background job commits its own work
            return
        _import(session_name, lines, commit=True)
    except Exception as e:
        if not _commits():
            raise
        frappe.db.rollback()  # back to the last batch committed, with its record on the session
        _stopped(session_name, _message_of_create(e))
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — a background job commits its own work
        frappe.log_error(title=_("FAC opening invoices import failed"), message=frappe.get_traceback())
    finally:
        from frappe_assistant_core.utils import import_plan

        import_plan.child_finished(session_name)  # in a migration plan, its next file


def _record(session_name: str, position: int, doctype: str, name: str) -> None:
    """List an invoice on the session (Created Records) without saving the whole session again."""
    from frappe_assistant_core.utils import import_dry_run as dry_run

    frappe.get_doc(
        {
            "doctype": RECORD_DOCTYPE,
            "parent": session_name,
            "parenttype": dry_run.SESSION_DOCTYPE,
            "parentfield": "created_records",
            "idx": position,
            "record_doctype": doctype,
            "record_name": name,
        }
    ).db_insert()


def _keep(session_name: str, created: Dict[str, Any], failed: Dict[str, Any], done: int, total: int) -> None:
    """What this import made and refused so far, on the session, in the same transaction as the invoices."""
    from frappe_assistant_core.utils import import_dry_run as dry_run

    options = frappe.parse_json(
        frappe.db.get_value(dry_run.SESSION_DOCTYPE, session_name, "template_options")
    )
    options["opening_invoices"]["created"] = created
    options["opening_invoices"]["failed"] = failed
    frappe.db.set_value(
        dry_run.SESSION_DOCTYPE,
        session_name,
        {"template_options": frappe.as_json(options), "progress": _progress("running", done, total)},
        update_modified=False,
    )


def _import(session_name: str, lines: List[Ready], commit: bool) -> None:
    from frappe_assistant_core.utils import import_dry_run as dry_run

    session = dry_run.engine_session(session_name)
    invoices = settings(session)
    created, failed = dict(invoices.get("created") or {}), {}
    position, total = len(session.created_records), len(lines)
    for done, line in enumerate(lines, start=1):
        # What the insert or submit queued for the commit goes with a refused invoice.
        marks = open_savepoint(CREATE_SAVEPOINT)
        try:
            doc = make_invoice(invoices, line)
            position += 1
            _record(session_name, position, invoices["doctype"], doc.name)
            created[doc.name] = {"row": line.row, "key": line.key, "amount": line.amount, "party": line.party}
        except Exception as e:
            rollback_to_savepoint(CREATE_SAVEPOINT, marks, invoices["doctype"], None)
            failed[str(line.row)] = {
                "message": _message_of_create(e),
                "error": type(e).__name__,
                "amount": line.amount,
                "party": line.party,
            }
        finally:
            frappe.clear_messages()
        if done % COMMIT_EVERY == 0 or done == total:
            _keep(session_name, created, failed, done, total)
            if commit and _commits():
                frappe.db.commit()  # nosemgrep: frappe-manual-commit — a background job commits its own work
    _finish(session_name, total, failed)
    if commit and _commits():
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — a background job commits its own work


def _finish(session_name: str, total: int, failed: Dict[str, Any]) -> None:
    from frappe_assistant_core.utils import import_dry_run as dry_run

    session = dry_run.engine_session(session_name)
    made = total - len(failed)
    if not failed:
        session.status = "Completed"
    else:
        session.status = "Partially Completed" if settings(session).get("created") else "Failed"
    session.progress = _progress("done", total, total)
    session.log_step(
        "Import",
        "Success" if not failed else ("Warning" if made else "Failed"),
        _("{0} opening invoices created, {1} rows refused.").format(made, len(failed)),
        rows_ok=made,
        rows_failed=len(failed),
    )
    session.save()


def _stopped(session_name: str, reason: str) -> None:
    """A background import that stopped before its end: what it committed is in."""
    from frappe_assistant_core.utils import import_dry_run as dry_run

    if frappe.db.get_value(dry_run.SESSION_DOCTYPE, session_name, "status") != "Importing":
        return  # it finished (or was stopped already) in the meantime
    session = dry_run.engine_session(session_name)
    session.status = "Partially Completed" if settings(session).get("created") else "Failed"
    last = frappe.parse_json(session.progress or "{}") or {}
    session.progress = _progress("stopped", last.get("done") or 0, last.get("total") or 0)
    session.log_step(
        "Import",
        "Failed",
        _("The import stopped: {0} Check the file again to import the rest.").format(reason),
    )
    session.save()


# -- the report ------------------------------------------------------------------------------

STALL_SECONDS = 600  # a background import silent this long, with no job, has stopped
DIFFERENCES_SHOWN = 50


def _job_running(session) -> bool:
    from frappe_assistant_core.utils.import_run import job_alive

    try:
        return job_alive(JOB.format(session.name))
    except Exception:
        return True  # the queue can't be asked (Redis down, say): don't call the job stopped


def _settle(session) -> None:
    """An import still Importing with no job behind it and no progress for a while has stopped
    (the worker was restarted, say): say so, keeping what it committed."""
    if session.status != "Importing" or _job_running(session):
        return
    progress = frappe.parse_json(session.progress or "{}") or {}
    updated = progress.get("updated_on")
    if updated and frappe.utils.time_diff_in_seconds(frappe.utils.now_datetime(), updated) <= STALL_SECONDS:
        return
    _stopped(session.name, _("the background job stopped."))
    session.reload()


def _failed_groups(failed: Dict[str, Any], precision: int) -> List[Dict[str, Any]]:
    from frappe_assistant_core.utils.import_fixes import row_ranges

    groups: Dict[str, Dict[str, Any]] = {}
    for row, entry in sorted(failed.items(), key=lambda item: int(item[0])):
        group = groups.setdefault(
            entry["message"],
            {"message": entry["message"], "error": entry.get("error"), "rows": [], "amount": 0},
        )
        group["rows"].append(int(row))
        group["amount"] += flt(entry.get("amount"))
    return [
        {**g, "amount": flt(g["amount"], precision), "count": len(g["rows"]), "rows": row_ranges(g["rows"])}
        for g in groups.values()
    ]


def _file_amounts(session, precision: int) -> Optional[Dict[str, float]]:
    """The file's total over every invoice row, and over the rows imported, read from the file
    now; None when it can't be read."""
    from frappe_assistant_core.utils.import_session import FileProblem
    from frappe_assistant_core.utils.import_signoff import tally

    try:
        return tally(outcomes(session), ("amount",), precision)["amount"]
    except FileProblem:
        return None


def report(session) -> Dict[str, Any]:
    """The total of the invoices made, per party type, against the file's amounts for the rows
    imported and for the whole file, and each invoice that differs from its row; the rows refused
    and left out. An invoice's total is its grand total: a payment after go-live lowers what is
    outstanding, not what was brought in."""
    from frappe_assistant_core.utils import import_dry_run as dry_run
    from frappe_assistant_core.utils.import_fixes import left_out_report

    _settle(session)
    invoices = settings(session)
    doctype, party_type, precision = invoices["doctype"], invoices["party_type"], _precision(invoices)
    created = invoices.get("created") or {}
    erpnext = erpnext_side(session)
    totals_of = erpnext["by_name"]
    submitted = [n for n in created if n in totals_of]
    erpnext_total = erpnext["total"]
    amounts = _file_amounts(session, precision)
    # The file can't be read (deleted, say): the amounts the rows had when they were imported.
    imported_total = (
        amounts["imported"] if amounts else flt(sum(flt(created[n]["amount"]) for n in submitted), precision)
    )
    file_total = amounts["source"] if amounts else None
    differences = sorted(
        (
            {
                "row": created[n]["row"],
                "invoice": n,
                "party": created[n].get("party"),
                "file_amount": flt(created[n]["amount"], precision),
                "erpnext_amount": totals_of[n],
            }
            for n in submitted
            if totals_of[n] != flt(created[n]["amount"], precision)
        ),
        key=lambda d: d["row"],
    )
    left_out = dry_run._excluded_rows(session)  # refused, then left out: shown under left_out only
    failed = _failed_groups(
        {row: entry for row, entry in (invoices.get("failed") or {}).items() if int(row) not in left_out},
        precision,
    )
    progress = frappe.parse_json(session.progress or "{}") or {}
    gone = [n for n in created if n not in submitted]  # cancelled or deleted since
    refused = sum(g["count"] for g in failed)
    stopped = session.status in ("Partially Completed", "Failed") and progress.get("state") == "stopped"

    if session.status == "Importing":
        message = _("Creating the invoices in the background: {0} of {1} done.").format(
            progress.get("done", 0), progress.get("total", "?")
        )
    else:
        if stopped:
            message = _(
                "The import stopped after {0} invoices were created ({1} rows refused). "
                "Check the file again to import the rest."
            ).format(len(submitted), refused)
        elif not submitted and failed:
            message = _(
                "No invoices were created; {0} rows were refused by ERPNext: fix them and check the file again."
            ).format(refused)
        elif not submitted and session.status in ("Partially Completed", "Failed"):
            message = _("The import stopped before its end. Check the file again to import the rest.")
        else:
            message = ""
        if submitted:
            message += " " + _(
                "{0} opening {1} invoices in ERPNext, {2} against {3} in the file's rows."
            ).format(len(submitted), _(invoices["invoice_type"]), erpnext_total, imported_total)
            if file_total is not None and file_total != imported_total:
                message += " " + _("The whole file holds {0}: {1} isn't in.").format(
                    file_total, flt(file_total - imported_total, precision)
                )
            if len(differences) > DIFFERENCES_SHOWN:
                message += " " + _("{0} differ from the file; the first {1} of {0} are listed.").format(
                    len(differences), DIFFERENCES_SHOWN
                )
            elif differences:
                message += " " + _("{0} differ from the file; they are listed row by row.").format(
                    len(differences)
                )
            else:
                message += " " + _("Every invoice matches the file.")
            if failed and not stopped:
                message += " " + _(
                    "{0} rows were refused by ERPNext: fix them and check the file again."
                ).format(refused)
        if gone:
            message += " " + _("{0} invoices made earlier were cancelled or deleted since.").format(len(gone))
        message = message.strip()
    out = {
        "status": session.status,
        "invoice_type": invoices["invoice_type"],
        "doctype": doctype,
        "invoices": len(submitted),
        "totals": {
            party_type: {
                "file": file_total,
                "imported": imported_total,
                "erpnext": erpnext_total,
                "difference": flt(erpnext_total - imported_total, precision),
                "not_imported": None if file_total is None else flt(file_total - imported_total, precision),
                "outstanding_now": erpnext["outstanding_now"],
            }
        },
        "differences": differences[:DIFFERENCES_SHOWN],
        "differences_count": len(differences),
        "no_longer_submitted": [
            {"invoice": n, "row": created[n]["row"], "amount": flt(created[n]["amount"], precision)}
            for n in gone[:DIFFERENCES_SHOWN]
        ],
        "no_longer_submitted_count": len(gone),
        "failed": failed,
        "left_out": left_out_report(session),
        "message": message,
    }
    if session.status == "Importing":
        out["progress"] = progress
    return out


# -- every row, for the sign-off report (reads only) -------------------------------------------


def outcomes(session) -> List[Dict[str, Any]]:
    """Every row of the file and where it stands now: imported (its invoice is submitted), left
    out, failed (the check or ERPNext refused it, with why) or not imported yet, with its amount
    as the file writes it. Writes nothing."""
    from frappe_assistant_core.utils import import_fixes
    from frappe_assistant_core.utils.import_signoff import NOT_IMPORTED

    invoices = settings(session)
    lines = read_lines(session)
    checker = _InvoiceChecker(invoices["doctype"])
    _check_lines(session, checker, lines)
    messages = {g["id"]: g.get("message") or _(g["cause"]) for g in checker.groups.values()}
    marked = {entry["row"]: entry for entry in checker.rows}
    refused = invoices.get("failed") or {}
    left = {entry["row"]: entry["reason"] for entry in import_fixes.left_out(session)}
    out = []
    for line in lines:
        entry = marked.get(line.row) or {"status": "ready"}
        status, reason = entry["status"], ""
        if status == "failed":
            reason = "; ".join(messages.get(g, "") for g in entry.get("groups") or [])
        elif status == "excluded":
            reason = left.get(line.row) or _("Left out by the user")
        elif status == "ready" and str(line.row) in refused:
            status, reason = "failed", refused[str(line.row)]["message"]
        elif status == "ready":
            status, reason = "not_imported", _(NOT_IMPORTED)
        try:
            amount, unreadable = opening_stock.number(line.cells.get("outstanding_amount")), False
        except ValueError:
            amount, unreadable = None, True
        totals_row = is_totals_row(line.cells)
        out.append(
            {
                "row": line.row,
                "status": status,
                "reason": reason,
                "amount": None if totals_row else amount,
                "unreadable": unreadable,
                "totals_row": totals_row,
                "file_says": amount if totals_row else None,
            }
        )
    return out


def erpnext_side(session) -> Dict[str, Any]:
    """The invoices this session made that are still submitted: how many, their total (their
    grand total, which a payment after go-live doesn't change), and what is still outstanding."""
    invoices = settings(session)
    precision = _precision(invoices)
    created = invoices.get("created") or {}
    found = frappe.get_all(
        invoices["doctype"],
        filters={"name": ["in", list(created) or [""]]},
        fields=["name", "docstatus", "grand_total", "outstanding_amount"],
    )
    submitted = [r for r in found if r.docstatus == 1]
    return {
        "invoices": len(submitted),
        "total": flt(sum(flt(r.grand_total) for r in submitted), precision),
        "outstanding_now": flt(sum(flt(r.outstanding_amount) for r in submitted), precision),
        "no_longer_submitted": len(created) - len(submitted),
        "by_name": {r.name: flt(r.grand_total, precision) for r in submitted},
    }


def summary(session) -> Dict[str, Any]:
    """The sign-off report's view of this session: its rows and amounts per status, and ERPNext's
    total against the file's amount for the rows imported. Writes nothing."""
    from frappe_assistant_core.utils.import_signoff import tally

    invoices = settings(session)
    precision = _precision(invoices)
    out = tally(outcomes(session), ("amount",), precision)
    erpnext = erpnext_side(session)
    erpnext.pop("by_name")
    erpnext["difference"] = flt(erpnext["total"] - out["amount"]["imported"], precision)
    out.update(
        {
            "kind": "opening_invoices",
            "doctype": invoices["doctype"],
            "label": _("Opening {0}").format(_(invoices["doctype"])),
            "company": invoices["company"],
            "cut_off": invoices["cut_off"],
            "balance": "receivables" if invoices["invoice_type"] == "Sales" else "payables",
            "erpnext": erpnext,
        }
    )
    return out
