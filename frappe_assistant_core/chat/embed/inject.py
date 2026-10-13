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

"""after_request: put the widget loader on the pages of Frappe apps an admin enabled.

Checked cheapest-first so the many requests that are not an enabled app's HTML
page pay almost nothing. Any failure leaves the response exactly as it was.
"""

import frappe

from frappe_assistant_core.chat.embed.apps import enabled_routes
from frappe_assistant_core.chat.gate import is_chat_enabled

LOADER_PATH = "/assets/frappe_assistant_core/chat/widget/widget_embed.js"
BODY_END = "</body>"


def _on_enabled_route(path: str, routes: list[str]) -> bool:
    return any(path == route or path.startswith(route + "/") for route in routes)


def _script_tag() -> str:
    from frappe_assistant_core.hooks import _widget_asset

    return f'<script src="{_widget_asset(LOADER_PATH)}" defer></script>'


def inject_widget(response, request) -> None:
    try:
        if request.method != "GET" or response.status_code != 200 or response.mimetype != "text/html":
            return
        if response.direct_passthrough or response.is_streamed:
            return
        if not _on_enabled_route(request.path, enabled_routes()):
            return
        user = frappe.session.user
        if user == "Guest" or frappe.get_cached_value("User", user, "user_type") != "System User":
            return
        if not is_chat_enabled():
            return
        html = response.get_data(as_text=True)
        at = html.rfind(BODY_END)
        if at == -1:
            return
        response.set_data(html[:at] + _script_tag() + html[at:])
    except Exception:
        frappe.logger("frappe_assistant_core").warning("FAC widget embed skipped", exc_info=True)
