"""Tests for the visualization tools' permission handling.

Both `create_dashboard` and `create_dashboard_chart` returned `str(e)` for a
document-level permission denial. Frappe raises that as a bare
`frappe.PermissionError` and keeps the reason in `frappe.flags.error_message`, so
the model received an empty error and retried.
"""

from unittest.mock import patch

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestVisualizationToolPermissionDenials(BaseAssistantTest):
    """A denied Dashboard / Dashboard Chart create said nothing at all.

    Both tools returned `str(e)` for a bare `frappe.PermissionError`, so the model
    received an empty reason and retried.
    """

    def setUp(self):
        super().setUp()
        frappe.flags.pop("error_message", None)
        self.addCleanup(lambda: frappe.flags.pop("error_message", None))
        log_error = patch("frappe.log_error")
        self.log_error = log_error.start()
        self.addCleanup(log_error.stop)

    def _refuse_insert(self, ptype):
        refusal = frappe.new_doc("ToDo")
        return patch(
            "frappe.model.document.Document.insert",
            side_effect=lambda *a, **k: refusal.raise_no_permission_to(ptype),
        )

    def test_dashboard_chart_create_says_why_it_was_refused(self):
        from frappe_assistant_core.plugins.visualization.tools.create_dashboard_chart import (
            CreateDashboardChart,
        )

        with self._refuse_insert("create"):
            result = CreateDashboardChart().execute(
                {
                    "chart_name": "perm denied chart",
                    "chart_type": "Bar",
                    "doctype": "ToDo",
                    "aggregate_function": "Count",
                    "based_on": "status",
                }
            )

        self.assertFalse(result.get("success"), result)
        self.assertEqual(result.get("error_type"), "permission_error")
        self.assertTrue(result.get("error"), result)
        self.assertNotIn("<", result["error"])

    def test_dashboard_create_says_why_it_was_refused(self):
        from frappe_assistant_core.plugins.visualization.tools.create_dashboard import (
            CreateDashboard,
        )

        with self._refuse_insert("create"):
            result = CreateDashboard()._create_frappe_dashboard(
                dashboard_name="perm denied dashboard",
                chart_links=[],
                share_with=[],
                mobile_optimized=False,
                auto_refresh=False,
            )

        self.assertFalse(result.get("success"), result)
        self.assertEqual(result.get("error_type"), "permission_error")
        self.assertTrue(result.get("error"), result)
        self.assertNotIn("<", result["error"])
