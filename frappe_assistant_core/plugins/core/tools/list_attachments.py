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
List Attachments Tool for Core Plugin.
Lists the files attached to an existing Frappe document.
"""

from typing import Any, Dict

import frappe

from frappe_assistant_core.core.base_tool import BaseTool


class ListAttachments(BaseTool):
    """
    Tool for listing files attached to an existing Frappe document.

    Returns each attachment's File record name, file name, URL, visibility,
    size, and metadata. Read permission on the target document is required.
    """

    def __init__(self):
        super().__init__()
        self.name = "list_attachments"
        self.description = (
            "List the files attached to an existing Frappe/ERPNext document. Provide the "
            "target 'doctype' and 'name'; returns each attachment's File record name "
            "(usable with remove_attachment), file_name, file_url, is_private, file_size, "
            "and creation metadata. The current user must have read permission on the "
            "target document."
        )
        self.requires_permission = None
        self.category = "read_only"

        self.inputSchema = {
            "type": "object",
            "properties": {
                "doctype": {
                    "type": "string",
                    "description": "The DocType whose attachments to list "
                    "(e.g. 'Sales Invoice', 'Purchase Order').",
                },
                "name": {
                    "type": "string",
                    "description": "The exact name/ID of the target document.",
                },
            },
            "required": ["doctype", "name"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """List attachments of a document."""
        doctype = arguments.get("doctype")
        name = arguments.get("name")

        if not frappe.db.exists(doctype, name):
            return {
                "success": False,
                "error": f"Target document not found: {doctype} '{name}'.",
                "error_type": "document_not_found",
                "doctype": doctype,
                "name": name,
            }

        # Read permission on the target document is the security boundary for
        # its attachments (File visibility follows the attached_to document).
        from frappe_assistant_core.core.security_config import validate_document_access

        validation_result = validate_document_access(
            user=frappe.session.user,
            doctype=doctype,
            name=name,
            perm_type="read",
        )
        if not validation_result["success"]:
            return validation_result

        # Scoped to a single parent the caller can read; this is the correct
        # access gate for attachments, so a direct File query is appropriate.
        files = frappe.get_all(
            "File",
            filters={
                "attached_to_doctype": doctype,
                "attached_to_name": name,
            },
            fields=[
                "name",
                "file_name",
                "file_url",
                "is_private",
                "file_size",
                "file_type",
                "creation",
                "owner",
            ],
            order_by="creation asc",
        )

        for f in files:
            f["is_private"] = bool(f.get("is_private"))
            f["creation"] = str(f.get("creation"))

        return {
            "success": True,
            "doctype": doctype,
            "name": name,
            "count": len(files),
            "attachments": files,
        }


# Make sure class name matches file name for discovery
list_attachments = ListAttachments
