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
from frappe import _
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
        # Get metadata by calling the actual API methods
        metadata = self._get_metadata_for_path(self.path)

        if metadata is None:
            # Unknown .well-known endpoint
            frappe.throw(_("Not Found"), exc=frappe.NotFound)

        return self._json_response(metadata)

    def _get_metadata_for_path(self, path):
        """
        Get metadata for the given .well-known path by calling the actual API methods.

        This ensures we have a single source of truth and no code duplication.
        """
        # Handle /.well-known/openid-configuration
        if path == ".well-known/openid-configuration":
            from frappe_assistant_core.api.oauth_discovery import openid_configuration

            # Call the API method - it sets frappe.local.response
            openid_configuration()
            return frappe.local.response

        # Handle /.well-known/oauth-authorization-server
        if path == ".well-known/oauth-authorization-server":
            from frappe_assistant_core.api.oauth_discovery import authorization_server_metadata

            return authorization_server_metadata()

        # Handle /.well-known/oauth-protected-resource
        if path == ".well-known/oauth-protected-resource":
            from frappe_assistant_core.api.oauth_discovery import protected_resource_metadata

            return protected_resource_metadata()

        # Unknown endpoint
        return None

    def _json_response(self, data):
        """Create a JSON response with CORS headers"""
        import json

        response = Response()
        response.status_code = self.http_status_code
        response.headers["Content-Type"] = "application/json"
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Cache-Control"] = "public, max-age=3600"  # Cache for 1 hour
        response.data = json.dumps(data, indent=2)

        return response
