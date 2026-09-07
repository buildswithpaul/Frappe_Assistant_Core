# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""_register_user_with_ar must key AR by email but OAuth tokens by Frappe docname.

Two identities are in play and they diverge for the Administrator account:
  * AR Tenant User / MCP server  -> keyed by EMAIL (AR's contract)
  * local OAuth Bearer Token.user -> keyed by the Frappe USER DOCNAME, because
    the MCP endpoint does frappe.set_user(bearer_token.user); an email that is
    not a User docname (e.g. Administrator's email) would fail that call.

For ordinary staff the two coincide (username == email); this test pins the
Administrator case where they differ.
"""

from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestRegisterUserIdentitySplit(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def test_administrator_registers_ar_by_email_oauth_by_docname(self):
        from frappe_assistant_core.chat.api import auth

        # Pinned rather than read from the site: an untouched Frappe install
        # leaves Administrator's email as the `admin@example.com` placeholder,
        # which `_ar_user_id` deliberately refuses to hand to AR. The invariant
        # under test is the docname/email *split*, not where the email came
        # from, so the resolver is stubbed with a real address.
        admin_email = "owner@promantia.com"

        client = MagicMock()
        client.register_user.return_value = {"user_id": admin_email}
        client.add_user_mcp_server.return_value = {"success": True}

        fake_tokens = {
            "client_id": "cid",
            "client_secret": "csecret",
            "access_token": "atok",
            "refresh_token": "rtok",
            "expires_in": 3600,
        }

        with patch(
            "frappe_assistant_core.chat.api.auth.get_fac_cloud_client",
            return_value=client,
        ), patch(
            "frappe_assistant_core.chat.api.auth._get_or_create_ar_oauth_client",
            return_value=MagicMock(),
        ), patch(
            "frappe_assistant_core.chat.api.auth._ar_user_id",
            return_value=admin_email,
        ), patch(
            "frappe_assistant_core.chat.api.auth._generate_oauth_tokens_for_user",
            return_value=fake_tokens,
        ) as mock_tokens:
            auth._register_user_with_ar("Administrator")

        # AR side keyed by email
        _, reg_kwargs = client.register_user.call_args
        self.assertEqual(reg_kwargs["user_id"], admin_email)
        self.assertEqual(reg_kwargs["registered_by"], admin_email)

        _, mcp_kwargs = client.add_user_mcp_server.call_args
        self.assertEqual(mcp_kwargs["user_id"], admin_email)

        # local OAuth token keyed by the Frappe docname (Administrator), NOT email
        token_args, _ = mock_tokens.call_args
        self.assertEqual(
            token_args[1],
            "Administrator",
            "OAuth Bearer Token must key on the Frappe User docname",
        )
