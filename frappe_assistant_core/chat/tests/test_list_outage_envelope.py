from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api import marketplace, workflows
from frappe_assistant_core.tests.base_test import BaseAssistantTest

CLIENT = "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client"


class _DownClient:
    """Production reaches the except branch when the SDK call itself raises —
    FAC Cloud unreachable or timing out. Every method raises the way the SDK does."""

    def __getattr__(self, name):
        def _raise(*args, **kwargs):
            raise ConnectionError("FAC Cloud unreachable")

        return _raise


class TestListOutageEnvelope(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def test_list_workflows_reports_an_outage(self):
        with patch(CLIENT, return_value=_DownClient()):
            result = workflows.list_workflows()
        self.assertEqual(result["workflows"], [])
        self.assertTrue(result.get("error"))

    def test_list_workflow_runs_reports_an_outage(self):
        with patch(CLIENT, return_value=_DownClient()):
            result = workflows.list_workflow_runs(workflow_name="WF-00001")
        self.assertEqual(result["runs"], [])
        self.assertTrue(result.get("error"))

    def test_list_listings_reports_an_outage(self):
        with (
            patch.object(marketplace, "_marketplace_enabled", return_value=True),
            patch(CLIENT, return_value=_DownClient()),
            patch.object(marketplace, "_ar_user_id", return_value="admin@example.com"),
        ):
            result = marketplace.list_listings(listing_type="Workflow")
        self.assertEqual(result["listings"], [])
        self.assertTrue(result.get("error"))

    def test_not_connected_is_not_an_outage(self):
        """Regression guard: pins unchanged behaviour, green before the fix."""
        with patch(CLIENT, return_value=None):
            result = workflows.list_workflows()
        self.assertNotIn("error", result)

    def test_list_listings_not_connected_is_not_an_outage(self):
        # A site that never connected to FAC Cloud has get_fac_cloud_client() return None.
        with (
            patch.object(marketplace, "_marketplace_enabled", return_value=True),
            patch(CLIENT, return_value=None),
        ):
            result = marketplace.list_listings(listing_type="Workflow")
        self.assertEqual(result["listings"], [])
        self.assertNotIn("error", result)
