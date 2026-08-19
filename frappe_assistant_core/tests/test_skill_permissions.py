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
Regression tests for FAC Skill publish/visibility authorization.

Ref: https://github.com/buildswithpaul/Frappe_Assistant_Core/issues/225

Before this fix, any Desk User (no Assistant Admin / System Manager role
required) could create or flip an FAC Skill straight to Published + Public,
and get_tool_skill_map() could leak a Private skill's content into another
user's tool description when skill_mode="replace".
"""

import frappe

from frappe_assistant_core.api.handlers.resources import SkillManager
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestSkillPermissions(BaseAssistantTest):
    """Non-admins may only create/hold Draft+Private skills; publishing/sharing requires admin."""

    NON_ADMIN_USER = "test_skill_nonadmin@example.com"
    OTHER_NON_ADMIN_USER = "test_skill_other_nonadmin@example.com"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._create_non_admin_user(cls.NON_ADMIN_USER)
        cls._create_non_admin_user(cls.OTHER_NON_ADMIN_USER)

    @classmethod
    def _create_non_admin_user(cls, email):
        if frappe.db.exists("User", email):
            frappe.delete_doc("User", email, force=True)

        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": "Test",
                "last_name": "SkillNonAdmin",
                "enabled": 1,
                "new_password": "test_password_123",
                "user_type": "System User",
            }
        )
        user.insert(ignore_permissions=True)

        user.reload()
        user.roles = [r for r in user.roles if r.role in ("All", "Guest")]
        user.save(ignore_permissions=True)

        # User.validate() recomputes user_type from desk_access of assigned
        # roles, which drops it back to "Website User" once we strip roles
        # down to All/Guest. Force it back so frappe.get_roles() grants the
        # automatic "Desk User" role these tests rely on.
        frappe.db.set_value("User", email, "user_type", "System User")
        frappe.clear_cache(user=email)

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        for email in (cls.NON_ADMIN_USER, cls.OTHER_NON_ADMIN_USER):
            if frappe.db.exists("User", email):
                frappe.delete_doc("User", email, force=True)
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self._created_skills = []

    def tearDown(self):
        frappe.set_user("Administrator")
        for name in self._created_skills:
            if frappe.db.exists("FAC Skill", name):
                doc = frappe.get_doc("FAC Skill", name)
                doc.flags.allow_system_delete = True
                doc.delete(ignore_permissions=True)
        super().tearDown()

    def _new_skill_doc(self, skill_id, owner_user, status="Draft", visibility="Private", **extra):
        doc_dict = {
            "doctype": "FAC Skill",
            "skill_id": skill_id,
            "title": skill_id,
            "description": f"Test skill {skill_id}",
            "content": "Test content",
            "status": status,
            "visibility": visibility,
            "skill_type": "Tool Usage",
            "owner_user": owner_user,
        }
        doc_dict.update(extra)
        return frappe.get_doc(doc_dict)

    def _insert_as_admin(self, skill_id, owner_user, status="Draft", visibility="Private", **extra):
        """Bypass our own validation to seed a skill in a specific state for setup."""
        frappe.set_user("Administrator")
        doc = self._new_skill_doc(skill_id, owner_user, status=status, visibility=visibility, **extra)
        doc.insert(ignore_permissions=True)
        self._created_skills.append(doc.name)
        return doc

    # =========================================================================
    # Controller-level gate on create
    # =========================================================================

    def test_non_admin_can_create_draft_private_skill(self):
        frappe.set_user(self.NON_ADMIN_USER)
        doc = self._new_skill_doc("test-skill-draft-private", self.NON_ADMIN_USER)
        doc.insert()
        self._created_skills.append(doc.name)
        self.assertEqual(doc.status, "Draft")
        self.assertEqual(doc.visibility, "Private")

    def test_non_admin_cannot_create_published_skill(self):
        frappe.set_user(self.NON_ADMIN_USER)
        doc = self._new_skill_doc("test-skill-published", self.NON_ADMIN_USER, status="Published")
        with self.assertRaises(frappe.PermissionError):
            doc.insert()

    def test_non_admin_cannot_create_public_skill(self):
        frappe.set_user(self.NON_ADMIN_USER)
        doc = self._new_skill_doc("test-skill-public", self.NON_ADMIN_USER, visibility="Public")
        with self.assertRaises(frappe.PermissionError):
            doc.insert()

    def test_non_admin_cannot_create_shared_skill(self):
        frappe.set_user(self.NON_ADMIN_USER)
        doc = self._new_skill_doc("test-skill-shared", self.NON_ADMIN_USER, visibility="Shared")
        doc.append("shared_with_roles", {"role": "System Manager"})
        with self.assertRaises(frappe.PermissionError):
            doc.insert()

    def test_admin_can_create_published_public_skill(self):
        frappe.set_user("Administrator")
        doc = self._new_skill_doc(
            "test-skill-admin-published", "Administrator", status="Published", visibility="Public"
        )
        doc.insert(ignore_permissions=True)
        self._created_skills.append(doc.name)
        self.assertEqual(doc.status, "Published")
        self.assertEqual(doc.visibility, "Public")

    # =========================================================================
    # Controller-level gate on update (direct save / REST-style flip)
    # =========================================================================

    def test_non_admin_cannot_flip_own_draft_skill_to_published(self):
        created = self._insert_as_admin("test-skill-flip-status", self.NON_ADMIN_USER)

        frappe.set_user(self.NON_ADMIN_USER)
        doc = frappe.get_doc("FAC Skill", created.name)
        doc.status = "Published"
        with self.assertRaises(frappe.PermissionError):
            doc.save()

    def test_non_admin_cannot_flip_own_skill_visibility_to_public(self):
        created = self._insert_as_admin("test-skill-flip-visibility", self.NON_ADMIN_USER)

        frappe.set_user(self.NON_ADMIN_USER)
        doc = frappe.get_doc("FAC Skill", created.name)
        doc.visibility = "Public"
        with self.assertRaises(frappe.PermissionError):
            doc.save()

    def test_non_admin_can_edit_content_on_already_published_owned_skill(self):
        """Regression guard: an admin-published skill's owner must still be able to edit it."""
        # Mirrors the real flow: the owner creates it as Draft/Private, then an
        # admin publishes it (like toggle_skill_status does, ignore_permissions=True) —
        # the owner is never re-created as Administrator, so Frappe's own
        # if_owner write-permission check still matches the real creator.
        frappe.set_user(self.NON_ADMIN_USER)
        doc = self._new_skill_doc("test-skill-edit-published", self.NON_ADMIN_USER)
        doc.insert()
        self._created_skills.append(doc.name)

        frappe.set_user("Administrator")
        doc.reload()
        doc.status = "Published"
        doc.visibility = "Public"
        doc.save(ignore_permissions=True)

        frappe.set_user(self.NON_ADMIN_USER)
        doc = frappe.get_doc("FAC Skill", doc.name)
        doc.content = "Updated content, status/visibility unchanged"
        doc.save()
        self.assertEqual(doc.content, "Updated content, status/visibility unchanged")

    # =========================================================================
    # get_tool_skill_map() access scoping + precedence (issue #225 core bug)
    # =========================================================================

    def test_get_tool_skill_map_excludes_private_skill_for_other_user(self):
        self._insert_as_admin(
            "test-skill-private-map",
            self.NON_ADMIN_USER,
            status="Published",
            visibility="Private",
            linked_tool="some_tool_private",
        )

        manager = SkillManager()
        tool_map = manager.get_tool_skill_map(user=self.OTHER_NON_ADMIN_USER)
        self.assertNotIn("some_tool_private", tool_map)

    def test_get_tool_skill_map_includes_private_skill_for_owner(self):
        self._insert_as_admin(
            "test-skill-private-map-owner",
            self.NON_ADMIN_USER,
            status="Published",
            visibility="Private",
            linked_tool="some_tool_private_owner",
        )

        manager = SkillManager()
        tool_map = manager.get_tool_skill_map(user=self.NON_ADMIN_USER)
        self.assertIn("some_tool_private_owner", tool_map)

    def test_get_tool_skill_map_precedence_prefers_system_skill(self):
        self._insert_as_admin(
            "test-skill-precedence-user",
            "Administrator",
            status="Published",
            visibility="Public",
            linked_tool="shared_precedence_tool",
        )
        self._insert_as_admin(
            "test-skill-precedence-system",
            "Administrator",
            status="Published",
            visibility="Public",
            linked_tool="shared_precedence_tool",
            is_system=1,
        )

        manager = SkillManager()
        tool_map = manager.get_tool_skill_map(user="Administrator")
        self.assertEqual(tool_map["shared_precedence_tool"]["skill_id"], "test-skill-precedence-system")

    # =========================================================================
    # get_user_accessible_skills() / read_skill_content() access scoping
    # =========================================================================

    def test_get_user_accessible_skills_excludes_other_users_private_skill(self):
        self._insert_as_admin(
            "test-skill-accessible-private", self.NON_ADMIN_USER, status="Published", visibility="Private"
        )

        manager = SkillManager()
        skills = manager.get_user_accessible_skills(self.OTHER_NON_ADMIN_USER)
        skill_ids = {s["skill_id"] for s in skills}
        self.assertNotIn("test-skill-accessible-private", skill_ids)

    def test_read_skill_content_blocks_other_user_from_private_draft_skill(self):
        self._insert_as_admin(
            "test-skill-read-private-draft", self.NON_ADMIN_USER, status="Draft", visibility="Private"
        )

        frappe.set_user(self.OTHER_NON_ADMIN_USER)
        manager = SkillManager()
        with self.assertRaises(frappe.PermissionError):
            manager.read_skill_content("test-skill-read-private-draft")
