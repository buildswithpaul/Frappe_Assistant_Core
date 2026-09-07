# Frappe Assistant Core - browser diagnostics tool tests
# Copyright (C) 2025 Paul Clinton
#
# AGPL-3.0 License

"""The composite diagnostics tool.

A screenshot alone cannot explain a Frappe error — the dialog truncates the
traceback and the real payload is in the XHR response. This tool exists so the
model gathers all three signals in one approved call instead of choosing one.
"""

from unittest.mock import patch

from frappe_assistant_core.plugins.faco.plugin import FacoPlugin
from frappe_assistant_core.plugins.faco.tools.browser_capture_diagnostics import (
    BrowserCaptureDiagnostics,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestBrowserCaptureDiagnostics(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.tool = BrowserCaptureDiagnostics()

    def test_registered_by_the_plugin(self):
        self.assertIn("browser_capture_diagnostics", FacoPlugin().get_tools())

    def test_routes_to_the_widget_handler(self):
        self.assertEqual(self.tool.tool_name, "capture_diagnostics")

    def test_budget_exceeds_the_screenshot_budget(self):
        # The composite takes a screenshot AND drains buffers; a 45s budget
        # would time out mid-capture on the screenshot alone.
        self.assertGreater(self.tool._timeout, 45)

    def test_description_directs_the_model_to_use_it_first(self):
        description = self.tool.description.lower()
        self.assertIn("error", description)
        self.assertNotIn("prefer browser_get_page_context", description)

    def test_description_does_not_overpromise_the_traceback(self):
        # `exc` is only ever present for a dev server or a system user with
        # allow_error_traceback on (frappe.utils.response.is_traceback_allowed);
        # an ordinary business user in production never gets it. The copy must
        # promise what's always there (error type + server message) and name
        # the traceback as conditional, not guaranteed.
        description = self.tool.description.lower()
        self.assertNotIn("including the frappe traceback", description)
        self.assertIn("when available", description)

    def test_defaults_include_a_screenshot(self):
        params = self.tool.get_tool_params({})
        self.assertTrue(params["include_screenshot"])

    def test_since_seconds_default_matches_the_recorder_drain_window(self):
        """The drain window must equal the hint window, not a narrower one.

        counts() (the hint) ages entries out at MAX_AGE_MS = 300s. If
        since_seconds defaulted to anything less, an entry between the two
        cutoffs would trigger the hint and then have the drain return
        nothing for it — the exact bug FIX 1 set out to kill, reopened in a
        narrower band. Pinning the default to the schema's own maximum (not
        an independently-chosen number) is what keeps the two from drifting
        apart again.
        """
        schema_max = self.tool.inputSchema["properties"]["since_seconds"]["maximum"]
        params = self.tool.get_tool_params({})
        self.assertEqual(params["since_seconds"], 300)
        self.assertEqual(params["since_seconds"], schema_max)

    def test_caller_can_skip_the_screenshot(self):
        params = self.tool.get_tool_params({"include_screenshot": False})
        self.assertFalse(params["include_screenshot"])

    def test_attaches_image_content_when_a_screenshot_came_back(self):
        widget_result = {
            "success": True,
            "console": [],
            "network": [],
            "screenshot": {"file_url": "/files/shot.jpg"},
        }
        with patch.object(
            BrowserCaptureDiagnostics.__bases__[0], "execute", return_value=widget_result
        ), patch(
            "frappe_assistant_core.plugins.faco.tools.screenshot_vision.read_image_content",
            return_value={"format": "jpeg", "data": "QUJD"},
        ):
            result = self.tool.execute({})

        self.assertEqual(result["_image_content"]["data"], "QUJD")

    def test_survives_a_result_with_no_screenshot(self):
        widget_result = {"success": True, "console": [], "network": []}
        with patch.object(BrowserCaptureDiagnostics.__bases__[0], "execute", return_value=widget_result):
            result = self.tool.execute({})

        self.assertNotIn("_image_content", result)
        self.assertTrue(result["success"])

    def test_screenshot_tool_no_longer_argues_against_itself(self):
        from frappe_assistant_core.plugins.faco.tools.browser_take_screenshot import (
            BrowserTakeScreenshot,
        )

        self.assertNotIn("prefer browser_get_page_context", BrowserTakeScreenshot().description.lower())
