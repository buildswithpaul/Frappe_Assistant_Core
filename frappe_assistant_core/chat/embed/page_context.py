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
No client text reaches the prompt: a path can come from a link anyone sent the
user, and page text such as a ticket subject is written by outsiders. The line
names only the app, and a document once it is confirmed to exist and be
readable; the model then reads that document through its tools, under the
user's own permissions.
"""

import json
import re
from urllib.parse import unquote

import frappe

from frappe_assistant_core.chat.embed.apps import discover_spa_apps

# Per app, the paths (after the app's route) that show one document.
PAGE_DOCUMENTS = {
    "helpdesk": [
        (r"tickets/(?P<name>[^/]+)", "HD Ticket"),
        (r"my-tickets/(?P<name>[^/]+)", "HD Ticket"),
    ],
    "crm": [(r"leads/(?P<name>[^/]+)", "CRM Lead"), (r"deals/(?P<name>[^/]+)", "CRM Deal")],
    "insights": [
        (r"dashboards/(?P<name>[^/]+)", "Insights Dashboard v3"),
        (r"workbook/[^/]+/chart/(?P<name>[^/]+)", "Insights Chart v3"),
        (r"workbook/[^/]+/query/(?P<name>[^/]+)", "Insights Query v3"),
    ],
}
SAFE_PATH = re.compile(r"/[A-Za-z0-9._~%/-]{0,199}")
SAFE_NAME = re.compile(r"[A-Za-z0-9._-]{1,140}")


def render_page_context(raw) -> str:
    """The prompt section for a widget message's page, or "". Never raises."""
    try:
        page = _resolve(raw)
    except Exception:
        return ""
    if not page:
        return ""
    if page["doctype"]:
        line = (
            f"The user is viewing {page['doctype']} {page['name']} in {page['title']}. When the "
            f'question is about it, read it with get_document (doctype "{page["doctype"]}", '
            f'name "{page["name"]}").'
        )
    else:
        line = f"The user is on a {page['title']} page."
    return "\n\n## Page Context\n\n" + line


def storable_context(context):
    """What FAC Chat Message can store for this context.

    A widget page becomes a "Page" record; its Context Type Select has no
    "app_page". Any other context is passed through unchanged.
    """
    if not isinstance(context, dict) or context.get("type") != "app_page":
        return context or None
    try:
        page = _resolve(context)
    except Exception:
        page = None
    if not page:
        return None
    return {"type": "Page", "url": page["path"], "doctype": page["doctype"], "name": page["name"]}


def _resolve(raw) -> dict | None:
    data = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(data, dict) or data.get("type") != "app_page":
        return None
    path = data.get("path")
    if not isinstance(path, str) or not SAFE_PATH.fullmatch(path):
        return None
    path = path.rstrip("/") or "/"
    app = next(
        (a for a in discover_spa_apps() if path == a["route"] or path.startswith(a["route"] + "/")),
        None,
    )
    if not app:
        return None
    doctype, name = _document_on(app["app"], path[len(app["route"]) :].lstrip("/")) or (None, None)
    return {"title": app["title"], "path": path, "doctype": doctype, "name": name}


def _document_on(app: str, rest: str) -> tuple[str, str] | None:
    for pattern, doctype in PAGE_DOCUMENTS.get(app, []):
        match = re.fullmatch(pattern, rest)
        if not match:
            continue
        name = unquote(match.group("name"))
        if not SAFE_NAME.fullmatch(name):
            return None
        if (
            frappe.db.exists("DocType", doctype)
            and frappe.db.exists(doctype, name)
            and frappe.has_permission(doctype, "read", doc=name)
        ):
            return doctype, name
        return None
    return None
