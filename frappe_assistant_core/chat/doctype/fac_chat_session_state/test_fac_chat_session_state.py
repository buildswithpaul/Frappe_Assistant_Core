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

"""Tests for FAC Chat Session State — the zero-retention session blob row.

Uses plain ``unittest.TestCase`` (not ``FrappeTestCase``) to match the rest of
the FAC suite: this is an ERPNext site and ``FrappeTestCase.setUpClass`` can
crash on fiscal-year fixtures. Each test cleans up its own rows in tearDown.
"""

import unittest
from unittest.mock import patch

import frappe
from frappe.utils import add_days, now_datetime

from frappe_assistant_core.chat.doctype.fac_chat_session_state.fac_chat_session_state import (
    FACChatSessionState,
    get_permission_query_conditions,
    has_permission,
)

TEST_USER = "Administrator"

# This class is plain unittest and commits for real — nothing here is rolled
# back. So any test exercising a USER-WIDE operation must run as a throwaway
# user, never as TEST_USER: archive_all_conversations() archives every
# unarchived conversation the current user owns, and as Administrator on a dev
# site that silently archives the developer's real chat history on every run.
ARCHIVE_ALL_USER = "fac-archive-all-test@example.com"


def _wire(blob="YmxvYg==", sig="deadbeef", format_version=1, turn_seq=None):
    """Build an AR-shaped wire form. The real wire is {blob, sig,
    format_version}; turn_seq is optional (FAC computes one when absent)."""
    w = {"blob": blob, "sig": sig, "format_version": format_version}
    if turn_seq is not None:
        w["turn_seq"] = turn_seq
    return w


class TestFACChatSessionState(unittest.TestCase):
    def setUp(self):
        self._session_ids = set()

    def tearDown(self):
        # Drop any state rows + chat messages this test created.
        for sid in self._session_ids:
            frappe.db.delete("FAC Chat Session State", {"session_id": sid})
            frappe.db.delete("FAC Chat Message", {"session_id": sid})
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — test seeds rows then asserts across the real archive / retention commit boundary

    def _sid(self, suffix):
        sid = f"test-zr-{suffix}-{frappe.generate_hash(length=8)}"
        self._session_ids.add(sid)
        return sid

    def _throwaway_user(self):
        """A user owning nothing but this test's rows, so a user-wide call
        can't reach real conversations."""
        if not frappe.db.exists("User", ARCHIVE_ALL_USER):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": ARCHIVE_ALL_USER,
                    "first_name": "Archive All",
                    "enabled": 1,
                    "send_welcome_email": 0,
                }
            ).insert(ignore_permissions=True)
        return ARCHIVE_ALL_USER

    # --- upsert / load_wire round-trip ---

    def test_upsert_then_load_wire_round_trip(self):
        sid = self._sid("roundtrip")
        FACChatSessionState.upsert(sid, TEST_USER, _wire(blob="Zmlyc3Q=", sig="sig1"))

        loaded = FACChatSessionState.load_wire(sid)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["blob"], "Zmlyc3Q=")
        self.assertEqual(loaded["sig"], "sig1")
        self.assertEqual(loaded["format_version"], 1)
        # No wire turn_seq → FAC assigns a monotonic 1 on first write.
        self.assertEqual(loaded["turn_seq"], 1)

    def test_load_wire_missing_returns_none(self):
        self.assertIsNone(FACChatSessionState.load_wire("test-zr-does-not-exist"))

    def test_upsert_replaces_blob_on_newer_write(self):
        sid = self._sid("replace")
        FACChatSessionState.upsert(sid, TEST_USER, _wire(blob="b25l", sig="s1"))
        FACChatSessionState.upsert(sid, TEST_USER, _wire(blob="dHdv", sig="s2"))

        loaded = FACChatSessionState.load_wire(sid)
        self.assertEqual(loaded["blob"], "dHdv")
        self.assertEqual(loaded["sig"], "s2")
        # Second serial write advances the monotonic counter.
        self.assertEqual(loaded["turn_seq"], 2)

    # --- last-writer-wins by turn_seq ---

    def test_stale_turn_seq_upsert_is_dropped(self):
        sid = self._sid("stale")
        # Establish turn_seq=5 explicitly via the wire.
        FACChatSessionState.upsert(sid, TEST_USER, _wire(blob="bmV3ZXI=", sig="new", turn_seq=5))
        # A stale write (turn_seq=3 <= 5) must be dropped.
        FACChatSessionState.upsert(sid, TEST_USER, _wire(blob="b2xkZXI=", sig="old", turn_seq=3))

        loaded = FACChatSessionState.load_wire(sid)
        self.assertEqual(loaded["blob"], "bmV3ZXI=")
        self.assertEqual(loaded["turn_seq"], 5)

    def test_equal_turn_seq_upsert_is_dropped(self):
        sid = self._sid("equal")
        FACChatSessionState.upsert(sid, TEST_USER, _wire(blob="a2VlcA==", sig="keep", turn_seq=7))
        FACChatSessionState.upsert(sid, TEST_USER, _wire(blob="ZHJvcA==", sig="drop", turn_seq=7))

        loaded = FACChatSessionState.load_wire(sid)
        self.assertEqual(loaded["blob"], "a2VlcA==")

    def test_empty_wire_is_noop(self):
        sid = self._sid("empty")
        FACChatSessionState.upsert(sid, TEST_USER, None)
        FACChatSessionState.upsert(sid, TEST_USER, {})
        FACChatSessionState.upsert(sid, TEST_USER, {"sig": "x"})  # no blob
        self.assertIsNone(FACChatSessionState.load_wire(sid))

    def test_has_pending_interrupt_persisted(self):
        sid = self._sid("interrupt")
        FACChatSessionState.upsert(sid, TEST_USER, _wire(), has_pending_interrupt=True)
        name = frappe.db.exists("FAC Chat Session State", {"session_id": sid})
        self.assertTrue(name)
        self.assertEqual(frappe.db.get_value("FAC Chat Session State", name, "has_pending_interrupt"), 1)

    # --- persist_safe: blob failure must not break the visible chat ---

    def test_persist_safe_swallows_upsert_failure_and_logs(self):
        """The relay's stream_complete path calls persist_safe so a blob write
        failure can't surface as a stream_error. An upsert exception must be
        caught and logged (content-free) rather than propagated."""
        sid = self._sid("persist-fail")
        with patch.object(
            FACChatSessionState, "upsert", side_effect=Exception("boom")
        ) as mocked_upsert, patch.object(frappe, "log_error") as mocked_log:
            # Must not raise — this is the whole guarantee.
            FACChatSessionState.persist_safe(sid, TEST_USER, _wire())

        mocked_upsert.assert_called_once()
        mocked_log.assert_called_once()
        # Privacy: the logged message carries only the session_id, never the
        # blob/transcript/message text.
        logged_message = mocked_log.call_args.kwargs["message"]
        self.assertEqual(logged_message, f"session_id={sid}")

    # --- delete_for_sessions: archive paths ---

    def test_archive_session_deletes_state_row(self):
        from frappe_assistant_core.chat.api.chat.sessions import archive_session
        from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import (
            FACChatMessage,
        )

        sid = self._sid("archive-one")
        frappe.set_user(TEST_USER)
        FACChatMessage.create_message(session_id=sid, role="user", content="hello")
        FACChatSessionState.upsert(sid, TEST_USER, _wire())
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — test seeds rows then asserts across the real archive / retention commit boundary

        self.assertTrue(frappe.db.exists("FAC Chat Session State", {"session_id": sid}))
        archive_session(sid)
        self.assertFalse(frappe.db.exists("FAC Chat Session State", {"session_id": sid}))

    def test_archive_all_conversations_deletes_all_state_rows(self):
        from frappe_assistant_core.chat.api.chat.sessions import archive_all_conversations
        from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import (
            FACChatMessage,
        )

        sid_a = self._sid("archive-all-a")
        sid_b = self._sid("archive-all-b")

        # Sentinel: a live conversation belonging to the developer running the
        # suite. It must still be unarchived afterwards.
        sentinel = self._sid("archive-all-bystander")
        frappe.set_user(TEST_USER)
        FACChatMessage.create_message(session_id=sentinel, role="user", content="keep me")

        # User-wide call, real commits: must not run as the developer's own user.
        user = self._throwaway_user()
        frappe.set_user(user)
        try:
            for sid in (sid_a, sid_b):
                FACChatMessage.create_message(session_id=sid, role="user", content="hi")
                FACChatSessionState.upsert(sid, user, _wire())
            frappe.db.commit()  # nosemgrep: frappe-manual-commit — test seeds rows then asserts across the real archive / retention commit boundary

            archive_all_conversations()
        finally:
            frappe.set_user(TEST_USER)

        self.assertFalse(frappe.db.exists("FAC Chat Session State", {"session_id": sid_a}))
        self.assertFalse(frappe.db.exists("FAC Chat Session State", {"session_id": sid_b}))

        # Nothing outside the throwaway user was touched.
        self.assertEqual(
            frappe.db.get_value("FAC Chat Message", {"session_id": sentinel}, "is_archived"),
            0,
            "archive_all_conversations reached a conversation it does not own — "
            "running this suite would archive the developer's real chat history",
        )

    def test_delete_for_sessions_accepts_string_and_list(self):
        sid_a = self._sid("del-a")
        sid_b = self._sid("del-b")
        FACChatSessionState.upsert(sid_a, TEST_USER, _wire())
        FACChatSessionState.upsert(sid_b, TEST_USER, _wire())

        FACChatSessionState.delete_for_sessions(sid_a)  # string
        self.assertFalse(frappe.db.exists("FAC Chat Session State", {"session_id": sid_a}))
        self.assertTrue(frappe.db.exists("FAC Chat Session State", {"session_id": sid_b}))

        FACChatSessionState.delete_for_sessions([sid_b])  # list
        self.assertFalse(frappe.db.exists("FAC Chat Session State", {"session_id": sid_b}))

    # --- delete-with-messages via retention (the headline privacy guarantee) ---

    def test_cleanup_old_messages_deletes_state_row_for_purged_session(self):
        from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import (
            FACChatMessage,
        )
        from frappe_assistant_core.chat.scheduler.retention import cleanup_old_messages

        sid = self._sid("retention")
        frappe.set_user(TEST_USER)

        # Seed an archived message well past any sane retention window, plus its
        # zero-retention session blob.
        msg = FACChatMessage.create_message(session_id=sid, role="user", content="old message")
        old = add_days(now_datetime(), -400)
        frappe.db.set_value(
            "FAC Chat Message",
            msg.name,
            {"is_archived": 1, "creation": old},
            update_modified=False,
        )
        FACChatSessionState.upsert(sid, TEST_USER, _wire())
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — test seeds rows then asserts across the real archive / retention commit boundary

        self.assertTrue(frappe.db.exists("FAC Chat Session State", {"session_id": sid}))

        # Ensure the gate + retention settings let the scheduler run.
        self._enable_retention()
        try:
            result = cleanup_old_messages()
        finally:
            self._restore_retention()

        self.assertEqual(result.get("status"), "success")
        # Message purged AND its blob deleted — no orphan.
        self.assertFalse(frappe.db.exists("FAC Chat Message", msg.name))
        self.assertFalse(
            frappe.db.exists("FAC Chat Session State", {"session_id": sid}),
            "retention must delete the session blob with its messages",
        )

    # --- owner-scoping permission hooks (IDOR fix) ---

    def test_query_conditions_scope_normal_user_to_own_rows(self):
        cond = get_permission_query_conditions("alice@example.com")
        self.assertIn("`tabFAC Chat Session State`.`user`", cond)
        self.assertIn(frappe.db.escape("alice@example.com"), cond)

    def test_query_conditions_empty_for_administrator(self):
        self.assertEqual(get_permission_query_conditions("Administrator"), "")

    def test_has_permission_true_for_owner(self):
        doc = frappe._dict(user="alice@example.com")
        self.assertTrue(has_permission(doc, user="alice@example.com"))

    def test_has_permission_false_for_non_owner(self):
        doc = frappe._dict(user="alice@example.com")
        self.assertFalse(has_permission(doc, user="bob@example.com"))

    def test_has_permission_true_for_administrator_regardless_of_owner(self):
        doc = frappe._dict(user="alice@example.com")
        self.assertTrue(has_permission(doc, user="Administrator"))

    # --- retention gate helpers ---

    def _enable_retention(self):
        self._prev_chat_enabled = frappe.db.get_single_value("Assistant Core Settings", "enable_fac_chat")
        frappe.db.set_single_value("Assistant Core Settings", "enable_fac_chat", 1)

        settings = frappe.get_doc("FAC Chat Settings")
        self._prev_retention = {
            "enable_retention_cleanup": settings.get("enable_retention_cleanup"),
            "message_retention_days": settings.get("message_retention_days"),
        }
        settings.enable_retention_cleanup = 1
        settings.message_retention_days = 30
        settings.save(ignore_permissions=True)
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — test seeds rows then asserts across the real archive / retention commit boundary
        frappe.clear_cache(doctype="FAC Chat Settings")
        from frappe_assistant_core.chat.gate import clear_chat_gate_cache

        clear_chat_gate_cache()

    def _restore_retention(self):
        frappe.db.set_single_value("Assistant Core Settings", "enable_fac_chat", self._prev_chat_enabled)
        settings = frappe.get_doc("FAC Chat Settings")
        for k, v in self._prev_retention.items():
            settings.set(k, v)
        settings.save(ignore_permissions=True)
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — test seeds rows then asserts across the real archive / retention commit boundary
        frappe.clear_cache(doctype="FAC Chat Settings")
        from frappe_assistant_core.chat.gate import clear_chat_gate_cache

        clear_chat_gate_cache()


if __name__ == "__main__":
    unittest.main()
