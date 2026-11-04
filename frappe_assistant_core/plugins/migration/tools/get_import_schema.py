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
Get Import Schema Tool for Core Plugin.
The short list of fields an import can fill on a DocType, for mapping a migration file.
"""

from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool
from frappe_assistant_core.utils.import_mapping import build_import_schema
from frappe_assistant_core.utils.import_session import import_target_problem


class GetImportSchema(BaseTool):
    """
    Tool for listing the importable fields of a DocType.

    get_doctype_info returns a DocType's entire metadata (Delivery Note: about 157,000
    characters), which is cut off before the model reads most of it. This returns only
    what a column can map to.
    """

    def __init__(self):
        super().__init__()
        self.name = "get_import_schema"
        self.description = (
            "List the fields a data import can fill on a DocType: fieldname, label, type, required "
            "flag, Select options or Link target, and each child table with its own fields. Use it "
            "when mapping a user's migration file (an uploaded spreadsheet) to ERPNext, instead of "
            "get_doctype_info, whose full metadata is too long to read. Fails up front, with the "
            "reason, when the user can't import into the DocType. Then save the mapping with "
            "set_column_mapping."
        )
        self.requires_permission = None  # Checked per DocType

        self.inputSchema = {
            "type": "object",
            "properties": {
                "doctype": {
                    "type": "string",
                    "description": "The DocType the file's rows become, e.g. 'Customer' or 'Item'",
                }
            },
            "required": ["doctype"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        try:
            doctype = arguments.get("doctype")
            # Refuse before any work when the user could never import into it.
            problem = import_target_problem(doctype)
            if problem:
                return {"success": False, "error": problem, "doctype": doctype}
            return {"success": True, **build_import_schema(doctype)}

        except Exception as e:
            frappe.log_error(
                title=_("Get Import Schema Error"), message=f"Error building import schema: {e!s}"
            )
            return {"success": False, "error": str(e)}


# Make sure class name matches file name for discovery
get_import_schema = GetImportSchema
