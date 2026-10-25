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

"""A full page stored in the database and shown by the ``fac-pages`` Desk page.

A page is personal ("Only me") or Shared. Any Desk user can build a personal page, and it opens
only for that user. Only System Managers can share a page, publish it, give it roles or change a
shared one.
"""

import hashlib
import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SLUG_MAX_LENGTH = 80
PERSONAL = "Only me"
SHARED = "Shared"
SYSTEM_MANAGER = "System Manager"


def owner_tag(user: str) -> str:
    """The suffix that keeps one user's personal page name apart from another's with the same slug."""
    return hashlib.sha1(user.encode()).hexdigest()[:6]


def is_system_manager(user: str) -> bool:
    return SYSTEM_MANAGER in frappe.get_roles(user)


def is_desk_user(user: str) -> bool:
    """A System User: one who works at the Desk, as opposed to a Website User."""
    return frappe.get_cached_value("User", user, "user_type") == "System User"


class FACPage(Document):
    def autoname(self):
        # A shared page is named by its slug; a personal one adds its owner's tag, so two users can
        # use the same slug. The primary key keeps a personal name from taking a shared one.
        if self.visibility == SHARED:
            self.name = self.slug
        else:
            self.name = f"{self.slug}-{owner_tag(self.owner)}"

    def validate(self):
        stored = (
            None
            if self.is_new()
            else frappe.db.get_value("FAC Page", self.name, ["slug", "visibility"], as_dict=True)
        )
        self.drop_audience_when_unshared(stored)
        self.validate_builder(stored)
        self.validate_slug()
        self.validate_slug_unchanged(stored)
        self.validate_slug_free()

    def drop_audience_when_unshared(self, stored):
        # A personal page opens for its owner alone, whatever its roles or published flag say.
        # Left in place they would lock the owner out of their own page, and come back live if
        # it were shared again; sharing again starts from an unpublished page with no roles.
        if stored and stored.visibility == SHARED and self.visibility != SHARED:
            self.published = 0
            self.set("roles", [])

    def validate_builder(self, stored):
        user = frappe.session.user
        if not is_desk_user(user):
            frappe.throw(_("Only Desk users can build pages."))
        if is_system_manager(user):
            return
        # A DocShare can let another user past has_permission; the page stays its owner's alone.
        if not self.is_new() and self.owner != user:
            frappe.throw(_("Only the page's owner or a System Manager can change it."))
        if self.visibility == SHARED or (stored and stored.visibility == SHARED):
            frappe.throw(_("Only a System Manager can share a page or change a shared one."))
        if self.roles or cint(self.published):
            frappe.throw(_("Only a System Manager can publish a page or choose who opens it."))

    def validate_slug(self):
        if len(self.slug or "") > SLUG_MAX_LENGTH or not SLUG_PATTERN.match(self.slug or ""):
            frappe.throw(
                _(
                    "Slug must be lower-case letters and digits in words joined by single hyphens, "
                    "at most {0} characters."
                ).format(SLUG_MAX_LENGTH)
            )

    def validate_slug_unchanged(self, stored):
        # The slug is in the record's name; set_only_once alone is skipped by some write paths.
        if stored and self.slug != stored.slug:
            frappe.throw(_("The slug cannot change after the page is saved."))

    def validate_slug_free(self):
        filters = {"slug": self.slug, "visibility": self.visibility, "name": ["!=", self.name]}
        if self.visibility != SHARED:
            filters["owner"] = self.owner
        if frappe.db.exists("FAC Page", filters):
            frappe.throw(
                _("A page with the slug {0} already exists.").format(self.slug), frappe.DuplicateEntryError
            )


def has_permission(doc, ptype: str | None = None, user: str | None = None, debug: bool = False) -> bool:
    """A System Manager may act on any page; anyone else only on their own personal page.

    A System Manager reads someone else's personal page as a record, with its code as text, never
    rendered: get_page serves a personal page only to its owner.
    """
    user = user or frappe.session.user
    if is_system_manager(user):
        return True
    return is_desk_user(user) and doc.owner == user and doc.visibility == PERSONAL


def get_permission_query_conditions(user: str | None = None) -> str:
    """List views show a user their own personal pages, and a System Manager shared pages too.

    Someone else's personal page is listed nowhere; a System Manager can still open it by name.
    """
    user = user or frappe.session.user
    mine = f"(`tabFAC Page`.`owner` = {frappe.db.escape(user)} and `tabFAC Page`.`visibility` = '{PERSONAL}')"
    if is_system_manager(user):
        return f"({mine} or `tabFAC Page`.`visibility` = '{SHARED}')"
    return mine
