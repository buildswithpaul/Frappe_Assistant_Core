# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""A conversation list that could not be read says so instead of answering ``[]``.

``get_user_sessions`` and ``get_archived_sessions`` used to catch every
exception and answer ``[]``, which is also what an account with no
conversations gets. A transient database error then emptied the list in every
client. They now let the error through: Frappe logs it and answers with an
error response, and a client keeps the list it already shows.

``initialize_spa`` embeds the same list. There a failed read must neither fail
the whole boot nor pass for an empty account, so the payload carries
``sessions: None``, which the SPA already reads as "not pre-fetched".

Runs as a throwaway user; the failing reads and the AR client are mocked.
"""

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest

SESSIONS_MODULE = "frappe_assistant_core.chat.api.chat.sessions"
LOG_HELPER = "frappe_assistant_core.chat.api._helpers._log"
BOOT_LOG_TITLE = "FAC Chat boot: conversation list unavailable"
GATE_READY = {"can_use": True, "status": "ready", "show_widget": True, "is_admin": False, "preferences": {}}
AUTH_READY = {
    "user_exists": True,
    "user_status": "Active",
    "has_mcp_servers": True,
    "active_server_count": 1,
    "servers_with_expired_tokens": [],
    "ready_for_streaming": True,
}
# (label, patch target): the aggregate query runs through frappe.qb, which
# executes on frappe.db.sql; the preview query is a frappe.get_all.
FAILING_READS = (("aggregate", "frappe.db.sql"), ("preview", "frappe.get_all"))


class TestSessionListsReportFailure(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.user = self.make_throwaway_user("session-lists")
        frappe.set_user(self.user)
        self.db_error = frappe.db.OperationalError
        self.lost_connection = self.db_error(2013, "Lost connection to server during query")
        self.active_sid = f"lists-active-{frappe.generate_hash(length=8)}"
        self.archived_sid = f"lists-archived-{frappe.generate_hash(length=8)}"

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _add_conversation(self, session_id: str, archived: int) -> None:
        frappe.get_doc(
            {
                "doctype": "FAC Chat Message",
                "session_id": session_id,
                "user": self.user,
                "role": "user",
                "content": f"Question in {session_id}",
                "is_archived": archived,
            }
        ).insert(ignore_permissions=True)

    def test_a_failed_read_raises_instead_of_answering_an_empty_list(self):
        from frappe_assistant_core.chat.api.chat.sessions import get_archived_sessions, get_user_sessions

        # One row per list, so the preview query is reached too.
        self._add_conversation(self.active_sid, archived=0)
        self._add_conversation(self.archived_sid, archived=1)
        for endpoint in (get_user_sessions, get_archived_sessions):
            for label, target in FAILING_READS:
                with self.subTest(endpoint=endpoint.__name__, read=label):
                    # log_error is stubbed so a catch-all's Error Log insert cannot
                    # hit the failing frappe.db.sql and raise on its behalf.
                    with patch("frappe.log_error"), patch(target, side_effect=self.lost_connection):
                        with self.assertRaises(self.db_error):
                            endpoint(limit=100)

    def test_the_lists_are_unchanged_when_the_reads_succeed(self):
        from frappe_assistant_core.chat.api.chat.sessions import get_archived_sessions, get_user_sessions

        self._add_conversation(self.active_sid, archived=0)
        self._add_conversation(self.archived_sid, archived=1)

        active = get_user_sessions(limit=100)
        archived = get_archived_sessions(limit=100)

        self.assertEqual([s["session_id"] for s in active], [self.active_sid])
        self.assertEqual(active[0]["preview"], f"Question in {self.active_sid}")
        self.assertEqual(active[0]["message_count"], 1)
        self.assertNotIn("is_archived", active[0])
        self.assertEqual([s["session_id"] for s in archived], [self.archived_sid])
        self.assertEqual(archived[0]["preview"], f"Question in {self.archived_sid}")
        self.assertIs(archived[0]["is_archived"], True)

    def test_an_account_with_no_conversations_still_gets_an_empty_list(self):
        from frappe_assistant_core.chat.api.chat.sessions import get_archived_sessions, get_user_sessions

        self.assertEqual(get_user_sessions(), [])
        self.assertEqual(get_archived_sessions(), [])

    def test_the_boot_helper_logs_and_answers_none_when_the_list_cannot_be_read(self):
        from frappe_assistant_core.chat.api.init import _fetch_sessions

        failing = patch(f"{SESSIONS_MODULE}.get_user_sessions", side_effect=self.lost_connection)
        with failing, patch(LOG_HELPER) as log:
            self.assertIsNone(_fetch_sessions())

        log.assert_called_once_with(BOOT_LOG_TITLE)

    def test_the_boot_survives_a_list_that_cannot_be_read(self):
        from frappe_assistant_core.chat.api import init as init_mod

        client = MagicMock()
        client.get_user_auth_status.return_value = AUTH_READY
        client.get_terms_status.return_value = None
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "frappe_assistant_core.chat.api.settings.access.can_use_faco",
                    return_value=dict(GATE_READY),
                )
            )
            stack.enter_context(
                patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client)
            )
            stack.enter_context(
                patch.object(init_mod, "_get_cached_or_fetch_capabilities", return_value=None)
            )
            # Keep the quota read off the shared cache: a mocked AR client would
            # mark the site's quota seed as failed for everyone on the dev site.
            stack.enter_context(patch.object(init_mod, "_build_quota", return_value={}))
            stack.enter_context(
                patch(f"{SESSIONS_MODULE}.get_user_sessions", side_effect=self.lost_connection)
            )
            stack.enter_context(patch(LOG_HELPER))
            payload = init_mod.initialize_spa()

        self.assertIsNone(payload["sessions"])
        self.assertIsNotNone(payload["user_auth"])
        self.assertTrue(payload["access"]["can_use"])
