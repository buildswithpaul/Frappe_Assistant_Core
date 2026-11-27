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
Get DocType Info Tool for Core Plugin.
Get DocType metadata and field information.
"""

from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool

#: What a successful call returns. Loose on purpose: see BaseTool.outputSchema.
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "doctype": {"type": "string"},
        "is_submittable": {"type": "boolean"},
        "fields": {
            "type": "array",
            "items": {"type": "object"},
            "description": "With doctype: each field's fieldname, label, fieldtype and options (a Link's target DocType, a Table's child DocType); reqd, read_only and hidden only when set.",
        },
        "child_tables": {
            "type": "array",
            "items": {"type": "object"},
            "description": "With doctype: each child table's fieldname, options (the child DocType) and fields.",
        },
        "doctypes": {
            "type": "array",
            "items": {"type": "object"},
            "description": "With topic: the DocTypes about it.",
        },
    },
}


class GetDoctypeInfo(BaseTool):
    """
    Tool for getting DocType metadata and field information.

    Provides capabilities for:
    - DocType metadata retrieval
    - Field information and structure
    - Permission and workflow details
    """

    def __init__(self):
        super().__init__()
        self.name = "get_doctype_info"
        self.outputSchema = OUTPUT_SCHEMA
        self.description = (
            "Get DocType metadata and field information. Pass doctype for its fields, or topic to "
            "find where data lives when no report fits. A field lists only what is set: no reqd, "
            "read_only or hidden means it is off."
        )
        self.requires_permission = None  # Permission checked dynamically per DocType

        self.inputSchema = {
            "type": "object",
            "properties": {
                "doctype": {"type": "string", "description": "DocType name"},
                "topic": {
                    "type": "string",
                    "description": (
                        "Where does this data live? A subject such as 'bookings' or 'complaints': "
                        "returns the DocTypes about it, whether they hold data, and their date, "
                        "amount and party fields. Use when no report fits, instead of exploring. "
                        "Ignored when doctype is given."
                    ),
                },
            },
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute DocType info retrieval"""
        try:
            # Import the metadata implementation
            from .metadata_tools import MetadataTools, compact_doctype_metadata

            if arguments.get("doctype"):
                return compact_doctype_metadata(
                    MetadataTools.get_doctype_metadata(doctype=arguments["doctype"])
                )
            if arguments.get("topic"):
                return MetadataTools.find_doctypes_for_topic(topic=arguments["topic"])
            return {"success": False, "error": _("Provide either a doctype or a topic")}

        except Exception as e:
            frappe.log_error(
                title=_("Get DocType Info Error"), message=f"Error getting DocType info: {str(e)}"
            )

            return {"success": False, "error": str(e)}


# Make sure class name matches file name for discovery
get_doctype_info = GetDoctypeInfo
