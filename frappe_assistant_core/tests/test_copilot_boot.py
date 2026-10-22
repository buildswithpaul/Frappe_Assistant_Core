# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""The FAC Chat page's boot data carries the site's own address for same-site links."""

from unittest.mock import patch

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.www import copilot
from frappe_assistant_core.www.copilot import get_boot


class TestCopilotBoot(BaseAssistantTest):
    def test_boot_carries_the_site_url(self):
        # The SPA turns links to this address into relative ones (Redmine #34378), so it must be
        # the same address answers link to: get_url(), which honours host_name.
        boot = get_boot()
        self.assertEqual(boot.get("site_url"), frappe.utils.get_url())

    def test_signed_out_visitor_gets_a_temporary_redirect_to_login(self):
        # Redmine #34442: a permanent (301) redirect can be cached and keep bouncing after sign-in.
        # Manufactured: production reaches this once an administrator switches FAC Chat on.
        previous = frappe.session.user
        self.addCleanup(frappe.set_user, previous)
        frappe.set_user("Guest")

        with patch.object(copilot, "is_chat_enabled", autospec=True, return_value=True):
            with self.assertRaises(frappe.Redirect) as raised:
                copilot.get_context(frappe._dict())

        self.assertEqual(raised.exception.http_status_code, 302)
        self.assertTrue(frappe.local.flags.redirect_location.startswith("/login?redirect-to="))
