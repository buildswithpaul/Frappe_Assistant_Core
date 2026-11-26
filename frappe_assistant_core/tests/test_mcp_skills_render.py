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

"""Tests for SKILL.md rendering, Agent Skills name rules and FAC Skill validation."""

import hashlib
import json
from pathlib import Path

import frappe
import yaml

from frappe_assistant_core.mcp.skills import (
    SKILL_URI,
    is_listable,
    is_valid_skill_name,
    render_skill_md,
    skill_entry,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest

SYSTEM_SKILLS_JSON = Path(frappe.get_app_path("frappe_assistant_core", "data", "system_skills.json"))


def _frontmatter(raw: bytes) -> dict:
    text = raw.decode("utf-8")
    assert text.startswith("---\n")
    block = text[4:].split("\n---\n", 1)[0]
    return yaml.safe_load(block)


class TestMcpSkillsRender(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self._created = []

    def tearDown(self):
        for name in self._created:
            if frappe.db.exists("FAC Skill", name):
                doc = frappe.get_doc("FAC Skill", name)
                doc.flags.allow_system_delete = True
                doc.delete(ignore_permissions=True)
        super().tearDown()

    def _skill_doc(self, skill_id, description="A skill"):
        return frappe.get_doc(
            {
                "doctype": "FAC Skill",
                "skill_id": skill_id,
                "title": skill_id,
                "description": description,
                "content": "Body",
                "status": "Draft",
                "visibility": "Private",
                "skill_type": "Tool Usage",
            }
        )

    def test_skill_uri_template(self):
        self.assertEqual(SKILL_URI.format(skill_id="a-b"), "skill://a-b/SKILL.md")

    def test_name_rules(self):
        self.assertTrue(is_valid_skill_name("list-documents-usage"))
        self.assertTrue(is_valid_skill_name("a" * 64))
        for bad in ("my_skill", "-a", "a-", "a--b", "A", "a" * 65, ""):
            self.assertFalse(is_valid_skill_name(bad), bad)

    def test_is_listable_checks_description_length(self):
        self.assertTrue(is_listable({"skill_id": "ok", "description": "d"}))
        self.assertFalse(is_listable({"skill_id": "ok", "description": ""}))
        self.assertFalse(is_listable({"skill_id": "ok", "description": "d" * 1025}))
        self.assertFalse(is_listable({"skill_id": "bad_id", "description": "d"}))

    def test_frontmatter_round_trips(self):
        for description in ("a: b", "# x", "- y", "line1\nline2", 'say "hi"'):
            raw = render_skill_md("my-skill", description, "Body text")
            front = _frontmatter(raw)
            self.assertEqual(front["name"], "my-skill")
            self.assertEqual(front["description"], description)
            self.assertTrue(raw.decode().endswith("---\n\nBody text"))

    def test_render_is_deterministic(self):
        self.assertEqual(render_skill_md("a", "d", "c"), render_skill_md("a", "d", "c"))

    def test_digest_matches_bytes(self):
        entry = skill_entry("my-skill", "desc", "Body é")
        raw = render_skill_md("my-skill", "desc", "Body é")
        resource = entry["resources"][0]
        self.assertEqual(resource["digest"], "sha256:" + hashlib.sha256(raw).hexdigest())
        self.assertEqual(resource["size"], len(raw))
        self.assertEqual(resource["uri"], "skill://my-skill/SKILL.md")
        self.assertEqual(entry["uri"], resource["uri"])
        self.assertEqual(entry["frontmatter"], {"name": "my-skill", "description": "desc"})

    def test_all_system_skills_listable(self):
        for skill in json.loads(SYSTEM_SKILLS_JSON.read_text()):
            self.assertTrue(is_listable(skill), skill["skill_id"])

    def test_validate_rejects_bad_new_id(self):
        with self.assertRaises(frappe.ValidationError):
            self._skill_doc("my_skill").insert(ignore_permissions=True)

    def test_validate_allows_editing_legacy_id(self):
        doc = self._skill_doc("legacy-seed")
        doc.insert(ignore_permissions=True)
        self._created.append(doc.name)
        # Production reaches this through skills saved before this release, when "_" was allowed.
        frappe.db.set_value("FAC Skill", doc.name, "skill_id", "my_skill")
        doc = frappe.get_doc("FAC Skill", doc.name)
        doc.content = "Edited"
        doc.save(ignore_permissions=True)
        self.assertEqual(frappe.db.get_value("FAC Skill", doc.name, "content"), "Edited")

    def test_validate_rejects_long_description_on_change(self):
        doc = self._skill_doc("long-desc")
        doc.insert(ignore_permissions=True)
        self._created.append(doc.name)
        doc.description = "d" * 1025
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)
