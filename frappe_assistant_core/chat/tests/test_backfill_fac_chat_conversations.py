# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""The backfill reproduces what the sidebar used to compute from messages, and is idempotent."""

import frappe

from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import FACChatMessage
from frappe_assistant_core.patches.v3_2.backfill_fac_chat_conversations import backfill
from frappe_assistant_core.tests.base_test import BaseAssistantTest

ACTIVE, ARCHIVED = "test-backfill-active", "test-backfill-archived"


class TestBackfillConversations(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; runs in an isolated transaction
        frappe.set_user("Administrator")
        for sid in (ACTIVE, ARCHIVED):
            frappe.db.delete("FAC Chat Message", {"session_id": sid})
        FACChatMessage.create_message(ACTIVE, "user", "First active question")
        FACChatMessage.create_message(ACTIVE, "assistant", "answer")
        FACChatMessage.create_message(ARCHIVED, "user", "Old question")
        frappe.db.set_value("FAC Chat Message", {"session_id": ARCHIVED}, "is_archived", 1)
        # Sites upgrading from 3.1 have messages but no conversation rows; production
        # reaches this state by every message written before this release.
        frappe.db.delete("FAC Chat Conversation", {"name": ["in", [ACTIVE, ARCHIVED]]})

    def test_backfill_builds_rows_from_messages(self):
        backfill(batch_size=1)  # 1 forces the batching loop through several pages
        active = frappe.get_doc("FAC Chat Conversation", ACTIVE)
        self.assertEqual(active.title, "First active question")
        self.assertEqual(active.message_count, 2)
        self.assertEqual(active.is_archived, 0)
        self.assertEqual(frappe.db.get_value("FAC Chat Conversation", ARCHIVED, "is_archived"), 1)

    def test_backfill_is_idempotent(self):
        backfill()
        self.assertEqual(backfill(), 0)
