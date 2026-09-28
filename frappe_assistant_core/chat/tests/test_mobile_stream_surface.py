# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""The FAC mobile app's server surface after the legacy SSE endpoints went (spec §8.2).

The app streams through ``send_message`` and the socket relay, like the SPA.
The old SSE ``stream_chat`` skipped the session-owner and processing-restriction
checks, ignored zero retention and never persisted blocks, and ``get_sessions``
and ``search_sessions`` listed archived conversations. Nothing called them, so
this pins that they stay gone and that the three helpers the app does use stay.
"""

import unittest

import frappe

from frappe_assistant_core.chat import api
from frappe_assistant_core.chat.api import mobile_stream, models

REMOVED_FROM_MODULE = (
    "stream_chat",
    "get_sessions",
    "get_messages",
    "search_sessions",
    "get_available_models",
    "_stream_generator",
    "_format_sse_event",
    "_extract_file_attachments",
    "_log_conversation",
    "_update_subscription_cache",
)
REMOVED_FROM_PACKAGE = (
    "stream_chat",
    "get_sessions",
    "get_messages",
    "search_sessions",
    "mobile_get_available_models",
)
KEPT_GET_ENDPOINTS = ("get_socket_session", "create_web_session", "download_file_by_token")


class TestMobileStreamSurface(unittest.TestCase):
    def test_the_legacy_endpoints_and_their_helpers_are_gone(self):
        for name in REMOVED_FROM_MODULE:
            with self.subTest(name=name):
                self.assertFalse(
                    hasattr(mobile_stream, name), f"mobile_stream.{name} was deleted (spec §8.2)"
                )

    def test_the_package_no_longer_re_exports_them(self):
        for name in REMOVED_FROM_PACKAGE:
            with self.subTest(name=name):
                self.assertFalse(hasattr(api, name), f"chat.api.{name} was deleted (spec §8.2)")

    def test_the_spa_model_list_still_resolves(self):
        self.assertIs(api.get_available_models, models.get_available_models)

    def test_the_helpers_the_app_uses_stay_whitelisted_for_get(self):
        for name in KEPT_GET_ENDPOINTS:
            with self.subTest(name=name):
                endpoint = getattr(mobile_stream, name)
                self.assertIn(endpoint, frappe.whitelisted)
                self.assertEqual(frappe.allowed_http_methods_for_whitelisted_func[endpoint], ["GET"])
