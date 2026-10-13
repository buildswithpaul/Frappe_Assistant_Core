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

"""The Insights tools on a real Insights install: permissions, numbers, fallbacks, caps.

Skipped where Insights is not installed (CI). Fixtures are built through Insights'
own DocTypes as Administrator, like an author working in the Insights UI.
"""

import json
import unittest

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest

INSIGHTS_USER = "test_insights_reader@example.com"
NO_ROLE_USER = "test_insights_norole@example.com"


def _installed() -> bool:
    return "insights" in frappe.get_installed_apps()


class TestInsightsTools(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not _installed():
            raise unittest.SkipTest("Frappe Insights is not installed")
        frappe.set_user("Administrator")
        cls.ds = frappe.get_all("Insights Data Source v3", filters={"is_site_db": 1}, pluck="name")[0]
        cls.wb = frappe.get_doc({"doctype": "Insights Workbook", "title": "FAC tools test"}).insert()
        cls.base = cls._query("ToDo rows", "select name, status, priority from `tabToDo`")
        cls.fresh_chart = cls._chart("ToDos by status", cls.base.name, fresh=True)
        cls.raw_chart = cls._chart("Raw ToDos", cls.base.name, fresh=False)
        cls.broken = cls._chart(
            "Broken", cls._query("Broken", "select nope from `tabToDo`").name, fresh=False
        )
        cls.dashboard = frappe.get_doc(
            {
                "doctype": "Insights Dashboard v3",
                "title": "FAC tools dashboard",
                "workbook": cls.wb.name,
                "items": json.dumps(
                    [
                        {"type": "chart", "chart": cls.fresh_chart.name, "layout": {"x": 0, "y": 0}},
                        {"type": "chart", "chart": cls.raw_chart.name, "layout": {"x": 10, "y": 0}},
                        {"type": "chart", "chart": cls.broken.name, "layout": {"x": 0, "y": 8}},
                        {
                            "type": "filter",
                            "filter_name": "Status",
                            "filter_type": "String",
                            "links": {cls.fresh_chart.name: f"`{cls.base.name}`.`status`"},
                            "default_operator": "=",
                            "default_value": "Open",
                            "layout": {"x": 0, "y": 16},
                        },
                    ]
                ),
            }
        ).insert()
        for email, roles in ((INSIGHTS_USER, ["Insights User"]), (NO_ROLE_USER, ["Desk User"])):
            if not frappe.db.exists("User", email):
                frappe.get_doc(
                    {
                        "doctype": "User",
                        "email": email,
                        "first_name": "Insights",
                        "user_type": "System User",
                        "send_welcome_email": 0,
                        "roles": [{"role": r} for r in roles if frappe.db.exists("Role", r)],
                    }
                ).insert(ignore_permissions=True)

    @classmethod
    def _query(cls, title, sql):
        return frappe.get_doc(
            {
                "doctype": "Insights Query v3",
                "title": title,
                "workbook": cls.wb.name,
                "is_native_query": 1,
                "use_live_connection": 1,
                "operations": json.dumps([{"type": "sql", "data_source": cls.ds, "raw_sql": sql}]),
            }
        ).insert()

    @classmethod
    def _chart(cls, title, query, fresh):
        config = {
            "x_axis": {
                "dimension": {"dimension_name": "Status", "column_name": "status", "data_type": "String"}
            },
            "y_axis": {
                "series": [
                    {
                        "measure": {
                            "measure_name": "ToDos",
                            "column_name": "name",
                            "data_type": "Integer",
                            "aggregation": "count",
                        }
                    }
                ]
            },
        }
        chart = frappe.get_doc(
            {
                "doctype": "Insights Chart v3",
                "title": title,
                "workbook": cls.wb.name,
                "query": query,
                "chart_type": "Bar",
                "config": json.dumps(config),
            }
        ).insert()
        if fresh:
            # Production: the chart editor saves these operations into data_query when its author
            # views the chart (confirmed live in Task 1 of the plan).
            dq = frappe.get_doc("Insights Query v3", chart.data_query)
            dq.operations = json.dumps(cls._data_query_operations(query))
            dq.use_live_connection = 1
            dq.save()
        return chart

    @classmethod
    def _data_query_operations(cls, query):
        return [
            {"type": "source", "table": {"type": "query", "workbook": cls.wb.name, "query_name": query}},
            {
                "type": "summarize",
                "measures": [
                    {
                        "measure_name": "todos",
                        "column_name": "name",
                        "data_type": "Integer",
                        "aggregation": "count",
                    }
                ],
                "dimensions": [{"dimension_name": "status", "column_name": "status", "data_type": "String"}],
            },
        ]

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _tool(self, name):
        module = __import__(f"frappe_assistant_core.plugins.insights.tools.{name}", fromlist=["*"])
        cls = next(
            v
            for v in vars(module).values()
            if isinstance(v, type) and getattr(v, "__module__", "") == module.__name__
        )
        return cls()

    def _dashboard(self, **args):
        return self._tool("get_insights_dashboard").execute({"name": self.dashboard.name, **args})

    def test_the_owner_reads_the_dashboard_with_its_default_filter(self):
        out = self._dashboard()
        self.assertTrue(out["success"], out)
        self.assertEqual(out["filters"][0]["source"], "default")
        fresh = next(c for c in out["charts"] if c["name"] == self.fresh_chart.name)
        self.assertEqual(fresh["source"], "chart")
        # A pivot's columns are its dimension values, so the measure's name is gone from the rows;
        # every chart says what its numbers measure (live: a table's sums read as "order value").
        self.assertEqual(fresh["config_summary"]["measures"][0]["aggregation"], "count")
        self.assertEqual({r["status"] for r in fresh["rows"]}, {"Open"} if fresh["rows"] else set())

    def test_an_override_changes_the_numbers(self):
        out = self._dashboard(filters=[{"filter": "Status", "operator": "=", "value": "Closed"}])
        fresh = next(c for c in out["charts"] if c["name"] == self.fresh_chart.name)
        self.assertTrue(all(r["status"] == "Closed" for r in fresh["rows"]))
        self.assertEqual(out["filters"][0]["source"], "override")

    def test_a_chart_edited_after_its_data_query_reads_raw(self):
        out = self._dashboard()
        raw = next(c for c in out["charts"] if c["name"] == self.raw_chart.name)
        self.assertEqual(raw["source"], "raw")
        self.assertEqual(raw["config_summary"]["measures"][0]["aggregation"], "count")
        self.assertIn("aggregate", raw["note"].lower())

    def test_one_unreadable_chart_does_not_fail_the_dashboard(self):
        out = self._dashboard()
        broken = next(c for c in out["charts"] if c["name"] == self.broken.name)
        self.assertIn("error", broken)
        self.assertNotIn("error", next(c for c in out["charts"] if c["name"] == self.fresh_chart.name))

    def test_rows_are_capped_and_truncation_reported(self):
        out = self._dashboard(max_rows_per_chart=1)
        raw = next(c for c in out["charts"] if c["name"] == self.raw_chart.name)
        self.assertLessEqual(len(raw["rows"]), 1)
        if frappe.db.count("ToDo") > 1:
            self.assertTrue(raw["truncated"])

    def test_an_insights_user_without_a_share_gets_the_not_found_answer(self):
        frappe.set_user(INSIGHTS_USER)
        out = self._dashboard()
        missing = self._tool("get_insights_dashboard").execute({"name": "no-such-dashboard"})
        self.assertFalse(out["success"])
        self.assertEqual(
            out["error"].replace(self.dashboard.name, "X"), missing["error"].replace("no-such-dashboard", "X")
        )

    def test_sharing_the_workbook_grants_the_dashboard(self):
        frappe.share.add("Insights Workbook", self.wb.name, INSIGHTS_USER, read=1, notify=0)
        frappe.set_user(INSIGHTS_USER)
        self.assertTrue(self._dashboard()["success"])

    def test_a_user_without_an_insights_role_is_refused(self):
        frappe.set_user(NO_ROLE_USER)
        for tool, args in (
            ("list_insights_dashboards", {}),
            ("get_insights_dashboard", {"name": self.dashboard.name}),
            ("get_insights_chart", {"name": self.fresh_chart.name}),
        ):
            out = self._tool(tool).execute(args)
            self.assertEqual(
                out, {"success": False, "error": "You don't have access to Frappe Insights."}, tool
            )

    def test_list_shows_only_readable_dashboards(self):
        names = [
            d["name"]
            for d in self._tool("list_insights_dashboards").execute({"search": "FAC tools"})["dashboards"]
        ]
        self.assertIn(self.dashboard.name, names)
        frappe.set_user(INSIGHTS_USER)
        names = [
            d["name"]
            for d in self._tool("list_insights_dashboards").execute({"search": "FAC tools"})["dashboards"]
        ]
        self.assertNotIn(self.dashboard.name, names)

    def test_a_chart_read_with_its_dashboard_applies_the_dashboard_filters(self):
        out = self._tool("get_insights_chart").execute(
            {"name": self.fresh_chart.name, "dashboard": self.dashboard.name}
        )
        self.assertTrue(out["success"], out)
        self.assertTrue(all(r["status"] == "Open" for r in out["chart"]["rows"]))

    def test_unknown_filter_names_are_reported(self):
        out = self._dashboard(filters=[{"filter": "Region", "operator": "=", "value": "EU"}])
        self.assertEqual(out["unknown_filters"], ["Region"])
