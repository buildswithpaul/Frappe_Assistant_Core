# Frappe Assistant Core - Chat Resume Ownership Tests
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""send_message, resume_interrupt and continue_response must be session-owner-only.

All three drive a conversation identified only by a client-supplied session_id.
Without an ownership check any authenticated user could append to, resume, or
continue somebody else's session by supplying its id — cancel_stream and
get_session_history already check.
"""

import unittest
from contextlib import ExitStack
from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api.chat import messages as messages_mod
from frappe_assistant_core.chat.api.chat.messages import _assert_session_owner

_MOD = "frappe_assistant_core.chat.api.chat.messages"


def _session_owned_by(owner: str | None, caller: str, roles: list[str]) -> ExitStack:
    """Patch the three things the guard reads: the row owner, caller, roles."""
    stack = ExitStack()
    stack.enter_context(patch(f"{_MOD}.frappe.db.get_value", return_value=owner))
    stack.enter_context(patch(f"{_MOD}.frappe.get_roles", return_value=roles))
    session = stack.enter_context(patch(f"{_MOD}.frappe.session"))
    session.user = caller
    return stack


class TestSessionOwnershipGuard(unittest.TestCase):
    def test_foreign_session_is_refused(self):
        with _session_owned_by("someone-else@example.com", "owner@example.com", ["All"]):
            with self.assertRaises(frappe.PermissionError):
                _assert_session_owner("sess-foreign")

    def test_own_session_is_allowed(self):
        with _session_owned_by("owner@example.com", "owner@example.com", ["All"]):
            _assert_session_owner("sess-own")

    def test_unknown_session_is_allowed(self):
        # A session with no persisted messages yet (zero-retention / restricted
        # processing) has no owner to compare against.
        with _session_owned_by(None, "owner@example.com", ["All"]):
            _assert_session_owner("sess-new")

    def test_system_manager_may_act_on_any_session(self):
        with _session_owned_by("someone-else@example.com", "admin@example.com", ["All", "System Manager"]):
            _assert_session_owner("sess-foreign")

    def test_guard_queries_the_latest_message_of_the_session(self):
        # Same query shape as cancel_stream, so both endpoints agree on owner.
        with _session_owned_by("owner@example.com", "owner@example.com", ["All"]):
            _assert_session_owner("sess-own")
            args, kwargs = messages_mod.frappe.db.get_value.call_args
        self.assertEqual(args[0], "FAC Chat Message")
        self.assertEqual(args[1], {"session_id": "sess-own"})
        self.assertEqual(args[2], "user")
        self.assertEqual(kwargs["order_by"], "creation desc")


class TestEndpointsRefuseForeignSessions(unittest.TestCase):
    """The refusal must reach the caller as PermissionError, before any work.

    Both endpoints wrap their body in ``except Exception``, and
    frappe.PermissionError does not subclass ValidationError, so the refusal
    needs an explicit re-raise to surface as cancel_stream's 403 rather than a
    generic 417.
    """

    def test_resume_interrupt_refuses_and_queues_nothing(self):
        with _session_owned_by("someone-else@example.com", "owner@example.com", ["All"]), patch.object(
            messages_mod._relay_pool, "submit"
        ) as submit:
            with self.assertRaises(frappe.PermissionError):
                messages_mod.resume_interrupt(
                    session_id="sess-foreign",
                    interrupt_response='[{"interruptId": "i-1", "response": "approve"}]',
                )
            submit.assert_not_called()

    def test_continue_response_refuses_and_queues_nothing(self):
        with _session_owned_by("someone-else@example.com", "owner@example.com", ["All"]), patch.object(
            messages_mod._relay_pool, "submit"
        ) as submit:
            with self.assertRaises(frappe.PermissionError):
                messages_mod.continue_response(
                    session_id="sess-foreign",
                    message_id="msg-1",
                )
            submit.assert_not_called()

    def test_send_message_refuses_and_persists_nothing(self):
        # send_message is the widest of the three: it both appends a message to
        # the foreign session and drives a turn on it.
        with _session_owned_by("someone-else@example.com", "owner@example.com", ["All"]), patch.object(
            messages_mod._relay_pool, "submit"
        ) as submit, patch(f"{_MOD}._is_processing_restricted", return_value=False) as restricted:
            with self.assertRaises(frappe.PermissionError):
                messages_mod.send_message(
                    session_id="sess-foreign",
                    message="hello",
                )
            submit.assert_not_called()
            # The guard runs before any persistence path is entered.
            restricted.assert_not_called()
