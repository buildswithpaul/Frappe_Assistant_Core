# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""``get_pending_interrupt`` tells "nothing pending" from "could not ask AR" (spec §8.7).

Clients restore approval cards through this probe. ``{pending: False}`` is how
AR says the pause is gone, so the FAC mobile app marks a card it still shows
"Resolved on another device". The probe used to give that same answer when FAC
had no AR client or AR was unreachable, so an AR outage flipped live approvals.
Those branches now add ``unavailable: True``; the app keeps its cards and asks
again on its next recovery.

Runs as a throwaway user with the AR client mocked, so nothing leaves the site.
"""

from unittest.mock import MagicMock, patch

import frappe
from assistant_runtime_sdk import ARAPIError, ARConnectionError, ARTimeoutError

from frappe_assistant_core.tests.base_test import BaseAssistantTest

CLIENT_FACTORY = "frappe_assistant_core.chat.api.chat.hitl.get_fac_cloud_client"
SESSION_ID = "s-probe"
UNAVAILABLE = {"pending": False, "unavailable": True}
PENDING = {
    "pending": True,
    "session_id": SESSION_ID,
    "expires_at": "2026-09-23T10:30:00+00:00",
    "event": {
        "tool_id": "toolu_probe",
        "tool_name": "create_document",
        "input": {"doctype": "ToDo"},
        "interrupts": [{"id": "int-1", "name": "create_document", "reason": {"type": "approval"}}],
    },
}


class TestPendingInterruptUnavailable(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.user = self.make_throwaway_user("hitl-probe")
        frappe.set_user(self.user)

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _probe(self, client) -> dict:
        from frappe_assistant_core.chat.api.chat import get_pending_interrupt

        with patch(CLIENT_FACTORY, return_value=client):
            return get_pending_interrupt(SESSION_ID)

    def test_no_ar_client_is_unavailable(self):
        self.assertEqual(self._probe(None), UNAVAILABLE)

    def test_a_transport_or_api_failure_is_unavailable(self):
        for error in (
            ARConnectionError("Failed to connect to get_pending_interrupt"),
            ARTimeoutError("Request to get_pending_interrupt timed out"),
            ARAPIError("Bad Gateway", status_code=502),
        ):
            with self.subTest(error=type(error).__name__):
                client = MagicMock()
                client.get_pending_interrupt.side_effect = error

                self.assertEqual(self._probe(client), UNAVAILABLE)

    def test_an_empty_reply_is_unavailable(self):
        client = MagicMock()
        client.get_pending_interrupt.return_value = None

        self.assertEqual(self._probe(client), UNAVAILABLE)

    def test_ar_saying_nothing_is_pending_stays_unflagged(self):
        client = MagicMock()
        client.get_pending_interrupt.return_value = {"pending": False}

        self.assertEqual(self._probe(client), {"pending": False})

    def test_a_pending_pause_is_forwarded_as_ar_sent_it(self):
        client = MagicMock()
        client.get_pending_interrupt.return_value = PENDING

        self.assertEqual(self._probe(client), PENDING)
        client.get_pending_interrupt.assert_called_once_with(SESSION_ID, self.user)
