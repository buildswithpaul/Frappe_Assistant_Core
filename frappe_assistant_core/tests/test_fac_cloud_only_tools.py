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
Tests for keeping FAC-Cloud-only tools away from other MCP clients.

The faco plugin's tools cannot work for anyone but FAC Cloud: the browser tools
run inside the FAC Chat page and talk to it over Socket.IO. Offered to Claude
Desktop they publish a realtime request nobody is listening for and then fail on
the 30 second timeout — which is what a user would report as "the tool hangs".

FAC Cloud is not reached by a private transport; `chat/api/auth.py` registers the
same `fac_endpoint.handle_mcp` URL every other client posts to. So the only thing
separating it from Claude Desktop is the OAuth client its bearer token belongs
to, and these tests use real `OAuth Client` and `OAuth Bearer Token` rows rather
than a mocked identity.

Note on plugin state: no test here enables or disables a plugin.
`PluginPersistence.save_plugin_state` calls `frappe.db.commit()`, so toggling a
plugin escapes the test rollback and would permanently change the site.
"""

from unittest.mock import patch

import frappe
from frappe.utils import set_request

from frappe_assistant_core.api.fac_endpoint import _build_tool_registry
from frappe_assistant_core.plugins.core.plugin import CorePlugin
from frappe_assistant_core.plugins.faco.plugin import FacoPlugin
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.mcp_caller import (
    FAC_CLOUD_OAUTH_CLIENT_ID,
    request_is_from_fac_cloud,
)
from frappe_assistant_core.utils.plugin_manager import get_plugin_manager

MCP_PATH = "/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp"


def _make_oauth_client(docname: str) -> str:
    """An OAuth Client whose docname is pinned, the way FAC pins both of its own.

    The controller forces `client_id = name`, so pinning the docname is what makes
    `client_id` predictable — see `_get_or_create_ar_oauth_client`.
    """
    redirect = "https://example.invalid/callback"
    return (
        frappe.get_doc(
            {
                "doctype": "OAuth Client",
                "app_name": f"Test {docname}",
                "scopes": "all openid",
                "redirect_uris": redirect,
                "default_redirect_uri": redirect,
                "grant_type": "Authorization Code",
                "response_type": "Code",
            }
        )
        .insert(ignore_permissions=True, set_name=docname)
        .name
    )


def _mint(user: str, client: str, status: str = "Active") -> str:
    """An OAuth Bearer Token row, as Frappe's save_bearer_token writes on sign-in."""
    access = frappe.generate_hash(length=30)
    frappe.get_doc(
        {
            "doctype": "OAuth Bearer Token",
            "client": client,
            "user": user,
            "scopes": "all openid",
            "access_token": access,
            "refresh_token": frappe.generate_hash(length=30),
            "expires_in": 3600,
            "status": status,
        }
    ).insert(ignore_permissions=True)
    return access


class FacCloudCallerTestCase(BaseAssistantTest):
    """Shared fixtures: the FAC Cloud client, an unrelated client, and a user."""

    def setUp(self):
        super().setUp()
        self.user = self.make_throwaway_user("fac-cloud-gate")

        # FAC Cloud's client may already exist on a site that has registered with
        # it; reuse the row rather than colliding on the pinned docname.
        if frappe.db.exists("OAuth Client", FAC_CLOUD_OAUTH_CLIENT_ID):
            self.fac_cloud_client = FAC_CLOUD_OAUTH_CLIENT_ID
        else:
            self.fac_cloud_client = _make_oauth_client(FAC_CLOUD_OAUTH_CLIENT_ID)

        # Stands in for a client created by dynamic registration — Claude Desktop,
        # ChatGPT, anything a user connects themselves.
        self.other_client = _make_oauth_client(f"dcr-client-{frappe.generate_hash(length=8)}")

    def _as_caller(self, access_token: str | None) -> None:
        """Make the current request look like one carrying this bearer token."""
        headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
        set_request(method="POST", path=MCP_PATH, headers=headers)
        frappe.set_user(self.user)


class TestFacCloudCallerIdentity(FacCloudCallerTestCase):
    """`request_is_from_fac_cloud` must answer from the token's OAuth client."""

    def test_fac_cloud_token_is_recognised(self):
        self._as_caller(_mint(self.user, self.fac_cloud_client))

        self.assertTrue(request_is_from_fac_cloud())

    def test_another_oauth_client_is_not_fac_cloud(self):
        """The whole point: a self-registered MCP client must not pass as FAC Cloud."""
        self._as_caller(_mint(self.user, self.other_client))

        self.assertFalse(request_is_from_fac_cloud())

    def test_a_request_without_a_bearer_token_is_not_fac_cloud(self):
        """A session cookie or API key caller — answered False, not raised."""
        self._as_caller(None)

        self.assertFalse(request_is_from_fac_cloud())

    def test_an_unknown_token_is_not_fac_cloud(self):
        self._as_caller(frappe.generate_hash(length=30))

        self.assertFalse(request_is_from_fac_cloud())

    def test_a_revoked_fac_cloud_token_is_not_fac_cloud(self):
        """Status is checked, so a revoked token cannot keep its privilege."""
        self._as_caller(_mint(self.user, self.fac_cloud_client, status="Revoked"))

        self.assertFalse(request_is_from_fac_cloud())

    def test_a_token_belonging_to_another_user_is_not_fac_cloud(self):
        """The token must belong to the session it arrives on."""
        bystander = self.make_throwaway_user("fac-cloud-bystander")
        self._as_caller(_mint(bystander, self.fac_cloud_client))

        self.assertFalse(request_is_from_fac_cloud())


class TestCallerIdentityWithoutARequest(BaseAssistantTest):
    """Asking who the caller is must never raise when there is no HTTP request.

    It did: ``frappe.get_request_header`` raises with no request bound, and
    ``_build_tool_registry`` catches everything, so the whole registry came back
    EMPTY — every tool gone, with only a log line to say so. Background jobs,
    bench commands and any test calling the builder directly hit this path.
    """

    def _without_a_request(self) -> None:
        original = getattr(frappe.local, "request", None)
        frappe.local.request = None
        self.addCleanup(lambda: setattr(frappe.local, "request", original))

    def test_no_request_is_simply_not_fac_cloud(self):
        self._without_a_request()

        self.assertFalse(request_is_from_fac_cloud())

    def test_the_registry_is_still_built_without_a_request(self):
        """The regression: this returned {} once the gate raised."""
        self._without_a_request()

        self.assertTrue(_build_tool_registry(), "registry came back empty")


class TestFacCloudOnlyDeclaration(BaseAssistantTest):
    """The restriction is declared by the plugin and resolved to tool names."""

    def test_faco_plugin_declares_itself_fac_cloud_only(self):
        self.assertTrue(FacoPlugin().is_fac_cloud_only())

    def test_core_plugin_is_not_restricted(self):
        """The default must stay False, or every plugin would vanish from MCP."""
        self.assertFalse(CorePlugin().is_fac_cloud_only())

    def test_discovery_records_the_flag(self):
        """Discovery keeps the flag; the plugin instance itself is not retained."""
        discovered = get_plugin_manager()._discovered_plugins

        self.assertTrue(discovered["faco"].fac_cloud_only)
        self.assertFalse(discovered["core"].fac_cloud_only)

    def test_restricted_tool_names_match_their_plugins(self):
        """Holds whether or not faco is enabled on this site, so it cannot go vacuous."""
        manager = get_plugin_manager()
        restricted = manager.get_fac_cloud_only_tools()

        for name, tool_info in manager.get_all_tools().items():
            plugin = manager._discovered_plugins.get(tool_info.plugin_name)
            expected = bool(getattr(plugin, "fac_cloud_only", False))
            self.assertEqual(name in restricted, expected, f"{name} (plugin {tool_info.plugin_name})")

    def test_send_email_belongs_to_core_and_is_never_restricted(self):
        """It has no FAC Chat dependency, so restricting faco must not remove it."""
        self.assertIn("send_email", CorePlugin().get_tools())
        self.assertNotIn("send_email", FacoPlugin().get_tools())
        self.assertNotIn("send_email", get_plugin_manager().get_fac_cloud_only_tools())

    def test_generate_document_and_browser_tools_stay_in_faco(self):
        faco_tools = FacoPlugin().get_tools()

        self.assertIn("generate_document", faco_tools)
        self.assertTrue([name for name in faco_tools if name.startswith("browser_")])


class TestRegistryHidesRestrictedTools(FacCloudCallerTestCase):
    """What `tools/list` offers, and what `tools/call` will therefore accept.

    The caller identity and the registry build are real here. Only the *set of
    restricted names* is substituted, so that the test does not depend on whether
    this site has the faco plugin enabled — enabling it in a test would commit.
    `TestFacCloudOnlyDeclaration` checks that set against the real plugins.
    """

    def setUp(self):
        super().setUp()
        self._as_caller(_mint(self.user, self.other_client))
        unfiltered = _build_tool_registry()
        if not unfiltered:
            self.skipTest("no tools available to this user — nothing to filter")
        # Restrict a tool this user really has, so removal is observable.
        self.restricted = next(iter(unfiltered))
        self.unrestricted = [name for name in unfiltered if name != self.restricted]

    def _registry_for(self, access_token: str) -> dict:
        self._as_caller(access_token)
        with patch(
            "frappe_assistant_core.utils.plugin_manager.PluginManager.get_fac_cloud_only_tools",
            return_value={self.restricted},
        ):
            return _build_tool_registry()

    def test_another_client_does_not_see_a_restricted_tool(self):
        registry = self._registry_for(_mint(self.user, self.other_client))

        self.assertNotIn(self.restricted, registry)

    def test_fac_cloud_still_sees_a_restricted_tool(self):
        registry = self._registry_for(_mint(self.user, self.fac_cloud_client))

        self.assertIn(self.restricted, registry)

    def test_unrestricted_tools_are_untouched_for_another_client(self):
        """A too-broad filter would strip core tools from every MCP client."""
        registry = self._registry_for(_mint(self.user, self.other_client))

        for name in self.unrestricted:
            self.assertIn(name, registry)

    def test_a_hidden_tool_is_refused_before_it_can_run(self):
        """Hiding also blocks execution: no realtime publish, no 30 second timeout.

        `_handle_tools_call` resolves names against the registry it is handed, so
        the one filter closes both `tools/list` and `tools/call`.
        """
        from frappe_assistant_core.api.fac_endpoint import mcp

        registry = self._registry_for(_mint(self.user, self.other_client))

        result = mcp._handle_tools_call({"name": self.restricted, "arguments": {}}, registry)

        self.assertTrue(result.get("isError"))
        self.assertIn("not found", str(result).lower())


class TestSharedBearerParsing(BaseAssistantTest):
    """`_mobile_sessions` and the MCP gate must read the header the same way."""

    def test_mobile_sign_out_still_rejects_a_missing_bearer(self):
        """The shared parser returns None; the mobile wrapper must still raise."""
        from frappe_assistant_core.chat.api._mobile_sessions import _presented_bearer

        set_request(method="POST", path=MCP_PATH, headers={})

        with self.assertRaises(frappe.AuthenticationError):
            _presented_bearer()

    def test_both_callers_read_the_same_token(self):
        from frappe_assistant_core.chat.api._mobile_sessions import _presented_bearer
        from frappe_assistant_core.utils.mcp_caller import presented_bearer_token

        token = frappe.generate_hash(length=30)
        set_request(method="POST", path=MCP_PATH, headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(presented_bearer_token(), token)
        self.assertEqual(_presented_bearer(), token)
