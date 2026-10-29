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

from frappe_assistant_core.plugins.faco.tools.generate_document import GenerateDocument
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

        for skill_id in SETUP_SKILLS + CUSTOMISATION_SKILLS:
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

    def test_add_custom_field_reports_placement_and_links_the_form(self):
        text = self._read_skill("add_custom_field.md")
        self.assertIn("`location`", text)
        self.assertIn("did not choose that place, move it before you report", text)
        self.assertIn("`applies_to.url`", text)
        self.assertIn("Never offer the link to the Custom Field record", text)
        self.assertIn("keeps its database column", text)

    def test_conditions_are_said_as_sentences_not_expressions(self):
        wording = {
            "setup_change_protocol.md": "never as an expression such as",
            "notification.md": "never as the expression",
            "set_up_approval_workflow.md": "never as the expression",
        }
        for name, phrase in wording.items():
            self.assertIn(phrase, self._read_skill(name), name)
        protocol = self._read_skill("setup_change_protocol.md")
        self.assertIn("when the grand total is over 100,000", protocol)
        self.assertIn("Pasting a raw condition", protocol)

    def _read_skill(self, name: str) -> str:
        with open(os.path.join(REPO_DIR, "docs", "skills", name), encoding="utf-8") as f:
            return f.read()

    def test_server_script_skill_states_what_scripts_off_really_does(self):
        text = self._read_skill("server_script.md")
        self.assertNotIn("would do nothing", text)
        self.assertNotIn("System Manager can switch", text)
        self.assertIn("private bench", text)

    def test_report_print_notification_skills_do_not_claim_system_manager_only(self):
        for name in ("custom_report.md", "print_format.md", "notification.md"):
            text = self._read_skill(name)
            self.assertNotIn("Only a System Manager", text, name)
            self.assertNotIn("needs a System Manager", text, name)
        protocol = self._read_skill("setup_change_protocol.md")
        step_one = protocol.split("1. **Check who")[1].split("If the user isn't one")[0]
        for doctype in ("`Report`", "`Print Format`", "`Notification`"):
            self.assertNotIn(doctype, step_one)

    def test_customisation_skills_ask_before_the_switched_off_fallback_and_hide_names(self):
        self.assertIn("Ask the user before", self._read_skill("server_script.md"))
        self.assertIn("ask whether to go ahead", self._read_skill("custom_report.md"))
        for skill_id in CUSTOMISATION_SKILLS:
            entry = next(e for e in _load_manifest("system_skills.json") if e["skill_id"] == skill_id)
            self.assertIn("Never show", self._read_skill(entry["content_file"]), skill_id)

    def test_publishing_and_switching_on_ask_with_the_final_code_even_on_the_plan(self):
        # FAC Cloud shows the card for a write that switches something on, plan or not.
        stale = (
            "unless the approved build plan marked the page as going live",
            "so the approved plan covers it",
            "so the approved plan is that yes",
            "or the plan entry for switching it on",
            "(or its plan entry)",
        )
        for name in ("fac_page.md", "server_script.md", "setup_change_protocol.md"):
            text = self._read_skill(name)
            self.assertIn("asks once, with the final code, even when it is on the plan", text, name)
            self.assertIn("so the user sees it coming", text, name)
            for phrase in stale:
                self.assertNotIn(phrase, text, name)

    def test_switch_on_card_is_the_go_ahead_and_testing_follows(self):
        # Switching code on always shows the card, so a chat question first asks twice.
        steps = {
            "server_script.md": "7. **Create it",
            "client_script.md": "6. **Create it",
            "notification.md": "6. **Show the plan",
            "custom_report.md": "7. **Create it",
        }
        for name, marker in steps.items():
            step = self._read_skill(name).split(marker)[1].split("\n")[0]
            self.assertNotIn("whether to go ahead", step, name)
            self.assertNotIn("Only after they say yes", step, name)
            self.assertIn("the card is the user's go-ahead", step, name)
            self.assertIn("straight away", step, name)
            self.assertLess(step.index("the card is the user's go-ahead"), step.index("straight away"), name)
            self.assertIn("switch it off again", step, name)

    def test_skills_say_editing_live_code_asks_even_on_the_plan(self):
        for name in (
            "setup_change_protocol.md",
            "frappe_app_pages.md",
            "client_script.md",
            "server_script.md",
        ):
            self.assertIn("live code", self._read_skill(name), name)

    def test_report_builder_example_uses_fields_and_notification_warns_about_blocked_saves(self):
        report = self._read_skill("custom_report.md")
        self.assertIn('\\"fields\\": [[', report)
        self.assertNotIn('\\"columns\\": [[', report)
        self.assertIn("private bench", report)
        self.assertIn("blocks saving or submitting", self._read_skill("notification.md"))

    def test_customisation_skills_name_records_by_purpose_not_by_value(self):
        rule = (
            "Name records by what they do, never by a value that may change "
            "(no limits, percentages or dates in names)"
        )
        for name in (
            "server_script.md",
            "client_script.md",
            "notification.md",
            "custom_report.md",
            "print_format.md",
            "setup_change_protocol.md",
        ):
            text = self._read_skill(name)
            self.assertIn(rule, text, name)
            self.assertIn(
                "'Discount limit on Sales Invoice submit', not 'Block discount above 15%'", text, name
            )
            self.assertIn("Changing a value never needs a rename.", text, name)

    def test_personal_pages_are_built_without_a_plan(self):
        # A personal page reads only what its owner may and asks before any change; a plan card adds nothing.
        self.assertIn("Don't call `propose_build_plan` or `ask_user`", self._read_skill("pages_in_chat.md"))
        for name in ("fac_page.md", "setup_change_protocol.md"):
            text = self._read_skill(name)
            self.assertIn('get_skill("pages-in-chat")', text, name)
            self.assertRegex(text, r"needs no plan|without a plan", name)

    def test_a_pdf_of_the_sites_figures_is_a_page_not_generate_document(self):
        self.assertIn('get_skill("pages-in-chat")', self._read_skill("document_authoring.md"))
        self.assertIn("pages-in-chat", GenerateDocument().description)
        entry = next(e for e in _load_manifest("system_skills.json") if e["skill_id"] == "pages-in-chat")
        self.assertIn("instead of generate_document", entry["description"])

    def test_faco_tests_a_page_before_calling_it_done(self):
        # The user judges a page by its figures and never sees its code, so FACO checks them first.
        text = self._read_skill("pages_in_chat.md")
        self.assertIn("**Test it before you say it's done.**", text)
        self.assertIn("`page_errors`", text)
        self.assertIn("run the page's queries yourself", text)
        self.assertIn(
            "Never call a page done while it shows errors or empty figures you can't explain.", text
        )
        entry = next(e for e in _load_manifest("system_skills.json") if e["skill_id"] == "pages-in-chat")
        self.assertIn("test it before saying it is done", entry["description"])

    def test_personal_pages_have_no_run_step(self):
        # A personal page runs on its own in its read-only frame; no skill may send the user to run it.
        for name in ("pages_in_chat.md", "fac_page.md"):
            text = self._read_skill(name)
            for step in ("Run new version", "View code", "View changes"):
                self.assertNotIn(step, text, f"{name}: {step}")
        text = self._read_skill("pages_in_chat.md")
        self.assertIn("**Everything else asks the user first**", text)
        self.assertIn("**Allow for this page**", text)

    def test_pages_in_chat_says_the_page_opens_by_itself(self):
        text = self._read_skill("pages_in_chat.md")
        self.assertNotIn("Point to the chip", text)
        self.assertIn("opens beside the chat as soon as your create saves", text)

    def test_page_data_is_explored_with_read_tools_that_dont_ask(self):
        # run_database_query asks on every call (raw SQL skips user permissions); three such cards
        # came before the page in the Ep.19 take. The permission-checked read tools don't ask.
        text = self._read_skill("pages_in_chat.md")
        self.assertIn("**look at the data with the read tools that don't ask**", text)
        self.assertIn("`group_by` and `aggregate`", text)
        self.assertIn("Don't use `run_database_query`", text)
        self.assertIn("Totals per month or week belong in the page's script", text)

    def test_a_doctypes_fields_come_from_get_doctype_info_not_python(self):
        # #34574: in the Ep.19 take FACO ran run_python_code (it always asks) to read DocField, which a
        # user can't read, and the call failed.
        for name in ("pages_in_chat.md", "fac_page.md"):
            text = self._read_skill(name)
            self.assertIn("never `run_python_code` or a read of `DocField`", text, name)

    def test_shared_pages_are_checked_for_errors_and_their_api_limits(self):
        # #34516: a published page broke its own API's 62-day limit, and only the user found out.
        text = self._read_skill("fac_page.md")
        self.assertIn("`browser_capture_diagnostics`", text)
        self.assertIn("Fix any script error before you say the page is done", text)
        self.assertIn("within the limits of that API", text)

    def test_a_page_is_checked_in_the_chat_app_with_the_screenshot_alone(self):
        # #34515: the Desk-only steps came first, so FACO in the chat app reached for tools it can't run there.
        step = self._read_skill("fac_page.md").split("4. **Check it**")[1].split("\n5. ")[0]
        self.assertIn("work only in the Desk widget", step)
        self.assertLess(step.index("`page_errors`"), step.index("`browser_navigate_to`"))

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
