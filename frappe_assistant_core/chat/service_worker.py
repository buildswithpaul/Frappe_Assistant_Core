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

"""Serves FAC Chat's service worker at /copilot/sw.js.

A service worker only controls pages under the path its script is served
from, and the build lands in /assets/, so the script is served from within
the SPA's path instead. A page renderer keeps that in app code, with no web
server configuration. Raven serves its worker the same way.
"""

import os

import frappe
from frappe.website.page_renderers.base_renderer import BaseRenderer
from werkzeug.wrappers import Response

from frappe_assistant_core.chat.gate import is_chat_enabled

SERVICE_WORKER_PATH = "/copilot/sw.js"


class FACChatServiceWorker(BaseRenderer):
    def can_render(self):
        # The /copilot/<path> route rule rewrites the path before renderers run,
        # so match on the original request path. With chat off, the request falls
        # through to the /copilot page, which answers 404.
        request = getattr(frappe.local, "request", None)
        return bool(request) and request.path == SERVICE_WORKER_PATH and is_chat_enabled()

    def render(self):
        file_path = frappe.get_app_path("frappe_assistant_core", "public", "chat", "spa", "sw.js")
        if not os.path.exists(file_path):
            return Response("// service worker not built", status=404, mimetype="text/javascript")
        with open(file_path, "rb") as f:  # nosemgrep: frappe-security-file-traversal
            content = f.read()
        return Response(
            content,
            mimetype="text/javascript",
            # Revalidated on every update check, so a deploy reaches installed apps
            # without waiting out a cached copy of the old worker.
            headers={"Cache-Control": "no-cache, max-age=0, must-revalidate"},
        )
