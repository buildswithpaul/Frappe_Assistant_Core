# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Tests for FAC-local conversation analytics aggregation and endpoints.

Under Zero Data Retention the AR side stores no conversations, so the usage
page reconstructs per-conversation analytics from local FAC Chat Message rows.
The pure aggregation helpers are tested with plain unittest (no DB); the
endpoint layer is tested with FrappeTestCase against real rows.
"""

import unittest

from frappe_assistant_core.chat.api._conversation_analytics_local import (
    build_conversation_list,
    build_message_credits,
)


class TestBuildConversationList(unittest.TestCase):
    def _rows(self):
        # Two sessions; credits only on assistant rows.
        return [
            {
                "session_id": "s1",
                "role": "user",
                "content": "First question about sales",
                "credits_used": 0,
                "timestamp": "2026-06-10 10:00:00",
                "user": "a@x.com",
                "idx": 1,
            },
            {
                "session_id": "s1",
                "role": "assistant",
                "content": "Answer",
                "credits_used": 12,
                "timestamp": "2026-06-10 10:00:05",
                "user": "a@x.com",
                "idx": 2,
            },
            {
                "session_id": "s2",
                "role": "user",
                "content": "Second",
                "credits_used": 0,
                "timestamp": "2026-06-11 09:00:00",
                "user": "b@x.com",
                "idx": 1,
            },
            {
                "session_id": "s2",
                "role": "assistant",
                "content": "Reply",
                "credits_used": 8,
                "timestamp": "2026-06-11 09:00:03",
                "user": "b@x.com",
                "idx": 2,
            },
        ]

    def test_groups_by_session_with_credits_and_counts(self):
        out = build_conversation_list(self._rows(), limit=50, offset=0)
        convs = {c["conversation_id"]: c for c in out["conversations"]}
        self.assertEqual(set(convs), {"s1", "s2"})
        self.assertEqual(convs["s1"]["total_credits"], 12)
        self.assertEqual(convs["s1"]["message_count"], 2)
        self.assertEqual(convs["s1"]["user_id"], "a@x.com")

    def test_title_is_first_user_message_truncated(self):
        out = build_conversation_list(self._rows(), limit=50, offset=0)
        convs = {c["conversation_id"]: c for c in out["conversations"]}
        self.assertEqual(convs["s1"]["title"], "First question about sales")

    def test_summary_totals(self):
        out = build_conversation_list(self._rows(), limit=50, offset=0)
        self.assertEqual(out["summary"]["total_conversations"], 2)
        self.assertEqual(out["summary"]["total_credits"], 20)
        self.assertEqual(out["summary"]["total_messages"], 4)

    def test_orders_by_last_activity_desc(self):
        out = build_conversation_list(self._rows(), limit=50, offset=0)
        ids = [c["conversation_id"] for c in out["conversations"]]
        self.assertEqual(ids, ["s2", "s1"])  # s2 is newer

    def test_pagination_limit_offset(self):
        out = build_conversation_list(self._rows(), limit=1, offset=0)
        self.assertEqual(len(out["conversations"]), 1)
        self.assertEqual(out["pagination"]["total"], 2)
        self.assertTrue(out["pagination"]["has_more"])

    def test_empty_rows_yields_empty_payload(self):
        out = build_conversation_list([], limit=50, offset=0)
        self.assertEqual(out["conversations"], [])
        self.assertEqual(out["summary"]["total_conversations"], 0)
        self.assertFalse(out["pagination"]["has_more"])


class TestBuildMessageCredits(unittest.TestCase):
    def _rows(self):
        return [
            {
                "message_id": "m1",
                "role": "user",
                "content": "Get me sales",
                "model": None,
                "credits_used": 0,
                "timestamp": "2026-06-10 10:00:00",
                "tool_calls": None,
            },
            {
                "message_id": "m2",
                "role": "assistant",
                "content": "Here are the sales numbers in detail " * 10,
                "model": "claude-x",
                "credits_used": 14,
                "timestamp": "2026-06-10 10:00:05",
                "tool_calls": '[{"name": "run_query"}]',
            },
        ]

    def test_maps_messages_with_credits_and_preview(self):
        out = build_message_credits("s1", self._rows())
        self.assertEqual(out["conversation_id"], "s1")
        self.assertEqual(len(out["messages"]), 2)
        asst = out["messages"][1]
        self.assertEqual(asst["credits_used"], 14)
        self.assertEqual(asst["model_id"], "claude-x")
        self.assertLessEqual(len(asst["content_preview"]), 200)
        self.assertEqual(asst["tool_count"], 1)
        self.assertEqual(asst["tool_names"], ["run_query"])

    def test_title_from_first_user_message(self):
        out = build_message_credits("s1", self._rows())
        self.assertEqual(out["title"], "Get me sales")

    def test_totals(self):
        out = build_message_credits("s1", self._rows())
        self.assertEqual(out["total_credits"], 14)
        self.assertEqual(out["total_messages"], 2)

    def test_malformed_tool_calls_does_not_crash(self):
        rows = [
            {
                "message_id": "m1",
                "role": "assistant",
                "content": "x",
                "model": "m",
                "credits_used": 1,
                "timestamp": "2026-06-10 10:00:00",
                "tool_calls": "not json",
            }
        ]
        out = build_message_credits("s1", rows)
        self.assertEqual(out["messages"][0]["tool_count"], 0)

    def test_model_breakdown_parsed_for_delegating_turn(self):
        rows = [
            {
                "message_id": "m1",
                "role": "assistant",
                "content": "x",
                "model": "claude-sonnet-4-6",
                "credits_used": 260,
                "timestamp": "2026-06-10 10:00:00",
                "tool_calls": None,
                "model_breakdown": (
                    '[{"model_id":"claude-sonnet-4-6","role":"orchestrator","credits":180,'
                    '"input_tokens":4200,"output_tokens":1100},'
                    '{"model_id":"claude-haiku-4-5","role":"helper","credits":80,'
                    '"input_tokens":9000,"output_tokens":2400}]'
                ),
            }
        ]
        out = build_message_credits("s1", rows)
        msg = out["messages"][0]
        bd = msg["model_breakdown"]
        self.assertEqual(len(bd), 2)
        self.assertEqual(bd[0]["role"], "orchestrator")
        self.assertEqual(bd[1]["model_id"], "claude-haiku-4-5")
        self.assertEqual(bd[1]["credits"], 80)
        # Tokens are never exposed — the product surfaces credits only.
        self.assertNotIn("tokens_used", msg)
        self.assertNotIn("input_tokens", bd[0])
        self.assertNotIn("output_tokens", bd[0])

    def test_model_breakdown_empty_for_single_model_and_malformed(self):
        rows = [
            {
                "message_id": "a",
                "role": "assistant",
                "content": "x",
                "model": "m",
                "credits_used": 1,
                "timestamp": "2026-06-10 10:00:00",
                "tool_calls": None,
                "model_breakdown": None,
            },
            {
                "message_id": "b",
                "role": "assistant",
                "content": "y",
                "model": "m",
                "credits_used": 1,
                "timestamp": "2026-06-10 10:00:01",
                "tool_calls": None,
                "model_breakdown": "not json",
            },
        ]
        out = build_message_credits("s1", rows)
        self.assertEqual(out["messages"][0]["model_breakdown"], [])
        self.assertEqual(out["messages"][1]["model_breakdown"], [])


import frappe  # noqa: E402

from frappe_assistant_core.chat.api import analytics  # noqa: E402
from frappe_assistant_core.tests.base_test import BaseAssistantTest  # noqa: E402


class TestAnalyticsEndpointsLocal(BaseAssistantTest):
    """The admin analytics endpoints read team-wide from local FAC Chat
    Message rows (authoritative under zero retention), not from AR/SDK.

    Uses BaseAssistantTest (IntegrationTestCase) so the inserts run inside a
    rolled-back transaction — no leaked rows, no fiscal-year fixture crash.
    """

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.sid = "test-analytics-sess-1"
        frappe.db.delete("FAC Chat Message", {"session_id": self.sid})
        for role, content, credits, idx in [
            ("user", "Show me Q2 sales", 0, 1),
            ("assistant", "Here is the breakdown", 17, 2),
        ]:
            frappe.get_doc(
                {
                    "doctype": "FAC Chat Message",
                    "session_id": self.sid,
                    "role": role,
                    "content": content,
                    "user": "Administrator",
                    "timestamp": frappe.utils.now(),
                    "credits_used": credits,
                    "idx": idx,
                }
            ).insert(ignore_permissions=True)

    def test_conversation_analytics_lists_local_session_with_credits(self):
        out = analytics.get_conversation_analytics(days=90, limit=50, offset=0)
        ids = [c["conversation_id"] for c in out["conversations"]]
        self.assertIn(self.sid, ids)
        conv = next(c for c in out["conversations"] if c["conversation_id"] == self.sid)
        self.assertEqual(conv["total_credits"], 17)
        self.assertEqual(conv["title"], "Show me Q2 sales")
        self.assertTrue(out["is_admin"])

    def test_conversation_analytics_includes_archived_sessions(self):
        """Archiving hides a conversation from the chat list, not from usage.

        Archiving is not erasure — the rows are kept deliberately, and GDPR
        erase deletes them outright instead. Every other panel on the usage
        page still counts what an archived conversation spent, so excluding it
        here left an admin looking at credits with nothing to attribute them
        to. ``get_message_credits`` never filtered on it either, so the
        drill-down already returned these rows.
        """
        archived_sid = "test-analytics-archived-1"
        frappe.db.delete("FAC Chat Message", {"session_id": archived_sid})
        for role, content, credits, idx in [
            ("user", "Archived question", 0, 1),
            ("assistant", "Archived answer", 9, 2),
        ]:
            frappe.get_doc(
                {
                    "doctype": "FAC Chat Message",
                    "session_id": archived_sid,
                    "role": role,
                    "content": content,
                    "user": "Administrator",
                    "timestamp": frappe.utils.now(),
                    "credits_used": credits,
                    "idx": idx,
                    "is_archived": 1,
                }
            ).insert(ignore_permissions=True)

        out = analytics.get_conversation_analytics(days=90, limit=50, offset=0)
        conv = next((c for c in out["conversations"] if c["conversation_id"] == archived_sid), None)
        self.assertIsNotNone(conv, "archived conversation missing from usage analytics")
        self.assertEqual(conv["total_credits"], 9)

    def test_message_credits_returns_local_messages(self):
        out = analytics.get_message_credits(conversation_id=self.sid)
        self.assertEqual(out["conversation_id"], self.sid)
        self.assertEqual(out["total_credits"], 17)
        self.assertEqual(len(out["messages"]), 2)

    def test_message_credits_unknown_session_raises(self):
        with self.assertRaises(frappe.DoesNotExistError):
            analytics.get_message_credits(conversation_id="no-such-session-xyz")


class TestLogConversationCredits(BaseAssistantTest):
    """The web streaming path must persist the credits_used value AR sends in
    stream_complete onto the local FAC Chat Message — previously dropped."""

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.sid = "test-logconv-credits-1"
        frappe.db.delete("FAC Chat Message", {"session_id": self.sid})

    def test_log_conversation_persists_credits(self):
        from frappe_assistant_core.chat.api.chat.helpers import _log_conversation

        _log_conversation(
            session_id=self.sid,
            message="hi",
            response="hello there",
            model="claude-x",
            context=None,
            credits=9,
        )
        row = frappe.db.get_value(
            "FAC Chat Message",
            {"session_id": self.sid, "role": "assistant"},
            ["credits_used", "model"],
            as_dict=True,
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["credits_used"], 9)

    def test_fractional_credits_survive_persistence(self):
        from frappe_assistant_core.chat.api.chat.helpers import _log_conversation

        _log_conversation(
            session_id=self.sid,
            message="hi",
            response="fractional turn",
            model="claude-x",
            context=None,
            credits=0.4,
        )
        row = frappe.db.get_value(
            "FAC Chat Message",
            {"session_id": self.sid, "role": "assistant"},
            ["credits_used"],
            as_dict=True,
        )
        self.assertIsNotNone(row)
        # Fractional credits must not truncate to 0 (the reported usage bug).
        self.assertAlmostEqual(float(row["credits_used"]), 0.4, places=2)


class TestFractionalCreditAggregation(unittest.TestCase):
    """The usage page must not truncate sub-1.0 credits (reported bug)."""

    def _assistant_row(self, sid, credits, ts, mid="m"):
        return {
            "session_id": sid,
            "message_id": mid,
            "role": "assistant",
            "content": "answer",
            "model": "claude-x",
            "credits_used": credits,
            "timestamp": ts,
            "tool_calls": None,
        }

    def test_conversation_total_preserves_fractions(self):
        rows = [
            self._assistant_row("s1", 0.4, "2026-06-10 10:00:00", "m1"),
            self._assistant_row("s1", 0.3, "2026-06-10 10:00:05", "m2"),
        ]
        out = build_conversation_list(rows)
        # 0.4 + 0.3 must be ~0.7, not 0 (double int() truncation bug).
        self.assertAlmostEqual(out["summary"]["total_credits"], 0.7, places=2)
        self.assertAlmostEqual(out["conversations"][0]["total_credits"], 0.7, places=2)

    def test_message_credits_preserve_fractions(self):
        rows = [self._assistant_row("s1", 2.7, "2026-06-10 10:00:00", "m1")]
        out = build_message_credits("s1", rows)
        self.assertAlmostEqual(out["messages"][0]["credits_used"], 2.7, places=2)
        self.assertAlmostEqual(out["total_credits"], 2.7, places=2)
