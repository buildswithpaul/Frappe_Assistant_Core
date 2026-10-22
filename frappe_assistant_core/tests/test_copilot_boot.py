# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""The FAC Chat page's boot data carries the site's own address for same-site links."""

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.www.copilot import get_boot


class TestCopilotBoot(BaseAssistantTest):
    def test_boot_carries_the_site_url(self):
        # The SPA turns links to this address into relative ones (Redmine #34378), so it must be
        # the same address answers link to: get_url(), which honours host_name.
        boot = get_boot()
        self.assertEqual(boot.get("site_url"), frappe.utils.get_url())
