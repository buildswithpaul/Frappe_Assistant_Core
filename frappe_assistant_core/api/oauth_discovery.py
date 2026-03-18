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
Enhanced OAuth/OIDC Discovery Endpoints

Extends Frappe's built-in OAuth endpoints with:
- jwks_uri (required by MCP Inspector)
- PKCE support (S256 code challenge method)
- MCP metadata
"""

import frappe
from frappe.oauth import get_server_url


@frappe.whitelist(allow_guest=True, methods=["GET"])
def openid_configuration():
    """
    Enhanced OpenID Connect Discovery endpoint.

    Extends Frappe's built-in endpoint with MCP-required fields.
    """
    from frappe_assistant_core.utils.oauth_compat import get_oauth_settings

    # Call Frappe's built-in method (it sets frappe.local.response directly)
    # Note: Function name varies by version (openid_configuration in v15, get_openid_configuration in v16+)
    try:
        # Try v16+ first
        from frappe.integrations.oauth2 import get_openid_configuration as frappe_openid_config
    except ImportError:
        # Fallback to v15
        from frappe.integrations.oauth2 import openid_configuration as frappe_openid_config

    frappe_openid_config()

    # Get the response that Frappe set
    metadata = frappe.local.response

    # Add MCP-required fields that are missing
    frappe_url = get_server_url()

    # Add jwks_uri (required by MCP Inspector)
    metadata["jwks_uri"] = f"{frappe_url}/api/method/frappe_assistant_core.api.oauth_discovery.jwks"

    # Add PKCE support (required by MCP Inspector)
    metadata["code_challenge_methods_supported"] = ["S256"]

    # Add MCP-specific metadata (optional but useful) - read from settings
    settings = get_oauth_settings()

    # Get MCP configuration from Assistant Core Settings
    mcp_protocol_version = "2025-06-18"
    mcp_transport = "StreamableHTTP"
    try:
        core_settings = frappe.get_single("Assistant Core Settings")
        mcp_protocol_version = core_settings.mcp_protocol_version or mcp_protocol_version
        mcp_transport = core_settings.mcp_transport_type or mcp_transport
    except Exception:
        pass

    metadata["mcp_endpoint"] = f"{frappe_url}/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp"
    metadata["mcp_transport"] = mcp_transport
    metadata["mcp_protocol_version"] = mcp_protocol_version

    # Add registration endpoint if dynamic client registration is enabled
    if settings.get("enable_dynamic_client_registration"):
        metadata["registration_endpoint"] = (
            f"{frappe_url}/api/method/frappe_assistant_core.api.oauth_registration.register_client"
        )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def jwks():
    """
    JSON Web Key Set endpoint.

    Returns the public keys for verifying JWT signatures.
    MCP Inspector requires this endpoint for OAuth validation.
    """
    # Frappe doesn't use JWT for OAuth, but MCP Inspector validates the presence of this endpoint
    return {"keys": []}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def mcp_discovery():
    """
    MCP-specific discovery endpoint.

    Returns MCP server capabilities and endpoint information.
    """
    from frappe_assistant_core import hooks

    frappe_url = get_server_url()

    # Get MCP configuration from settings
    mcp_protocol_version = "2025-06-18"
    mcp_transport = "StreamableHTTP"
    mcp_server_name = "frappe-assistant-core"
    try:
        core_settings = frappe.get_single("Assistant Core Settings")
        mcp_protocol_version = core_settings.mcp_protocol_version or mcp_protocol_version
        mcp_transport = core_settings.mcp_transport_type or mcp_transport
        mcp_server_name = core_settings.mcp_server_name or mcp_server_name
    except Exception:
        pass

    return {
        "mcp_endpoint": f"{frappe_url}/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp",
        "mcp_transport": mcp_transport,
        "mcp_protocol_version": mcp_protocol_version,
        "oauth_metadata_url": f"{frappe_url}/.well-known/openid-configuration",
        "capabilities": {"tools": True, "prompts": False, "resources": False, "streaming": False},
        "server_info": {
            "name": hooks.app_name,
            "version": hooks.app_version,
            "description": hooks.app_description,
            "title": hooks.app_title,
            "publisher": hooks.app_publisher,
        },
    }


def _get_frappe_authorization_server_metadata():
    """
    Get base authorization server metadata from Frappe.

    Uses Frappe V16's built-in method if available, otherwise builds
    metadata manually for V15 compatibility.
    """
    try:
        # Try Frappe V16 method first
        from frappe.integrations.oauth2 import _get_authorization_server_metadata

        return _get_authorization_server_metadata()
    except ImportError:
        # Fallback for Frappe V15 - build metadata manually
        frappe_url = get_server_url()

        # Base metadata following RFC 8414
        metadata = {
            "issuer": frappe_url,
            "authorization_endpoint": f"{frappe_url}/api/method/frappe.integrations.oauth2.authorize",
            "token_endpoint": f"{frappe_url}/api/method/frappe.integrations.oauth2.get_token",
            "response_types_supported": ["code"],
            "response_modes_supported": ["query"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_methods_supported": ["none", "client_secret_basic"],
            "service_documentation": "https://docs.frappe.io/framework/user/en/guides/integration/how_to_set_up_oauth",
            "revocation_endpoint": f"{frappe_url}/api/method/frappe.integrations.oauth2.revoke_token",
            "revocation_endpoint_auth_methods_supported": ["client_secret_basic"],
            "introspection_endpoint": f"{frappe_url}/api/method/frappe.integrations.oauth2.introspect_token",
            "userinfo_endpoint": f"{frappe_url}/api/method/frappe.integrations.oauth2.openid_profile",
            "code_challenge_methods_supported": ["S256"],
        }

        return metadata


@frappe.whitelist(allow_guest=True, methods=["GET"])
def authorization_server_metadata():
    """
    OAuth 2.0 Authorization Server Metadata endpoint.

    Implements RFC 8414 - OAuth 2.0 Authorization Server Metadata
    https://datatracker.ietf.org/doc/html/rfc8414

    Endpoint: /api/method/frappe_assistant_core.api.oauth_discovery.authorization_server_metadata
    Also accessible via: /.well-known/oauth-authorization-server (if configured)

    Returns metadata about the authorization server's endpoints, supported
    features, and capabilities.
    """
    from frappe_assistant_core.utils.oauth_compat import get_oauth_settings

    settings = get_oauth_settings()

    # Check if authorization server metadata is enabled
    if not settings.get("show_auth_server_metadata", True):
        from werkzeug.exceptions import NotFound

        raise NotFound("Authorization server metadata is not enabled")

    # Get base metadata from Frappe (V16 built-in or V15 fallback)
    metadata = _get_frappe_authorization_server_metadata()

    # Add/override custom service documentation
    frappe_url = get_server_url()
    metadata["service_documentation"] = "https://github.com/buildswithpaul/Frappe_Assistant_Core"

    # Add client_secret_post as an additional auth method (Frappe V16 only has client_secret_basic)
    if "client_secret_post" not in metadata.get("token_endpoint_auth_methods_supported", []):
        metadata["token_endpoint_auth_methods_supported"].append("client_secret_post")

    if "client_secret_post" not in metadata.get("revocation_endpoint_auth_methods_supported", []):
        metadata["revocation_endpoint_auth_methods_supported"].append("client_secret_post")

    # Add registration endpoint if dynamic client registration is enabled
    if settings.get("enable_dynamic_client_registration"):
        metadata["registration_endpoint"] = (
            f"{frappe_url}/api/method/frappe_assistant_core.api.oauth_registration.register_client"
        )

    scopes_supported_value = settings.get("scopes_supported")
    if scopes_supported_value and isinstance(scopes_supported_value, str):
        # Clean and parse scopes - handle both single scopes and newline-separated lists
        scopes = []
        for line in scopes_supported_value.split("\n"):
            line = line.strip()
            if line:
                # Further split by whitespace to handle space-separated scopes
                for scope in line.split():
                    scope = scope.strip()
                    if scope and scope not in scopes:  # Avoid duplicates
                        scopes.append(scope)

        if scopes:
            metadata["scopes_supported"] = scopes

    return metadata


@frappe.whitelist(allow_guest=True, methods=["GET"])
def protected_resource_metadata():
    """
    OAuth 2.0 Protected Resource Metadata endpoint.

    Implements RFC 9728 - OAuth 2.0 Protected Resource Metadata
    https://datatracker.ietf.org/doc/html/rfc9728

    Returns metadata about the protected resource server.
    """
    from frappe_assistant_core.utils.oauth_compat import get_oauth_settings

    # Bypass cache for discovery endpoints to ensure fresh data
    # This is important because OAuth clients may cache this response
    # and we want them to see updates immediately
    settings = get_oauth_settings(use_cache=False)

    # Check if protected resource metadata is enabled
    if not settings.get("show_protected_resource_metadata", True):
        from werkzeug.exceptions import NotFound

        raise NotFound("Protected resource metadata is not enabled")

    frappe_url = get_server_url()

    # Build list of authorization servers
    authorization_servers = [frappe_url]

    # Include social login keys if configured
    if settings.get("show_social_login_key_as_authorization_server"):
        try:
            social_logins = frappe.get_list(
                "Social Login Key",
                filters={"enable_social_login": True},
                fields=["base_url"],
                ignore_permissions=True,
            )
            authorization_servers.extend([s.base_url for s in social_logins if s.base_url])
        except Exception:
            pass

    metadata = {
        "resource": frappe_url.rstrip("/"),
        "authorization_servers": authorization_servers,
        "bearer_methods_supported": ["header"],
        "resource_name": settings.get("resource_name") or "Frappe Assistant Core",
        "resource_documentation": settings.get("resource_documentation"),
        "resource_policy_uri": settings.get("resource_policy_uri"),
        "resource_tos_uri": settings.get("resource_tos_uri"),
    }

    # Add supported scopes if configured
    scopes_supported_value = settings.get("scopes_supported")
    if scopes_supported_value and isinstance(scopes_supported_value, str):
        # Clean and parse scopes - handle both single scopes and newline-separated lists
        scopes = []
        # Split by newlines and also by spaces (to handle "openid profile" format)
        for line in scopes_supported_value.split("\n"):
            line = line.strip()
            if line:
                # Further split by whitespace to handle space-separated scopes
                for scope in line.split():
                    scope = scope.strip()
                    if scope and scope not in scopes:  # Avoid duplicates
                        scopes.append(scope)

        if scopes:
            metadata["scopes_supported"] = scopes
            frappe.logger().debug(f"Protected Resource Metadata: Added scopes_supported = {scopes}")

    # Remove None values
    _del_none_values(metadata)

    return metadata


def _del_none_values(d: dict):
    """Remove keys with None values from dictionary."""
    for k in list(d.keys()):
        if k in d and d[k] is None:
            del d[k]
