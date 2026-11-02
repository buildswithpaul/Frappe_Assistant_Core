# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Rows from frappe.get_all / frappe.db.sql are frappe._dict, which answers any attribute with None:
pandas reads ``ndim`` off them and takes them for an array ("invalid __array_struct__", GitHub #379).
The tools that build a DataFrame from such rows pass plain dicts."""

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest

ROWS = [frappe._dict(status="Open", amount=10), frappe._dict(status="Closed", amount=5)]


class TestFrappeRowsDataFrame(BaseAssistantTest):
    def test_run_database_query_analyses_frappe_rows(self):
        from frappe_assistant_core.plugins.data_science.tools.run_database_query import QueryAndAnalyse

        analysis = QueryAndAnalyse()._analyze_results(list(ROWS), "basic")
        self.assertNotIn("error", analysis, analysis)
        self.assertEqual(analysis["basic_info"]["total_rows"], 2)
        self.assertEqual(analysis["basic_info"]["total_columns"], 2)

    def test_chart_suggestions_read_frappe_rows(self):
        from frappe_assistant_core.plugins.visualization.utils.chart_suggestions import ChartSuggestionEngine

        fields = ChartSuggestionEngine()._analyze_fields("ToDo", ["status", "amount"], list(ROWS))
        self.assertEqual(set(fields), {"status", "amount"})
