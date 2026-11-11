# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
#34407: the model sees grouped causes, not every row.

- ERPNext's refusals quote the value they refused, so rows are grouped by the message with their
  own values read as "…", and the group lists the values.
- An import's failed rows come back capped, as many causes as the dry run shows.
- A master named by a series is suggested by its title.
- What a check costs, not only its row count, decides whether it runs in the background.
"""

import unittest
from unittest.mock import patch

import frappe

from frappe_assistant_core.tests import test_import_run as run_tests
from frappe_assistant_core.utils import import_dry_run, import_failures, import_fixes, import_run

LEAD_MAPPING = {"First Name": "first_name", "Email": "email_id"}


class TestTheMessagePattern(unittest.TestCase):
    def test_the_rows_own_values_and_row_numbers_read_as_quoted(self):
        message, values = import_dry_run.message_pattern(
            "Row #3: Acme Traders is closed", ["Acme Traders", "Retail", "3"]
        )

        self.assertEqual((message, values), ("Row #…: … is closed", ["Acme Traders"]))

    def test_a_value_inside_another_word_or_too_short_is_left_alone(self):
        message, values = import_dry_run.message_pattern("Companyless rows are refused", ["Company", "No"])

        self.assertEqual((message, values), ("Companyless rows are refused", []))


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Lead and Customer")
class TestFailureGroups(run_tests.ImportRunCase):
    def _lead_session(self, rows):
        lines = [",".join(LEAD_MAPPING)] + [",".join(row) for row in rows]
        file_doc = self._file("leads.csv", ("\n".join(lines) + "\n").encode())
        session = self._run("start_import_session", {"file_id": file_doc.name})["result"]["session_id"]
        mapped = self._run(
            "set_column_mapping", {"session": session, "mapping": LEAD_MAPPING, "doctype": "Lead"}
        )
        self.assertTrue(mapped["success"], mapped)
        return session

    def test_refusals_quoting_their_values_are_one_group_that_lists_them(self):
        # ERPNext refuses a bad email address naming it: "<value> is not a valid Email Address".
        bad = [f"not-an-email-{i}-{self.tag}" for i in range(3)]
        session = self._lead_session([[f"Lead {i} {self.tag}", value] for i, value in enumerate(bad)])

        check = self._run("dry_run_import", {"session": session})["result"]

        rejected = [g for g in check["groups"] if g["cause"] == import_dry_run.CAUSE_REJECTED]
        self.assertEqual(len(rejected), 1, check["groups"])
        self.assertEqual((rejected[0]["count"], sorted(rejected[0]["values"])), (3, sorted(bad)))
        self.assertNotIn(bad[0], rejected[0]["message"])
        self.assertIn(bad[0], rejected[0]["explanation"])

    def test_an_imports_refusals_are_grouped_the_same_way(self):
        file_rows = [["Email"], ["bad-1@"], ["bad-2@"]]
        logs = [
            frappe._dict(
                row_indexes=f"[{n}]", messages=f'[{{"message": "{v} is not a valid Email Address"}}]'
            )
            for n, v in ((2, "bad-1@"), (3, "bad-2@"))
        ]

        groups = import_failures.failure_groups(self._doc(self._ready_session()[0]), logs, file_rows)

        self.assertEqual(len(groups), 1, groups)
        self.assertEqual((groups[0]["count"], groups[0]["values"]), (2, ["bad-1@", "bad-2@"]))
        self.assertEqual(groups[0]["reason"], "… is not a valid Email Address")

    def test_only_the_groups_shown_are_explained(self):
        logs = [
            frappe._dict(row_indexes=f"[{n}]", messages=f'[{{"message": "cause {n}"}}]') for n in range(2, 6)
        ]

        groups = import_failures.failure_groups(self._doc(self._ready_session()[0]), logs, explained=2)

        self.assertEqual([("explanation" in g) for g in groups], [True, True, False, False])

    def test_an_imports_failed_rows_are_capped_and_the_rest_counted(self):
        session, checked = self._ready_session()
        data_import = self._import(session, checked)["result"]["data_import"]
        many = [
            {"reason": f"cause {n}", "error": "ValidationError", "count": 1, "rows": [n], "explanation": "x"}
            for n in range(import_fixes.GROUPS_SHOWN + 5)
        ]

        with patch.object(import_failures, "failure_groups", autospec=True, return_value=many):
            result = import_run.result_of(self._doc(session), data_import)

        self.assertEqual(len(result["failed_rows"]), import_fixes.GROUPS_SHOWN)
        self.assertEqual((result["failed_groups_total"], result["failed_groups_not_shown"]), (len(many), 5))
        self.assertIn(f"{len(many) - import_run.FAILED_GROUPS_SHOWN} other causes", result["message"])

    def test_a_master_named_by_a_series_is_suggested_by_its_title(self):
        # A Lead is named by its naming series (CRM-LEAD-2026-00001); the user knows its name.
        lead = frappe.get_doc({"doctype": "Lead", "first_name": f"Acme Trading Co {self.tag}"}).insert()
        self.assertNotIn("Acme", lead.name)

        self.assertIn(lead.name, import_fixes.closest_names("Lead", f"Acme Trading {self.tag}"))

    def test_what_a_check_costs_decides_the_background(self):
        def session(doctype, rows, submit=0):
            return frappe._dict(
                target_doctype=doctype,
                submit_after_import=submit,
                sheet=None,
                sheets=frappe.as_json([{"name": None, "columns": ["A"], "row_count": rows}]),
                template_options="{}",
            )

        self.assertEqual(import_dry_run.check_cost(session("Customer", 300)), 300)
        self.assertEqual(import_dry_run.check_cost(session("Sales Invoice", 300)), 600)
        self.assertEqual(import_dry_run.check_cost(session("Sales Invoice", 300, submit=1)), 900)
        # 300 invoices are under the row limit, but cost more than it: checked in the background
        self.assertLess(300, import_dry_run.BACKGROUND_ROWS)
        self.assertGreater(
            import_dry_run.check_cost(session("Sales Invoice", 300)), import_dry_run.BACKGROUND_ROWS
        )
