# Frappe Assistant Core - Debug Bundle Export API Tests
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Tests for the System-Manager-only debug bundle export.

Uses plain ``unittest.TestCase`` (not ``FrappeTestCase``) to match the rest of
the FAC suite: this is an ERPNext site and ``FrappeTestCase.setUpClass`` can
crash on fiscal-year fixtures. Each test cleans up its own rows in tearDown.
"""

import io
import json
import unittest
import zipfile
from unittest.mock import patch

import frappe

from frappe_assistant_core import __version__ as fac_version
from frappe_assistant_core.chat.api.chat.debug_bundle import export_debug_bundle

TEST_USER = "Administrator"


class TestDebugBundle(unittest.TestCase):
    def setUp(self):
        self._session_ids = set()
        self._file_names = set()

    def tearDown(self):
        for sid in self._session_ids:
            frappe.db.delete("FAC Chat Session State", {"session_id": sid})
            frappe.db.delete("FAC Chat Message", {"session_id": sid})
        for fname in self._file_names:
            frappe.db.delete("File", {"name": fname})
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — test seeds rows then asserts across the real File insert commit boundary

    def _sid(self, suffix):
        sid = f"test-debug-{suffix}-{frappe.generate_hash(length=8)}"
        self._session_ids.add(sid)
        return sid

    def _seed_session(self, sid):
        """Seed two FAC Chat Message rows + a session state row for ``sid``."""
        for idx, (role, content) in enumerate([("user", "hello world"), ("assistant", "hi there")], start=1):
            frappe.get_doc(
                {
                    "doctype": "FAC Chat Message",
                    "session_id": sid,
                    "role": role,
                    "content": content,
                    "user": TEST_USER,
                    "timestamp": frappe.utils.now(),
                    "idx": idx,
                }
            ).insert(ignore_permissions=True)

        frappe.get_doc(
            {
                "doctype": "FAC Chat Session State",
                "session_id": sid,
                "user": TEST_USER,
                "turn_seq": 1,
                "state_blob": "YmxvYg==",
                "state_sig": "deadbeef",
                "format_version": 1,
            }
        ).insert(ignore_permissions=True)
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — seed rows must be visible to the endpoint's own reads

    # --- role gate ---

    def test_non_system_manager_raises_permission_error(self):
        """A user without System Manager must get nothing."""
        sid = self._sid("gate")
        with patch.object(frappe, "get_roles", return_value=["All", "Guest"]):
            with self.assertRaises(frappe.PermissionError):
                export_debug_bundle(sid)

    # --- happy path ---

    def test_system_manager_gets_valid_three_member_zip(self):
        sid = self._sid("happy")
        self._seed_session(sid)

        result = export_debug_bundle(sid)

        self.assertIn("file_url", result)
        self.assertTrue(result["file_url"])

        file_doc = frappe.get_doc("File", {"file_url": result["file_url"]})
        self._file_names.add(file_doc.name)

        # The bundle must never be world-readable.
        self.assertEqual(file_doc.is_private, 1)

        content = file_doc.get_content()
        if isinstance(content, str):
            content = content.encode("utf-8")

        with zipfile.ZipFile(io.BytesIO(content)) as z:
            names = set(z.namelist())
            self.assertEqual(names, {"messages.json", "session_state.json", "versions.json"})

            messages = json.loads(z.read("messages.json"))
            self.assertEqual(len(messages), 2)
            self.assertEqual(messages[0]["role"], "user")
            self.assertEqual(messages[0]["content"], "hello world")
            self.assertEqual(messages[1]["role"], "assistant")

            state = json.loads(z.read("session_state.json"))
            self.assertEqual(state["state_blob"], "YmxvYg==")
            self.assertEqual(state["turn_seq"], 1)

            versions = json.loads(z.read("versions.json"))
            self.assertIn("frappe", versions)
            self.assertIn("frappe_assistant_core", versions)
            self.assertEqual(versions["frappe_assistant_core"], fac_version)


if __name__ == "__main__":
    unittest.main()
