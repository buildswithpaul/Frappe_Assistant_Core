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

"""
Custom Page Renderer for .well-known OAuth endpoints

This is the proper way to handle .well-known endpoints in Frappe v15.
Instead of modifying app.py (like v16 does), we use the page_renderer hook
which allows custom renderers to handle specific paths.
"""

import frappe
from werkzeug.wrappers import Response


class WellKnownRenderer:
    """
    Custom page renderer for .well-known OAuth endpoints.

    This renderer intercepts requests to:
    - /.well-known/oauth-authorization-server
    - /.well-known/oauth-protected-resource
    - /.well-known/openid-configuration

    And returns proper JSON responses instead of HTML.
    """

    def __init__(self, path, http_status_code=200):
        self.path = path
        self.http_status_code = http_status_code

    def can_render(self):
        """Check if this renderer can handle the current path"""
        # Only handle .well-known paths with GET requests
        if not self.path.startswith(".well-known/"):
            return False

        if frappe.request.method != "GET":
            return False

        return True

    def render(self):
        """Render the .well-known endpoint response"""
        from frappe_assistant_core.api.oauth_discovery import (
            authorization_server_metadata,
            openid_configuration,
            protected_resource_metadata,
        )

        # Handle /.well-known/openid-configuration
        if self.path == ".well-known/openid-configuration":
            # openid_configuration() modifies frappe.local.response directly
            openid_configuration()
            metadata = frappe.local.response
            return self._json_response(metadata)

        # Handle /.well-known/oauth-authorization-server
        if self.path == ".well-known/oauth-authorization-server":
            metadata = authorization_server_metadata()
            return self._json_response(metadata)

        # Handle /.well-known/oauth-protected-resource
        if self.path == ".well-known/oauth-protected-resource":
            metadata = protected_resource_metadata()
            return self._json_response(metadata)

        # Unknown .well-known endpoint
        frappe.throw("Not Found", exc=frappe.NotFound)

    def _json_response(self, data):
        """Create a JSON response"""
        import json

        response = Response()
        response.status_code = self.http_status_code
        response.headers["Content-Type"] = "application/json"
        response.data = json.dumps(data, indent=2)

        return response
