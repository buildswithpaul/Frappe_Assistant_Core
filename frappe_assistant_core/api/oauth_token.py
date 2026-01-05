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
Custom OAuth Token Endpoint

Overrides Frappe's get_token endpoint to properly handle Basic auth
for client authentication during token exchange.

Frappe's default implementation doesn't properly parse Authorization: Basic
headers for confidential client authentication. This override adds that support.
"""

import base64
import json

import frappe
from frappe.integrations.oauth2 import get_oauth_server
from frappe.oauth import generate_json_error_response
from oauthlib.oauth2 import FatalClientError, OAuth2Error


@frappe.whitelist(allow_guest=True)
def get_token(*args, **kwargs):
    """
    OAuth 2.0 Token Endpoint with proper Basic auth support.

    This endpoint handles token requests for:
    - Authorization Code exchange
    - Refresh Token grants
    - Client Credentials grants

    Supports client authentication via:
    - Authorization: Basic base64(client_id:client_secret)
    - client_id/client_secret in POST body
    """
    try:
        r = frappe.request

        # Check for Basic auth and inject client_id into form if needed
        form_data = _prepare_form_with_client_auth(r)

        headers, body, status = get_oauth_server().create_token_response(
            r.url, r.method, form_data, r.headers, frappe.flags.oauth_credentials
        )
        body = frappe._dict(json.loads(body))

        if body.error:
            frappe.local.response = body
            frappe.local.response["http_status_code"] = 400
            return

        frappe.local.response = body
        return

    except (FatalClientError, OAuth2Error) as e:
        return generate_json_error_response(e)


def _prepare_form_with_client_auth(request):
    """
    Prepare form data with client credentials from Basic auth header.

    If Authorization: Basic header is present and client_id is not in form,
    extract and add client credentials to the form data.

    This allows oauthlib to find client_id in the request body and properly
    authenticate the client.
    """
    # Start with the original form data
    form_data = request.form.to_dict() if hasattr(request.form, "to_dict") else dict(request.form)

    # Check if client_id is already in the form
    if form_data.get("client_id"):
        return form_data

    # Check for Basic auth header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Basic "):
        return form_data

    try:
        # Decode Basic auth: base64(client_id:client_secret)
        encoded = auth_header[6:]  # Remove "Basic " prefix
        decoded = base64.b64decode(encoded).decode("utf-8")

        if ":" in decoded:
            client_id, client_secret = decoded.split(":", 1)

            # Add to form data so oauthlib can find them
            form_data["client_id"] = client_id
            form_data["client_secret"] = client_secret

            frappe.logger().debug("OAuth token: extracted client_id from Basic auth header")

    except Exception as e:
        frappe.logger().error(f"OAuth token: failed to parse Basic auth header: {e}")

    return form_data
