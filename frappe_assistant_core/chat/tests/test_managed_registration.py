# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""_register_user_with_ar must send `managed=True` on its MCP server registration.

FAC's connection is auto-provisioned and never user-removable. AR actually derives
managed status server-side from the FAC registration shape (server_name/endpoint_url),
NOT from this parameter — the parameter has no effect on AR's decision either way.
This test exists purely for wire compatibility: it proves FAC sends the value the
SDK's `add_user_mcp_server(..., managed=...)` parameter expects, in case AR's
enforcement mechanism ever changes to trust it. It cannot prove the SDK accepts it
(client is a MagicMock here) — that is Task 8's job.
"""

from unittest.mock import MagicMock, patch

from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestManagedRegistration(BaseAssistantTest):
    def test_registration_marks_the_server_managed(self):
        from frappe_assistant_core.chat.api import auth

        client = MagicMock()
        client.register_user.return_value = {"user_id": "user@example.com"}
        client.add_user_mcp_server.return_value = {"success": True}

        with (
            patch.object(auth, "get_fac_cloud_client", return_value=client),
            patch.object(auth, "_get_or_create_ar_oauth_client", return_value=MagicMock()),
            patch.object(
                auth,
                "_generate_oauth_tokens_for_user",
                return_value={
                    "client_id": "cid",
                    "client_secret": "csecret",
                    "access_token": "atok",
                    "refresh_token": "rtok",
                    "expires_in": 3600,
                },
            ),
        ):
            auth._register_user_with_ar("user@example.com")

        self.assertIs(client.add_user_mcp_server.call_args.kwargs.get("managed"), True)


class TestGetUserMcpServersUnreachable(BaseAssistantTest):
    """get_user_mcp_servers must forward AR's `_ar_unreachable` marker the
    same way its sibling get_user_auth_status already does — a transient AR
    outage is not "you have zero servers configured"."""

    def test_forwards_ar_unreachable_marker(self):
        from frappe_assistant_core.chat.api import auth

        client = MagicMock()
        client.get_user_mcp_servers.return_value = {
            "_ar_unreachable": True,
            "error": "AR is temporarily unreachable",
        }

        with patch.object(auth, "get_fac_cloud_client", return_value=client):
            result = auth.get_user_mcp_servers()

        self.assertEqual(
            result,
            {
                "success": True,
                "mcp_servers": [],
                "_ar_unreachable": True,
                "error": "AR is temporarily unreachable",
            },
        )
