# Frappe Assistant Core - files attached in a chat conversation
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""A file attached to one message stays visible to the model for the rest of the conversation.

The model read a receipt on the turn it was attached, but the extracted text rode on a one-turn
system prompt addendum and it was never told which File doc the receipt was. Asked two turns
later to attach the receipt to a Purchase Invoice, it searched the File list and attached some
other file.
"""

import base64
import inspect
from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api.chat import conversation_files, live_turn, messages
from frappe_assistant_core.chat.api.chat.conversation_files import conversation_files_addendum
from frappe_assistant_core.chat.api.chat.helpers import _attach_files_to_message
from frappe_assistant_core.chat.api.chat.relay import _relay_ar_interrupt_resume, _relay_ar_stream
from frappe_assistant_core.chat.api.settings.uploads import upload_message_file
from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import FACChatMessage
from frappe_assistant_core.tests.base_test import BaseAssistantTest


def _unique(body: str) -> str:
    # Frappe content-addresses uploads: identical bytes share one file_url across tests.
    return f"{body}\n{frappe.generate_hash(length=8)}"


class ConversationFilesTestCase(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # The rollback runs per class, so each test gets a conversation of its own.
        self.session = f"conversation-files-{frappe.generate_hash(length=8)}"
        self.addCleanup(live_turn.clear, self.session)

    def _upload(self, file_name: str, body: str | bytes, content_type: str = "text/plain") -> dict:
        data = body if isinstance(body, bytes) else body.encode()
        with patch(
            "frappe_assistant_core.chat.api.settings.access.can_use_faco",
            return_value={"can_use": True},
        ):
            uploaded = upload_message_file(
                file_data=base64.b64encode(data).decode(),
                file_name=file_name,
                content_type=content_type,
            )
        self.addCleanup(frappe.cache.delete_value, f"fac_chat_file_text:{uploaded['file']['name']}")
        return uploaded["file"]

    def _user_message(
        self, text: str, attach: tuple[str, str] | None = None, session: str | None = None
    ) -> str:
        """A user turn as send_message persists it, with a file uploaded and linked the same way."""
        msg = FACChatMessage.create_message(session_id=session or self.session, role="user", content=text)
        if attach:
            file_name, body = attach
            self.file = self._upload(file_name, body)
            _attach_files_to_message([self.file["file_url"]], msg.name)
        return msg.name

    def _relayed(self, endpoint, relay, **kwargs):
        with patch.object(messages._relay_pool, "submit") as submit, patch(
            "frappe_assistant_core.chat.api.settings.can_use_faco", return_value={"can_use": True}
        ), patch.object(messages, "_is_processing_restricted", return_value=False):
            endpoint(session_id=self.session, **kwargs)
        bound = inspect.signature(relay).bind(*submit.call_args[0][1:], **submit.call_args[1])
        return bound.arguments.get("system_prompt_addendum") or ""


class TestFilesStayInTheConversation(ConversationFilesTestCase):
    def setUp(self):
        super().setUp()
        self._user_message(
            "Can you summarize this receipt?", attach=("receipt.txt", _unique("Invoice ZX-4417"))
        )

    def test_a_later_turn_still_sees_the_receipt_and_its_file_id(self):
        addendum = self._relayed(
            messages.send_message, _relay_ar_stream, message="Attach this receipt to PINV-26-00050"
        )

        self.assertIn(f"File: {self.file['file_name']}", addendum)
        self.assertIn(f"File ID: {self.file['name']}", addendum)
        self.assertIn(f"File URL: {self.file['file_url']}", addendum)
        self.assertIn("ZX-4417", addendum)

    def test_the_turn_resumed_after_an_approval_still_sees_the_receipt(self):
        # AR rebuilds the system prompt on a resume; an approval is how the attach turn runs.
        addendum = self._relayed(
            messages.resume_interrupt,
            _relay_ar_interrupt_resume,
            interrupt_response='[{"interruptId": "int1", "response": "approve"}]',
            message_id="m-paused",
        )

        self.assertIn(f"File ID: {self.file['name']}", addendum)

    def test_a_continued_answer_still_sees_the_receipt(self):
        addendum = self._relayed(messages.continue_response, _relay_ar_stream, message_id="m-cut")

        self.assertIn(f"File ID: {self.file['name']}", addendum)

    def test_the_file_text_is_extracted_once_for_the_whole_conversation(self):
        with patch.object(conversation_files, "_extract", wraps=conversation_files._extract) as extract:
            conversation_files_addendum(self.session, frappe.session.user)
            conversation_files_addendum(self.session, frappe.session.user)

        self.assertEqual(extract.call_count, 1)


class TestConversationFilesScope(ConversationFilesTestCase):
    def test_no_files_means_no_section(self):
        self._user_message("hello")

        self.assertEqual(conversation_files_addendum(self.session, frappe.session.user), "")

    def test_another_user_never_sees_the_conversations_files(self):
        self._user_message("Summarize", attach=("mine.txt", _unique("private numbers")))

        self.assertEqual(conversation_files_addendum(self.session, "someone.else@example.com"), "")

    def test_a_large_file_is_truncated_and_still_listed(self):
        self._user_message("Read this", attach=("big.txt", _unique("x" * 500)))

        with patch.object(conversation_files, "MAX_FILE_CHARS", 100):
            addendum = conversation_files_addendum(self.session, frappe.session.user)

        self.assertIn(f"File ID: {self.file['name']}", addendum)
        self.assertIn("[Truncated", addendum)
        self.assertNotIn("x" * 101, addendum)


class TestTheSameFileInTwoConversations(ConversationFilesTestCase):
    def test_sending_it_again_leaves_the_first_conversation_its_copy(self):
        # Re-sending a receipt is common, and identical bytes get the same file_url.
        body = _unique("Receipt ST-88231")
        first_message = self._user_message("Summarize this", attach=("receipt.txt", body))
        first_file = self.file["name"]
        other_session = f"conversation-files-{frappe.generate_hash(length=8)}"
        second_message = self._user_message(
            "And this one", attach=("receipt.txt", body), session=other_session
        )

        self.assertEqual(frappe.db.get_value("File", first_file, "attached_to_name"), first_message)
        self.assertEqual(
            frappe.get_all(
                "File",
                filters={"attached_to_doctype": "FAC Chat Message", "attached_to_name": second_message},
                pluck="name",
            ),
            [self.file["name"]],
        )
        self.assertIn(
            f"File ID: {first_file}", conversation_files_addendum(self.session, frappe.session.user)
        )


class TestFilesWithoutText(ConversationFilesTestCase):
    def test_an_image_with_no_text_says_the_model_has_already_seen_it(self):
        # A site without the OCR dependencies extracts nothing from an image.
        msg = FACChatMessage.create_message(session_id=self.session, role="user", content="What is this?")
        png = b"\x89PNG\r\n\x1a\n" + frappe.generate_hash(length=32).encode()
        self.file = self._upload("photo.png", png, content_type="image/png")
        _attach_files_to_message([self.file["file_url"]], msg.name)

        with patch.object(conversation_files, "_extract", return_value=""):
            addendum = conversation_files_addendum(self.session, frappe.session.user)

        self.assertIn(f"File ID: {self.file['name']}", addendum)
        self.assertIn("Content: an image, shown to you", addendum)
