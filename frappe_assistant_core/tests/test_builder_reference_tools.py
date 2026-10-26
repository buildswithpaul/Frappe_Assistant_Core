# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

"""Tests for the sandbox_reference and recent_errors tools."""

from unittest.mock import patch

import frappe
from frappe.utils import add_to_date, now_datetime

from frappe_assistant_core.plugins.core.tools.recent_errors import RecentErrors
from frappe_assistant_core.plugins.core.tools.sandbox_reference import SandboxReference
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestSandboxReference(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.tool = SandboxReference()

    def test_prefix_lists_dotted_names_the_sandbox_exposes(self):
        result = self.tool.execute({"prefix": "frappe.db"})
        self.assertTrue(result["success"])
        self.assertIn("frappe.db.get_value", result["names"])
        self.assertEqual(result["names"], sorted(result["names"]))
        self.assertTrue(all(n.startswith("frappe.db.") for n in result["names"]))
        # Frappe leaves these out of the sandbox, so a script cannot call them
        self.assertNotIn("frappe.db.delete", result["names"])

    def test_limit_truncates(self):
        full = self.tool.execute({"prefix": "frappe.db", "limit": 500})
        result = self.tool.execute({"prefix": "frappe.db", "limit": 2})
        self.assertEqual(len(result["names"]), 2)
        self.assertTrue(result["truncated"])
        self.assertFalse(full["truncated"])

    def test_request_data_is_listed_by_name_not_by_key(self):
        # A request carries arbitrary form_dict keys; production reaches this on any API call
        frappe.local.form_dict["sentinel_key_7c1"] = "x"
        names = self.tool.execute({"limit": 500})["names"]
        self.assertIn("frappe.form_dict", names)
        self.assertFalse([n for n in names if "sentinel_key_7c1" in n])

    def test_builtins_and_public_underscore_names_listed_guards_hidden(self):
        names = self.tool.execute({"limit": 500})["names"]
        for expected in ("len", "str", "_", "_dict"):
            self.assertIn(expected, names)
        self.assertNotIn("_getattr_", names)
        self.assertFalse([n for n in names if n.startswith("__")])

    def test_form_dict_underscore_key_survives(self):
        # Browsers add a "_" cache-buster to the query string of every GET request
        frappe.local.form_dict["_"] = "1700000000"
        self.tool.execute({})
        self.assertEqual(frappe.local.form_dict.get("_"), "1700000000")

    def test_marks_names_blocked_in_doctype_events(self):
        result = self.tool.execute({"prefix": "frappe.db"})
        self.assertEqual(
            result["not_in_doctype_event"],
            ["frappe.db.add_index", "frappe.db.commit", "frappe.db.rollback"],
        )

    def test_rules_present(self):
        self.assertTrue(self.tool.execute({})["rules"])

    def test_refused_for_non_system_manager(self):
        # A user without the role is what calls the tool in production when it is exposed to them
        with patch.object(frappe, "get_roles", autospec=True, return_value=["Guest"]):
            with self.assertRaises(frappe.PermissionError):
                self.tool.check_permission()


class TestRecentErrors(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.tool = RecentErrors()
        self.marker = f"MARKER-{frappe.generate_hash(length=8)}"

    def _log(self, text: str):
        # Production reaches an Error Log row when a Server Script raises and Frappe logs it
        log = frappe.log_error(title="Server Script test", message=text)
        # Error Log is a MyISAM table, so the class rollback cannot undo this insert
        self.addCleanup(frappe.db.delete, "Error Log", {"name": log.name})

    def test_finds_logged_error_and_filters_by_contains(self):
        self._log(f"boom {self.marker}")
        self._log("something else")
        found = self.tool.execute({"contains": self.marker})
        self.assertTrue(found["success"])
        self.assertEqual(len(found["errors"]), 1)
        self.assertIn(self.marker, found["errors"][0]["error"])
        self.assertEqual(found["errors"][0]["title"], "Server Script test")
        self.assertEqual(self.tool.execute({"contains": "no-such-text-xyz"})["errors"], [])

    def test_contains_is_literal_not_a_pattern(self):
        self._log(f"axb {self.marker}")
        self.assertEqual(self.tool.execute({"contains": f"a_b {self.marker}"})["errors"], [])
        self.assertEqual(len(self.tool.execute({"contains": f"axb {self.marker}"})["errors"]), 1)
        self.assertEqual(self.tool.execute({"contains": "%"})["errors"], [])

    def test_excludes_rows_older_than_minutes(self):
        self._log(f"old {self.marker}")
        name = frappe.get_all("Error Log", filters=[["error", "like", f"%{self.marker}%"]], pluck="name")[0]
        # Rows age in production as time passes; creation is back-dated here to stand in for that
        frappe.db.set_value("Error Log", name, "creation", add_to_date(now_datetime(), minutes=-30))
        self.assertEqual(self.tool.execute({"minutes": 10, "contains": self.marker})["errors"], [])
        self.assertEqual(len(self.tool.execute({"minutes": 60, "contains": self.marker})["errors"]), 1)

    def test_error_trimmed_to_last_4000_characters(self):
        self._log("HEAD" + "x" * 5000 + self.marker)
        error = self.tool.execute({"contains": self.marker})["errors"][0]["error"]
        self.assertEqual(len(error), 4000)
        self.assertTrue(error.endswith(self.marker))

    def test_failed_job_listed_and_success_ignored(self):
        job_type = frappe.get_all("Scheduled Job Type", pluck="name", limit_page_length=1)[0]
        # The scheduler writes these rows when a job finishes; here they are inserted directly
        for status, details in (("Failed", f"trace {self.marker}"), ("Complete", f"fine {self.marker}")):
            frappe.get_doc(
                {
                    "doctype": "Scheduled Job Log",
                    "scheduled_job_type": job_type,
                    "status": status,
                    "details": details,
                }
            ).insert(ignore_permissions=True)
        jobs = self.tool.execute({"contains": self.marker})["failed_jobs"]
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["job"], job_type)

    def test_failed_job_matched_by_job_name(self):
        job_type = frappe.get_all("Scheduled Job Type", pluck="name", limit_page_length=1)[0]
        # The scheduler writes these rows when a job finishes; here one is inserted directly
        frappe.get_doc(
            {
                "doctype": "Scheduled Job Log",
                "scheduled_job_type": job_type,
                "status": "Failed",
                "details": "x",
            }
        ).insert(ignore_permissions=True)
        jobs = self.tool.execute({"contains": job_type})["failed_jobs"]
        self.assertTrue([j for j in jobs if j["job"] == job_type])

    def test_does_not_log_errors_itself(self):
        before = frappe.db.count("Error Log")
        self.tool.execute({"minutes": 5000, "limit": 500})
        self.assertEqual(frappe.db.count("Error Log"), before)

    def test_refused_for_non_system_manager(self):
        # A user without the role is what calls the tool in production when it is exposed to them
        with patch.object(frappe, "get_roles", autospec=True, return_value=["Guest"]):
            with self.assertRaises(frappe.PermissionError):
                self.tool.check_permission()
