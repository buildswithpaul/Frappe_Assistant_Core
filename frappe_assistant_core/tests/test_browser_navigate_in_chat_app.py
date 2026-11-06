# Frappe Assistant Core - navigate_to in the chat app
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""browser_navigate_to answers at once when the chat app holds the turn (#34515).

navigate_to never waits for the browser and always reported success. The chat app no longer
leaves for Desk on it, so on a turn the chat app holds (its own, or one it took over from the
widget) FACO must hear that the tool can't run there, and what to use instead.
"""

from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api.chat import live_turn
from frappe_assistant_core.chat.api.chat.live_turn import claim_live_turn
from frappe_assistant_core.plugins.faco.tools import browser_bridge
from frappe_assistant_core.plugins.faco.tools.browser_bridge import TURN_CLAIM_PREFIX, _pending_calls_key
from frappe_assistant_core.plugins.faco.tools.browser_navigate_to import BrowserNavigateTo
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestNavigateInChatApp(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.session_id = f"sess-nav-{frappe.generate_hash(length=8)}"
        self.addCleanup(self._clear_redis)
        # fac_endpoint sets these from AR's X-AR-Session-Id and X-AR-Client-Type headers.
        self._local = {}
        for name in ("ar_session_id", "ar_client_type"):
            self._local[name] = getattr(frappe.local, name, None)
        self.addCleanup(self._restore_local)

    def _restore_local(self):
        for name, value in self._local.items():
            setattr(frappe.local, name, value)

    def _clear_redis(self):
        frappe.cache.delete_value(f"{TURN_CLAIM_PREFIX}{self.session_id}")
        frappe.cache.delete_value(_pending_calls_key("", self.session_id))
        live_turn.clear(self.session_id)

    def _navigate(self, client_type):
        frappe.local.ar_session_id = self.session_id
        frappe.local.ar_client_type = client_type
        with patch.object(browser_bridge.frappe, "publish_realtime") as publish:
            result = BrowserNavigateTo().execute({"url": "/app/fac-pages/sales"})
        return result, publish

    def test_the_chat_apps_own_turn_is_told_to_use_the_page_screenshot(self):
        result, publish = self._navigate("spa")

        self.assertFalse(result["success"])
        self.assertIn("browser_take_screenshot", result["error"])
        publish.assert_not_called()

    def test_a_widget_turn_taken_over_by_the_chat_app_is_told_too(self):
        live_turn.start(self.session_id)
        claim_live_turn(self.session_id)

        result, publish = self._navigate("widget")

        self.assertFalse(result["success"])
        self.assertIn("browser_take_screenshot", result["error"])
        publish.assert_not_called()

    def test_the_widgets_own_turn_still_navigates(self):
        result, publish = self._navigate("widget")

        self.assertTrue(result["success"])
        self.assertEqual(publish.call_args.kwargs["message"]["client_type"], "widget")
