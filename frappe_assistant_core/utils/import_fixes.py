# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Explaining dry-run failures and fixing them together (#33991), and creating the missing
masters in one approved batch (#33992).

Each failure group from the dry run gets a plain explanation and the fixes that fit it:

- **map** a value to one that exists (a link's record, or a select option). The engine
  ranks the existing names; the model only presents them.
- **create** the missing record, when a master that simple can be: the dry run plans every
  one (``masters_plan``) and create_document creates them all in one call (its documents list,
  with import_session), so with one approval. The records then exist, so the next check
  passes the rows that need them.
- **leave out** the rows, with a reason. The import skips them and reports them.

Map and leave out are stored on the session, never in the file: the value maps and the
reasons in ``transformation_rules``, the row numbers in ``excluded_rows``. Created masters
are listed in ``created_records``.
"""

import difflib
import json
import re
from typing import Any, Dict, List, Optional, Tuple

import frappe
from frappe import _
from frappe.model import no_value_fields, table_fields
from frappe.utils import cint, cstr
from frappe.utils.nestedset import get_root_of

from frappe_assistant_core.utils import import_dry_run as dry_run
from frappe_assistant_core.utils import import_keys
from frappe_assistant_core.utils.import_session import readable_session_file

MAP = "map"
CREATE = "create"
LEAVE_OUT = "leave_out"
ALLOW_ZERO_RATE = "allow_zero_rate"  # opening stock: bring an item in at zero value
POST_AT_CUTOFF = "post_at_cutoff"  # opening invoices: post invoices dated in no fiscal year at the cut-off
FILL = "fill"  # one value for a required field the rows leave blank, or the file has no column for
MAKE_UNIQUE = "make_unique"  # a repeated name: the later rows get their ID (or a number) added to it
DROP_COLUMN = "drop_column"  # a column whose values the site can't take: left empty, every row kept
ACTIONS = (
    MAP,
    LEAVE_OUT,
    ALLOW_ZERO_RATE,
    POST_AT_CUTOFF,
    CREATE,
    FILL,
    MAKE_UNIQUE,
    DROP_COLUMN,
)  # applied by dry_run_import; create only in a migration plan, else create_document does it

CLOSEST_LIMIT = 5
MIN_SCORE = 0.6  # below it a name only shares letters: "Kerala" isn't a misspelt "Karnataka" (0.53)
LIKELY_SPELLING = 0.8  # a closest name spelt this alike, and LIKELY_LEAD ahead of the next, is the one meant
LIKELY_LEAD = 0.1
FULL_SCAN = 2000  # rank every record when a DocType has at most this many
WORD_MATCHES = 200  # else only records sharing a word with the value, this many per word
GROUPS_SHOWN = 30  # the dry run's reply lists this many groups; the results file keeps them all
MASTERS_SHOWN = 50  # and this many missing masters to create
DECISION_VALUES = 20  # a decision lists this many of its values, each with its suggested answer
PLANNED_SHOWN = 10  # planned masters named in an error about one that was not planned

#: Masters simple enough to create that are still never created during an import. Sites add
#: more with the ``fac_import_never_create_doctypes`` site config key (a list of DocTypes).
NEVER_CREATE = {
    "Company": "creating one also creates a chart of accounts, warehouses and taxes",
}

#: Masters each company defines for itself, that ERPNext names "<name> - <company abbreviation>": DocType →
#: (its name field, its company field). A file names them without the abbreviation ("DEL"), so a new one is
#: created for the import's company and the rows find it by "<name> - <abbr>". Live, 2026-11-19: a client's
#: 7 department codes couldn't be created (ERPNext names it itself) and were forced onto ERPNext's defaults.
COMPANY_NAMED = {
    "Department": ("department_name", "company"),
}


class FixProblem(Exception):
    """A fix that can't be applied. The message is shown to the user."""


class AlreadyThere(FixProblem):
    """A planned master that exists already."""


class CreatedBefore(FixProblem):
    """Every master sent exists already: an earlier call created them (live, 2026-11-19: the chat
    called create_document again 28 s after it had created 264 masters, and told the user someone
    else must have added them)."""

    def __init__(self, count: int):
        super().__init__(
            _(
                "All {0} masters sent exist already: an earlier call created them, so none was created "
                "now. Tell the user they are in place, then check the file again with dry_run_import."
            ).format(count)
        )
        self.count = count


class FixProblems(FixProblem):
    """Some fixes were wrong, so none was saved. ``problems`` says which and why."""

    def __init__(self, problems: List[Dict[str, Any]], message: Optional[str] = None):
        super().__init__(message or _("No fix was saved. Correct these and call again."))
        self.problems = problems


# -- what the session holds ------------------------------------------------------------


def _rules(session) -> Dict[str, Any]:
    return frappe.parse_json(session.transformation_rules or "{}") or {}


def value_maps(session) -> List[Dict[str, Any]]:
    return list(_rules(session).get("value_maps") or [])


def renames(session) -> Dict[str, Dict[str, str]]:
    """Row → ``{"parent", "field", "value"}``: a repeated name made unique (MAKE_UNIQUE)."""
    return dict(_rules(session).get("renames") or {})


def dropped(session) -> List[Dict[str, str]]:
    """``{"parent", "field", "label"}`` of each column left empty in every row (DROP_COLUMN)."""
    return list(_rules(session).get("dropped_fields") or [])


def fills(session) -> List[Dict[str, Any]]:
    """The fills: ``{"field", "label", "value"}``, each a field of the target DocType that every
    record the file starts gets this value for, when its row leaves it blank (#34415)."""
    return list(_rules(session).get("fills") or [])


FILLED_HEADER = "{0} (filled in)"  # the column a fill adds when no column of the file is mapped to it


def left_out(session) -> List[Dict[str, Any]]:
    """Rows the user chose to leave out, each ``{"row", "reason"}``, in row order."""
    reasons = _rules(session).get("left_out") or {}
    rows = sorted(dry_run._excluded_rows(session))
    return [{"row": row, "reason": cstr(reasons.get(str(row)))} for row in rows]


def left_out_problems(session) -> Dict[str, Dict[str, Optional[str]]]:
    """What the check found wrong with each row left out, by row: ``{"error", "fix"}``. The
    reason given for leaving rows out is often only the user's request ("leave the failing rows
    out"); the failed-rows file says what to correct in them (#34417)."""
    return dict(_rules(session).get("left_out_problems") or {})


def left_out_report(session) -> List[Dict[str, Any]]:
    """The left-out rows grouped by reason, for the user: reason, count and the row numbers."""
    by_reason: Dict[str, List[int]] = {}
    for entry in left_out(session):
        by_reason.setdefault(entry["reason"] or _("Left out by the user"), []).append(entry["row"])
    return [
        {"reason": reason, "count": len(rows), "rows": row_ranges(rows)} for reason, rows in by_reason.items()
    ]


MAX_RANGES = 20  # row ranges named in a reply; the failed-rows file has every row


def row_ranges(rows: List[int]) -> str:
    """[2, 3, 4, 9] → "2-4, 9". Past MAX_RANGES ranges the rest is counted, not listed: 20,000
    scattered rows would be some 150 KB in every reply."""
    parts, start, previous, rest = [], None, None, 0
    for row in sorted(set(rows)):
        if start is None:
            start = previous = row
        elif row == previous + 1:
            previous = row
        else:
            if len(parts) < MAX_RANGES:
                parts.append(_range(start, previous))
            else:
                rest += previous - start + 1
            start = previous = row
    if start is not None:
        if len(parts) < MAX_RANGES:
            parts.append(_range(start, previous))
        else:
            rest += previous - start + 1
    text = ", ".join(parts)
    return _("{0} and {1} more rows").format(text, rest) if rest else text


def _rows(count: int) -> str:
    return _("1 row") if count == 1 else _("{0} rows").format(count)


def _range(start: int, end: int) -> str:
    return str(start) if start == end else f"{start}-{end}"


# -- applying the value maps to the file's rows -------------------------------------------


def apply_value_maps(session, rows: List[List[str]]) -> List[List[str]]:
    """The file's rows (header first) with each old ID column translated (#34244) and every value map
    applied to its columns. Every reader of the file's rows comes through here."""
    rows = _with_fills(session, import_keys.translate(session, rows))
    if not rows:
        return rows
    maps = value_maps(session)
    targets = _column_targets(session)
    by_column: Dict[int, Dict[str, str]] = {}
    for position, target in targets.items():
        for rule in maps:
            if target == (rule.get("parent"), rule.get("field")):
                by_column.setdefault(position, {})[cstr(rule.get("from")).strip()] = cstr(rule.get("to"))
    if by_column:
        out = [rows[0]]
        for row in rows[1:]:
            row = list(row)
            for position, replace in by_column.items():
                if position < len(row) and cstr(row[position]).strip() in replace:
                    row[position] = replace[cstr(row[position]).strip()]
            out.append(row)
        rows = out
    return _with_renames(
        session, _without_dropped(session, _company_named(session, rows, targets), targets), targets
    )


def _company_named(session, rows: List[List[str]], targets) -> List[List[str]]:
    """The rows with each value of a COMPANY_NAMED link ("DEL") as ERPNext names the record of the row's
    company ("DEL - SD"), where that record exists and the value alone doesn't."""
    columns = {}
    for position, (parent, field) in targets.items():
        df = frappe.get_meta(parent).get_field(field)
        if df and df.fieldtype == "Link" and df.options in COMPANY_NAMED:
            columns[position] = df.options
    if not columns:
        return rows
    company_at = next(
        (
            p
            for p, (parent, field) in targets.items()
            if parent == session.target_doctype and field == "company"
        ),
        None,
    )
    fallback = import_company(session, rows)
    abbr_of: Dict[str, Optional[str]] = {}
    found: Dict[Tuple[str, str], bool] = {}

    def exists(doctype: str, name: str) -> bool:
        if (doctype, name) not in found:
            found[(doctype, name)] = bool(frappe.db.exists(doctype, name))
        return found[(doctype, name)]

    out = [rows[0]]
    for row in rows[1:]:
        row = list(row)
        company = cstr(row[company_at]).strip() if company_at is not None and company_at < len(row) else ""
        company = company or fallback
        if company not in abbr_of:
            abbr_of[company] = frappe.get_cached_value("Company", company, "abbr") if company else None
        abbr = abbr_of[company]
        for position, doctype in columns.items():
            value = cstr(row[position]).strip() if position < len(row) else ""
            if abbr and value and not exists(doctype, value) and exists(doctype, f"{value} - {abbr}"):
                row[position] = f"{value} - {abbr}"
        out.append(row)
    return out


def import_company(session, rows: Optional[List[List[str]]] = None) -> Optional[str]:
    """The company the file's records go to: the one its company column names most (after the value maps),
    a fill's, or the site's default company."""
    for fill in fills(session):
        if fill.get("field") == "company" and fill.get("value"):
            return fill["value"]
    targets = _column_targets(session)
    at = next(
        (
            p
            for p, (parent, field) in targets.items()
            if parent == session.target_doctype and field == "company"
        ),
        None,
    )
    if at is not None and rows:
        counts: Dict[str, int] = {}
        mapped = {
            cstr(m.get("from")).strip(): cstr(m.get("to"))
            for m in value_maps(session)
            if m.get("field") == "company"
        }
        for row in rows[1:]:
            value = cstr(row[at]).strip() if at < len(row) else ""
            value = mapped.get(value, value)
            if value and frappe.db.exists("Company", value):
                counts[value] = counts.get(value, 0) + 1
        if counts:
            return max(counts, key=counts.get)
    return frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
        "Global Defaults", "default_company"
    )


def _without_dropped(session, rows: List[List[str]], targets) -> List[List[str]]:
    """The rows with each dropped column's values left empty: every row is kept, the field isn't set."""
    wanted = {(d.get("parent"), d.get("field")) for d in dropped(session)}
    positions = [p for p, target in targets.items() if target in wanted]
    if not positions:
        return rows
    out = [rows[0]]
    for row in rows[1:]:
        row = list(row)
        for position in positions:
            if position < len(row):
                row[position] = ""
        out.append(row)
    return out


def _with_renames(session, rows: List[List[str]], targets) -> List[List[str]]:
    """The rows with each repeated name made unique, as MAKE_UNIQUE worked it out (by row number)."""
    wanted = renames(session)
    if not wanted:
        return rows
    position_of = {target: p for p, target in targets.items()}
    out = [rows[0]]
    for number, row in enumerate(rows[1:], start=2):
        rename = wanted.get(str(number))
        if rename:
            at = position_of.get((rename.get("parent"), rename.get("field")))
            if at is not None and at < len(row):
                row = list(row)
                row[at] = rename["value"]
        out.append(row)
    return out


def _with_fills(session, rows: List[List[str]]) -> List[List[str]]:
    """The rows with each fill's value in the rows that start a record and leave it blank: in
    its column, or in a column added at the end for a field the file has none for."""
    wanted = fills(session)
    if not wanted or not rows:
        return rows
    targets = _column_targets(session)
    own = [position for position, (parent, _field) in targets.items() if parent == session.target_doctype]
    column = {
        field: position for position, (parent, field) in targets.items() if parent == session.target_doctype
    }
    added = [fill for fill in wanted if fill["field"] not in column]
    width = len(rows[0])
    out = [list(rows[0]) + [FILLED_HEADER.format(fill["label"]) for fill in added]]
    for row in rows[1:]:
        row = list(row) + [""] * (width - len(row))
        # A row that continues the record above (a child table's) has none of the record's own values
        starts = any(cstr(row[position]).strip() for position in own if position < width)
        for fill in wanted:
            at = column.get(fill["field"])
            if starts and at is not None and not cstr(row[at]).strip():
                row[at] = fill["value"]
        out.append(row + [fill["value"] if starts else "" for fill in added])
    return out


def filled_columns(session, header: List[str]) -> Dict[str, str]:
    """Position → field for the columns the fills added to ``header``, for the import's column map."""
    added = {FILLED_HEADER.format(fill["label"]): fill["field"] for fill in fills(session)}
    return {str(i): added[cstr(name)] for i, name in enumerate(header) if cstr(name) in added}


def _fill_field(session, group: Dict[str, Any]):
    """The target DocType's field ``group``'s rows leave blank, or None: a required value missing,
    or ERPNext's own "Value missing for <DocType>: <Label>" for a field no column is mapped to."""
    meta = frappe.get_meta(session.target_doctype)
    df = None
    if group.get("cause") == dry_run.CAUSE_REQUIRED_MISSING:
        if group.get("parent", session.target_doctype) == session.target_doctype:
            df = meta.get_field(group.get("field"))
    elif group.get("cause") == dry_run.CAUSE_REJECTED and group.get("error") == "MandatoryError":
        message = cstr(group.get("message")).strip()
        found = re.search(r"Value missing for (.+?): (.+)$", message)
        if found and found.group(1).strip() in (session.target_doctype, _(session.target_doctype)):
            label = found.group(2).strip()
            fields = [field for field in meta.fields if field.reqd and label in (field.label, _(field.label))]
            df = fields[0] if len(fields) == 1 else None
        elif not found:
            df = _field_named_in(meta, message)
    elif group.get("cause") == dry_run.CAUSE_REJECTED:
        df = _group_type_field(meta, cstr(group.get("message")))
    # One value for every record can't be what names or titles each, nor one no two records share
    if not df or df.unique or df.fieldname in (dry_run._name_field(session.target_doctype), meta.title_field):
        return None
    return df


def _group_type_field(meta, message: str):
    """The one link field ERPNext's "Cannot select a Group type <DocType>" is about, or None. A Customer
    with no Customer Group column gets Selling Settings' default, which is the group "All Customer
    Groups" on many sites, and ERPNext refuses it: one non-group value for every row is the fix."""
    found = re.search(r"Cannot select a Group type (.+?)\.", message)
    if not found:
        return None
    target = found.group(1).strip()
    fields = [df for df in meta.fields if df.fieldtype == "Link" and target in (df.options, _(df.options))]
    return fields[0] if len(fields) == 1 else None


def _field_named_in(meta, message: str):
    """The one field of ``meta`` an app's own "<Label> is required" names, or None. India Compliance
    refuses an Item with "HSN/SAC Code is required. Please enter a valid HSN/SAC code." for its
    HSN/SAC field, which isn't mandatory in the DocType (PR #392, F4). The longest label found in
    the message wins (HSN/SAC over a field called Code); two fields with that label are no answer."""
    from frappe.model import data_fieldtypes, table_fields

    text = message.casefold()
    found = {}
    for field in meta.fields:
        if field.fieldtype not in data_fieldtypes or field.fieldtype in table_fields or field.read_only:
            continue
        for label in {field.label, _(field.label)} - {None, ""}:
            if re.search(r"(?<!\w)" + re.escape(label.casefold()) + r"(?!\w)", text):
                found.setdefault(len(label), set()).add(field.fieldname)
    if not found:
        return None
    longest = found[max(found)]
    return meta.get_field(next(iter(longest))) if len(longest) == 1 else None


def _fill(session, group: Dict[str, Any], fix: Dict[str, Any], wanted: List[Dict[str, Any]]):
    """The fills with ``fix``'s value for the field ``group``'s rows leave blank."""
    if dry_run.special_engine(session) or (session.import_type or dry_run.INSERT) != dry_run.INSERT:
        raise FixProblem(_("Only new records of a Data Import can have a value filled in."))
    df = _fill_field(session, group)
    if not df:
        raise FixProblem(
            _(
                "Only a required value the rows leave blank can be filled in. Leave these rows out, or correct them in the file."
            )
        )
    value = cstr(fix.get("value")).strip()
    if not value:
        raise FixProblem(_("Say which value every row gets, in 'value'."))
    if df.fieldtype == "Link":
        coming = {name.casefold(): name for name in _planned(session, df.options)}.get(value.casefold())
        if coming and not frappe.db.exists(df.options, value):
            value = coming  # an earlier file of the plan creates it before these rows are imported
        else:
            _check_existing(session, {"label": df.label}, df.options, value)
            leaf_only = dry_run.PARTY_DEFAULTS.get(session.target_doctype, {}).get(
                df.fieldname, (None, False)
            )[1]
            if leaf_only and frappe.db.exists(df.options, {"name": value, "is_group": 1}):
                # A group of the tree can't hold the party: ERPNext refuses it (live 2026-11-10)
                leaves = frappe.get_list(
                    df.options, filters={"is_group": 0}, pluck="name", limit_page_length=20
                )
                raise FixProblem(
                    _("'{0}' is a group, so it can't hold records. Some that can: {1}.").format(
                        value, ", ".join(leaves)
                    )
                )
    elif df.fieldtype == "Select":
        choices = [c for c in cstr(df.options).split("\n") if c]
        if value not in choices:
            raise FixProblem(
                _("'{0}' isn't one of the choices for {1}: {2}.").format(
                    value, _(df.label), ", ".join(choices)
                )
            )
    return [f for f in wanted if f["field"] != df.fieldname] + [
        {"field": df.fieldname, "label": df.label, "value": value}
    ]


def _column_targets(session) -> Dict[int, Tuple[str, str]]:
    """Column position → (DocType the field is on, fieldname), for mapped columns."""
    meta = frappe.get_meta(session.target_doctype)
    targets = {}
    for position, target in dry_run.column_to_field_map(session).items():
        if not str(position).isdigit() or not target or target == "Don't Import":
            continue
        if "." in target:
            table_field, fieldname = target.split(".", 1)
            table = meta.get_field(table_field)
            if not table:
                continue
            targets[int(position)] = (table.options, fieldname)
        else:
            targets[int(position)] = (session.target_doctype, target)
    return targets


def _with_target(session, group: Dict[str, Any]) -> Dict[str, Any]:
    """``group`` with the DocType its field is on and, for a missing link, the DocType it
    links to, both worked out from the session's mapping."""
    if not group.get("field"):
        return group
    # The dry run says which DocType the field is on; only a duplicate's key field, always
    # on the target DocType, comes without it.
    parent = group.get("parent")
    if not parent:
        parents = [p for p, field in _column_targets(session).values() if field == group["field"]]
        parent = session.target_doctype if session.target_doctype in parents else next(iter(parents), None)
    out = {**group, "parent": parent or session.target_doctype}
    if group.get("cause") == dry_run.CAUSE_MISSING_LINK:
        df = frappe.get_meta(out["parent"]).get_field(group["field"])
        out["link_doctype"] = df.options if df else None
    return out


# -- closest existing values -------------------------------------------------------------


#: How files write a currency other than by its code, which no spelling match finds ("RS" isn't
#: close to "INR"): the code it means, offered first when that currency is switched on.
CURRENCY_WORDS = {
    "rs": "INR",
    "rs.": "INR",
    "rupee": "INR",
    "rupees": "INR",
    "₹": "INR",
    "$": "USD",
    "us$": "USD",
    "dollar": "USD",
    "dollars": "USD",
    "€": "EUR",
    "euro": "EUR",
    "euros": "EUR",
    "£": "GBP",
    "pound": "GBP",
    "pounds": "GBP",
}

#: How files, Tally's above all, write a unit short, which no spelling match finds ("Mtr" is 0.75
#: like "Meter"): the ERPNext UOM it means, offered when that UOM is switched on (#34001).
UOM_WORDS = {
    **dict.fromkeys(("mtr", "mtrs", "mt", "mts", "m", "metre", "metres", "meters"), "Meter"),
    **dict.fromkeys(("kgs", "kg.", "kilo", "kilos", "kilogram", "kilograms"), "Kg"),
    **dict.fromkeys(("ltr", "ltrs", "lt", "lts", "l", "liter", "liters", "litres"), "Litre"),
    **dict.fromkeys(("gm", "gms", "g", "grm", "grms", "grams"), "Gram"),
    **dict.fromkeys(("no", "no.", "nos.", "number", "numbers"), "Nos"),
    **dict.fromkeys(("cm", "cms", "centimetre", "centimetres"), "Centimeter"),
    **dict.fromkeys(("mm", "mms", "millimetre", "millimetres"), "Millimeter"),
    **dict.fromkeys(("ft", "feet", "foot."), "Foot"),
    **dict.fromkeys(("in", "inches", "inch."), "Inch"),
    **dict.fromkeys(("sqm", "sq.m", "sq m", "sq.mtr", "sq mtr", "sqmtr"), "Square Meter"),
    **dict.fromkeys(("sqft", "sq.ft", "sq ft", "sft"), "Square Foot"),
    **dict.fromkeys(("cbm", "cu.m", "cum", "cu m"), "Cubic Meter"),
    **dict.fromkeys(("ml", "mls", "millilitre", "milliliter"), "Millilitre"),
    **dict.fromkeys(("prs", "pairs"), "Pair"),
}
WORDS = {"Currency": CURRENCY_WORDS, "UOM": UOM_WORDS}

#: Another system's word for a choice, and the choice it most likely means: suggested only when the
#: field has that choice, never applied without the user (live: Finished, In process, Created).
OPTION_WORDS = {
    "finished": "Completed",
    "done": "Completed",
    "closed": "Completed",
    "complete": "Completed",
    "in process": "Open",
    "in progress": "Open",
    "ongoing": "Open",
    "active": "Open",
    "created": "Open",
    "new": "Open",
    "hold": "On hold",
    "on hold": "On hold",
    "paused": "On hold",
    "canceled": "Cancelled",
    "dropped": "Cancelled",
}


def word_for(doctype: str, value: str) -> Optional[str]:
    """The record a file's word for it means (Rs: INR, Mtr: Meter), when it is switched on."""
    meant = (WORDS.get(doctype) or {}).get(cstr(value).strip().casefold())
    if meant and frappe.db.exists(doctype, {"name": meant, **_switched_on(frappe.get_meta(doctype))}):
        return meant
    return None


#: Trees whose group nodes ERPNext refuses as a link: a Customer's group (Customer.validate), and
#: an Account, Cost Center or Warehouse in a transaction. A group Territory, Item Group or Supplier
#: Group is accepted (PR #392, F5: the group territory "Karnataka" was never offered for "Karnatka").
LEAF_ONLY_TREES = frozenset({"Account", "Cost Center", "Warehouse", "Customer Group"})


def closest_names(
    doctype: str, value: str, limit: int = CLOSEST_LIMIT, groups: Optional[bool] = None
) -> List[str]:
    """Existing names of ``doctype`` closest to ``value``, best first, that the user can read.

    A record is matched on its name, title and search fields (#34407): a master named by a series
    (CUST-00012) is found by "Acme Ltd". Disabled records are left out, and a tree's group nodes
    where a link to them fails (LEAF_ONLY_TREES); ``groups`` says it for the link at hand (True for
    a tree's own parent field, which only a group can be).
    """
    if not frappe.has_permission(doctype, "read"):
        return []
    meta = frappe.get_meta(doctype)
    filters = _switched_on(meta)
    if groups is None:
        groups = doctype not in LEAF_ONLY_TREES
    if meta.is_tree and meta.has_field("is_group") and not groups:
        filters["is_group"] = 0
    fields = ["name", *_text_fields(meta)]

    if frappe.db.count(doctype) <= FULL_SCAN:
        records = frappe.get_list(doctype, filters=filters, fields=fields, limit_page_length=FULL_SCAN)
    else:
        records = []
        for word in _words(value)[:5]:
            records += frappe.get_list(
                doctype,
                filters=filters,
                or_filters={field: ["like", f"%{word}%"] for field in fields},
                fields=fields,
                limit_page_length=WORD_MATCHES,
            )
    name_of: Dict[str, str] = {}
    for record in records:
        for field in fields:
            text = cstr(record.get(field)).strip()
            if text:
                name_of.setdefault(text, record.name)
    ranked = list(dict.fromkeys(name_of[text] for text in rank(value, list(name_of), len(name_of))))[:limit]
    meant = word_for(doctype, value)
    if meant:
        ranked = [meant] + [name for name in ranked if name != meant][: limit - 1]
    return ranked


def _planned(session, doctype: Optional[str]) -> List[str]:
    """The ``doctype`` records the earlier files of the session's plan create (#34244 AC5)."""
    if not doctype or not session.get("migration_plan"):
        return []
    from frappe_assistant_core.utils import import_plan

    return import_plan.planned_titles(session, doctype)


def _closest(session, doctype: str, value: str, groups: Optional[bool] = None) -> List[str]:
    """closest_names, and the records the plan's earlier files create that come close: a value
    misspelling one of those is mapped to it, not created as a record of its own."""
    closest = closest_names(doctype, value, groups=groups)
    planned = rank(value, _planned(session, doctype))
    return list(dict.fromkeys(planned + closest))[:CLOSEST_LIMIT] if planned else closest


def _text_fields(meta) -> List[str]:
    """The DocType's title and search fields that hold text, which a user knows a record by."""
    names = [meta.title_field, *cstr(meta.search_fields).split(",")]
    out = []
    for name in (n.strip() for n in names if n and n.strip()):
        df = meta.get_field(name)
        if df and df.fieldtype in ("Data", "Small Text", "Text", "Read Only") and name not in out:
            out.append(name)
    return out


def _switched_on(meta) -> Dict[str, int]:
    """Filters for the records not switched off: by "disabled", or by "enabled" (UOM, Currency)."""
    filters = {}
    if meta.has_field("disabled"):
        filters["disabled"] = 0
    if meta.has_field("enabled"):
        filters["enabled"] = 1
    return filters


def rank(value: str, candidates: List[str], limit: int = CLOSEST_LIMIT) -> List[str]:
    scored = [(score(value, c), c) for c in dict.fromkeys(cstr(c) for c in candidates) if c]
    scored = [(s, c) for s, c in scored if s >= MIN_SCORE]
    scored.sort(key=lambda pair: (-pair[0], len(pair[1]), pair[1]))
    return [c for _s, c in scored[:limit]]


def likely(value: str, names: List[str]) -> Optional[str]:
    """The name ``value`` is almost surely a misspelling of ("Hospitls" → "Hospitals"), well ahead
    of the next: creating ``value`` as a new record would make a misspelt master. Spelling only: a
    value inside a longer name ("Retail" → "Retail Customers") may well be a record of its own."""
    spelt = sorted(((_spelling(value, name), name) for name in names), reverse=True)
    if not spelt or spelt[0][0] < LIKELY_SPELLING:
        return None
    if len(spelt) > 1 and spelt[1][0] > spelt[0][0] - LIKELY_LEAD:
        return None
    return spelt[0][1]


def _one_letter_apart(value: str, name: str) -> bool:
    """One letter added, left out or changed, ignoring case and spaces: "Karnatka" / "Karnataka"."""
    a, b = (re.sub(r"\s+", " ", cstr(text)).strip().casefold() for text in (value, name))
    if a == b or abs(len(a) - len(b)) > 1:
        return a == b
    if len(a) > len(b):
        a, b = b, a
    for i in range(len(b)):
        if i >= len(a) or a[i] != b[i]:
            return a[i + (len(a) == len(b)) :] == b[i + 1 :]
    return True


def _spelling(value: str, candidate: str) -> float:
    v, c = " ".join(_words(value)).casefold(), " ".join(_words(candidate)).casefold()
    return difflib.SequenceMatcher(None, v, c).ratio() if v and c else 0.0


def score(value: str, candidate: str) -> float:
    """How likely ``candidate`` is the record ``value`` meant, from 0 to 1.

    Spelling ("Retial" → "Retail"), containment ("Retail" → "Retail Customers") and shared
    words ("Cust Retail" → "Retail Customers") each count.
    """
    v, c = " ".join(_words(value)).casefold(), " ".join(_words(candidate)).casefold()
    if not v or not c:
        return 0.0
    if v == c:
        return 1.0
    best = difflib.SequenceMatcher(None, v, c).ratio()
    if v in c or c in v:
        best = max(best, 0.85)
    shared = set(v.split()) & set(c.split())
    if shared:
        best = max(best, 0.6 + 0.3 * len(shared) / len(set(v.split())))
    return round(best, 3)


def _words(text: str) -> List[str]:
    return re.findall(r"\w+", cstr(text))


# -- explaining a group ----------------------------------------------------------------


def known_refusals() -> Tuple[Tuple[str, str], ...]:
    """ERPNext's and India Compliance's refusals that come as a plain "Rejected by ERPNext", with what
    they mean in the user's words (#34417): (pattern of the message, explanation; {0} is "3 rows").
    Built per call, so the explanations are translated into the request's language."""
    return (
        (
            r"HSN.{0,3}SAC|HSN code",
            _(
                "{0}: India Compliance needs an HSN/SAC code on each item. Map the column that has it, "
                "or give one code for every item (fill)."
            ),
        ),
        (
            r"GSTIN",
            _(
                "{0}: the GSTIN isn't one India Compliance accepts. A GSTIN has 15 characters and starts "
                "with the state's two-digit code: correct it in the file."
            ),
        ),
        (
            r"not in any active Fiscal Year|Fiscal Year .{0,60}(not found|does not exist|doesn't exist)",
            _(
                "{0}: the date isn't in a fiscal year ERPNext has. Create that fiscal year first, or correct the date."
            ),
        ),
        (
            r"negative stock|insufficient stock|(not|isn't) available in (the )?warehouse",
            _(
                "{0}: there isn't enough stock in the warehouse for this. Bring in the opening stock "
                "first, or import the receipts before."
            ),
        ),
        (
            r"\bis disabled\b",
            _(
                "{0}: a record these rows point to is disabled in ERPNext. Enable it, or point the rows at another one."
            ),
        ),
    )


def known_refusal(message: Optional[str], rows: str) -> Optional[str]:
    """The user's words for a refusal ERPNext only said in its own, or None."""
    for pattern, explanation in known_refusals():
        if re.search(pattern, cstr(message), re.IGNORECASE):
            return explanation.format(rows)
    return None


def advise(session, group: Dict[str, Any]) -> Dict[str, Any]:
    """A plain explanation of ``group`` and the fixes that fit it, with the closest names."""
    group = _with_target(session, group)
    cause, count = group.get("cause"), group.get("count") or 0
    label, value = _(group.get("label") or group.get("field") or ""), group.get("value")
    rows = _rows(count)
    leave_out = {"action": LEAVE_OUT, "rows": count}

    if cause == dry_run.CAUSE_MISSING_LINK and group.get("link_doctype"):
        doctype = group["link_doctype"]
        explanation = _("{0}: there is no {1} called '{2}' in ERPNext.").format(rows, _(doctype), value)
        parent_meta = frappe.get_meta(group.get("parent") or session.target_doctype)
        is_parent = parent_meta.is_tree and group.get("field") == parent_meta.get("nsm_parent_field")
        closest = _closest(session, doctype, value, groups=True if is_parent else None)
        fixes = [{"action": MAP, "closest": closest}]
        spelt = likely(value, closest)
        meant = spelt or word_for(doctype, value)  # Mtr is Meter, though not spelt alike
        if meant:
            fixes[0]["likely"] = meant
            explanation += " " + (
                _("It is most likely '{0}', misspelt.")
                if spelt
                else _("It is most likely '{0}', written short.")
            ).format(meant)
        reason = _creating_problem(doctype, session)
        if not reason and (group["parent"], group["field"]) in import_keys.translated_fields(session):
            # An old ID (#34244): a record named by it would stay in ERPNext as a stand-in (DM52's IG-199)
            reason = _("'{0}' is an ID of the old system, not a name").format(value)
        if not reason and spelt and _one_letter_apart(value, spelt):
            # "Karnatka" beside "Karnataka" is a typo, never a new record (PR #392, F5)
            reason = _("'{0}' is one letter away from '{1}', which is already there").format(value, spelt)
        if not reason and meant and not spelt:
            # Mtr is Meter written short, never a new UOM: offered, it was created (live, 2026-11-06)
            reason = _("'{0}' is how '{1}' is written short").format(value, meant)
        if not reason:
            create = {"action": CREATE, "doctype": doctype, "name": value, "parent": default_parent(doctype)}
            if not session.get("migration_plan"):  # in a plan, it is a fix: the plan creates it when it runs
                create["use"] = "create_document"
            if meant:
                create["note"] = _("Only if '{0}' is really a new {1}, not a misspelt '{2}'.").format(
                    value, _(doctype), meant
                )
            fixes.append(create)
        drop = _drop_fix(session, group)
        if drop:
            fixes.append(drop)
        fixes.append(leave_out)
        out = {"explanation": explanation, "fixes": fixes}
        if reason:
            out["cannot_create"] = _("A {0} can't be created here: {1}.").format(_(doctype), reason)
        return out

    if cause == dry_run.CAUSE_BAD_OPTION:
        options = _select_options(session, group)
        explanation = _("{0}: '{1}' isn't one of the choices for {2} ({3}).").format(
            rows, value, label, ", ".join(options)
        )
        closest = rank(value, options) or options[:CLOSEST_LIMIT]
        fix = {"action": MAP, "closest": closest}
        meant = OPTION_WORDS.get(cstr(value).strip().casefold())
        if meant in options:
            fix["likely"] = meant
            if meant not in closest:
                fix["closest"] = [meant, *closest][:CLOSEST_LIMIT]
        drop = _drop_fix(session, group)
        return {"explanation": explanation, "fixes": [fix, *([drop] if drop else []), leave_out]}

    from frappe_assistant_core.utils import import_opening_stock as opening_stock

    if cause in opening_stock.NEW_CAUSES:
        explanation = _("{0}: {1}").format(rows, group.get("message") or _(cause))
        fixes = [leave_out]
        if cause == opening_stock.CAUSE_NO_RATE:
            fixes.insert(0, {"action": ALLOW_ZERO_RATE, "note": _("Only if this stock really has no value.")})
        if cause in (opening_stock.CAUSE_OTHER_COMPANY, opening_stock.CAUSE_GROUP_WAREHOUSE):
            fixes.insert(0, {"action": MAP, "closest": closest_names("Warehouse", value)})
        return {
            "explanation": explanation,
            "fixes": fixes,
            "fix_in_file": cause != opening_stock.CAUSE_TOTALS_ROW,
        }

    from frappe_assistant_core.utils import import_opening_invoices as opening_invoices

    if cause in opening_invoices.NEW_CAUSES:
        explanation = _("{0}: {1}").format(rows, group.get("message") or _(cause))
        fixes = [leave_out]
        if cause == opening_invoices.CAUSE_NO_FISCAL_YEAR:
            cut_off = opening_invoices.settings(session).get("cut_off")
            fixes.insert(
                0,
                {
                    "action": POST_AT_CUTOFF,
                    "note": _(
                        "Posts them at the cut-off date ({0}), keeping the due date unless it is "
                        "earlier; the old date goes in the remarks."
                    ).format(cut_off),
                },
            )
        if cause == opening_invoices.CAUSE_PARTY_DISABLED:
            party_type = opening_invoices.settings(session).get("party_type")
            fixes.insert(0, {"action": MAP, "closest": closest_names(party_type, value)})
        return {"explanation": explanation, "fixes": fixes, "fix_in_file": True}

    from frappe_assistant_core.utils import import_opening_balances as opening_balances

    if cause == opening_balances.CAUSE_NOT_BALANCED:
        # No fixes: the file itself is wrong, so it must be corrected and checked again.
        explanation = _(
            "{0} The file's debits and credits must be made to balance in the file; it is then checked again."
        ).format(group.get("message") or _(cause))
        return {"explanation": explanation, "fixes": [], "fix_in_file": True}

    if cause in opening_balances.NEW_CAUSES:
        explanation = _("{0}: {1}").format(rows, group.get("message") or _(cause))
        fixes = [leave_out]
        if cause in opening_balances.BY_VALUE:
            fixes.insert(0, {"action": MAP, "closest": closest_names("Account", value)})
        return {"explanation": explanation, "fixes": fixes, "fix_in_file": True}

    explanations = {
        dry_run.CAUSE_BAD_DATE: _("{0}: {1} isn't a date ERPNext can read. {2}"),
        dry_run.CAUSE_BAD_VALUE: _("{0}: a value ERPNext can't use. {2}"),
        dry_run.CAUSE_DUPLICATE_IN_FILE: _(
            "{0}: the {1} repeats one earlier in the file, and only the first can be imported."
        ),
        dry_run.CAUSE_ALREADY_EXISTS: _(
            "{0}: a record with this {1} is already in ERPNext, so importing would duplicate it."
        ),
        dry_run.CAUSE_REJECTED: _("{0} rejected by ERPNext: {2}"),
        dry_run.CAUSE_REQUIRED_MISSING: _(
            "{0}: {1} is empty, and a new record can't be saved without it. Fill it in the file, "
            "give every row one value (fill), or leave the rows out."
        ),
        dry_run.CAUSE_NO_MATCH: _("{0}: no record has this {1}, so there is nothing to update. {2}"),
        dry_run.CAUSE_MANY_MATCHES: _(
            "{0}: more than one record has this {1}, so FACO can't tell which. {2}"
        ),
        dry_run.CAUSE_SAME_RECORD: _("{0}: another row updates the same record, so only the first can. {2}"),
        dry_run.CAUSE_FETCHED: _("{0}: {2}"),
        dry_run.CAUSE_SUMMARY_ROW: _(
            "{0}: a total or footer line of the spreadsheet, not a record. Leave it out; if it "
            "really is a record, change it in the file."
        ),
    }
    template = explanations.get(cause, _("{0} would fail. {2}"))
    explanation = template.format(rows, label, group.get("message") or "").strip()
    if cause == dry_run.CAUSE_REJECTED:
        # in business words when FACO knows the message; ERPNext's own stays in the group's message
        explanation = known_refusal(group.get("message"), rows) or explanation
    if group.get("values"):
        # The values a refusal's message quoted, "…" in it (#34407)
        explanation += " " + _("Values: {0}.").format(_listed(group["values"]))
    fixes = [leave_out]
    if cause == dry_run.CAUSE_DUPLICATE_IN_FILE and group.get("field"):
        # keep every row: the later ones get their ID, or a number, added to the name (MAKE_UNIQUE)
        fixes.insert(0, {"action": MAKE_UNIQUE, "add": ["id", "number"]})
    blank = _fill_field(session, group)
    if blank:
        # One value for every row: the HSN code of a file of items, say (#34415)
        fixes.insert(0, {"action": FILL, "field": blank.fieldname, "label": _(blank.label)})
    # Anything else is corrected in the file, which is then checked again.
    return {"explanation": explanation, "fixes": fixes, "fix_in_file": True}


def _drop_fix(session, group: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Leaving the column empty in every row, when the record can be saved without it: no row is lost.
    Live, 2026-11-19: 2,083 of 2,084 projects were left out over a Department column."""
    try:
        entry = _droppable(session, group)
    except FixProblem:
        return None
    return {"action": DROP_COLUMN, "note": _("{0} stays empty; every row is kept.").format(entry["label"])}


def _listed(values: List[str], shown: int = 5) -> str:
    """The first ``shown`` values, and how many more."""
    text = ", ".join(values[:shown])
    if len(values) > shown:
        text += " " + _("and {0} more").format(len(values) - shown)
    return text


def _select_options(session, group: Dict[str, Any]) -> List[str]:
    meta = frappe.get_meta(group.get("parent") or session.target_doctype)
    df = meta.get_field(group.get("field"))
    return [o for o in cstr(df.options if df else "").split("\n") if o]


# -- applying fixes ------------------------------------------------------------------


#: The fixes saved, each as sent (its group id with it): the same fix sent again is said saved, not refused
#: as an unknown group; another fix for that group still is
FIXED_GROUPS = "fixed_groups"
FIXED_GROUPS_KEPT = 2000


def _signature(fix: Dict[str, Any]) -> str:
    return json.dumps(fix, sort_keys=True, default=str)


def apply_fixes(session, groups: Dict[str, Dict[str, Any]], fixes: List[Dict[str, Any]]) -> List[str]:
    """Check every fix, then store them all on the session, or none if any is wrong.

    ``groups`` are the last dry run's groups by id, with all their rows. Returns one plain
    sentence per fix applied. The caller saves the session and checks it again.
    """
    from frappe_assistant_core.utils import import_opening_balances as opening_balances

    fixes = _expanded(fixes)
    maps = value_maps(session)
    filled = fills(session)
    reasons = {str(entry["row"]): entry["reason"] for entry in left_out(session)}
    row_problems = left_out_problems(session)
    zero_rate = list(_rules(session).get("zero_rate_items") or [])
    renamed = renames(session)
    dropped_fields = dropped(session)
    post_at_cutoff = bool(_rules(session).get("post_at_cutoff"))
    saved_before = list(_rules(session).get(FIXED_GROUPS) or [])
    fixed_now = []
    done, problems, planned = [], [], []
    for fix in fixes:
        group = groups.get(cstr(fix.get("group")))
        if not group and _signature(fix) in saved_before:
            # live, 2026-11-20: the same fixes sent again after the check that applied them; that check no
            # longer has their groups (they're fixed), so they were refused and the call made a third time
            done.append(_("The fix for {0} was already saved.").format(fix.get("group")))
            continue
        try:
            if not group:
                # live, 2026-11-19: a fix from an earlier check listed all 280 groups, five times
                raise FixProblem(
                    _(
                        "There is no group {0} in the last check: group ids change with every check. Use "
                        "the ids of the latest check's card (or decisions)."
                    ).format(fix.get("group"))
                )
            group = _with_target(session, group)
            fixed_now.append(_signature(fix))
            action = fix.get("action")
            if group.get("cause") == opening_balances.CAUSE_NOT_BALANCED:
                raise FixProblem(
                    _("Debits and credits that don't balance can only be corrected in the file.")
                )
            if action == MAP:
                maps = _map(session, group, fix, maps)
                done.append(
                    _("{0} '{1}' becomes '{2}' in {3}.").format(
                        _(group["label"]), group["value"], fix["to"], _rows(group["count"])
                    )
                )
            elif action == LEAVE_OUT:
                from frappe_assistant_core.utils.import_failures import fix_of

                error = group.get("message") or group["cause"]
                reason = cstr(fix.get("reason")).strip() or error
                problem = {"error": error, "fix": fix_of(session, group)}
                for row in group["rows"]:
                    reasons.setdefault(str(row), reason)
                    row_problems.setdefault(str(row), problem)
                done.append(_("Left out {0}: {1}.").format(_rows(group["count"]), row_ranges(group["rows"])))
            elif action == ALLOW_ZERO_RATE:
                from frappe_assistant_core.utils import import_opening_stock as opening_stock

                if group["cause"] != opening_stock.CAUSE_NO_RATE:
                    raise FixProblem(_("Only rows with no valuation rate can be allowed a zero rate."))
                if group["value"] not in zero_rate:
                    zero_rate.append(group["value"])
                done.append(
                    _("{0} is brought in at zero value in {1}.").format(group["value"], _rows(group["count"]))
                )
            elif action == POST_AT_CUTOFF:
                from frappe_assistant_core.utils import (
                    import_opening_invoices as opening_invoices,
                )

                if group["cause"] != opening_invoices.CAUSE_NO_FISCAL_YEAR:
                    raise FixProblem(
                        _("Only invoices dated in no fiscal year can be posted at the cut-off date.")
                    )
                post_at_cutoff = True
                done.append(_("{0} are posted at the cut-off date.").format(_rows(group["count"])))
            elif action == FILL:
                filled = _fill(session, group, fix, filled)
                done.append(
                    _("{0} is '{1}' in {2}.").format(
                        _(filled[-1]["label"]), filled[-1]["value"], _rows(group["count"])
                    )
                )
            elif action == MAKE_UNIQUE:
                renamed.update(_unique_names(session, group, fix, renamed))
                done.append(
                    _("{0}: {1} repeated names made unique, e.g. '{2}'.").format(
                        _(group["label"]),
                        group["count"],
                        next(iter(renamed.values()))["value"] if renamed else "",
                    )
                )
            elif action == DROP_COLUMN:
                entry = _droppable(session, group)
                if entry not in dropped_fields:
                    dropped_fields.append(entry)
                done.append(
                    _("{0} is left empty in every row; no row is left out.").format(_(entry["label"]))
                )
            elif action == CREATE:
                if not session.get("migration_plan"):
                    raise FixProblem(
                        _(
                            "Create missing records with create_document and import_session: "
                            "planned_masters {count: masters_plan_total or the masters_plan length} "
                            "creates every planned one in one approval (ask a party's group and "
                            "territory once, as shared), or documents from masters_plan for a few. "
                            "Then call dry_run_import again without fixes. "
                            "create as a fix is for a session in a migration plan."
                        )
                    )
                item = _plan_master(session, group, fix)
                planned.append(item)
                done.append(
                    _("{0} '{1}' is created when the plan runs.").format(
                        _(item["doctype"]), _planned_name(item)
                    )
                )
            else:
                raise FixProblem(_("action must be one of: {0}.").format(", ".join(ACTIONS)))
        except FixProblem as e:
            problems.append({"group": fix.get("group"), "error": str(e)})

    if problems:
        raise FixProblems(problems)
    if planned:
        from frappe_assistant_core.utils import import_plan

        import_plan.add_masters(session, planned)

    rules = {
        "value_maps": maps,
        "fills": filled,
        "left_out": reasons,
        "left_out_problems": {row: problem for row, problem in row_problems.items() if row in reasons},
        "zero_rate_items": zero_rate,
        "post_at_cutoff": post_at_cutoff,
        "renames": renamed,
        "dropped_fields": dropped_fields,
        FIXED_GROUPS: list(dict.fromkeys(saved_before + fixed_now))[-FIXED_GROUPS_KEPT:],
    }
    rules = {key: value for key, value in rules.items() if value}
    # what the fixes don't own stays: the column that holds the old ID, and the references it translates
    kept = {key: value for key, value in _rules(session).items() if key in import_keys.RULE_KEYS and value}
    rules = {**rules, **kept}
    session.transformation_rules = frappe.as_json(rules) if rules else None
    session.excluded_rows = frappe.as_json(sorted(int(row) for row in reasons)) if reasons else None
    if session.source_file:
        # Until a check of them, the fixes are why the session isn't what was checked (#34607)
        options = frappe.parse_json(session.template_options or "{}") or {}
        options[dry_run.UNCHECKED_FIXES] = dry_run.fingerprint(session, readable_session_file(session))
        session.template_options = frappe.as_json(options)
    session.log_step("Fix Errors", "Success", " ".join(done))
    return done


def forget_left_out(session) -> str:
    """Put back every row left out, for a different file: its rows aren't the ones that were
    left out. Value maps stay, as they follow values, not rows. Returns what to tell the user."""
    rows = dry_run._excluded_rows(session)
    if not rows:
        return ""
    rules = _rules(session)
    rules.pop("left_out", None)
    rules.pop("left_out_problems", None)
    session.transformation_rules = frappe.as_json(rules) if rules else None
    session.excluded_rows = None
    note = _("This is a different file, so the {0} left out before are checked again.").format(
        _rows(len(rows))
    )
    session.log_step("Fix Errors", "Success", note)
    session.save()
    return note


def _map(session, group, fix, maps):
    from frappe_assistant_core.utils import import_opening_balances as opening_balances
    from frappe_assistant_core.utils import import_opening_invoices as opening_invoices
    from frappe_assistant_core.utils import import_opening_stock as opening_stock

    # Causes besides a missing link whose fix is another record of a DocType: which DocType.
    other_records = {
        opening_stock.CAUSE_OTHER_COMPANY: "Warehouse",
        opening_stock.CAUSE_GROUP_WAREHOUSE: "Warehouse",
        opening_invoices.CAUSE_PARTY_DISABLED: opening_invoices.settings(session).get("party_type"),
        opening_balances.CAUSE_NOT_THIS_COMPANY: "Account",
        opening_balances.CAUSE_GROUP_ACCOUNT: "Account",
        opening_balances.CAUSE_DISABLED_ACCOUNT: "Account",
    }
    if group["cause"] not in (dry_run.CAUSE_MISSING_LINK, dry_run.CAUSE_BAD_OPTION, *other_records):
        raise FixProblem(
            _(
                "Only a missing link or a value that isn't an allowed option can be mapped. "
                "Leave these rows out, or correct them in the file."
            )
        )
    to = cstr(fix.get("to")).strip()
    if not to:
        raise FixProblem(_("Say which existing value to use, in 'to'."))
    if group["cause"] in (dry_run.CAUSE_MISSING_LINK, *other_records):
        doctype = group.get("link_doctype") or other_records.get(group["cause"])
        coming = {name.casefold(): name for name in _planned(session, doctype)}.get(to.casefold())
        if coming and not frappe.db.exists(doctype, to):
            to = coming  # an earlier file of the plan creates it before these rows are imported
        else:
            _check_existing(session, group, doctype, to)
    elif to not in _select_options(session, group):
        raise FixProblem(
            _("'{0}' isn't one of the choices for {1}: {2}.").format(
                to, _(group["label"]), ", ".join(_select_options(session, group))
            )
        )
    rule = {
        "parent": group["parent"],
        "field": group["field"],
        "label": group["label"],
        "from": group["value"],
        "to": to,
    }
    # A new choice for the same value replaces the earlier one.
    same = (rule["parent"], rule["field"], cstr(rule["from"]))
    return [m for m in maps if (m.get("parent"), m.get("field"), cstr(m.get("from"))) != same] + [rule]


def _check_existing(session, group, doctype: Optional[str], to: str) -> None:
    """A value mapped to must be a record in ERPNext the user can read and the rows can use."""
    from frappe_assistant_core.utils import import_opening_balances as opening_balances

    if not doctype or not frappe.db.exists(doctype, to) or not frappe.has_permission(doctype, "read", doc=to):
        closest = _closest(session, doctype, to) if doctype else []
        raise FixProblem(
            _("There is no {0} called '{1}'.").format(_(doctype or group["label"]), to)
            + (" " + _("Closest: {0}.").format(", ".join(closest)) if closest else "")
        )
    if doctype == "Account" and opening_balances.is_opening_balances(session):
        _check_account(session, to)
    if not frappe.db.exists(doctype, {"name": to, **_switched_on(frappe.get_meta(doctype))}):
        closest = closest_names(doctype, to)
        raise FixProblem(
            _("{0} '{1}' is switched off, so the rows can't use it.").format(_(doctype), to)
            + (" " + _("Closest: {0}.").format(", ".join(closest)) if closest else "")
        )


# -- creating the missing masters (#33992) -------------------------------------------------


def _check_account(session, name: str) -> None:
    """An account that can take the entry: a ledger, enabled, of the session's company."""
    from frappe_assistant_core.utils import import_opening_balances as opening_balances

    account = frappe.db.get_value("Account", name, ["is_group", "disabled", "company"], as_dict=True)
    company = opening_balances.settings(session).get("company")
    if account.is_group or account.disabled or (company and account.company != company):
        raise FixProblem(
            _("{0} can't take entries: it must be an enabled ledger account of {1}.").format(
                name, company or _("the session's company")
            )
        )


def _creating_problem(doctype: str, session) -> str:
    """Why the missing ``doctype`` record of ``session``'s rows can't be created, or "". In a
    migration plan, the plan creates it when it runs, as create_planned does, with no session: a
    party, which create_document makes for an opening-invoices file, it can't make (ERPNext names
    it in code), so it isn't offered and an approved plan never refuses to run over it."""
    reason = cannot_create(doctype, session)
    if not reason and session.get("migration_plan"):
        reason = cannot_create(doctype)
    return reason


def cannot_create(doctype: str, session=None) -> str:
    """Why a missing ``doctype`` record can't be created here, or "" when it can.

    Only a master that needs nothing but its name (and a parent, in a tree) and that keeps
    the name it is given: otherwise the record created isn't the one the rows link to. For
    ``session``, never a record of the DocType the file itself imports: a missing one is a
    row of the file (a tree's parent, say), which the import creates as the file has it.
    """
    if session and doctype == session.target_doctype:
        return _("the file imports {0} records itself, so add it to the file").format(_(doctype))
    if is_party(session, doctype):
        if doctype in (frappe.conf.get("fac_import_never_create_doctypes") or []):
            return _("this site doesn't allow creating it during an import")
        # A party may be named by a series: the rows find it by its customer or supplier name.
        if not frappe.has_permission(doctype, "create"):
            return _("you aren't allowed to create a {0}").format(_(doctype))
        if not _may_use_create_document():
            return _("creating records with FACO is turned off for you")
        return ""
    if doctype in NEVER_CREATE:
        return _(NEVER_CREATE[doctype])
    if doctype in COMPANY_NAMED:
        # created for the import's company, found by "<name> - <abbr>" (_company_named)
        if not frappe.has_permission(doctype, "create"):
            return _("you aren't allowed to create a {0}").format(_(doctype))
        if not _may_use_create_document():
            return _("creating records with FACO is turned off for you")
        return ""
    if doctype in (frappe.conf.get("fac_import_never_create_doctypes") or []):
        return _("this site doesn't allow creating it during an import")
    meta = frappe.get_meta(doctype)
    if meta.issingle or meta.istable or meta.is_virtual or meta.is_submittable:
        return _("it isn't a master record")
    if frappe.local.module_app.get(frappe.scrub(meta.module)) == "frappe":
        return _("it's a system record")
    name_field = _name_field(meta)
    if not name_field:
        return _("ERPNext names it itself, so it wouldn't get the name the file uses")
    name_df = meta.get_field(name_field)
    if name_df and name_df.fieldtype in ("Link", "Dynamic Link"):
        return _("its name must be an existing {0}").format(_(name_df.options or name_df.label))
    needs = _other_required(meta)
    if needs:
        return _("it needs more than a name ({0})").format(", ".join(_(df.label) for df in needs))
    if not frappe.has_permission(doctype, "create"):
        return _("you aren't allowed to create a {0}").format(_(doctype))
    if not _may_use_create_document():
        return _("creating records with FACO is turned off for you")
    return ""


def is_party(session, doctype: str) -> bool:
    """A Customer or Supplier masters_plan proposes with its type, group and territory: an
    opening-invoices file's party, found by its name whatever ERPNext names it, or one any file
    links to when Selling or Buying Settings name a new one by its customer or supplier name, so
    the record created has the name the rows use. Live, 2026-11-17: 262 customers a projects file
    named were refused as "ERPNext names it itself", and imported as a second file."""
    from frappe_assistant_core.utils import import_opening_invoices as opening_invoices

    if opening_invoices.is_party(session, doctype):
        return True
    if not session:
        # A migration plan creates its masters with create_master, which sends only the name: a
        # party needs its group and territory, so an approved plan would refuse to run over it.
        return False
    name_field = opening_invoices.PARTY_NAME_FIELDS.get(doctype)
    return bool(name_field) and dry_run._name_field(doctype) == name_field


def _may_use_create_document() -> bool:
    """The records are created through create_document, so its settings in FAC Tool
    Configuration (turned off, or kept to some roles) apply here too."""
    from frappe_assistant_core.core.tool_registry import get_tool_registry

    return get_tool_registry()._is_tool_accessible("create_document", frappe.session.user)


def _name_field(meta) -> Optional[str]:
    """The field whose value becomes the record's name, when the name is the user's."""
    autoname = cstr(meta.autoname).strip()
    if autoname.lower().startswith("field:"):
        return autoname[len("field:") :].strip()
    if autoname.lower() == "prompt":
        return "__newname"
    return None


def _parent_field(meta) -> Optional[str]:
    if not meta.is_tree:
        return None
    return meta.get("nsm_parent_field") or f"parent_{frappe.scrub(meta.name)}"


def _other_required(meta) -> list:
    """Required fields besides the name and the parent, a required table (one row at least)
    among them."""
    own = {_name_field(meta), _parent_field(meta), "naming_series"}
    return [
        df
        for df in meta.fields
        if df.reqd
        and not df.default
        and df.fieldname not in own
        and (df.fieldtype in table_fields or df.fieldtype not in no_value_fields)
    ]


def default_parent(doctype: str) -> Optional[str]:
    """Where a new record of a tree goes unless the user says otherwise: under its root,
    when the root can hold records (a tree may have several roots, some of them leaves)."""
    if not frappe.get_meta(doctype).is_tree:
        return None
    root = get_root_of(doctype)
    return root if root and _holds_records(doctype, root) else None


def _holds_records(doctype: str, name: str) -> bool:
    """Whether ``name`` exists and can have records under it: a group, in a tree that has groups."""
    if frappe.get_meta(doctype).has_field("is_group"):
        return bool(frappe.db.exists(doctype, {"name": name, "is_group": 1}))
    return bool(frappe.db.exists(doctype, name))


def id_column(session, rows: List[List[str]]) -> Optional[int]:
    """The column of the file that tells its rows apart: mapped to the record's ID, the old ID column, or a
    column headed "... ID" whose values are all different. None when the file has none."""
    targets = _column_targets(session)
    for position, (parent, field) in targets.items():
        if parent == session.target_doctype and field == "name":
            return position
    key = import_keys.source_key(session)
    if key:
        return int(key["position"])
    for position, heading in enumerate(rows[0] if rows else []):
        if not re.search(r"\b(id|code|no\.?|number)\s*$", cstr(heading).strip().lower()):
            continue
        filled = [row for row in rows[1:] if any(cstr(cell).strip() for cell in row)]
        values = [cstr(row[position]).strip() if position < len(row) else "" for row in filled]
        if values and all(values) and len(set(values)) == len(values):
            return position
    return None


def _unique_names(
    session, group: Dict[str, Any], fix: Dict[str, Any], already: Dict
) -> Dict[str, Dict[str, str]]:
    """Row → new name for each later row of a repeated name: the name with the row's ID ("Accenture - COVID
    (PMSF_0074_01)"), or with a number when the file has no ID column or ``add`` is "number". Never a name
    the file or the site has already. Live, 2026-11-19: 322 sub-projects named like their main project
    could only be left out."""
    if group.get("cause") != dry_run.CAUSE_DUPLICATE_IN_FILE:
        raise FixProblem(_("Only a name repeated in the file can be made unique."))
    from frappe_assistant_core.utils.import_dry_run import read_sheet_rows

    rows = apply_value_maps(session, read_sheet_rows(readable_session_file(session), session.sheet or None))
    targets = _column_targets(session)
    parent = group.get("parent") or session.target_doctype
    at = next((p for p, target in targets.items() if target == (parent, group["field"])), None)
    if at is None:
        raise FixProblem(
            _("No column of the file is mapped to {0}.").format(_(group.get("label") or group["field"]))
        )
    by_id = None if fix.get("add") == "number" else id_column(session, rows)
    taken = {cstr(row[at]).strip().casefold() for row in rows[1:] if at < len(row)}
    if frappe.get_meta(parent).has_field(group["field"]):
        taken |= {
            cstr(v).casefold() for v in frappe.get_all(parent, pluck=group["field"], limit_page_length=0) if v
        }
    out = {}
    for number in sorted(int(r) for r in group["rows"]):
        if number - 1 >= len(rows):
            continue
        row = rows[number - 1]
        base = cstr(row[at]).strip()
        tag = cstr(row[by_id]).strip() if by_id is not None and by_id < len(row) else ""
        candidate, n = (f"{base} ({tag})" if tag else f"{base} (2)"), 2
        while candidate.casefold() in taken:
            n += 1
            candidate = f"{base} ({tag} {n})" if tag else f"{base} ({n})"
        taken.add(candidate.casefold())
        out[str(number)] = {"parent": parent, "field": group["field"], "value": candidate}
    return out


def _droppable(session, group: Dict[str, Any]) -> Dict[str, str]:
    """The column ``group`` is about, to leave empty in every row, or FixProblem when the record can't be
    saved without it."""
    if not group.get("field"):
        raise FixProblem(_("This problem isn't about one column."))
    parent = group.get("parent") or session.target_doctype
    df = frappe.get_meta(parent).get_field(group["field"])
    if df and df.reqd:
        raise FixProblem(_("{0} is required, so it can't be left empty.").format(_(df.label)))
    return {"parent": parent, "field": group["field"], "label": _(df.label) if df else group["field"]}


def masters_plan(session, groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Every missing master the rows need that can be created: what FACO shows the user, as
    one table, before create_document creates them (documents, with import_session). One entry
    per record, with the rows it fixes and its ``data`` as create_document takes it."""
    from frappe_assistant_core.utils import import_opening_invoices as opening_invoices

    plan: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for group in groups:
        group = _with_target(session, group)
        doctype = group.get("link_doctype")
        if group.get("cause") != dry_run.CAUSE_MISSING_LINK or not doctype or cannot_create(doctype, session):
            continue
        choose = {}
        record_name = group["value"]
        if doctype in COMPANY_NAMED:
            company = import_company(session)
            abbr = frappe.get_cached_value("Company", company, "abbr") if company else None
            if not abbr:
                continue
            name_field, company_field = COMPANY_NAMED[doctype]
            meta = frappe.get_meta(doctype)
            parent = default_parent(doctype)
            data = {name_field: group["value"], company_field: company}
            if parent:
                data[_parent_field(meta)] = parent
            record_name = f"{group['value']} - {abbr}"
        elif is_party(session, doctype):
            parent, data = None, opening_invoices.party_data(doctype, group["value"])
            choose = opening_invoices.party_choices(doctype, data)
        else:
            parent = default_parent(doctype)
            meta = frappe.get_meta(doctype)
            data = {_name_field(meta): group["value"]}
            if parent:
                data[_parent_field(meta)] = parent
        entry = plan.setdefault(
            (doctype, group["value"]),
            {
                "group": group["id"],
                "doctype": doctype,
                "name": record_name,
                "value": group["value"],
                "parent": parent,
                "rows": 0,
                "data": data,  # as create_document takes it in documents
            },
        )
        if any(choose.values()):
            # a group or territory the Settings default couldn't give: add one of these to data
            entry["choose"] = choose
        entry["rows"] += group.get("count") or 0
    return list(plan.values())


PLANNED_AT_ONCE = 1000  # missing masters planned_masters creates in one call, inside one request


def planned_documents(session, planned: Any) -> List[Dict[str, Any]]:
    """create_document's planned_masters: every missing master the session's latest check planned
    (masters_plan), as it planned it, with ``shared`` values added to each of a DocType (a
    party's group or territory). Live, 2026-11-17: 262 planned customers had to be listed one by
    one, more than a call takes (100) and more than the assistant could copy back reliably, so it
    asked the user for a separate customer file. ``count`` must be the number planned, so the
    approval card shows it."""
    from frappe_assistant_core.utils import import_opening_invoices as opening_invoices

    if not isinstance(planned, dict):
        raise FixProblem(_("planned_masters is an object: {count, shared}."))
    plan = masters_plan(session, list(last_groups(session).values()))
    by_doctype: Dict[str, int] = {}
    for entry in plan:
        by_doctype[entry["doctype"]] = by_doctype.get(entry["doctype"], 0) + 1
    listed = ", ".join(f"{count} {_(doctype)}" for doctype, count in by_doctype.items()) or _("none")
    if cint(planned.get("count")) != len(plan):
        raise FixProblem(
            _(
                "The last check planned {0} missing masters ({1}). Pass count {0}, so the approval "
                "card shows how many are created."
            ).format(len(plan), listed)
        )
    if not plan:
        raise FixProblem(_("The last check planned no missing masters: nothing to create."))
    if len(plan) > PLANNED_AT_ONCE:
        raise FixProblem(
            _("{0} missing masters are more than one call creates ({1}). Map or leave out some.").format(
                len(plan), PLANNED_AT_ONCE
            )
        )
    shared = planned.get("shared") or {}
    if not isinstance(shared, dict) or any(not isinstance(v, dict) for v in shared.values()):
        raise FixProblem(
            _('shared is {DocType: {field: value}}, e.g. {"Customer": {"customer_group": "Commercial"}}.')
        )
    for doctype, values in shared.items():
        allowed = (
            set(opening_invoices.PARTY_LINKS.get(doctype) or {}) if is_party(session, doctype) else set()
        )
        if doctype not in by_doctype or set(values) - allowed:
            raise FixProblem(
                _("shared takes, for {0}, only {1}.").format(
                    _(doctype), ", ".join(sorted(allowed)) or _("nothing")
                )
            )
    # a group (or territory) the Settings don't give must be chosen: live, 2026-11-19, on a new site 262
    # customers were created with no customer group at all
    for entry in plan:
        for field, options in (entry.get("choose") or {}).items():
            # the group only: a territory may stay empty, as ERPNext lets it
            if field.endswith("_group") and options and not (shared.get(entry["doctype"]) or {}).get(field):
                raise FixProblem(
                    _(
                        "Ask the user which {0} the new {1} records go under (one of: {2}), then pass it "
                        'in shared, e.g. {{"{1}": {{"{0}": "{3}"}}}}.'
                    ).format(field, entry["doctype"], ", ".join(options), options[0])
                )
    return [
        {"doctype": entry["doctype"], "data": {**entry["data"], **(shared.get(entry["doctype"]) or {})}}
        for entry in plan
    ]


def check_masters(session, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """``documents`` sent to create_document with ``import_session``: each must be one of the
    session's missing masters, as the latest check planned it (masters_plan), so nothing is
    created that the rows don't need. A tree record's missing parent may come in the same list:
    it is created first, as a group (#34409). Returns them as they will be created, parents
    first, with each tree record's parent filled in. Raises FixProblem, or FixProblems listing
    every wrong one."""
    if dry_run.is_running(session):
        raise FixProblem(
            _("The file is still being checked. Create the masters once the check has finished.")
        )
    if session.status not in ("Dry Run Failed", "Ready to Import") or not checked_as_is(session):
        raise FixProblem(
            _(
                "The file or its mapping changed since the last check, or it hasn't been checked. "
                "Check it with dry_run_import first: the masters come from that check."
            )
        )
    plan = {(m["doctype"], m["name"]): m for m in masters_plan(session, list(last_groups(session).values()))}
    listed, named = _listed_tree(documents)
    planned, problems, seen = [], [], set()
    for number, entry in enumerate(documents, start=1):
        try:
            item = _planned_master(session, plan, entry, listed, named)
            _as_sent(entry, item)
        except FixProblem as e:
            problems.append(
                {"document": number, "doctype": entry.get("doctype"), "error": str(e)}
                | ({"exists": True} if isinstance(e, AlreadyThere) else {})
            )
            continue
        key = (item["doctype"], _planned_name(item))
        if key not in seen:
            seen.add(key)
            planned.append(item)
    if problems and len(problems) == len(documents) and all(p.get("exists") for p in problems):
        raise CreatedBefore(len(problems))
    if problems:
        raise FixProblems(problems, _("Nothing was created. Correct these and call again."))
    return parents_first(planned)


def _as_sent(entry: Dict[str, Any], item: Dict[str, Any]) -> None:
    """Raise FixProblem unless ``entry`` was sent as ``item`` is created. The approval card shows
    what was sent, so a parent or a group added here would be created unseen (#34409)."""

    def given(data):
        return {k: cstr(v).strip() for k, v in (data or {}).items() if cstr(v).strip() not in ("", "0")}

    if given(entry.get("data")) != given(item["data"]):
        raise FixProblem(
            _("{0} '{1}' is created as {2}: send it so, so the approval card shows what is created.").format(
                _(item["doctype"]), _planned_name(item), json.dumps(item["data"])
            )
        )


def _listed_tree(documents) -> Tuple[set, set]:
    """Of ``documents``' tree records: the (doctype, name) of each, and of each parent one names."""
    listed, named = set(), set()
    for entry in documents:
        doctype = cstr(entry.get("doctype")).strip()
        if not doctype or not frappe.db.exists("DocType", doctype):
            continue
        meta = frappe.get_meta(doctype)
        name_field, parent_field = _name_field(meta), _parent_field(meta)
        if not parent_field:
            continue
        data = entry.get("data") or {}
        listed.add((doctype, cstr(data.get(name_field)).strip()))
        parent = cstr(data.get(parent_field)).strip()
        if parent:
            named.add((doctype, parent))
    return listed, named


def parents_first(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """``items`` (records to create) with each tree record after the one in the list it goes
    under (#34409), otherwise as given. Raises FixProblem when records go under each other."""
    parent_of = {}
    for item in items:
        parent_field = _parent_field(frappe.get_meta(item["doctype"]))
        parent = item["data"].get(parent_field) if parent_field else None
        parent_of[(item["doctype"], _planned_name(item))] = (item["doctype"], parent) if parent else None

    def depth(key) -> int:
        seen, parent, level = [key], parent_of[key], 0
        while parent in parent_of:
            if parent in seen:
                raise FixProblem(
                    _(
                        "These {0} records go under each other: {1}. Put one under a record outside the list."
                    ).format(_(key[0]), ", ".join(f"'{name}'" for _doctype, name in seen))
                )
            seen.append(parent)
            level += 1
            parent = parent_of[parent]
        return level

    levels = {key: depth(key) for key in parent_of}
    return sorted(items, key=lambda item: levels[(item["doctype"], _planned_name(item))])


def _planned_company_record(session, plan, doctype: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """A COMPANY_NAMED record from masters_plan (a client's department): its name, its company and its
    parent, exactly as planned; ERPNext names it "<name> - <abbr>"."""
    name_field, company_field = COMPANY_NAMED[doctype]
    parent_field = _parent_field(frappe.get_meta(doctype))
    others = sorted(set(data) - {name_field, company_field, parent_field})
    if others:
        raise FixProblem(
            _("A missing {0} takes {1} only (as masters_plan's data has them), not {2}.").format(
                _(doctype),
                ", ".join(f for f in (name_field, company_field, parent_field) if f),
                ", ".join(others),
            )
        )
    value, company = cstr(data.get(name_field)).strip(), cstr(data.get(company_field)).strip()
    abbr = frappe.get_cached_value("Company", company, "abbr") if company else None
    if not abbr:
        raise FixProblem(_("{0} needs a company that exists.").format(_(doctype)))
    name = f"{value} - {abbr}"
    if (doctype, name) not in plan:
        raise FixProblem(
            _("{0} '{1}' isn't one of the masters the last check found missing ({2}).").format(
                _(doctype), value, _planned_list(plan)
            )
        )
    if frappe.db.exists(doctype, name):
        raise AlreadyThere(
            _("{0} '{1}' already exists. Check the file again with dry_run_import.").format(_(doctype), name)
        )
    planned = {name_field: value, company_field: company}
    # the parent is checked as for any master (a group the user may read), and is of no other company
    parent = _parent(doctype, cstr(data.get(parent_field)).strip() if parent_field else "")
    if parent:
        owner = frappe.db.get_value(doctype, parent, company_field)
        if owner and owner != company:
            raise FixProblem(_("'{0}' belongs to another company than {1}.").format(parent, company))
        planned[parent_field] = parent
    return {"doctype": doctype, "data": planned}


def _planned_master(session, plan, entry, listed=frozenset(), named=frozenset()) -> Dict[str, Any]:
    doctype = cstr(entry.get("doctype")).strip()
    if not frappe.db.exists("DocType", doctype):
        raise FixProblem(_("There is no DocType {0}.").format(doctype))
    reason = cannot_create(doctype, session)
    if reason:
        raise FixProblem(
            _("A {0} can't be created here: {1}. Map the rows to an existing one, or leave them out.").format(
                _(doctype), reason
            )
        )
    from frappe_assistant_core.utils import import_opening_invoices as opening_invoices

    if is_party(session, doctype):
        data = {k: cstr(v).strip() for k, v in (entry.get("data") or {}).items() if cstr(v).strip()}
        problem = opening_invoices.party_problem(doctype, data)
        if problem:
            raise FixProblem(problem)
        name = data[opening_invoices.PARTY_NAME_FIELDS[doctype]]
        if (doctype, name) not in plan:
            missing = _planned_list(plan)
            raise FixProblem(
                _("{0} '{1}' isn't one of the masters the last check found missing ({2}).").format(
                    _(doctype), name, missing
                )
            )
        if opening_invoices.find_party(doctype, name):
            raise AlreadyThere(
                _("{0} '{1}' already exists. Check the file again with dry_run_import.").format(
                    _(doctype), name
                )
            )
        return {"doctype": doctype, "data": data}
    if doctype in COMPANY_NAMED:
        return _planned_company_record(session, plan, doctype, entry.get("data") or {})
    meta = frappe.get_meta(doctype)
    name_field, parent_field = _name_field(meta), _parent_field(meta)
    group_field = "is_group" if parent_field and meta.has_field("is_group") else None
    data = entry.get("data") or {}
    others = sorted(set(data) - {name_field, parent_field, group_field})
    if others:
        fields = " and ".join(f for f in (name_field, parent_field) if f)
        raise FixProblem(
            _("A missing {0} takes {1} only (as masters_plan's data has them), not {2}.").format(
                _(doctype), fields, ", ".join(others)
            )
        )
    name = cstr(data.get(name_field)).strip()
    # a parent another record in the list goes under is needed too, though no row names it
    if (doctype, name) not in plan and (doctype, name) not in named:
        missing = _planned_list(plan)
        raise FixProblem(
            _("{0} '{1}' isn't one of the masters the last check found missing ({2}).").format(
                _(doctype), name, missing
            )
        )
    if frappe.db.exists(doctype, name):
        raise AlreadyThere(
            _("{0} '{1}' already exists. Check the file again with dry_run_import.").format(_(doctype), name)
        )
    planned = {name_field: name}
    in_list = {n for d, n in listed if d == doctype}
    parent = _parent(doctype, cstr(data.get(parent_field)).strip() if parent_field else "", in_list)
    if parent:
        planned[parent_field] = parent
    if group_field and (doctype, name) in named:
        planned[group_field] = 1  # it holds the records the list puts under it
    elif group_field and cint(data.get(group_field)):
        raise FixProblem(
            _("{0} '{1}' is created as a group only when another record in the list goes under it.").format(
                _(doctype), name
            )
        )
    return {"doctype": doctype, "data": planned}


def _plan_master(session, group: Dict[str, Any], fix: Dict[str, Any]) -> Dict[str, Any]:
    """The missing master of ``group`` as its migration plan creates it: what masters_plan
    proposes, with the user's parent (or data) instead, checked as create_document checks it."""
    from frappe_assistant_core.utils import import_plan

    doctype = group.get("link_doctype")
    if group.get("cause") != dry_run.CAUSE_MISSING_LINK or not doctype:
        raise FixProblem(_("Only a record the rows link to and that doesn't exist can be created."))
    reason = _creating_problem(doctype, session)
    if reason:
        raise FixProblem(_("A {0} can't be created here: {1}.").format(_(doctype), reason))
    source = (
        import_plan.planned_names(session).get(doctype, {}).get(cstr(group.get("value")).strip().casefold())
    )
    if source:
        raise FixProblem(
            _("{0} '{1}' comes from {2}, so it isn't created again. Check the file again.").format(
                _(doctype), group.get("value"), source
            )
        )
    proposed = masters_plan(session, [group])
    if not proposed:
        raise FixProblem(
            _("A {0} can't be created here: {1}.").format(_(doctype), cannot_create(doctype, session))
        )
    data = {**proposed[0]["data"], **(fix.get("data") or {})}
    parent_field = _parent_field(frappe.get_meta(doctype))
    if fix.get("parent") and parent_field:
        data[parent_field] = fix["parent"]
    known = {(entry["doctype"], entry["name"]): entry for entry in proposed}
    return _planned_master(session, known, {"doctype": doctype, "data": data})


def create_master(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Create one missing master as create_document creates it, refused if ERPNext would name it
    otherwise than the rows have it (kept_its_name)."""
    from frappe_assistant_core.plugins.core.tools.create_document import DocumentCreate

    result = DocumentCreate().execute({"doctype": entry["doctype"], "data": dict(entry["data"])})
    if result.get("success"):
        result = kept_its_name(entry, result)
    return {**result, "doctype": entry["doctype"]}


def _planned_list(plan) -> str:
    """The masters the last check planned, for an error: the first PLANNED_SHOWN, then a count."""
    names = [f"{_(d)} '{n}'" for d, n in plan]
    if not names:
        return _("none")
    listed = ", ".join(names[:PLANNED_SHOWN])
    if len(names) > PLANNED_SHOWN:
        listed = _("{0} and {1} more").format(listed, len(names) - PLANNED_SHOWN)
    return listed


def _planned_name(entry: Dict[str, Any]) -> str:
    from frappe_assistant_core.utils import import_opening_invoices as opening_invoices

    if entry["doctype"] in COMPANY_NAMED:
        name_field, company_field = COMPANY_NAMED[entry["doctype"]]
        abbr = frappe.get_cached_value("Company", entry["data"].get(company_field), "abbr")
        return f"{entry['data'][name_field]} - {abbr}"
    field = _name_field(frappe.get_meta(entry["doctype"])) or opening_invoices.PARTY_NAME_FIELDS.get(
        entry["doctype"]
    )
    return entry["data"][field]


def kept_its_name(entry: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """create_document's result for a missing master, refused if ERPNext named the record
    otherwise: the rows link to the name the file uses."""
    from frappe_assistant_core.utils import import_opening_invoices as opening_invoices

    doctype = entry["doctype"]
    if not _name_field(frappe.get_meta(doctype)) and doctype in opening_invoices.PARTY_NAME_FIELDS:
        # A party is found by its customer or supplier name, whatever name ERPNext gave it.
        found = opening_invoices.find_party(doctype, _planned_name(entry))
        by_name = dry_run._name_field(doctype) == opening_invoices.PARTY_NAME_FIELDS[doctype]
        if result.get("success") and (
            not (found and found.name == result.get("name"))
            or (by_name and result.get("name") != _planned_name(entry))  # rows link by the name
        ):
            return {
                "success": False,
                "error": _("ERPNext named it '{0}', and the rows wouldn't find it by '{1}'").format(
                    result.get("name"), _planned_name(entry)
                ),
            }
        return result
    if result.get("name") != _planned_name(entry):
        return {
            "success": False,
            "error": _("ERPNext would name it '{0}', not '{1}' as the file has it").format(
                result.get("name"), _planned_name(entry)
            ),
        }
    return result


def link_created(session, results: List[Dict[str, Any]]) -> None:
    """List the masters create_document made on the session (Created Records), and log the step. Runs inside create_document's batch, so a failure here
    undoes the records too."""
    for result in results:
        parent_field = _parent_field(frappe.get_meta(result["doctype"]))
        session.append(
            "created_records",
            {
                "record_doctype": result["doctype"],
                "record_name": result["name"],
                "parent_record": frappe.db.get_value(result["doctype"], result["name"], parent_field)
                if parent_field
                else None,
            },
        )
    # A lookup earlier in this request (a dry run in the same workflow) may have cached these
    # records as missing; a commit would clear that cache, and nothing has committed.
    frappe.db.value_cache.clear()
    session.log_step(
        "Create Masters",
        "Success",
        _("Created {0}.").format(", ".join(f"{_(r['doctype'])} '{r['name']}'" for r in results)),
    )
    session.save()


def _parent(doctype: str, parent: str, in_list=frozenset()) -> Optional[str]:
    """The parent the record goes under: one the user chose, or the tree's root. A parent
    ``in_list`` (created in the same call) is created first, as a group."""
    if not frappe.get_meta(doctype).is_tree:
        if parent:
            raise FixProblem(_("A {0} has no parent.").format(_(doctype)))
        return None
    parent = parent or default_parent(doctype)
    if not parent or parent in in_list:
        return parent or None
    if not _holds_records(doctype, parent) or not frappe.has_permission(doctype, "read", doc=parent):
        filters = {"is_group": 1} if frappe.get_meta(doctype).has_field("is_group") else {}
        groups = frappe.get_list(doctype, filters=filters, pluck="name", limit_page_length=FULL_SCAN)
        message = _("'{0}' isn't a {1} that can hold others.").format(parent, _(doctype))
        if groups:
            message += " " + _("Groups: {0}.").format(
                ", ".join(rank(parent, groups) or groups[:CLOSEST_LIMIT])
            )
        else:
            message += " " + _("This tree has no groups: leave the parent out.")
        raise FixProblem(message)
    return parent


# -- the reply ------------------------------------------------------------------------


def check(session_name: str, commit_progress: bool = False, in_background: bool = False) -> Dict[str, Any]:
    """The dry run, explained. The reply is also kept in validation_summary, so a check run
    in the background reads the same as one that came back at once. The session keeps no row
    of the file, so it keeps the example rows' numbers, not their values. ``in_background``:
    the caller is a background job, so a large file is checked here (see dry_run.run)."""
    summary = dry_run.run(session_name, commit_progress=commit_progress, in_background=in_background)
    session = frappe.get_doc(dry_run.SESSION_DOCTYPE, session_name)
    reply = report(session, summary)
    # What this check was of (file, mapping, fixes): the import's approval names it (#34402).
    reply["validated_fingerprint"] = dry_run.check_id(session.validated_fingerprint)
    kept = [
        {
            **{k: v for k, v in group.items() if k != "examples"},
            "example_rows": [e["row"] for e in group["examples"]],
        }
        for group in reply["groups"]
    ]
    session.db_set("validation_summary", frappe.as_json({**reply, "groups": kept}), update_modified=False)
    return reply


def checked_as_is(session) -> bool:
    """Whether the last check was of the session as it is now: same file, mapping and fixes."""
    if not session.source_file or not session.validated_fingerprint:
        return False
    file_doc = readable_session_file(session)
    return dry_run.fingerprint(session, file_doc) == session.validated_fingerprint


def fixed_unchecked(session) -> bool:
    """Whether the session is as its last fixes left it, and no check of it finished: the check
    after them failed (a lost connection, a worker restart), so the fixes stay applied (#34607)."""
    fixed = (frappe.parse_json(session.template_options or "{}") or {}).get(dry_run.UNCHECKED_FIXES)
    if not fixed or not session.source_file or fixed == session.validated_fingerprint:
        return False
    return dry_run.fingerprint(session, readable_session_file(session)) == fixed


def last_groups(session) -> Dict[str, Dict[str, Any]]:
    """The last dry run's groups by id, each with all its rows, from the result file."""
    file_doc = dry_run._results_file(session)
    if not file_doc:
        return {}
    content = frappe.parse_json(file_doc.get_content()) or {}
    return {group["id"]: group for group in content.get("groups") or []}


def ready_message(summary: Dict[str, Any]) -> str:
    """What FACO says once nothing fails: the file is ready, with the final count."""
    update = summary.get("update")
    if update is not None:  # an update (#34005): records that change, and rows that wouldn't
        if not summary["ready"]:
            # start_import closes it (#34436): left Ready to Import, the sign-off lists it as open
            return _(
                "Nothing to update: every matched record already has the file's values. "
                "start_import closes the session as Completed, sending nothing."
            )
        text = _("The file is ready: {0} will be updated ({1}).").format(
            _("1 record") if summary["ready"] == 1 else _("{0} records").format(summary["ready"]),
            _("1 field change")
            if update["fields_changing"] == 1
            else _("{0} field changes").format(update["fields_changing"]),
        )
        if summary.get("unchanged"):
            text += " " + (
                _("1 row already has these values and is skipped.")
                if summary["unchanged"] == 1
                else _("{0} rows already have these values and are skipped.").format(summary["unchanged"])
            )
        if summary.get("excluded"):
            text += " " + _("{0} left out; the import report will list them.").format(
                _rows(summary["excluded"])
            )
        return text
    if summary.get("imported") and not summary["ready"]:
        text = _("Nothing is left to import: {0} already imported").format(_rows(summary["imported"]))
        if summary.get("excluded"):
            text += _(", {0} left out").format(_rows(summary["excluded"]))
        return text + "."
    text = _("The file is ready: {0} will be imported.").format(_rows(summary["ready"]))
    if summary.get("imported"):
        text += " " + _("{0} already imported are skipped.").format(_rows(summary["imported"]))
    if summary.get("excluded"):
        text += " " + _("{0} left out; the import report will list them.").format(_rows(summary["excluded"]))
    return text


def decisions(session, groups: List[Dict[str, Any]], masters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Every failure of the check as the questions to ask, all at once: one per field and cause,
    each with its values (up to DECISION_VALUES), the rows of each, and a suggested answer. The
    groups shown are the first GROUPS_SHOWN only; live, 2026-11-17, a status value among 276 groups
    came up four rounds after the others. Fixes reach every group, shown or not."""
    planned = {(m["doctype"], m.get("value", m["name"])) for m in masters}
    out: Dict[Tuple[Any, Any, Any], Dict[str, Any]] = {}
    for group in groups:
        key = (group.get("cause"), group.get("parent"), group.get("field"))
        decision = out.setdefault(
            key,
            {
                "cause": group.get("cause"),
                "field": group.get("field"),
                "label": group.get("label") or group.get("field"),
                **({"parent": group["parent"]} if group.get("parent") else {}),
                "rows": 0,
                "values_total": 0,
                "values": [],
            },
        )
        decision["rows"] += group.get("count") or 0
        decision["values_total"] += 1
        if len(decision["values"]) >= DECISION_VALUES:
            continue
        entry = {"group": group["id"], "value": group.get("value"), "rows": group.get("count") or 0}
        suggested = _suggested(session, group, planned)
        if suggested:
            entry["suggested"] = suggested
        decision["values"].append(entry)
    for decision in out.values():
        answers = {cstr((v.get("suggested") or {}).get("action")) for v in decision["values"]}
        if decision["values_total"] == len(decision["values"]) and len(answers) == 1 and "" not in answers:
            decision["suggested_for_all"] = decision["values"][0]["suggested"]["action"]
        elif answers == {CREATE} and decision["values_total"] > len(decision["values"]):
            decision["suggested_for_all"] = CREATE  # every planned master: planned_masters
    return list(out.values())


def _suggested(session, group: Dict[str, Any], planned) -> Optional[Dict[str, Any]]:
    """The answer to suggest for one group: create a planned master, map to the likely name or
    choice, leave out the later rows of a repeated name; None when only the user can say."""
    target = _with_target(session, group)
    if target.get("link_doctype") in COMPANY_NAMED:
        # the client's own departments: map only a clear match (HR → Human Resources), else create it
        likely = (
            ({f.get("action"): f for f in advise(session, group).get("fixes") or []}).get(MAP) or {}
        ).get("likely")
        if likely:
            return {"action": MAP, "to": likely}
    if (target.get("link_doctype"), group.get("value")) in planned:
        return {"action": CREATE}
    if group.get("cause") == dry_run.CAUSE_DUPLICATE_IN_FILE:
        # live, 2026-11-19: 322 sub-projects named like their main project were only offered "leave out"
        return {"action": MAKE_UNIQUE}
    fixes = {fix.get("action"): fix for fix in advise(session, group).get("fixes") or []}
    likely = (fixes.get(MAP) or {}).get("likely")
    if likely:
        return {"action": MAP, "to": likely}
    return None


def report(session, summary: Dict[str, Any]) -> Dict[str, Any]:
    """The dry run's reply to the model: the headline, then each group with its examples,
    a plain explanation and the fixes that fit, and the ready message once nothing fails."""
    # A summary at any file size: 5,000 different wrong values would otherwise be 5,000 groups
    # in the reply. Fixes find every group in the results file, shown or not.
    shown_groups = summary["groups"][:GROUPS_SHOWN]
    examples = dry_run.examples(session, shown_groups)
    groups = []
    for group in shown_groups:
        shown = {k: v for k, v in group.items() if k != "example_rows"}
        shown["examples"] = examples.get(group["id"], [])
        shown.update(advise(session, group))
        groups.append(shown)

    message = dry_run.headline(summary) + " " + _("Nothing was written.")
    hidden = len(summary["groups"]) - len(shown_groups)
    if hidden:
        # decisions covers every group, shown or not: "the next ones show" had the assistant ask round
        # by round (live, 2026-11-18)
        message += " " + _(
            "{0} more kinds of failure aren't listed here, but decisions covers every one: ask the user "
            "all of them at once and send every answer in one call."
        ).format(hidden)
    if not summary["failed"]:
        message += " " + ready_message(summary)
    masters = masters_plan(session, summary["groups"])
    out = {
        "session": session.name,
        "status": session.status,
        "message": message,
        **{k: v for k, v in summary.items() if k != "groups"},
        "groups": groups,
        "groups_total": len(summary["groups"]),
        "masters_plan": masters[:MASTERS_SHOWN],
    }
    if hidden:
        out["groups_not_shown"] = hidden
    if summary["groups"]:
        out["decisions"] = decisions(session, summary["groups"], masters)
    choices = card(session, summary, masters)
    if choices:
        out["card"] = choices
        out["next"] = _(CARD_HOW)  # outside the card: the card quotes the file and is fenced
        if len(json.dumps(out, default=str)) > REPLY_BUDGET:
            # live, 2026-11-19: replies set aside by FAC Cloud (130,000, then 20,000 characters): FACO read parts,
            # missed the card and typed the questions. The card carries every fix: the lists go, counts stay.
            out["groups"] = out["groups"][:GROUPS_DETAILED]
            out.pop("decisions", None)
            # live, 2026-11-20: an empty masters_plan was read as nothing to create, and the chat stopped
            out.pop("masters_plan", None)
            out["masters_plan_total"] = len(masters)
            if masters:
                out["masters_plan_left_out"] = _(
                    "{0} records to create, left out to keep this short: create them with the card's create "
                    "option (create_document with import_session and planned_masters {{count: {0}}})."
                ).format(len(masters))
            out["message"] += " " + _(
                "The details are left out to keep this short: card has every choice, with what to send."
            )
        # the instruction and the card first, so a reply cut or set aside still starts with them
        out = {"next": out.pop("next"), "card": out.pop("card"), **out}
    if len(masters) > MASTERS_SHOWN:
        out["masters_plan_total"] = len(masters)
    if summary.get("excluded"):
        out["left_out"] = left_out_report(session)
    return out


# -- the one card: every choice of a check, in plain words -----------------------------------------
# Live, 2026-11-19 (2,084 projects): six questions one after another, "exclude rows with missing departments"
# left 1 row of 2,084, repeated names could only be left out, and the user was asked to type department
# names. The card puts every choice of the check on one card, each option saying what it does, the
# recommended one first, with the fixes (and the records to create first) FACO sends when it is picked.

CARD_LISTED = 6  # values named in an option's label

#: How FACO uses the card, in the reply it always reads (live, 2026-11-19: it asked one question of eight,
#: confirmed three times, printed the mapping table twice and ran 15 calls without a word to the user).
CARD_HOW = (
    "Show this card now: one ask_user call per question (single_select, its recommended option "
    "pre-selected, its title and result as the description), ALL in the same response as parallel tool "
    "calls: the chat shows them together as one card. Never one ask_user holding several questions. Don't decide, summarise or leave out any question, "
    "don't add your own (the company again, one question summing up the others, a final 'Proceed?': the "
    "card's answers are the go-ahead), and don't print the mapping table. When the user answers, don't ask again: tell them in one line what "
    "you'll do, then do it in this order, with a short line after each step: 1) the columns option's calls: "
    "one create_document call per field (never a list: records and documents refuse a Custom Field), ALL in "
    "ONE response as parallel tool calls, never one after another's approval: the chat then shows them on one "
    "card ('N changes go live') approved once. Then set_column_mapping for those columns and, after its reply, "
    "dry_run_import with every chosen option's fixes (the records to create come from a check of the current mapping); 2) "
    "records to create in one create_document call with import_session (create_all's planned_masters with the "
    "chosen shared values, or the chosen options' create as documents); 3) dry_run_import (with the chosen "
    "fixes if step 1 didn't send them; fixes once saved needn't be sent again); 4) if it is ready, "
    "start_import. An option with "
    "fix_in_file: tell the user what to correct and stop."
)
CARD_CREATE_LISTED = 10  # records an option lists to create; more are created by planned_masters, by count
GROUPS_DETAILED = 5  # groups a big reply still shows with their example rows
REPLY_BUDGET = 12000  # a check's reply above it keeps the card and counts, not every group's detail
CARD_LIKELY = 50  # groups of a question looked up for a clear match


def _plural(doctype: str, count: int) -> str:
    return _(doctype) if count == 1 else _("{0} records").format(_(doctype))


def card(session, summary: Dict[str, Any], masters: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The check's choices for ONE card: ``title``, ``intro``, ``questions`` (each ``title``, ``detail`` and
    ``options``: ``label``, ``effect``, ``recommended``, and what to send, ``fixes`` for dry_run_import and
    ``create`` records for create_document first), and ``result``: how many rows the recommended answers
    import. None when there is nothing to ask."""
    total = summary.get("total_rows") or summary.get("records") or 0
    questions: List[Dict[str, Any]] = []
    target = session.target_doctype
    if session.import_type == "Update Existing Records" and not frappe.db.count(target):
        questions.append(
            {
                "id": "import_type",
                "title": _("There are no {0} records yet").format(_(target)),
                "detail": _("Updating would change nothing: every row would find no record to update."),
                "options": [
                    {
                        "label": _("Import them as new records"),
                        "effect": _("All {0} rows are created.").format(total),
                        "recommended": True,
                        "then": _(
                            "set_column_mapping again with the same mapping and import_type 'Insert New Records', then dry_run_import"
                        ),
                    },
                    {
                        "label": _("Keep updating"),
                        "effect": _("Nothing would be imported."),
                        "recommended": False,
                    },
                ],
            }
        )
    by_key: Dict[Tuple[Any, Any, Any], List[Dict[str, Any]]] = {}
    for group in summary.get("groups") or []:
        by_key.setdefault((group.get("cause"), group.get("parent"), group.get("field")), []).append(group)
    planned = {(m["doctype"], m.get("value", m["name"])): m for m in masters}
    for (cause, _parent, field), groups in by_key.items():
        rows = sum(g.get("count") or 0 for g in groups)
        label = _(groups[0].get("label") or field or "")
        skip = {
            "label": _("Ignore these for now: skip the {0} rows").format(rows),
            "effect": _("These rows aren't imported; the import report lists them."),
            "fixes": _compact([{"group": g["id"], "action": LEAVE_OUT} for g in groups]),
        }
        if cause == dry_run.CAUSE_DUPLICATE_IN_FILE:
            questions.append(_duplicate_question(session, groups, label, rows, skip))
        elif cause == dry_run.CAUSE_MISSING_LINK:
            questions.append(_missing_question(session, groups, label, rows, planned, skip))
        elif cause == dry_run.CAUSE_BAD_OPTION:
            questions.append(_option_question(session, groups, label, rows, skip))
        else:
            first = advise(session, groups[0])
            questions.append(
                {
                    "id": f"{cause}:{field}",
                    "title": _("{0} rows: {1}").format(rows, label or _(cause)),
                    "detail": first.get("explanation"),
                    "options": [
                        {
                            "label": _("I'll correct the file and upload it again"),
                            "effect": _("Nothing is imported until then."),
                            "fix_in_file": True,
                        },
                        skip,
                    ],
                }
            )
    unplaced = _columns_question(session)
    if unplaced:
        questions.append(unplaced)
    choose = _shared_question(masters)
    if choose:
        questions.append(choose)
    if not questions:
        return None
    for question in questions:
        if not any(o.get("recommended") for o in question["options"]):
            question["options"][0]["recommended"] = question["options"][0].get("fix_in_file") is not True
    lost = sum(o.get("rows_lost", 0) for q in questions for o in q["options"] if o.get("recommended"))
    company = import_company(session)
    return {
        "title": (
            _("Import {0} {1} into {2}").format(total, _plural(target, total), company)
            if company and frappe.get_meta(target).has_field("company")
            else _("Import {0} {1}").format(total, _plural(target, total))
        ),
        "intro": _("I checked the file. These need your choice; the recommended answer is selected."),
        "questions": questions,
        **(
            {"create_all": {"planned_masters": {"count": len(masters)}}}
            if any(o.get("create_planned") for q in questions for o in q["options"])
            else {}
        ),
        "result": _("With the recommended answers, up to {0} of {1} rows are imported.").format(
            max(total - lost, 0), total
        ),
    }


def _duplicate_question(session, groups, label, rows, skip) -> Dict[str, Any]:
    from frappe_assistant_core.utils.import_dry_run import read_sheet_rows

    example, heading = "", ""
    try:
        first = (groups[0].get("rows") or groups[0].get("example_rows") or [])[:1]
        sample = _unique_names(session, {**_with_target(session, groups[0]), "rows": first}, {}, {})
        example = next(iter(sample.values()))["value"] if sample else ""
        file_rows = apply_value_maps(
            session, read_sheet_rows(readable_session_file(session), session.sheet or None)
        )
        at = id_column(session, file_rows)
        heading = cstr(file_rows[0][at]) if at is not None else ""
    except Exception:
        pass
    options = []
    if heading:
        options.append(
            {
                "label": _("Give them different names: add the {0}").format(heading),
                "effect": _("All {0} rows are kept, e.g. '{1}'.").format(rows, example),
                "recommended": True,
                "fixes": [{"group": g["id"], "action": MAKE_UNIQUE, "add": "id"} for g in groups],
            }
        )
    options.append(
        {
            "label": _("Give them different names: add a number"),
            "effect": _("All {0} rows are kept, e.g. '… (2)'.").format(rows),
            "recommended": not heading,
            "fixes": [{"group": g["id"], "action": MAKE_UNIQUE, "add": "number"} for g in groups],
        }
    )
    options.append(
        {
            "label": _("I'll rename them in the file and upload it again"),
            "effect": _("Nothing is imported until then."),
            "fix_in_file": True,
        }
    )
    options.append({**skip, "rows_lost": rows})
    return {
        "id": f"duplicate:{groups[0].get('field')}",
        "title": _("{0} rows repeat a {1} used earlier in the file").format(rows, label),
        "detail": _("ERPNext allows each {0} only once, so these can't come in as they are.").format(label),
        "options": options,
    }


def _missing_question(session, groups, label, rows, planned, skip) -> Dict[str, Any]:
    doctype = _with_target(session, groups[0]).get("link_doctype") or label
    create, maps, unplaced = [], [], 0
    groups_left = groups
    if doctype == "Company":
        # the company the user is importing into, never the closest-sounding one (live: samb → Sambhav Demo)
        company = import_company(session)
        if company:
            maps, groups_left = [(g, company) for g in groups], []
    for index, group in enumerate(groups_left):
        plan = planned.get((doctype, group.get("value")))
        clear = None
        if index < CARD_LIKELY:
            fix = {f.get("action"): f for f in advise(session, group).get("fixes") or []}.get(MAP) or {}
            clear = fix.get("likely")
        if clear and (doctype in COMPANY_NAMED or not plan):
            maps.append((group, clear))
        elif plan:
            create.append(plan)
        else:
            unplaced += group.get("count") or 0
    values = [cstr(g.get("value")) for g in groups]
    options = []
    if create or maps:
        parts = []
        if create:
            parts.append(
                _("Create {0} new {1}: {2}").format(
                    len(create),
                    _plural(doctype, len(create)),
                    ", ".join(c["value"] if "value" in c else c["name"] for c in create[:CARD_LISTED])
                    + ("…" if len(create) > CARD_LISTED else ""),
                )
            )
        if maps:
            parts.append(
                _("use {0}").format(
                    ", ".join(f"{_short(to)} for {g.get('value')}" for g, to in maps[:CARD_LISTED])
                )
            )
        option = {
            "label": "; ".join(parts),
            "effect": _("Every row is kept.")
            if not unplaced
            else _("{0} rows still need another answer.").format(unplaced),
            "recommended": True,
            "fixes": [{"group": g["id"], "action": MAP, "to": to} for g, to in maps],
            "rows_lost": unplaced,
        }
        if len(create) > CARD_CREATE_LISTED:
            # too many to list: planned_masters creates every planned record, by count (card.create_all)
            option["create_planned"] = {"doctype": doctype, "count": len(create)}
        elif create:
            option["create"] = [{"doctype": c["doctype"], "data": c["data"]} for c in create]
        options.append(option)
    drop = _drop_fix(session, groups[0])
    if drop:
        options.append(
            {
                "label": _("Leave {0} empty").format(label),
                "effect": _("Every row is kept, with no {0}.").format(label),
                "recommended": not options,
                "fixes": [{"group": groups[0]["id"], "action": DROP_COLUMN}],
            }
        )
    options.append(
        {
            "label": _("I'll correct them in the file and upload it again"),
            "effect": _("Nothing is imported until then."),
            "fix_in_file": True,
        }
    )
    options.append({**skip, "rows_lost": rows})
    return {
        "id": f"missing:{groups[0].get('field')}",
        "title": _("{0} {1} in the file don't exist in ERPNext yet").format(len(groups), label),
        "detail": _("Values: {0}.").format(
            ", ".join(values[:CARD_LISTED]) + ("…" if len(values) > CARD_LISTED else "")
        ),
        "options": options,
    }


def _short(name: str) -> str:
    """A company record's name without the company's abbreviation, for the user: "Human Resources"."""
    return re.sub(r" - [A-Za-z0-9&.]{1,10}$", "", cstr(name))


def _option_question(session, groups, label, rows, skip) -> Dict[str, Any]:
    maps, unknown = [], []
    for group in groups:
        fix = {f.get("action"): f for f in advise(session, group).get("fixes") or []}.get(MAP) or {}
        to = fix.get("likely") or next(iter(fix.get("closest") or []), None)
        (maps if to else unknown).append((group, to))
    options = []
    if maps:
        options.append(
            {
                "label": _("Use ERPNext's: {0}").format(
                    ", ".join(f"{g.get('value')} → {to}" for g, to in maps[:CARD_LISTED])
                ),
                "effect": _("Every row is kept."),
                "recommended": True,
                "fixes": [{"group": g["id"], "action": MAP, "to": to} for g, to in maps],
            }
        )
    drop = _drop_fix(session, groups[0])
    if drop:
        options.append(
            {
                "label": _("Leave {0} empty").format(label),
                "effect": _("Every row is kept, with no {0}.").format(label),
                "fixes": [{"group": groups[0]["id"], "action": DROP_COLUMN}],
            }
        )
    options.append({**skip, "rows_lost": rows})
    return {
        "id": f"option:{groups[0].get('field')}",
        "title": _("{0} values in the file aren't ERPNext's choices for {1}").format(len(groups), label),
        "detail": _("{0} rows.").format(rows),
        "options": options,
    }


def _columns_question(session) -> Optional[Dict[str, Any]]:
    """The file's columns with values that go nowhere (unmapped or Don't Import): create a text field for each
    on the DocType, or leave them out. Not a column of old IDs, nor one that repeats another column. Live,
    2026-11-19: 17 columns of a client's projects were offered "put in Notes"."""
    from frappe_assistant_core.utils.import_dry_run import read_sheet_rows

    try:
        rows = apply_value_maps(
            session, read_sheet_rows(readable_session_file(session), session.sheet or None)
        )
    except Exception:
        return None
    if not rows:
        return None
    mapped = _column_targets(session)
    key = import_keys.source_key(session)
    skip = {int(key["position"])} if key else set()
    ids = id_column(session, rows)
    if ids is not None:
        skip.add(ids)  # the file's own IDs: the record's ID, not a field (set-column-mapping-usage)
    columns = {p: [cstr(r[p]).strip() if p < len(r) else "" for r in rows[1:]] for p in range(len(rows[0]))}
    meta = frappe.get_meta(session.target_doctype)
    labels = {cstr(df.label).strip().casefold() for df in meta.fields}
    left = []
    for position, values in columns.items():
        heading = cstr(rows[0][position]).strip()
        if position in mapped or position in skip or not heading or not any(values):
            continue
        if any(
            values == other for p, other in columns.items() if p != position and (p in mapped or p < position)
        ):
            continue  # a copy of another column
        if heading.casefold() in labels:
            continue  # the DocType has a field of that name: a mapping question, not a new field
        left.append(heading)
    if not left:
        return None
    doctype = session.target_doctype
    return {
        "id": "columns",
        "title": _("{0} columns of the file have no field on {1}").format(len(left), _(doctype)),
        "detail": ", ".join(left[:12]) + ("…" if len(left) > 12 else ""),
        "options": [
            {
                "label": _("Create a text field on {0} for each, and import them").format(_(doctype)),
                "effect": _("{0} new fields on the {1} form; their values come in.").format(
                    len(left), _(doctype)
                ),
                "recommended": True,
                "calls": [
                    {
                        "tool": "create_document",
                        "arguments": {
                            "doctype": "Custom Field",
                            "data": {"dt": doctype, "label": heading, "fieldtype": "Data"},
                        },
                    }
                    for heading in left
                ],
                "then": _(
                    "make each of calls as its own create_document call (live: a list of them was refused), all "
                    "sent together in one message so the user approves them on one card; then map every column to "
                    "its new field with set_column_mapping"
                ),
            },
            {
                "label": _("Don't import these columns"),
                "effect": _("Their values stay only in the file."),
            },
        ],
    }


#: The group a new party that is a company most likely belongs to, when no existing party says otherwise
BUSINESS_GROUPS = {"customer_group": ("Commercial",)}


def _likeliest_first(doctype: str, field: str, values: List[str]) -> List[str]:
    """``values`` with the one the site's own records use most first, then the usual one for a business (a
    customer group of Commercial), then as listed. Live, 2026-11-20: 262 CSR clients were offered
    "Government" as recommended, only because it was listed first."""
    used = {v: frappe.db.count(doctype, {field: v}) for v in values}
    usual = {_(v) for v in BUSINESS_GROUPS.get(field, ())} | set(BUSINESS_GROUPS.get(field, ()))
    return sorted(values, key=lambda v: (-used[v], v not in usual, values.index(v)))


def _shared_question(masters: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """For new customers or suppliers the site has no default group or territory for: which one, once for
    all of them (masters_plan's ``choose``), as one question of the card."""
    wanted: Dict[Tuple[str, str], List[str]] = {}
    for entry in masters:
        for field, values in (entry.get("choose") or {}).items():
            if values:
                wanted.setdefault((entry["doctype"], field), list(values))
    if not wanted:
        return None
    (doctype, field), values = next(iter(wanted.items()))
    values = _likeliest_first(doctype, field, values)
    count = sum(1 for m in masters if m["doctype"] == doctype)
    label = _(frappe.get_meta(doctype).get_label(field))
    return {
        "id": f"shared:{doctype}:{field}",
        "title": _("{0} for the {1} new {2}").format(label, count, _plural(doctype, count)),
        "detail": _("The site has no default {0}: one is given to all of them.").format(label),
        "options": [
            {
                "label": value,
                "effect": _("All {0} get {1}.").format(count, value),
                "recommended": i == 0,
                "shared": {doctype: {field: value}},
            }
            for i, value in enumerate(values[:CARD_LISTED])
        ],
    }


def _expanded(fixes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Fixes as the card sends them for many groups at once, ``{"groups": [ids], "action": ...}``, one per
    group: 262 groups' "leave out" written one by one made the card too long to show (live, 2026-11-19)."""
    out = []
    for fix in fixes or []:
        if isinstance(fix, dict) and isinstance(fix.get("groups"), list) and not fix.get("group"):
            rest = {k: v for k, v in fix.items() if k != "groups"}
            out.extend({**rest, "group": group} for group in fix["groups"])
        else:
            out.append(fix)
    return out


def _compact(fixes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The same fix for many groups as one entry with their ids (_expanded reads it back)."""
    if len(fixes) <= 3 or any(set(f) - {"group", "action"} for f in fixes):
        return fixes
    actions = {f["action"] for f in fixes}
    if len(actions) != 1:
        return fixes
    return [{"action": actions.pop(), "groups": [f["group"] for f in fixes]}]
