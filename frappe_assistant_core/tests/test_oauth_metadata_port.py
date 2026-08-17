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
Regression tests for: https://github.com/buildswithpaul/Frappe_Assistant_Core/issues/196

OAuth metadata URLs must honor a configured host_name verbatim, including a
non-standard port. Frappe's frappe.oauth.get_server_url() reconstructs the
host/port from the request or the Social Login Key base_url and drops the
configured port, which broke the OAuth handshake for deployments behind a
port-restricted network (public URL on e.g. :8000).

The MCP endpoint's 401 WWW-Authenticate header advertises the
resource_metadata URL; it previously used get_server_url() and dropped the
port. It now builds from get_public_base_url() (the same host_name-aware base
the discovery endpoints use), so the port is preserved.
"""

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import frappe
from werkzeug.wrappers import Response

from frappe_assistant_core.tests.base_test import BaseAssistantTest

_HOST_WITH_PORT = "https://mysite.example.net:8000"


def _patch_conf(stack: ExitStack, conf: dict):
    """Patch frappe.conf.get to read from a test dict."""
    stack.enter_context(patch.object(frappe, "conf", conf))


class TestPublicBaseUrlHonorsPort(BaseAssistantTest):
    """get_public_base_url must return a host_name with a non-standard port
    verbatim, without routing through Frappe's port-dropping get_server_url."""

    def test_host_name_with_port_used_verbatim(self):
        from frappe_assistant_core.api import oauth_discovery

        with ExitStack() as stack:
            _patch_conf(stack, {"host_name": _HOST_WITH_PORT})
            # If host_name is honored, get_server_url must not even be consulted.
            get_server_url = stack.enter_context(
                patch(
                    "frappe_assistant_core.api.oauth_discovery.get_server_url",
                    side_effect=AssertionError("host_name with scheme must be used verbatim"),
                )
            )

            base = oauth_discovery.get_public_base_url()

        self.assertEqual(base, _HOST_WITH_PORT)
        self.assertIn(":8000", base)
        get_server_url.assert_not_called()

    def test_host_name_without_scheme_falls_back_to_server_url(self):
        """Without a scheme in host_name, behavior is unchanged (uses
        get_server_url) — this fix does not alter the fallback path."""
        from frappe_assistant_core.api import oauth_discovery

        with ExitStack() as stack:
            _patch_conf(stack, {"host_name": "mysite.example.net:8000"})  # no scheme
            stack.enter_context(
                patch(
                    "frappe_assistant_core.api.oauth_discovery.get_server_url",
                    return_value="https://internal.local",
                )
            )

            base = oauth_discovery.get_public_base_url()

        self.assertEqual(base, "https://internal.local")


class TestWwwAuthenticatePreservesPort(BaseAssistantTest):
    """The MCP 401 WWW-Authenticate resource_metadata URL must keep the port."""

    def _make_request(self, auth_header: str = ""):
        request = MagicMock()
        request.method = "POST"
        request.headers = {"Authorization": auth_header} if auth_header else {}
        # A realistic *internal* request URL with no public port — this is what
        # Frappe's get_server_url() would fall back to, so the pre-fix code
        # produces a port-less metadata URL and these tests fail cleanly on it.
        request.url = "https://internal.local/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp"
        return request

    def test_unauthenticated_resource_metadata_keeps_port(self):
        from frappe_assistant_core.api import fac_endpoint

        with ExitStack() as stack:
            _patch_conf(stack, {"host_name": _HOST_WITH_PORT})
            # Guard: the endpoint must not fall back to Frappe's get_server_url.
            stack.enter_context(
                patch(
                    "frappe_assistant_core.api.oauth_discovery.get_server_url",
                    side_effect=AssertionError("must build metadata URL from host_name, not get_server_url"),
                )
            )
            frappe.local.request = self._make_request(auth_header="")

            # No valid auth → returns a 401 Response with WWW-Authenticate.
            result = fac_endpoint._authenticate_mcp_request()

        self.assertIsInstance(result, Response)
        self.assertEqual(result.status_code, 401)
        www_auth = result.headers.get("WWW-Authenticate", "")
        self.assertIn("resource_metadata=", www_auth)
        self.assertIn(
            f'resource_metadata="{_HOST_WITH_PORT}/.well-known/oauth-protected-resource"',
            www_auth,
        )
        self.assertIn(":8000", www_auth)

    def test_invalid_bearer_token_resource_metadata_keeps_port(self):
        """The Bearer-token-not-found 401 path must also keep the port."""
        from frappe_assistant_core.api import fac_endpoint

        with ExitStack() as stack:
            _patch_conf(stack, {"host_name": _HOST_WITH_PORT})
            stack.enter_context(
                patch(
                    "frappe_assistant_core.api.oauth_discovery.get_server_url",
                    side_effect=AssertionError("must build metadata URL from host_name, not get_server_url"),
                )
            )
            # A bearer token that does not exist → DoesNotExistError → 401.
            stack.enter_context(
                patch.object(
                    fac_endpoint.frappe,
                    "get_doc",
                    side_effect=frappe.DoesNotExistError,
                )
            )
            frappe.local.request = self._make_request(auth_header="Bearer nonexistent-token")

            result = fac_endpoint._authenticate_mcp_request()

        self.assertIsInstance(result, Response)
        self.assertEqual(result.status_code, 401)
        www_auth = result.headers.get("WWW-Authenticate", "")
        self.assertIn(
            f'resource_metadata="{_HOST_WITH_PORT}/.well-known/oauth-protected-resource"',
            www_auth,
        )
