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
Request-level tests for the MCP 2026-07-28 era served by ``MCPServer.handle``, and the
handshake-era snapshot that proves older clients see no change.
"""

import json
import os
from collections import OrderedDict

import frappe
from werkzeug.datastructures import Headers
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request, Response

from frappe_assistant_core.api.fac_endpoint import _build_tool_registry, mcp
from frappe_assistant_core.mcp.protocol import (
    META_CAPABILITIES,
    META_VERSION,
    TASKS_EXT,
    ClientCaps,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.migration_hooks import _install_system_skills

MODERN = "2026-07-28"
SNAPSHOT_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "mcp_handshake_snapshot.json")
# Fixed names so the snapshot never depends on what else a site has installed.
FIXTURE_ROLE = "System Manager"
# System skills with no requires_app, so they are listed on every CI bench (a CRM skill is not).
SNAPSHOT_SKILLS = ("add-custom-field", "attach-chat-file-usage", "set-up-approval-workflow")
# Of the fixture record, only what every supported Frappe version and site gives the same.
STORED_CONTENT = "<the skill's stored content, exactly>"
SNAPSHOT_RECORD_KEYS = ("doctype", "name", "role_name")


MCP_ENDPOINT_PATH = "/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp"


def _request(body: dict, headers: dict | None = None) -> Request:
    """A real POST to the MCP endpoint: the tools a request runs (an import, a report) may read
    any attribute of frappe.local.request, as Frappe does, so a mock would answer with mocks."""
    builder = EnvironBuilder(
        method="POST",
        path=MCP_ENDPOINT_PATH,
        headers=Headers(headers or {}),
        data=json.dumps(body),
        content_type="application/json",
    )
    return Request(builder.get_environ())


def _modern(method: str, params: dict | None = None, *, caps: dict | None = None, **overrides):
    """Return ``(body, headers)`` for a well-formed modern-era request."""
    params = dict(params or {})
    params["_meta"] = {META_VERSION: MODERN, META_CAPABILITIES: caps or {}}
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    headers = {"MCP-Protocol-Version": MODERN, "Mcp-Method": method}
    if method == "tools/call":
        headers["Mcp-Name"] = params.get("name", "")
    if method == "resources/read":
        headers["Mcp-Name"] = params.get("uri", "")
    headers.update(overrides)
    return body, headers


def _send(body: dict, headers: dict | None = None, registry=None) -> Response:
    request = _request(body, headers)
    original = getattr(frappe.local, "request", None)
    frappe.local.request = request
    try:
        return mcp.handle(
            request, Response(), tool_registry=registry if registry is not None else OrderedDict()
        )
    finally:
        frappe.local.request = original


def _json(response: Response) -> dict:
    return json.loads(response.get_data(as_text=True))


def _normalise(value):
    """Drop what changes from run to run: timestamps and the per-call timing a record carries."""
    volatile = {"creation", "modified", "execution_time", "last_sync", "last_synced"}
    if isinstance(value, dict):
        return {k: _normalise(v) for k, v in value.items() if k not in volatile}
    if isinstance(value, list):
        return [_normalise(v) for v in value]
    if isinstance(value, str):
        # A tools/call result is JSON text inside a string, so volatile keys hide in it too.
        try:
            parsed = json.loads(value)
        except ValueError:
            return value
        if isinstance(parsed, (dict, list)):
            return json.dumps(_normalise(parsed), sort_keys=True)
    return value


def _stable_record(call_result: dict) -> dict:
    """Cut a get_document result down to ``SNAPSHOT_RECORD_KEYS``: the full Role record varies with
    the installed Frappe version and with local edits."""
    text = call_result["result"]["content"][0]["text"]
    payload = json.loads(text)
    data = payload.get("data", {})
    call_result["result"]["content"][0]["text"] = json.dumps(
        {"success": payload.get("success"), "data": {k: data.get(k) for k in SNAPSHOT_RECORD_KEYS}},
        sort_keys=True,
    )
    return call_result


def build_handshake_snapshot() -> dict:
    """Run the five handshake-era calls and return their normalised responses.

    The fixture embeds the get_document tool description and the skills' descriptions, so
    regenerate it with ``write_snapshot`` (on code that still serves handshake clients unchanged)
    when those change on purpose.

    Normalised: ``creation``/``modified`` and timing keys (change every run); tools/call keeps only
    ``SNAPSHOT_RECORD_KEYS`` of the record. tools/list is limited to ``get_document`` and
    resources/list to ``SNAPSHOT_SKILLS``, because which other tools and skills exist depends on
    the site, not on the code under test.
    """
    settings = frappe.get_single("Assistant Core Settings")
    # skill_mode "supplementary" is the shipped default; set it so a site's own setting can't leak in.
    settings.skill_mode = "supplementary"
    settings.save(ignore_permissions=True)
    # after_migrate installs the system skills from docs/skills on every site, as CI's fresh install
    # does; a dev site whose rows predate the latest skill text would otherwise serve older text.
    _install_system_skills()

    full = _build_tool_registry()
    registry = OrderedDict((name, full[name]) for name in ("get_document",) if name in full)
    headers = {"MCP-Protocol-Version": "2025-06-18"}

    def call(request_id, method, params):
        body = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        return _normalise(_json(_send(body, headers if method != "initialize" else {}, registry)))

    snapshot = {
        "initialize": call(1, "initialize", {"protocolVersion": "2025-06-18", "clientInfo": {"name": "t"}}),
        "tools/list": call(2, "tools/list", {}),
        "resources/list": call(3, "resources/list", {}),
        "tools/call": _stable_record(
            call(
                5,
                "tools/call",
                {"name": "get_document", "arguments": {"doctype": "Role", "name": FIXTURE_ROLE}},
            )
        ),
    }
    listing = snapshot["resources/list"]["result"]
    wanted = {f"fac://skills/{skill_id}" for skill_id in SNAPSHOT_SKILLS}
    listing["resources"] = sorted(
        (r for r in listing["resources"] if r["uri"] in wanted), key=lambda r: r["uri"]
    )
    snapshot["resources/read"] = call(4, "resources/read", {"uri": f"fac://skills/{SNAPSHOT_SKILLS[0]}"})
    # The skill's text is what Frappe's sanitiser left of docs/skills on save, which differs between
    # Frappe versions; the handshake contract is that the read returns exactly the stored content.
    for content in snapshot["resources/read"].get("result", {}).get("contents", []):
        stored = frappe.db.get_value("FAC Skill", {"skill_id": SNAPSHOT_SKILLS[0]}, "content")
        if content.get("text") == stored:
            content["text"] = STORED_CONTENT
    return snapshot


def write_snapshot():
    """One-off: ``bench execute`` this on unmodified code to (re)generate the fixture."""
    snapshot = build_handshake_snapshot()
    with open(SNAPSHOT_PATH, "w") as handle:
        json.dump(snapshot, handle, indent=2, sort_keys=True)
        handle.write("\n")
    frappe.db.rollback()


class TestHandshakeUnchanged(BaseAssistantTest):
    def test_handshake_unchanged(self):
        """Handshake-era clients get byte-for-byte what they got before the modern era existed."""
        with open(SNAPSHOT_PATH) as handle:
            expected = json.load(handle)
        self.assertEqual(build_handshake_snapshot(), expected)

    def test_handshake_ping_still_answers(self):
        body = {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}}
        response = _send(body, {"MCP-Protocol-Version": "2025-06-18"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(_json(response)["result"], {})

    def test_server_discover_on_handshake_header_is_method_not_found(self):
        body = {"jsonrpc": "2.0", "id": 1, "method": "server/discover", "params": {}}
        response = _send(body, {"MCP-Protocol-Version": "2025-06-18"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(_json(response)["error"]["code"], -32601)


class TestModernEra(BaseAssistantTest):
    def test_discover_without_initialize(self):
        body, headers = _modern("server/discover")
        response = _send(body, headers)
        result = _json(response)["result"]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(result["resultType"], "complete")
        self.assertIn(MODERN, result["supportedVersions"])
        self.assertIn(TASKS_EXT, result["capabilities"]["extensions"])
        self.assertIn("io.modelcontextprotocol/skills", result["capabilities"]["extensions"])

    def test_modern_tools_list_decorated(self):
        body, headers = _modern("tools/list")
        result = _json(_send(body, headers, _build_tool_registry()))["result"]

        self.assertEqual(result["resultType"], "complete")
        self.assertEqual(result["cacheScope"], "private")
        self.assertEqual(result["ttlMs"], 300000)
        self.assertEqual(result["_meta"]["io.modelcontextprotocol/serverInfo"]["name"], mcp.name)
        self.assertTrue(result["tools"])

    def test_modern_tools_call_is_decorated_without_cache_fields(self):
        body, headers = _modern(
            "tools/call", {"name": "get_document", "arguments": {"doctype": "Role", "name": FIXTURE_ROLE}}
        )
        result = _json(_send(body, headers, _build_tool_registry()))["result"]

        self.assertEqual(result["resultType"], "complete")
        self.assertNotIn("cacheScope", result)
        self.assertNotIn("ttlMs", result)

    def test_modern_resources_read_gets_short_ttl(self):
        listing = _json(_send(*_modern("resources/list")))["result"]["resources"]
        body, headers = _modern("resources/read", {"uri": listing[0]["uri"]})
        result = _json(_send(body, headers))["result"]

        self.assertEqual(result["ttlMs"], 60000)
        self.assertEqual(result["cacheScope"], "private")

    def test_modern_ping_is_404(self):
        body, headers = _modern("ping")
        response = _send(body, headers)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(_json(response)["error"]["code"], -32601)

    def test_modern_log_level_is_404(self):
        response = _send(*_modern("logging/setLevel", {"level": "info"}))
        self.assertEqual(response.status_code, 404)

    def test_modern_unknown_method_is_404(self):
        response = _send(*_modern("nonsense/method"))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(_json(response)["error"]["code"], -32601)

    def test_unknown_version_is_400(self):
        body, headers = _modern("tools/list")
        headers["MCP-Protocol-Version"] = "2031-01-01"
        response = _send(body, headers)
        error = _json(response)["error"]

        self.assertEqual(response.status_code, 400)
        self.assertEqual(error["code"], -32022)
        self.assertEqual(error["data"]["requested"], "2031-01-01")

    def test_modern_resource_not_found(self):
        uri = "fac://skills/no-such-skill"
        response = _send(*_modern("resources/read", {"uri": uri}))
        error = _json(response)["error"]

        self.assertEqual(error["code"], -32602)
        self.assertEqual(error["data"], {"uri": uri})

    def test_header_mismatch_is_400(self):
        body, headers = _modern("tools/list")
        headers["Mcp-Method"] = "prompts/list"
        response = _send(body, headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(_json(response)["error"]["code"], -32020)

    def test_non_dict_params_is_400_not_500(self):
        """A malformed body is a client error; validate_modern_request must not raise AttributeError."""
        body, headers = _modern("tools/call", {"name": "x"})
        body["params"] = ["not", "a", "dict"]
        response = _send(body, headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(_json(response)["error"]["code"], -32602)

    def test_modern_request_does_not_mint_a_session_id(self):
        _send(*_modern("server/discover"))
        self.assertFalse(frappe.local.assistant_session_id)

    def test_handshake_request_does_not_mint_a_session_id(self):
        _send({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}})
        self.assertFalse(frappe.local.assistant_session_id)

    def test_session_id_header_is_still_honoured(self):
        body, headers = _modern("server/discover")
        headers["X-Assistant-Session-Id"] = "abc"
        _send(body, headers)
        self.assertEqual(frappe.local.assistant_session_id, "abc")

    def test_client_name_comes_from_meta_client_info(self):
        body, headers = _modern("server/discover")
        body["params"]["_meta"]["io.modelcontextprotocol/clientInfo"] = {"name": "inspector"}
        _send(body, headers)
        self.assertEqual(frappe.local.assistant_client_id, "inspector")


class TestEraOnLocal(BaseAssistantTest):
    def test_caps_on_local(self):
        body, headers = _modern("server/discover", caps={"extensions": {TASKS_EXT: {}}})
        _send(body, headers)

        self.assertEqual(frappe.local.mcp_era, "modern")
        self.assertIs(frappe.local.mcp_client_caps.tasks, True)

    def test_handshake_leaves_default_caps(self):
        _send({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}})

        self.assertEqual(frappe.local.mcp_era, "handshake")
        self.assertEqual(frappe.local.mcp_client_caps, ClientCaps())

    def test_previous_request_cannot_leak_into_the_next(self):
        _send(*_modern("server/discover", caps={"extensions": {TASKS_EXT: {}}}))
        # Rejected before routing: still has to reset what the modern request set.
        _send({"jsonrpc": "2.0", "id": None, "method": "ping", "params": {}})

        self.assertEqual(frappe.local.mcp_era, "handshake")
        self.assertEqual(frappe.local.mcp_client_caps, ClientCaps())

    def test_notification_resets_era_too(self):
        _send(*_modern("server/discover", caps={"extensions": {TASKS_EXT: {}}}))
        _send({"jsonrpc": "2.0", "method": "notifications/initialized"})

        self.assertEqual(frappe.local.mcp_client_caps, ClientCaps())
