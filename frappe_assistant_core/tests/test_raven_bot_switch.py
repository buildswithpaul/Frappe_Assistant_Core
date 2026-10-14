# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""FAC Bot is opt-in: an administrator switches it on in FAC Admin, which creates the bot."""

import unittest

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestRavenBotSwitch(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "raven" not in frappe.get_installed_apps():
            raise unittest.SkipTest("Raven is not installed")

    def tearDown(self):
        from frappe_assistant_core.integrations.raven import bot

        frappe.set_user("Administrator")
        super().tearDown()
        # The bot rows roll back with the test; the cached state must not outlive them.
        bot.clear_state_cache()

    def test_the_switch_is_off_on_a_site_that_never_turned_it_on(self):
        # Production: a Check field on a Single reads its type default, 0, until someone saves 1.
        frappe.db.set_single_value("FAC Chat Settings", "enable_raven_bot", 0)
        from frappe_assistant_core.chat.api.settings.raven_bot import get_raven_bot

        self.assertEqual(get_raven_bot(), {"available": True, "enabled": False})

    def test_switching_on_creates_fac_bot_without_raven_ai(self):
        from frappe_assistant_core.chat.api.settings.raven_bot import set_raven_bot_enabled
        from frappe_assistant_core.integrations.raven import bot

        set_raven_bot_enabled(True)
        doc = frappe.get_doc("Raven Bot", bot.BOT_NAME)
        self.assertEqual(doc.is_ai_bot, 0)
        self.assertEqual(bot.state(), "on")

        set_raven_bot_enabled(False)
        self.assertEqual(bot.state(), "off")
        # Kept, so the bot's channel memberships and history survive switching it off.
        self.assertTrue(frappe.db.exists("Raven Bot", bot.BOT_NAME))

    def test_only_a_chat_admin_can_flip_it(self):
        from frappe_assistant_core.chat.api.settings.raven_bot import set_raven_bot_enabled

        frappe.set_user(self.make_throwaway_user("raven-switch", roles=("Desk User",)))
        with self.assertRaises(frappe.PermissionError):
            set_raven_bot_enabled(True)

    def test_raven_is_not_offered_the_widget(self):
        # Raven is a chat app with FAC Bot inside it; a floating chat widget on top is redundant.
        from frappe_assistant_core.chat.embed.apps import discover_spa_apps

        self.assertNotIn("raven", [app["app"] for app in discover_spa_apps()])

    def test_a_site_that_had_ticked_raven_no_longer_serves_the_widget_there(self):
        from frappe_assistant_core.chat.embed.apps import clear_routes_cache, enabled_routes

        # Production: an administrator ticked Raven under Other Frappe apps before this change.
        settings = frappe.get_single("FAC Chat Settings")
        settings.append("widget_embed_apps", {"app_name": "raven"})
        settings.save(ignore_permissions=True)
        clear_routes_cache()
        self.addCleanup(clear_routes_cache)
        self.assertNotIn("/raven", enabled_routes())
