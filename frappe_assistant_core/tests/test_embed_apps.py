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

"""Which standalone Frappe apps can show the FACO widget, and which an admin switched on."""

from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api.settings.embed import (
    get_embed_apps,
    get_widget_entry,
    set_embed_app_enabled,
)
from frappe_assistant_core.chat.embed.apps import (
    clear_routes_cache,
    discover_spa_apps,
    enabled_routes,
    normalise_route,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest

APPS = "frappe_assistant_core.chat.embed.apps"
EMBED_API = "frappe_assistant_core.chat.api.settings.embed"
# CI installs no standalone Frappe app; production discovers this entry from Helpdesk's
# add_to_apps_screen hook.
HELPDESK = [{"app": "helpdesk", "title": "Helpdesk", "route": "/helpdesk"}]
WEBSITE_USER = "test_embed_website_user@example.com"


class TestEmbedApps(BaseAssistantTest):
    def tearDown(self):
        # frappe.cache is Redis: the test rollback does not undo it.
        clear_routes_cache()
        super().tearDown()

    def test_routes_are_normalised_and_desk_routes_refused(self):
        self.assertEqual(normalise_route("helpdesk/"), "/helpdesk")
        self.assertEqual(normalise_route("/desktop"), "/desktop")
        for route in ("/desk", "/desk/fac-admin", "/app", "/app/build", "/", "", None, 42):
            self.assertIsNone(normalise_route(route), route)

    def test_discovery_never_offers_a_desk_route(self):
        for app in discover_spa_apps():
            self.assertIsNotNone(normalise_route(app["route"]), app)
        self.assertNotIn("frappe_assistant_core", [a["app"] for a in discover_spa_apps()])

    def test_discovery_offers_helpdesk_when_it_is_installed(self):
        if "helpdesk" not in frappe.get_installed_apps():
            self.skipTest("Helpdesk is not installed on this site")
        self.assertIn({"app": "helpdesk", "title": "Helpdesk", "route": "/helpdesk"}, discover_spa_apps())

    def test_enabling_an_app_serves_its_route(self):
        with patch(f"{APPS}.discover_spa_apps", autospec=True, return_value=HELPDESK):
            set_embed_app_enabled("helpdesk", True)
            self.assertEqual(enabled_routes(), ["/helpdesk"])
            self.assertEqual(get_embed_apps(), [{**HELPDESK[0], "enabled": True}])

    def test_disabling_an_app_takes_effect_without_a_restart(self):
        with patch(f"{APPS}.discover_spa_apps", autospec=True, return_value=HELPDESK):
            set_embed_app_enabled("helpdesk", True)
            self.assertEqual(enabled_routes(), ["/helpdesk"])  # now cached
            set_embed_app_enabled("helpdesk", False)
            self.assertEqual(enabled_routes(), [])

    def test_enabling_twice_keeps_one_row(self):
        with patch(f"{APPS}.discover_spa_apps", autospec=True, return_value=HELPDESK):
            set_embed_app_enabled("helpdesk", True)
            set_embed_app_enabled("helpdesk", True)
        rows = frappe.get_single("FAC Chat Settings").widget_embed_apps
        # BaseAssistantTest rolls back per class, so other tests' rows may be present too.
        self.assertEqual([r.app_name for r in rows].count("helpdesk"), 1)

    def test_an_app_that_is_not_discovered_is_refused(self):
        with patch(f"{APPS}.discover_spa_apps", autospec=True, return_value=HELPDESK):
            with self.assertRaises(frappe.ValidationError):
                set_embed_app_enabled("not_an_app", True)

    def test_a_row_for_an_app_no_longer_installed_serves_nothing(self):
        # A row can outlive its app: Helpdesk uninstalled after an admin enabled it.
        settings = frappe.get_single("FAC Chat Settings")
        settings.set("widget_embed_apps", [{"app_name": "uninstalled_app"}])
        settings.save(ignore_permissions=True)
        with patch(f"{APPS}.discover_spa_apps", autospec=True, return_value=HELPDESK):
            self.assertEqual(enabled_routes(), [])

    def test_the_endpoints_refuse_a_user_who_cannot_manage_chat(self):
        if not frappe.db.exists("User", WEBSITE_USER):
            frappe.get_doc(
                {"doctype": "User", "email": WEBSITE_USER, "first_name": "Embed", "user_type": "Website User"}
            ).insert(ignore_permissions=True)
        frappe.set_user(WEBSITE_USER)
        try:
            with self.assertRaises(frappe.PermissionError):
                get_embed_apps()
            with self.assertRaises(frappe.PermissionError):
                set_embed_app_enabled("helpdesk", True)
        finally:
            frappe.set_user("Administrator")

    def test_get_widget_entry_returns_the_built_entry(self):
        entry = {"entry": "/assets/frappe_assistant_core/chat/widget-app/assets/main.abc.js", "css": []}
        # Production reads this from the Vite manifest that `yarn build` writes.
        with patch(f"{EMBED_API}.widget_entry", autospec=True, return_value=entry):
            self.assertEqual(get_widget_entry(), entry)


class TestSupportedApps(BaseAssistantTest):
    """The widget is offered only in apps FACO has been built and tested for."""

    def tearDown(self):
        clear_routes_cache()
        super().tearDown()

    def test_only_supported_apps_are_offered(self):
        offered = {a["app"] for a in discover_spa_apps()}
        installed = set(frappe.get_installed_apps())
        self.assertEqual(offered, {"helpdesk", "insights", "crm"} & installed)
        self.assertNotIn("builder", offered)

    def test_a_row_saved_for_an_unsupported_app_serves_nothing(self):
        if "builder" not in frappe.get_installed_apps():
            self.skipTest("Builder is not installed")
        # An admin could enable Builder before the allowlist existed; that row stays in the table.
        settings = frappe.get_single("FAC Chat Settings")
        settings.append("widget_embed_apps", {"app_name": "builder"})
        settings.save(ignore_permissions=True)
        # The routes cache from before the upgrade still lists /builder; only migrate runs next.
        frappe.cache().set_value("fac_widget_embed_routes", ["/builder"])
        self.assertIn(
            "frappe_assistant_core.chat.embed.apps.clear_routes_cache", frappe.get_hooks("after_migrate")
        )
        frappe.get_attr("frappe_assistant_core.chat.embed.apps.clear_routes_cache")()
        self.assertNotIn("/builder", enabled_routes())
