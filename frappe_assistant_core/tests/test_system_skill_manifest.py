# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Tests for the system skill and prompt template manifests.

`_install_system_skills` skips a manifest entry whose content file is missing
and only logs it, so a typo in `content_file` ships a skill that never
installs. These tests fail on that instead, and pin that retired system
entries are removed from sites that already have them.
"""

import json
import os
import re

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.migration_hooks import (
    _install_system_prompt_templates,
    _install_system_skills,
)

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_DIR = os.path.dirname(APP_DIR)

SETUP_SKILLS = (
    "site-health-check",
    "setup-change-protocol",
    "guided-setup",
    "add-custom-field",
    "set-up-approval-workflow",
    "configure-naming-series",
)
CUSTOMISATION_SKILLS = (
    "server-script",
    "client-script",
    "print-format",
    "custom-report",
    "notification-setup",
)
RETIRED_TEMPLATE = "export_fac_skills"


def _load_manifest(name: str) -> list:
    with open(os.path.join(APP_DIR, "data", name), encoding="utf-8") as f:
        return json.load(f)


class TestSystemSkillManifest(BaseAssistantTest):
    def test_every_entry_has_its_content_file(self):
        for entry in _load_manifest("system_skills.json"):
            path = os.path.join(REPO_DIR, "docs", "skills", entry["content_file"])
            self.assertTrue(os.path.isfile(path), f"{entry['skill_id']}: {path} missing")
            with open(path, encoding="utf-8") as f:
                self.assertTrue(f.read().strip(), f"{entry['skill_id']}: content is empty")

    def test_skill_ids_are_unique_and_well_formed(self):
        ids = [entry["skill_id"] for entry in _load_manifest("system_skills.json")]
        self.assertEqual(len(ids), len(set(ids)))
        for skill_id in ids:
            self.assertRegex(skill_id, re.compile(r"^[a-z0-9_-]+$"))

    def test_setup_skills_install_as_published_system_skills(self):
        _install_system_skills()

        for skill_id in SETUP_SKILLS:
            skill = frappe.db.get_value(
                "FAC Skill",
                {"skill_id": skill_id},
                ["is_system", "status", "skill_type", "content"],
                as_dict=True,
            )
            self.assertIsNotNone(skill, f"{skill_id} was not installed")
            self.assertEqual(skill.is_system, 1)
            self.assertEqual(skill.status, "Published")
            self.assertEqual(skill.skill_type, "Workflow")
            self.assertTrue(skill.content.startswith("# "))

    def test_customisation_skills_registered(self):
        entries = {e["skill_id"]: e for e in _load_manifest("system_skills.json")}
        for skill_id in CUSTOMISATION_SKILLS:
            self.assertIn(skill_id, entries)
            entry = entries[skill_id]
            self.assertEqual(entry["skill_type"], "Workflow")
            self.assertEqual(entry["status"], "Published")
            self.assertEqual(entry["visibility"], "Public")
            path = os.path.join(REPO_DIR, "docs", "skills", entry["content_file"])
            self.assertTrue(os.path.isfile(path), f"{skill_id}: {path} missing")
            with open(path, encoding="utf-8") as f:
                self.assertIn("setup-change-protocol", f.read(), skill_id)

    def test_add_custom_field_undo_note_corrected(self):
        path = os.path.join(REPO_DIR, "docs", "skills", "add_custom_field.md")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        self.assertNotIn("drop any values", text)
        self.assertNotIn("drops the column", text)
        self.assertIn("keeps its database column", text)

    def test_retired_export_template_is_removed(self):
        self.assertNotIn(
            RETIRED_TEMPLATE,
            {t.get("prompt_id") for t in _load_manifest("system_prompt_templates.json")},
        )
        if not frappe.db.exists("Prompt Template", {"prompt_id": RETIRED_TEMPLATE}):
            frappe.get_doc(
                {
                    "doctype": "Prompt Template",
                    "prompt_id": RETIRED_TEMPLATE,
                    "title": "Export FAC Skills as Claude Skills",
                    "status": "Published",
                    "description": "Retired system template.",
                    "template_content": "Export the skills.",
                    "is_system": 1,
                }
            ).insert(ignore_permissions=True)

        _install_system_prompt_templates()

        self.assertFalse(frappe.db.exists("Prompt Template", {"prompt_id": RETIRED_TEMPLATE}))
