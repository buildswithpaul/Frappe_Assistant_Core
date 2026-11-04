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

"""Old-system IDs (#34244): which old ID became which ERPNext record, and finding it again.

An old system links records by its own IDs ("customer 100"); ERPNext names the record differently.
Nothing in Frappe keeps the old ID, so a later file, or the same file a month later, can't say
which record "customer 100" is. This module keeps and finds it, in the place the consultant chose
for each DocType and source system:

* a **field** on the record (an existing one, or ``fac_old_system_id`` added with their yes), or
* the **key map** (``FAC Import Key Map``), FAC's own table, when they would rather not add a field.

The choice is kept per site, DocType and source system. Only the engine writes old IDs, never the
model. Nothing here shows a user a record they can't read.
"""

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

import frappe
from frappe import _
from frappe.utils import cstr

KEY_MAP = "FAC Import Key Map"
FIELD_NAME = "fac_old_system_id"
FIELD_LABEL = "Old System ID"

#: The site's choice of where a DocType keeps one source system's old IDs (``field:<name>``,
#: ``key_map`` or ``refused_field``), as global defaults, so no extra DocType is needed.
_CHOICE_KEY = "fac_old_id::{doctype}::{system}"
_SYSTEMS_KEY = "fac_old_id_systems::{doctype}::{fieldname}"

CHUNK = 500
#: What share of a file's IDs a field has to hold before it is offered: a field the consultant
#: filled themselves holds the IDs or it doesn't; a standard field (a customer's tax ID) may hold
#: some and is reported with how many.
CUSTOM_FIELD_SHARE = 0.9
STANDARD_FIELD_SHARE = 0.5

#: Standard fields that may hold an old system's ID, by DocType.
STANDARD_FIELDS = {
    "Item": ("item_code",),
    "Account": ("account_number",),
    "Customer": ("tax_id", "gstin"),
    "Supplier": ("tax_id", "gstin"),
}

_WORDS = frozenset({"id", "code", "ref", "reference", "old", "legacy", "external", "source", "number"})
_TEXT_TYPES = ("Data", "Int", "Small Text")


def system_name(value: Any) -> str:
    """A source system as it is kept: trimmed and lowercase ("Odoo " -> "odoo")."""
    return cstr(value).strip().lower()


def normalise(value: Any) -> str:
    """An old ID as text, the way a file's cell and a stored key are compared: no surrounding
    spaces, and a whole number Excel read as a float ("100.0", 100.0) is "100". Text keeps its
    leading zeros ("00100" stays)."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = cstr(value).strip()
    if re.fullmatch(r"-?\d+\.0+", text):
        return text.split(".")[0]
    return text


def distinct_keys(values: Iterable[Any]) -> List[str]:
    """The non-empty IDs of ``values``, each once, in order."""
    seen, out = set(), []
    for value in values:
        key = normalise(value)
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def _chunks(items: List[Any], size: int = CHUNK):
    for start in range(0, len(items), size):
        yield items[start : start + size]


# -- the column of a file that holds the old ID ------------------------------------------------

#: The keys of a session's ``transformation_rules`` that belong to old IDs: other code that rewrites
#: the rules (the fixes) keeps them.
SOURCE_KEY = "source_key"
KEY_MAPS = "key_maps"
RULE_KEYS = (SOURCE_KEY, KEY_MAPS)


def _rules(session) -> Dict[str, Any]:
    return frappe.parse_json(session.transformation_rules or "{}") or {}


def source_key(session) -> Optional[Dict[str, Any]]:
    """The column of the session's file that holds each row's old ID: ``{"position": 0, "system":
    "odoo"}``, or None when the file has none."""
    found = _rules(session).get(SOURCE_KEY)
    return found if isinstance(found, dict) and "position" in found and found.get("system") else None


def set_source_key(session, position: int, system: str) -> None:
    """Mark the column at ``position`` as the old ID of ``system``. The session is saved by the caller."""
    rules = _rules(session)
    rules[SOURCE_KEY] = {"position": int(position), "system": system_name(system)}
    session.transformation_rules = frappe.as_json(rules)


def clear_source_key(session) -> None:
    """The file has no old ID column (any more). The session is saved by the caller."""
    rules = _rules(session)
    if rules.pop(SOURCE_KEY, None) is not None:
        session.transformation_rules = frappe.as_json(rules) if rules else None


def storage_problem(session) -> Optional[str]:
    """Why the session can't be checked yet because nobody has said where its old IDs are kept, or None.
    A file with an old ID column is asked about before its dry run, so the answer is there when the
    records are created."""
    kept = source_key(session)
    if not kept or not session.target_doctype or storage_for(session.target_doctype, kept["system"]):
        return None
    from frappe_assistant_core.utils.import_mapping import session_headers

    headers = session_headers(session)
    position = int(kept["position"])
    column = headers[position] if position < len(headers) else str(position)
    return _(
        "Column '{0}' holds the old system's IDs. Ask the user where to keep them, with "
        "choose_old_id_storage, before the check."
    ).format(column)


def key_maps(session) -> Dict[int, Dict[str, str]]:
    """The columns of the session's file whose values are old IDs of another DocType's records, to be
    translated to the record names: ``{position: {"doctype": "Customer", "system": "odoo"}}``."""
    found = _rules(session).get(KEY_MAPS)
    out: Dict[int, Dict[str, str]] = {}
    for position, spec in (found or {}).items() if isinstance(found, dict) else []:
        if str(position).isdigit() and isinstance(spec, dict) and spec.get("doctype") and spec.get("system"):
            out[int(position)] = {"doctype": spec["doctype"], "system": system_name(spec["system"])}
    return out


def set_key_maps(session, entries: Dict[int, Dict[str, str]]) -> None:
    """Keep ``entries`` as the session's old ID translations (those not in it are dropped). The session is
    saved by the caller."""
    rules = _rules(session)
    if entries:
        rules[KEY_MAPS] = {
            str(position): {"doctype": spec["doctype"], "system": system_name(spec["system"])}
            for position, spec in entries.items()
        }
    else:
        rules.pop(KEY_MAPS, None)
    session.transformation_rules = frappe.as_json(rules) if rules else None


def link_targets(target_doctype: str, column_map: Dict[str, str]) -> Dict[int, str]:
    """``{position: DocType}`` for each mapped column whose field links to a DocType: a field of the
    record, or of one of its child tables (``items.item_code``)."""
    meta = frappe.get_meta(target_doctype)
    out: Dict[int, str] = {}
    for position, key in column_map.items():
        if not str(position).isdigit() or not key or key == "Don't Import":
            continue
        if "." in key:
            table_field, fieldname = key.split(".", 1)
            table = meta.get_field(table_field)
            df = frappe.get_meta(table.options).get_field(fieldname) if table and table.options else None
        else:
            df = meta.get_field(key)
        if df and df.fieldtype == "Link" and df.options:
            out[int(position)] = df.options
    return out


def systems_for(doctype: str) -> List[str]:
    """The source systems whose old IDs of ``doctype`` the site keeps somewhere."""
    prefix = _CHOICE_KEY.format(doctype=doctype, system="")
    rows = frappe.get_all(
        "DefaultValue", filters={"parent": "__default", "defkey": ["like", f"{prefix}%"]}, fields=["defkey"]
    )
    return sorted(row["defkey"][len(prefix) :] for row in rows)


def translate(session, rows: List[List[Any]]) -> List[List[Any]]:
    """The file's rows (header first) with each old ID column's values replaced by the names of the
    records they stand for. An ID that is not kept stays as it is, so the check reports it. Nothing is
    written back: the rule is the session's, the names are looked up each time the rows are read."""
    maps = key_maps(session)
    if not maps or not rows:
        return rows
    user = frappe.session.user
    found = {
        position: resolve(
            spec["doctype"],
            spec["system"],
            [row[position] for row in rows[1:] if position < len(row)],
            user=user,
        )
        for position, spec in maps.items()
    }
    out = [rows[0]]
    for row in rows[1:]:
        row = list(row)
        for position, names in found.items():
            if position < len(row):
                name = names.get(normalise(row[position]))
                if name:
                    row[position] = name
        out.append(row)
    return out


def translated_fields(session) -> set:
    """``(DocType, fieldname)`` of each field an old ID column is mapped to: where the check says an
    ID "isn't imported yet" instead of that a record doesn't exist."""
    from frappe_assistant_core.utils.import_dry_run import column_to_field_map

    maps = key_maps(session)
    if not maps or not session.target_doctype:
        return set()
    meta = frappe.get_meta(session.target_doctype)
    fields = set()
    for position, key in column_to_field_map(session).items():
        if not str(position).isdigit() or int(position) not in maps or not key:
            continue
        if "." in key:
            table_field, fieldname = key.split(".", 1)
            table = meta.get_field(table_field)
            if table:
                fields.add((table.options, fieldname))
        else:
            fields.add((session.target_doctype, key))
    return fields


def suggest(session, rows: List[List[Any]], limit: int = 2000) -> List[Dict[str, Any]]:
    """The mapped columns that hold old IDs the site keeps: for each column that links to a DocType with
    kept IDs and isn't translated yet, the source system in which at least 90 % of its (distinct)
    values resolve. ``rows`` is the file with its header; only its first ``limit`` rows are read."""
    from frappe_assistant_core.utils.import_dry_run import column_to_field_map

    if not rows or not session.target_doctype:
        return []
    kept = key_maps(session)
    headers = rows[0]
    found = []
    for position, doctype in link_targets(session.target_doctype, column_to_field_map(session)).items():
        if position in kept or position >= len(headers):
            continue
        values = distinct_keys(row[position] for row in rows[1 : limit + 1] if position < len(row))
        if not values:
            continue
        best = None
        for system in systems_for(doctype):
            resolved = sum(1 for name in resolve(doctype, system, values).values() if name)
            if resolved / len(values) >= CUSTOM_FIELD_SHARE and (not best or resolved > best["resolved"]):
                best = {
                    "column": str(headers[position]),
                    "position": position,
                    "doctype": doctype,
                    "system": system,
                    "resolved": resolved,
                    "total": len(values),
                }
        if best:
            found.append(best)
    return found


def duplicates(rows: List[List[Any]], position: int, shown: int = 10) -> List[Dict[str, Any]]:
    """The old IDs that more than one row of the file has: ``{"key", "rows"}`` (file row numbers, the
    header being row 1), at most ``shown`` of them."""
    seen: Dict[str, List[int]] = {}
    for number, row in enumerate(rows[1:], start=2):
        key = normalise(row[position]) if position < len(row) else ""
        if key:
            seen.setdefault(key, []).append(number)
    return [{"key": key, "rows": numbers} for key, numbers in seen.items() if len(numbers) > 1][:shown]


# -- where a DocType keeps its old IDs ----------------------------------------------------------


def choice(doctype: str, system: str) -> Optional[str]:
    """``field:<fieldname>``, ``key_map`` or ``refused_field``, or None when nobody has chosen."""
    return frappe.defaults.get_global_default(_CHOICE_KEY.format(doctype=doctype, system=system_name(system)))


def set_choice(doctype: str, system: str, value: str) -> None:
    """Remember where ``doctype`` keeps the old IDs of ``system``. The first source system whose IDs
    go into a field keeps them as they are; any later one's are prefixed with the system's name, so
    two systems' IDs can share one field (R-D4)."""
    system = system_name(system)
    if value.startswith("field:"):
        fieldname = value.split(":", 1)[1]
        systems = systems_of(doctype, fieldname)
        if system not in systems:
            frappe.defaults.set_global_default(
                _SYSTEMS_KEY.format(doctype=doctype, fieldname=fieldname), ",".join(systems + [system])
            )
    frappe.defaults.set_global_default(_CHOICE_KEY.format(doctype=doctype, system=system), value)


def systems_of(doctype: str, fieldname: str) -> List[str]:
    """The source systems whose old IDs ``doctype.fieldname`` keeps, the first one first."""
    value = frappe.defaults.get_global_default(_SYSTEMS_KEY.format(doctype=doctype, fieldname=fieldname))
    return [s for s in cstr(value).split(",") if s]


def storage_for(doctype: str, system: str) -> Optional[Dict[str, Any]]:
    """Where ``doctype`` keeps ``system``'s old IDs: ``{"kind": "field", "fieldname": ...}`` or
    ``{"kind": "key_map"}``; None while nobody has chosen. A refused field is the key map."""
    value = choice(doctype, system)
    if not value:
        return None
    if value.startswith("field:"):
        return {"kind": "field", "fieldname": value.split(":", 1)[1]}
    return {"kind": "key_map"}


def field_value(doctype: str, system: str, key: str) -> str:
    """What the field stores for ``key``: the key itself for the first source system whose IDs the field
    keeps, ``<system>:<key>`` for any later one."""
    storage = storage_for(doctype, system)
    if not storage or storage["kind"] != "field":
        return key
    systems = systems_of(doctype, storage["fieldname"])
    system = system_name(system)
    if not systems or systems[0] == system:
        return key
    return f"{system}:{key}"


# -- finding a field that already holds the IDs -------------------------------------------------


def _candidate_fields(doctype: str) -> List[Tuple[str, str, bool]]:
    """``(fieldname, label, standard)`` for each field of ``doctype`` that may hold old IDs."""
    meta = frappe.get_meta(doctype)
    found: Dict[str, Tuple[str, str, bool]] = {}
    for fieldname in STANDARD_FIELDS.get(doctype, ()):
        df = meta.get_field(fieldname)
        if df:
            found[fieldname] = (fieldname, df.label or fieldname, True)
    if meta.autoname and meta.autoname.startswith("field:"):
        named_by = meta.autoname.split(":", 1)[1]
        if named_by not in found and meta.get_field(named_by):
            found[named_by] = (named_by, meta.get_field(named_by).label or named_by, True)
    for df in meta.fields:
        if (
            df.fieldname in found
            or df.fieldtype not in _TEXT_TYPES
            or (df.hidden and df.fieldname != FIELD_NAME)
        ):
            continue
        if looks_like_id(df.fieldname, df.label):
            found[df.fieldname] = (df.fieldname, df.label or df.fieldname, False)
    return list(found.values())


def looks_like_id(fieldname: str, label: Optional[str] = None) -> bool:
    """Whether a field's name or label says it may hold another system's ID (id, code, legacy ...),
    or it is the field FAC adds for the purpose."""
    if fieldname == FIELD_NAME:
        return True
    return bool(set(re.split(r"[^a-z0-9]+", f"{fieldname} {label or ''}".lower())) & _WORDS)


def find_fields(doctype: str, values: Iterable[Any]) -> List[Dict[str, Any]]:
    """The fields of ``doctype`` that already hold the file's IDs, best first: for each, how many of
    the file's distinct IDs it holds (``matched`` of ``total``), whether a value sits on more than
    one record (``ambiguous``), and whether it is a standard field. A field is listed when it holds
    at least 90 % of the IDs (a standard one, 50 %), and never when an ID would find two records."""
    keys = distinct_keys(values)
    if not keys:
        return []
    found = []
    for fieldname, label, standard in _candidate_fields(doctype):
        matched, ambiguous = _count_matches(doctype, fieldname, keys)
        share = matched / len(keys)
        if ambiguous or share < (STANDARD_FIELD_SHARE if standard else CUSTOM_FIELD_SHARE):
            continue
        found.append(
            {
                "fieldname": fieldname,
                "label": label,
                "standard": standard,
                "matched": matched,
                "total": len(keys),
                "ambiguous": False,
            }
        )
    return sorted(found, key=lambda f: (-f["matched"], f["standard"]))


def _count_matches(doctype: str, fieldname: str, keys: List[str]) -> Tuple[int, bool]:
    """How many of ``keys`` ``doctype.fieldname`` holds, and whether one of them is on two records."""
    held: Dict[str, int] = {}
    for chunk in _chunks(keys):
        for stored in frappe.get_all(doctype, filters={fieldname: ["in", chunk]}, pluck=fieldname):
            held[cstr(stored).casefold()] = held.get(cstr(stored).casefold(), 0) + 1
    matched = sum(1 for key in keys if key.casefold() in held)
    return matched, any(count > 1 for count in held.values())


# -- resolving an old ID ------------------------------------------------------------------------


def resolve(
    doctype: str, system: str, keys: Iterable[Any], user: Optional[str] = None
) -> Dict[str, Optional[str]]:
    """``{key: record name or None}`` for each old ID: through the field when ``doctype`` keeps its
    IDs in one, else through the key map. A record ``user`` can't read counts as not found, and
    its name is never returned."""
    user = user or frappe.session.user
    keys = distinct_keys(keys)
    storage = storage_for(doctype, system)
    if not keys or not storage:
        return {key: None for key in keys}
    found = (
        _from_field(doctype, system, storage["fieldname"], keys, user)
        if storage["kind"] == "field"
        else _from_map(doctype, system, keys, user)
    )
    return {key: found.get(key) for key in keys}


def _from_field(doctype: str, system: str, fieldname: str, keys: List[str], user: str) -> Dict[str, str]:
    stored = {field_value(doctype, system, key).casefold(): key for key in keys}
    found: Dict[str, str] = {}
    for chunk in _chunks([field_value(doctype, system, key) for key in keys]):
        try:
            rows = frappe.get_list(
                doctype,
                filters={fieldname: ["in", chunk]},
                fields=["name", fieldname],
                user=user,
                limit_page_length=0,
            )
        except frappe.PermissionError:  # a user who can't read the DocType finds nothing
            return {}
        for row in rows:
            key = stored.get(cstr(row[fieldname]).casefold())
            if key is not None:
                found[key] = row["name"]
    return found


def _from_map(doctype: str, system: str, keys: List[str], user: str) -> Dict[str, str]:
    rows: List[Dict[str, Any]] = []
    for chunk in _chunks(keys):
        rows += frappe.get_all(
            KEY_MAP,
            filters={
                "source_system": system_name(system),
                "target_doctype": doctype,
                "source_key": ["in", chunk],
            },
            fields=["source_key", "target_name"],
        )
    visible = _visible(doctype, [row["target_name"] for row in rows], user)
    return {row["source_key"]: row["target_name"] for row in rows if row["target_name"] in visible}


def _visible(doctype: str, names: List[str], user: str) -> set:
    """Which of the records ``names`` of ``doctype`` exist and ``user`` may read."""
    seen = set()
    for chunk in _chunks(sorted(set(names))):
        try:
            seen.update(
                frappe.get_list(
                    doctype, filters={"name": ["in", chunk]}, pluck="name", user=user, limit_page_length=0
                )
            )
        except frappe.PermissionError:
            return set()
    return seen


# -- recording an old ID ------------------------------------------------------------------------


def record_pairs(
    session_name: Optional[str], doctype: str, system: str, pairs: Iterable[Tuple[Any, str]]
) -> Dict[str, List[str]]:
    """Keep the old ID of each ``(old ID, record name)`` where ``doctype`` keeps them: in its field,
    or as a key-map row. Running it again for the same pairs adds nothing. Returns ``{"written": [...],
    "conflicts": [...]}``: a conflict is an old ID that already names another record that still
    exists, which is never overwritten; one naming a record that is gone is overwritten."""
    storage = storage_for(doctype, system)
    out: Dict[str, List[str]] = {"written": [], "conflicts": []}
    if not storage:
        return out
    pairs = [(normalise(key), name) for key, name in pairs if normalise(key) and name]
    if storage["kind"] == "field":
        _write_field(doctype, system, storage["fieldname"], pairs, out)
    else:
        _write_map(session_name, doctype, system, pairs, out)
    return out


def _write_field(doctype: str, system: str, fieldname: str, pairs, out) -> None:
    for key, name in pairs:
        value = field_value(doctype, system, key)
        owner = frappe.db.get_value(doctype, {fieldname: value, "name": ["!=", name]}, "name")
        if owner:
            out["conflicts"].append(key)
            continue
        if frappe.db.get_value(doctype, name, fieldname) != value:
            frappe.db.set_value(doctype, name, fieldname, value, update_modified=False)
        out["written"].append(key)


def _write_map(session_name, doctype: str, system: str, pairs, out) -> None:
    system = system_name(system)
    for key, name in pairs:
        existing = frappe.db.get_value(
            KEY_MAP,
            {"source_system": system, "target_doctype": doctype, "source_key": key},
            ["name", "target_name"],
            as_dict=True,
        )
        if existing and existing.target_name == name:
            out["written"].append(key)
            continue
        if existing and frappe.db.exists(doctype, existing.target_name):
            out["conflicts"].append(key)
            continue
        if existing:  # its record is gone: the key is free again
            frappe.delete_doc(KEY_MAP, existing.name, ignore_permissions=True, force=True)
        frappe.get_doc(
            {
                "doctype": KEY_MAP,
                "source_system": system,
                "source_key": key,
                "target_doctype": doctype,
                "target_name": name,
                "import_session": session_name,
                "how": "Imported",
            }
        ).insert(ignore_permissions=True)
        out["written"].append(key)


def record(session, data_import: str) -> Dict[str, Any]:
    """After a Data Import of ``session`` ended: keep the old ID of every record it created, from the
    key column of the file it imported. Rows that failed or were left out have no record, so get
    nothing; a record spread over several rows takes the first non-empty key. Run again for the same
    Data Import (a retry, each level of a tree file), it adds nothing twice. Returns what
    ``record_pairs`` does, ``{}`` when the file has no old ID column, nobody has chosen where to
    keep them, or the session updates records instead of creating them."""
    kept = source_key(session)
    if not kept or (session.import_type or "Insert New Records") != "Insert New Records":
        return {}
    if not session.target_doctype or not storage_for(session.target_doctype, kept["system"]):
        return {}
    from frappe_assistant_core.utils import import_failures

    rows = import_failures._import_file_rows(data_import)
    position = int(kept["position"])
    pairs: List[Tuple[str, str]] = []
    for log in frappe.get_all(
        "Data Import Log",
        filters={"data_import": data_import, "success": 1},
        fields=["docname", "row_indexes"],
        order_by="log_index",
    ):
        for number in sorted(frappe.parse_json(log.row_indexes or "[]")):
            row = rows[number - 1] if 2 <= number <= len(rows) else []
            key = normalise(row[position]) if position < len(row) else ""
            if key:
                pairs.append((key, log.docname))
                break
    return record_pairs(session.name, session.target_doctype, kept["system"], pairs)


def remove_for_session(session_name: str) -> int:
    """Undo: delete the key-map rows an import session wrote. Field values go with their records."""
    names = frappe.get_all(KEY_MAP, filters={"import_session": session_name}, pluck="name")
    for name in names:
        frappe.delete_doc(KEY_MAP, name, ignore_permissions=True, force=True)
    return len(names)


def sweep_orphans() -> int:
    """Delete the key-map rows whose record is gone (deleted by hand since). The resolver already
    treats them as not found; this keeps the table from growing."""
    removed = 0
    for doctype in frappe.get_all(KEY_MAP, pluck="target_doctype", distinct=True):
        if not frappe.db.exists("DocType", doctype):
            gone = frappe.get_all(KEY_MAP, filters={"target_doctype": doctype}, pluck="name")
        else:
            rows = frappe.get_all(
                KEY_MAP, filters={"target_doctype": doctype}, fields=["name", "target_name"]
            )
            alive = (
                set(
                    frappe.get_all(
                        doctype, filters={"name": ["in", [r["target_name"] for r in rows]]}, pluck="name"
                    )
                )
                if rows
                else set()
            )
            gone = [row["name"] for row in rows if row["target_name"] not in alive]
        for name in gone:
            frappe.delete_doc(KEY_MAP, name, ignore_permissions=True, force=True)
            removed += 1
    return removed
