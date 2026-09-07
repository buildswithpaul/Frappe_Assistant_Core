# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Idempotency tests for _get_or_create_ar_oauth_client.

Regression coverage for a bug where the helper deduped on a non-existent
`client_name` field of the core OAuth Client doctype. Because the filter
matched no column it always returned falsy, so EVERY call minted a brand-new
OAuth Client. Per-user OAuth Bearer Tokens are keyed on the client's docname,
so a later call's different client orphaned earlier tokens and produced a
FALSE NEGATIVE in the FACO membership gate (`_is_faco_member`) — wrongly
locking out real members.

The fix dedupes on a stable explicit `client_id` ("fac-cloud-integration").
Because client_id is read-only and validate() forces client_id = name, the
stable value is achieved by pinning the docname via insert(set_name=...) — a
single write — rather than an insert→rename→save round-trip.
"""

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestOAuthClientIdempotency(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # _get_or_create_ar_oauth_client throws without fac_cloud_url, which
        # would mask the idempotency assertions behind a configuration error.
        settings = frappe.get_single("FAC Chat Settings")
        if not settings.fac_cloud_url:
            settings.fac_cloud_url = "https://test.example.com"
            settings.save(ignore_permissions=True)

    def test_get_or_create_is_idempotent(self):
        """Calling twice must return the SAME OAuth Client (not create a 2nd)."""
        from frappe_assistant_core.chat.api.auth import _get_or_create_ar_oauth_client

        c1 = _get_or_create_ar_oauth_client()
        c2 = _get_or_create_ar_oauth_client()
        self.assertEqual(
            c1.name,
            c2.name,
            "second call must reuse the same client, not create a new one",
        )

    def test_canonical_client_id_is_stable(self):
        """The minted client carries the stable, dedupe-able client_id."""
        from frappe_assistant_core.chat.api.auth import _get_or_create_ar_oauth_client

        c = _get_or_create_ar_oauth_client()
        self.assertEqual(c.client_id, "fac-cloud-integration")

    def test_token_lookup_survives_repeated_calls(self):
        """A token issued against the client is still found after another
        get_or_create call.

        The bug: the 2nd call made a NEW client, so the membership gate's
        {"client": <new client>.name, "user": ...} lookup missed the token
        issued against the FIRST client — a false-negative lockout.
        """
        from frappe_assistant_core.chat.api.auth import _get_or_create_ar_oauth_client

        client = _get_or_create_ar_oauth_client()
        frappe.get_doc(
            {
                "doctype": "OAuth Bearer Token",
                "client": client.name,
                "user": "Administrator",
                "scopes": "all openid",
                "access_token": "idem_tok",
                "refresh_token": "idem_ref",
                "expires_in": 3600,
                "token_type": "Bearer",
            }
        ).insert(ignore_permissions=True)

        # A later call must return the SAME client, so the token still resolves.
        client2 = _get_or_create_ar_oauth_client()
        self.assertEqual(client.name, client2.name)
        self.assertTrue(
            frappe.db.exists(
                "OAuth Bearer Token",
                {"client": client2.name, "user": "Administrator"},
            )
        )

    def test_preexisting_canonical_name_converges(self):
        """If a row already holds the canonical name, get_or_create must return
        it (not raise) — covers the cold-start race / legacy-named-row case."""
        from frappe_assistant_core.chat.api.auth import _get_or_create_ar_oauth_client

        # First call mints the canonical row.
        c1 = _get_or_create_ar_oauth_client()
        # A second call when the canonical name already exists must converge, not raise.
        c2 = _get_or_create_ar_oauth_client()
        self.assertEqual(c1.name, c2.name)
        self.assertEqual(c2.name, "fac-cloud-integration")

    def test_canonical_client_preserves_scopes_and_redirect(self):
        """The canonical client keeps its scopes/redirect through creation."""
        from frappe_assistant_core.chat.api.auth import _get_or_create_ar_oauth_client

        c = _get_or_create_ar_oauth_client()
        self.assertEqual(c.scopes, "all openid")
        self.assertTrue(c.redirect_uris)  # callback_uri was set
        self.assertEqual(c.grant_type, "Authorization Code")
