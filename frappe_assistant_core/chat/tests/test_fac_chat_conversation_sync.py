# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""FAC Chat Conversation rows follow the messages written through the production path."""

from unittest.mock import create_autospec, patch

import frappe
from assistant_runtime_sdk import AssistantRuntimeClient

from frappe_assistant_core.chat.doctype.fac_chat_conversation.fac_chat_conversation import auto_title
from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import FACChatMessage
from frappe_assistant_core.chat.doctype.fac_workflow_trigger.fac_workflow_trigger import DOCTYPE_BLOCKLIST
from frappe_assistant_core.chat.tests.test_chat_projects_api import OTHER_USER, ensure_user, make_project
from frappe_assistant_core.tests.base_test import BaseAssistantTest

SID = "test-conv-sync-1"


class TestConversationSync(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; runs in an isolated transaction
        frappe.set_user("Administrator")
        frappe.db.delete("FAC Chat Message", {"session_id": SID})
        frappe.db.delete("FAC Chat Conversation", {"name": SID})

    def _row(self):
        return frappe.db.get_value(
            "FAC Chat Conversation",
            SID,
            ["user", "title", "title_is_custom", "message_count", "is_archived", "project"],
            as_dict=True,
        )

    def test_first_user_message_creates_row_with_title(self):
        FACChatMessage.create_message(SID, "user", "  How many   overdue invoices?\n")
        row = self._row()
        self.assertEqual(row.user, "Administrator")
        self.assertEqual(row.title, "How many overdue invoices?")
        self.assertEqual(row.message_count, 1)

    def test_later_messages_bump_count_and_keep_title(self):
        FACChatMessage.create_message(SID, "user", "First question")
        FACChatMessage.create_message(SID, "assistant", "")  # streaming shell, as relay creates it
        FACChatMessage.create_message(SID, "user", "Second question")
        row = self._row()
        self.assertEqual(row.message_count, 3)
        self.assertEqual(row.title, "First question")

    def test_custom_title_survives_later_messages(self):
        FACChatMessage.create_message(SID, "user", "First question")
        # rename_session (Task 4) is the production writer of these two fields
        frappe.db.set_value("FAC Chat Conversation", SID, {"title": "Mine", "title_is_custom": 1})
        FACChatMessage.create_message(SID, "user", "Another")
        self.assertEqual(self._row().title, "Mine")

    def test_project_passed_on_first_message_is_kept(self):
        project = frappe.get_doc(
            {"doctype": "FAC Chat Project", "user": "Administrator", "title": "P"}
        ).insert(ignore_permissions=True)
        FACChatMessage.create_message(SID, "user", "Hi", project=project.name)
        self.assertEqual(self._row().project, project.name)
        self.assertIsNotNone(frappe.db.get_value("FAC Chat Project", project.name, "last_activity"))

    def test_archived_insert_creates_archived_row(self):
        # Archived history exists in production from before this table; tests and the
        # backfill both insert such rows directly, and they must not resurface in Recents.
        frappe.get_doc(
            {
                "doctype": "FAC Chat Message",
                "session_id": SID,
                "role": "user",
                "content": "old",
                "user": "Administrator",
                "is_archived": 1,
                "idx": 1,
            }
        ).insert(ignore_permissions=True)
        self.assertEqual(self._row().is_archived, 1)

    def test_archive_session_mirrors_onto_row(self):
        from frappe_assistant_core.chat.api.chat.sessions import archive_session

        FACChatMessage.create_message(SID, "user", "Hi")
        archive_session(SID)
        self.assertEqual(self._row().is_archived, 1)

    def test_live_message_unarchives_the_row(self):
        from frappe_assistant_core.chat.api.chat.sessions import archive_session

        FACChatMessage.create_message(SID, "user", "Hi")
        archive_session(SID)
        FACChatMessage.create_message(SID, "user", "Back again")
        self.assertEqual(self._row().is_archived, 0)

    def test_export_keeps_the_faco_block_when_ar_returns_empty_data(self):
        from frappe_assistant_core.chat.api.privacy import export_my_data

        make_project("Administrator", title="Kept")
        client = create_autospec(AssistantRuntimeClient, instance=True)
        client.export_user_data.return_value = {"status": "success", "data": {}}
        with patch("frappe_assistant_core.chat.api.privacy._get_client", return_value=client):
            faco = export_my_data()["data"]["faco"]
        self.assertIn("Kept", [p["title"] for p in faco["faco_projects"]])
        self.assertIn("faco_conversations", faco)

    def test_erase_my_data_deletes_conversations_and_projects(self):
        from frappe_assistant_core.chat.api.privacy import erase_my_data

        project = make_project("Administrator", title="Erase Me")
        FACChatMessage.create_message(SID, "user", "Hello", project=project)
        client = create_autospec(AssistantRuntimeClient, instance=True)
        with patch("frappe_assistant_core.chat.api.privacy._get_client", return_value=client), patch(
            "frappe.utils.password.check_password"
        ):
            erase_my_data(password="irrelevant")
        self.assertFalse(frappe.db.exists("FAC Chat Conversation", SID))
        self.assertFalse(frappe.db.exists("FAC Chat Project", project))

    def test_archive_all_mirrors_onto_rows(self):
        from frappe_assistant_core.chat.api.chat.sessions import archive_all_conversations

        FACChatMessage.create_message(SID, "user", "Hi")
        archive_all_conversations()
        self.assertEqual(self._row().is_archived, 1)

    def test_retention_purge_removes_orphan_rows(self):
        from frappe_assistant_core.chat.scheduler.retention import _purge_archived_messages

        FACChatMessage.create_message(SID, "user", "Hi")
        frappe.db.set_value("FAC Chat Message", {"session_id": SID}, "is_archived", 1)
        _purge_archived_messages(frappe.utils.add_days(frappe.utils.now(), 1), delete_attachments=False)
        self.assertFalse(frappe.db.exists("FAC Chat Conversation", SID))

    def test_export_includes_projects_and_conversations(self):
        from frappe_assistant_core.chat.api.privacy import export_my_data

        project = make_project("Administrator", title="Export Me", instructions="Be brief")
        FACChatMessage.create_message(SID, "user", "Hello export", project=project)

        # AR is a remote service; export_my_data asks it first, so stand in a client that
        # answers the way a reachable AR does (a non-empty data block, which is what the
        # merge keys on). The autospec keeps the method name honest.
        client = create_autospec(AssistantRuntimeClient, instance=True)
        client.export_user_data.return_value = {"status": "success", "data": {"profile": {}}}
        with patch("frappe_assistant_core.chat.api.privacy._get_client", return_value=client):
            faco = export_my_data()["data"]["faco"]

        self.assertIn(
            ("Export Me", "Be brief"), [(p["title"], p["instructions"]) for p in faco["faco_projects"]]
        )
        convo = next(c for c in faco["faco_conversations"] if c["session_id"] == SID)
        self.assertEqual(convo["title"], "Hello export")
        self.assertEqual(convo["project"], project)
        self.assertEqual(convo["is_archived"], 0)

    def test_another_users_message_does_not_touch_the_row(self):
        FACChatMessage.create_message(SID, "user", "First question")
        ensure_user(OTHER_USER)
        # A colliding session_id from another user is the case under guard; the relay
        # writes messages as the session user, so this is how it would arrive.
        # nosemgrep: frappe-setuser — test bootstrap; runs in an isolated transaction
        frappe.set_user(OTHER_USER)
        try:
            FACChatMessage.create_message(SID, "user", "Hijack")
        finally:
            # nosemgrep: frappe-setuser — restore the test user
            frappe.set_user("Administrator")
        row = self._row()
        self.assertEqual(row.message_count, 1)
        self.assertEqual(row.title, "First question")
        self.assertEqual(row.user, "Administrator")

    def test_lost_insert_race_does_not_touch_the_winners_row(self):
        from frappe_assistant_core.chat.doctype.fac_chat_conversation.fac_chat_conversation import (
            FACChatConversation,
        )

        ensure_user(OTHER_USER)
        frappe.get_doc(
            {
                "doctype": "FAC Chat Conversation",
                "session_id": SID,
                "user": OTHER_USER,
                "title": "",
                "message_count": 1,
            }
        ).insert(ignore_permissions=True)

        # Production reaches this when two inserts race on the same session_id: both
        # read "no row", the second insert hits the unique key. Hide the row from the
        # first read only, so the insert collides and the re-read sees the winner.
        real_get_value = frappe.db.get_value
        calls = []

        def first_read_misses(*args, **kwargs):
            calls.append(args)
            return None if len(calls) == 1 else real_get_value(*args, **kwargs)

        with patch.object(frappe.db, "get_value", side_effect=first_read_misses):
            FACChatConversation.touch(SID, "Administrator", "user", "Intruder")

        row = self._row()
        self.assertEqual(row.user, OTHER_USER)
        self.assertEqual(row.message_count, 1)
        self.assertFalse(row.title)

    def test_conversation_doctype_cannot_be_a_workflow_trigger_target(self):
        self.assertIn("FAC Chat Conversation", DOCTYPE_BLOCKLIST)

    def test_auto_title_truncates_with_ellipsis(self):
        title = auto_title("word " * 40)
        self.assertEqual(len(title), 80)
        self.assertTrue(title.endswith("…"))
