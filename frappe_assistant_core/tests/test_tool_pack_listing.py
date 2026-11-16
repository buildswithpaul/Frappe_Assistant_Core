# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""tools/list names each tool's pack and tells AR which packs a conversation wants (#34608)."""

from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import FACChatMessage
from frappe_assistant_core.core import tool_pack_listing
from frappe_assistant_core.mcp.server import MCPServer
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.plugin_manager import PluginManager, get_plugin_manager


def _tool(name: str) -> dict:
    return {"name": name, "description": name, "inputSchema": {"type": "object"}, "annotations": None}


class TestToolPackListing(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        manager = get_plugin_manager()
        # Production reads the enabled set from FAC Plugin Configuration rows; enabling a plugin
        # commits, so the enabled set is patched here instead.
        patcher = patch.object(PluginManager, "get_enabled_plugins", autospec=True)
        self.enabled = patcher.start()
        self.enabled.return_value = set(manager._discovered_plugins)
        self.addCleanup(patcher.stop)
        self.server = MCPServer("test")
        self.addCleanup(self._clear_ar_session)

    def _clear_ar_session(self):
        frappe.local.ar_session_id = None

    def _list(self, *names: str, ar_session: str | None = None) -> dict:
        # The AR endpoint sets ar_session_id from the X-AR-Session-Id header (fac_endpoint.py).
        frappe.local.ar_session_id = ar_session
        return self.server._handle_tools_list({}, tool_registry={n: _tool(n) for n in names})

    def _chat_with_file(self, file_name: str) -> str:
        session_id = f"pack-listing-{frappe.generate_hash(length=8)}"
        msg = FACChatMessage.create_message(session_id=session_id, role="user", content="here")
        # Production attaches uploads to the user's FAC Chat Message rows (conversation_files.py).
        frappe.get_doc(
            {
                "doctype": "File",
                "file_name": file_name,
                "attached_to_doctype": "FAC Chat Message",
                "attached_to_name": msg.name,
                "content": frappe.generate_hash(length=12),
            }
        ).insert(ignore_permissions=True)
        return session_id

    def test_tool_meta_names_its_pack(self):
        tools = {t["name"]: t for t in self._list("start_import", "list_documents")["tools"]}
        self.assertEqual(tools["start_import"]["_meta"], {"fac/pack": "migration"})
        self.assertNotIn("_meta", tools["list_documents"])

    def test_catalogue_only_for_ar_caller(self):
        result = self._list("start_import", "list_documents")
        self.assertNotIn("_meta", result)
        self.assertEqual([t["name"] for t in result["tools"]], ["start_import", "list_documents"])

        with_ar = self._list("start_import", "list_documents", ar_session="s1")
        packs = {p["id"]: p for p in with_ar["_meta"]["fac/packs"]}
        self.assertEqual(packs["migration"]["tools"], ["start_import"])
        self.assertEqual(packs["migration"]["file_types"], ["csv", "xlsx", "xls", "xml"])
        self.assertEqual(
            set(packs["migration"]), {"id", "title", "description", "tools", "file_types", "skills"}
        )

    def test_wanted_for_spreadsheet(self):
        session_id = self._chat_with_file("customers.xlsx")
        result = self._list("start_import", ar_session=session_id)
        self.assertEqual(result["_meta"]["fac/wanted_packs"], ["migration"])

    def test_no_wanted_without_files(self):
        session_id = self._chat_with_file("notes.txt")
        self.assertEqual(self._list("start_import", ar_session=session_id)["_meta"]["fac/wanted_packs"], [])
        self.assertEqual(
            self._list("start_import", ar_session="no-such-chat")["_meta"]["fac/wanted_packs"], []
        )

    def test_catalogue_omits_pack_with_no_listed_tools(self):
        result = self._list("list_documents", ar_session="s1")
        self.assertEqual(result["_meta"]["fac/packs"], [])

    def _packs_listed(self, *names: str) -> dict:
        """``{tool: pack id or None}`` as tools/list tells AR."""
        tools = self._list(*names, ar_session="s1")["tools"]
        return {t["name"]: (t.get("_meta") or {}).get("fac/pack") for t in tools}

    def test_plain_question_tools_are_base(self):
        base = (
            "list_documents",
            "get_document",
            "create_document",
            "update_document",
            "search_documents",
            "generate_report",
            "report_list",
            "extract_file_content",
            "attach_chat_file",
            "get_doctype_info",
        )
        self.assertEqual(self._packs_listed(*base), dict.fromkeys(base))

    def test_hidden_tools_are_in_no_pack(self):
        listed = self._packs_listed("customisation_impact", "check_build_plan")
        self.assertEqual(listed, {"customisation_impact": None, "check_build_plan": None})

    def test_a_disabled_plugins_tools_carry_no_pack(self):
        self.enabled.return_value = {"core"}
        listed = self._packs_listed("start_import", "test_as_user")
        self.assertEqual(listed, {"start_import": None, "test_as_user": "builder"})

    def test_unreadable_packs_still_list_every_tool(self):
        with patch.object(
            PluginManager, "get_tool_packs", autospec=True, side_effect=RuntimeError("bad pack")
        ):
            result = self._list("start_import", "list_documents", ar_session="s1")

        self.assertEqual([t["name"] for t in result["tools"]], ["start_import", "list_documents"])
        # Without the packs, AR treats every tool as base.
        self.assertNotIn("_meta", result)
        self.assertFalse(any("_meta" in t for t in result["tools"]))

    def test_unreadable_attachments_still_list_every_tool_with_its_pack(self):
        with patch.object(
            tool_pack_listing, "wanted_packs", autospec=True, side_effect=RuntimeError("db gone")
        ):
            result = self._list("start_import", "list_documents", ar_session="s1")

        self.assertEqual([t["name"] for t in result["tools"]], ["start_import", "list_documents"])
        self.assertNotIn("_meta", result)
        self.assertEqual(result["tools"][0]["_meta"], {"fac/pack": "migration"})
