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
Required for public clients (browser-based) to make registration and token requests.

Also handles OAuth token endpoint authentication bypass - prevents Frappe from
treating OAuth client credentials (in Authorization: Basic header) as User API keys.

COMPATIBILITY:
- Uses frappe.local.allow_cors (Frappe v16 mechanism)
- Also sets frappe.conf.allow_cors (v15 fallback)
- Ensures forward compatibility when users upgrade from v15 to v16
"""

import frappe

from frappe_assistant_core.utils.oauth_compat import get_oauth_settings


def set_cors_for_oauth_endpoints():
    """
    Set CORS headers for OAuth-related endpoints.

    This is called as a before_request hook and enables CORS for:
    1. Dynamic client registration endpoint
    2. Token, revocation, introspection, and userinfo endpoints
    3. Well-known discovery endpoints (openid-configuration, oauth-authorization-server, oauth-protected-resource)
    4. MCP endpoint (for browser-based MCP clients)

    Without CORS, public clients (like MCP Inspector) cannot make
    preflight OPTIONS requests or actual API calls from the browser.

    Additionally, this function bypasses Frappe's API key validation for OAuth
    token endpoints that use Authorization: Basic with client credentials.
    """
    if not frappe.local.request:
        return

    request_path = frappe.request.path
    request_method = frappe.request.method

    # Handle OAuth token endpoint authentication bypass FIRST
    # This must run before validate_auth() tries to validate Basic auth as API keys
    _handle_oauth_token_endpoint_auth(request_path)

    # Handle malformed concatenated URLs from OAuth clients
    # e.g., /.well-known/oauth-protected-resource/api/method/...
    if "/.well-known/" in request_path and "/api/method/" in request_path:
        _handle_malformed_wellknown_url(request_path, request_method)
        return

    # Handle well-known discovery endpoints directly to prevent Frappe's redirect
    # Frappe has a website_redirect that redirects these paths before page_renderer can handle them
    wellknown_endpoints = [
        "/.well-known/openid-configuration",
        "/.well-known/oauth-authorization-server",
        "/.well-known/oauth-protected-resource",
    ]

    for endpoint in wellknown_endpoints:
        if request_path == endpoint and request_method in ("GET", "OPTIONS"):
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
        "/api/method/frappe_assistant_core.api.oauth_discovery.authorization_server_metadata",
        "/api/method/frappe_assistant_core.api.oauth_discovery.protected_resource_metadata",
        "/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp",
    ]

    if any(request_path.startswith(endpoint) for endpoint in oauth_endpoints):
        if request_method in ("POST", "GET", "OPTIONS"):
            _set_allowed_cors()
        return


def _set_allowed_cors():
    """
    Set CORS headers for OAuth endpoints.

    CONFIGURATION (in order of precedence):
    1. frappe.conf.oauth_cors_allowed_origins (site_config.json) - RECOMMENDED
       Example: "oauth_cors_allowed_origins": "*"
       Example: "oauth_cors_allowed_origins": ["http://localhost:6274"]

    2. Assistant Core Settings > allowed_public_client_origins (EXPERIMENTAL)
       For users who prefer UI configuration over site_config.json

    COMPATIBILITY:
    - Sets frappe.local.allow_cors (Frappe V16 native support)
    - Sets frappe.conf.allow_cors (V15 fallback)

    NOTE: Most production deployments (Claude Desktop, Claude Web) do NOT need CORS.
    This is only for browser-based OAuth clients like MCP Inspector during development.
    """
    # Priority 1: Check site_config.json (frappe.conf)
    conf_origins = frappe.conf.get("oauth_cors_allowed_origins")

    if conf_origins:
        # Use site_config setting
        if conf_origins == "*":
            frappe.local.allow_cors = "*"
            frappe.conf.allow_cors = "*"
        elif isinstance(conf_origins, (list, tuple)):
            frappe.local.allow_cors = list(conf_origins)
            frappe.conf.allow_cors = list(conf_origins)
        return

    # Priority 2: Check Assistant Core Settings (EXPERIMENTAL)
    settings = get_oauth_settings()
    allowed = settings.get("allowed_public_client_origins")

    if not allowed:
        # No CORS configured - this is the expected state for production
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
    Handle well-known discovery endpoints directly to bypass Frappe's redirect.

    Handles:
    - /.well-known/openid-configuration (OpenID Connect Discovery)
    - /.well-known/oauth-authorization-server (RFC 8414 - Authorization Server Metadata)
    - /.well-known/oauth-protected-resource (RFC 9728 - Protected Resource Metadata)

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

    elif request_path == "/.well-known/oauth-authorization-server":
        from frappe_assistant_core.api.oauth_discovery import authorization_server_metadata

        metadata = authorization_server_metadata()

    elif request_path == "/.well-known/oauth-protected-resource":
        from frappe_assistant_core.api.oauth_discovery import protected_resource_metadata

        metadata = protected_resource_metadata()

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
                    "Access-Control-Allow-Headers": "Content-Type, MCP-Protocol-Version",
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
                    "Access-Control-Allow-Headers": "Content-Type, MCP-Protocol-Version",
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
                    "Access-Control-Allow-Headers": "Content-Type, MCP-Protocol-Version",
                    "Cache-Control": "public, max-age=3600",
                },
            )

        # Raise the response as an HTTPException to bypass normal processing
        from werkzeug.exceptions import HTTPException

        class ResponseException(HTTPException):
            def get_response(self, environ=None):
                return response

        raise ResponseException()


def _handle_oauth_token_endpoint_auth(request_path: str):
    """
    Bypass Frappe's API key validation for OAuth token endpoints.

    OAuth token endpoints use Authorization: Basic with client_id:client_secret,
    which is NOT a User API key. Frappe's validate_auth() incorrectly tries to
    validate this as a User API key and fails.

    This function monkey-patches frappe.get_request_header to hide the
    Authorization header from validate_auth() for OAuth token endpoints.

    This runs in before_request hook, BEFORE validate_auth() is called.
    """
    # OAuth token endpoints that use client credentials in Basic auth
    oauth_token_endpoints = [
        "/api/method/frappe.integrations.oauth2.get_token",
        "/api/method/frappe.integrations.oauth2.revoke_token",
        "/api/method/frappe.integrations.oauth2.introspect_token",
    ]

    # Check if this is an OAuth token endpoint
    if not any(request_path.startswith(ep) for ep in oauth_token_endpoints):
        return

    # Check if Authorization header is Basic (OAuth client credentials)
    auth_header = frappe.request.headers.get("Authorization", "")
    if not auth_header.startswith("Basic "):
        return

    # Store original get_request_header function
    original_get_request_header = frappe.get_request_header

    def patched_get_request_header(key, default=None):
        """
        Patched version that hides Authorization header from validate_auth().

        This prevents Frappe from treating OAuth client credentials as User API keys.
        Our custom oauth_token.py endpoint reads the header directly from request.headers.
        """
        if key.lower() == "authorization":
            # Hide the Basic auth header from Frappe's API key validation
            return default if default is not None else ""
        return original_get_request_header(key, default)

    # Apply the monkey-patch
    frappe.get_request_header = patched_get_request_header

    frappe.logger().debug(f"OAuth token endpoint auth bypass: hiding Authorization header for {request_path}")
