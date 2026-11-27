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

"""Request-level tests for skills/list, skills/get and skill:// reads on the MCP 2026-07-28 era."""

import hashlib

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.tests.test_mcp_modern_era import _json, _modern, _send

# A Tool Usage skill every site has: it is gettable but never listed.
TOOL_USAGE_ID = "list-documents-usage"
TOOL_USAGE_URI = f"skill://{TOOL_USAGE_ID}/SKILL.md"


def _call(method: str, params: dict | None = None):
    return _json(_send(*_modern(method, params)))


class TestMcpSkillsExtension(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self._created = []

    def tearDown(self):
        frappe.set_user("Administrator")
        for name in self._created:
            if frappe.db.exists("FAC Skill", name):
                doc = frappe.get_doc("FAC Skill", name)
                doc.flags.allow_system_delete = True
                doc.delete(ignore_permissions=True)
        super().tearDown()

    def _publish(self, skill_id, skill_type="Workflow", visibility="Public", description="A skill"):
        # Production reaches this through the review flow: an owner drafts, an administrator
        # publishes. The test inserts as Administrator, who may create a Published skill directly.
        doc = frappe.get_doc(
            {
                "doctype": "FAC Skill",
                "skill_id": skill_id,
                "title": skill_id,
                "description": description,
                "content": f"Body of {skill_id}",
                "status": "Published",
                "visibility": visibility,
                "skill_type": skill_type,
            }
        )
        doc.insert(ignore_permissions=True)
        self._created.append(doc.name)
        return doc

    def _use_count(self, name):
        return frappe.db.get_value("FAC Skill", name, "use_count") or 0

    def test_list_has_only_published_workflow_skills(self):
        result = _call("skills/list")["result"]

        self.assertEqual(result["resultType"], "complete")
        self.assertEqual(result["cacheScope"], "private")
        self.assertEqual(result["ttlMs"], 300000)
        self.assertTrue(result["skills"])
        for entry in result["skills"]:
            skill_id = entry["frontmatter"]["name"]
            row = frappe.db.get_value(
                "FAC Skill", {"skill_id": skill_id}, ["skill_type", "status"], as_dict=1
            )
            self.assertEqual((row.skill_type, row.status), ("Workflow", "Published"), skill_id)
        self.assertNotIn(TOOL_USAGE_URI, [entry["uri"] for entry in result["skills"]])

    def test_list_includes_a_newly_published_workflow_skill(self):
        self._publish("fresh-workflow")
        uris = [entry["uri"] for entry in _call("skills/list")["result"]["skills"]]
        self.assertIn("skill://fresh-workflow/SKILL.md", uris)

    def test_list_skips_legacy_id(self):
        doc = self._publish("legacy-seed")
        # Production reaches this through skills saved before this release, when "_" was allowed.
        frappe.db.set_value("FAC Skill", doc.name, "skill_id", "my_skill")
        uris = [entry["uri"] for entry in _call("skills/list")["result"]["skills"]]
        self.assertNotIn("skill://my_skill/SKILL.md", uris)

    def test_get_returns_tool_usage_skill(self):
        result = _call("skills/get", {"uri": TOOL_USAGE_URI})["result"]

        self.assertEqual(result["skill"]["uri"], TOOL_USAGE_URI)
        self.assertEqual(result["skill"]["frontmatter"]["name"], TOOL_USAGE_ID)
        self.assertEqual(result["cacheScope"], "private")

    def test_get_other_users_private_skill_is_unknown(self):
        # Another user's Published-but-Private skill: only its owner may read it.
        self._publish("admins-eyes-only", visibility="Private")
        frappe.set_user(self.make_desk_user("skills-other"))
        private = _call("skills/get", {"uri": "skill://admins-eyes-only/SKILL.md"})["error"]
        missing = _call("skills/get", {"uri": "skill://no-such-skill/SKILL.md"})["error"]

        self.assertEqual(private["code"], -32602)
        self.assertEqual(private["data"], {"uri": "skill://admins-eyes-only/SKILL.md"})
        self.assertEqual(
            private["message"].replace("admins-eyes-only", "X"),
            missing["message"].replace("no-such-skill", "X"),
        )

    def test_get_malformed_uri_is_unknown(self):
        for uri in ("nonsense", "skill://x", "fac://skills/x"):
            error = _call("skills/get", {"uri": uri})["error"]
            self.assertEqual((error["code"], error["data"]), (-32602, {"uri": uri}), uri)

    def test_read_matches_manifest(self):
        entry = _call("skills/get", {"uri": TOOL_USAGE_URI})["result"]["skill"]
        name = frappe.db.get_value("FAC Skill", {"skill_id": TOOL_USAGE_ID}, "name")
        before = self._use_count(name)

        result = _call("resources/read", {"uri": TOOL_USAGE_URI})["result"]
        content = result["contents"][0]

        self.assertEqual(content["mimeType"], "text/markdown")
        raw = content["text"].encode()
        manifest = entry["resources"][0]
        self.assertEqual("sha256:" + hashlib.sha256(raw).hexdigest(), manifest["digest"])
        self.assertEqual(len(raw), manifest["size"])
        self.assertEqual(self._use_count(name), before + 1)
        self.assertEqual(result["ttlMs"], 60000)

    def test_read_other_path_is_unknown(self):
        uri = f"skill://{TOOL_USAGE_ID}/references/a.md"
        error = _call("resources/read", {"uri": uri})["error"]
        self.assertEqual((error["code"], error["data"]), (-32602, {"uri": uri}))

    def test_read_of_a_skill_the_user_may_not_access_is_unknown_not_internal(self):
        self._publish("admins-eyes-only", visibility="Private")
        frappe.set_user(self.make_desk_user("skills-other"))
        for uri, missing_uri in (
            ("skill://admins-eyes-only/SKILL.md", "skill://no-such-skill/SKILL.md"),
            ("fac://skills/admins-eyes-only", "fac://skills/no-such-skill"),
        ):
            error = _call("resources/read", {"uri": uri})["error"]
            missing = _call("resources/read", {"uri": missing_uri})["error"]
            self.assertEqual(error["code"], -32602, uri)
            self.assertEqual(error["data"], {"uri": uri})
            self.assertEqual(
                error["message"].replace("admins-eyes-only", "X"),
                missing["message"].replace("no-such-skill", "X"),
                uri,
            )

    def test_handshake_skills_list_is_method_not_found(self):
        body = {"jsonrpc": "2.0", "id": 1, "method": "skills/list", "params": {}}
        response = _send(body, {"MCP-Protocol-Version": "2025-06-18"})
        self.assertEqual(_json(response)["error"]["code"], -32601)

    def test_handshake_skill_uri_read_is_unchanged(self):
        body = {"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": TOOL_USAGE_URI}}
        self.assertEqual(_json(_send(body, {"MCP-Protocol-Version": "2025-06-18"}))["error"]["code"], -32603)

    def test_resources_list_unchanged(self):
        modern = _call("resources/list")["result"]["resources"]
        body = {"jsonrpc": "2.0", "id": 1, "method": "resources/list", "params": {}}
        handshake = _json(_send(body, {"MCP-Protocol-Version": "2025-06-18"}))["result"]["resources"]
        for resources in (modern, handshake):
            self.assertTrue(resources)
            self.assertFalse([r for r in resources if r["uri"].startswith("skill://")])
