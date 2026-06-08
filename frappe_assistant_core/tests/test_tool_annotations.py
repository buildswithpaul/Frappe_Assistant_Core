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
Tests for MCP tool annotation hints derived from FAC tool categories.

MCP clients (e.g. Claude Desktop) group tools and pick default approval
behavior from the annotation hints in the tools/list response. FAC previously
emitted no annotations, so every tool landed in a single "Other tools" bucket.
The FAC tool category (FAC Tool Configuration.tool_category, admin-overridable)
is now translated into readOnlyHint / destructiveHint, so the client grouping
matches the admin page — one source of truth.
"""

from collections import OrderedDict
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import frappe
from werkzeug.wrappers import Request, Response

from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.tool_category_detector import category_to_annotations


class TestCategoryToAnnotations(BaseAssistantTest):
    """category_to_annotations maps the 4 FAC categories to MCP hints."""

    def test_read_only(self):
        self.assertEqual(category_to_annotations("read_only"), {"readOnlyHint": True})

    def test_write(self):
        self.assertEqual(category_to_annotations("write"), {"readOnlyHint": False})

    def test_read_write(self):
        self.assertEqual(category_to_annotations("read_write"), {"readOnlyHint": False})

    def test_privileged_is_destructive(self):
        self.assertEqual(
            category_to_annotations("privileged"),
            {"readOnlyHint": False, "destructiveHint": True},
        )

    def test_dangerous_legacy_alias(self):
        self.assertEqual(
            category_to_annotations("dangerous"),
            {"readOnlyHint": False, "destructiveHint": True},
        )

    def test_unknown_category_yields_no_hints(self):
        # Unknown -> empty dict (degrade to "no hint", never a wrong hint).
        self.assertEqual(category_to_annotations("something_else"), {})


class TestResolveToolCategories(BaseAssistantTest):
    """_resolve_tool_categories prefers the stored (override-able) category."""

    def test_stored_category_wins_over_autodetect(self):
        from frappe_assistant_core.api import fac_endpoint

        registry = MagicMock()
        # Auto-detect would say read_only, but the stored config says privileged
        # (e.g. an admin override). The stored value must win.
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    fac_endpoint.frappe,
                    "get_all",
                    return_value=[{"tool_name": "get_document", "tool_category": "privileged"}],
                )
            )
            detect = stack.enter_context(
                patch(
                    "frappe_assistant_core.utils.tool_category_detector.detect_tool_category",
                    return_value="read_only",
                )
            )

            result = fac_endpoint._resolve_tool_categories(["get_document"], registry)

        self.assertEqual(result["get_document"], "privileged")
        detect.assert_not_called()  # no need to auto-detect when stored value exists

    def test_falls_back_to_autodetect_when_no_config_row(self):
        from frappe_assistant_core.api import fac_endpoint

        registry = MagicMock()
        registry.get_tool.return_value = MagicMock(name="tool_instance")
        with ExitStack() as stack:
            stack.enter_context(patch.object(fac_endpoint.frappe, "get_all", return_value=[]))
            stack.enter_context(
                patch(
                    "frappe_assistant_core.utils.tool_category_detector.detect_tool_category",
                    return_value="write",
                )
            )

            result = fac_endpoint._resolve_tool_categories(["create_document"], registry)

        self.assertEqual(result["create_document"], "write")

    def test_defaults_to_read_write_when_instance_missing(self):
        from frappe_assistant_core.api import fac_endpoint

        registry = MagicMock()
        registry.get_tool.return_value = None  # tool instance unavailable
        with ExitStack() as stack:
            stack.enter_context(patch.object(fac_endpoint.frappe, "get_all", return_value=[]))

            result = fac_endpoint._resolve_tool_categories(["mystery_tool"], registry)

        self.assertEqual(result["mystery_tool"], "read_write")


class TestToolsListEmitsAnnotations(BaseAssistantTest):
    """The MCP tools/list response must carry the annotation hints so the
    client can categorize tools."""

    def test_tools_list_includes_annotations(self):
        from frappe_assistant_core.mcp.server import MCPServer

        server = MCPServer("test")
        tool_registry = OrderedDict()
        tool_registry["get_document"] = {
            "name": "get_document",
            "description": "Read a document",
            "inputSchema": {"type": "object", "properties": {}},
            "annotations": {"readOnlyHint": True},
            "fn": lambda **kw: {},
        }
        tool_registry["delete_document"] = {
            "name": "delete_document",
            "description": "Delete a document",
            "inputSchema": {"type": "object", "properties": {}},
            "annotations": {"readOnlyHint": False, "destructiveHint": True},
            "fn": lambda **kw: {},
        }

        result = server._handle_tools_list({}, tool_registry)

        by_name = {t["name"]: t for t in result["tools"]}
        self.assertEqual(by_name["get_document"]["annotations"], {"readOnlyHint": True})
        self.assertEqual(
            by_name["delete_document"]["annotations"],
            {"readOnlyHint": False, "destructiveHint": True},
        )


class TestBuildToolRegistryAttachesAnnotations(BaseAssistantTest):
    """End-to-end: tools built for a request carry category-derived annotations
    instead of landing unclassified."""

    def test_every_built_tool_has_annotations(self):
        from frappe_assistant_core.api.fac_endpoint import _build_tool_registry

        registry = _build_tool_registry()
        self.assertTrue(registry, "expected at least one available tool")

        unclassified = [name for name, td in registry.items() if not td.get("annotations")]
        self.assertEqual(
            unclassified,
            [],
            f"these tools reached the client with no annotation hints: {unclassified}",
        )

        # Spot-check known classifications.
        if "get_document" in registry:
            self.assertEqual(registry["get_document"]["annotations"].get("readOnlyHint"), True)
        if "delete_document" in registry:
            ann = registry["delete_document"]["annotations"]
            self.assertEqual(ann.get("readOnlyHint"), False)
            self.assertEqual(ann.get("destructiveHint"), True)
