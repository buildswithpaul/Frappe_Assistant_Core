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


@frappe.whitelist(allow_guest=True, methods=["GET"])
def openid_configuration():
    """
    Enhanced OpenID Connect Discovery endpoint.

    Extends Frappe's built-in endpoint with MCP-required fields.
    """
    from frappe.integrations.oauth2 import openid_configuration as frappe_openid_config

    # Call Frappe's built-in method (it sets frappe.local.response directly)
    frappe_openid_config()

    # Get the response that Frappe set
    metadata = frappe.local.response

    # Add MCP-required fields that are missing
    frappe_url = frappe.utils.get_url()

    # Add jwks_uri (required by MCP Inspector)
    metadata["jwks_uri"] = f"{frappe_url}/api/method/frappe_assistant_core.api.oauth_discovery.jwks"

    # Add PKCE support (required by MCP Inspector)
    metadata["code_challenge_methods_supported"] = ["S256"]

    # Add MCP-specific metadata (optional but useful)
    metadata["mcp_endpoint"] = f"{frappe_url}/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp"
    metadata["mcp_transport"] = "StreamableHTTP"
    metadata["mcp_protocol_version"] = "2025-03-26"


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

    frappe_url = frappe.utils.get_url()

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
