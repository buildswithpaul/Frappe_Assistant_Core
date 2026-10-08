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
Attach Chat File Tool — attaches a file the user uploaded in FAC Chat to a document.

Asked to "attach this receipt to the Purchase Invoice", the model used to search the File list
and re-point some File's attachment fields with update_document, which moved an unrelated file
off whatever it was attached to. This tool takes the File ID the conversation lists, accepts only
a file the user themselves sent in chat, and attaches a new File doc to the target the way Desk's
"attach from library" does, so the chat keeps its own copy.
"""

from typing import Any

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool

CHAT_MESSAGE_DOCTYPE = "FAC Chat Message"


class AttachChatFile(BaseTool):
    """MCP tool that attaches a chat upload to a Frappe document."""

    def __init__(self):
        super().__init__()
        self.name = "attach_chat_file"
        self.description = (
            "Attach a file the user uploaded in this chat to a document, e.g. a receipt to a "
            "Purchase Invoice. Pass the File ID from the conversation's attached-files list. "
            "The document gets its own copy and the chat keeps the original. Use this instead "
            "of create_document or update_document on File."
        )
        self.source_app = "frappe_assistant_core"
        self.category = "Document"
        self.requires_permission = None

        self.inputSchema = {
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "string",
                    "description": "File ID of the chat upload, as listed in the conversation",
                },
                "doctype": {"type": "string", "description": "DocType to attach to, e.g. Purchase Invoice"},
                "name": {"type": "string", "description": "Document name, e.g. PINV-26-00050"},
            },
            "required": ["file_id", "doctype", "name"],
        }

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        file_id = (arguments.get("file_id") or "").strip()
        doctype = (arguments.get("doctype") or "").strip()
        docname = (arguments.get("name") or "").strip()

        source = self._chat_upload(file_id)
        if not source:
            return {
                "success": False,
                "error": _("No file with File ID {0} was attached by you in this chat.").format(file_id),
            }

        if not frappe.db.exists("DocType", doctype) or not frappe.db.exists(doctype, docname):
            return {"success": False, "error": _("{0} {1} does not exist.").format(doctype, docname)}

        # The same check Desk applies before attaching a library file to a document.
        if not frappe.get_doc(doctype, docname).has_permission("write"):
            return {
                "success": False,
                "error": _("You do not have permission to attach files to {0} {1}.").format(doctype, docname),
            }

        existing = frappe.db.get_value(
            "File",
            {"attached_to_doctype": doctype, "attached_to_name": docname, "file_url": source.file_url},
            "name",
        )
        if existing:
            return self._result(existing, source, doctype, docname, already_attached=True)

        attached = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": source.file_name,
                "file_url": source.file_url,
                "is_private": source.is_private,
                "attached_to_doctype": doctype,
                "attached_to_name": docname,
            }
        ).insert()
        return self._result(attached.name, source, doctype, docname)

    @staticmethod
    def _chat_upload(file_id: str):
        """The File, if it is one the session user sent with a chat message, else None."""
        if not file_id:
            return None
        source = frappe.db.get_value(
            "File",
            file_id,
            ["name", "file_name", "file_url", "is_private", "owner", "attached_to_doctype"],
            as_dict=True,
        )
        if (
            not source
            or source.attached_to_doctype != CHAT_MESSAGE_DOCTYPE
            or source.owner != frappe.session.user
        ):
            return None
        return source

    @staticmethod
    def _result(file_name, source, doctype, docname, already_attached=False):
        message = (
            _("{0} was already attached to {1} {2}.") if already_attached else _("Attached {0} to {1} {2}.")
        )
        return {
            "success": True,
            "message": message.format(source.file_name, doctype, docname),
            "file_id": file_name,
            "file_url": source.file_url,
            "attached_to": {"doctype": doctype, "name": docname},
            "already_attached": already_attached,
        }
