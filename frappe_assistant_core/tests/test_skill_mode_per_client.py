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
Replace mode shortens tool descriptions for FAC Cloud only.

FAC Chat loads the linked skill through ``get_skill``; every other MCP client has no such tool, so
shortening for it would only hide the guidance. FAC Cloud is recognised by the OAuth client of the
presented bearer token, so these tests use real ``OAuth Client`` and ``OAuth Bearer Token`` rows.
"""

import json
import os
from collections import OrderedDict
from unittest.mock import patch

import frappe
from frappe.utils import set_request

from frappe_assistant_core.api.fac_endpoint import _build_tool_registry, mcp
from frappe_assistant_core.mcp import protocol
from frappe_assistant_core.tests.test_fac_cloud_only_tools import (
    MCP_PATH,
    FacCloudCallerTestCase,
    _make_oauth_client,
    _mint,
)
from frappe_assistant_core.utils.mcp_caller import FAC_CLOUD_OAUTH_CLIENT_ID as FAC_CLOUD_CLIENT

SNAPSHOT_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "mcp_fac_cloud_replace_snapshot.json")
SKILL_TOOL = "list_documents"
POINTER = "Detailed guidance: fac://skills/list-documents-usage"


def _pinned_registry() -> OrderedDict:
    """Two stable core tools, so the snapshot never depends on which plugins a site enables."""
    full = _build_tool_registry()
    return OrderedDict((name, full[name]) for name in ("get_document", SKILL_TOOL) if name in full)


def _tools_list(mode: str, registry: OrderedDict | None = None) -> dict:
    """tools/list the way a request gets it, with the per-request state reset first."""
    settings = frappe.get_single("Assistant Core Settings")
    settings.skill_mode = mode
    settings.save(ignore_permissions=True)
    protocol.set_request_state()
    return mcp._handle_tools_list({}, tool_registry=registry or _pinned_registry())


def build_fac_cloud_replace_snapshot() -> dict:
    """FAC Cloud's tools/list in replace mode, as a FAC Cloud bearer token would get it."""
    client = (
        FAC_CLOUD_CLIENT
        if frappe.db.exists("OAuth Client", FAC_CLOUD_CLIENT)
        else _make_oauth_client(FAC_CLOUD_CLIENT)
    )
    user = "Administrator"
    set_request(method="POST", path=MCP_PATH, headers={"Authorization": f"Bearer {_mint(user, client)}"})
    frappe.set_user(user)
    return _tools_list("replace")


def write_snapshot():
    """One-off: ``bench execute`` this on code from before the per-client change."""
    snapshot = build_fac_cloud_replace_snapshot()
    with open(SNAPSHOT_PATH, "w") as handle:
        json.dump(snapshot, handle, indent=2, sort_keys=True)
        handle.write("\n")
    frappe.db.rollback()


class TestSkillModePerClient(FacCloudCallerTestCase):
    def setUp(self):
        super().setUp()
        self.registry = _pinned_registry()
        self.full_description = self.registry[SKILL_TOOL]["description"]

    def _descriptions(self, mode: str = "replace") -> dict:
        return {t["name"]: t["description"] for t in _tools_list(mode, self.registry)["tools"]}

    def test_replace_mode_full_descriptions_for_other_clients(self):
        # A DCR client (Claude Desktop, ChatGPT) presents its own OAuth client's token.
        self._as_caller(_mint(self.user, self.other_client))

        descriptions = self._descriptions()

        for name, tool in self.registry.items():
            self.assertEqual(descriptions[name], tool["description"])

    def test_replace_mode_short_for_fac_cloud(self):
        self._as_caller(_mint(self.user, self.fac_cloud_client))

        self.assertTrue(self._descriptions()[SKILL_TOOL].endswith(POINTER))

    def test_replace_mode_full_without_a_bearer_token(self):
        self._as_caller(None)

        self.assertEqual(self._descriptions()[SKILL_TOOL], self.full_description)

    def test_supplementary_mode_is_full_for_fac_cloud(self):
        self._as_caller(_mint(self.user, self.fac_cloud_client))

        self.assertEqual(self._descriptions("supplementary")[SKILL_TOOL], self.full_description)

    def test_fac_cloud_replace_payload_unchanged(self):
        """The shortened FAC Cloud payload is byte-for-byte what it was before this change."""
        self._as_caller(_mint(self.user, self.fac_cloud_client))
        with open(SNAPSHOT_PATH) as handle:
            expected = json.load(handle)

        self.assertEqual(_tools_list("replace", self.registry), expected)

    def test_token_looked_up_once(self):
        self._as_caller(_mint(self.user, self.fac_cloud_client))
        _tools_list("replace", self.registry)  # sets replace mode
        protocol.set_request_state()  # a new request: the first call's memo is gone
        real = frappe.db.get_value

        with patch.object(frappe.db, "get_value", wraps=real) as spy:
            for _ in range(2):
                mcp._handle_tools_list({}, tool_registry=self.registry)

        token_reads = [c for c in spy.call_args_list if c.args and c.args[0] == "OAuth Bearer Token"]
        self.assertEqual(len(token_reads), 1)

    def test_a_second_request_with_another_token_gets_its_own_answer(self):
        """frappe.local survives between simulated requests; the memo must not leak across them."""
        self._as_caller(_mint(self.user, self.fac_cloud_client))
        self.assertTrue(self._descriptions()[SKILL_TOOL].endswith(POINTER))

        # Same worker, next request, no reset by the test: only the memo key can tell them apart.
        self._as_caller(_mint(self.user, self.other_client))
        settings = frappe.get_single("Assistant Core Settings")
        self.assertEqual(settings.skill_mode, "replace")
        descriptions = {
            t["name"]: t["description"]
            for t in mcp._handle_tools_list({}, tool_registry=self.registry)["tools"]
        }
        self.assertEqual(descriptions[SKILL_TOOL], self.full_description)
