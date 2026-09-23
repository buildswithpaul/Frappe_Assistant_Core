# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Read-only viewer policy on the workflow passthroughs.

Non-admins may READ workflows and runs; every mutation needs System Manager.
`cancel_workflow_run` shipped with no check at all — any authenticated user
could kill any tenant run — so it is pinned here first.
"""

from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api import workflows
from frappe_assistant_core.tests.base_test import BaseAssistantTest

NON_ADMIN = "workflow_viewer@example.com"


class TestWorkflowPermissions(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self._make_non_admin(NON_ADMIN)
        self.addCleanup(frappe.set_user, "Administrator")

    def _make_non_admin(self, email):
        if not frappe.db.exists("User", email):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": email,
                    "first_name": "Viewer",
                    "enabled": 1,
                    "send_welcome_email": 0,
                }
            ).insert(ignore_permissions=True)
        user = frappe.get_doc("User", email)
        user.set("roles", [])
        user.save(ignore_permissions=True)
        return email

    # --- mutations -------------------------------------------------------

    def test_non_admin_cannot_cancel_a_run(self):
        frappe.set_user(NON_ADMIN)
        with self.assertRaises(frappe.PermissionError):
            workflows.cancel_workflow_run(run_name="WFR-00001")

    def test_non_admin_cannot_mutate(self):
        frappe.set_user(NON_ADMIN)

        with self.assertRaises(frappe.PermissionError):
            workflows.update_workflow(name="WF-00001", description="x")
        with self.assertRaises(frappe.PermissionError):
            workflows.create_workflow(workflow_name="nope")
        with self.assertRaises(frappe.PermissionError):
            workflows.delete_workflow(name="WF-00001")
        with self.assertRaises(frappe.PermissionError):
            workflows.execute_workflow(name="WF-00001")
        with self.assertRaises(frappe.PermissionError):
            workflows.set_workflow_schedule(name="WF-00001", cron_expression="0 * * * *")
        with self.assertRaises(frappe.PermissionError):
            workflows.test_workflow_node(node_json='{"id": "n1", "type": "agent"}')
        with self.assertRaises(frappe.PermissionError):
            workflows.run_workflow_node(name="WF-00001", node_id="n1")

    # --- reads -----------------------------------------------------------

    def test_non_admin_may_read(self):
        """A viewer reaches the client, so the failure is "not connected", not 403."""
        frappe.set_user(NON_ADMIN)

        with patch.object(workflows, "_ar_user_id", return_value=NON_ADMIN), patch(
            "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client",
            return_value=None,
        ):
            self.assertEqual(workflows.list_workflows()["workflows"], [])
            self.assertEqual(workflows.list_workflow_runs()["runs"], [])

            with self.assertRaises(frappe.ValidationError):
                workflows.get_workflow(name="WF-00001")
            with self.assertRaises(frappe.ValidationError):
                workflows.get_workflow_run(run_name="WFR-00001")

    def test_guest_cannot_read(self):
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            workflows.list_workflows()
        with self.assertRaises(frappe.PermissionError):
            workflows.get_workflow(name="WF-00001")
        with self.assertRaises(frappe.PermissionError):
            workflows.get_workflow_run(run_name="WFR-00001")
        with self.assertRaises(frappe.PermissionError):
            workflows.list_user_tools()

    def test_admin_passes_every_gate(self):
        frappe.set_user("Administrator")
        with patch(
            "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client",
            return_value=None,
        ):
            # No client → the endpoint's own "not connected" error, never a 403.
            with self.assertRaises(frappe.ValidationError):
                workflows.cancel_workflow_run(run_name="")
            self.assertEqual(workflows.list_workflows()["workflows"], [])


class TestRunNodeIdentity(BaseAssistantTest):
    """run_workflow_node's user_id OVERRIDES the workflow's runtime user."""

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def test_user_id_is_normalised_to_the_ar_identity(self):
        client = _RecordingClient()
        with patch(
            "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client",
            return_value=client,
        ), patch.object(workflows, "_ar_user_id", return_value="owner@example.com"):
            workflows.run_workflow_node(name="WF-00001", node_id="n1", user_id="Administrator")

        self.assertEqual(client.calls[0]["user_id"], "owner@example.com")

    def test_absent_user_id_stays_absent(self):
        client = _RecordingClient()
        with patch(
            "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client",
            return_value=client,
        ):
            workflows.run_workflow_node(name="WF-00001", node_id="n1")

        self.assertIsNone(client.calls[0]["user_id"])


class _RecordingClient:
    def __init__(self):
        self.calls = []

    def run_workflow_node(self, **kwargs):
        self.calls.append(kwargs)
        return {"status": "ok"}


class TestToolDiscoveryFailureSurfaces(BaseAssistantTest):
    """An expired token must reach the SPA as a reconnect CTA, not "no tools"."""

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def _call_with(self, payload):
        client = _StubToolClient(payload)
        with patch(
            "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client",
            return_value=client,
        ), patch.object(workflows, "_ar_user_id", return_value="owner@example.com"):
            return workflows.list_user_tools()

    def test_per_server_auth_failure_is_a_failure(self):
        result = self._call_with(
            {
                "tools": [],
                "servers_queried": [],
                "errors": [
                    {
                        "server": "Main Frappe Site",
                        "error": "Refresh token expired",
                        "error_code": "REFRESH_TOKEN_EXPIRED",
                    }
                ],
            }
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "REFRESH_TOKEN_EXPIRED")
        self.assertEqual(result["action_required"], "re_authorize")

    def test_tenant_level_error_is_a_failure(self):
        result = self._call_with(
            {
                "error": "No MCP servers configured for this user.",
                "error_code": "NO_MCP_SERVERS",
                "action_required": "add_mcp_server",
            }
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["action_required"], "add_mcp_server")

    def test_real_tools_still_succeed(self):
        result = self._call_with(
            {
                "tools": [{"name": "site:run_report", "original_name": "run_report"}],
                "servers_queried": ["site"],
                "errors": None,
            }
        )

        self.assertTrue(result["success"])
        self.assertEqual(len(result["tools"]), 1)

    def test_partial_success_keeps_the_tools_and_the_errors(self):
        result = self._call_with(
            {
                "tools": [{"name": "site:run_report"}],
                "servers_queried": ["site"],
                "errors": [{"server": "other", "error": "boom"}],
            }
        )

        self.assertTrue(result["success"])
        self.assertEqual(len(result["errors"]), 1)


class _StubToolClient:
    def __init__(self, payload):
        self._payload = payload

    def list_tools(self, **_kwargs):
        return self._payload
