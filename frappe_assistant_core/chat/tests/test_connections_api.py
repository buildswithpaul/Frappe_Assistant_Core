# frappe_assistant_core/chat/tests/test_connections_api.py
import unittest
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.chat.api import connections

MOD = "frappe_assistant_core.chat.api.connections"
# `_is_faco_member` is imported lazily inside `_assert_chat_access()`, so it is
# never bound in `connections`'s module namespace — patch it at its real
# definition site instead (verified: patching f"{MOD}._is_faco_member" raises
# AttributeError since connections has no such attribute at all).
FACO_MEMBER = "frappe_assistant_core.chat.api.settings.access._is_faco_member"


class TestListConnections(unittest.TestCase):
    def setUp(self):
        # Every test in this class exercises the "gate passes" path by default;
        # the two gate-specific tests below override one or the other to False.
        self._gate_patches = [
            patch(f"{MOD}.is_chat_enabled", return_value=True),
            patch(FACO_MEMBER, return_value=True),
        ]
        for p in self._gate_patches:
            p.start()
            self.addCleanup(p.stop)

    def _client(self, servers):
        client = MagicMock()
        client.get_user_mcp_servers.return_value = {"mcp_servers": servers}
        return client

    def test_managed_connection_is_listed_first(self):
        client = self._client(
            [
                {"server_name": "Acme", "managed": 0, "status": "Active"},
                {"server_name": "Main Frappe Site", "managed": 1, "status": "Active"},
            ]
        )
        with patch.object(connections, "_client", return_value=client):
            result = connections.list_connections()
        self.assertEqual(result["connections"][0]["server_name"], "Main Frappe Site")
        self.assertTrue(result["connections"][0]["managed"])

    def test_ar_unreachable_is_distinguished_from_empty(self):
        client = MagicMock()
        client.get_user_mcp_servers.return_value = {"mcp_servers": [], "_ar_unreachable": True}
        with patch.object(connections, "_client", return_value=client):
            result = connections.list_connections()
        self.assertTrue(result["ar_unreachable"])

    def test_removing_a_managed_connection_is_refused_locally(self):
        client = self._client([{"server_name": "Main Frappe Site", "managed": 1}])
        with patch.object(connections, "_client", return_value=client):
            with self.assertRaises(frappe.ValidationError):
                connections.remove_connection("Main Frappe Site")
        client.remove_user_mcp_server.assert_not_called()

    def test_chat_disabled_refuses_the_call(self):
        with patch(f"{MOD}.is_chat_enabled", return_value=False):
            with self.assertRaises(frappe.PermissionError):
                connections.list_connections()

    def test_a_non_member_is_refused(self):
        with patch(FACO_MEMBER, return_value=False):
            with self.assertRaises(frappe.PermissionError):
                connections.list_connections()

    def test_adding_a_connection_named_like_the_managed_one_is_refused_locally(self):
        client = MagicMock()
        with patch.object(connections, "_client", return_value=client):
            with self.assertRaises(frappe.ValidationError):
                connections.add_connection(
                    server_name="Main Frappe Site",
                    endpoint_url="https://attacker.example/api/method/frappe_assistant_core.mcp_handler",
                )
        client.add_user_mcp_server.assert_not_called()


class TestConnectWizardEndpoints(unittest.TestCase):
    """The wizard's five proxy endpoints.

    NOTE ON WHAT THESE TESTS CANNOT PROVE: `client` here is a MagicMock, which
    answers any attribute with a new mock and swallows any kwarg. If the real
    SDK never defined `begin_mcp_connect`, or declared different parameter
    names, every assertion below would still pass. The real-class assertion
    lives in frappe_assistant_core/tests/test_sdk_pin.py; the only proof that
    the PUBLISHED artifact has them is a clean-venv install of the pin.
    """

    def setUp(self):
        self._gate_patches = [
            patch(f"{MOD}.is_chat_enabled", return_value=True),
            patch(FACO_MEMBER, return_value=True),
        ]
        for p in self._gate_patches:
            p.start()
            self.addCleanup(p.stop)

    def test_begin_connect_forwards_the_url_and_the_ar_user(self):
        client = MagicMock()
        client.begin_mcp_connect.return_value = {"handle": "h-1", "preflight": {"steps": []}}
        with patch.object(connections, "_client", return_value=client):
            result = connections.begin_connect(endpoint_url="https://acme.example/mcp")

        kwargs = client.begin_mcp_connect.call_args.kwargs
        self.assertEqual(kwargs["endpoint_url"], "https://acme.example/mcp")
        self.assertTrue(kwargs["user_id"])
        self.assertEqual(result["handle"], "h-1")

    def test_begin_connect_omits_blank_manual_credentials(self):
        # A blank string would make AR record an empty manual registration
        # instead of taking the DCR path.
        client = MagicMock()
        client.begin_mcp_connect.return_value = {}
        with patch.object(connections, "_client", return_value=client):
            connections.begin_connect(endpoint_url="https://acme.example/mcp", client_id="  ")

        self.assertIsNone(client.begin_mcp_connect.call_args.kwargs["client_id"])

    def test_get_connect_session_forwards_the_handle(self):
        client = MagicMock()
        client.get_mcp_connect_session.return_value = {"status": "Authorized"}
        with patch.object(connections, "_client", return_value=client):
            result = connections.get_connect_session(handle="h-1")

        self.assertEqual(client.get_mcp_connect_session.call_args.kwargs["handle"], "h-1")
        self.assertEqual(result["status"], "Authorized")

    def test_get_connect_session_passes_reauth_server_name_through(self):
        # The wizard's only signal that a handle belongs to a reconnect. If this
        # proxy projects a subset of keys instead of returning AR's payload, a
        # reconnect resumed in a fresh tab falls through to the review step and
        # is refused for a duplicate name the user is not changing.
        client = MagicMock()
        client.get_mcp_connect_session.return_value = {
            "status": "Authorized",
            "reauth_server_name": "Acme Tasks",
        }
        with patch.object(connections, "_client", return_value=client):
            result = connections.get_connect_session(handle="h-1")

        self.assertEqual(result["reauth_server_name"], "Acme Tasks")

    def test_commit_connect_refuses_the_reserved_managed_name_locally(self):
        client = MagicMock()
        with patch.object(connections, "_client", return_value=client):
            with self.assertRaises(frappe.ValidationError):
                connections.commit_connect(handle="h-1", server_name="Main Frappe Site")
        client.commit_mcp_connect.assert_not_called()

    def test_commit_connect_forwards_a_normal_name(self):
        client = MagicMock()
        client.commit_mcp_connect.return_value = {"success": True}
        with patch.object(connections, "_client", return_value=client):
            result = connections.commit_connect(handle="h-1", server_name="Acme")

        kwargs = client.commit_mcp_connect.call_args.kwargs
        self.assertEqual(kwargs["handle"], "h-1")
        self.assertEqual(kwargs["server_name"], "Acme")
        self.assertTrue(result["success"])

    def test_abandon_connect_forwards_the_handle(self):
        client = MagicMock()
        client.abandon_mcp_connect.return_value = {"success": True}
        with patch.object(connections, "_client", return_value=client):
            connections.abandon_connect(handle="h-1")

        self.assertEqual(client.abandon_mcp_connect.call_args.kwargs["handle"], "h-1")

    def test_begin_reauth_uses_the_reauth_method_not_begin_connect(self):
        # Reconnecting must open a session with reauth_target set, so commit
        # updates the existing row in place. Routing it through
        # begin_mcp_connect would take the add path and hit the duplicate-name
        # refusal for a connection nobody is renaming.
        client = MagicMock()
        client.begin_mcp_reauth.return_value = {"handle": "h-9", "preflight": {"steps": []}}
        with patch.object(connections, "_client", return_value=client):
            result = connections.begin_reauth(server_name="Acme")

        kwargs = client.begin_mcp_reauth.call_args.kwargs
        self.assertEqual(kwargs["server_name"], "Acme")
        self.assertTrue(kwargs["user_id"])
        self.assertEqual(result["handle"], "h-9")
        client.begin_mcp_connect.assert_not_called()

    def test_begin_reauth_refuses_the_reserved_managed_name(self):
        # The managed connection's Frappe-specific OAuth path is untouched by
        # this feature; it must not be dragged through the MCP connect flow.
        client = MagicMock()
        with patch.object(connections, "_client", return_value=client):
            with self.assertRaises(frappe.ValidationError):
                connections.begin_reauth(server_name="Main Frappe Site")
        client.begin_mcp_reauth.assert_not_called()

    def test_every_wizard_endpoint_is_gated(self):
        client = MagicMock()
        with patch(f"{MOD}.is_chat_enabled", return_value=False):
            with patch.object(connections, "_client", return_value=client):
                for call in (
                    lambda: connections.begin_connect(endpoint_url="https://acme.example/mcp"),
                    lambda: connections.get_connect_session(handle="h-1"),
                    lambda: connections.commit_connect(handle="h-1", server_name="Acme"),
                    lambda: connections.abandon_connect(handle="h-1"),
                    lambda: connections.begin_reauth(server_name="Acme"),
                ):
                    with self.assertRaises(frappe.PermissionError):
                        call()
