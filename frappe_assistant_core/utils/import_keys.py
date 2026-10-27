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
