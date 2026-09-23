# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Support endpoints must hand AR an email, never a Frappe docname.

A Frappe User's docname is its email for ordinary staff, but not for
Administrator — whose docname is the literal string "Administrator". AR keys
AR Tenant User by email, so that string matches no member: `raised_by` lands
blank and Helpdesk never opens the email thread, and the ticket list comes
back empty because the tickets were filed under a different id.

`_ar_user_id` is the canonical resolver and every AR-facing call here goes
through it. The transcript filter deliberately does NOT — it reads local
FAC Chat Message rows, which are keyed by the docname.
"""

import inspect
import unittest
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.chat.api import support

ADMIN_DOCNAME = "Administrator"
ADMIN_EMAIL = "paul@promantia.com"


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


class TestAdministratorReachesARAsAnEmail(unittest.TestCase):
    """The session account is "Administrator"; AR must still see the address."""

    def setUp(self):
        self.client = MagicMock()
        for p in (
            patch.object(support, "_get_client", return_value=self.client),
            patch.object(frappe, "session", frappe._dict(user=ADMIN_DOCNAME)),
            patch("frappe.db.get_value", return_value=ADMIN_EMAIL),
        ):
            p.start()
            self.addCleanup(p.stop)

    def _user_id_sent(self, method_name):
        return getattr(self.client, method_name).call_args.kwargs["user_id"]

    def test_create_ticket(self):
        _unwrap(support.create_ticket)(subject="s", description="d")
        self.assertEqual(self._user_id_sent("create_ticket"), ADMIN_EMAIL)

    def test_submit_feedback(self):
        _unwrap(support.submit_feedback)(rating=5)
        self.assertEqual(self._user_id_sent("submit_feedback"), ADMIN_EMAIL)

    def test_list_my_tickets(self):
        self.client.list_tickets.return_value = []
        _unwrap(support.list_my_tickets)()
        self.assertEqual(self._user_id_sent("list_tickets"), ADMIN_EMAIL)

    def test_list_my_feedback(self):
        self.client.list_feedback.return_value = []
        _unwrap(support.list_my_feedback)()
        self.assertEqual(self._user_id_sent("list_feedback"), ADMIN_EMAIL)

    def test_get_ticket_thread(self):
        _unwrap(support.get_ticket_thread)(ticket_id="7")
        self.assertEqual(self._user_id_sent("get_ticket_thread"), ADMIN_EMAIL)

    def test_reply_to_ticket(self):
        _unwrap(support.reply_to_ticket)(ticket_id="7", message="m")
        self.assertEqual(self._user_id_sent("reply_to_ticket"), ADMIN_EMAIL)

    def test_upload_and_download_resolve_too(self):
        # Both take the identity straight from _ar_user(); asserting the
        # resolver itself keeps this off their file-handling machinery.
        self.assertEqual(support._ar_user(), ADMIN_EMAIL)


class TestOrdinaryStaffArePassedThrough(unittest.TestCase):
    def test_a_docname_that_is_already_an_address_is_untouched(self):
        with patch.object(frappe, "session", frappe._dict(user="hari@promantia.com")):
            self.assertEqual(support._ar_user(), "hari@promantia.com")


class TestTheLocalFilterStaysOnTheDocname(unittest.TestCase):
    """The mirror-image regression: resolving here would break the scoping."""

    def test_transcript_reads_fac_chat_message_by_session_user(self):
        src = inspect.getsource(support._render_transcript)
        self.assertIn('"user": frappe.session.user', src)
        self.assertNotIn("_ar_user(", src)


class TestNoEndpointStillSendsTheRawDocname(unittest.TestCase):
    def test_no_ar_call_passes_frappe_session_user_as_user_id(self):
        src = inspect.getsource(support)
        self.assertNotIn("user_id=frappe.session.user", src)
