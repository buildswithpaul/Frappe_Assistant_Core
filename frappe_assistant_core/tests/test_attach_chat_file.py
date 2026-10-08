# Frappe Assistant Core - attach_chat_file tool tests
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""attach_chat_file attaches a chat upload to a document, and nothing else.

Asked to attach a receipt the user had sent in chat to a Purchase Invoice, the model searched
the File list and re-pointed an unrelated File with update_document. The tool takes the File ID
the conversation lists, refuses any File the user did not send in chat, and leaves the chat's
copy where it is.
"""

import base64
from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api.chat.helpers import _attach_files_to_message
from frappe_assistant_core.chat.api.settings.uploads import upload_message_file
from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import FACChatMessage
from frappe_assistant_core.plugins.faco.tools.attach_chat_file import AttachChatFile
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestAttachChatFile(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.note = self._note()

    def _note(self) -> str:
        return (
            frappe.get_doc({"doctype": "Note", "title": f"Expenses {frappe.generate_hash(length=6)}"})
            .insert(ignore_permissions=True)
            .name
        )

    def _chat_upload(self, file_name: str = "receipt.txt") -> dict:
        """A file as the session user sends it in chat: uploaded, then linked to their message."""
        session_id = f"attach-chat-file-{frappe.generate_hash(length=8)}"
        msg = FACChatMessage.create_message(session_id=session_id, role="user", content="Here is the receipt")
        # Unique bytes: Frappe content-addresses uploads, so identical bodies would share a File.
        body = f"Receipt {frappe.generate_hash(length=12)}".encode()
        with patch(
            "frappe_assistant_core.chat.api.settings.access.can_use_faco",
            return_value={"can_use": True},
        ):
            uploaded = upload_message_file(
                file_data=base64.b64encode(body).decode(), file_name=file_name, content_type="text/plain"
            )
        _attach_files_to_message([uploaded["file"]["file_url"]], msg.name)
        return uploaded["file"]

    def _attach(self, file_id: str, name: str | None = None) -> dict:
        return AttachChatFile().execute({"file_id": file_id, "doctype": "Note", "name": name or self.note})

    def _files_on(self, name: str) -> list:
        return frappe.get_all(
            "File", filters={"attached_to_doctype": "Note", "attached_to_name": name}, pluck="file_url"
        )

    def test_attaches_a_copy_and_the_chat_keeps_its_own(self):
        upload = self._chat_upload()

        result = self._attach(upload["name"])

        self.assertTrue(result["success"], result)
        self.assertEqual(self._files_on(self.note), [upload["file_url"]])
        self.assertNotEqual(result["file_id"], upload["name"])
        self.assertEqual(
            frappe.db.get_value("File", upload["name"], "attached_to_doctype"), "FAC Chat Message"
        )

    def test_attaching_the_same_file_twice_does_not_duplicate_it(self):
        upload = self._chat_upload()

        self._attach(upload["name"])
        again = self._attach(upload["name"])

        self.assertTrue(again["already_attached"])
        self.assertEqual(len(self._files_on(self.note)), 1)

    def test_refuses_a_file_that_was_not_sent_in_chat(self):
        # What the model reached for: an arbitrary File already attached to some other record.
        other_note = self._note()
        unrelated = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": "unrelated.txt",
                "content": f"Unrelated {frappe.generate_hash(length=12)}".encode(),
                "is_private": 1,
                "attached_to_doctype": "Note",
                "attached_to_name": other_note,
            }
        ).insert(ignore_permissions=True)

        result = self._attach(unrelated.name)

        self.assertFalse(result["success"])
        self.assertEqual(self._files_on(self.note), [])
        self.assertEqual(frappe.db.get_value("File", unrelated.name, "attached_to_name"), other_note)

    def test_refuses_another_users_chat_upload(self):
        other = self.make_throwaway_user("chat-uploader")
        frappe.set_user(other)  # nosemgrep: frappe-setuser — act as the other chat user
        upload = self._chat_upload()
        frappe.set_user("Administrator")  # nosemgrep: frappe-setuser

        result = self._attach(upload["name"])

        self.assertFalse(result["success"])
        self.assertEqual(self._files_on(self.note), [])

    def test_refuses_a_document_the_user_cannot_write(self):
        # A user with no roles has no write access to a Note that someone else owns.
        reader = self.make_throwaway_user("no-write")
        frappe.set_user(reader)  # nosemgrep: frappe-setuser — act as the chat user
        upload = self._chat_upload()

        result = self._attach(upload["name"])
        frappe.set_user("Administrator")  # nosemgrep: frappe-setuser

        self.assertFalse(result["success"])
        self.assertIn("permission", result["error"])
        self.assertEqual(self._files_on(self.note), [])

    def test_refuses_a_document_that_does_not_exist(self):
        upload = self._chat_upload()

        result = self._attach(upload["name"], name="NOTE-DOES-NOT-EXIST")

        self.assertFalse(result["success"])
