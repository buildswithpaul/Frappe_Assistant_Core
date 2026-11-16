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

"""Where the old IDs of an import session are kept (#34244), through set_column_mapping.

FAC's key map by default: it adds nothing to the DocType and nobody has to answer for it. A field
instead, when a System Manager chooses one (``old_id_field``): one that already holds the file's IDs,
or the Old System ID field FACO adds with ``create_document`` (its own approval card and
customisation warning, never a batch) when the user wants to see the IDs on the form. Nothing here
writes a customisation: this module only reports, verifies and records the choice.
"""

from typing import Any, Dict, List, Optional

import frappe
from frappe import _

from frappe_assistant_core.utils import import_keys
from frappe_assistant_core.utils.import_mapping import session_headers
from frappe_assistant_core.utils.import_session import read_sheet_rows, readable_session_file

SECTION_TYPES = ("Section Break", "Tab Break")


class StorageProblem(Exception):
    """The choice can't be made. The message is shown to the user."""


def key_column(session) -> Dict[str, Any]:
    """The session's old ID column: ``{"position", "system", "header"}``. Raises StorageProblem when the
    session has none yet."""
    kept = import_keys.source_key(session)
    if not kept:
        raise StorageProblem(
            _(
                "This session has no old ID column yet. Mark it with set_column_mapping "
                "(source_key_column and source_system) first."
            )
        )
    headers = session_headers(session)
    position = int(kept["position"])
    return {
        "position": position,
        "system": kept["system"],
        "header": headers[position] if position < len(headers) else str(position),
    }


def key_values(session) -> List[str]:
    """The distinct old IDs of the session's file, from its key column."""
    position = key_column(session)["position"]
    try:
        rows = read_sheet_rows(readable_session_file(session), session.sheet or None)
    except Exception as e:  # a file that stayed in the chat can't be read here
        raise StorageProblem(str(e))
    return import_keys.distinct_keys(row[position] for row in rows[1:] if position < len(row))


def keys_by_row(session) -> Dict[int, str]:
    """``{file row number: old ID}`` for the session's file (the header is row 1), empty cells left out.
    Empty when the session has no old ID column or its file can't be read."""
    try:
        position = key_column(session)["position"]
        rows = read_sheet_rows(readable_session_file(session), session.sheet or None)
    except Exception:
        return {}
    found = {}
    for number, row in enumerate(rows[1:], start=2):
        key = import_keys.normalise(row[position]) if position < len(row) else ""
        if key:
            found[number] = key
    return found


def first_section_end(doctype: str) -> Optional[str]:
    """The last field of the form's first section: where a field FAC adds sits, in view. None when
    the form has no field to put it after."""
    fields = [df for df in frappe.get_meta(doctype).fields if df.fieldname]
    previous = None
    for index, df in enumerate(fields):
        if index and df.fieldtype in SECTION_TYPES:
            break
        previous = df.fieldname
    return previous


def field_record(doctype: str) -> Dict[str, Any]:
    """The ``create_document`` input that adds the Old System ID field to ``doctype``: a read-only,
    indexed Data field that a copy of the record doesn't carry."""
    data = {
        "dt": doctype,
        "fieldname": import_keys.FIELD_NAME,
        "label": import_keys.FIELD_LABEL,
        "fieldtype": "Data",
        "read_only": 1,
        "search_index": 1,
        "no_copy": 1,
        "description": _("The record's ID in the system it was migrated from."),
    }
    after = first_section_end(doctype)
    if after:
        data["insert_after"] = after
    return {"doctype": "Custom Field", "data": data}


def report(session) -> Dict[str, Any]:
    """What to ask the consultant about where to keep the session's old IDs, and the choice made so
    far. Reads the file; changes nothing."""
    column = key_column(session)
    doctype, system = session.target_doctype, column["system"]
    out: Dict[str, Any] = {
        "doctype": doctype,
        "system": system,
        "column": column["header"],
    }
    storage = import_keys.storage_for(doctype, system)
    if storage["kind"] == "field":
        out["kept_in"] = storage["fieldname"]
        out["message"] = _("The old IDs of {0} for {1} are kept in {1} > {2}.").format(
            system, _(doctype), storage["fieldname"]
        )
        return out
    out["kept_in"] = "key_map"

    values = key_values(session)
    out["ids"] = len(values)
    candidates = import_keys.find_fields(doctype, values)
    ours = frappe.get_meta(doctype).has_field(import_keys.FIELD_NAME)
    if ours and not any(c["fieldname"] == import_keys.FIELD_NAME for c in candidates):
        # made earlier, for another file: it holds none of this file's IDs yet, and is the right place
        candidates.insert(
            0,
            {
                "fieldname": import_keys.FIELD_NAME,
                "label": import_keys.FIELD_LABEL,
                "standard": False,
                "matched": 0,
                "total": len(values),
                "ambiguous": False,
            },
        )
    out["existing_fields"] = candidates
    if candidates:
        best = candidates[0]
        out["message"] = _(
            "They are kept in FAC's key map, which adds nothing to the {0} form. They are also in "
            "{0} > {1} ({2} of {3} match): a System Manager can keep them there instead."
        ).format(_(doctype), _(best["label"]), best["matched"], best["total"])
    else:
        out["message"] = _("They are kept in FAC's key map, which adds nothing to the {0} form.").format(
            _(doctype)
        )
        # Only when the user asks to see the old IDs on the form: the field to add, on its own card.
        out["new_field"] = field_record(doctype)
    return out


def use_field(session, fieldname: str) -> Dict[str, Any]:
    """Keep the session's old IDs in ``fieldname`` of its DocType. Only a field that holds the file's IDs
    (as ``find_fields`` finds), or the one FAC adds, can be chosen: nothing is taken on trust."""
    column = key_column(session)
    doctype, system = session.target_doctype, column["system"]
    _only_a_system_manager()
    allowed = {c["fieldname"] for c in import_keys.find_fields(doctype, key_values(session))}
    if frappe.get_meta(doctype).has_field(import_keys.FIELD_NAME):
        allowed.add(import_keys.FIELD_NAME)
    if fieldname not in allowed:
        raise StorageProblem(
            _(
                "{0} doesn't hold this file's IDs, so it can't be used for them. The mapping's "
                "old_ids lists the fields that can."
            ).format(fieldname)
        )
    import_keys.set_choice(doctype, system, f"field:{fieldname}")
    return _recorded(session, doctype, system, _("in {0} > {1}").format(_(doctype), fieldname))


def use_key_map(session) -> Dict[str, Any]:
    """Keep the session's old IDs in FAC's key map: nothing is added to the DocType."""
    column = key_column(session)
    doctype, system = session.target_doctype, column["system"]
    if import_keys.storage_for(doctype, system)["kind"] == "field":
        _only_a_system_manager()  # moving a System Manager's field choice back is theirs too
    import_keys.set_choice(doctype, system, "key_map")
    return _recorded(session, doctype, system, _("in FAC's key map"))


def keep_in_key_map_unless_chosen(session) -> None:
    """The default for a session's old ID column: FAC's key map, recorded for its DocType and source
    system so later files find the system, unless a choice is already kept. Overwrites nothing."""
    column = key_column(session)
    if not import_keys.choice(session.target_doctype, column["system"]):
        import_keys.set_choice(session.target_doctype, column["system"], "key_map")


def _only_a_system_manager() -> None:
    """Where a DocType keeps old IDs is one setting for every import on the site, and a field choice
    writes the IDs into that field of each record: a System Manager's call, not any importer's."""
    if "System Manager" not in frappe.get_roles():
        raise StorageProblem(
            _(
                "Only a System Manager can choose a field for the old IDs. They are kept in FAC's "
                "key map, which works the same for the import."
            )
        )


def _recorded(session, doctype: str, system: str, where: str) -> Dict[str, Any]:
    message = _("The old IDs of {0} for {1} are kept {2}.").format(system, _(doctype), where)
    session.log_step("Old IDs", "Success", message)
    session.save()
    return {
        "doctype": doctype,
        "system": system,
        "kept_in": import_keys.storage_for(doctype, system).get("fieldname", "key_map"),
        "message": message,
    }
