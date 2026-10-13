# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Sidebar sessions API over FAC Chat Conversation."""

import frappe

from frappe_assistant_core.chat.api.chat.sessions import (
    archive_session,
    continue_archived_session,
    get_archived_sessions,
    get_user_sessions,
    move_session_to_project,
    rename_session,
)
from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import FACChatMessage
from frappe_assistant_core.chat.tests.test_chat_projects_api import OTHER_USER, ensure_user, make_project
from frappe_assistant_core.tests.base_test import BaseAssistantTest

PREFIX = "test-sessions-api-"


def chat(sid: str, text: str, user: str = "Administrator") -> str:
    # nosemgrep: frappe-setuser — test bootstrap; runs in an isolated transaction
    frappe.set_user(user)
    FACChatMessage.create_message(PREFIX + sid, "user", text)
    # nosemgrep: frappe-setuser — test bootstrap; runs in an isolated transaction
    frappe.set_user("Administrator")
    return PREFIX + sid


class TestSessionsApi(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; runs in an isolated transaction
        frappe.set_user("Administrator")
        ensure_user(OTHER_USER)
        frappe.db.delete("FAC Chat Message", {"session_id": ["like", PREFIX + "%"]})
        frappe.db.delete("FAC Chat Conversation", {"name": ["like", PREFIX + "%"]})

    def _ids(self, rows):
        return [r["session_id"] for r in rows if r["session_id"].startswith(PREFIX)]

    def test_rows_keep_backward_compatible_keys(self):
        chat("a", "Hello there")
        row = next(r for r in get_user_sessions(limit=100) if r["session_id"] == PREFIX + "a")
        for key in ("session_id", "preview", "started", "last_activity", "message_count", "title", "project"):
            self.assertIn(key, row)
        self.assertEqual(row["preview"], "Hello there")

    def test_pagination_reaches_every_conversation(self):
        for i in range(5):
            chat(f"p{i}", f"Question {i}")
        seen = []
        offset = 0
        while True:
            page = get_user_sessions(limit=2, offset=offset)
            if not page:
                break
            seen += self._ids(page)
            offset += len(page)
        self.assertEqual(len(set(seen)), 5)

    def test_search_matches_title_and_message_content(self):
        chat("t", "Reorder levels for steel")
        sid = chat("c", "Unrelated opener")
        FACChatMessage.create_message(sid, "user", "what about the zebra stock?")
        self.assertEqual(self._ids(get_user_sessions(limit=100, search="steel")), [PREFIX + "t"])
        self.assertEqual(self._ids(get_user_sessions(limit=100, search="zebra")), [PREFIX + "c"])

    def test_search_escapes_wildcards(self):
        chat("pct", "growth was 50% this year")
        chat("plain", "growth was 50 units")
        self.assertEqual(self._ids(get_user_sessions(limit=100, search="50%")), [PREFIX + "pct"])
        self.assertEqual(self._ids(get_user_sessions(limit=100, search="5_")), [])

    def test_search_shorter_than_two_chars_is_ignored(self):
        chat("x", "anything")
        self.assertIn(PREFIX + "x", self._ids(get_user_sessions(limit=100, search="q")))

    def test_project_filter(self):
        project = make_project("Administrator")
        sid = chat("in", "inside")
        chat("out", "outside")
        move_session_to_project(sid, project)
        self.assertEqual(self._ids(get_user_sessions(limit=100, project=project)), [sid])

    def test_rename_sets_custom_title_and_blank_reverts(self):
        sid = chat("r", "Original opener")
        self.assertEqual(rename_session(sid, "  My   name ")["title"], "My name")
        self.assertEqual(frappe.db.get_value("FAC Chat Conversation", sid, "title_is_custom"), 1)
        result = rename_session(sid, "   ")
        self.assertEqual(result["title"], "Original opener")
        self.assertFalse(result["title_is_custom"])

    def test_rename_rejects_too_long(self):
        sid = chat("long", "x")
        with self.assertRaises(frappe.ValidationError):
            rename_session(sid, "y" * 141)

    def test_rename_other_users_conversation_is_refused(self):
        theirs = chat("theirs", "secret", user=OTHER_USER)
        with self.assertRaises(frappe.DoesNotExistError):
            rename_session(theirs, "hijack")
        self.assertEqual(frappe.db.get_value("FAC Chat Conversation", theirs, "title"), "secret")

    def test_move_into_other_users_project_is_refused(self):
        sid = chat("m", "mine")
        with self.assertRaises(frappe.DoesNotExistError):
            move_session_to_project(sid, make_project(OTHER_USER))
        self.assertIsNone(frappe.db.get_value("FAC Chat Conversation", sid, "project"))

    def test_move_out_of_project(self):
        project = make_project("Administrator")
        sid = chat("o", "x")
        move_session_to_project(sid, project)
        self.assertIsNone(move_session_to_project(sid, None)["project"])

    def test_archived_sessions_come_from_the_table(self):
        sid = chat("arch", "old")
        archive_session(sid)
        self.assertIn(sid, self._ids(get_archived_sessions(limit=100)))
        self.assertNotIn(sid, self._ids(get_user_sessions(limit=100)))

    def test_continue_archived_returns_the_project(self):
        project = make_project("Administrator")
        sid = chat("cont", "old")
        move_session_to_project(sid, project)
        archive_session(sid)
        self.assertEqual(continue_archived_session(sid)["project"], project)

    def test_non_system_manager_sees_only_their_own_conversations(self):
        # Real chat users are plain System Users, not System Managers, so the "All"/if_owner
        # permission row applies; every other test here runs as Administrator and skips it.
        # OTHER_USER is created by ensure_user as a System User with no extra roles, as FAC seats are.
        chat("admin-own", "steel from admin")
        mine = chat("mine", "steel from other", user=OTHER_USER)
        gone = chat("mine-old", "old steel from other", user=OTHER_USER)
        # nosemgrep: frappe-setuser — test bootstrap; runs in an isolated transaction
        frappe.set_user(OTHER_USER)
        try:
            archive_session(gone)
            self.assertEqual(self._ids(get_user_sessions(limit=100)), [mine])
            self.assertEqual(self._ids(get_user_sessions(limit=100, search="steel")), [mine])
            self.assertEqual(self._ids(get_archived_sessions(limit=100)), [gone])
        finally:
            # nosemgrep: frappe-setuser — test bootstrap; runs in an isolated transaction
            frappe.set_user("Administrator")
