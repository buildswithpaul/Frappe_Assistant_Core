# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""A skill written for one app (CRM, Insights) exists only where that app is installed."""

import frappe

from frappe_assistant_core.api.handlers.resources import SkillManager
from frappe_assistant_core.tests.base_test import BaseAssistantTest

MISSING_APP = "fac_test_app_that_is_not_installed"


def _skill(skill_id: str, requires_app: str | None, **extra):
    # An app-shipped skill: the installer writes requires_app from the skill manifest.
    return frappe.get_doc(
        {
            "doctype": "FAC Skill",
            "skill_id": skill_id,
            "title": skill_id,
            "description": f"{skill_id} description",
            "content": f"# {skill_id}",
            "status": "Published",
            "visibility": "Public",
            "skill_type": extra.pop("skill_type", "Workflow"),
            "owner_user": "Administrator",
            "requires_app": requires_app,
            **extra,
        }
    ).insert(ignore_permissions=True)


class TestSkillRequiresApp(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        _skill("fac-test-needs-missing-app", MISSING_APP)
        _skill("fac-test-needs-frappe", "frappe")
        _skill("fac-test-needs-nothing", None)

    def _listed(self):
        return {s.skill_id for s in SkillManager().get_user_accessible_skills()}

    def test_listing_hides_a_skill_whose_app_is_missing(self):
        listed = self._listed()
        self.assertNotIn("fac-test-needs-missing-app", listed)
        self.assertIn("fac-test-needs-frappe", listed)
        self.assertIn("fac-test-needs-nothing", listed)

    def test_reading_a_skill_whose_app_is_missing_finds_nothing(self):
        self.assertIsNone(SkillManager().read_skill_content("fac-test-needs-missing-app"))
        self.assertEqual(
            SkillManager().read_skill_content("fac-test-needs-frappe"), "# fac-test-needs-frappe"
        )

    def test_tool_skill_map_skips_a_skill_whose_app_is_missing(self):
        if not frappe.db.exists("FAC Skill", {"skill_id": "fac-test-tool-missing-app"}):
            _skill(
                "fac-test-tool-missing-app",
                MISSING_APP,
                skill_type="Tool Usage",
                linked_tool="fac_test_only_tool",
            )
        tool_map = SkillManager().get_tool_skill_map()
        self.assertNotIn("fac_test_only_tool", tool_map)

    def test_installer_writes_requires_app_from_the_manifest(self):
        from frappe_assistant_core.utils.migration_hooks import _install_system_skills

        _install_system_skills()
        self.assertEqual(
            frappe.db.get_value(
                "FAC Skill", {"skill_id": "insights-dashboard", "is_system": 1}, "requires_app"
            ),
            "insights",
        )
