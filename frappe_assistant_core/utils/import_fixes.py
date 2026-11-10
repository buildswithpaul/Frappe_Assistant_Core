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
ACTIONS = (
    MAP,
    LEAVE_OUT,
    ALLOW_ZERO_RATE,
    POST_AT_CUTOFF,
    CREATE,
    FILL,
)  # applied by dry_run_import; create only in a migration plan, else create_document does it

CLOSEST_LIMIT = 5
MIN_SCORE = 0.6  # below it a name only shares letters: "Kerala" isn't a misspelt "Karnataka" (0.53)
LIKELY_SPELLING = 0.8  # a closest name spelt this alike, and LIKELY_LEAD ahead of the next, is the one meant
LIKELY_LEAD = 0.1
FULL_SCAN = 2000  # rank every record when a DocType has at most this many
WORD_MATCHES = 200  # else only records sharing a word with the value, this many per word
GROUPS_SHOWN = 30  # the dry run's reply lists this many groups; the results file keeps them all
MASTERS_SHOWN = 50  # and this many missing masters to create
PLANNED_SHOWN = 10  # planned masters named in an error about one that was not planned

#: Masters simple enough to create that are still never created during an import. Sites add
#: more with the ``fac_import_never_create_doctypes`` site config key (a list of DocTypes).
NEVER_CREATE = {
    "Company": "creating one also creates a chart of accounts, warehouses and taxes",
}


class FixProblem(Exception):
    """A fix that can't be applied. The message is shown to the user."""


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
    maps = value_maps(session)
    if not maps or not rows:
        return rows
    by_column: Dict[int, Dict[str, str]] = {}
    for position, target in _column_targets(session).items():
        for rule in maps:
            if target == (rule.get("parent"), rule.get("field")):
                by_column.setdefault(position, {})[cstr(rule.get("from")).strip()] = cstr(rule.get("to"))
    if not by_column:
        return rows
    out = [rows[0]]
    for row in rows[1:]:
        row = list(row)
        for position, replace in by_column.items():
            if position < len(row) and cstr(row[position]).strip() in replace:
                row[position] = replace[cstr(row[position]).strip()]
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
        found = re.search(r"Value missing for (.+?): (.+)$", cstr(group.get("message")).strip())
        if found and found.group(1).strip() in (session.target_doctype, _(session.target_doctype)):
            label = found.group(2).strip()
            fields = [field for field in meta.fields if field.reqd and label in (field.label, _(field.label))]
            df = fields[0] if len(fields) == 1 else None
    # One value for every record can't be what names or titles each, nor one no two records share
    if not df or df.unique or df.fieldname in (dry_run._name_field(session.target_doctype), meta.title_field):
        return None
    return df


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


def word_for(doctype: str, value: str) -> Optional[str]:
    """The record a file's word for it means (Rs: INR, Mtr: Meter), when it is switched on."""
    meant = (WORDS.get(doctype) or {}).get(cstr(value).strip().casefold())
    if meant and frappe.db.exists(doctype, {"name": meant, **_switched_on(frappe.get_meta(doctype))}):
        return meant
    return None


def closest_names(doctype: str, value: str, limit: int = CLOSEST_LIMIT) -> List[str]:
    """Existing names of ``doctype`` closest to ``value``, best first, that the user can read.

    A record is matched on its name, title and search fields (#34407): a master named by a series
    (CUST-00012) is found by "Acme Ltd". Disabled records and the group nodes of a tree are left
    out: a link to them fails.
    """
    if not frappe.has_permission(doctype, "read"):
        return []
    meta = frappe.get_meta(doctype)
    filters = _switched_on(meta)
    if meta.is_tree and meta.has_field("is_group"):
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


def _closest(session, doctype: str, value: str) -> List[str]:
    """closest_names, and the records the plan's earlier files create that come close: a value
    misspelling one of those is mapped to it, not created as a record of its own."""
    closest = closest_names(doctype, value)
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
                "or give the items their code first."
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
        closest = _closest(session, doctype, value)
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
        return {"explanation": explanation, "fixes": [{"action": MAP, "closest": closest}, leave_out]}

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
    blank = _fill_field(session, group)
    if blank:
        # One value for every row: the HSN code of a file of items, say (#34415)
        fixes.insert(0, {"action": FILL, "field": blank.fieldname, "label": _(blank.label)})
    # Anything else is corrected in the file, which is then checked again.
    return {"explanation": explanation, "fixes": fixes, "fix_in_file": True}


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


def apply_fixes(session, groups: Dict[str, Dict[str, Any]], fixes: List[Dict[str, Any]]) -> List[str]:
    """Check every fix, then store them all on the session, or none if any is wrong.

    ``groups`` are the last dry run's groups by id, with all their rows. Returns one plain
    sentence per fix applied. The caller saves the session and checks it again.
    """
    from frappe_assistant_core.utils import import_opening_balances as opening_balances

    maps = value_maps(session)
    filled = fills(session)
    reasons = {str(entry["row"]): entry["reason"] for entry in left_out(session)}
    zero_rate = list(_rules(session).get("zero_rate_items") or [])
    post_at_cutoff = bool(_rules(session).get("post_at_cutoff"))
    done, problems, planned = [], [], []
    for fix in fixes:
        group = groups.get(cstr(fix.get("group")))
        try:
            if not group:
                raise FixProblem(
                    _("There is no group {0} in the last check. Groups: {1}.").format(
                        fix.get("group"), ", ".join(groups)
                    )
                )
            group = _with_target(session, group)
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
                reason = cstr(fix.get("reason")).strip() or group.get("message") or group["cause"]
                for row in group["rows"]:
                    reasons.setdefault(str(row), reason)
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
            elif action == CREATE:
                if not session.get("migration_plan"):
                    raise FixProblem(
                        _(
                            "Create missing records with create_document (documents from masters_plan, "
                            "with import_session), then call dry_run_import again without fixes. "
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
        "zero_rate_items": zero_rate,
        "post_at_cutoff": post_at_cutoff,
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
    from frappe_assistant_core.utils import import_opening_invoices as opening_invoices

    if opening_invoices.is_party(session, doctype):
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
        if opening_invoices.is_party(session, doctype):
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
                "name": group["value"],
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
            problems.append({"document": number, "doctype": entry.get("doctype"), "error": str(e)})
            continue
        key = (item["doctype"], _planned_name(item))
        if key not in seen:
            seen.add(key)
            planned.append(item)
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

    if opening_invoices.is_party(session, doctype):
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
            raise FixProblem(
                _("{0} '{1}' already exists. Check the file again with dry_run_import.").format(
                    _(doctype), name
                )
            )
        return {"doctype": doctype, "data": data}
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
        raise FixProblem(
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
        if result.get("success") and not (found and found.name == result.get("name")):
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
        message += " " + _(
            "{0} more kinds of failure aren't listed here; fix these, check again, and the next ones show."
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
    if len(masters) > MASTERS_SHOWN:
        out["masters_plan_total"] = len(masters)
    if summary.get("excluded"):
        out["left_out"] = left_out_report(session)
    return out
