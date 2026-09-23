"""The zero-retention blob must be stored on every terminal event, errors included.

The blob is the only copy of conversation state. FAC used to store it in the two
``stream_complete`` branches only, so a turn that ended in ``stream_error`` left
the stored state one turn behind — while the partial assistant reply WAS
persisted to the transcript. The user then saw a message the model had never
heard of, and a later HITL resume rebuilt its history from a blob that predated
the pending tool call, producing AR's "No tool call found for function call
output" 400.

These tests pin the shared helper's gating and the discipline that all four
terminal branches (2 funnels x complete/error) route through it.
"""

import ast
import inspect
import unittest
from pathlib import Path
from unittest.mock import patch

WIRE = {"blob": "H4sIA...", "sig": "abc", "format_version": 1, "turn_seq": 7}


def _relay():
    from frappe_assistant_core.chat.api.chat import relay

    return relay


class TestPersistSessionBlob(unittest.TestCase):
    def _call(self, **overrides):
        relay = _relay()
        kwargs = {
            "session_id": "S1",
            "user": "a@b.com",
            "data": {"session_state": WIRE},
            "zero_retention": True,
            "restricted": False,
        }
        kwargs.update(overrides)
        with patch(
            "frappe_assistant_core.chat.doctype.fac_chat_session_state"
            ".fac_chat_session_state.FACChatSessionState.persist_safe"
        ) as persist:
            relay._persist_session_blob(
                kwargs["session_id"],
                kwargs["user"],
                kwargs["data"],
                kwargs["zero_retention"],
                kwargs["restricted"],
            )
        return persist

    def test_stores_the_blob_on_a_zero_retention_turn(self):
        persist = self._call()
        persist.assert_called_once()
        self.assertEqual(persist.call_args[0][2], WIRE)

    def test_records_a_pending_interrupt_from_ars_own_flag(self):
        """The send funnel used to omit has_pending_interrupt entirely, marking an
        interrupted turn as having none. Deriving it here keeps both funnels honest."""
        persist = self._call(data={"session_state": WIRE, "interrupted": True})
        self.assertIs(persist.call_args[1]["has_pending_interrupt"], True)

    def test_records_no_pending_interrupt_on_a_plain_turn(self):
        persist = self._call()
        self.assertIs(persist.call_args[1]["has_pending_interrupt"], False)

    def test_stateful_tenant_stores_nothing(self):
        """zero_retention is read off AR's stream_start; when false, AR keeps the
        rows and there is no blob to hold."""
        self._call(zero_retention=False).assert_not_called()

    def test_gdpr_restricted_user_stores_nothing(self):
        """Article 18: no blob loaded inbound, none stored outbound — the error
        path must not become a back door for that rule."""
        self._call(restricted=True).assert_not_called()

    def test_event_without_a_blob_stores_nothing(self):
        self._call(data={"error": "boom"}).assert_not_called()


class TestTerminalBranchDiscipline(unittest.TestCase):
    """Both relay funnels must persist the blob on completion AND on error."""

    def setUp(self):
        source = Path(inspect.getfile(_relay())).read_text()
        self.tree = ast.parse(source)

    def _funnel(self, name: str) -> ast.FunctionDef:
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return node
        raise AssertionError(f"{name} not found in relay.py")

    def _branch_event_types(self, funnel: ast.FunctionDef) -> set[str]:
        """The ``event_type == "..."`` branches whose body calls the blob helper."""
        persisting = set()
        for node in ast.walk(funnel):
            if not isinstance(node, ast.If):
                continue
            calls_helper = any(
                isinstance(c, ast.Call)
                and isinstance(c.func, ast.Name)
                and c.func.id == "_persist_session_blob"
                for c in ast.walk(node)
            )
            if not calls_helper:
                continue
            for cmp_node in ast.walk(node.test):
                if isinstance(cmp_node, ast.Constant) and isinstance(cmp_node.value, str):
                    persisting.add(cmp_node.value)
        return persisting

    def test_send_funnel_persists_on_complete_and_error(self):
        types = self._branch_event_types(self._funnel("_relay_ar_stream"))
        self.assertIn("stream_complete", types)
        self.assertIn("stream_error", types)

    def test_resume_funnel_persists_on_complete_and_error(self):
        types = self._branch_event_types(self._funnel("_relay_ar_interrupt_resume"))
        self.assertIn("stream_complete", types)
        self.assertIn("stream_error", types)
