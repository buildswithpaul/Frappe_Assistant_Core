# Frappe Assistant Core - chat upload size limit tests
# Copyright (C) 2025 Paul Clinton
#
# AGPL-3.0 License

"""Frappe's File rejects anything over System Settings → Max File Size, which is 25 MB
unless an administrator raises it. Chat uploads follow that limit, up to 50 MB, so a
file over it is refused with a message that says how to raise it, and a site that has
raised it, in System Settings and the site config Frappe holds every request to, takes
migration exports up to 50 MB.
"""

import base64
from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api.settings.uploads import upload_message_file
from frappe_assistant_core.tests.base_test import BaseAssistantTest

MB = 1024 * 1024


def _csv(size: int) -> bytes:
    # Unique header: Frappe content-addresses uploads.
    header = f"Customer Name,Territory,{frappe.generate_hash(length=8)}\n".encode()
    row = b"Acme,India,x\n"
    return header + row * ((size - len(header)) // len(row) + 1)


class TestChatUploadSizeLimit(BaseAssistantTest):
    def _set_site_limit_mb(self, mb: int):
        # What an administrator does in System Settings → Max File Size.
        original = frappe.db.get_single_value("System Settings", "max_file_size")
        frappe.db.set_single_value("System Settings", "max_file_size", mb)
        self._clear_settings_cache()
        self.addCleanup(self._clear_settings_cache)
        self.addCleanup(frappe.db.set_single_value, "System Settings", "max_file_size", original)

    @staticmethod
    def _clear_settings_cache():
        frappe.clear_document_cache("System Settings", "System Settings")
        if hasattr(frappe.local, "system_settings"):
            del frappe.local.system_settings

    def _upload(self, content: bytes) -> dict:
        with patch(
            "frappe_assistant_core.chat.api.settings.access.can_use_faco",
            return_value={"can_use": True},
        ):
            return upload_message_file(
                file_data=base64.b64encode(content).decode(),
                file_name="customers.csv",
                content_type="text/csv",
            )

    def test_file_over_the_site_limit_says_how_to_raise_it(self):
        self._set_site_limit_mb(25)
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._upload(_csv(26 * MB))
        self.assertIn("25 MB upload limit", str(ctx.exception))
        self.assertIn("System Settings", str(ctx.exception))

    def test_a_limit_raised_only_in_system_settings_is_still_the_requests_25_mb(self):
        # #33987: Frappe refuses any request but its own upload_file over the site config's
        # max_file_size (25 MB unset), so the 30 MB file never reached this code; over HTTP it
        # was an HTML 413, and the chat said only "Something went wrong"
        self._set_site_limit_mb(50)
        with patch.dict(frappe.conf, {"max_file_size": None}):
            with self.assertRaises(frappe.ValidationError) as ctx:
                self._upload(_csv(26 * MB))
        self.assertIn("25 MB upload limit", str(ctx.exception))
        self.assertIn("max_file_size", str(ctx.exception))

    def test_raised_site_limit_takes_a_file_over_25_mb(self):
        self._set_site_limit_mb(50)
        # and the site config's, which Frappe holds every request but upload_file's to
        with patch.dict(frappe.conf, {"max_file_size": 50 * MB}):
            result = self._upload(_csv(30 * MB))
        # Removes the 30 MB file from disk too; the rollback only undoes the row.
        self.addCleanup(
            frappe.delete_doc, "File", result["file"]["name"], ignore_permissions=True, force=True
        )

        self.assertTrue(result["success"])
        self.assertGreater(result["file"]["file_size"], 25 * MB)

    def test_chat_never_takes_more_than_50_mb(self):
        self._set_site_limit_mb(100)
        with patch.dict(frappe.conf, {"max_file_size": 100 * MB}), self.assertRaises(
            frappe.ValidationError
        ) as ctx:
            self._upload(_csv(51 * MB))
        self.assertIn("50MB", str(ctx.exception))
