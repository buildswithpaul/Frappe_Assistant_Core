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

"""FAC Page records, the role-checked read endpoint and the host Desk page."""

import frappe

from frappe_assistant_core.api.fac_page import get_page
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestFACPage(BaseAssistantTest):
    def _make_page(self, published: int = 1, roles: tuple = (), **overrides) -> str:
        slug = overrides.pop("slug", f"test-page-{frappe.generate_hash(length=8).lower()}")
        doc = frappe.get_doc(
            {
                "doctype": "FAC Page",
                "title": "Team Planner",
                "slug": slug,
                "published": published,
                "roles": [{"role": role} for role in roles],
                "html": '<div class="mk-card">Plan</div>',
                "script": "root_element.querySelector('.mk-card').dataset.ready = '1';",
                "style": ".mk-card { color: red; }",
                **overrides,
            }
        )
        doc.insert(ignore_permissions=True)
        return doc.name

    def _act_as(self, prefix: str, roles: tuple = ()) -> None:
        # Production reaches get_page as the logged-in Desk user; these are such users with exactly
        # the roles the case needs, rolled back with the test transaction.
        user = self.make_throwaway_user(prefix, roles=roles)
        # nosemgrep: frappe-setuser — test acts as a non-Administrator inside the test transaction
        frappe.set_user(user)

    def test_a_listed_role_reads_the_page(self):
        slug = self._make_page(roles=("Report Manager",))
        self._act_as("fac-page-reader", roles=("Report Manager",))

        page = get_page(slug)

        self.assertEqual(page["title"], "Team Planner")
        self.assertEqual(page["html"], '<div class="mk-card">Plan</div>')
        self.assertIn("dataset.ready", page["script"])
        self.assertEqual(page["style"], ".mk-card { color: red; }")

    def test_a_user_without_a_listed_role_is_refused(self):
        slug = self._make_page(roles=("Report Manager",))
        self._act_as("fac-page-outsider", roles=("Workspace Manager",))

        with self.assertRaises(frappe.PermissionError):
            get_page(slug)

    def test_no_roles_means_system_manager_only(self):
        slug = self._make_page(roles=())
        self._act_as("fac-page-no-roles", roles=("Report Manager",))
        with self.assertRaises(frappe.PermissionError):
            get_page(slug)

        self._act_as("fac-page-sysman", roles=("System Manager",))
        self.assertEqual(get_page(slug)["title"], "Team Planner")

    def test_an_unpublished_page_does_not_exist_for_others(self):
        slug = self._make_page(published=0, roles=("Report Manager",))
        self._act_as("fac-page-draft-reader", roles=("Report Manager",))

        with self.assertRaises(frappe.DoesNotExistError) as caught:
            get_page(slug)
        self.assertNotIn("permission", str(caught.exception).lower())

    def test_a_system_manager_reads_an_unpublished_page(self):
        slug = self._make_page(published=0)
        self._act_as("fac-page-draft-sysman", roles=("System Manager",))

        self.assertEqual(get_page(slug)["html"], '<div class="mk-card">Plan</div>')

    def test_a_missing_page_does_not_exist(self):
        self._act_as("fac-page-missing", roles=("System Manager",))

        with self.assertRaises(frappe.DoesNotExistError):
            get_page("no-such-page")

    def test_guest_is_refused(self):
        slug = self._make_page(roles=("Guest",))
        # nosemgrep: frappe-setuser — an anonymous request runs as Guest
        frappe.set_user("Guest")

        with self.assertRaises(frappe.PermissionError):
            get_page(slug)

    def test_bad_slugs_are_refused(self):
        for slug in ("Team Planner", "a--b", "-x", "x-", "a" * 81):
            with self.subTest(slug=slug), self.assertRaises(frappe.ValidationError):
                self._make_page(slug=slug)

    def test_a_slug_naming_a_desk_page_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            self._make_page(slug="fac-page")

    def test_a_long_slug_up_to_the_limit_is_kept(self):
        self.assertEqual(self._make_page(slug="a" * 80), "a" * 80)

    def test_a_duplicate_slug_is_refused(self):
        self._make_page(slug="team-planner-dup")

        with self.assertRaises(frappe.DuplicateEntryError):
            self._make_page(slug="team-planner-dup")

    def test_the_host_page_is_installed(self):
        self.assertTrue(frappe.db.exists("Page", "fac-page"))

    def test_only_system_manager_has_doctype_permissions(self):
        roles = {perm.role for perm in frappe.get_meta("FAC Page").permissions}

        self.assertEqual(roles, {"System Manager"})
