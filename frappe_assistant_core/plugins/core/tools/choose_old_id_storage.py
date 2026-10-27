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
Choose Old ID Storage Tool for Core Plugin (#34244).

Where the old system's IDs of an import session are kept: in a field that already holds them, in a
new "Old System ID" field (which FACO adds with create_document, on its own approval card), or in
FAC's key map. Called without ``use`` it reports what to ask the user; called with it, it records
the answer after checking it.
"""

from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool, exception_message, permission_error_result
from frappe_assistant_core.utils import import_key_setup
from frappe_assistant_core.utils.import_mapping import SESSION_DOCTYPE, load_session


class ChooseOldIdStorage(BaseTool):
    """Ask where an import session's old IDs are kept, and record the answer."""

    def __init__(self):
        super().__init__()
        self.name = "choose_old_id_storage"
        self.description = (
            "Where to keep the old system's IDs of an import session whose file has an old ID column "
            "(marked with set_column_mapping source_key_column). Ask before the dry run: the check is "
            "refused until the choice is made. Call it with only the session: the result says what to "
            "ask the user. offer 'existing_field': a field already holds these IDs, so ask the "
            "question in `question` and, on yes, call again with use 'field' and that fieldname. "
            "offer 'new_field': ask `question`; on yes create the field with create_document, exactly "
            "the input in new_field.record, on its own (never in a list), then call again with use "
            "'field' and fieldname 'fac_old_system_id'. When the user doesn't want a field, call "
            "again with use 'key_map': the IDs are then kept in FAC's own key map, and nothing is "
            "added to the DocType; say so in one sentence and don't ask again. The choice is kept for "
            "later sessions of the same DocType and source system, so it is asked once."
        )
        self.requires_permission = None  # Checked on the session
        # The file's header and the user's own words reach the model fenced (#34003).
        self.untrusted_fields = ("column", "question", "message", "error", "existing_fields", "new_field")
        self.inputSchema = {
            "type": "object",
            "properties": {
                "session": {"type": "string", "description": "The import session id"},
                "use": {
                    "type": "string",
                    "enum": ["field", "key_map"],
                    "description": "The user's answer: keep the IDs in a field, or in FAC's key map. "
                    "Leave out to see what to ask.",
                },
                "fieldname": {
                    "type": "string",
                    "description": "With use 'field': the field that holds the IDs.",
                },
            },
            "required": ["session"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        session_name = arguments.get("session")
        use = arguments.get("use")
        try:
            try:
                session = load_session(session_name)
            except frappe.DoesNotExistError:
                return {"success": False, "error": _("Import session '{0}' not found.").format(session_name)}
            except frappe.PermissionError as e:
                return permission_error_result(SESSION_DOCTYPE, exception_message(e), name=session_name)
            if not session.target_doctype:
                return {"success": False, "error": _("Map the columns first, with set_column_mapping.")}

            try:
                if use == "field":
                    fieldname = arguments.get("fieldname")
                    if not fieldname:
                        return {"success": False, "error": _("Pass the fieldname that holds the IDs.")}
                    result = import_key_setup.use_field(session, fieldname)
                elif use == "key_map":
                    result = import_key_setup.use_key_map(session)
                elif use:
                    return {"success": False, "error": _("use must be 'field' or 'key_map'.")}
                else:
                    result = import_key_setup.report(session)
            except import_key_setup.StorageProblem as e:
                return {"success": False, "error": str(e), "session": session_name}
            return {"success": True, "session": session_name, **result}
        except Exception as e:
            frappe.log_error(title=_("Choose Old ID Storage Error"), message=f"{e!s}")
            return {"success": False, "error": str(e)}


# Make sure class name matches file name for discovery
choose_old_id_storage = ChooseOldIdStorage
