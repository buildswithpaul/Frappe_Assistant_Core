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
Tests for OAuth CORS handler — specifically the Authorization header bypass.

These tests verify that the monkey-patch of frappe.get_request_header is
properly scoped to individual requests and does not contaminate subsequent
requests on the same Gunicorn worker.

Regression tests for: https://github.com/buildswithpaul/Frappe_Assistant_Core/issues/129
"""

import base64
import unittest
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.api.oauth_cors import (
    _AUTH_PATCH_INSTALLED,
    _handle_oauth_token_endpoint_auth,
    _install_auth_header_patch,
)


class TestOAuthAuthHeaderBypass(unittest.TestCase):
    """Tests for the OAuth Basic auth header bypass mechanism."""

    def setUp(self):
        """Reset module state before each test."""
        import frappe_assistant_core.api.oauth_cors as cors_module

        # Reset the patch-installed flag so each test starts clean
        cors_module._AUTH_PATCH_INSTALLED = False

        # Store the real get_request_header to restore after each test
        self._original_get_request_header = frappe.get_request_header

    def tearDown(self):
        """Restore frappe.get_request_header to its original function."""
        import frappe_assistant_core.api.oauth_cors as cors_module

        frappe.get_request_header = self._original_get_request_header
        cors_module._AUTH_PATCH_INSTALLED = False

        # Clean up the per-request flag if set
        if hasattr(frappe.local, "_bypass_oauth_basic_auth"):
            del frappe.local._bypass_oauth_basic_auth

    def _make_basic_auth_header(self, client_id: str = "test_client", client_secret: str = "test_secret"):
        """Create a Basic auth header from client credentials."""
        credentials = f"{client_id}:{client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    def _mock_request(self, path: str, auth_header: str = ""):
        """Set up a mock frappe.request for the given path and auth header."""
        mock_request = MagicMock()
        mock_request.path = path
        mock_request.method = "POST"
        mock_request.headers = {"Authorization": auth_header} if auth_header else {}
        frappe.local.request = mock_request

    def test_oauth_endpoint_hides_basic_auth_header(self):
        """OAuth token endpoint with Basic auth should hide the Authorization header."""
        basic_header = self._make_basic_auth_header()
        self._mock_request("/api/method/frappe.integrations.oauth2.get_token", basic_header)

        _handle_oauth_token_endpoint_auth("/api/method/frappe.integrations.oauth2.get_token")

        # The patched function should hide the Authorization header
        result = frappe.get_request_header("Authorization", "")
        self.assertEqual(result, "", "Authorization header should be hidden for OAuth token endpoint")

        # The flag should be set
        self.assertTrue(getattr(frappe.local, "_bypass_oauth_basic_auth", False))

    def test_non_oauth_endpoint_preserves_auth_header(self):
        """Non-OAuth endpoints should pass the Authorization header through unchanged."""
        api_key_header = "token api_key:api_secret"
        self._mock_request("/api/method/frappe.client.get_list", api_key_header)

        _handle_oauth_token_endpoint_auth("/api/method/frappe.client.get_list")

        # The flag should NOT be set
        self.assertFalse(getattr(frappe.local, "_bypass_oauth_basic_auth", False))

        # Even after the patch is installed, non-OAuth requests should get the real header
        result = frappe.get_request_header("Authorization", "")
        self.assertEqual(
            result, api_key_header, "Authorization header should pass through for non-OAuth endpoints"
        )

    def test_no_cross_request_contamination(self):
        """
        THE KEY REGRESSION TEST.

        Simulates the exact bug from issue #129:
        1. Request A: OAuth token endpoint with Basic auth → header hidden
        2. Request B: Normal API endpoint with API key auth → header must be visible

        In production, frappe.local is reset between requests by Frappe's init().
        We simulate this by deleting the per-request flag.
        """
        # --- Request A: OAuth token endpoint ---
        basic_header = self._make_basic_auth_header()
        self._mock_request("/api/method/frappe.integrations.oauth2.get_token", basic_header)

        _handle_oauth_token_endpoint_auth("/api/method/frappe.integrations.oauth2.get_token")

        # Verify header is hidden during Request A
        result_a = frappe.get_request_header("Authorization", "")
        self.assertEqual(result_a, "", "Request A: Authorization header should be hidden")

        # --- Simulate new request (frappe.local reset) ---
        # In production, frappe.init() resets frappe.local between requests.
        # We simulate this by removing the per-request flag.
        if hasattr(frappe.local, "_bypass_oauth_basic_auth"):
            del frappe.local._bypass_oauth_basic_auth

        # --- Request B: Normal API endpoint with API key auth ---
        api_key_header = "token api_key:api_secret"
        self._mock_request("/api/method/frappe.client.get_list", api_key_header)

        _handle_oauth_token_endpoint_auth("/api/method/frappe.client.get_list")

        # Verify header is NOT hidden during Request B
        result_b = frappe.get_request_header("Authorization", "")
        self.assertEqual(
            result_b,
            api_key_header,
            "Request B: Authorization header must be visible after OAuth request on same worker",
        )

    def test_non_basic_auth_not_intercepted(self):
        """OAuth endpoint with Bearer token (not Basic) should NOT trigger the bypass."""
        bearer_header = "Bearer some_access_token"
        self._mock_request("/api/method/frappe.integrations.oauth2.get_token", bearer_header)

        _handle_oauth_token_endpoint_auth("/api/method/frappe.integrations.oauth2.get_token")

        # The flag should NOT be set — Bearer auth is not client credentials
        self.assertFalse(getattr(frappe.local, "_bypass_oauth_basic_auth", False))

    def test_revoke_endpoint_also_bypassed(self):
        """The revoke_token endpoint should also bypass auth validation."""
        basic_header = self._make_basic_auth_header()
        self._mock_request("/api/method/frappe.integrations.oauth2.revoke_token", basic_header)

        _handle_oauth_token_endpoint_auth("/api/method/frappe.integrations.oauth2.revoke_token")

        result = frappe.get_request_header("Authorization", "")
        self.assertEqual(result, "", "Authorization header should be hidden for revoke endpoint")

    def test_introspect_endpoint_also_bypassed(self):
        """The introspect_token endpoint should also bypass auth validation."""
        basic_header = self._make_basic_auth_header()
        self._mock_request("/api/method/frappe.integrations.oauth2.introspect_token", basic_header)

        _handle_oauth_token_endpoint_auth("/api/method/frappe.integrations.oauth2.introspect_token")

        result = frappe.get_request_header("Authorization", "")
        self.assertEqual(result, "", "Authorization header should be hidden for introspect endpoint")

    def test_patch_installed_only_once(self):
        """The wrapper should be installed only once, not re-installed on every request."""
        import frappe_assistant_core.api.oauth_cors as cors_module

        basic_header = self._make_basic_auth_header()

        # First request — patch gets installed
        self._mock_request("/api/method/frappe.integrations.oauth2.get_token", basic_header)
        _handle_oauth_token_endpoint_auth("/api/method/frappe.integrations.oauth2.get_token")
        self.assertTrue(cors_module._AUTH_PATCH_INSTALLED)

        # Capture the function reference after first install
        patched_fn = frappe.get_request_header

        # Simulate new request
        if hasattr(frappe.local, "_bypass_oauth_basic_auth"):
            del frappe.local._bypass_oauth_basic_auth

        # Second request — patch should NOT be re-installed
        self._mock_request("/api/method/frappe.integrations.oauth2.get_token", basic_header)
        _handle_oauth_token_endpoint_auth("/api/method/frappe.integrations.oauth2.get_token")

        # Same function reference — not wrapped again
        self.assertIs(
            frappe.get_request_header,
            patched_fn,
            "Patch should be installed once, not re-wrapped on every request",
        )

    def test_other_headers_unaffected(self):
        """Non-Authorization headers should always pass through regardless of bypass state."""
        basic_header = self._make_basic_auth_header()
        self._mock_request("/api/method/frappe.integrations.oauth2.get_token", basic_header)
        frappe.local.request.headers["Content-Type"] = "application/x-www-form-urlencoded"

        _handle_oauth_token_endpoint_auth("/api/method/frappe.integrations.oauth2.get_token")

        # Other headers should be unaffected
        result = frappe.get_request_header("Content-Type", "")
        self.assertEqual(result, "application/x-www-form-urlencoded")
