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

"""
Tests for the registry-build guard on the MCP endpoint.

`initialize`, `ping`, `prompts/*` and `resources/*` never touch a tool, so the
endpoint skips building the per-request registry for them. Skipping is only safe
while the guard reads the JSON-RPC method exactly as `MCPServer.handle()` does.

`handle()` parses with `get_json(force=True)`, which ignores the Content-Type
header. A guard parsing with `get_json(silent=True)` instead sees nothing when a
client omits `application/json` — it would then skip the registry while
`handle()` still dispatches `tools/list`, fall back to the empty shared
registry, and answer with zero tools and no error anywhere. That presents to the
user as "my tools disappeared".
"""

import json

import frappe
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from frappe_assistant_core.api.fac_endpoint import _REGISTRY_METHODS, _requested_mcp_method
from frappe_assistant_core.tests.base_test import BaseAssistantTest

TOOLS_LIST = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}


class TestRequestedMCPMethod(BaseAssistantTest):
    """The guard's view of the request must match the dispatcher's."""

    def _bind(self, body, content_type="application/json"):
        """Bind a real Werkzeug request, so Content-Type behaves as in production."""
        data = body if isinstance(body, str) else json.dumps(body)
        builder = EnvironBuilder(method="POST", data=data, content_type=content_type)
        request = Request(builder.get_environ())
        original = getattr(frappe.local, "request", None)
        frappe.local.request = request
        self.addCleanup(lambda: setattr(frappe.local, "request", original))
        return request

    def test_json_content_type_is_read(self):
        self._bind(TOOLS_LIST)

        self.assertEqual(_requested_mcp_method(), "tools/list")

    def test_a_wrong_content_type_still_reads_the_method(self):
        """The bug: this returned None, so the registry was skipped and dispatch got none."""
        self._bind(TOOLS_LIST, content_type="text/plain")

        self.assertEqual(_requested_mcp_method(), "tools/list")

    def test_a_missing_content_type_still_reads_the_method(self):
        self._bind(TOOLS_LIST, content_type=None)

        self.assertEqual(_requested_mcp_method(), "tools/list")

    def test_the_guard_agrees_with_the_dispatcher_on_every_content_type(self):
        """Encodes the invariant directly: whatever handle() would dispatch, the
        guard must see, or it skips a registry the request goes on to need."""
        for content_type in ("application/json", "text/plain", "application/json; charset=utf-8", None):
            with self.subTest(content_type=content_type):
                request = self._bind(TOOLS_LIST, content_type=content_type)

                # The guard runs first, exactly as it does in the endpoint.
                # Werkzeug caches a parsed body, so asking the dispatcher first
                # would populate that cache and hide a guard that could not
                # parse this Content-Type on its own.
                guarded = _requested_mcp_method()

                # Exactly how MCPServer.handle() parses the body.
                dispatched = request.get_json(force=True).get("method")

                self.assertEqual(guarded, dispatched)
                self.assertIn(dispatched, _REGISTRY_METHODS)

    def test_a_non_registry_method_is_reported_as_itself(self):
        for method in ("initialize", "ping", "prompts/list", "resources/list"):
            with self.subTest(method=method):
                self._bind({"jsonrpc": "2.0", "id": 1, "method": method})

                resolved = _requested_mcp_method()

                self.assertEqual(resolved, method)
                self.assertNotIn(resolved, _REGISTRY_METHODS)

    def test_a_non_dict_body_does_not_raise(self):
        """`.get("method")` on a JSON list raised AttributeError out of the guard."""
        self._bind([1, 2, 3])

        self.assertIsNone(_requested_mcp_method())

    def test_a_json_scalar_body_does_not_raise(self):
        self._bind("42")

        self.assertIsNone(_requested_mcp_method())

    def test_an_unparseable_body_does_not_raise(self):
        self._bind("{not json")

        self.assertIsNone(_requested_mcp_method())

    def test_an_empty_body_does_not_raise(self):
        self._bind("")

        self.assertIsNone(_requested_mcp_method())

    def test_a_non_string_method_is_ignored(self):
        self._bind({"jsonrpc": "2.0", "id": 1, "method": {"nested": "object"}})

        self.assertIsNone(_requested_mcp_method())

    def test_no_bound_request_does_not_raise(self):
        original = getattr(frappe.local, "request", None)
        frappe.local.request = None
        self.addCleanup(lambda: setattr(frappe.local, "request", original))

        self.assertIsNone(_requested_mcp_method())
