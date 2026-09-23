# Frappe Assistant Core - chat attachment flag lifecycle tests
# Copyright (C) 2025 Paul Clinton
#
# AGPL-3.0 License

"""Upload marks a file pending; sending clears it. Between those two points the
orphan sweep is what stops abandoned uploads accumulating, so both halves of the
handshake need to hold — and the send half must only ever touch the sender's own
files.
"""

import base64
from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api.chat.helpers import _attach_files_to_message
from frappe_assistant_core.chat.api.settings.uploads import upload_message_file
from frappe_assistant_core.tests.base_test import BaseAssistantTest

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64).decode()


class TestUploadMarksPending(BaseAssistantTest):
    def test_upload_flags_file_as_pending(self):
        with patch(
            "frappe_assistant_core.chat.api.settings.access.can_use_faco",
            return_value={"can_use": True},
        ):
            result = upload_message_file(file_data=PNG, file_name="shot.png", content_type="image/png")

        self.assertTrue(result["success"])
        self.assertEqual(
            frappe.db.get_value("File", result["file"]["name"], "fac_pending_chat_attachment"), 1
        )

    def test_upload_returns_vision_keys_the_clients_read(self):
        # The Desk widget builds its vision payload off `type` and `format`.
        # Renaming either without updating widget.js silently disables vision.
        with patch(
            "frappe_assistant_core.chat.api.settings.access.can_use_faco",
            return_value={"can_use": True},
        ):
            result = upload_message_file(file_data=PNG, file_name="shot.png", content_type="image/png")

        self.assertEqual(result["file"]["type"], "image")
        self.assertEqual(result["file"]["format"], "png")
        self.assertTrue(result["file"]["base64_data"])


class TestAttachFilesToMessage(BaseAssistantTest):
    def _pending_file(self, file_name: str, owner: str) -> str:
        # Content must be unique per file: Frappe content-addresses uploads, so
        # identical bytes collapse onto a single file_url and the lookup under
        # test would match every one of them.
        f = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": file_name,
                "content": b"\x89PNG\r\n\x1a\n" + frappe.generate_hash(length=32).encode(),
                "is_private": 1,
                "folder": "Home/Attachments",
                "fac_pending_chat_attachment": 1,
            }
        )
        f.insert(ignore_permissions=True)
        if owner != f.owner:
            frappe.db.set_value("File", f.name, "owner", owner, update_modified=False)
        return f.name

    def test_linking_clears_the_pending_flag(self):
        name = self._pending_file("mine.png", frappe.session.user)
        file_url = frappe.db.get_value("File", name, "file_url")

        linked = _attach_files_to_message([file_url], "FACMSG-TEST-0001")

        self.assertEqual(linked, 1)
        row = frappe.db.get_value(
            "File",
            name,
            ["attached_to_doctype", "attached_to_name", "fac_pending_chat_attachment"],
            as_dict=True,
        )
        self.assertEqual(row.attached_to_doctype, "FAC Chat Message")
        self.assertEqual(row.attached_to_name, "FACMSG-TEST-0001")
        self.assertEqual(row.fac_pending_chat_attachment, 0)

    def test_refuses_to_link_a_file_owned_by_someone_else(self):
        # get_all bypasses permissions, so the owner filter is the only gate.
        # Without it, naming any private file_url would pull that file's text
        # into the prompt via _extract_file_attachments.
        foreign = self._pending_file("theirs.png", "Guest")
        file_url = frappe.db.get_value("File", foreign, "file_url")

        linked = _attach_files_to_message([file_url], "FACMSG-TEST-0002")

        self.assertEqual(linked, 0)
        self.assertIsNone(frappe.db.get_value("File", foreign, "attached_to_name"))
        self.assertEqual(frappe.db.get_value("File", foreign, "fac_pending_chat_attachment"), 1)

    def test_links_own_files_while_skipping_foreign_ones(self):
        mine = self._pending_file("mine.png", frappe.session.user)
        theirs = self._pending_file("theirs.png", "Guest")
        urls = [
            frappe.db.get_value("File", mine, "file_url"),
            frappe.db.get_value("File", theirs, "file_url"),
        ]

        linked = _attach_files_to_message(urls, "FACMSG-TEST-0003")

        self.assertEqual(linked, 1)
        self.assertEqual(frappe.db.get_value("File", mine, "attached_to_name"), "FACMSG-TEST-0003")
        self.assertIsNone(frappe.db.get_value("File", theirs, "attached_to_name"))
