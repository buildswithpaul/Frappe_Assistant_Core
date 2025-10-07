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
    # Skip if no request or CORS already allowed globally
    if (
        frappe.conf.allow_cors == "*"
        or not frappe.local.request
        or not frappe.local.request.headers.get("Origin")
    ):
        return

    request_path = frappe.request.path
    request_method = frappe.request.method

    # Allow CORS for well-known endpoints (GET and OPTIONS)
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
    """
    settings = get_oauth_settings()
    allowed = settings.get("allowed_public_client_origins")

    if not allowed:
        return

    allowed = allowed.strip().splitlines()
    allowed = [origin.strip() for origin in allowed if origin.strip()]

    if "*" in allowed:
        frappe.local.allow_cors = "*"
    elif allowed:
        frappe.local.allow_cors = allowed
