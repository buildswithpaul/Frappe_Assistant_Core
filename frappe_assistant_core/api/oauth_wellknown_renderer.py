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
        # Handle /.well-known/openid-configuration
        if self.path == ".well-known/openid-configuration":
            metadata = self._get_openid_configuration()
            return self._json_response(metadata)

        # Handle /.well-known/oauth-authorization-server
        if self.path == ".well-known/oauth-authorization-server":
            from frappe_assistant_core.api.oauth_discovery import authorization_server_metadata

            metadata = authorization_server_metadata()
            return self._json_response(metadata)

        # Handle /.well-known/oauth-protected-resource
        if self.path == ".well-known/oauth-protected-resource":
            from frappe_assistant_core.api.oauth_discovery import protected_resource_metadata

            metadata = protected_resource_metadata()
            return self._json_response(metadata)

        # Unknown .well-known endpoint
        frappe.throw("Not Found", exc=frappe.NotFound)

    def _get_openid_configuration(self):
        """
        Get OpenID configuration without triggering redirects.

        We can't call openid_configuration() directly because it calls Frappe's
        built-in method which may trigger redirects. Instead, we build the
        response directly.
        """
        from frappe.oauth import get_server_url

        from frappe_assistant_core.utils.oauth_compat import get_oauth_settings

        frappe_url = get_server_url()
        settings = get_oauth_settings()

        # Build OpenID configuration metadata
        metadata = {
            "issuer": frappe_url,
            "authorization_endpoint": f"{frappe_url}/api/method/frappe.integrations.oauth2.authorize",
            "token_endpoint": f"{frappe_url}/api/method/frappe.integrations.oauth2.get_token",
            "userinfo_endpoint": f"{frappe_url}/api/method/frappe.integrations.oauth2.openid_profile",
            "revocation_endpoint": f"{frappe_url}/api/method/frappe.integrations.oauth2.revoke_token",
            "introspection_endpoint": f"{frappe_url}/api/method/frappe.integrations.oauth2.introspect_token",
            "response_types_supported": [
                "code",
                "token",
                "code id_token",
                "code token id_token",
                "id_token",
                "id_token token",
            ],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["HS256"],
            "jwks_uri": f"{frappe_url}/api/method/frappe_assistant_core.api.oauth_discovery.jwks",
            "code_challenge_methods_supported": ["S256"],
            "mcp_endpoint": f"{frappe_url}/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp",
            "mcp_transport": "StreamableHTTP",
            "mcp_protocol_version": "2025-03-26",
        }

        # Add registration endpoint if dynamic client registration is enabled
        if settings.get("enable_dynamic_client_registration"):
            metadata["registration_endpoint"] = (
                f"{frappe_url}/api/method/frappe_assistant_core.api.oauth_registration.register_client"
            )

        return metadata

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
