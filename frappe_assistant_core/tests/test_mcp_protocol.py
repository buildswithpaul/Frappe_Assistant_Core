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

"""Tests for the pure MCP protocol rules in mcp/protocol.py."""

import base64

from frappe_assistant_core.mcp.protocol import (
    ALL_VERSIONS,
    SKILLS_EXT,
    TASKS_EXT,
    ClientCaps,
    ProtocolError,
    client_caps,
    decorate_result,
    discover_result,
    era_of,
    validate_modern_request,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest

MODERN = "2026-07-28"
META_VERSION = "io.modelcontextprotocol/protocolVersion"
META_CAPS = "io.modelcontextprotocol/clientCapabilities"


def body(**capabilities):
    return {"params": {"_meta": {"io.modelcontextprotocol/clientCapabilities": capabilities}}}


def modern_body(method="tools/call", params=None):
    params = {"name": "get_document", **(params or {})}
    params["_meta"] = {META_VERSION: MODERN, META_CAPS: {}}
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}


def modern_headers(method="tools/call", name="get_document"):
    headers = {"MCP-Protocol-Version": MODERN, "Mcp-Method": method}
    if name is not None:
        headers["Mcp-Name"] = name
    return headers


class TestEra(BaseAssistantTest):
    def test_initialize_is_handshake(self):
        self.assertEqual(era_of("initialize", MODERN), "handshake")

    def test_no_header_is_handshake(self):
        self.assertEqual(era_of("tools/list", None), "handshake")

    def test_old_header_is_handshake(self):
        self.assertEqual(era_of("tools/list", "2025-06-18"), "handshake")

    def test_modern_header_is_modern(self):
        self.assertEqual(era_of("tools/list", MODERN), "modern")

    def test_unknown_version_is_400_32022(self):
        with self.assertRaises(ProtocolError) as ctx:
            era_of("tools/list", "2030-01-01")
        self.assertEqual(ctx.exception.http_status, 400)
        self.assertEqual(ctx.exception.code, -32022)
        self.assertEqual(ctx.exception.data, {"supported": list(ALL_VERSIONS), "requested": "2030-01-01"})


class TestModernValidation(BaseAssistantTest):
    def assert_rejected(self, headers, req, code):
        with self.assertRaises(ProtocolError) as ctx:
            validate_modern_request(headers, req)
        self.assertEqual(ctx.exception.http_status, 400)
        self.assertEqual(ctx.exception.code, code)

    def test_valid_request_passes(self):
        self.assertIsNone(validate_modern_request(modern_headers(), modern_body()))

    def test_meta_version_mismatch(self):
        req = modern_body()
        req["params"]["_meta"][META_VERSION] = "2025-06-18"
        self.assert_rejected(modern_headers(), req, -32020)

    def test_missing_meta_version(self):
        req = modern_body()
        del req["params"]["_meta"][META_VERSION]
        self.assert_rejected(modern_headers(), req, -32020)

    def test_missing_mcp_method(self):
        headers = modern_headers()
        del headers["Mcp-Method"]
        self.assert_rejected(headers, modern_body(), -32020)

    def test_mcp_method_mismatch(self):
        self.assert_rejected(modern_headers(method="tools/list"), modern_body(), -32020)

    def test_mcp_name_mismatch_on_tools_call(self):
        self.assert_rejected(modern_headers(name="other"), modern_body(), -32020)

    def test_missing_mcp_name_on_tools_call(self):
        self.assert_rejected(modern_headers(name=None), modern_body(), -32020)

    def test_prompts_get_uses_name(self):
        req = modern_body("prompts/get", {"name": "p1"})
        self.assertIsNone(validate_modern_request(modern_headers("prompts/get", "p1"), req))

    def test_resources_read_uses_uri(self):
        req = modern_body("resources/read", {"uri": "fac://x"})
        self.assertIsNone(validate_modern_request(modern_headers("resources/read", "fac://x"), req))
        self.assert_rejected(modern_headers("resources/read", "fac://y"), req, -32020)

    def test_other_methods_need_no_name(self):
        req = modern_body("tools/list")
        self.assertIsNone(validate_modern_request(modern_headers("tools/list", None), req))

    def test_base64_sentinel_name_is_decoded(self):
        name = "café ✓"
        encoded = "=?base64?" + base64.b64encode(name.encode()).decode() + "?="
        req = modern_body(params={"name": name})
        self.assertIsNone(validate_modern_request(modern_headers(name=encoded), req))

    def test_header_names_are_case_insensitive(self):
        headers = {k.lower(): v for k, v in modern_headers().items()}
        self.assertIsNone(validate_modern_request(headers, modern_body()))

    def test_missing_client_capabilities(self):
        req = modern_body()
        del req["params"]["_meta"][META_CAPS]
        self.assert_rejected(modern_headers(), req, -32602)


class TestClientCaps(BaseAssistantTest):
    def test_empty_elicitation_is_form(self):
        self.assertTrue(client_caps(body(elicitation={})).elicitation_form)

    def test_form_key_is_form(self):
        self.assertTrue(client_caps(body(elicitation={"form": {}})).elicitation_form)

    def test_url_only_is_not_form(self):
        self.assertFalse(client_caps(body(elicitation={"url": {}})).elicitation_form)

    def test_tasks_extension(self):
        self.assertTrue(client_caps(body(extensions={TASKS_EXT: {}})).tasks)

    def test_nothing_declared(self):
        self.assertEqual(client_caps(body()), ClientCaps())

    def test_no_meta_at_all(self):
        self.assertEqual(client_caps({}), ClientCaps())


class TestDecorate(BaseAssistantTest):
    def decorate(self, result, **kw):
        kw.setdefault("cache", False)
        kw.setdefault("ttl_ms", None)
        return decorate_result(result, server_name="fac", server_version="1.0", **kw)

    def test_sets_complete_and_server_info(self):
        out = self.decorate({"a": 1})
        self.assertEqual(out["resultType"], "complete")
        self.assertEqual(
            out["_meta"]["io.modelcontextprotocol/serverInfo"], {"name": "fac", "version": "1.0"}
        )
        self.assertNotIn("ttlMs", out)

    def test_keeps_existing_result_type(self):
        self.assertEqual(self.decorate({"resultType": "task"})["resultType"], "task")

    def test_keeps_existing_meta(self):
        out = self.decorate({"_meta": {"x": 1}})
        self.assertEqual(out["_meta"]["x"], 1)

    def test_list_gets_private_cache(self):
        out = self.decorate({}, cache=True, ttl_ms=300000)
        self.assertEqual(out["ttlMs"], 300000)
        self.assertEqual(out["cacheScope"], "private")

    def test_discover_declares_both_extensions(self):
        out = discover_result(server_name="fac", server_version="1.0")
        self.assertEqual(out["capabilities"]["extensions"], {SKILLS_EXT: {}, TASKS_EXT: {}})
        self.assertEqual(out["supportedVersions"], list(ALL_VERSIONS))
        self.assertEqual(out["ttlMs"], 300000)
        self.assertEqual(out["cacheScope"], "private")
        for key in ("tools", "prompts", "resources"):
            self.assertIn(key, out["capabilities"])
        self.assertIn("io.modelcontextprotocol/serverInfo", out["_meta"])
