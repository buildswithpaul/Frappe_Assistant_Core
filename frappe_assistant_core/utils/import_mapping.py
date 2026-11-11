# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Helpers for get_import_schema and set_column_mapping (#33989): which fields of a DocType
can be imported, and the column mapping kept on a FAC Import Session.

The mapping uses Data Import's own shape, ``template_options.column_to_field_map``:
``{"<0-based column position>": "<fieldname>" | "<table fieldname>.<fieldname>" | "Don't Import"}``,
so the import itself (#33993) can copy it straight onto a Data Import.

Whether the user may import into a DocType is import_session.import_target_problem, the
check start_import_session uses.
"""

import difflib
from typing import Any, Dict, List, Optional, Tuple

import frappe
from frappe import _
from frappe.model import display_fieldtypes, no_value_fields, table_fields
from frappe.model.base_document import get_controller
from frappe.utils import cint, flt

DONT_IMPORT = "Don't Import"
# A column that only numbers the rows (S.No, Sr. No., #): never data, so never asked about (#34415)
ROW_NUMBER_HEADERS = {
    "#",
    "sno",
    "srno",
    "slno",
    "rowno",
    "rownumber",
    "lineno",
}  # not "Serial No": a stock item's


def row_number_column(header: str) -> bool:
    return "".join(ch for ch in str(header or "").lower() if ch not in " ._-") in ROW_NUMBER_HEADERS


def unplaced_columns(doc) -> List[Tuple[str, str]]:
    """(position, header) of the session's columns no field was given, not even Don't Import, and
    that hold data: what the user is asked about, all at once."""
    mapped = session_mapping(doc)
    return [
        (str(i), header)
        for i, header in enumerate(session_headers(doc))
        if not mapped.get(str(i)) and str(header).strip() and not row_number_column(header)
    ]


MAX_SELECT_OPTIONS = 25
SESSION_DOCTYPE = "FAC Import Session"


# --- Schema --------------------------------------------------------------------------


def build_import_schema(doctype: str) -> Dict[str, Any]:
    """The fields Data Import can fill on `doctype`, kept short enough for the model to read.

    Uses the rule of Frappe's own import template (no layout or display fields) and also
    leaves out hidden and read-only fields, which an import does not set.
    """
    meta = frappe.get_meta(doctype)
    provided = _provided_fields(doctype)
    fields = _importable_fields(meta)
    if provided:
        # what the import provider leaves out of the record itself (a party's phone and email,
        # which its contacts table imports) isn't offered on it
        own = {df.get("fieldname") for df in provided.get("fields") or []}
        fields = [field for field in fields if field["fieldname"] in own]
    schema: Dict[str, Any] = {
        "doctype": doctype,
        "naming": _naming(meta),
        "fields": fields,
    }

    child_tables = []
    for table_df in meta.get_table_fields():
        if table_df.hidden or table_df.read_only:
            continue
        table = {
            "fieldname": table_df.fieldname,
            "label": table_df.label or table_df.fieldname,
            "doctype": table_df.options,
        }
        if table_df.reqd:
            table["required"] = True
        table["fields"] = _importable_fields(frappe.get_meta(table_df.options))
        child_tables.append(table)
    child_tables += _linked_tables(meta, provided)
    if child_tables:
        schema["child_tables"] = child_tables

    schema["map_as"] = (
        "Map a column to a field by its fieldname, to a child table field as "
        f"'<table fieldname>.<fieldname>', or to \"{DONT_IMPORT}\"."
    )
    return schema


def _provided_fields(doctype: str) -> Optional[Dict[str, Any]]:
    """The fields and tables the DocType's import provider takes (Frappe 16; ERPNext has one for
    Customer and Supplier), or None. Data Import maps the columns against these."""
    try:
        from frappe.core.doctype.data_import.import_provider import get_import_provider
    except ImportError:  # Frappe 15
        return None
    provider = get_import_provider(doctype)
    return (provider.get_import_fields() or None) if provider else None


def _linked_tables(meta, provided: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The import provider's tables that aren't the DocType's own: other records it creates and
    links to each one, as ERPNext's party provider does with Contacts and Addresses."""
    own = {table_df.fieldname for table_df in meta.get_table_fields()}
    tables = []
    for table in (provided or {}).get("child_tables") or []:
        docfields = [frappe._dict(df) for df in table.get("fields") or []]
        linked = docfields[0].get("parent") if docfields else None
        if table["fieldname"] in own or not linked:
            continue
        for df in docfields:
            if df.get("in_import_template"):
                # set by the provider though the DocType's form keeps it (Contact email and mobile)
                df.read_only = 0
        tables.append(
            {
                "fieldname": table["fieldname"],
                "label": table.get("label") or table["fieldname"],
                "doctype": linked,
                "linked": True,
                "note": _("Each row creates a {0} linked to the {1}; the first row is its primary.").format(
                    _(linked), _(meta.name)
                ),
                "fields": _importable_fields(frappe.get_meta(linked), docfields),
            }
        )
    return tables


def _importable_fields(meta, docfields=None) -> List[Dict[str, Any]]:
    fields = []
    for df in meta.fields if docfields is None else docfields:
        if df.fieldtype in display_fieldtypes + no_value_fields or df.hidden or df.read_only:
            continue
        field: Dict[str, Any] = {
            "fieldname": df.fieldname,
            "label": df.label or df.fieldname,
            "type": df.fieldtype,
        }
        if df.fieldtype == "Read Only":
            # The field's type, not a lock (read_only is unset, so an import sets it). Shown as
            # "Read Only", it read as one, and a Customer's phone and email were left out.
            field["type"] = "Data"
            field["note"] = _read_only_type_note(meta, df)
        if df.reqd:
            field["required"] = True
            if df.default:
                field["default"] = df.default
        elif _hsn_validated(meta.name, df.fieldname):
            field["required"] = True
            field["note"] = _("Required by India Compliance on this site for an Item that is sold.")
        elif df.mandatory_depends_on:
            # required in Desk when this holds; the server doesn't check it, so an import doesn't
            field["required_when"] = df.mandatory_depends_on
        if df.fieldtype == "Link":
            field["link"] = df.options
        elif df.fieldtype == "Dynamic Link":
            field["link_type_from"] = df.options
        elif df.fieldtype == "Select" and df.options:
            options = [option for option in df.options.split("\n") if option]
            field["options"] = options[:MAX_SELECT_OPTIONS]
            if len(options) > MAX_SELECT_OPTIONS:
                field["options_total"] = len(options)
        fields.append(field)
    return fields


def _makes_primary_contact(meta, df) -> bool:
    """Whether a new record makes its primary Contact from ``df``: a Customer's or Supplier's
    phone and email on ERPNext 15, read by its create_primary_contact. (ERPNext 16 hides them, and
    its import provider takes them in a contacts table instead.)"""
    if df.fieldtype != "Read Only" or not df.fetch_from:
        return False
    link = meta.get_field(df.fetch_from.partition(".")[0])
    if not (link and link.fieldtype == "Link" and link.options == "Contact"):
        return False
    try:
        return hasattr(get_controller(meta.name), "create_primary_contact")
    except Exception:
        return False


def _read_only_type_note(meta, df) -> str:
    """What becomes of a value imported into a field of type Read Only, which shows a value
    fetched through a link (``fetch_from``) or set by the DocType's own code."""
    if _makes_primary_contact(meta, df):
        return _("On a new {0}, ERPNext creates the primary contact from this.").format(_(meta.name))
    link = meta.get_field(df.fetch_from.partition(".")[0]) if df.fetch_from else None
    if link:
        return _("Filled from {0} when that is set, so the file's value is kept only without it.").format(
            _(link.label or link.fieldname)
        )
    return _("ERPNext may set this itself when the record is saved.")


def _hsn_validated(doctype: str, fieldname: str) -> bool:
    """Whether this is the Item HSN/SAC field and the site refuses a sales Item without it. India
    Compliance makes the field mandatory in code (GST Settings), not in the DocType, so ``reqd`` is 0."""
    if doctype != "Item" or fieldname != "gst_hsn_code":
        return False
    if "india_compliance" not in frappe.get_installed_apps():
        return False
    try:
        from india_compliance.gst_india.utils import get_hsn_settings
    except ImportError:  # an India Compliance without it: the dry run still finds the refusal
        return False

    return bool(get_hsn_settings()[0])


def _naming(meta) -> Dict[str, Any]:
    autoname = (meta.autoname or "").strip()
    if autoname.startswith("field:"):
        rule = f"from the {autoname[len('field:') :]} field"
    elif autoname.lower() == "prompt":
        rule = "typed by the user, so map a column to 'name' (ID) when inserting"
    elif autoname.startswith("naming_series:") or autoname == "naming_series":
        rule = "naming series"
    elif autoname in ("", "hash"):
        rule = "automatic"
    else:
        rule = autoname
    return {"rule": rule, "id_field": "name", "id_note": "Map a column to 'name' to update existing records."}


def _mapping_targets(schema: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Every value a column may map to, keyed the way column_to_field_map stores it."""
    targets: Dict[str, Dict[str, Any]] = {"name": {"label": "ID", "table": None}}
    for field in schema["fields"]:
        targets[field["fieldname"]] = {**field, "table": None}
    for table in schema.get("child_tables", []):
        for field in table["fields"]:
            targets[f"{table['fieldname']}.{field['fieldname']}"] = {**field, "table": table}
    return targets


# --- Column mapping --------------------------------------------------------------------


def resolve_mapping(
    doctype: str, schema: Dict[str, Any], headers: List[str], mapping: Dict[str, Any]
) -> Tuple[Dict[str, str], List[str]]:
    """Turn {column: field} from the model into column_to_field_map entries.

    A column is its header as in the file, or its 0-based position. A field is a fieldname,
    '<table>.<fieldname>', an exact label, or "Don't Import". Returns the entries and a
    message for every one that could not be resolved.
    """
    targets = _mapping_targets(schema)
    by_label = _unique_labels(targets)
    resolved: Dict[str, str] = {}
    problems: List[str] = []

    for column, field in mapping.items():
        position, problem = _column_position(column, headers)
        if problem:
            problems.append(problem)
            continue
        key, problem = _field_key(doctype, field, targets, by_label)
        if problem:
            problems.append(_("Column '{0}': {1}").format(headers[int(position)], problem))
            continue
        resolved[position] = key

    return resolved, problems


def duplicate_targets(column_to_field_map: Dict[str, str], headers: List[str]) -> List[str]:
    """A message for each field that more than one column maps to."""
    columns_by_field: Dict[str, List[str]] = {}
    for position, field in column_to_field_map.items():
        if field != DONT_IMPORT and position.isdigit() and int(position) < len(headers):
            columns_by_field.setdefault(field, []).append(headers[int(position)])
    return [
        _("Columns {0} all map to '{1}'. Map only one of them.").format(
            ", ".join(repr(c) for c in columns), field
        )
        for field, columns in columns_by_field.items()
        if len(columns) > 1
    ]


def describe_mapping(
    schema: Dict[str, Any],
    headers: List[str],
    column_to_field_map: Dict[str, str],
    update: bool = False,
    samples: Optional[List[List[str]]] = None,
) -> Dict[str, Any]:
    """The mapping as FACO shows it: parent and child table rows apart, gaps marked. An
    ``update`` changes only the fields mapped, so no required field is missing for it. For an
    insert, ``samples`` (the file's first rows) say which fields a condition makes required."""
    targets = _mapping_targets(schema)
    parent_rows: List[Dict[str, Any]] = []
    child_rows: Dict[str, List[Dict[str, Any]]] = {}
    not_imported, unmapped = [], []
    mapped_fields = set()

    for position, header in enumerate(headers):
        field = column_to_field_map.get(str(position))
        if not field:
            unmapped.append(header)
            continue
        if field == DONT_IMPORT:
            not_imported.append(header)
            continue
        target = targets.get(field)
        if not target:
            unmapped.append(header)
            continue
        mapped_fields.add(field)
        row = {"column": header, "position": position, "field": field, "label": target["label"]}
        if target["table"]:
            child_rows.setdefault(_table_title(target["table"]), []).append(row)
        else:
            parent_rows.append(row)

    mapped_tables = {field.split(".", 1)[0] for field in mapped_fields if "." in field}
    missing_required = []
    for field, target in [] if update else targets.items():
        table = target["table"]
        if not target.get("required") or target.get("default") or field in mapped_fields:
            continue
        # A child table's required fields matter once any of its columns is mapped.
        if table and table["fieldname"] not in mapped_tables:
            continue
        missing = {"field": field, "label": target["label"]}
        if table:
            missing["table"] = _table_title(table)
        missing_required.append(missing)
    meta = frappe.get_meta(schema["doctype"])
    if not update and (meta.autoname or "").strip().lower() == "prompt" and "name" not in mapped_fields:
        # named by what the user types: Data Import refuses a row without it (#34408)
        missing_required.append({"field": "name", "label": "ID"})
    required_when = (
        [] if update else _required_when(meta, targets, mapped_fields, column_to_field_map, samples)
    )

    summary = _("{0} columns mapped, {1} not imported, {2} unmapped.").format(
        len(parent_rows) + sum(len(rows) for rows in child_rows.values()), len(not_imported), len(unmapped)
    )
    if missing_required:
        summary += " " + _("{0} required field(s) have no column: {1}.").format(
            len(missing_required), ", ".join(m["label"] for m in missing_required)
        )
    if required_when:
        summary += " " + _(
            "{0} field(s) may be required for some rows (Desk asks for them when its condition holds): {1}."
        ).format(len(required_when), ", ".join(r["label"] for r in required_when))

    return {
        "mapping": parent_rows,
        "child_tables": child_rows,
        "not_imported": not_imported,
        "unmapped_columns": unmapped,
        "missing_required": missing_required,
        "required_when": required_when,
        "summary": summary,
    }


def _required_when(meta, targets, mapped_fields, column_to_field_map, samples) -> List[Dict[str, Any]]:
    """The unmapped fields a condition (mandatory_depends_on) makes required, when the sample rows
    meet it or it can't be worked out here (#34408). Frappe checks these only in Desk, so the import
    goes through, and the record then can't be saved in Desk without them."""
    docs = _sample_docs(meta, column_to_field_map, samples)
    out = []
    for field, target in targets.items():
        condition = target.get("required_when")
        if not condition or target["table"] or field in mapped_fields or target.get("default"):
            continue
        rows = _rows_meeting(condition, docs)
        if rows is None or rows:
            out.append({"field": field, "label": target["label"], "when": condition, "sample_rows": rows})
    return out


def _sample_docs(meta, column_to_field_map, samples) -> List[frappe._dict]:
    """Each sample row as the record it would make: its mapped fields, numbers read as numbers."""
    docs = []
    for row in samples or []:
        doc = frappe._dict()
        for position, field in column_to_field_map.items():
            if field == DONT_IMPORT or "." in field or not position.isdigit() or int(position) >= len(row):
                continue
            df = meta.get_field(field)
            value = row[int(position)]
            if df and df.fieldtype in ("Check", "Int"):
                value = cint(value)
            elif df and df.fieldtype in ("Float", "Currency", "Percent"):
                value = flt(value)
            doc[field] = value
        docs.append(doc)
    return docs


def _rows_meeting(condition: str, docs: List[frappe._dict]) -> Optional[int]:
    """In how many sample rows ``condition`` holds, or None when it can't be told: no sample
    rows, or a condition written for the browser (JavaScript) that Python can't read."""
    from frappe.utils.safe_exec import safe_eval

    condition = condition.strip()
    if not docs:
        return None
    if not condition.startswith("eval:"):
        return sum(1 for doc in docs if doc.get(condition))
    met = 0
    for doc in docs:
        try:
            # The DocType's own condition, set by a developer or a System Manager, in Frappe's
            # sandbox; the file's values are its data (doc), never its code.
            # nosemgrep: frappe-codeinjection-eval — sandboxed safe_eval of DocType metadata
            met += bool(safe_eval(condition[len("eval:") :], None, {"doc": doc}))
        except Exception:
            return None
    return met


def _column_position(column: Any, headers: List[str]) -> Tuple[Optional[str], Optional[str]]:
    """The 0-based position of ``column``: a header, or a position. A number is a position first
    (#34413), as the reply names a repeated header's columns by position; only when it is also
    the header of another single column is it refused, naming both ways to say each."""
    key = str(column).strip()
    if key.isdigit() and int(key) < len(headers):
        same = [i for i, header in enumerate(headers) if header.strip() == key]
        if len(same) == 1 and same[0] != int(key):
            return None, _(
                "'{0}' is both a position and the header of column {1}. Pass {1} for the column "
                "headed '{0}', or '{2}' for the column at position {0}."
            ).format(key, same[0], headers[int(key)])
        return key, None
    for matches in (
        [i for i, header in enumerate(headers) if header.strip() == key],
        [i for i, header in enumerate(headers) if header.strip().lower() == key.lower()],
    ):
        if len(matches) == 1:
            return str(matches[0]), None
        if len(matches) > 1:
            return None, _(
                "Column '{0}' appears {1} times in the file. Use its 0-based position instead: {2}."
            ).format(key, len(matches), ", ".join(str(i) for i in matches))
    return None, _("'{0}' is not a column in the file. Its columns are: {1}.").format(key, ", ".join(headers))


def _field_key(
    doctype: str, field: Any, targets: Dict[str, Dict[str, Any]], by_label: Dict[str, str]
) -> Tuple[Optional[str], Optional[str]]:
    if field is None or str(field).strip() in ("", DONT_IMPORT):
        return DONT_IMPORT, None
    value = str(field).strip()
    if value in targets:
        return value, None
    if value.lower() in by_label:
        return by_label[value.lower()], None

    table_part, _dot, fieldname = value.rpartition(".")
    meta = frappe.get_meta(doctype)
    if table_part:
        # a child table's field: judged on the child DocType (#34408)
        table_df = meta.get_field(table_part)
        meta = frappe.get_meta(table_df.options) if table_df and table_df.fieldtype in table_fields else None
    df = meta.get_field(fieldname) if meta else None
    contact_table = f"contacts.{fieldname}"
    if df and df.hidden and not table_part and contact_table in targets:
        # ERPNext 16 hides a party's phone and email: they are its primary Contact's, which its import
        # makes from the same row's contacts table (#34414)
        return (
            None,
            _(
                "'{0}' is hidden on {1}: it is its primary Contact's. Map the column to {2}, and the "
                "Contact is made with the {1} from the same row."
            ).format(value, _(meta.name), contact_table),
        )
    if df and (df.hidden or df.read_only):
        return (
            None,
            (
                _("'{0}' is hidden on {1}, so an import won't set it.")
                if df.hidden
                else _("'{0}' is read-only on {1}, so an import won't set it.")
            ).format(value, meta.name),
        )

    candidates = {**{key: key for key in targets}, **by_label}
    close = difflib.get_close_matches(value.lower(), [c.lower() for c in candidates], n=3, cutoff=0.6)
    lookup = {c.lower(): key for c, key in candidates.items()}
    suggestions = list(dict.fromkeys(lookup[c] for c in close))
    problem = _("'{0}' is not an importable field of {1}.").format(value, doctype)
    if suggestions:
        problem += " " + _("Did you mean {0}?").format(
            f" {_('or')} ".join(f"'{s}' ({targets[s]['label']})" for s in suggestions)
        )
    return None, problem + " " + _("Check get_import_schema for the field list.")


def _unique_labels(targets: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
    """Lowercased label -> target, only for labels that name one field."""
    seen: Dict[str, List[str]] = {}
    for key, target in targets.items():
        # Child fields go by Frappe's import-template label: "Barcode (Barcodes)".
        label = target["label"] if not target["table"] else f"{target['label']} ({target['table']['label']})"
        seen.setdefault(label.lower(), []).append(key)
    return {label: keys[0] for label, keys in seen.items() if len(keys) == 1}


def _table_title(table: Dict[str, Any]) -> str:
    return f"{table['label']} ({table['fieldname']})"


# --- Import session --------------------------------------------------------------------


def load_session(name: str):
    """The session, if this user may change it. Raises DoesNotExistError or PermissionError."""
    from frappe_assistant_core.assistant_core.doctype.fac_import_session.fac_import_session import (
        engine_session,
    )
    from frappe_assistant_core.utils import import_plan

    # The import tools change the session through this copy: it is the engine's (#34400).
    doc = engine_session(name)
    if not frappe.has_permission(SESSION_DOCTYPE, "write", doc=doc):
        raise frappe.PermissionError(_("You can't change import session {0}.").format(name))
    plan = doc.get("migration_plan")
    if plan and import_plan.plan_status(plan) == "Running":
        raise frappe.PermissionError(
            _(
                "Import session {0} is being imported by migration plan {1}: it can't change until the "
                "plan ends. Stop it with stop_migration_plan."
            ).format(name, plan)
        )
    return doc


def session_headers(doc) -> List[str]:
    """The chosen sheet's column headers, as start_import_session stored them."""
    sheets = frappe.parse_json(doc.sheets or "[]") or []
    chosen = [s for s in sheets if s.get("name") == doc.sheet] or sheets[:1]
    return [str(column) for column in (chosen[0].get("columns") if chosen else None) or []]


def session_mapping(doc) -> Dict[str, str]:
    options = frappe.parse_json(doc.template_options or "{}") or {}
    return dict(options.get("column_to_field_map") or {})


def save_mapping(doc, target_doctype: str, column_to_field_map: Dict[str, str], summary: str) -> None:
    """Store the mapping, move the session to Mapped and log the step."""
    options = frappe.parse_json(doc.template_options or "{}") or {}
    options["column_to_field_map"] = column_to_field_map
    doc.target_doctype = target_doctype
    doc.template_options = frappe.as_json(options)
    doc.status = "Mapped"
    doc.log_step("Map Columns", "Success", summary)
    doc.save()
