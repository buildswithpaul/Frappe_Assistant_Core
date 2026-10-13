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

"""The after_request hook that puts the widget loader on enabled Frappe app pages."""

from unittest.mock import patch

import frappe
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request, Response

from frappe_assistant_core.chat.embed.inject import inject_widget
from frappe_assistant_core.tests.base_test import BaseAssistantTest

INJECT = "frappe_assistant_core.chat.embed.inject"
PAGE = '<html><body><div id="app"></div><script>window.csrf_token="t"</script></body></html>'
WEBSITE_USER = "test_inject_website_user@example.com"


def page(path="/helpdesk/tickets", method="GET", status=200, mimetype="text/html", body=PAGE):
    # Built as frappe.app.application has them when after_request runs: a werkzeug Request
    # from the WSGI environ and the Response the www page renderer returned.
    request = Request(EnvironBuilder(path=path, method=method).get_environ())
    return request, Response(body, status=status, mimetype=mimetype)


class TestEmbedInject(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # Production: an admin enabled Helpdesk (set_embed_app_enabled, tested in test_embed_apps)
        # and switched chat on with toggle_chat.
        self.routes = patch(f"{INJECT}.enabled_routes", autospec=True, return_value=["/helpdesk"])
        self.chat = patch(f"{INJECT}.is_chat_enabled", autospec=True, return_value=True)
        self.routes_on = self.routes.start()
        self.chat_on = self.chat.start()
        frappe.set_user("Administrator")

    def tearDown(self):
        patch.stopall()
        frappe.set_user("Administrator")
        super().tearDown()

    def assertInjected(self, response):
        html = response.get_data(as_text=True)
        self.assertEqual(html.count("widget_embed.js?v="), 1)
        self.assertTrue(html.endswith("defer></script></body></html>"))

    def assertUntouched(self, response, body=PAGE):
        self.assertEqual(response.get_data(as_text=True), body)

    def test_an_enabled_app_page_gets_the_loader_once_before_body_ends(self):
        request, response = page()
        inject_widget(response, request)
        self.assertInjected(response)

    def test_the_app_root_and_any_sub_path_get_it(self):
        for path in ("/helpdesk", "/helpdesk/", "/helpdesk/tickets/12"):
            request, response = page(path=path)
            inject_widget(response, request)
            self.assertInjected(response)

    def test_a_path_that_only_starts_with_the_route_text_does_not(self):
        request, response = page(path="/helpdeskish")
        inject_widget(response, request)
        self.assertUntouched(response)

    def test_an_app_that_is_not_enabled_does_not(self):
        request, response = page(path="/crm/leads")
        inject_widget(response, request)
        self.assertUntouched(response)

    def test_a_guest_does_not(self):
        frappe.set_user("Guest")
        request, response = page()
        inject_widget(response, request)
        self.assertUntouched(response)

    def test_a_website_user_does_not(self):
        if not frappe.db.exists("User", WEBSITE_USER):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": WEBSITE_USER,
                    "first_name": "Inject",
                    "user_type": "Website User",
                }
            ).insert(ignore_permissions=True)
        frappe.set_user(WEBSITE_USER)
        request, response = page()
        inject_widget(response, request)
        self.assertUntouched(response)

    def test_nothing_is_added_while_chat_is_off(self):
        self.chat_on.return_value = False
        request, response = page()
        inject_widget(response, request)
        self.assertUntouched(response)

    def test_errors_json_and_posts_are_left_alone(self):
        for kwargs in ({"status": 404}, {"mimetype": "application/json"}, {"method": "POST"}):
            request, response = page(**kwargs)
            inject_widget(response, request)
            self.assertUntouched(response)

    def test_a_page_without_a_body_end_is_left_alone(self):
        body = "<html><div>partial</div></html>"
        request, response = page(body=body)
        inject_widget(response, request)
        self.assertUntouched(response, body)

    def test_the_last_body_end_is_used(self):
        body = '<html><body><script>var s = "</body>";</script></body></html>'
        request, response = page(body=body)
        inject_widget(response, request)
        html = response.get_data(as_text=True)
        self.assertTrue(html.startswith('<html><body><script>var s = "</body>";</script><script src='))

    def test_a_failure_inside_the_hook_leaves_the_page_untouched(self):
        self.routes_on.side_effect = RuntimeError("redis down")
        request, response = page()
        inject_widget(response, request)
        self.assertUntouched(response)
