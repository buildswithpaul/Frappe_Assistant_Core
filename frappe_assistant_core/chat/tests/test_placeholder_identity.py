# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""`admin@example.com` is not an identity — it is Frappe's install fixture.

`frappe/utils/install.py` stamps `User("Administrator").email` with
`admin@example.com` on every site, and `bench new-site` has no flag to change
it. So on essentially every customer site the Administrator account carries a
placeholder address that no one can receive mail at (example.com is reserved by
RFC 2606).

`_ar_user_id` faithfully returned it, and FAC then registered the tenant owner
on AR under that address: production's only tenant has
`owner_user_id = "admin@example.com"` beside a real, verified
`owner_email = "hari.madhavan@promantia.com"`.

Nothing is hardcoded here — the value is Frappe's, and the defect is that a
shared placeholder became a durable identity. The moment anyone gives
Administrator a real address, `_ar_user_id` returns something new: FAC creates
a *second* AR Tenant User (a second billed seat), the placeholder seat stays
Active as an orphan, and `_is_tenant_owner` stops matching — locking the real
owner out of their own tenant.
"""

from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest

AR_STOP = {}


class TestPlaceholderEmailsAreNotIdentities(BaseAssistantTest):
    def test_frappes_install_placeholders_are_recognised(self):
        from frappe_assistant_core.chat.api.auth import _is_placeholder_email

        self.assertTrue(_is_placeholder_email("admin@example.com"))
        self.assertTrue(_is_placeholder_email("guest@example.com"))
        self.assertTrue(_is_placeholder_email("ADMIN@EXAMPLE.COM"))

    def test_a_real_address_is_not_a_placeholder(self):
        from frappe_assistant_core.chat.api.auth import _is_placeholder_email

        self.assertFalse(_is_placeholder_email("hari.madhavan@promantia.com"))
        # Only Frappe's two fixtures, not the whole reserved domain: a site
        # deliberately using example.com elsewhere is not our business.
        self.assertFalse(_is_placeholder_email("hari@example.com"))

    def test_resolution_stays_total_so_existing_tenants_keep_their_seat(self):
        """`_ar_user_id` must still return the placeholder.

        Every AR read path — membership, boot, privacy, streaming — resolves
        through here. A tenant already seated under `admin@example.com` (which
        production is) would stop matching its own seat the moment this
        returned anything else, and lose chat entirely. The placeholder is
        refused where it would become durable instead: at seat creation.
        """
        from frappe_assistant_core.chat.api.auth import _ar_user_id

        with patch("frappe.db.get_value", return_value="admin@example.com"):
            self.assertEqual(_ar_user_id("Administrator"), "admin@example.com")

    def test_a_real_administrator_email_still_resolves(self):
        """The normalization that made the owner recognizable still works."""
        from frappe_assistant_core.chat.api.auth import _ar_user_id

        with patch("frappe.db.get_value", return_value="paul@promantia.com"):
            self.assertEqual(_ar_user_id("Administrator"), "paul@promantia.com")


class TestNoSeatIsCreatedForAPlaceholder(BaseAssistantTest):
    def test_registration_refuses_rather_than_minting_a_junk_seat(self):
        """The seat is the billed unit; it must not be created under a
        placeholder that every Frappe site on earth shares."""
        from frappe_assistant_core.chat.api import auth

        client = frappe._dict({"register_user": lambda **kw: None})

        with patch.object(auth, "get_fac_cloud_client", return_value=client), patch.object(
            auth, "_ar_user_id", return_value="admin@example.com"
        ), patch.object(auth, "_get_user_context", return_value={}):
            with self.assertRaises(frappe.ValidationError) as caught:
                auth._register_user_with_ar("Administrator")

        # Actionable, not a stack trace: the admin has to fix their own account.
        self.assertIn("email", str(caught.exception).lower())

    def test_a_real_address_still_creates_the_seat(self):
        """The guard must not stand between ordinary staff and a seat."""
        from frappe_assistant_core.chat.api import auth

        client = MagicMock()
        client.register_user.return_value = {"user_id": "hari@promantia.com"}
        client.add_user_mcp_server.return_value = {"success": True}
        tokens = {
            "client_id": "cid",
            "client_secret": "cs",
            "access_token": "at",
            "refresh_token": "rt",
            "expires_in": 3600,
        }

        with patch.object(auth, "get_fac_cloud_client", return_value=client), patch.object(
            auth, "_ar_user_id", return_value="hari@promantia.com"
        ), patch.object(auth, "_get_user_context", return_value={}), patch.object(
            auth, "_get_or_create_ar_oauth_client", return_value=MagicMock()
        ), patch.object(auth, "_generate_oauth_tokens_for_user", return_value=tokens):
            result = auth._register_user_with_ar("hari@promantia.com")

        self.assertTrue(result["success"])
        client.register_user.assert_called_once()


def _fake_resolver(*, administrator_is):
    """Stand in for `_ar_user_id`: pass addresses through, map the docname."""

    def resolve(user=None):
        user = user or "Administrator"
        return administrator_is if user == "Administrator" else user

    return resolve


class TestOwnerIdentityIsTheLoginNotTheMailbox(BaseAssistantTest):
    """`accepted_by` becomes AR Tenant.owner_user_id, which both owner gates
    match against `_ar_user_id(frappe.session.user)`. It is therefore the
    REGISTERING LOGIN, never the address typed into the form — that address is
    `owner_email`, a mailbox that may be shared and may be nobody's login.

    Conflating the two is the bug, and it has now been made in both
    directions: first the session account (a placeholder every Frappe install
    shares), then the typed mailbox (an address nobody signs in as, which
    locks the real owner out with no admin left to ask).
    """

    def _call(self, resolver, **kwargs):
        target = "frappe_assistant_core.chat.fac_cloud_client.register_tenant"
        with patch("frappe_assistant_core.chat.api.auth._ar_user_id", resolver), patch(
            target, return_value=AR_STOP
        ) as register_tenant:
            from frappe_assistant_core.chat.api.settings.registration import (
                register_with_ar,
            )

            result = register_with_ar(terms_version="1.0", **kwargs)
        return result, register_tenant

    def test_the_typed_mailbox_does_not_become_the_owner_identity(self):
        resolver = _fake_resolver(administrator_is="clinton@acme.com")
        _, register_tenant = self._call(resolver, owner_email="accounts@acme.com")

        kwargs = register_tenant.call_args.kwargs
        self.assertEqual(kwargs["accepted_by"], "clinton@acme.com")
        self.assertEqual(kwargs["owner_email"], "accounts@acme.com")

    def test_the_two_agree_when_the_admin_types_their_own_address(self):
        resolver = _fake_resolver(administrator_is="clinton@acme.com")
        _, register_tenant = self._call(resolver, owner_email="clinton@acme.com")

        kwargs = register_tenant.call_args.kwargs
        self.assertEqual(kwargs["accepted_by"], "clinton@acme.com")
        self.assertEqual(kwargs["owner_email"], "clinton@acme.com")

    def test_a_placeholder_login_is_refused_before_a_tenant_exists(self):
        """The wall `_register_user_with_ar` already puts up at first connect,
        moved earlier — before it can strand a tenant that exists on AR but
        whose owner can never be recognised."""
        resolver = _fake_resolver(administrator_is="admin@example.com")
        result, register_tenant = self._call(resolver, owner_email="real@acme.com")

        self.assertFalse(result["success"])
        self.assertIn("no email address", result["error"].lower())
        register_tenant.assert_not_called()

    def test_the_caller_cannot_nominate_someone_else_as_owner(self):
        """Identity is derived, never accepted: a supplied `accepted_by` would
        be a claim, and this endpoint would be the one place that honoured it."""
        import inspect

        from frappe_assistant_core.chat.api.settings.registration import register_with_ar

        fn = register_with_ar
        while hasattr(fn, "__wrapped__"):
            fn = fn.__wrapped__
        self.assertNotIn("accepted_by", inspect.signature(fn).parameters)
