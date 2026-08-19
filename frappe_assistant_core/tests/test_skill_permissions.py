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

Refs:
- https://github.com/buildswithpaul/Frappe_Assistant_Core/issues/225
- https://github.com/buildswithpaul/Frappe_Assistant_Core/issues/239

Before #225 was fixed, any Desk User (no Assistant Admin / System Manager role
required) could create or flip an FAC Skill straight to Published + Public, and
get_tool_skill_map() could leak a Private skill's content into another user's
tool description when skill_mode="replace".

#239 closed what that gate left open. It guarded the status/visibility
*transition* only, so once an admin published a reviewed draft its non-admin
owner could still rewrite the approved content, repoint linked_tool at another
tool, widen shared_with_roles, or set is_system.
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

    def _publish_as_admin(self, skill_id, owner_user, visibility="Public", roles=None, **extra):
        """
        Seed the real review flow: the owner drafts it privately, an admin publishes.

        Creating it *as the owner* matters — Frappe's own ``if_owner`` write rule is
        what lets the owner save it again afterwards, so a skill seeded as
        Administrator would fail the later assertions for the wrong reason.
        """
        frappe.set_user(owner_user)
        doc = self._new_skill_doc(skill_id, owner_user, **extra)
        doc.insert()
        self._created_skills.append(doc.name)

        frappe.set_user("Administrator")
        doc.reload()
        doc.status = "Published"
        doc.visibility = visibility
        for role in roles or []:
            doc.append("shared_with_roles", {"role": role})
        doc.save(ignore_permissions=True)
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

    def test_non_admin_owner_can_resave_published_skill_unchanged(self):
        """No false positives: a no-op save on a published skill must still succeed."""
        created = self._publish_as_admin("test-skill-noop-save", self.NON_ADMIN_USER)

        frappe.set_user(self.NON_ADMIN_USER)
        doc = frappe.get_doc("FAC Skill", created.name)
        doc.save()
        self.assertEqual(doc.status, "Published")

    def test_non_admin_can_edit_content_on_published_private_skill(self):
        """Published + Private is owner-only, so there is no approval to protect."""
        created = self._publish_as_admin(
            "test-skill-edit-published-private", self.NON_ADMIN_USER, visibility="Private"
        )

        frappe.set_user(self.NON_ADMIN_USER)
        doc = frappe.get_doc("FAC Skill", created.name)
        doc.content = "Revised while private"
        doc.save()
        self.assertEqual(doc.content, "Revised while private")

    # =========================================================================
    # Approved content is frozen while the skill is exposed (issue #239)
    # =========================================================================

    def test_non_admin_cannot_edit_content_on_published_public_skill(self):
        """The core #239 gap: an admin's publish must cover the text it approves."""
        created = self._publish_as_admin("test-skill-lock-content", self.NON_ADMIN_USER)

        frappe.set_user(self.NON_ADMIN_USER)
        doc = frappe.get_doc("FAC Skill", created.name)
        doc.content = "Injected instructions after admin review"
        with self.assertRaises(frappe.PermissionError):
            doc.save()

    def test_non_admin_cannot_edit_description_on_published_public_skill(self):
        """description is spliced into other users' tool descriptions in replace mode."""
        created = self._publish_as_admin("test-skill-lock-description", self.NON_ADMIN_USER)

        frappe.set_user(self.NON_ADMIN_USER)
        doc = frappe.get_doc("FAC Skill", created.name)
        doc.description = "Rewritten description"
        with self.assertRaises(frappe.PermissionError):
            doc.save()

    def test_non_admin_cannot_repoint_linked_tool_on_published_public_skill(self):
        """Retargeting is as powerful as rewriting: same approval, different tool."""
        created = self._publish_as_admin(
            "test-skill-lock-linked-tool", self.NON_ADMIN_USER, linked_tool="list_documents"
        )

        frappe.set_user(self.NON_ADMIN_USER)
        doc = frappe.get_doc("FAC Skill", created.name)
        doc.linked_tool = "run_python_code"
        with self.assertRaises(frappe.PermissionError):
            doc.save()

    def test_non_admin_cannot_edit_content_on_published_shared_skill(self):
        """Shared is exposed too, not just Public."""
        created = self._publish_as_admin(
            "test-skill-lock-shared", self.NON_ADMIN_USER, visibility="Shared", roles=["Assistant User"]
        )

        frappe.set_user(self.NON_ADMIN_USER)
        doc = frappe.get_doc("FAC Skill", created.name)
        doc.content = "Injected instructions after admin review"
        with self.assertRaises(frappe.PermissionError):
            doc.save()

    def test_non_admin_cannot_widen_shared_roles_on_published_skill(self):
        """visibility stays 'Shared', so the #225 transition check never fires here."""
        created = self._publish_as_admin(
            "test-skill-lock-roles", self.NON_ADMIN_USER, visibility="Shared", roles=["Assistant User"]
        )

        frappe.set_user(self.NON_ADMIN_USER)
        doc = frappe.get_doc("FAC Skill", created.name)
        doc.append("shared_with_roles", {"role": "System Manager"})
        with self.assertRaises(frappe.PermissionError):
            doc.save()

    def test_non_admin_can_edit_content_while_unpublishing_in_same_save(self):
        """De-escalation must stay open — that is the supported way to revise."""
        created = self._publish_as_admin("test-skill-unpublish-and-edit", self.NON_ADMIN_USER)

        frappe.set_user(self.NON_ADMIN_USER)
        doc = frappe.get_doc("FAC Skill", created.name)
        doc.status = "Draft"
        doc.content = "Revised after unpublishing"
        doc.save()

        self.assertEqual(doc.status, "Draft")
        self.assertEqual(doc.content, "Revised after unpublishing")

    def test_non_admin_can_edit_content_while_making_private_in_same_save(self):
        """Dropping visibility to Private is de-escalation as well."""
        created = self._publish_as_admin("test-skill-privatize-and-edit", self.NON_ADMIN_USER)

        frappe.set_user(self.NON_ADMIN_USER)
        doc = frappe.get_doc("FAC Skill", created.name)
        doc.visibility = "Private"
        doc.content = "Revised after going private"
        doc.save()

        self.assertEqual(doc.visibility, "Private")
        self.assertEqual(doc.content, "Revised after going private")

    def test_admin_can_edit_content_on_published_public_skill(self):
        """Admins are unrestricted — they are the approvers."""
        created = self._publish_as_admin("test-skill-admin-edit-published", self.NON_ADMIN_USER)

        frappe.set_user("Administrator")
        doc = frappe.get_doc("FAC Skill", created.name)
        doc.content = "Admin revision"
        doc.save(ignore_permissions=True)
        self.assertEqual(doc.content, "Admin revision")

    # =========================================================================
    # is_system is not user-settable (issue #239)
    # =========================================================================

    def test_non_admin_cannot_create_system_skill(self):
        """read_only is a form-layer concern; the API writes is_system happily."""
        frappe.set_user(self.NON_ADMIN_USER)
        doc = self._new_skill_doc("test-skill-is-system-create", self.NON_ADMIN_USER, is_system=1)
        with self.assertRaises(frappe.PermissionError):
            doc.insert()

    def test_non_admin_cannot_set_is_system_on_own_draft(self):
        frappe.set_user(self.NON_ADMIN_USER)
        doc = self._new_skill_doc("test-skill-is-system-update", self.NON_ADMIN_USER)
        doc.insert()
        self._created_skills.append(doc.name)

        doc.is_system = 1
        with self.assertRaises(frappe.PermissionError):
            doc.save()

    def test_admin_can_set_is_system(self):
        frappe.set_user("Administrator")
        doc = self._new_skill_doc("test-skill-is-system-admin", "Administrator", is_system=1)
        doc.insert(ignore_permissions=True)
        self._created_skills.append(doc.name)
        self.assertTrue(doc.is_system)

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

    # =========================================================================
    # get_skill_by_tool() access scoping + precedence (issue #239)
    # =========================================================================

    def test_get_skill_by_tool_excludes_other_users_private_skill(self):
        """Used to pick one arbitrary Published row, so a Private skill could mask a
        visible one on the same tool."""
        self._insert_as_admin(
            "test-skill-by-tool-private",
            self.NON_ADMIN_USER,
            status="Published",
            visibility="Private",
            linked_tool="by_tool_masking",
        )
        self._insert_as_admin(
            "test-skill-by-tool-public",
            "Administrator",
            status="Published",
            visibility="Public",
            linked_tool="by_tool_masking",
        )

        manager = SkillManager()
        found = manager.get_skill_by_tool("by_tool_masking", user=self.OTHER_NON_ADMIN_USER)
        self.assertIsNotNone(found)
        self.assertEqual(found["skill_id"], "test-skill-by-tool-public")

    def test_get_skill_by_tool_returns_none_when_nothing_accessible(self):
        self._insert_as_admin(
            "test-skill-by-tool-hidden",
            self.NON_ADMIN_USER,
            status="Published",
            visibility="Private",
            linked_tool="by_tool_hidden",
        )

        manager = SkillManager()
        self.assertIsNone(manager.get_skill_by_tool("by_tool_hidden", user=self.OTHER_NON_ADMIN_USER))

    def test_get_skill_by_tool_agrees_with_tool_skill_map(self):
        """The two resolvers must never disagree about which skill owns a tool."""
        self._insert_as_admin(
            "test-skill-by-tool-user",
            "Administrator",
            status="Published",
            visibility="Public",
            linked_tool="by_tool_precedence",
        )
        self._insert_as_admin(
            "test-skill-by-tool-system",
            "Administrator",
            status="Published",
            visibility="Public",
            linked_tool="by_tool_precedence",
            is_system=1,
        )

        manager = SkillManager()
        found = manager.get_skill_by_tool("by_tool_precedence", user="Administrator")
        mapped = manager.get_tool_skill_map(user="Administrator")["by_tool_precedence"]
        self.assertEqual(found["skill_id"], "test-skill-by-tool-system")
        self.assertEqual(found["skill_id"], mapped["skill_id"])
