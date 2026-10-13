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
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""The pure parts of reading an Insights chart: filters, freshness, shaping and caps.

They mirror Insights 3.14.2's dashboard page (frontend/src2/dashboard/dashboard.ts
getAdhocFilters, query/components/filter_utils.ts isFilterValid) and run without Insights.
"""

import json
from datetime import datetime, timedelta

from frappe_assistant_core.plugins.insights.chart_data import (
    MAX_DASHBOARD_ROWS,
    adhoc_filters_for,
    chart_names,
    config_summary,
    dashboard_filters,
    is_fresh,
    notes,
    resolve_filters,
    row_budget,
    shape_result,
    unknown_overrides,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest

ITEMS = [
    {"type": "chart", "chart": "c-second", "layout": {"x": 10, "y": 0}},
    {"type": "chart", "chart": "c-first", "layout": {"x": 0, "y": 0}},
    {"type": "chart", "chart": "c-below", "layout": {"x": 0, "y": 8}},
    {
        "type": "filter",
        "filter_name": "Status",
        "filter_type": "String",
        "links": {"c-first": "`q-base`.`status`"},
        "default_operator": "=",
        "default_value": "Open",
        "layout": {"x": 0, "y": 16},
    },
    {
        "type": "filter",
        "filter_name": "Priority",
        "filter_type": "String",
        "links": {"c-first": "`q-base`.`priority`", "c-second": "`q-other`.`priority`"},
        "layout": {"x": 4, "y": 16},
    },
    {"type": "text", "text": "<p>Revenue &amp; <b>margin</b></p>", "layout": {"x": 0, "y": 17}},
]


class TestInsightsChartData(BaseAssistantTest):
    def test_filters_take_their_default_only_when_both_parts_are_set(self):
        filters = {f["name"]: f for f in dashboard_filters(ITEMS)}
        self.assertEqual(filters["Status"]["default"], ("=", "Open"))
        self.assertIsNone(filters["Priority"]["default"])

    def test_a_filter_reaches_only_the_charts_it_links(self):
        resolved = resolve_filters(
            dashboard_filters(ITEMS), [{"filter": "Priority", "operator": "=", "value": "High"}]
        )
        self.assertEqual(
            adhoc_filters_for("c-first", resolved),
            {
                "q-base": {
                    "type": "filter_group",
                    "logical_operator": "And",
                    "filters": [
                        {
                            "column": {"type": "column", "column_name": "status"},
                            "operator": "=",
                            "value": "Open",
                        },
                        {
                            "column": {"type": "column", "column_name": "priority"},
                            "operator": "=",
                            "value": "High",
                        },
                    ],
                }
            },
        )
        self.assertEqual(
            adhoc_filters_for("c-second", resolved)["q-other"]["filters"],
            [{"column": {"type": "column", "column_name": "priority"}, "operator": "=", "value": "High"}],
        )
        self.assertEqual(adhoc_filters_for("c-below", resolved), {})

    def test_an_override_replaces_the_default_and_says_so(self):
        resolved = {
            f["name"]: f
            for f in resolve_filters(
                dashboard_filters(ITEMS), [{"filter": "Status", "operator": "=", "value": "Closed"}]
            )
        }
        self.assertEqual((resolved["Status"]["value"], resolved["Status"]["source"]), ("Closed", "override"))
        self.assertEqual(resolved["Priority"]["source"], "none")

    def test_an_invalid_filter_applies_nothing(self):
        resolved = {
            f["name"]: f
            for f in resolve_filters(
                dashboard_filters(ITEMS), [{"filter": "Status", "operator": "=", "value": ""}]
            )
        }
        self.assertEqual(resolved["Status"]["source"], "none")
        self.assertEqual(adhoc_filters_for("c-first", list(resolved.values())), {})

    def test_valueless_operators_need_no_value(self):
        resolved = resolve_filters(dashboard_filters(ITEMS), [{"filter": "Priority", "operator": "is_set"}])
        self.assertEqual({f["name"]: f["source"] for f in resolved}["Priority"], "override")

    def test_number_between_needs_two_numbers(self):
        filters = [{"name": "Amount", "type": "Number", "links": {"c": "`q`.`amount`"}, "default": None}]
        good = resolve_filters(filters, [{"filter": "Amount", "operator": "between", "value": [1, 9]}])
        bad = resolve_filters(filters, [{"filter": "Amount", "operator": "between", "value": [1, "x"]}])
        self.assertEqual((good[0]["source"], bad[0]["source"]), ("override", "none"))

    def test_unknown_override_names_are_reported(self):
        self.assertEqual(
            unknown_overrides(dashboard_filters(ITEMS), [{"filter": "Region", "value": "EU"}]), ["Region"]
        )

    def test_charts_come_in_reading_order(self):
        self.assertEqual(chart_names(ITEMS), ["c-first", "c-second", "c-below"])
        self.assertEqual(chart_names(json.dumps(ITEMS)), ["c-first", "c-second", "c-below"])

    def test_text_blocks_become_short_plain_notes(self):
        self.assertEqual(notes(ITEMS), ["Revenue & margin"])
        self.assertEqual(len(notes([{"type": "text", "text": "x" * 900}])[0]), 501)

    def test_a_data_query_is_fresh_only_with_operations_and_saved_after_the_chart(self):
        now = datetime(2026, 10, 13, 12, 0)
        ops = json.dumps([{"type": "source"}])
        self.assertTrue(is_fresh(now, now, ops))
        self.assertFalse(is_fresh(now - timedelta(seconds=1), now, ops))
        self.assertFalse(is_fresh(now, now, "[]"))
        self.assertFalse(is_fresh(None, now, ops))

    def test_config_summary_finds_dimensions_and_measures_in_any_chart_type(self):
        config = {
            "x_axis": {
                "dimension": {"dimension_name": "Status", "column_name": "status", "data_type": "String"}
            },
            "y_axis": {
                "series": [
                    {"measure": {"measure_name": "Count", "column_name": "name", "aggregation": "count"}}
                ]
            },
            "limit": 50,
        }
        self.assertEqual(
            config_summary("Bar", json.dumps(config)),
            {
                "chart_type": "Bar",
                "dimensions": [{"column": "status", "label": "Status", "granularity": None}],
                "measures": [{"column": "name", "aggregation": "count", "label": "Count"}],
                "limit": 50,
            },
        )

    def test_shape_cuts_long_cells_and_drops_hidden_columns(self):
        result = {
            "columns": [
                {"name": "a", "type": "String"},
                {"name": "secret__currency", "type": "String", "hidden": True},
            ],
            "rows": [{"a": "x" * 300, "secret__currency": "INR"}, {"a": "y", "secret__currency": "INR"}],
        }
        shaped = shape_result(result, max_rows=1)
        self.assertEqual(shaped["columns"], [{"name": "a", "type": "String"}])
        self.assertEqual(shaped["rows"], [{"a": "x" * 200 + "…"}])
        self.assertTrue(shaped["truncated"])

    def test_row_budget_never_exceeds_the_dashboard_cap(self):
        self.assertEqual(row_budget(50, 0), 50)
        self.assertEqual(row_budget(50, MAX_DASHBOARD_ROWS - 10), 10)
        self.assertEqual(row_budget(50, MAX_DASHBOARD_ROWS), 0)


class TestInsightsToolCategory(BaseAssistantTest):
    def test_the_insights_tools_are_read_only(self):
        # Read-only tools run without an approval card; read_write would stop every dashboard question.
        from frappe_assistant_core.utils.tool_category_detector import detect_tool_category

        for module, cls in (
            ("list_insights_dashboards", "ListInsightsDashboards"),
            ("get_insights_dashboard", "GetInsightsDashboard"),
            ("get_insights_chart", "GetInsightsChart"),
        ):
            tool = getattr(
                __import__(f"frappe_assistant_core.plugins.insights.tools.{module}", fromlist=[cls]), cls
            )()
            self.assertEqual(detect_tool_category(tool), "read_only", module)
