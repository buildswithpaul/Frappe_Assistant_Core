# Copyright (C) 2026 Paul Clinton
# AGPL-3.0 License

"""FAC Chat Settings.tenant_secret must survive Singles saves and round-trip decrypt.

Root cause of first-connect "Encryption key is invalid / credentials corrupted":
an empty Singles value for the Password field makes Document.save() call
remove_encrypted_password() and wipe a perfectly good __Auth row — or leave
the field in a state where the next get_password() decrypts garbage.

These tests lock the store/clear/preserve contract.
"""

from __future__ import annotations

import frappe
from frappe.utils.password import get_decrypted_password

from frappe_assistant_core.tests.base_test import BaseAssistantTest

SECRET = "test-tenant-secret-value-32chars!!"


class TestTenantSecretStorage(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        from frappe_assistant_core.chat.tenant_credentials import clear_tenant_secret

        clear_tenant_secret()

    def tearDown(self):
        from frappe_assistant_core.chat.tenant_credentials import clear_tenant_secret

        clear_tenant_secret()
        super().tearDown()

    def test_store_round_trips_via_get_password(self):
        from frappe_assistant_core.chat.tenant_credentials import store_tenant_secret

        store_tenant_secret(SECRET)

        settings = frappe.get_single("FAC Chat Settings")
        self.assertEqual(settings.get_password("tenant_secret"), SECRET)
        self.assertEqual(
            get_decrypted_password("FAC Chat Settings", "FAC Chat Settings", "tenant_secret"),
            SECRET,
        )

    def test_empty_singles_value_plus_unrelated_save_does_not_wipe_secret(self):
        """The production bug: Singles row empty/blank while __Auth still holds
        the ciphertext. Any later Document.save() of FAC Chat Settings used to
        treat empty Password as 'clear' and delete __Auth — first connect then
        fails decrypt / looks like a corrupted encryption key.
        """
        from frappe_assistant_core.chat.tenant_credentials import store_tenant_secret

        store_tenant_secret(SECRET)

        # Corrupt only the Singles display value the way db_set("") does.
        frappe.db.set_single_value("FAC Chat Settings", "tenant_secret", "")
        frappe.clear_document_cache("FAC Chat Settings", "FAC Chat Settings")

        settings = frappe.get_single("FAC Chat Settings")
        self.assertFalse(settings.get("tenant_secret"))
        settings.max_context_tokens = (settings.max_context_tokens or 4000) + 1
        settings.save(ignore_permissions=True)

        frappe.clear_document_cache("FAC Chat Settings", "FAC Chat Settings")
        settings = frappe.get_single("FAC Chat Settings")
        self.assertEqual(settings.get_password("tenant_secret"), SECRET)

    def test_clear_removes_secret_from_auth(self):
        from frappe_assistant_core.chat.tenant_credentials import (
            clear_tenant_secret,
            store_tenant_secret,
        )

        store_tenant_secret(SECRET)
        clear_tenant_secret()

        missing = get_decrypted_password(
            "FAC Chat Settings",
            "FAC Chat Settings",
            "tenant_secret",
            raise_exception=False,
        )
        self.assertIsNone(missing)

    def test_store_rejects_short_secret(self):
        from frappe_assistant_core.chat.tenant_credentials import store_tenant_secret

        with self.assertRaises(frappe.ValidationError):
            store_tenant_secret("too-short")
