# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""The "Bring your data in" starter is offered only where migration is enabled and the
user can import: the server says so through ``bring_data_in`` on the suggestions payload."""

from unittest.mock import create_autospec, patch

import frappe

from frappe_assistant_core.chat.api.prompts import can_bring_data_in, get_suggested_prompts
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.plugin_manager import PluginManager


class TestBringDataInFlag(BaseAssistantTest):
    def tearDown(self):
        # nosemgrep: frappe-setuser — restore the suite's user after acting as another
        frappe.set_user("Administrator")
        super().tearDown()

    def enabled_plugins(self, *names):
        """The plugin manager reports ``names`` as enabled; nothing is enabled or committed.

        Production reaches the same state by the admin enabling plugins in Assistant Core
        Settings, which the manager reads back from the database.
        """
        manager = create_autospec(PluginManager, instance=True)
        manager.get_enabled_plugins.return_value = set(names)
        patcher = patch("frappe_assistant_core.utils.plugin_manager.get_plugin_manager", return_value=manager)
        patcher.start()
        self.addCleanup(patcher.stop)

    def act_as(self, user):
        # nosemgrep: frappe-setuser — the flag is per session user
        frappe.set_user(user)

    def test_true_with_plugin_and_system_manager(self):
        self.enabled_plugins("core", "migration")
        self.act_as(self.make_throwaway_user("sysmgr", roles=("System Manager",)))
        self.assertTrue(can_bring_data_in())

    def test_false_without_the_plugin(self):
        self.enabled_plugins("core")
        self.act_as(self.make_throwaway_user("sysmgr", roles=("System Manager",)))
        self.assertFalse(can_bring_data_in())

    def test_false_for_a_user_who_cannot_import(self):
        self.enabled_plugins("core", "migration")
        user = self.make_desk_user("noimport")
        self.assert_cannot(user, "create", "Data Import")
        self.act_as(user)
        self.assertFalse(can_bring_data_in())

    @patch(
        "frappe_assistant_core.chat.api.prompts._get_template_suggestions",
        return_value=([], {"templates": [], "categories": [], "pinned": []}),
    )
    def test_the_suggestions_payload_carries_the_flag(self, _templates):
        self.enabled_plugins("migration")
        self.act_as(self.make_throwaway_user("sysmgr", roles=("System Manager",)))
        self.assertIs(get_suggested_prompts()["bring_data_in"], True)
        self.act_as(self.make_desk_user("noimport"))
        self.assertIs(get_suggested_prompts()["bring_data_in"], False)
