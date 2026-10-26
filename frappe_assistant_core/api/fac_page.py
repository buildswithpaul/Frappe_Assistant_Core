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

"""Read endpoint for FAC Page records, shown by the ``fac-pages`` Desk page."""

import frappe
from bs4 import BeautifulSoup
from frappe import _
from frappe.utils.html_utils import sanitize_html

from frappe_assistant_core.assistant_core.doctype.fac_page.fac_page import SHARED, SYSTEM_MANAGER

_OPEN, _NOT_FOUND, _NOT_ALLOWED = "open", "not found", "not allowed"

# Tags that act on the whole document (a refresh, a stylesheet), or that could draw a fake
# prompt posting to another server, rather than showing the page.
DRAFT_DISALLOWED_TAGS = [
    "meta",
    "link",
    "html",
    "head",
    "body",
    "form",
    "input",
    "button",
    "select",
    "textarea",
]

# sanitize_html keeps only Frappe's allowlisted tags and attributes, and only safe URL schemes
# (no javascript: or data:). A personal page keeps its form controls, which its own script may
# wire, but also loses these allowlisted tags: ones that act on the whole document, and SVG
# animation, which can set an attribute to a javascript: URL after the page is sanitised.
PERSONAL_DISALLOWED_TAGS = [
    "script",
    "iframe",
    "object",
    "embed",
    "meta",
    "link",
    "base",
    "html",
    "head",
    "body",
    "animate",
    "animateColor",
    "animateMotion",
    "animateTransform",
    "set",
]


@frappe.whitelist(methods=["GET"])
def get_page(slug: str) -> dict:
    """Return a FAC Page for the session user to render, if they may open it.

    ``slug`` is the record name, which for a personal page is not its slug. A personal page opens
    only for its owner, and reads as missing for everyone else, System Managers included. A shared
    page's access is decided here from its ``published`` flag and ``roles`` table rather than by
    DocType permission. A shared draft is served without its script and with sanitised html: it is
    dormant, so previewing it must run no code until it is published (publishing goes through an
    approval card). The host page renders a draft in a sandboxed iframe whose CSP blocks scripts
    and fetches; this is defence in depth.
    """
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Log in to view this page."), frappe.PermissionError)

    access = _page_access(slug, user)
    # A page the user may not see at all reads as missing, so the response does not reveal it.
    if access == _NOT_FOUND:
        frappe.throw(_("This page does not exist."), frappe.DoesNotExistError)
    if access == _NOT_ALLOWED:
        frappe.throw(_("You are not allowed to view this page."), frappe.PermissionError)

    # Access was decided above; a shared page's reader cannot read the DocType itself.
    page = frappe.get_doc("FAC Page", slug)
    draft = page.visibility == SHARED and not page.published
    return {
        "title": page.title,
        "html": _served_html(page.html, draft, page.visibility),
        "script": "" if draft else page.script,
        "style": page.style,
        "draft": draft,
        "visibility": page.visibility,
        "owner_is_me": page.owner == user,
    }


def can_open_page(name: str, user: str) -> bool:
    """Whether ``user`` may open the FAC Page ``name``, decided as ``get_page`` decides it."""
    return _page_access(name, user) == _OPEN


def roles_that_open_page(name: str) -> list[str]:
    """Roles that open the page: none for a personal page, which opens for its owner alone; for a
    shared page its listed roles while published, and always System Manager."""
    record = frappe.db.get_value("FAC Page", name, ["published", "visibility"], as_dict=True)
    if record is None or record.visibility != SHARED:
        return []
    roles = _listed_roles(name) if record.published else []
    return list(dict.fromkeys([*roles, SYSTEM_MANAGER]))


def _page_access(name: str, user: str) -> str:
    """``_OPEN``, ``_NOT_FOUND`` or ``_NOT_ALLOWED`` for ``user`` and the FAC Page ``name``.

    A personal page opens for its owner only, and is not found for anyone else, System Managers
    included. A published shared page opens for a System Manager or a holder of one of its roles,
    so a shared page with no roles is System Manager only. An unpublished shared page opens for a
    System Manager only, and is not found for anyone else.
    """
    if user == "Guest":
        return _NOT_ALLOWED
    record = frappe.db.get_value("FAC Page", name, ["published", "visibility", "owner"], as_dict=True)
    if record is None:
        return _NOT_FOUND
    if record.visibility != SHARED:
        return _OPEN if record.owner == user else _NOT_FOUND
    user_roles = set(frappe.get_roles(user))
    is_system_manager = SYSTEM_MANAGER in user_roles
    if not record.published and not is_system_manager:
        return _NOT_FOUND
    if is_system_manager or user_roles.intersection(_listed_roles(name)):
        return _OPEN
    return _NOT_ALLOWED


def _listed_roles(name: str) -> list[str]:
    """The roles in the page's FAC Page Role rows."""
    return frappe.get_all("FAC Page Role", filters={"parenttype": "FAC Page", "parent": name}, pluck="role")


def _served_html(html: str | None, draft: bool, visibility: str) -> str | None:
    """The html a host page may render: a shared published page's as approved on its publish
    card; a draft's and a personal page's cleaned of inline code."""
    if draft:
        return _draft_html(html)
    if visibility != SHARED:
        return _personal_html(html)
    return html


def _personal_html(html: str | None) -> str | None:
    """A personal page's html without inline handlers, javascript: URLs or code-bearing tags.

    The page's code may only live in ``script``, which the host pages run once the owner has seen
    it and clicked Run new version. An inline handler in the html would run without that.
    """
    return sanitize_html(html, always_sanitize=True, disallowed_tags=PERSONAL_DISALLOWED_TAGS)


def _draft_html(html: str | None) -> str | None:
    """A draft's html without inline handlers, form controls or link targets.

    Defence in depth for most of it: the host page already renders a draft in an empty-sandbox
    iframe, where none of these could run or submit. A link could still navigate that frame to a
    remote page, so anchors and image-map areas lose their href.
    """
    html = sanitize_html(html, always_sanitize=True, disallowed_tags=DRAFT_DISALLOWED_TAGS)
    if not html:
        return html
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all(["a", "area"]):
        for attr in ("href", "xlink:href", "target", "ping"):
            link.attrs.pop(attr, None)
    return str(soup)
