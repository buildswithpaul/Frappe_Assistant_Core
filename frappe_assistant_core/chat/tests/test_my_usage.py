# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Tests for ``get_my_usage``: per-member usage, scoped server-side to the session user."""

from unittest.mock import create_autospec, patch

import frappe
from assistant_runtime_sdk import AssistantRuntimeClient

from frappe_assistant_core.tests.base_test import BaseAssistantTest

CLIENT_PATH = "frappe_assistant_core.chat.api.analytics._get_client"


class TestMyUsage(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")  # nosemgrep: frappe-setuser — reset to the test default
        self.client = create_autospec(AssistantRuntimeClient, instance=True)
        self.client.get_token_analytics.return_value = {
            "period": {"days": 30},
            "summary": {"total_credits": 5},
            "daily": [],
            "by_model": [],
            "by_source": [],
            "by_team": [{"team": "x", "credits": 1}],
            "by_user": [{"user_id": "someone-else@example.com", "credits": 99}],
        }

    def tearDown(self):
        frappe.set_user("Administrator")  # nosemgrep: frappe-setuser — restore the test default
        super().tearDown()

    def _as_member(self) -> str:
        # Production reaches this as any logged-in seated member; seating is not a Frappe role.
        email = self.make_throwaway_user("my-usage")
        frappe.set_user(email)  # nosemgrep: frappe-setuser — act as a non-admin member
        return email

    def _call(self, **kwargs):
        from frappe_assistant_core.chat.api import get_my_usage

        with patch(CLIENT_PATH, return_value=self.client):
            return get_my_usage(**kwargs)

    def test_scoped_to_the_session_user(self):
        email = self._as_member()
        self._call()
        self.client.get_token_analytics.assert_called_once_with(days=30, user_id=email)

    def test_never_returns_by_user(self):
        self._as_member()
        res = self._call()
        self.assertNotIn("by_user", res)
        self.assertEqual(set(res), {"period", "summary", "daily", "by_model", "by_source"})

    def test_days_are_clamped(self):
        self._as_member()
        self._call(days=45)
        self.assertEqual(self.client.get_token_analytics.call_args.kwargs["days"], 30)
        self._call(days="90")
        self.assertEqual(self.client.get_token_analytics.call_args.kwargs["days"], 90)
        for bad in (None, -7):
            self._call(days=bad)
            self.assertEqual(self.client.get_token_analytics.call_args.kwargs["days"], 30)

    def test_administrator_is_queried_by_email(self):
        self._call()
        expected = frappe.db.get_value("User", "Administrator", "email")
        self.assertEqual(self.client.get_token_analytics.call_args.kwargs["user_id"], expected)

    def test_empty_ar_user_id_is_refused(self):
        self._as_member()
        with patch("frappe_assistant_core.chat.api.auth._ar_user_id", return_value=""):
            with self.assertRaises(frappe.PermissionError):
                self._call()
        self.client.get_token_analytics.assert_not_called()

    def test_guest_is_refused(self):
        frappe.set_user("Guest")  # nosemgrep: frappe-setuser — an anonymous request runs as Guest
        with self.assertRaises(frappe.PermissionError):
            self._call()

    def test_admin_endpoints_stay_admin_only(self):
        self._as_member()
        from frappe_assistant_core.chat.api.analytics import get_analytics_data

        with patch(CLIENT_PATH, return_value=self.client), self.assertRaises(frappe.PermissionError):
            get_analytics_data()
