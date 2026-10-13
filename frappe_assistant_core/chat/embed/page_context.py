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
"""Which page a widget user is on in another Frappe app, as one server-written prompt line.

Desk answers this through browser tools. Standalone apps (Helpdesk, CRM,
Insights…) cannot, so the widget sends the page's path with each message.
Only the path crosses over: page text such as a ticket subject is written by
outsiders, so it is never put in the prompt. The model reads a named document
through its tools, under the user's own permissions.
"""

import json
import re
from urllib.parse import unquote

import frappe

from frappe_assistant_core.chat.embed.apps import discover_spa_apps

# Per app, the paths (after the app's route) that show one document.
PAGE_DOCUMENTS = {
    "helpdesk": [(r"tickets/(?P<name>[^/]+)", "HD Ticket")],
    "crm": [(r"leads/(?P<name>[^/]+)", "CRM Lead"), (r"deals/(?P<name>[^/]+)", "CRM Deal")],
    "insights": [
        (r"dashboards/(?P<name>[^/]+)", "Insights Dashboard v3"),
        (r"workbook/[^/]+/chart/(?P<name>[^/]+)", "Insights Chart v3"),
        (r"workbook/[^/]+/query/(?P<name>[^/]+)", "Insights Query v3"),
    ],
}
SAFE_PATH = re.compile(r"/[A-Za-z0-9._~%/-]{0,199}")


def render_page_context(raw) -> str:
    """The prompt section for a widget message's page, or "". Never raises."""
    try:
        return _render(raw)
    except Exception:
        return ""


def _render(raw) -> str:
    data = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(data, dict) or data.get("type") != "app_page":
        return ""
    path = data.get("path")
    if not isinstance(path, str) or not SAFE_PATH.fullmatch(path):
        return ""
    path = path.rstrip("/") or "/"
    app = next(
        (a for a in discover_spa_apps() if path == a["route"] or path.startswith(a["route"] + "/")),
        None,
    )
    if not app:
        return ""
    line = f"The user is on {path} in {app['title']}."
    document = _document_on(app["app"], path[len(app["route"]) :].lstrip("/"))
    if document:
        doctype, name = document
        line = (
            f"The user is viewing {doctype} {name} in {app['title']} ({path}). When the question "
            f'is about it, read it with get_document (doctype "{doctype}", name "{name}").'
        )
    return "\n\n## Page Context\n\n" + line


def _document_on(app: str, rest: str) -> tuple[str, str] | None:
    for pattern, doctype in PAGE_DOCUMENTS.get(app, []):
        match = re.fullmatch(pattern, rest)
        if not match:
            continue
        name = unquote(match.group("name"))
        if any(ord(char) < 32 for char in name):
            return None
        if (
            frappe.db.exists("DocType", doctype)
            and frappe.db.exists(doctype, name)
            and frappe.has_permission(doctype, "read", doc=name)
        ):
            return doctype, name
        return None
    return None
