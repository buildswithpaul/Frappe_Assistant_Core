# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Tests for _is_tenant_owner() — recognizing the FACO tenant owner.

The owner must be able to self-connect before any seat exists (a chicken-and-egg
otherwise: membership is created by the very call the guard blocks). AR is the
source of truth for who the owner is; FAC learns it from get_tenant_info and
compares against the user's AR identity (email).
"""

from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest

_OWNER_EMAIL = "owner_detect@example.com"


class TestTenantOwnerDetection(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def _client_returning_owner(self, owner_email=None, owner_user_id=None):
        client = MagicMock()
        client.get_tenant_info.return_value = {
            "tenant_id": "T-TEST",
            "owner_email": owner_email,
            "owner_user_id": owner_user_id,
        }
        return client

    def test_owner_matched_by_email(self):
        from frappe_assistant_core.chat.api.auth import _is_tenant_owner

        client = self._client_returning_owner(owner_email=_OWNER_EMAIL)
        with patch(
            "frappe_assistant_core.chat.api.auth.get_fac_cloud_client",
            return_value=client,
        ):
            self.assertTrue(_is_tenant_owner(_OWNER_EMAIL))

    def test_non_owner_not_matched(self):
        from frappe_assistant_core.chat.api.auth import _is_tenant_owner

        client = self._client_returning_owner(owner_email=_OWNER_EMAIL)
        with patch(
            "frappe_assistant_core.chat.api.auth.get_fac_cloud_client",
            return_value=client,
        ):
            self.assertFalse(_is_tenant_owner("someone_else@example.com"))

    def test_owner_matched_by_owner_user_id_fallback(self):
        """Legacy tenants may carry owner_user_id (e.g. an email) but no
        owner_email; the match still succeeds on owner_user_id."""
        from frappe_assistant_core.chat.api.auth import _is_tenant_owner

        client = self._client_returning_owner(owner_user_id=_OWNER_EMAIL)
        with patch(
            "frappe_assistant_core.chat.api.auth.get_fac_cloud_client",
            return_value=client,
        ):
            self.assertTrue(_is_tenant_owner(_OWNER_EMAIL))

    def test_owner_matched_by_user_id_when_email_differs(self):
        """The connecting user is identified by their Frappe identity, which AR
        stores as owner_user_id — NOT owner_email (the billing/verification
        address, which can differ). The match must key on owner_user_id, exactly
        like AR's own _validate_registration_authority (registered_by ==
        owner_user_id). This is the production case that regressed: owner_user_id
        = the admin's account email, owner_email = a different typed-in address.
        """
        from frappe_assistant_core.chat.api.auth import _is_tenant_owner

        client = self._client_returning_owner(
            owner_user_id="paul.clinton@gmail.com",
            owner_email="paul.clinton@promantia.com",
        )
        with patch(
            "frappe_assistant_core.chat.api.auth.get_fac_cloud_client",
            return_value=client,
        ):
            self.assertTrue(_is_tenant_owner("paul.clinton@gmail.com"))
            # The billing email is NOT the connect identity — must not match it.
            self.assertFalse(_is_tenant_owner("paul.clinton@promantia.com"))

    def test_no_client_is_not_owner(self):
        from frappe_assistant_core.chat.api.auth import _is_tenant_owner

        with patch(
            "frappe_assistant_core.chat.api.auth.get_fac_cloud_client",
            return_value=None,
        ):
            self.assertFalse(_is_tenant_owner(_OWNER_EMAIL))

    def test_ar_failure_is_not_owner(self):
        """A transient AR failure must not grant owner status (fail closed on
        ownership — it only widens access, so an error must not widen it)."""
        from frappe_assistant_core.chat.api.auth import _is_tenant_owner

        client = MagicMock()
        client.get_tenant_info.side_effect = Exception("AR down")
        with patch(
            "frappe_assistant_core.chat.api.auth.get_fac_cloud_client",
            return_value=client,
        ):
            self.assertFalse(_is_tenant_owner(_OWNER_EMAIL))
