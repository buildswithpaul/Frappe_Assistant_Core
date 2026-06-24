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
Remove Attachment Tool for Core Plugin.
Removes a file attached to an existing Frappe document.

This tool only removes files that are attachments (i.e. have an
attached_to_doctype/attached_to_name). It will not delete standalone File
records, and it enforces write permission on the parent document.
"""

from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool


class RemoveAttachment(BaseTool):
    """
    Tool for removing a file attached to an existing Frappe document.

    The attachment can be identified either by its File record name ('file'),
    or by the target document plus a file_url or file_name. Write permission
    on the parent document is required. Standalone (non-attachment) File
    records are never deleted by this tool.
    """

    def __init__(self):
        super().__init__()
        self.name = "remove_attachment"
        self.description = (
            "Remove (delete) a file attached to an existing Frappe/ERPNext document. "
            "Identify the attachment EITHER by 'file' (the File record name, e.g. from "
            "list_attachments) OR by 'doctype' + 'name' plus one of 'file_url' or "
            "'file_name' to locate it. If more than one attachment matches, the call "
            "returns the candidates so you can retry with a specific 'file'. The current "
            "user must have write permission on the parent document. This tool only "
            "removes files that are attachments; it will not delete standalone files. "
            "This action is irreversible."
        )
        self.requires_permission = None
        self.category = "privileged"

        self.inputSchema = {
            "type": "object",
            "properties": {
                "file": {
                    "type": "string",
                    "description": "The File record name (ID) of the attachment to remove, "
                    "e.g. as returned by list_attachments or attach_file_to_document. The "
                    "most precise way to target an attachment.",
                },
                "doctype": {
                    "type": "string",
                    "description": "The parent DocType (used with 'name' to locate the "
                    "attachment when 'file' is not given).",
                },
                "name": {
                    "type": "string",
                    "description": "The parent document name/ID (used with 'doctype').",
                },
                "file_url": {
                    "type": "string",
                    "description": "The file_url of the attachment to remove (used with "
                    "'doctype' and 'name').",
                },
                "file_name": {
                    "type": "string",
                    "description": "The file_name of the attachment to remove (used with "
                    "'doctype' and 'name'). Less precise than file_url if duplicates exist.",
                },
            },
            "required": [],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Remove an attachment from a document."""
        file_id = arguments.get("file")
        doctype = arguments.get("doctype")
        name = arguments.get("name")
        file_url = arguments.get("file_url")
        file_name = arguments.get("file_name")

        # --- Resolve the File record to remove -------------------------------
        if file_id:
            if not frappe.db.exists("File", file_id):
                return {
                    "success": False,
                    "error": f"File record not found: '{file_id}'.",
                    "error_type": "file_not_found",
                }
            target_file = file_id
        else:
            if not (doctype and name and (file_url or file_name)):
                return {
                    "success": False,
                    "error": "Provide either 'file' (File record name), or 'doctype' and "
                    "'name' together with 'file_url' or 'file_name'.",
                    "error_type": "insufficient_identifiers",
                }
            if not frappe.db.exists(doctype, name):
                return {
                    "success": False,
                    "error": f"Target document not found: {doctype} '{name}'.",
                    "error_type": "document_not_found",
                    "doctype": doctype,
                    "name": name,
                }

            filters = {
                "attached_to_doctype": doctype,
                "attached_to_name": name,
            }
            if file_url:
                filters["file_url"] = file_url
            if file_name:
                filters["file_name"] = file_name

            matches = frappe.get_all(
                "File",
                filters=filters,
                fields=["name", "file_name", "file_url", "is_private"],
            )
            if len(matches) == 0:
                return {
                    "success": False,
                    "error": "No matching attachment found on " f"{doctype} '{name}'.",
                    "error_type": "attachment_not_found",
                }
            if len(matches) > 1:
                return {
                    "success": False,
                    "error": f"{len(matches)} attachments match. Retry with a specific "
                    "'file' from the candidates.",
                    "error_type": "ambiguous_attachment",
                    "candidates": matches,
                }
            target_file = matches[0]["name"]

        # --- Confirm it is an attachment and find its parent -----------------
        file_doc = frappe.get_doc("File", target_file)
        if not (file_doc.attached_to_doctype and file_doc.attached_to_name):
            return {
                "success": False,
                "error": "This File is not attached to any document. remove_attachment "
                "only removes attachments and will not delete standalone files.",
                "error_type": "not_an_attachment",
                "file": target_file,
            }

        # Guard against mismatched identifiers when both were supplied.
        if doctype and file_doc.attached_to_doctype != doctype:
            return {
                "success": False,
                "error": f"Attachment is linked to {file_doc.attached_to_doctype}, not " f"{doctype}.",
                "error_type": "parent_mismatch",
            }
        if name and file_doc.attached_to_name != name:
            return {
                "success": False,
                "error": f"Attachment is linked to '{file_doc.attached_to_name}', not " f"'{name}'.",
                "error_type": "parent_mismatch",
            }

        parent_doctype = file_doc.attached_to_doctype
        parent_name = file_doc.attached_to_name

        # --- Write permission on the parent document -------------------------
        from frappe_assistant_core.core.security_config import validate_document_access

        validation_result = validate_document_access(
            user=frappe.session.user,
            doctype=parent_doctype,
            name=parent_name,
            perm_type="write",
        )
        if not validation_result["success"]:
            return validation_result

        removed = {
            "file": file_doc.name,
            "file_name": file_doc.file_name,
            "file_url": file_doc.file_url,
            "attached_to_doctype": parent_doctype,
            "attached_to_name": parent_name,
        }

        # --- Delete (respects permissions; File on_trash unlinks the bytes) --
        try:
            frappe.delete_doc("File", file_doc.name)
            return {
                "success": True,
                "message": f"Attachment '{removed['file_name']}' removed from "
                f"{parent_doctype} '{parent_name}'.",
                "removed": removed,
            }
        except frappe.PermissionError as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": "permission_error",
            }
        except Exception as e:
            frappe.log_error(
                title=_("Remove Attachment Error"),
                message=f"Error removing File '{file_doc.name}' from {parent_doctype} "
                f"'{parent_name}': {str(e)}",
            )
            return {
                "success": False,
                "error": str(e),
                "error_type": "remove_failed",
            }


# Make sure class name matches file name for discovery
remove_attachment = RemoveAttachment
