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
Set Column Mapping Tool for Core Plugin.
Saves which file column goes to which field on an import session.
"""

from typing import Any, Dict

import frappe
from frappe import _
from frappe.utils import cstr

from frappe_assistant_core.core.base_tool import BaseTool, exception_message, permission_error_result
from frappe_assistant_core.utils import import_keys, import_update
from frappe_assistant_core.utils.import_mapping import (
    DONT_IMPORT,
    SESSION_DOCTYPE,
    _column_position,
    build_import_schema,
    describe_mapping,
    duplicate_targets,
    load_session,
    resolve_mapping,
    save_mapping,
    session_headers,
    session_mapping,
)
from frappe_assistant_core.utils.import_session import (
    SAMPLE_SIZE,
    FileProblem,
    import_target_problem,
    read_sheet_rows,
    readable_session_file,
)


class SetColumnMapping(BaseTool):
    """
    Tool for saving a migration file's column mapping on its import session.

    Every field is checked against the DocType's import schema first, and nothing is saved
    unless all of them pass, so the model can correct a mistake and call again.
    """

    def __init__(self):
        super().__init__()
        self.name = "set_column_mapping"
        self.description = (
            "Save which column of the user's migration file goes to which ERPNext field, on its "
            "import session. Pass only the columns to set or change; columns already mapped keep "
            "their field. Each field is checked against get_import_schema, and nothing is saved if "
            "any is wrong: the result says what to fix. Pass doctype the first time, or to change "
            "the target (that clears the old mapping). The result is the full mapping to show the "
            "user: parent fields and each child table apart, with unmapped columns and required "
            'fields that have no column. Map a column to "Don\'t Import" only when the user says '
            "so: a column you can't place is asked about, never dropped. Next, once the user "
            "agrees the mapping: dry_run_import to "
            "check every row. For a session in a migration plan, don't ask the user here: map what "
            "you are sure of, and dry_run_import with the plan asks the rest with the plan's other "
            "questions. "
            "When the file has a column holding the old system's own ID for each row (an Odoo id or "
            "External ID, a Zoho Customer ID, a ledger's name), pass it as source_key_column with "
            "source_system: the IDs are then kept, so later files that refer to them can be translated. "
            "The key column is not imported unless you also map it to a field."
        )
        self.requires_permission = None  # Checked on the session and the target DocType
        # what the user's file says reaches the model fenced (#34003)
        self.untrusted_fields = (
            "mapping",
            "child_tables",
            "not_imported",
            "unmapped_columns",
            "summary",
            "problems",
            "columns",
            "old_ids",
            "old_id_columns",
            "old_id_suggestions",
            "error",
        )

        self.inputSchema = {
            "type": "object",
            "properties": {
                "session": {"type": "string", "description": "The import session id"},
                "mapping": {
                    "type": "object",
                    "description": (
                        "Column → field. A column is its header exactly as in the file, or its "
                        "0-based position. A field is a fieldname, '<table fieldname>.<fieldname>' "
                        f'for a child table, or "{DONT_IMPORT}" to skip the column.'
                    ),
                },
                "doctype": {
                    "type": "string",
                    "description": "The target DocType. Needed the first time; changing it clears the mapping.",
                },
                "import_type": {
                    "type": "string",
                    "enum": ["Insert New Records", "Update Existing Records"],
                    "description": "Change the session's import type. Default: keep it.",
                },
                "old_id_columns": {
                    "type": "object",
                    "description": (
                        "Columns that hold the OLD system's ID of a record this file points at (an invoice's "
                        "partner_id 42, meaning customer 42 of the old system), by column: "
                        '{"Partner ID": {"doctype": "Customer", "source_system": "odoo"}}. The values are '
                        "then translated to the records' names before the check, in the record's fields "
                        "and its child tables. source_system can be left out when the site keeps the IDs of "
                        "only one system for that DocType. The result's old_id_suggestions lists the "
                        "columns that look like this."
                    ),
                },
                "source_key_column": {
                    "type": "string",
                    "description": (
                        "The column that holds the old system's ID for each row (its header, or its "
                        "0-based position). Set it when the file has one; pass it again to change it."
                    ),
                },
                "source_system": {
                    "type": "string",
                    "description": (
                        "The system the file comes from, for example 'odoo', 'zoho' or 'tally': the "
                        "old IDs of one system are kept apart from another's. Needed with source_key_column."
                    ),
                },
                "match_on": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "For Update Existing Records: the field(s) that find each row's "
                    "record, e.g. ['tax_id'] or ['item_code', 'price_list']. Each must be mapped from "
                    "a column. Not needed when a column is mapped to the ID ('name').",
                },
            },
            "required": ["session", "mapping"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        session_name = arguments.get("session")
        mapping = arguments.get("mapping")
        try:
            key_column = arguments.get("source_key_column")
            has_key = key_column is not None and cstr(key_column).strip() != ""
            old_id_columns = arguments.get("old_id_columns")
            has_translations = isinstance(old_id_columns, dict) and bool(old_id_columns)
            if not isinstance(mapping, dict) or (not mapping and not has_key and not has_translations):
                return {"success": False, "error": _("mapping must be an object of column → field.")}

            try:
                doc = load_session(session_name)
            except frappe.DoesNotExistError:
                return {"success": False, "error": _("Import session '{0}' not found.").format(session_name)}
            except frappe.PermissionError as e:
                return permission_error_result(SESSION_DOCTYPE, exception_message(e), name=session_name)

            # Mapping sets the session back to Mapped, for a check of the rows not imported yet: never
            # while its import runs (a second import would take rows the first hasn't reached yet),
            # nor once it was cancelled or undone.
            refused = _mapping_refused(doc.status) or _check_running(doc)
            if refused:
                return {"success": False, "error": refused, "session": session_name}

            current_target = doc.target_doctype or None
            target = arguments.get("doctype") or current_target
            if not target:
                return {
                    "success": False,
                    "error": _("This session has no target DocType yet. Pass doctype, e.g. 'Customer'."),
                }

            import_type = arguments.get("import_type") or doc.import_type or "Insert New Records"
            refused = _imported_as(doc, target, import_type)
            if refused:
                return {"success": False, "error": refused, "session": session_name}
            # Before any work: the user must be able to import into the target.
            problem = import_target_problem(target, import_type)
            if problem:
                return {"success": False, "error": problem, "doctype": target}

            headers = session_headers(doc)
            if not headers:
                return {"success": False, "error": _("The session has no column headers for its sheet.")}

            schema = build_import_schema(target)
            existing = session_mapping(doc) if target == current_target else {}
            resolved, problems = resolve_mapping(target, schema, headers, mapping)
            merged = {**existing, **resolved}
            problems += duplicate_targets(merged, headers)
            key_position, key_system = None, ""
            if has_key:
                key_position, key_problems = _source_key(doc, headers, key_column, arguments)
                problems += key_problems
                if key_position is not None and key_position not in merged:
                    merged[key_position] = (
                        DONT_IMPORT  # an old ID is kept, not imported, unless it is mapped too
                    )
                key_system = import_keys.system_name(arguments.get("source_system"))
            translations, translation_problems = _translations(doc, target, headers, merged, old_id_columns)
            problems += translation_problems
            match_key = ""
            if import_type == import_update.UPDATE:
                match_on, update_problems = import_update.mapping_problems(
                    target, merged, headers, arguments.get("match_on") or []
                )
                problems += update_problems
                match_key = ",".join(match_on)
            if problems:
                return {
                    "success": False,
                    "error": _("The mapping was not saved. Fix these and call again."),
                    "problems": problems,
                    "columns": headers,
                }

            described = describe_mapping(
                schema, headers, merged, update=import_type == import_update.UPDATE, samples=_samples(doc)
            )
            doc.import_type = import_type
            doc.match_key = match_key
            if key_position is not None:
                import_keys.set_source_key(doc, int(key_position), key_system or _kept_system(doc))
            elif target != current_target:
                import_keys.clear_source_key(doc)  # another DocType: the old column isn't this file's key
            import_keys.set_key_maps(doc, translations)
            save_mapping(doc, target, merged, described["summary"])
            result = {
                "success": True,
                "session": session_name,
                "doctype": target,
                "status": doc.status,
                **described,
            }
            if key_position is not None:
                header = headers[int(key_position)]
                # the key column is not imported on purpose: not a column the model couldn't place
                described["not_imported"] = [h for h in described["not_imported"] if h != header]
                result["not_imported"] = described["not_imported"]
                result["old_ids"] = {
                    "column": header,
                    "system": import_keys.source_key(doc)["system"],
                    "message": _(
                        "Column '{0}' holds the old system's IDs. They are kept for each record the import "
                        "creates; before the dry run, ask where to keep them (choose_old_id_storage)."
                    ).format(header),
                }
            result.update(_old_id_notes(doc, key_position, translations))
            if described["not_imported"]:
                # A column the model couldn't place went to Don't Import unasked, and the customers got
                # the default territory. Names no column: they are the file's, fenced in not_imported.
                result["note"] = _(
                    "The columns in not_imported won't be imported. Unless the user chose that, show "
                    "them to the user and ask: a column with no field of the same name may still belong "
                    "in one (a state or region in Territory). In a migration plan, ask with the plan's "
                    "questions."
                )
            return result

        except Exception as e:
            frappe.log_error(
                title=_("Set Column Mapping Error"), message=f"Error saving column mapping: {e!s}"
            )
            return {"success": False, "error": str(e)}


def _translations(doc, target, headers, merged, given):
    """``(entries, problems)``: the session's old ID translations after this call. The ones it had stay
    while their column still links to the same DocType; ``given`` adds or changes some."""
    links = import_keys.link_targets(target, merged)
    entries = {
        position: spec
        for position, spec in import_keys.key_maps(doc).items()
        if links.get(position) == spec["doctype"]
    }
    problems = []
    for column, spec in (given if isinstance(given, dict) else {}).items():
        position, problem = _column_position(column, headers)
        if problem:
            problems.append(problem)
            continue
        position = int(position)
        spec = spec if isinstance(spec, dict) else {}
        doctype = spec.get("doctype")
        if not doctype or links.get(position) != doctype:
            problems.append(
                _(
                    "Column '{0}' isn't mapped to a field that links to {1}, so its IDs can't be translated."
                ).format(headers[position], _(doctype or "?"))
            )
            continue
        system = import_keys.system_name(spec.get("source_system"))
        known = import_keys.systems_for(doctype)
        if not system:
            if len(known) == 1:
                system = known[0]
            else:
                problems.append(
                    _("Column '{0}': say which system its IDs come from (source_system){1}.").format(
                        headers[position],
                        _(": the site keeps IDs of {0}").format(", ".join(known)) if known else "",
                    )
                )
                continue
        if system not in known:
            problems.append(
                _(
                    "No old IDs of {0} for {1} are kept on this site, so column '{2}' can't be translated."
                ).format(system, _(doctype), headers[position])
            )
            continue
        entries[position] = {"doctype": doctype, "system": system}
    return entries, problems


def _old_id_notes(doc, key_position, translations):
    """What the result adds about old IDs: suggestions for columns that look like them, a repeated key,
    and the columns being translated."""
    notes = {}
    links = import_keys.link_targets(doc.target_doctype, session_mapping(doc))
    if not (
        translations
        or key_position is not None
        or any(import_keys.systems_for(d) for d in set(links.values()))
    ):
        return notes  # nothing to say about old IDs: the file isn't read again
    try:
        rows = read_sheet_rows(readable_session_file(doc), doc.sheet or None)
    except FileProblem:
        rows = []
    if translations:
        notes["old_id_columns"] = {
            str(rows[0][p]) if rows and p < len(rows[0]) else str(p): spec for p, spec in translations.items()
        }
    suggestions = import_keys.suggest(doc, rows)
    if suggestions:
        notes["old_id_suggestions"] = suggestions
    if key_position is not None and rows:
        repeated = import_keys.duplicates(rows, int(key_position))
        if repeated:
            notes.setdefault("old_ids", {})["duplicates"] = repeated
    return notes


def _source_key(doc, headers, column, arguments):
    """``(position, problems)`` for the column that holds the old IDs, and the system they are from:
    passed now, or the one the session already has."""
    position, problem = _column_position(column, headers)
    if problem:
        return None, [problem]
    if not import_keys.system_name(arguments.get("source_system")) and not _kept_system(doc):
        return None, [
            _(
                "Say which system the old IDs come from (source_system), for example 'odoo' or "
                "'zoho': the IDs of one system are kept apart from another's."
            )
        ]
    return position, []


def _kept_system(doc) -> str:
    """The source system the session already has, or ''."""
    kept = import_keys.source_key(doc)
    return kept["system"] if kept else ""


def _samples(doc) -> list:
    """The file's first rows under its headings: what the mapping judges a field's condition on."""
    try:
        return read_sheet_rows(readable_session_file(doc), doc.sheet or None)[1 : SAMPLE_SIZE + 1]
    except FileProblem:
        return []  # a session whose file stayed in the chat (before #34405)


# Make sure class name matches file name for discovery
set_column_mapping = SetColumnMapping


def _imported_as(doc, target: str, import_type: str):
    """Rows a Data Import of the session brought in are known as imported by their row
    numbers, whatever the DocType: another target or import type would skip them for good."""
    current = doc.import_type or "Insert New Records"
    if not doc.data_imports or (target, import_type) == (doc.target_doctype, current):
        return None
    return _(
        "This session already imported rows as {0} ({1}), so it stays {0}. To import the file as "
        "{2} ({3}), start a new import session."
    ).format(_(doc.target_doctype), _(current), _(target), _(import_type))


def _check_running(doc):
    """A background check stores its result when it ends: a remap now would be stamped as checked."""
    from frappe_assistant_core.utils import import_dry_run as dry_run

    return dry_run.check_running() if dry_run.is_running(doc) else None


def _mapping_refused(status: str):
    """Why a session with ``status`` can't be remapped, or None."""
    from frappe_assistant_core.utils.import_dry_run import RUNNABLE_STATUSES

    if status in ("File Read", *RUNNABLE_STATUSES):
        return None
    if status == "Importing":
        return _(
            "This session's import is still running. Wait for it to finish, or continue it with "
            "start_import, before changing the mapping."
        )
    if status in ("Undoing", "Undone"):
        being = _("is being undone") if status == "Undoing" else _("was undone")
        return _("This import session is {0}: the import {1}. Start a new import session.").format(
            status, being
        )
    return _("This import session is {0}, so its mapping can't change. Start a new import session.").format(
        status
    )
