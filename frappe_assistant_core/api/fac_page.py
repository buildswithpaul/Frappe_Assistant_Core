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

import re

import frappe
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
_CSS_ESCAPE = re.compile(r"\\([0-9a-fA-F]{1,6})\s?|\\(.)", re.DOTALL)
_CSS_IMPORT = re.compile(r"@import\b[^;]*;?", re.IGNORECASE)
# A url() or image-set() value, allowing one level of nested parentheses.
_CSS_FETCH = re.compile(r"(?:url|(?:-webkit-)?image-set)\s*\((?:[^()]|\([^()]*\))*\)", re.IGNORECASE)


@frappe.whitelist(methods=["GET"])
def get_page(slug: str) -> dict:
    """Return a FAC Page's title, html, script, style and draft flag if the session user may see it.

    The FAC Page DocType is System Manager only, so access to a page is decided here from
    its ``published`` flag and ``roles`` table rather than by DocType permission. A draft is
    served without its script and with sanitised html and style: it is dormant, so previewing it
    must run no code and reach no other server until it is published (publishing goes through
    an approval card).
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
        "style": _draft_style(page.style) if draft else page.style,
        "draft": draft,
    }


def _draft_html(html: str | None) -> str | None:
    """A draft's html without inline handlers, javascript: links, form controls or url() values.

    The host page's create_shadow_element strips only <script> and <style>, so attributes such
    as onerror would still run in the previewer's session.
    """
    html = sanitize_html(html, always_sanitize=True, disallowed_tags=DRAFT_DISALLOWED_TAGS)
    # Inline style attributes keep url() through sanitize_html.
    return _CSS_FETCH.sub("none", html) if html else html


def _unescape_css(match: re.Match) -> str:
    hex_digits, char = match.groups()
    if hex_digits is None:
        return char
    code = int(hex_digits, 16)
    return chr(code) if 0 < code <= 0x10FFFF and not 0xD800 <= code <= 0xDFFF else "\ufffd"


def _draft_style(style: str | None) -> str | None:
    """A draft's style without @import rules or url()/image-set() values, so it fetches nothing.

    CSS escapes are decoded first, so a spelling such as ``\\75 rl(`` is caught too. A backslash
    left after decoding (from an escaped backslash) is dropped, or the browser would decode again.
    """
    if not style:
        return style
    style = _CSS_ESCAPE.sub(_unescape_css, style).replace("\\", "")
    return _CSS_FETCH.sub("none", _CSS_IMPORT.sub("", style))
