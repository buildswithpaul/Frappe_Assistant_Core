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
OAuth Compatibility Layer for Frappe v15 and v16+

This module provides version-agnostic OAuth configuration access by detecting
the Frappe version and routing to the appropriate settings source:
- Frappe v15: Uses Assistant Core Settings (our implementation)
- Frappe v16+: Uses native OAuth Settings from frappe.integrations
"""

import frappe
from frappe import _


def is_frappe_v16_or_later():
    """
    Detect if we're running on Frappe v16 or later.
    Returns:
            bool: True if Frappe v16+, False if v15
    """
    # Check if the native OAuth Settings DocType exists in Integrations module
    return (
        frappe.db.exists("DocType", "OAuth Settings", cache=True)
        and frappe.db.get_value("DocType", "OAuth Settings", "module") == "Integrations"
    )


def get_oauth_settings(use_cache=True):
    """
    Get OAuth settings in a version-agnostic way.

    For v15: Reads from Assistant Core Settings
    For v16+: Reads from native OAuth Settings (frappe.integrations)

    Args:
            use_cache (bool): If False, bypasses cache and fetches fresh data. Default True.

    Returns:
            frappe._dict: Dictionary containing OAuth configuration with keys:
                    - show_auth_server_metadata (bool)
                    - enable_dynamic_client_registration (bool)
                    - allowed_public_client_origins (str)
                    - show_protected_resource_metadata (bool)
                    - resource_name (str)
                    - resource_documentation (str)
                    - resource_policy_uri (str)
                    - resource_tos_uri (str)
                    - scopes_supported (str)
    """
    if is_frappe_v16_or_later():
        # Use native Frappe v16 OAuth Settings
        try:
            if use_cache:
                oauth_settings = frappe.get_cached_doc(
                    "OAuth Settings", "OAuth Settings", ignore_permissions=True
                )
            else:
                oauth_settings = frappe.get_doc("OAuth Settings", "OAuth Settings")

            return frappe._dict(
                {
                    "show_auth_server_metadata": oauth_settings.show_auth_server_metadata,
                    "enable_dynamic_client_registration": oauth_settings.enable_dynamic_client_registration,
                    "skip_authorization": getattr(
                        oauth_settings, "skip_authorization", False
                    ),  # v16 has this
                    "allowed_public_client_origins": oauth_settings.allowed_public_client_origins,
                    "show_protected_resource_metadata": oauth_settings.show_protected_resource_metadata,
                    "show_social_login_key_as_authorization_server": getattr(
                        oauth_settings, "show_social_login_key_as_authorization_server", False
                    ),  # v16 has this
                    "resource_name": oauth_settings.resource_name,
                    "resource_documentation": oauth_settings.resource_documentation,
                    "resource_policy_uri": oauth_settings.resource_policy_uri,
                    "resource_tos_uri": oauth_settings.resource_tos_uri,
                    "scopes_supported": oauth_settings.scopes_supported,
                }
            )
        except Exception:
            # Fallback to defaults if OAuth Settings doesn't exist yet
            return _get_default_oauth_settings()
    else:
        # Use Frappe v15 - read from Assistant Core Settings
        try:
            if use_cache:
                settings = frappe.get_cached_doc(
                    "Assistant Core Settings", "Assistant Core Settings", ignore_permissions=True
                )
            else:
                settings = frappe.get_doc("Assistant Core Settings", "Assistant Core Settings")

            return frappe._dict(
                {
                    "show_auth_server_metadata": settings.show_auth_server_metadata,
                    "enable_dynamic_client_registration": settings.enable_dynamic_client_registration,
                    "skip_authorization": False,  # Removed from v15, return False for compatibility
                    "allowed_public_client_origins": settings.allowed_public_client_origins,
                    "show_protected_resource_metadata": settings.show_protected_resource_metadata,
                    "show_social_login_key_as_authorization_server": False,  # Removed from v15, return False for compatibility
                    "resource_name": settings.resource_name,
                    "resource_documentation": settings.resource_documentation,
                    "resource_policy_uri": settings.resource_policy_uri,
                    "resource_tos_uri": settings.resource_tos_uri,
                    "scopes_supported": settings.scopes_supported,
                }
            )
        except Exception:
            # Fallback to defaults if settings don't exist yet
            return _get_default_oauth_settings()


def _get_default_oauth_settings():
    """Get default OAuth settings when no configuration exists."""
    return frappe._dict(
        {
            "show_auth_server_metadata": True,
            "enable_dynamic_client_registration": True,
            "skip_authorization": False,
            "allowed_public_client_origins": "",
            "show_protected_resource_metadata": True,
            "show_social_login_key_as_authorization_server": False,
            "resource_name": "Frappe Assistant Core",
            "resource_documentation": "https://github.com/buildswithpaul/Frappe_Assistant_Core",
            "resource_policy_uri": "",
            "resource_tos_uri": "",
            "scopes_supported": "",
        }
    )


def create_oauth_client(client_metadata):
    """
    Create an OAuth Client from dynamic registration metadata.

    For v15: Creates basic OAuth Client without custom fields
    For v16+: Uses native frappe.integrations.utils.create_new_oauth_client

    Args:
            client_metadata: OAuth2DynamicClientMetadata pydantic model

    Returns:
            dict: Client registration response with client_id and optionally client_secret
    """
    if is_frappe_v16_or_later():
        # Use native v16 implementation
        from frappe.integrations.utils import create_new_oauth_client

        doc = create_new_oauth_client(client_metadata)

        # Fix Frappe v16 bug: create_new_oauth_client uses newline delimiter for redirect_uris,
        # but oauth.py's validate_redirect_uri expects space delimiter
        redirect_uris = [str(uri) for uri in client_metadata.redirect_uris]
        doc.redirect_uris = " ".join(redirect_uris)
        doc.save(ignore_permissions=True)

        # v16 returns an OAuthClient document, convert to dict for RFC 7591 response
        redirect_uris = [str(uri) for uri in client_metadata.redirect_uris]
        response = {
            "client_id": doc.client_id,
            "client_secret": doc.get_password("client_secret"),
            "client_name": doc.app_name,
            "redirect_uris": redirect_uris,
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": client_metadata.token_endpoint_auth_method or "client_secret_basic",
        }

        # Add optional metadata fields if provided
        if client_metadata.client_uri:
            response["client_uri"] = str(client_metadata.client_uri)
        if client_metadata.logo_uri:
            response["logo_uri"] = str(client_metadata.logo_uri)
        if client_metadata.scope:
            response["scope"] = client_metadata.scope
        if client_metadata.contacts:
            response["contacts"] = client_metadata.contacts
        if client_metadata.tos_uri:
            response["tos_uri"] = str(client_metadata.tos_uri)
        if client_metadata.policy_uri:
            response["policy_uri"] = str(client_metadata.policy_uri)
        if client_metadata.software_id:
            response["software_id"] = client_metadata.software_id
        if client_metadata.software_version:
            response["software_version"] = client_metadata.software_version

        return response
    else:
        # Frappe v15 - create basic OAuth Client without custom fields
        from typing import cast

        from frappe.integrations.doctype.oauth_client.oauth_client import OAuthClient

        doc = cast(OAuthClient, frappe.get_doc({"doctype": "OAuth Client"}))

        # Deduplicate redirect URIs
        seen = set()
        redirect_uris = []
        for uri in client_metadata.redirect_uris:
            uri_str = str(uri)
            if uri_str not in seen:
                seen.add(uri_str)
                redirect_uris.append(uri_str)

        # Set basic fields (v15 compatible)
        doc.app_name = client_metadata.client_name
        doc.scopes = client_metadata.scope or "all"
        doc.redirect_uris = "\n".join(redirect_uris)
        doc.default_redirect_uri = redirect_uris[0]
        doc.response_type = "Code"
        doc.grant_type = "Authorization Code"
        doc.skip_authorization = False

        # Insert and get credentials
        doc.insert(ignore_permissions=True)

        # Build response - always include client_secret
        # Even if token_endpoint_auth_method is "none", the client should receive
        # the secret. They may choose not to use it for authentication, but should have it.
        response = {
            "client_id": doc.client_id,
            "client_secret": doc.get_password("client_secret"),
            "client_name": doc.app_name,
            "redirect_uris": redirect_uris,
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": client_metadata.token_endpoint_auth_method or "client_secret_basic",
        }

        # Add optional metadata fields if provided
        if client_metadata.client_uri:
            response["client_uri"] = str(client_metadata.client_uri)
        if client_metadata.logo_uri:
            response["logo_uri"] = str(client_metadata.logo_uri)
        if client_metadata.scope:
            response["scope"] = client_metadata.scope
        if client_metadata.contacts:
            response["contacts"] = client_metadata.contacts
        if client_metadata.tos_uri:
            response["tos_uri"] = str(client_metadata.tos_uri)
        if client_metadata.policy_uri:
            response["policy_uri"] = str(client_metadata.policy_uri)
        if client_metadata.software_id:
            response["software_id"] = client_metadata.software_id
        if client_metadata.software_version:
            response["software_version"] = client_metadata.software_version

        return response


def validate_dynamic_client_metadata(client_metadata):
    """
    Validate OAuth 2.0 Dynamic Client Registration metadata.

    For v15: Uses our custom validation logic
    For v16+: Uses native frappe.integrations.utils.validate_dynamic_client_metadata

    Args:
            client_metadata: OAuth2DynamicClientMetadata pydantic model

    Returns:
            str or None: Error message if invalid, None if valid
    """
    if is_frappe_v16_or_later():
        # Use native v16 validation
        from frappe.integrations.utils import validate_dynamic_client_metadata as v16_validate

        return v16_validate(client_metadata)
    else:
        # Frappe v15 - custom validation
        from urllib.parse import urlparse

        invalidation_reasons = []

        if len(client_metadata.redirect_uris) == 0:
            invalidation_reasons.append("redirect_uris is required")

        if client_metadata.grant_types and not set(client_metadata.grant_types).issubset(
            {"authorization_code", "refresh_token"}
        ):
            invalidation_reasons.append(
                "only 'authorization_code' and 'refresh_token' grant types are supported"
            )

        if client_metadata.response_types and not all(rt == "code" for rt in client_metadata.response_types):
            invalidation_reasons.append("only 'code' response_type is supported")

        # Validate HTTPS redirect URIs (allow localhost/127.0.0.1 with http for development)
        for uri in client_metadata.redirect_uris:
            uri_str = str(uri)  # Convert Pydantic HttpUrl to string
            parsed_uri = urlparse(uri_str)

            if parsed_uri.scheme != "https":
                # Allow http for localhost and 127.0.0.1 (common for development tools like MCP Inspector)
                is_localhost = parsed_uri.hostname in ("localhost", "127.0.0.1", "::1")
                if not is_localhost and not frappe.conf.developer_mode:
                    invalidation_reasons.append(
                        f"redirect_uri '{uri_str}' must use https (http is only allowed for localhost)"
                    )

        if invalidation_reasons:
            return ",\n".join(invalidation_reasons)

        return None
