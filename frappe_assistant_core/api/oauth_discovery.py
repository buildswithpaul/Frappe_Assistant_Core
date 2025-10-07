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
    from frappe.integrations.oauth2 import openid_configuration as frappe_openid_config

    from frappe_assistant_core.utils.oauth_compat import get_oauth_settings

    # Call Frappe's built-in method (it sets frappe.local.response directly)
    metadata = frappe_openid_config()

    # Get the response that Frappe set
    # metadata = frappe.local.response

    # Add MCP-required fields that are missing
    frappe_url = get_server_url()

    # Add jwks_uri (required by MCP Inspector)
    metadata["jwks_uri"] = f"{frappe_url}/api/method/frappe_assistant_core.api.oauth_discovery.jwks"

    # Add PKCE support (required by MCP Inspector)
    metadata["code_challenge_methods_supported"] = ["S256"]

    # Add MCP-specific metadata (optional but useful)
    metadata["mcp_endpoint"] = f"{frappe_url}/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp"
    metadata["mcp_transport"] = "StreamableHTTP"
    metadata["mcp_protocol_version"] = "2025-03-26"

    # Add registration endpoint if dynamic client registration is enabled
    settings = get_oauth_settings()
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

    return {
        "mcp_endpoint": f"{frappe_url}/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp",
        "mcp_transport": "StreamableHTTP",
        "mcp_protocol_version": "2025-03-26",
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

    frappe_url = get_server_url()

    metadata = {
        "issuer": frappe_url,
        "authorization_endpoint": f"{frappe_url}/api/method/frappe.integrations.oauth2.authorize",
        "token_endpoint": f"{frappe_url}/api/method/frappe.integrations.oauth2.get_token",
        "response_types_supported": ["code"],
        "response_modes_supported": ["query"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": ["none", "client_secret_basic", "client_secret_post"],
        "service_documentation": "https://github.com/buildswithpaul/Frappe_Assistant_Core",
        "revocation_endpoint": f"{frappe_url}/api/method/frappe.integrations.oauth2.revoke_token",
        "revocation_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post"],
        "introspection_endpoint": f"{frappe_url}/api/method/frappe.integrations.oauth2.introspect_token",
        "userinfo_endpoint": f"{frappe_url}/api/method/frappe.integrations.oauth2.openid_profile",
        "code_challenge_methods_supported": ["S256"],
    }

    # Add registration endpoint if dynamic client registration is enabled
    if settings.get("enable_dynamic_client_registration"):
        metadata["registration_endpoint"] = (
            f"{frappe_url}/api/method/frappe_assistant_core.api.oauth_registration.register_client"
        )

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

    settings = get_oauth_settings()

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
        "resource": frappe_url,
        "authorization_servers": authorization_servers,
        "bearer_methods_supported": ["header"],
        "resource_name": settings.get("resource_name") or "Frappe Assistant Core",
        "resource_documentation": settings.get("resource_documentation"),
        "resource_policy_uri": settings.get("resource_policy_uri"),
        "resource_tos_uri": settings.get("resource_tos_uri"),
    }

    # Add supported scopes if configured
    if settings.get("scopes_supported"):
        scopes = []
        for line in settings.get("scopes_supported").split("\n"):
            scope = line.strip()
            if scope:
                scopes.append(scope)
        if scopes:
            metadata["scopes_supported"] = scopes

    # Remove None values
    _del_none_values(metadata)

    return metadata


def _del_none_values(d: dict):
    """Remove keys with None values from dictionary."""
    for k in list(d.keys()):
        if k in d and d[k] is None:
            del d[k]
