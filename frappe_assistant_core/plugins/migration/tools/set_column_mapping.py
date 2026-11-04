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

from frappe_assistant_core.core.base_tool import BaseTool, exception_message, permission_error_result
from frappe_assistant_core.utils import import_update
from frappe_assistant_core.utils.import_mapping import (
    DONT_IMPORT,
    SESSION_DOCTYPE,
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
            "questions."
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
            if not isinstance(mapping, dict) or not mapping:
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
            save_mapping(doc, target, merged, described["summary"])
            result = {
                "success": True,
                "session": session_name,
                "doctype": target,
                "status": doc.status,
                **described,
            }
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
