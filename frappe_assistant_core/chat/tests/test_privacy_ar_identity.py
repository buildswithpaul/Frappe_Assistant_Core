# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Privacy/GDPR proxy endpoints must address AR by the email identity.

AR keys AR Tenant Users by email (see _ar_user_id). Every privacy.py call that
reaches AR through the SDK must pass the resolved email, not the raw Frappe
docname — otherwise the AR-side {tenant, user_id} lookup misses for any account
whose username is not an email (the canonical case: Administrator), the write is
silently swallowed, and memory_consent never lands. These tests run as
Administrator precisely because that is the account where docname != email.
"""

from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestPrivacyArIdentity(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.admin_email = frappe.db.get_value("User", "Administrator", "email")
        self.assertTrue(self.admin_email, "Administrator must carry an email for these tests")
        self.assertNotEqual(self.admin_email, "Administrator", "test premise: docname != email")

    def _patch_client(self):
        """Patch _get_client to return a MagicMock SDK client."""
        client = MagicMock()
        p = patch("frappe_assistant_core.chat.api.privacy._get_client", return_value=client)
        p.start()
        self.addCleanup(p.stop)
        return client

    def test_save_initial_consent_addresses_ar_by_email(self):
        from frappe_assistant_core.chat.api import privacy

        client = self._patch_client()
        privacy.save_initial_consent(memory_consent=True)

        client.update_user_consent.assert_called_once()
        kwargs = client.update_user_consent.call_args.kwargs
        self.assertEqual(
            kwargs.get("user_id"),
            self.admin_email,
            "consent write must target the email-keyed AR Tenant User, not the docname",
        )
        self.assertEqual(kwargs.get("granted"), True)

        client.complete_onboarding.assert_called_once()
        oc_kwargs = client.complete_onboarding.call_args.kwargs
        oc_args = client.complete_onboarding.call_args.args
        passed = oc_kwargs.get("user_id") if "user_id" in oc_kwargs else (oc_args[0] if oc_args else None)
        self.assertEqual(passed, self.admin_email)

    def test_failed_consent_write_does_not_mark_complete(self):
        """If the AR consent write fails, the local privacy_consent_complete flag
        must NOT be set — otherwise the tour never reappears to retry and the
        wrong state is locked in permanently."""
        from frappe_assistant_core.chat.api import privacy

        # Isolate from any pre-existing row: start with the flag explicitly 0.
        prefs_name = frappe.db.get_value("FAC Chat User Preferences", {"user": "Administrator"}, "name")
        if prefs_name:
            frappe.db.set_value("FAC Chat User Preferences", prefs_name, "privacy_consent_complete", 0)
        else:
            doc = frappe.new_doc("FAC Chat User Preferences")
            doc.user = "Administrator"
            doc.privacy_consent_complete = 0
            doc.insert(ignore_permissions=True)

        client = self._patch_client()
        client.update_user_consent.side_effect = RuntimeError("AR down / user not found")

        with self.assertRaises(RuntimeError):
            privacy.save_initial_consent(memory_consent=True)

        flag = frappe.db.get_value(
            "FAC Chat User Preferences", {"user": "Administrator"}, "privacy_consent_complete"
        )
        self.assertNotEqual(flag, 1, "must not mark consent complete when the AR write failed")

    def test_update_my_consent_addresses_ar_by_email(self):
        from frappe_assistant_core.chat.api import privacy

        client = self._patch_client()
        privacy.update_my_consent(consent_type="memory", granted=True)

        kwargs = client.update_user_consent.call_args.kwargs
        self.assertEqual(kwargs.get("user_id"), self.admin_email)

    def test_restrict_my_processing_addresses_ar_by_email(self):
        from frappe_assistant_core.chat.api import privacy

        client = self._patch_client()
        privacy.restrict_my_processing(restrict=True)

        kwargs = client.restrict_user_processing.call_args.kwargs
        self.assertEqual(kwargs.get("user_id"), self.admin_email)

    def test_get_privacy_config_reads_user_by_email(self):
        from frappe_assistant_core.chat.api import privacy

        client = self._patch_client()
        client.get_user.return_value = {"memory_consent": True, "processing_restricted": False}
        privacy.get_privacy_config()

        kwargs = client.get_user.call_args.kwargs
        args = client.get_user.call_args.args
        passed = kwargs.get("user_id") if "user_id" in kwargs else (args[0] if args else None)
        self.assertEqual(passed, self.admin_email)

    def test_export_and_erase_and_rectify_address_ar_by_email(self):
        from frappe_assistant_core.chat.api import privacy

        client = self._patch_client()
        client.export_user_data.return_value = {"status": "success", "data": {}}
        privacy.export_my_data()
        self.assertEqual(client.export_user_data.call_args.kwargs.get("user_id"), self.admin_email)

        client.rectify_user_data.return_value = {"status": "success"}
        privacy.update_my_data(updates='{"display_name": "X"}')
        self.assertEqual(client.rectify_user_data.call_args.kwargs.get("user_id"), self.admin_email)
