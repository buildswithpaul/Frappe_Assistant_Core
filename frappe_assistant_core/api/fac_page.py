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

# A personal page keeps its form controls, which its own script may wire, but loses every tag
# that runs code, embeds another document or acts on the whole document.
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

    record = frappe.db.get_value("FAC Page", slug, ["published", "visibility", "owner"], as_dict=True)
    if record is None:
        _not_found()
    if record.visibility == SHARED:
        _check_shared_access(slug, record.published)
        draft = not record.published
    elif record.owner == user:
        draft = False
    else:
        # A personal page reads as missing, so the response does not reveal that it exists.
        _not_found()

    # Access was decided above; a shared page's reader cannot read the DocType itself.
    page = frappe.get_doc("FAC Page", slug)
    return {
        "title": page.title,
        "html": _served_html(page.html, draft, page.visibility),
        "script": "" if draft else page.script,
        "style": page.style,
        "draft": draft,
        "visibility": page.visibility,
        "owner_is_me": page.owner == user,
    }


def _not_found():
    frappe.throw(_("This page does not exist."), frappe.DoesNotExistError)


def _check_shared_access(name: str, published: int) -> None:
    """Refuse a shared page the session user may not open; empty roles mean System Managers only."""
    user_roles = set(frappe.get_roles())
    if SYSTEM_MANAGER in user_roles:
        return
    # An unpublished page reads as missing, so the response does not reveal that it exists.
    if not published:
        _not_found()
    allowed_roles = frappe.get_all(
        "FAC Page Role", filters={"parenttype": "FAC Page", "parent": name}, pluck="role"
    )
    if not user_roles.intersection(allowed_roles):
        frappe.throw(_("You are not allowed to view this page."), frappe.PermissionError)


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
