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
OAuth 2.0 Dynamic Client Registration

Implements RFC 7591 - OAuth 2.0 Dynamic Client Registration Protocol
https://datatracker.ietf.org/doc/html/rfc7591
"""

import frappe
from pydantic import BaseModel, HttpUrl, ValidationError
from werkzeug import Response
from werkzeug.exceptions import NotFound

from frappe_assistant_core.utils.oauth_compat import (
    create_oauth_client,
    get_oauth_settings,
    validate_dynamic_client_metadata,
)


class OAuth2DynamicClientMetadata(BaseModel):
    """
    OAuth 2.0 Dynamic Client Registration Metadata.

    As defined in RFC7591 - OAuth 2.0 Dynamic Client Registration Protocol
    https://datatracker.ietf.org/doc/html/rfc7591#section-2
    """

    # Used to identify the client to the authorization server
    redirect_uris: list[HttpUrl]
    token_endpoint_auth_method: str | None = "client_secret_basic"
    grant_types: list[str] | None = ["authorization_code"]
    response_types: list[str] | None = ["code"]

    # Client identifiers shown to user
    client_name: str
    scope: str | None = None
    client_uri: HttpUrl | None = None
    logo_uri: HttpUrl | None = None

    # Client contact and other information for the client
    contacts: list[str] | None = None
    tos_uri: HttpUrl | None = None
    policy_uri: HttpUrl | None = None
    software_id: str | None = None
    software_version: str | None = None

    # JSON Web Key Set (JWKS) not used here
    jwks_uri: HttpUrl | None = None
    jwks: dict | None = None


@frappe.whitelist(allow_guest=True, methods=["POST"])
def register_client():
    """
    Register an OAuth 2.0 client dynamically.

    Endpoint: /api/method/frappe_assistant_core.api.oauth_registration.register_client

    Reference: https://datatracker.ietf.org/doc/html/rfc7591

    This endpoint allows OAuth clients to register themselves without manual
    intervention. The client sends metadata in the request body, and receives
    client credentials (client_id and optionally client_secret) in the response.

    Request Body (JSON):
        {
            "redirect_uris": ["https://example.com/callback"],
            "client_name": "My Application",
            "client_uri": "https://example.com",
            "logo_uri": "https://example.com/logo.png",
            "scope": "all openid",
            "contacts": ["admin@example.com"],
            "tos_uri": "https://example.com/tos",
            "policy_uri": "https://example.com/privacy",
            "software_id": "my-app",
            "software_version": "1.0.0",
            "token_endpoint_auth_method": "client_secret_basic" | "client_secret_post" | "none"
        }

    Response (201 Created):
        {
            "client_id": "abc123...",
            "client_secret": "secret123...",  # Omitted for public clients
            "client_id_issued_at": 1234567890,
            "client_secret_expires_at": 0,
            "client_name": "My Application",
            "redirect_uris": ["https://example.com/callback"],
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
            "scope": "all openid",
            ...
        }

    Error Response (400 Bad Request):
        {
            "error": "invalid_client_metadata",
            "error_description": "Detailed error message"
        }
    """
    # Check if dynamic client registration is enabled
    settings = get_oauth_settings()
    if not settings.get("enable_dynamic_client_registration"):
        raise NotFound("Dynamic client registration is not enabled")

    response = Response()
    response.mimetype = "application/json"

    # Get request data
    data = frappe.request.json

    if data is None:
        response.status_code = 400
        response.data = frappe.as_json(
            {"error": "invalid_client_metadata", "error_description": "Request body is empty"}
        )
        return response

    # Validate client metadata using Pydantic
    try:
        client = OAuth2DynamicClientMetadata.model_validate(data)
    except ValidationError as e:
        response.status_code = 400
        response.data = frappe.as_json({"error": "invalid_client_metadata", "error_description": str(e)})
        return response

    # Additional business logic validation
    if error := validate_dynamic_client_metadata(client):
        response.status_code = 400
        response.data = frappe.as_json({"error": "invalid_client_metadata", "error_description": error})
        return response

    # Create the OAuth Client
    try:
        oauth_client = create_oauth_client(client)
    except Exception as e:
        frappe.log_error("OAuth Client Registration Failed", str(e))
        response.status_code = 500
        response.data = frappe.as_json(
            {
                "error": "server_error",
                "error_description": "Failed to create OAuth client. Please try again.",
            }
        )
        return response

    # Convert to dict and add required RFC 7591 fields
    import time

    response_data = oauth_client.as_dict() if hasattr(oauth_client, "as_dict") else dict(oauth_client)
    
    # Ensure redirect_uris is an array (it might be stored as a newline-separated string)
    if "redirect_uris" in response_data and isinstance(response_data["redirect_uris"], str):
        response_data["redirect_uris"] = [uri.strip() for uri in response_data["redirect_uris"].split("\n") if uri.strip()]
    
    response_data["client_id_issued_at"] = int(time.time())
    response_data["client_secret_expires_at"] = 0  # Client secrets don't expire

    # Remove None values
    _del_none_values(response_data)

    response.status_code = 201  # Created
    response.data = frappe.as_json(response_data)
    return response


def _del_none_values(d: dict):
    """Remove keys with None values from dictionary."""
    for k in list(d.keys()):
        if k in d and d[k] is None:
            del d[k]
