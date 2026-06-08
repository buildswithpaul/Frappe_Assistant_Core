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
Concurrency regression tests for the MCP server tool registry.

Regression tests for: https://github.com/buildswithpaul/Frappe_Assistant_Core/issues/197

Background
----------
The MCP endpoint uses a single module-level ``MCPServer`` instance. The old
request flow cleared and repopulated that instance's shared ``_tool_registry``
on every request:

    mcp._tool_registry.clear()
    register_base_tool(mcp, tool_instance)   # repeated per tool

With concurrent ``tools/call`` requests handled in the same worker, one request
could ``clear()`` the registry while another was validating or executing a tool
against it. Symptoms reported in #197:

  * an in-flight call failing with "Tool '<name>' not found. Available tools:
    [...]" even though the tool exists, and
  * only one of several concurrent executions making it into Assistant Audit
    Log.

The fix (Option A) builds a per-request tool registry on the call stack and
passes it into ``MCPServer.handle()``. No request mutates shared state, so
concurrent requests are isolated.

These tests exercise ``MCPServer.handle()`` directly with mocked Werkzeug
requests, which is the layer where the race lived. The test tool overrides
``log_execution`` to a no-op so tool execution stays entirely in memory — the
threaded test never opens a DB connection and therefore never escapes the test
runner's transaction/rollback boundary.
"""

import json
import threading
import time
from collections import OrderedDict
from typing import Any, Dict
from unittest.mock import MagicMock

import frappe
from werkzeug.wrappers import Response

from frappe_assistant_core.core.base_tool import BaseTool
from frappe_assistant_core.mcp.server import MCPServer
from frappe_assistant_core.mcp.tool_adapter import build_tool_dict
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class _SlowEchoTool(BaseTool):
    """A BaseTool that sleeps briefly (to force request overlap) then echoes.

    The sleep widens the window in which two requests are simultaneously inside
    ``handle()`` — under the old shared-registry code this is exactly when one
    request's ``clear()`` corrupted another's lookup. ``log_execution`` is a
    no-op so executing the tool never touches the database, keeping the threaded
    test free of cross-connection state.
    """

    def __init__(self, name: str, delay: float = 0.02):
        super().__init__()
        self.name = name
        self.description = "Concurrency test tool"
        self.inputSchema = {
            "type": "object",
            "properties": {"doc": {"type": "string"}},
        }
        self.requires_permission = None  # skip the DocType permission check
        self.source_app = "frappe_assistant_core"
        self._delay = delay

    def execute(self, arguments: Dict[str, Any]) -> Any:
        if self._delay:
            time.sleep(self._delay)
        return {"echo": arguments.get("doc")}

    def log_execution(self, *args, **kwargs):
        # No-op: keep execution in memory so threads need no DB connection.
        return None


def _make_request(tool_name: str, doc: str, request_id: int) -> MagicMock:
    """Build a mock Werkzeug request carrying a tools/call JSON-RPC payload."""
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": {"doc": doc}},
    }
    request = MagicMock()
    request.method = "POST"
    # Real dict so .get("mcp-protocol-version") works on the global proxy path.
    request.headers = {}
    request.get_json.return_value = payload
    request.get_data.return_value = json.dumps(payload)
    return request


def _handle(server: MCPServer, request: MagicMock, tool_registry) -> Response:
    """Call server.handle with the mock bound to frappe.local.request.

    MCPServer reads the global ``frappe.request`` proxy (e.g. for the
    mcp-protocol-version response header), which is unbound under tests unless we
    bind a request onto ``frappe.local``. ``frappe.local`` is thread-local, so a
    worker thread must bind its own request; this helper does that for whichever
    thread calls it.
    """
    frappe.local.request = request
    return server.handle(request, Response(), tool_registry=tool_registry)


def _registry_with(*tools) -> "OrderedDict[str, dict]":
    """Build a per-request registry dict from BaseTool instances."""
    reg = OrderedDict()
    for tool in tools:
        reg[tool.name] = build_tool_dict(tool)
    return reg


def _result_of(response: Response) -> Dict[str, Any]:
    """Parse a JSON-RPC Response body and return its ``result`` payload."""
    body = json.loads(response.get_data(as_text=True))
    return body.get("result", {})


class TestMCPRegistryIsolation(BaseAssistantTest):
    """A request must route against the registry passed into handle(), never a
    shared/global one — this is the core of the #197 fix."""

    def test_handle_uses_per_request_registry_not_shared(self):
        """A tool present only in the per-request registry must be callable even
        when the server's shared registry is empty.

        Under the old code, ``_handle_tools_call`` read ``self._tool_registry``,
        so a tool absent from the shared singleton produced "tool not found".
        """
        server = MCPServer("test")
        self.assertEqual(len(server._tool_registry), 0, "shared registry should start empty")

        tool = _SlowEchoTool("only_in_request_registry", delay=0)
        request = _make_request(tool.name, "DOC-1", request_id=1)

        response = _handle(server, request, _registry_with(tool))
        result = _result_of(response)

        self.assertFalse(result.get("isError"), f"unexpected error: {result}")
        self.assertIn("DOC-1", result["content"][0]["text"])

    def test_mutating_shared_registry_does_not_affect_in_flight_request(self):
        """Clearing the shared singleton (the old per-request side effect) must
        have zero impact on a request that carries its own registry."""
        server = MCPServer("test")
        tool = _SlowEchoTool("isolated_tool", delay=0)
        per_request = _registry_with(tool)

        # Simulate another request wiping the shared registry mid-flight.
        server._tool_registry.clear()

        response = _handle(server, _make_request(tool.name, "DOC-2", 2), per_request)
        result = _result_of(response)

        self.assertFalse(result.get("isError"), f"unexpected error: {result}")
        self.assertIn("DOC-2", result["content"][0]["text"])

    def test_distinct_registries_route_independently(self):
        """Two requests carrying disjoint registries each resolve only their own
        tool — a stand-in for two concurrent users with different tool sets. The
        shared singleton is empty, so any leakage would surface as 'not found'.
        """
        server = MCPServer("test")
        tool_a = _SlowEchoTool("tool_a", delay=0)
        tool_b = _SlowEchoTool("tool_b", delay=0)

        # Request for A sees only tool_a; request for B sees only tool_b.
        resp_a = _handle(server, _make_request("tool_a", "A", 1), _registry_with(tool_a))
        resp_b = _handle(server, _make_request("tool_b", "B", 2), _registry_with(tool_b))
        self.assertFalse(_result_of(resp_a).get("isError"))
        self.assertFalse(_result_of(resp_b).get("isError"))

        # A's registry must not expose B's tool, and vice versa.
        cross = _handle(server, _make_request("tool_b", "X", 3), _registry_with(tool_a))
        self.assertTrue(_result_of(cross).get("isError"))
        self.assertIn("not found", _result_of(cross)["content"][0]["text"])


class TestMCPConcurrentToolsCall(BaseAssistantTest):
    """End-to-end: N overlapping tools/call requests against one shared
    MCPServer must all succeed, with no spurious 'tool not found'.

    Execution stays in memory (the tool's ``log_execution`` is a no-op), so the
    worker threads need no DB connection and nothing escapes the test runner's
    rollback. This isolates the property under test — registry isolation under
    concurrency — from Frappe's per-thread DB-context mechanics.
    """

    def test_concurrent_calls_do_not_corrupt_registry(self):
        server = MCPServer("test")
        tool = _SlowEchoTool("concurrent_tool", delay=0.03)

        n = 8
        docs = [f"DOC-{i}" for i in range(n)]
        results: Dict[int, Dict[str, Any]] = {}
        errors: list = []
        start_barrier = threading.Barrier(n)
        results_lock = threading.Lock()

        # Each thread mimics one concurrent request hitting the same worker: its
        # own per-request tool registry (as the endpoint now builds) handed to a
        # shared MCPServer instance — the production module-level singleton.
        def run_call(index: int):
            try:
                start_barrier.wait()  # release all threads together to maximise overlap
                per_request = _registry_with(tool)
                request = _make_request(tool.name, docs[index], request_id=index)
                response = _handle(server, request, per_request)
                with results_lock:
                    results[index] = _result_of(response)
            except Exception as e:  # pragma: no cover - surfaced via assertion below
                with results_lock:
                    errors.append(f"thread {index}: {type(e).__name__}: {e}")

        threads = [threading.Thread(target=run_call, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        self.assertEqual(errors, [], f"threads raised: {errors}")
        self.assertEqual(len(results), n, "every request should have produced a result")

        # No request saw a corrupted registry ("tool not found"), and each got
        # its own arguments back — proving the in-flight calls did not clobber
        # one another's registry or routing.
        for index, result in results.items():
            self.assertFalse(
                result.get("isError"),
                f"request {index} failed (registry corruption regression): {result}",
            )
            self.assertIn(docs[index], result["content"][0]["text"])
