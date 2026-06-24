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
Test suite for the attach_file_to_document tool.
Exercises registration, input validation, and a real attach round-trip
against a safe doctype (ToDo).
"""

import base64
import unittest

import frappe

from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.plugins.core.tools.attach_file_to_document import (
    AttachFileToDocument,
)
from frappe_assistant_core.plugins.core.tools.list_attachments import ListAttachments
from frappe_assistant_core.plugins.core.tools.remove_attachment import RemoveAttachment
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestAttachFileTool(BaseAssistantTest):
    """Test the attach_file_to_document tool through the registry and directly."""

    def setUp(self):
        super().setUp()
        # Other tests in the suite leak a MagicMock onto frappe.local.request,
        # which breaks File inserts on Frappe v16. Isolate this test class by
        # clearing the request for each test and restoring the original in
        # tearDown.
        self._original_request = getattr(frappe.local, "request", None)
        frappe.local.request = None
        self.registry = get_tool_registry()
        # A safe, always-present, attach-friendly doctype.
        self.todo = frappe.get_doc(
            {"doctype": "ToDo", "description": "attach_file_to_document test target"}
        ).insert()
        self._created_files = []

    def tearDown(self):
        for file_name in self._created_files:
            try:
                frappe.delete_doc("File", file_name, force=True, ignore_permissions=True)
            except Exception:
                pass
        try:
            frappe.delete_doc("ToDo", self.todo.name, force=True, ignore_permissions=True)
        except Exception:
            pass
        super().tearDown()
        # Restore whatever request the suite had before this test ran.
        frappe.local.request = self._original_request

    def test_tool_is_registered(self):
        """The tool should be discoverable through the registry."""
        tools = self.registry.get_available_tools()
        tool_names = [tool["name"] for tool in tools]
        self.assertIn("attach_file_to_document", tool_names)

    def test_requires_a_content_source(self):
        """Omitting every content source returns a structured error."""
        result = AttachFileToDocument().execute(
            {"doctype": "ToDo", "name": self.todo.name, "file_name": "x.txt"}
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "missing_content_source")

    def test_rejects_multiple_content_sources(self):
        """Supplying more than one content source returns a structured error."""
        result = AttachFileToDocument().execute(
            {
                "doctype": "ToDo",
                "name": self.todo.name,
                "file_name": "x.txt",
                "content_base64": base64.b64encode(b"hi").decode(),
                "file_url": "/private/files/x.txt",
            }
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "ambiguous_content_source")

    def test_missing_target_document(self):
        """A non-existent target document is reported clearly."""
        result = AttachFileToDocument().execute(
            {
                "doctype": "ToDo",
                "name": "TODO-DOES-NOT-EXIST-999999",
                "file_name": "x.txt",
                "content_base64": base64.b64encode(b"hi").decode(),
            }
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "document_not_found")

    def test_invalid_base64(self):
        """Malformed base64 content is rejected before any File is created."""
        result = AttachFileToDocument().execute(
            {
                "doctype": "ToDo",
                "name": self.todo.name,
                "file_name": "x.txt",
                "content_base64": "not-valid-base64!!!",
            }
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "invalid_base64")

    def test_attach_base64_content_roundtrip(self):
        """Inline base64 content is attached and linked to the target document."""
        payload = b"Stergy attach test content"
        result = AttachFileToDocument().execute(
            {
                "doctype": "ToDo",
                "name": self.todo.name,
                "file_name": "stergy_attach_test.txt",
                "content_base64": base64.b64encode(payload).decode(),
                "is_private": True,
            }
        )
        self.assertTrue(result["success"], msg=result)
        self.assertIn("file", result)
        self._created_files.append(result["file"])

        file_doc = frappe.get_doc("File", result["file"])
        self.assertEqual(file_doc.attached_to_doctype, "ToDo")
        self.assertEqual(file_doc.attached_to_name, self.todo.name)
        self.assertEqual(int(file_doc.is_private), 1)

    # --- helpers ---------------------------------------------------------

    def _attach(self, file_name, payload=b"data"):
        """Attach a file to the test ToDo and track it for cleanup."""
        result = AttachFileToDocument().execute(
            {
                "doctype": "ToDo",
                "name": self.todo.name,
                "file_name": file_name,
                "content_base64": base64.b64encode(payload).decode(),
            }
        )
        self.assertTrue(result["success"], msg=result)
        self._created_files.append(result["file"])
        return result["file"]

    # --- list_attachments ------------------------------------------------

    def test_list_attachments_registered(self):
        tool_names = [t["name"] for t in self.registry.get_available_tools()]
        self.assertIn("list_attachments", tool_names)

    def test_list_attachments_returns_attached_file(self):
        self._attach("listme.txt")
        result = ListAttachments().execute({"doctype": "ToDo", "name": self.todo.name})
        self.assertTrue(result["success"], msg=result)
        self.assertGreaterEqual(result["count"], 1)
        names = [a["file_name"] for a in result["attachments"]]
        self.assertIn("listme.txt", names)

    def test_list_attachments_missing_document(self):
        result = ListAttachments().execute({"doctype": "ToDo", "name": "TODO-DOES-NOT-EXIST-999999"})
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "document_not_found")

    # --- remove_attachment -----------------------------------------------

    def test_remove_attachment_registered(self):
        tool_names = [t["name"] for t in self.registry.get_available_tools()]
        self.assertIn("remove_attachment", tool_names)

    def test_remove_attachment_by_file_id(self):
        file_id = self._attach("removeme.txt")
        result = RemoveAttachment().execute({"file": file_id})
        self.assertTrue(result["success"], msg=result)
        self.assertFalse(frappe.db.exists("File", file_id))
        # already gone; drop from cleanup list
        self._created_files.remove(file_id)

    def test_remove_attachment_by_parent_and_name(self):
        self._attach("byname.txt")
        result = RemoveAttachment().execute(
            {"doctype": "ToDo", "name": self.todo.name, "file_name": "byname.txt"}
        )
        self.assertTrue(result["success"], msg=result)
        self.assertEqual(result["removed"]["file_name"], "byname.txt")

    def test_remove_attachment_insufficient_identifiers(self):
        result = RemoveAttachment().execute({"doctype": "ToDo"})
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "insufficient_identifiers")

    def test_remove_attachment_not_found(self):
        result = RemoveAttachment().execute({"file": "FILE-DOES-NOT-EXIST-999999"})
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "file_not_found")


if __name__ == "__main__":
    unittest.main()
