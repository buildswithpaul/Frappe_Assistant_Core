# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Idempotency tests for _register_mobile_oauth_client.

Regression coverage for the same class of bug already fixed for the FAC Cloud
client (_get_or_create_ar_oauth_client). The mobile registrar assigned a stable
client_id AFTER insert:

    client.client_id = client_id
    client.insert(ignore_permissions=True)

But the core OAuth Client controller forces ``client_id = self.name`` in
validate() (client_id is read-only) and the doctype names by random hash. So the
assigned client_id was CLOBBERED with the hash, and the dedup at the top of the
function (``get_value("OAuth Client", {"client_id": client_id})``) NEVER matched.
A brand-new "FACO Mobile" OAuth Client was therefore minted on EVERY registration
call (13 duplicate rows observed on the dev site).

The fix mirrors the FAC Cloud fix: pin the docname via
``insert(set_name=client_id, ...)`` so ``client_id == name == "faco-mobile-<device>"``
in a single write, making the dedup idempotent (one client per device, not one
per call), with a DuplicateEntryError catch + re-read to converge on races /
pre-existing rows.
"""

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestMobileOAuthIdempotency(BaseAssistantTest):
    REDIRECT = "facomobile://oauth/callback"

    def test_mobile_client_is_idempotent_per_device(self):
        """Registering the same device twice must reuse ONE client, not mint a 2nd."""
        from frappe_assistant_core.chat.api.auth import _register_mobile_oauth_client

        c1 = _register_mobile_oauth_client(self.REDIRECT, device_id="dev-abc-123")
        c2 = _register_mobile_oauth_client(self.REDIRECT, device_id="dev-abc-123")
        self.assertEqual(c1.name, c2.name, "same device must reuse the same client")

    def test_mobile_client_id_is_stable_and_intended(self):
        """The stored client_id must equal the intended faco-mobile-<device> value
        (not a random hash) so the dedup matches + the app gets a deterministic id."""
        from frappe_assistant_core.chat.api.auth import _register_mobile_oauth_client

        # device_id "shortdev" is < 16 chars, so client_id = "faco-mobile-shortdev".
        c = _register_mobile_oauth_client(self.REDIRECT, device_id="shortdev")
        self.assertEqual(c.client_id, "faco-mobile-shortdev")
        self.assertEqual(c.client_id, c.name)  # client_id mirrors docname now

    def test_mobile_client_id_truncates_long_device_id(self):
        """device_id is truncated to 16 chars in the stable client_id."""
        from frappe_assistant_core.chat.api.auth import _register_mobile_oauth_client

        # 20-char device_id → only first 16 chars used.
        c = _register_mobile_oauth_client(self.REDIRECT, device_id="abcdefghijklmnopqrst")
        self.assertEqual(c.client_id, "faco-mobile-abcdefghijklmnop")
        self.assertEqual(c.client_id, c.name)

    def test_mobile_default_client_id_when_no_device(self):
        from frappe_assistant_core.chat.api.auth import _register_mobile_oauth_client

        c = _register_mobile_oauth_client(self.REDIRECT)  # no device_id
        self.assertEqual(c.client_id, "faco-mobile")
        self.assertEqual(c.name, "faco-mobile")

    def test_security_redirect_uri_mismatch_still_refused(self):
        """The existing security check must remain: a 2nd registration for the same
        device with a DIFFERENT redirect_uri must be refused."""
        from frappe_assistant_core.chat.api.auth import _register_mobile_oauth_client

        _register_mobile_oauth_client(self.REDIRECT, device_id="dev-sec-1")
        with self.assertRaises(frappe.ValidationError):
            _register_mobile_oauth_client("evil://attacker/callback", device_id="dev-sec-1")

    def test_mobile_client_preserves_pkce_settings(self):
        from frappe_assistant_core.chat.api.auth import _register_mobile_oauth_client

        c = _register_mobile_oauth_client(self.REDIRECT, device_id="dev-pkce-1")
        self.assertEqual(c.scopes, "all openid")
        self.assertIn(self.REDIRECT, (c.redirect_uris or ""))
        self.assertEqual(c.grant_type, "Authorization Code")
        # PKCE public client: no secret auth.
        #
        # OAuth Client gained token_endpoint_auth_method in Frappe v16. On v15
        # the field does not exist, so the value _register_mobile_oauth_client
        # passes is dropped on insert and there is nothing to read back. The
        # rest of the client is identical on both, and PKCE is enforced by
        # FAC's own get_token override rather than by this field, so this is
        # asserted where the field exists rather than skipped outright.
        if frappe.get_meta("OAuth Client").get_field("token_endpoint_auth_method"):
            self.assertEqual(c.token_endpoint_auth_method, "None")
