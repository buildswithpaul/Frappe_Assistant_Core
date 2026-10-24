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

SYSTEM_MANAGER = "System Manager"
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


@frappe.whitelist(methods=["GET"])
def get_page(slug: str) -> dict:
    """Return a FAC Page's title, html, script, style and draft flag if the session user may see it.

    The FAC Page DocType is System Manager only, so access to a page is decided here from
    its ``published`` flag and ``roles`` table rather than by DocType permission. A draft is
    served without its script and with sanitised html: it is dormant, so previewing it must run no
    code until it is published (publishing goes through an approval card). The host page renders
    a draft in a sandboxed iframe whose CSP blocks scripts and fetches; this is defence in depth.
    """
    if frappe.session.user == "Guest":
        frappe.throw(_("Log in to view this page."), frappe.PermissionError)

    user_roles = set(frappe.get_roles())
    is_system_manager = SYSTEM_MANAGER in user_roles

    published = frappe.db.get_value("FAC Page", slug, "published")
    # An unpublished page reads as missing, so the response does not reveal that it exists.
    if published is None or (not published and not is_system_manager):
        frappe.throw(_("This page does not exist."), frappe.DoesNotExistError)

    if not is_system_manager:
        allowed_roles = frappe.get_all(
            "FAC Page Role", filters={"parenttype": "FAC Page", "parent": slug}, pluck="role"
        )
        if not user_roles.intersection(allowed_roles):
            frappe.throw(_("You are not allowed to view this page."), frappe.PermissionError)

    # Access was decided above; the reader cannot read the DocType itself.
    page = frappe.get_doc("FAC Page", slug)
    draft = not published
    return {
        "title": page.title,
        "html": _draft_html(page.html) if draft else page.html,
        "script": "" if draft else page.script,
        "style": page.style,
        "draft": draft,
    }


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
