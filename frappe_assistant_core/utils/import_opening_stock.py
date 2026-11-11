# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Opening stock (#33996): the old system's closing stock becomes an Opening Stock Stock
Reconciliation at the cut-off date.

Stock Reconciliation has Allow Import off, and one holds every row of the file, so Data Import
isn't used. The session, the file reading, the grouped dry run, the fixes and the results file
are the import's own; this module adds the setup, the row checks, the creation and the report.
An opening-stock session keeps its settings in ``template_options.opening_stock``.
"""

import math
import re
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import erpnext
import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, getdate

from frappe_assistant_core.utils.import_mapping import save_mapping, session_headers
from frappe_assistant_core.utils.import_session import read_sheet_rows, readable_session_file
from frappe_assistant_core.utils.savepoint import open_savepoint, rollback_to_savepoint

TARGET = "Stock Reconciliation"
IMPORT_TOOL = "import_opening_stock"
ITEM_TABLE = "Stock Reconciliation Item"
PURPOSE = "Opening Stock"
DEFAULT_TIME = "23:59:59"
CHUNK_ROWS = 1000
ITEM_FIELDS = ("item_code", "warehouse", "qty", "valuation_rate", "amount", "batch_no", "serial_no")
EXTRA_FIELDS = ("uom", "expiry_date")  # read by this module; not Stock Reconciliation Item fields
REQUIRED_FIELDS = ("item_code", "warehouse", "qty")


class OpeningStockProblem(Exception):
    """Opening stock can't be set up, checked or created. The message is shown to the user."""


def settings(session) -> Dict[str, Any]:
    options = frappe.parse_json(session.template_options or "{}") or {}
    return dict(options.get("opening_stock") or {})


def is_opening_stock(session) -> bool:
    return bool(settings(session))


def setup_problem(company: str, posting_date: str, difference_account: Optional[str]) -> Optional[str]:
    """Why opening stock can't be set up with these values, or None."""
    if not frappe.has_permission(TARGET, "create") or not frappe.has_permission(TARGET, "submit"):
        return _(
            "Opening stock is created and submitted as a Stock Reconciliation, and you can't do both. "
            "A Stock Manager can import it."
        )
    if not company or not frappe.db.exists("Company", company):
        return _("Company {0} doesn't exist.").format(company)
    try:
        date = getdate(posting_date)
    except Exception:
        return _("'{0}' isn't a date. Give the cut-off date as YYYY-MM-DD.").format(posting_date)
    from erpnext.accounts.utils import FiscalYearError, get_fiscal_year

    try:
        get_fiscal_year(date, company=company)
    except FiscalYearError:
        return _("{0} isn't in any fiscal year of {1}. Create the fiscal year first.").format(date, company)
    if not difference_account:
        return _(
            "{0} has no Temporary Opening account. Name the Balance Sheet account the opening stock "
            "is posted against, as difference_account."
        ).format(company)
    account = frappe.db.get_value(
        "Account", difference_account, ["company", "is_group", "report_type"], as_dict=True
    )
    if not account or account.company != company or account.is_group:
        return _("{0} isn't an account of {1} that entries can be posted to.").format(
            difference_account, company
        )
    if erpnext.is_perpetual_inventory_enabled(company) and account.report_type != "Balance Sheet":
        return _(
            "Opening stock is posted against a Balance Sheet account, such as Temporary Opening; "
            "{0} is a Profit and Loss account."
        ).format(difference_account)
    return None


def default_difference_account(company: str) -> Optional[str]:
    return frappe.db.get_value("Account", {"company": company, "account_type": "Temporary", "is_group": 0})


def setup(
    session,
    company: str,
    posting_date: str,
    columns: Dict[str, str],
    posting_time: Optional[str] = None,
    difference_account: Optional[str] = None,
) -> Dict[str, Any]:
    """Store the company, cut-off, account and columns on the session, which becomes Mapped.
    Raises OpeningStockProblem, listing every wrong column at once."""
    if session.status not in ("File Read", "Mapped", "Dry Run Failed", "Ready to Import"):
        raise OpeningStockProblem(
            _("This session is {0}, so it can't be set up again.").format(_(session.status))
        )
    difference_account = difference_account or default_difference_account(company)
    problem = setup_problem(company, posting_date, difference_account)
    if problem:
        raise OpeningStockProblem(problem)

    headers = session_headers(session)
    mapping, extra, problems = {}, {}, []
    for column, field in (columns or {}).items():
        if column not in headers:
            problems.append(_("There is no column '{0}'. Columns: {1}.").format(column, ", ".join(headers)))
        elif field not in ITEM_FIELDS + EXTRA_FIELDS:
            problems.append(
                _("'{0}' can't be mapped. Map columns to: {1}.").format(
                    field, ", ".join(ITEM_FIELDS + EXTRA_FIELDS)
                )
            )
        elif field in ITEM_FIELDS:
            mapping[str(headers.index(column))] = f"items.{field}"
        else:
            extra[field] = headers.index(column)
    given = {target.split(".", 1)[1] for target in mapping.values()}
    missing = [field for field in REQUIRED_FIELDS if field not in given]
    if missing:
        problems.append(_("Map a column to each of: {0}.").format(", ".join(missing)))
    if "valuation_rate" not in given and "amount" not in given:
        problems.append(_("Map a column to valuation_rate or to amount (the stock value)."))
    if problems:
        raise OpeningStockProblem(" ".join(problems))
    for position in range(len(headers)):
        mapping.setdefault(str(position), "Don't Import")

    stock = {
        "company": company,
        "posting_date": str(getdate(posting_date)),
        "posting_time": posting_time or DEFAULT_TIME,
        "difference_account": difference_account,
        "perpetual": bool(erpnext.is_perpetual_inventory_enabled(company)),
        "columns": extra,
    }
    options = frappe.parse_json(session.template_options or "{}") or {}
    if (options.get("opening_invoices") or {}).get("created"):
        raise OpeningStockProblem(
            _("This session brought in opening invoices. Start a new session for the stock.")
        )
    if (options.get("opening_balances") or {}).get("created"):
        raise OpeningStockProblem(
            _("This session brought in opening balances. Start a new session for the stock.")
        )
    for other in ("opening_invoices", "opening_balances"):  # a session is one kind of special import
        options.pop(other, None)
    if settings(session).get("created"):  # what the earlier documents held stays on the session
        stock["created"] = settings(session)["created"]
    options["opening_stock"] = stock
    session.template_options = frappe.as_json(options)
    session.import_type = "Insert New Records"
    save_mapping(
        session,
        TARGET,
        mapping,
        _("Opening stock for {0} at {1} {2}, against {3}.").format(
            company, stock["posting_date"], stock["posting_time"], difference_account
        ),
    )
    return {"opening_stock": stock, "column_to_field_map": shown_mapping(mapping, extra)}


# -- reading the file ------------------------------------------------------------------------

TOTALS = re.compile(r"^\s*(grand\s*|sub\s*-?\s*)?totals?\s*:?\s*$", re.IGNORECASE)


@dataclass
class Line:
    row: int
    cells: Dict[str, str] = dataclass_field(default_factory=dict)


class Typed(str):
    """A cell's text as the user typed it, in a CSV. A workbook's number reaches the engine as
    Python writes it ('2.125'), so its point is always the decimal one; typed text is the user's
    own format, where '1.500' on a site that writes 1.500,00 is fifteen hundred."""


PRESET_FILE = "preset_file"  # template_options: the CSV a preset wrote for the session (start_import_session)


def shown_mapping(mapping: Dict[str, str], extra: Dict[str, int]) -> Dict[str, str]:
    """The column map as the reply shows it. A column the engine reads itself (an invoice number,
    a batch) is stored as Don't Import, Data Import's word for a column it doesn't take: shown
    so, the model told the user the column wasn't imported. It is shown by its field."""
    return {**mapping, **{str(position): field for field, position in extra.items()}}


def typed_file(session, file_doc) -> bool:
    """Whether the file's cells are the user's typing: a CSV, but not the one a preset
    wrote, whose numbers it already read and wrote as Python does ('2.125')."""
    if (file_doc.get_extension()[1] or "").lstrip(".").lower() != "csv":
        return False
    options = frappe.parse_json(session.template_options or "{}") or {}
    return options.get(PRESET_FILE) != file_doc.name


def cell_texts(file_doc, row: List[str], positions: Dict[int, str], typed: bool) -> Dict[str, str]:
    """Field -> the row's text in its column, marked Typed when ``typed`` (see typed_file)."""
    cells = {f: cstr(row[p]).strip() if p < len(row) else "" for p, f in positions.items()}
    return {f: Typed(v) if typed else v for f, v in cells.items()}


def decimal_comma() -> bool:
    """Whether the site writes decimals after a comma (System Settings' number format, as
    "#.###,##"). A format with one separator only groups: its decimals take the other one."""
    separators = [c for c in cstr(frappe.db.get_default("number_format") or "#,###.##") if c != "#"]
    if len(set(separators)) > 1:
        return separators[-1] == ","
    return bool(separators) and separators[0] == "."


def _grouped(text: str, group: str) -> bool:
    """Whether ``text`` is digits grouped by threes with ``group`` ('1,234,567'), or the Indian
    way: the last three, then twos ('12,34,567')."""
    g = re.escape(group)
    return bool(
        re.fullmatch(r"-?\d{1,3}(" + g + r"\d{3})+", text)
        or re.fullmatch(r"-?\d{1,2}(" + g + r"\d{2})*" + g + r"\d{3}", text)
    )


def number(text) -> Optional[float]:
    """A number as accountants write it: '1,250.50', '1.250,50', '(12)' for -12. None when blank.

    With both separators, the last one holds the decimals. With commas only, one comma is the
    decimal point where the site writes decimals after a comma or the thousands are grouped by
    spaces, and commas grouping by threes are thousands. Anything else raises ValueError rather
    than being read as another number: '12,5' on a site that writes 12.5 isn't taken for 125."""
    typed = isinstance(text, Typed)
    text = cstr(text).strip()
    spaced = bool(re.search(r"\d[ \u00a0']\d{3}", text))  # thousands grouped by spaces: '1 234,5'
    text = text.replace(" ", "").replace("\u00a0", "").replace("'", "")
    if not text:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    if "," in text and "." in text:
        point = "," if text.rindex(",") > text.rindex(".") else "."
        group = "." if point == "," else ","
        whole, _sep, decimals = text.rpartition(point)
        if not decimals.isdigit() or not (whole.lstrip("-").isdigit() or _grouped(whole, group)):
            raise ValueError(text)
        text = f"{whole.replace(group, '')}.{decimals}"
    elif "," in text:
        if text.count(",") == 1 and (decimal_comma() or spaced):
            text = text.replace(",", ".")
        elif _grouped(text, ","):
            text = text.replace(",", "")
        else:
            raise ValueError(text)
    elif text.count(".") > 1:
        if not _grouped(text, "."):
            raise ValueError(text)
        text = text.replace(".", "")
    elif typed and decimal_comma() and _grouped(text, "."):
        raise ValueError(text)  # '1.500' typed where the site writes 1.500,00: not taken for 1.5
    value = float(text)
    if not math.isfinite(value):  # float() reads 'nan' and 'inf'
        raise ValueError(text)
    return -value if negative else value


def is_totals_row(cells: Dict[str, str]) -> bool:
    item = cstr(cells.get("item_code")).strip()
    has_number = any(cstr(cells.get(f)).strip() for f in ("qty", "valuation_rate", "amount"))
    return has_number and (not item or bool(TOTALS.match(item)))


def read_lines(session) -> List[Line]:
    """Every non-blank row of the session's sheet, as field → text, with value maps applied."""
    from frappe_assistant_core.utils.import_dry_run import column_to_field_map
    from frappe_assistant_core.utils.import_fixes import apply_value_maps

    file_doc = readable_session_file(session)
    rows = apply_value_maps(session, read_sheet_rows(file_doc, session.sheet or None))
    positions = {
        int(position): target.split(".", 1)[1]
        for position, target in column_to_field_map(session).items()
        if str(position).isdigit() and target.startswith("items.")
    }
    positions.update({int(p): f for f, p in (settings(session).get("columns") or {}).items()})
    lines, typed = [], typed_file(session, file_doc)
    for index, row in enumerate(rows[1:], start=2):
        cells = cell_texts(file_doc, row, positions, typed)
        if any(cells.values()):
            lines.append(Line(index, cells))
    return lines


# -- checking the rows -----------------------------------------------------------------------

CAUSE_TOTALS_ROW = "Totals row"
CAUSE_NOT_STOCK = "Can't hold stock"
CAUSE_OTHER_COMPANY = "Warehouse of another company"
CAUSE_GROUP_WAREHOUSE = "Group warehouse"
CAUSE_NO_CONVERSION = "No UOM conversion"
CAUSE_NEGATIVE = "Negative quantity"
CAUSE_ZERO = "Zero quantity"
CAUSE_NO_RATE = "No valuation rate"
CAUSE_NEEDS_BATCH = "Batch needed"
CAUSE_NEEDS_SERIAL = "Serial numbers needed"
CAUSE_SERIAL_COUNT = "Serial numbers don't match the quantity"
CAUSE_SAME_ITEM = "Same item and warehouse"
CAUSE_HAS_STOCK = "Already has stock"
CAUSE_ROUNDED_RATE = "Value changed by rounding"
# ERPNext keeps a valuation rate to its field's precision, so a row is posted as qty x the rounded
# rate. Up to this many of the currency's smallest unit (1.00 at 2 decimals) from the file's value
# is rounding; further, the row needs a decision (#34435).
ROUNDING_UNITS = 100
NEW_CAUSES = (
    CAUSE_TOTALS_ROW,
    CAUSE_NOT_STOCK,
    CAUSE_OTHER_COMPANY,
    CAUSE_GROUP_WAREHOUSE,
    CAUSE_NO_CONVERSION,
    CAUSE_NEGATIVE,
    CAUSE_ZERO,
    CAUSE_NO_RATE,
    CAUSE_NEEDS_BATCH,
    CAUSE_NEEDS_SERIAL,
    CAUSE_SERIAL_COUNT,
    CAUSE_SAME_ITEM,
    CAUSE_HAS_STOCK,
    CAUSE_ROUNDED_RATE,
)
# Failures are one group per cause, so "4 rows can't hold stock" is one decision. These are one
# group per value, because the fix depends on the value: a name to map, an item to allow.
BY_VALUE = (CAUSE_NO_RATE, CAUSE_OTHER_COMPANY, CAUSE_GROUP_WAREHOUSE)
LABELS = {
    "item_code": "Item Code",
    "warehouse": "Warehouse",
    "qty": "Quantity",
    "valuation_rate": "Valuation Rate",
    "amount": "Amount",
}


@dataclass
class Ready:
    row: int
    item_code: str
    warehouse: str
    qty: float
    valuation_rate: float
    batch_no: str = ""
    serial_no: str = ""
    expiry_date: str = ""
    after_file: str = ""  # in a migration plan: the earlier file that brings its item
    file_value: Optional[float] = None  # the file's own value, before the rate was rounded (#34435)


def check_can_run(session) -> None:
    from frappe_assistant_core.utils import import_dry_run as dry_run

    dry_run.check_status(session)
    stock = settings(session)
    problem = setup_problem(stock.get("company"), stock.get("posting_date"), stock.get("difference_account"))
    if problem:
        raise dry_run.DryRunProblem(problem)
    if not session.source_file:
        raise dry_run.DryRunProblem(
            _("The file {0} is only in the chat. Upload it in File Manager and pass its file_id.").format(
                session.file_name
            )
        )


class _StockChecker:
    """Groups failures the dry run's way, so its results file, fixes and reply are reused."""

    def __init__(self):
        from frappe_assistant_core.utils import import_dry_run as dry_run

        self.doctype = TARGET
        self.key_df = None
        self.groups: Dict[tuple, Dict[str, Any]] = {}
        self.rows: List[Dict[str, Any]] = []
        self._group_of = dry_run._Checker._group
        self._id_of = dry_run._Checker._group_id

    def _group_id(self, key):
        return self._id_of(self, key)

    def fail(self, row: int, key: tuple, info: Dict[str, Any]) -> None:
        payload = SimpleNamespace(rows=[SimpleNamespace(row_number=row)])
        group_id = self._group_of(self, key, info, payload)
        self.rows.append({"row": row, "status": "failed", "groups": [group_id]})

    def mark(self, row: int, status: str, **extra) -> None:
        self.rows.append({"row": row, "status": status, **extra})


def _problem(cause: str, field: str, value: str, message: str):
    from frappe_assistant_core.utils import import_dry_run as dry_run

    by_value = cause in BY_VALUE or cause == dry_run.CAUSE_MISSING_LINK
    key = (cause, ITEM_TABLE, field) + ((value,) if by_value else ())
    info = {
        "cause": cause,
        "parent": ITEM_TABLE,
        "field": field,
        "label": _(LABELS[field]),
        "value": value if by_value else None,
        "message": message,
    }
    return key, info


def _warehouse(name: str, company: str):
    """The warehouse named ``name``, or the only one of ``company`` whose warehouse_name it is."""
    fields = ["name", "company", "is_group", "disabled"]
    found = frappe.db.get_value("Warehouse", name, fields, as_dict=True)
    if found:
        return found
    matches = frappe.get_all("Warehouse", filters={"warehouse_name": name, "company": company}, fields=fields)
    return matches[0] if len(matches) == 1 else None


def _conversion(item_code: str, uom: str) -> Optional[float]:
    return frappe.db.get_value(
        "UOM Conversion Detail", {"parent": item_code, "uom": uom}, "conversion_factor"
    )


def _has_stock(item_code: str, warehouse: str, posting_date: str) -> bool:
    if flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty")):
        return True
    return bool(
        frappe.db.exists(
            "Stock Ledger Entry",
            {
                "item_code": item_code,
                "warehouse": warehouse,
                "posting_date": [">", posting_date],
                "is_cancelled": 0,
            },
        )
    )


IMPORTED = object()  # a line whose item and warehouse an earlier document of the session holds


def _line_problem(
    line: Line, stock: Dict[str, Any], allowed_zero: set, imported: set = frozenset(), coming=None
):
    """The line's problem as (key, info), the Ready line, or IMPORTED. ``coming``: in a migration
    plan, the records its earlier files bring (import_plan.planned_names)."""
    from frappe_assistant_core.utils import import_dry_run as dry_run

    cells = line.cells
    if is_totals_row(cells):
        return (CAUSE_TOTALS_ROW,), {
            "cause": CAUSE_TOTALS_ROW,
            "message": _("A totals row, not an item."),
        }
    values = {}
    for name in ("qty", "valuation_rate", "amount"):
        try:
            values[name] = number(cells.get(name))
        except ValueError:
            return _problem(
                dry_run.CAUSE_BAD_VALUE, name, cells[name], _("'{0}' isn't a number.").format(cells[name])
            )
    for name in ("valuation_rate", "amount"):
        if (values[name] or 0) < 0:
            return _problem(
                dry_run.CAUSE_BAD_VALUE, name, cells[name], _("A negative valuation rate or value.")
            )

    code = cells.get("item_code", "")
    item = frappe.db.get_value(
        "Item",
        code,
        [
            "name",
            "disabled",
            "has_variants",
            "is_stock_item",
            "is_fixed_asset",
            "has_batch_no",
            "has_serial_no",
            "stock_uom",
        ],
        as_dict=True,
    )
    if not item:
        brought = (coming or {}).get("Item", {}).get(code.strip().casefold()) if code else None
        if not brought:
            return _problem(
                dry_run.CAUSE_MISSING_LINK, "item_code", code, _("Item '{0}' doesn't exist.").format(code)
            )
        # An earlier file of the plan creates it: the line is checked without it now, and again in
        # full just before its file is imported, as the plan checks every file then.
        item = frappe._dict(name=code, is_stock_item=1, brought_by=brought)
    given = cells.get("warehouse", "")
    warehouse = _warehouse(given, stock["company"])
    if not warehouse:
        return _problem(
            dry_run.CAUSE_MISSING_LINK, "warehouse", given, _("Warehouse '{0}' doesn't exist.").format(given)
        )
    if (item.name, warehouse.name) in imported:
        # In an earlier document: its stock is in, so it isn't checked again, and an item or
        # warehouse disabled since (as ERPNext allows with stock in it) doesn't undo that.
        return IMPORTED
    if item.disabled or item.has_variants or not item.is_stock_item or item.is_fixed_asset:
        return _problem(
            CAUSE_NOT_STOCK,
            "item_code",
            code,
            _("The item is disabled, a template, a fixed asset or not a stock item."),
        )
    if warehouse.company != stock["company"]:
        return _problem(
            CAUSE_OTHER_COMPANY,
            "warehouse",
            given,
            _("{0} belongs to {1}, not {2}.").format(warehouse.name, warehouse.company, stock["company"]),
        )
    if warehouse.is_group or warehouse.disabled:
        return _problem(
            CAUSE_GROUP_WAREHOUSE,
            "warehouse",
            given,
            _("{0} is a group or disabled, so it can't hold stock.").format(warehouse.name),
        )

    qty, rate, amount = values["qty"] or 0, values["valuation_rate"], values["amount"]
    uom = cstr(cells.get("uom", "")).strip()
    if uom and uom.casefold() != cstr(item.stock_uom).casefold():
        from frappe_assistant_core.utils.import_fixes import word_for

        # Live, 2026-11-06: "Mtr" for an item kept in Meter found no conversion and was left out
        uom = word_for("UOM", uom) or uom
    if uom and uom.casefold() != cstr(item.stock_uom).casefold() and not item.brought_by:
        factor = _conversion(item.name, uom)
        if not factor:
            return _problem(
                CAUSE_NO_CONVERSION,
                "item_code",
                code,
                _("The item has no conversion from the file's unit to its stock unit."),
            )
        qty, rate = qty * factor, (rate / factor if rate else rate)
    if qty < 0:
        return _problem(CAUSE_NEGATIVE, "qty", cells.get("qty", ""), _("Opening stock can't be negative."))
    if qty == 0:
        return _problem(CAUSE_ZERO, "qty", cells.get("qty", ""), _("There is no stock to bring in."))
    if not rate and amount:
        rate = amount / qty
    if not rate and item.name not in allowed_zero:
        return _problem(
            CAUSE_NO_RATE,
            "item_code",
            code,
            _("{0} has no valuation rate, so it would be valued at zero.").format(code),
        )
    if rate and amount:
        # The Value is what the books hold: a Rate beside it is often rounded for show (Tally's).
        rate = amount / qty
    file_value = 0.0
    if rate:
        # What ERPNext will post: the totals, the approval card and the document use it.
        precision = _rate_precision()
        kept = flt(rate, precision)
        file_value = amount or qty * rate
        posted = qty * kept
        if abs(posted - file_value) > rounding_allowed(_currency_precision()):
            return _problem(
                CAUSE_ROUNDED_RATE,
                "valuation_rate",
                cells.get("amount") or cells.get("valuation_rate", ""),
                _(
                    "ERPNext keeps a valuation rate to {0} decimals, so {1} x {2} would be posted as {3}, "
                    "not the file's {4}. Give the rate with at most {0} decimals, or ask an administrator "
                    "to raise the Currency Precision."
                ).format(precision, flt(qty), kept, flt(posted, 2), flt(file_value, 2)),
            )
        rate = kept

    batch = cells.get("batch_no", "")
    serials = [s for s in re.split(r"[\s,]+", cells.get("serial_no", "")) if s]
    if item.has_batch_no and not batch:
        return _problem(CAUSE_NEEDS_BATCH, "item_code", code, _("The item is tracked by batch."))
    if item.has_serial_no and not serials:
        return _problem(CAUSE_NEEDS_SERIAL, "item_code", code, _("The item is tracked by serial number."))
    if item.has_serial_no and len(serials) != qty:
        return _problem(
            CAUSE_SERIAL_COUNT,
            "item_code",
            code,
            _("The number of serial numbers differs from the quantity."),
        )
    if _has_stock(item.name, warehouse.name, stock["posting_date"]):
        return _problem(
            CAUSE_HAS_STOCK,
            "item_code",
            code,
            _("The item already has stock, or stock moves after the cut-off, in this warehouse."),
        )
    return Ready(
        line.row,
        item.name,
        warehouse.name,
        qty,
        flt(rate),
        batch,
        "\n".join(serials),
        cells.get("expiry_date", ""),
        item.brought_by or "",
        file_value,
    )


def _allowed_zero(session) -> set:
    rules = frappe.parse_json(session.transformation_rules or "{}") or {}
    return set(rules.get("zero_rate_items") or [])


def _check_lines(session, checker: _StockChecker, lines: Optional[List[Line]] = None) -> List[Ready]:
    from frappe_assistant_core.utils import import_dry_run as dry_run
    from frappe_assistant_core.utils import import_plan

    stock, excluded, allowed = settings(session), dry_run._excluded_rows(session), _allowed_zero(session)
    imported, coming = imported_keys(session), import_plan.planned_names(session)
    ready, seen = [], {}
    for line in read_lines(session) if lines is None else lines:
        if line.row in excluded:
            checker.mark(line.row, "excluded")
            continue
        outcome = _line_problem(line, stock, allowed, imported, coming)
        if outcome is IMPORTED:
            checker.mark(line.row, "imported")
            continue
        if not isinstance(outcome, Ready):
            checker.fail(line.row, *outcome)
            continue
        key = (outcome.item_code, outcome.warehouse, outcome.batch_no)
        if key in seen:
            checker.fail(
                line.row,
                *_problem(
                    CAUSE_SAME_ITEM,
                    "item_code",
                    outcome.item_code,
                    _("The same item is in this warehouse in row {0} too.").format(seen[key]),
                ),
            )
            continue
        seen[key] = line.row
        ready.append(outcome)
    return ready


def _rate_precision() -> int:
    """The decimals ERPNext keeps of an opening stock row's valuation rate."""
    return cint(frappe.new_doc("Stock Reconciliation Item").precision("valuation_rate"))


def _currency_precision() -> int:
    """The decimals of an opening stock row's amount: the company currency's."""
    return cint(frappe.get_precision(ITEM_TABLE, "amount") or 2)


def rounding_allowed(precision: int) -> float:
    """How far a row's posted value may be from the file's, as rounding, at ``precision``: never
    more than one whole unit, so a currency without decimals isn't allowed 100 (#34541)."""
    return flt(min(ROUNDING_UNITS * 10**-precision, 1), precision)


def _totals(ready: List[Ready]) -> Dict[str, Any]:
    """Per warehouse: the quantity and the value ERPNext will post, and the file's own value
    (``file_value``), which the report compares the ledger with."""
    warehouses: Dict[str, Dict[str, Any]] = {}
    for line in ready:
        entry = warehouses.setdefault(line.warehouse, {"qty": 0, "value": 0, "file_value": 0, "rows": 0})
        entry["qty"] += line.qty
        entry["value"] += line.qty * line.valuation_rate
        entry["file_value"] += line.qty * line.valuation_rate if line.file_value is None else line.file_value
        entry["rows"] += 1
    precision = _currency_precision()
    for entry in warehouses.values():
        entry["qty"], entry["value"] = flt(entry["qty"], 6), flt(entry["value"], precision)
        entry["file_value"] = flt(entry["file_value"], precision)
    return {
        "total_qty": flt(sum(e["qty"] for e in warehouses.values()), 6),
        "total_value": flt(sum(e["value"] for e in warehouses.values()), precision),
        "warehouses": warehouses,
    }


def run(session_name: str, commit_progress: bool = False) -> Dict[str, Any]:
    """The dry run of an opening-stock session: every row checked, ERPNext's own validation of
    the ready rows, the result stored the dry run's way, with the totals."""
    from frappe_assistant_core.utils import import_dry_run as dry_run

    session = dry_run.engine_session(session_name)
    file_doc = readable_session_file(session)
    checker = _StockChecker()
    ready = _check_lines(session, checker)
    # ERPNext can't check a line whose item an earlier file of the plan brings until it is there.
    waiting = [line for line in ready if line.after_file]
    ready = _erpnext_check(session, [line for line in ready if not line.after_file], checker) + waiting
    for line in ready:
        waits = {"after_files": [line.after_file], "needs": [line.item_code]} if line.after_file else {}
        checker.mark(line.row, "ready", **waits)
    checker.rows.sort(key=lambda r: r["row"])
    summary = dry_run._store(session_name, file_doc, checker, len(checker.rows))
    summary["opening_stock"] = _totals(ready)
    frappe.db.set_value(
        dry_run.SESSION_DOCTYPE,
        session_name,
        "validation_summary",
        frappe.as_json(summary),
        update_modified=False,
    )
    return summary


def ready_lines(session) -> List[Ready]:
    """The lines that pass the row checks now."""
    return _check_lines(session, _StockChecker())


SAVEPOINT = "fac_opening_stock_check"


def chunks(lines: List[Ready]) -> List[List[Ready]]:
    """``lines`` in documents of about CHUNK_ROWS rows. An item and warehouse are never split
    across documents, so what a document holds can be told from its item and warehouse alone."""
    lines = sorted(lines, key=lambda line: (line.item_code, line.warehouse, line.row))
    out: List[List[Ready]] = []
    current: List[Ready] = []
    for line in lines:
        same_pair = bool(current) and (current[-1].item_code, current[-1].warehouse) == (
            line.item_code,
            line.warehouse,
        )
        if len(current) >= CHUNK_ROWS and not same_pair:
            out.append(current)
            current = []
        current.append(line)
    if current:
        out.append(current)
    return out


def build_document(stock: Dict[str, Any], lines: List[Ready]):
    """An unsaved Opening Stock Stock Reconciliation of ``lines``."""
    # A row that names a batch or serial asks ERPNext to make its bundle from those fields. It
    # does so whatever Stock Settings says, which is off on a fresh v16 site (#34428).
    return frappe.get_doc(
        {
            "doctype": TARGET,
            "purpose": PURPOSE,
            "company": stock["company"],
            "posting_date": stock["posting_date"],
            "posting_time": stock["posting_time"],
            "set_posting_time": 1,
            "expense_account": stock["difference_account"],
            "cost_center": frappe.get_cached_value("Company", stock["company"], "cost_center"),
            "items": [
                {
                    "item_code": line.item_code,
                    "warehouse": line.warehouse,
                    "qty": line.qty,
                    "valuation_rate": line.valuation_rate,
                    "allow_zero_valuation_rate": 0 if line.valuation_rate else 1,
                    "batch_no": line.batch_no or None,
                    "serial_no": line.serial_no or None,
                    "use_serial_batch_fields": 1 if (line.batch_no or line.serial_no) else 0,
                }
                for line in lines
            ],
        }
    )


def _ensure_batches(lines: List[Ready]) -> List[str]:
    """Create the batches the file names that don't exist yet. Returns their names."""
    made = []
    for line in lines:
        if line.batch_no and not frappe.db.exists("Batch", line.batch_no) and line.batch_no not in made:
            frappe.get_doc(
                {
                    "doctype": "Batch",
                    "batch_id": line.batch_no,
                    "item": line.item_code,
                    "expiry_date": line.expiry_date or None,
                }
            ).insert()
            made.append(line.batch_no)
    return made


ISOLATE_LIMIT = 20  # rows a chunk's check singles out before it fails the rest together


def _draft_error(stock: Dict[str, Any], lines: List[Ready]) -> Optional[Exception]:
    """None when ERPNext accepts ``lines`` as an Opening Stock, inserted and submitted, else why
    not: some refusals come only on submit (#34435). Rolled back."""
    from frappe_assistant_core.utils import import_dry_run as dry_run

    frappe.clear_messages()
    with dry_run.held_back():
        frappe.db.savepoint(SAVEPOINT)
        try:
            _ensure_batches(lines)
            doc = build_document(stock, lines).insert()
            # submit() hands more than 100 rows to a background queue; _submit() is the same
            # submission in this request, as the opening balances check does.
            doc._submit()
            if doc.docstatus != 1:
                frappe.throw(_("The Stock Reconciliation was not submitted."))
            return None
        except Exception as e:
            return e
        finally:
            frappe.db.rollback(save_point=SAVEPOINT)
            frappe.clear_messages()
            # ERPNext caches, by voucher name, whether later stock moves exist: the real document
            # gets the same name, so the rolled-back one's answer must not be read for it (#34435)
            frappe.local.future_sle = {}


def _erpnext_check(session, ready: List[Ready], checker: _StockChecker) -> List[Ready]:
    """Insert and submit each chunk inside a savepoint, rolled back: ERPNext's own validation.
    When it refuses a chunk and names a row ("Row #3"), that row fails alone, under its place in
    the sheet, and the rest are tried again. Otherwise the whole chunk fails together."""
    from frappe_assistant_core.utils import import_dry_run as dry_run

    def fail(line, message, kind):
        checker.fail(
            line.row,
            (dry_run.CAUSE_REJECTED, kind, message),
            {"cause": dry_run.CAUSE_REJECTED, "error": kind, "message": message},
        )

    stock, passed = settings(session), []
    for chunk in chunks(ready):
        remaining, isolated = list(chunk), 0
        while remaining:
            error = _draft_error(stock, remaining)
            if error is None:
                passed += remaining
                break
            kind, message = dry_run.refusal(error)
            named = re.search(r"Row\s*#\s*(\d+)", message)
            index = int(named.group(1)) if named else 0
            if named and 1 <= index <= len(remaining) and isolated < ISOLATE_LIMIT:
                bad = remaining.pop(index - 1)
                isolated += 1
                fail(bad, message.replace(named.group(0), f"Row {bad.row}", 1), kind)
                continue
            for line in remaining:
                fail(line, message, kind)
            break
    return passed


# -- creating --------------------------------------------------------------------------------

CREATE_SAVEPOINT = "fac_opening_stock_create"


def documents(session) -> List[str]:
    return [r.record_name for r in session.created_records if r.record_doctype == TARGET]


# ERPNext submits a Stock Reconciliation of more than 100 rows in a background job that may run
# 4600 seconds. A draft neither waiting in the queue nor failed is taken to have stopped (its
# worker was killed, say) only after longer than that.
STALL_SECONDS = 2 * 60 * 60
ACTION_FAILED = "Action Failed"  # the comment Frappe adds when a queued submit fails


def submitted_documents(session) -> List[str]:
    names = documents(session)
    submitted = set(
        frappe.get_all(TARGET, filters={"name": ["in", names or [""]], "docstatus": 1}, pluck="name")
    )
    return [n for n in names if n in submitted]


def _drafts(session) -> List[Any]:
    names = documents(session)
    return frappe.get_all(
        TARGET, filters={"name": ["in", names or [""]], "docstatus": 0}, fields=["name", "modified"]
    )


def _queued(name: str) -> bool:
    """Whether ERPNext's submit of ``name`` is still waiting in the queue: Frappe locks a
    document when it queues an action on it, and the job unlocks it when it starts."""
    return frappe.get_doc(TARGET, name).is_locked


def _submit_failed(name: str, since) -> bool:
    """Whether a queued submit of ``name`` failed: Frappe then adds an "Action Failed" comment."""
    return bool(
        frappe.get_all(
            "Comment",
            filters={
                "reference_doctype": TARGET,
                "reference_name": name,
                "comment_type": "Comment",
                "creation": [">=", since],
            },
            # in the language of whoever ran the job
            or_filters=[["content", "like", f"{text}%"] for text in {ACTION_FAILED, _(ACTION_FAILED)}],
            limit=1,
        )
    )


def stalled(session) -> List[str]:
    """Drafts of this session that ERPNext's background submit never finished: it said it
    failed, or the draft is out of the queue and has stayed a draft longer than the job may run."""
    now, out = frappe.utils.now_datetime(), []
    for draft in _drafts(session):
        if _submit_failed(draft.name, draft.modified):
            out.append(draft.name)
        elif (
            not _queued(draft.name) and frappe.utils.time_diff_in_seconds(now, draft.modified) > STALL_SECONDS
        ):
            out.append(draft.name)
    return out


def pending(session) -> List[str]:
    """The session's Stock Reconciliations ERPNext is still submitting in the background."""
    late = set(stalled(session))
    return [d.name for d in _drafts(session) if d.name not in late]


def imported_keys(session) -> set:
    """(item, warehouse) of every row in a submitted Stock Reconciliation of this session.
    Chunks never split an item and warehouse, so this tells what is in whatever the sheet looks like."""
    submitted = submitted_documents(session)
    if not submitted:
        return set()
    rows = frappe.get_all(
        ITEM_TABLE,
        filters={"parent": ["in", submitted], "parenttype": TARGET},
        fields=["item_code", "warehouse"],
    )
    return {(r.item_code, r.warehouse) for r in rows}


def check_card(session, company, posting_date, rows, total_qty, total_value) -> None:
    """The approval card shows what FACO passed: refuse unless it is what the last check found."""
    summary = frappe.parse_json(session.validation_summary or "{}") or {}
    totals, stock = summary.get("opening_stock") or {}, settings(session)
    checked = (
        stock.get("company"),
        stock.get("posting_date"),
        summary.get("ready"),
        flt(totals.get("total_qty"), 6),
        flt(totals.get("total_value"), 2),
    )
    try:
        asked = (
            cstr(company).strip(),
            str(getdate(posting_date)),
            int(rows),
            flt(total_qty, 6),
            flt(total_value, 2),
        )
    except (TypeError, ValueError):
        asked = None
    if asked != checked:
        raise OpeningStockProblem(
            _(
                "The last check found {2} rows for {0} at {1}: quantity {3}, value {4}. Pass those, so "
                "the approval card shows them."
            ).format(*checked)
        )


def _message_of_create(e: Exception) -> str:
    from frappe_assistant_core.utils import import_dry_run as dry_run

    return _("ERPNext refused the opening stock: {0}").format(dry_run._message_of(e))


DELETE_SAVEPOINT = "fac_opening_stock_delete_stalled"


def _delete_stalled(session) -> None:
    """Delete the drafts ERPNext never submitted, before the stock is brought in again: a slow
    background job could otherwise still submit one, and post the same stock twice. The session's
    link to each goes first (Frappe refuses to delete a linked record); all of it or none."""
    late = stalled(session)
    if not late:
        return
    frappe.db.savepoint(DELETE_SAVEPOINT)
    try:
        session.created_records = [
            r for r in session.created_records if not (r.record_doctype == TARGET and r.record_name in late)
        ]
        session.log_step(
            "Import", "Warning", _("Deleted {0}: drafts ERPNext never submitted.").format(", ".join(late))
        )
        session.save()
        for name in late:
            frappe.delete_doc(TARGET, name)
    except Exception as e:
        frappe.db.rollback(save_point=DELETE_SAVEPOINT)
        session.reload()
        raise OpeningStockProblem(
            _("{0} is a draft ERPNext never submitted, and it couldn't be deleted: {1}").format(
                ", ".join(late), _message_of_create(e)
            )
        ) from e


JOB = "fac_opening_stock::{0}"


def create(session) -> List[str]:
    """Create and submit the opening stock, a chunk at a time, each all or nothing: one chunk in
    this request, more in a background job, so a large sheet never runs into the request's time
    limit. Chunks made by an earlier call are skipped, so calling again never duplicates. Returns
    the names made in this request."""
    from frappe_assistant_core.utils import import_fixes

    if session.status in ("Completed", "Importing"):
        return []  # done, or still being made: the caller reports
    if session.status != "Ready to Import" or not import_fixes.checked_as_is(session):
        raise OpeningStockProblem(
            _(
                "The sheet isn't ready, or it changed since its last check. Check it with dry_run_import first."
            )
        )
    waiting = pending(session)
    if waiting:
        raise OpeningStockProblem(
            _(
                "ERPNext is still submitting {0} from the earlier try. Wait for it, then call again: "
                "importing now could bring the same stock in twice."
            ).format(", ".join(waiting))
        )
    _delete_stalled(session)
    lines = ready_lines(session)
    expected = (frappe.parse_json(session.validation_summary or "{}") or {}).get("ready")
    if len(lines) != expected:
        raise OpeningStockProblem(
            _(
                "The stock changed since the last check: {0} rows are ready now, not {1}. Check it "
                "again with dry_run_import."
            ).format(len(lines), expected)
        )
    session.status = "Importing"
    session.progress = _progress("queued")
    session.save()
    if len(chunks(lines)) > 1:
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
        return []
    return _create_chunks(session, lines, commit=False)  # the request commits when it returns


def _commits() -> bool:
    """Whether the job commits each document (not under tests, which roll back at the end)."""
    return not frappe.flags.in_test


def create_job(session_name: str, user: str) -> None:
    """Background job: the opening stock, as the user who approved it."""
    from frappe_assistant_core.utils import import_dry_run as dry_run
    from frappe_assistant_core.utils import import_fixes

    frappe.set_user(user)  # nosemgrep: frappe-setuser — the job runs as the user who approved the import
    session = dry_run.engine_session(session_name)
    lines = ready_lines(session)
    # What the user approved is what the last check found: the same rows, and nothing the
    # check depends on changed since.
    approved = (frappe.parse_json(session.validation_summary or "{}") or {}).get("ready")
    if len(lines) != approved or not import_fixes.checked_as_is(session):
        session.status = "Partially Completed" if submitted_documents(session) else "Failed"
        session.log_step(
            "Import",
            "Failed",
            _("The import stopped: the sheet changed after it was approved; check it again."),
        )
        session.save()
    else:
        try:
            _create_chunks(session, lines, commit=True)
        except OpeningStockProblem:
            if not _commits():
                raise
            # the document that failed is rolled back; the ones before it, and the session's
            # record of them and of the failure, are kept
        except Exception:
            if not _commits():
                raise
            frappe.db.rollback()
            _stopped(session_name, _("the background job stopped."))
            frappe.log_error(title=_("FAC opening stock import failed"), message=frappe.get_traceback())
    from frappe_assistant_core.utils import import_plan

    import_plan.child_finished(session_name)  # in a migration plan, its next file
    if _commits():
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — a background job commits its own work


def _create_chunks(session, lines: List[Ready], commit: bool) -> List[str]:
    stock, made = settings(session), []
    for chunk in chunks(lines):
        # What the insert or submit queued for the commit goes with a refused document.
        marks = open_savepoint(CREATE_SAVEPOINT)
        try:
            batches = _ensure_batches(chunk)
            doc = build_document(stock, chunk).insert()
            doc.submit()  # ERPNext submits more than 100 rows in the background
            session.append("created_records", {"record_doctype": TARGET, "record_name": doc.name})
            for batch in batches:
                session.append("created_records", {"record_doctype": "Batch", "record_name": batch})
            # What the file said for this document, kept for the report: later checks only see
            # the rows still to import.
            options = frappe.parse_json(session.template_options or "{}") or {}
            options["opening_stock"].setdefault("created", {})[doc.name] = _totals(chunk)["warehouses"]
            session.template_options = frappe.as_json(options)
            session.log_step(
                "Import", "Success", _("{0}: {1} rows.").format(doc.name, len(chunk)), rows_ok=len(chunk)
            )
            session.save()
            made.append(doc.name)
        except Exception as e:
            rollback_to_savepoint(CREATE_SAVEPOINT, marks, TARGET, None)
            session.reload()
            session.status = "Partially Completed" if documents(session) else "Failed"
            session.log_step("Import", "Failed", _message_of_create(e), rows_failed=len(chunk))
            session.save()
            raise OpeningStockProblem(_message_of_create(e)) from e
        if commit and _commits():
            frappe.db.commit()  # nosemgrep: frappe-manual-commit — a background job commits its own work
    # Over 100 rows, ERPNext submits in the background: the session stays Importing until
    # report() finds every document submitted.
    session.status = "Importing" if pending(session) else "Completed"
    session.progress = _progress("done")
    session.save()
    return made


def _progress(state: str) -> str:
    return frappe.as_json({"step": "Import", "state": state, "updated_on": str(frappe.utils.now_datetime())})


def _building(session) -> bool:
    """Whether the background job is still making this session's documents. A job that is no
    longer queued or running and never finished has stopped: the session says so."""
    progress = frappe.parse_json(session.progress or "{}") or {}
    if session.status != "Importing" or progress.get("step") != "Import" or progress.get("state") == "done":
        return False
    if _job_running(session):
        return True
    _stopped(session.name, _("the background job stopped."))
    session.reload()
    return False


def _stopped(session_name: str, reason: str) -> None:
    """A background import that stopped before its end: what it committed is in."""
    from frappe_assistant_core.utils import import_dry_run as dry_run

    session = dry_run.engine_session(session_name)
    if session.status != "Importing":
        return
    session.status = "Partially Completed" if documents(session) else "Failed"
    session.log_step(
        "Import",
        "Failed",
        _("The import stopped: {0} Check the file again to import the rest.").format(reason),
    )
    session.save()


def _job_running(session) -> bool:
    from frappe_assistant_core.utils.import_run import job_alive

    try:
        return job_alive(JOB.format(session.name))
    except Exception:
        return True  # the queue can't be asked (Redis down, say): don't call the job stopped


def ledger_by_warehouse(submitted: List[str]) -> Dict[str, Any]:
    """Quantity and value per warehouse that the Stock Reconciliations ``submitted`` posted.

    A Stock Reconciliation's ledger entry keeps its balance in qty_after_transaction (its
    actual_qty is 0 in v15), and a batch adds onto its item's running balance: so each item and
    warehouse counts its final balance once. Items that already had stock are refused by the
    check, so that balance is what the file brought in. Summed with frappe.qb: Frappe v16 refuses
    SQL functions in get_all's fields."""
    from frappe.query_builder.functions import Max, Sum

    ledger: Dict[str, Any] = {}
    if not submitted:
        return ledger
    sle = frappe.qb.DocType("Stock Ledger Entry")
    rows = (
        frappe.qb.from_(sle)
        .select(
            sle.warehouse,
            sle.item_code,
            Max(sle.qty_after_transaction).as_("qty"),
            Sum(sle.stock_value_difference).as_("value"),
        )
        .where((sle.voucher_type == TARGET) & sle.voucher_no.isin(submitted) & (sle.is_cancelled == 0))
        .groupby(sle.warehouse, sle.item_code)
    ).run(as_dict=True)
    for row in rows:
        entry = ledger.setdefault(row.warehouse, frappe._dict(qty=0, value=0))
        entry.qty += flt(row.qty)
        entry.value += flt(row.value)
    return ledger


def report(session) -> Dict[str, Any]:
    """Quantity and value per warehouse from the Stock Ledger, next to the file's totals."""
    names, stock = documents(session), settings(session)
    building = _building(session)
    submitted, waiting, late = submitted_documents(session), pending(session), stalled(session)
    if building:
        pass  # the background job is still making documents
    elif late and session.status == "Importing":
        # ERPNext reverts a background submit that fails to a draft, and tells nobody here.
        session.status = "Partially Completed" if submitted else "Failed"
        session.log_step("Import", "Failed", _("ERPNext didn't submit {0}.").format(", ".join(late)))
        session.save()
    elif session.status == "Importing" and names and not waiting:
        # ERPNext's background submit has finished since the import was started.
        session.db_set("status", "Completed")
        session.status = "Completed"

    # What the file said for the documents that are in, kept when each was made.
    created, file_side = stock.get("created") or {}, {}
    for name in submitted:
        for warehouse, held in (created.get(name) or {}).items():
            entry = file_side.setdefault(warehouse, {"qty": 0, "value": 0, "rows": 0})
            entry["qty"] += held["qty"]
            # the file's own value: what rounding the rate changed shows as a difference (#34435)
            entry["value"] += held.get("file_value", held["value"])
            entry["rows"] += held["rows"]

    ledger = ledger_by_warehouse(submitted)
    precision = _currency_precision()
    warehouses, differences = {}, []
    for warehouse, expected in file_side.items():
        got = ledger.get(warehouse) or frappe._dict(qty=0, value=0)
        entry = {
            "file_qty": expected["qty"],
            "file_value": flt(expected["value"], precision),
            "erpnext_qty": flt(got.qty, 6),
            "erpnext_value": flt(got.value, precision),
        }
        entry["difference_qty"] = flt(entry["erpnext_qty"] - entry["file_qty"], 6)
        entry["difference_value"] = flt(entry["erpnext_value"] - entry["file_value"], precision)
        tolerance = 0.5 * 10 ** (-precision) * max(expected.get("rows") or 1, 1)
        if entry["difference_qty"] or abs(entry["difference_value"]) > tolerance:
            differences.append(warehouse)
        warehouses[warehouse] = entry

    reposting = bool(
        submitted
        and frappe.db.exists(
            "Repost Item Valuation",
            {
                "voucher_type": TARGET,
                "voucher_no": ["in", submitted],
                "status": ["not in", ["Completed", "Skipped"]],
                "docstatus": ["<", 2],
            },
        )
    )
    accounting = (
        _("Posted against {0}.").format(stock.get("difference_account"))
        if stock.get("perpetual")
        else _("Perpetual inventory is off for this company, so no accounting entries were made.")
    )
    if building:
        message = _("Creating the opening stock in the background: {0} documents made so far.").format(
            len(names)
        )
    elif late:
        why = []
        for name in late:
            comment = frappe.get_all(
                "Comment",
                filters={"reference_doctype": TARGET, "reference_name": name, "comment_type": "Comment"},
                pluck="content",
                order_by="creation desc",
                limit=1,
            )
            why.append(f"{name}: {frappe.utils.strip_html_tags(comment[0])}" if comment else name)
        message = _(
            "ERPNext couldn't submit {0}. Check the sheet again with dry_run_import; importing again "
            "deletes that draft first."
        ).format("; ".join(why))
    elif waiting:
        message = _("{0} still being submitted in the background: {1}.").format(
            len(waiting), ", ".join(waiting)
        )
    elif differences:
        message = _("Imported, but these warehouses differ from the file: {0}.").format(
            ", ".join(differences)
        )
    else:
        message = _("Opening stock imported: every warehouse matches the file.")
    if reposting:
        message += " " + _("ERPNext is still reposting stock values, so values can still change.")
    return {
        "status": session.status,
        "documents": names,
        "pending": waiting,
        "failed_documents": late,
        "reposting": reposting,
        "warehouses": warehouses,
        "differences": differences,
        "accounting": accounting,
        "message": message,
    }


# -- every row, for the sign-off report (reads only) -------------------------------------------


def _row_value(cells: Dict[str, str]):
    """The row's quantity and value as the file writes them (the value is its amount, else
    quantity times rate), and whether a number in it can't be read."""
    try:
        qty, rate, amount = (number(cells.get(name)) for name in ("qty", "valuation_rate", "amount"))
    except ValueError:
        return None, None, True
    if amount is None and qty is not None and rate is not None:
        amount = qty * rate
    return qty, amount, False


def _last_import_failure(session) -> Optional[str]:
    if session.status not in ("Partially Completed", "Failed"):
        return None
    steps = [step for step in session.steps if step.step == "Import"]
    return steps[-1].message if steps and steps[-1].outcome == "Failed" else None


def outcomes(session) -> List[Dict[str, Any]]:
    """Every row of the file and where it stands now: imported (in a submitted document of the
    session), left out, failed (the check or ERPNext refused it, with why) or not imported yet,
    with its quantity and value as the file writes them. Writes nothing."""
    from frappe_assistant_core.utils import import_fixes
    from frappe_assistant_core.utils.import_signoff import NOT_IMPORTED

    lines = read_lines(session)
    checker = _StockChecker()
    _check_lines(session, checker, lines)
    messages = {g["id"]: g.get("message") or _(g["cause"]) for g in checker.groups.values()}
    marked = {entry["row"]: entry for entry in checker.rows}
    left = {entry["row"]: entry["reason"] for entry in import_fixes.left_out(session)}
    stopped = _last_import_failure(session)
    out = []
    for line in lines:
        entry = marked.get(line.row) or {"status": "ready"}
        status, reason = entry["status"], ""
        if status == "failed":
            reason = "; ".join(messages.get(g, "") for g in entry.get("groups") or [])
        elif status == "excluded":
            reason = left.get(line.row) or _("Left out by the user")
        elif status == "ready" and stopped:
            status, reason = "failed", stopped
        elif status == "ready":
            status, reason = "not_imported", _(NOT_IMPORTED)
        qty, value, unreadable = _row_value(line.cells)
        totals_row = is_totals_row(line.cells)
        out.append(
            {
                "row": line.row,
                "status": status,
                "reason": reason,
                "value": None if totals_row else value,
                "qty": None if totals_row else qty,
                "unreadable": unreadable,
                "totals_row": totals_row,
                "file_says": value if totals_row else None,
            }
        )
    return out


def summary(session) -> Dict[str, Any]:
    """The sign-off report's view of this session: its rows, quantities and values per status, and
    the Stock Ledger's value against the file's for the rows imported. Writes nothing."""
    from frappe_assistant_core.utils.import_signoff import tally

    stock = settings(session)
    precision = frappe.get_precision(ITEM_TABLE, "amount") or 2
    out = tally(outcomes(session), ("value", "qty"), precision)
    names, submitted = documents(session), submitted_documents(session)
    drafts = {d.name for d in _drafts(session)}
    ledger = ledger_by_warehouse(submitted)
    total = flt(sum(entry.value for entry in ledger.values()), precision)
    difference = flt(total - out["value"]["imported"], precision)
    # Each ledger entry rounds its own value: within half a cent a row, that is rounding.
    rounding = abs(difference) <= 0.5 * 10 ** (-precision) * max(out["rows"]["imported"], 1)
    out.update(
        {
            "kind": "opening_stock",
            "doctype": TARGET,
            "label": _("Opening Stock"),
            "company": stock["company"],
            "cut_off": stock["posting_date"],
            "balance": "stock",
            "erpnext": {
                "documents": len(submitted),
                "pending": len([n for n in names if n in drafts]),
                "total": total,
                "qty": flt(sum(entry.qty for entry in ledger.values()), 6),
                "difference": 0.0 if rounding else difference,
                "rounding": difference if rounding else 0.0,
                "no_longer_submitted": len([n for n in names if n not in submitted and n not in drafts]),
            },
        }
    )
    return out
