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
OAuth CORS Handler

Handles CORS (Cross-Origin Resource Sharing) for OAuth endpoints.
Required for public clients to make registration and token requests.
"""

import frappe

from frappe_assistant_core.utils.oauth_compat import get_oauth_settings


def set_cors_for_oauth_endpoints():
    """
    Set CORS headers for OAuth-related endpoints.

    This is called as a before_request hook and enables CORS for:
    1. Dynamic client registration endpoint
    2. Token, revocation, introspection, and userinfo endpoints
    3. Well-known discovery endpoints

    Without CORS, public clients (like MCP Inspector) cannot make
    preflight OPTIONS requests or actual API calls from the browser.
    """
    if not frappe.local.request:
        return

    request_path = frappe.request.path
    request_method = frappe.request.method

    # Handle malformed concatenated URLs from OAuth clients
    # e.g., /.well-known/oauth-protected-resource/api/method/...
    if "/.well-known/" in request_path and "/api/method/" in request_path:
        _handle_malformed_wellknown_url(request_path, request_method)
        return

    # Handle .well-known/openid-configuration directly to prevent Frappe's redirect
    # Frappe has a website_redirect that redirects this path before page_renderer can handle it
    if request_path == "/.well-known/openid-configuration" and request_method in ("GET", "OPTIONS"):
        _handle_wellknown_endpoint(request_path, request_method)
        return

    # Skip if CORS already allowed globally
    if frappe.conf.allow_cors == "*" or not frappe.local.request.headers.get("Origin"):
        return

    # Allow CORS for other well-known endpoints (GET and OPTIONS)
    if request_path.startswith("/.well-known/") and request_method in ("GET", "OPTIONS"):
        frappe.local.allow_cors = "*"
        return

    # Allow CORS for dynamic client registration endpoint
    if request_path.startswith(
        "/api/method/frappe_assistant_core.api.oauth_registration.register_client"
    ) and request_method in ("POST", "OPTIONS"):
        settings = get_oauth_settings()
        if settings.get("enable_dynamic_client_registration"):
            _set_allowed_cors()
        return

    # Allow CORS for OAuth token endpoints (for public clients)
    oauth_endpoints = [
        "/api/method/frappe.integrations.oauth2.get_token",
        "/api/method/frappe.integrations.oauth2.revoke_token",
        "/api/method/frappe.integrations.oauth2.introspect_token",
        "/api/method/frappe.integrations.oauth2.openid_profile",
        "/api/method/frappe_assistant_core.api.oauth_discovery.openid_configuration",
        "/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp",
    ]

    if any(request_path.startswith(endpoint) for endpoint in oauth_endpoints):
        if request_method in ("POST", "GET", "OPTIONS"):
            _set_allowed_cors()
        return


def _set_allowed_cors():
    """
    Set CORS headers based on allowed_public_client_origins setting.

    If allowed_public_client_origins contains "*", allow all origins.
    Otherwise, only allow origins in the whitelist.

    NOTE: For Frappe V15, we set frappe.conf.allow_cors (works immediately).
    For Frappe V16+, we also set frappe.local.allow_cors (native support).
    This ensures compatibility with both versions without restart.
    """
    settings = get_oauth_settings()
    allowed = settings.get("allowed_public_client_origins")

    if not allowed:
        return

    allowed = allowed.strip().splitlines()
    allowed = [origin.strip() for origin in allowed if origin.strip()]

    if "*" in allowed:
        # Set both for V15 and V16 compatibility
        frappe.conf.allow_cors = "*"
        frappe.local.allow_cors = "*"
    elif allowed:
        # Set both for V15 and V16 compatibility
        frappe.conf.allow_cors = allowed
        frappe.local.allow_cors = allowed


def _handle_wellknown_endpoint(request_path: str, request_method: str):
    """
    Handle .well-known/openid-configuration directly to bypass Frappe's redirect.

    Frappe V15 has a website_redirect that redirects /.well-known/openid-configuration
    to /api/method/frappe.integrations.oauth2.openid_configuration before our
    page_renderer can intercept it. This handler catches it in before_request.
    """
    import json

    from werkzeug.wrappers import Response

    # Determine which endpoint is being requested
    metadata = None

    if request_path == "/.well-known/openid-configuration":
        from frappe_assistant_core.api.oauth_discovery import openid_configuration

        openid_configuration()
        metadata = frappe.local.response

    if metadata:
        # Build a proper werkzeug Response and bypass Frappe's handler
        from werkzeug.wrappers import Response as WerkzeugResponse

        # Handle OPTIONS preflight request
        if request_method == "OPTIONS":
            response = WerkzeugResponse(
                "",
                status=200,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type",
                    "Access-Control-Max-Age": "3600",
                },
            )
        else:
            # Return JSON response for GET
            response = WerkzeugResponse(
                json.dumps(metadata, indent=2),
                status=200,
                headers={
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type",
                    "Cache-Control": "public, max-age=3600",
                },
            )

        # Raise the response as an HTTPException to bypass normal processing
        from werkzeug.exceptions import HTTPException

        class ResponseException(HTTPException):
            def get_response(self, environ=None):
                return response

        raise ResponseException()


def _handle_malformed_wellknown_url(request_path: str, request_method: str):
    """
    Handle malformed URLs where OAuth client concatenated .well-known with MCP endpoint.

    Some OAuth clients incorrectly parse the resource_metadata URL and concatenate it
    with the MCP endpoint, creating URLs like:
    /.well-known/oauth-protected-resource/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp

    This handler extracts the .well-known endpoint and returns the correct metadata.
    """
    import json

    from werkzeug.wrappers import Response

    # Extract the .well-known endpoint name
    wellknown_part = request_path.split("/api/method/")[0]

    # Determine which endpoint is being requested
    metadata = None

    if "openid-configuration" in wellknown_part:
        from frappe_assistant_core.api.oauth_discovery import openid_configuration

        openid_configuration()
        metadata = frappe.local.response

    elif "oauth-protected-resource" in wellknown_part:
        from frappe_assistant_core.api.oauth_discovery import protected_resource_metadata

        metadata = protected_resource_metadata()

    elif "oauth-authorization-server" in wellknown_part:
        from frappe_assistant_core.api.oauth_discovery import authorization_server_metadata

        metadata = authorization_server_metadata()

    if metadata:
        # Build a proper werkzeug Response and bypass Frappe's handler
        from werkzeug.wrappers import Response as WerkzeugResponse

        # Handle OPTIONS preflight request
        if request_method == "OPTIONS":
            response = WerkzeugResponse(
                "",
                status=200,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization, MCP-Protocol-Version",
                    "Access-Control-Max-Age": "3600",
                },
            )
        else:
            # Return JSON response for GET
            response = WerkzeugResponse(
                json.dumps(metadata, indent=2),
                status=200,
                headers={
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type",
                    "Cache-Control": "public, max-age=3600",
                },
            )

        # Raise the response as an HTTPException to bypass normal processing
        from werkzeug.exceptions import HTTPException

        class ResponseException(HTTPException):
            def get_response(self, environ=None):
                return response

        raise ResponseException()
