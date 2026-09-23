# Frappe Assistant Core - FAC Cloud Client
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
FAC Cloud Client Module

This module provides a thin wrapper around the assistant_runtime_sdk
to integrate with Frappe's settings system. It provides:

- get_fac_cloud_client(): Factory function to get a configured client from FAC Chat Settings
- Re-exports of SDK classes and functions for convenience

The SDK handles:
- HMAC-SHA256 authentication
- SSE streaming
- All API endpoints (streaming, billing, users, conversations, etc.)
"""

from typing import Any, Optional

import frappe

# Import SDK classes and functions
from assistant_runtime_sdk import (
    ARAPIError,
    ARAuthenticationError,
    ARBillingUnavailableError,
    ARConfigurationError,
    ARConnectionError,
    # Exceptions - using AR naming going forward
    ARError,
    ARRateLimitError,
    ARStreamError,
    ARTimeoutError,
    # Client classes
    AssistantRuntimeClient,
)
from assistant_runtime_sdk import (
    # Standalone functions
    get_terms as sdk_get_terms,
)
from assistant_runtime_sdk import (
    register_tenant as sdk_register_tenant,
)

from frappe_assistant_core.chat.cloud_url import get_fac_cloud_url

# Re-export exceptions for convenience
__all__ = [
    "ARAPIError",
    "ARAuthenticationError",
    "ARBillingUnavailableError",
    "ARConfigurationError",
    "ARConnectionError",
    # Exceptions
    "ARError",
    "ARRateLimitError",
    "ARStreamError",
    "ARTimeoutError",
    # Client class
    "AssistantRuntimeClient",
    # Factory function
    "get_fac_cloud_client",
    "get_capabilities",
    # Standalone functions
    "get_terms",
    "register_tenant",
    "get_registration_state",
]


def get_fac_cloud_client() -> AssistantRuntimeClient | None:
    """
    Factory function to get a configured FAC Cloud client from FAC Chat Settings.

    Returns:
        Configured AssistantRuntimeClient or None if not registered

    Example:
        >>> client = get_fac_cloud_client()
        >>> if client:
        ...     models = client.list_available_models()
    """
    settings = frappe.get_single("FAC Chat Settings")

    if settings.registration_status != "Registered":
        return None

    if not settings.tenant_id or not settings.tenant_secret:
        return None

    fac_cloud_url = get_fac_cloud_url()

    try:
        from frappe_assistant_core.chat.tenant_credentials import read_tenant_secret

        tenant_secret = read_tenant_secret(raise_exception=True)
    except frappe.ValidationError:
        # Stale / unreadable encrypted secret. Reset registration so the admin
        # can re-register cleanly — never db_set a Password field.
        from frappe_assistant_core.chat.tenant_credentials import clear_tenant_secret

        frappe.logger().warning("FACO: tenant_secret decryption failed — clearing stale registration")
        clear_tenant_secret()
        settings.flags.clear_tenant_secret = True
        settings.db_set("registration_status", "Not Registered")
        settings.db_set("tenant_id", "")
        settings.tenant_secret = None
        frappe.db.commit()
        return None

    return AssistantRuntimeClient(
        tenant_id=settings.tenant_id,
        tenant_secret=tenant_secret,
        ar_url=fac_cloud_url,
        # Origin binding (Phase 2): the SDK injects this into every signed
        # payload. AR's validate_tenant_signature rejects requests without it.
        site_url=frappe.utils.get_url(),
    )


def get_terms(fac_cloud_url: str | None = None) -> dict[str, Any] | None:
    """
    Fetch current Terms and Conditions from FAC Cloud.

    No authentication required - allows display before registration.

    Args:
        fac_cloud_url: FAC Cloud server URL. If None, resolves from site_config.

    Returns:
        Terms content dict or None on failure
    """
    fac_cloud_url = fac_cloud_url or get_fac_cloud_url()

    return sdk_get_terms(fac_cloud_url)


def register_tenant(
    site_url: str,
    owner_email: str | None = None,
    fac_mcp_endpoint: str | None = None,
    terms_accepted: bool = True,
    terms_version: str | None = None,
    accepted_by: str | None = None,
    fac_cloud_url: str | None = None,
    referral_code: str | None = None,
    application_id: str = "faco",
    promotion_token: str | None = None,
) -> dict[str, Any]:
    """
    Register this FAC installation as a tenant with FAC Cloud.

    Args:
        site_url: This site's URL (e.g., https://mysite.frappe.cloud)
        fac_mcp_endpoint: Optional FAC MCP server endpoint URL
        terms_accepted: Must be True to register
        terms_version: Version of terms being accepted
        accepted_by: User email/username who accepted the terms
        fac_cloud_url: FAC Cloud server URL. If None, resolves from site_config.
        application_id: AR Application this tenant registers under. Always "faco"
            for FAC — the application never changes.

    Returns:
        Registration result with tenant_id and tenant_secret, or error
    """
    fac_cloud_url = fac_cloud_url or get_fac_cloud_url()

    return sdk_register_tenant(
        ar_url=fac_cloud_url,
        site_url=site_url,
        owner_email=owner_email,
        application_id=application_id,
        fac_mcp_endpoint=fac_mcp_endpoint,
        terms_accepted=terms_accepted,
        terms_version=terms_version,
        accepted_by=accepted_by,
        referral_code=referral_code,
        promotion_token=promotion_token,
    )


def get_registration_state(
    site_url: str,
    tenant_id: str | None = None,
    fac_cloud_url: str | None = None,
) -> dict[str, Any]:
    """Ask AR whether a tenant already exists for this site (guest lookup)."""
    from assistant_runtime_sdk.client import get_registration_state as sdk_state

    fac_cloud_url = fac_cloud_url or get_fac_cloud_url()
    return sdk_state(ar_url=fac_cloud_url, site_url=site_url, tenant_id=tenant_id)


def get_capabilities(fac_cloud_url: str | None = None) -> dict[str, Any] | None:
    """
    Fetch capabilities from FAC Cloud backend.

    No authentication required - public endpoint.

    Args:
        fac_cloud_url: Base URL of FAC Cloud server. If None, resolves from site_config.

    Returns:
        Capabilities dict with features, version, billing info, or None on failure
    """
    import requests

    fac_cloud_url = fac_cloud_url or get_fac_cloud_url()

    url = f"{fac_cloud_url.rstrip('/')}/api/method/assistant_runtime.api.get_capabilities"

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("message", data)
        return None
    except Exception:
        return None
