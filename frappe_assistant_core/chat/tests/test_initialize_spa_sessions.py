# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Regression: the SPA boot payload and the sidebar refetch must agree.

The bug: ``initialize_spa`` built its ``sessions`` block from ``_fetch_sessions``,
a private COPY of ``get_user_sessions`` that had drifted — it never applied the
``is_archived = 0`` filter. So a page load hydrated the sidebar with archived
conversations, and the very next in-app navigation (Usage → Chat) remounted
ChatView, refetched via ``get_user_sessions``, and replaced the list with the
correctly-filtered one. With every conversation archived the sidebar went empty
on navigation and came back on refresh.

Same failure mode as ``test_initialize_spa_access`` — a stale copy of an
endpoint diverging from the endpoint. These tests pin the boot path to the one
authoritative implementation so the two can never disagree again.
"""

from unittest.mock import patch

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestInitializeSpaSessions(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; runs in an isolated transaction
        frappe.set_user("Administrator")
        self.active_sid = "test-boot-active"
        self.archived_sid = "test-boot-archived"
        for sid, archived in ((self.active_sid, 0), (self.archived_sid, 1)):
            frappe.db.delete("FAC Chat Message", {"session_id": sid})
            frappe.get_doc(
                {
                    "doctype": "FAC Chat Message",
                    "session_id": sid,
                    "role": "user",
                    "content": f"Question in {sid}",
                    "user": "Administrator",
                    "timestamp": frappe.utils.now(),
                    "is_archived": archived,
                    "idx": 1,
                }
            ).insert(ignore_permissions=True)

    def test_boot_payload_excludes_archived_conversations(self):
        """A conversation the user archived must not come back in the boot
        payload. It reappearing is what made the sidebar shrink to nothing on
        the first in-app navigation."""
        from frappe_assistant_core.chat.api.init import _fetch_sessions

        ids = {s["session_id"] for s in _fetch_sessions(limit=100)}

        self.assertIn(self.active_sid, ids)
        self.assertNotIn(self.archived_sid, ids)

    def test_boot_payload_matches_sidebar_refetch(self):
        """The list the SPA boots with and the list it refetches on every
        ChatView remount must be the same list — otherwise the sidebar changes
        under the user for navigating."""
        from frappe_assistant_core.chat.api.chat.sessions import get_user_sessions
        from frappe_assistant_core.chat.api.init import _fetch_sessions

        boot = [s["session_id"] for s in _fetch_sessions(limit=100)]
        refetch = [s["session_id"] for s in get_user_sessions(limit=100)]

        self.assertEqual(boot, refetch)

    def test_boot_delegates_to_the_authoritative_endpoint(self):
        """Pin the delegation itself: the boot path must call
        ``get_user_sessions`` and return its result verbatim, so a future edit
        to the endpoint can't leave a second copy behind."""
        from frappe_assistant_core.chat.api import init as init_mod

        sentinel = [{"session_id": "sentinel", "preview": "p", "message_count": 1}]
        with patch(
            "frappe_assistant_core.chat.api.chat.sessions.get_user_sessions",
            return_value=sentinel,
        ) as mocked:
            result = init_mod._fetch_sessions(limit=20)

        mocked.assert_called_once()
        self.assertEqual(result, sentinel)
