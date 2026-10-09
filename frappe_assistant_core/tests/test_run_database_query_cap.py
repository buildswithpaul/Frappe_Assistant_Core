# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""run_database_query never returns more than 1000 rows.

An explicit LIMIT used to switch the cap off, and so did any query that
merely contained the letters "limit" (a credit_limit column). tabDocField has
thousands of rows on every site, so these run against the real database.
"""

import frappe

from frappe_assistant_core.plugins.data_science.tools.run_database_query import (
    HARD_ROW_CAP,
    QueryAndAnalyse,
    _cap_query,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestRunDatabaseQueryCap(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; isolated transaction
        frappe.set_user("Administrator")
        self.tool = QueryAndAnalyse()
        total = frappe.db.count("DocField")
        if total <= HARD_ROW_CAP:
            self.skipTest(f"needs more than {HARD_ROW_CAP} DocField rows, site has {total}")

    def _run(self, query, **extra):
        result = self.tool.execute({"query": query, "validate_query": False, **extra})
        self.assertTrue(result["success"], result.get("error"))
        return result

    def test_explicit_large_limit_is_capped(self):
        result = self._run("SELECT name FROM `tabDocField` LIMIT 5000")
        self.assertEqual(result["rows_returned"], HARD_ROW_CAP)
        self.assertTrue(result["truncated"])

    def test_offset_form_is_capped(self):
        result = self._run("SELECT name FROM `tabDocField` LIMIT 10, 5000")
        self.assertEqual(result["rows_returned"], HARD_ROW_CAP)

    def test_a_column_named_like_limit_still_gets_the_default_cap(self):
        result = self._run("SELECT name, fieldname AS credit_limit FROM `tabDocField`")
        self.assertEqual(result["rows_returned"], 100)
        self.assertTrue(result["truncated"])

    def test_query_ending_in_a_line_comment_still_gets_the_cap(self):
        result = self._run("SELECT name FROM `tabDocField` -- trailing comment")
        self.assertEqual(result["rows_returned"], 100)
        self.assertTrue(result["truncated"])

    def test_clamped_limit_before_a_line_comment_is_still_capped(self):
        result = self._run("SELECT name FROM `tabDocField` LIMIT 5000 -- trailing comment")
        self.assertEqual(result["rows_returned"], HARD_ROW_CAP)
        self.assertTrue(result["truncated"])

    def test_small_explicit_limit_and_order_are_kept(self):
        result = self._run("SELECT name FROM `tabDocType` ORDER BY name ASC LIMIT 3;")
        names = [row["name"] for row in result["data"]]
        self.assertEqual(len(names), 3)
        self.assertEqual(names, sorted(names))
        self.assertFalse(result["truncated"])


class TestCapQuery(BaseAssistantTest):
    def test_trailing_limit_over_the_cap_is_clamped(self):
        self.assertEqual(_cap_query("SELECT 1 LIMIT 99999", 100), ("SELECT 1 LIMIT 1001", 1000))

    def test_limit_with_offset_keyword(self):
        self.assertEqual(
            _cap_query("SELECT 1 LIMIT 5000 OFFSET 7", 100),
            ("SELECT 1 LIMIT 1001 OFFSET 7", 1000),
        )

    def test_limit_inside_a_subquery_still_gets_an_outer_cap(self):
        query = "SELECT * FROM (SELECT name FROM `tabDocField` LIMIT 5000) t"
        self.assertEqual(_cap_query(query, 50), (f"{query}\nLIMIT 51", 50))

    def test_appended_limit_starts_a_new_line_after_a_line_comment(self):
        self.assertEqual(
            _cap_query("SELECT name FROM `tabDocField` -- trailing comment", 100),
            ("SELECT name FROM `tabDocField` -- trailing comment\nLIMIT 101", 100),
        )

    def test_limit_inside_a_comment_is_not_a_limit(self):
        self.assertEqual(
            _cap_query("SELECT 1 -- LIMIT 5000", 100), ("SELECT 1 -- LIMIT 5000\nLIMIT 101", 100)
        )

    def test_limit_inside_a_string_is_not_a_limit(self):
        self.assertEqual(
            _cap_query("SELECT 'LIMIT 5000' AS note", 100),
            ("SELECT 'LIMIT 5000' AS note\nLIMIT 101", 100),
        )

    def test_credit_limit_column_does_not_count_as_a_limit(self):
        self.assertEqual(
            _cap_query("SELECT credit_limit FROM `tabCustomer`", 100),
            ("SELECT credit_limit FROM `tabCustomer`\nLIMIT 101", 100),
        )
