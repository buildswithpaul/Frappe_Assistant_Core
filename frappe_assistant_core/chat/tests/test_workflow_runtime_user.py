# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""A workflow runs as its runtime user; FAC must hand AR that user's AR identity.

AR keys tenant users by email. `Administrator` is the one Frappe user whose
docname is not its email, so every path that forwards a user id maps it.
"""

from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api import workflows
from frappe_assistant_core.tests.base_test import BaseAssistantTest

CLIENT = "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client"


def _ar_identity(user=None):
    """Stand-in for auth._ar_user_id: Administrator's User.email is site-specific."""
    user = user or frappe.session.user
    return "owner@example.com" if user == "Administrator" else user


class _RecordingClient:
    def __init__(self):
        self.calls = []

    def _record(self, method, kwargs):
        self.calls.append((method, kwargs))
        return {"name": "WF-00001", "status": "ok"}

    def create_workflow(self, **kwargs):
        return self._record("create_workflow", kwargs)

    def update_workflow(self, **kwargs):
        return self._record("update_workflow", kwargs)

    def test_workflow_node(self, **kwargs):
        return self._record("test_workflow_node", kwargs)

    def run_workflow_node(self, **kwargs):
        return self._record("run_workflow_node", kwargs)


class TestRuntimeUserIsMapped(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; isolated transaction
        frappe.set_user("Administrator")
        self.client = _RecordingClient()
        for p in (
            patch(CLIENT, return_value=self.client),
            patch.object(workflows, "_ar_user_id", side_effect=_ar_identity),
        ):
            p.start()
            self.addCleanup(p.stop)

    def _sent(self, method):
        return next(kwargs for name, kwargs in self.client.calls if name == method)

    def test_create_maps_the_given_user(self):
        workflows.create_workflow(workflow_name="Probe", default_user_id="Administrator")
        self.assertEqual(self._sent("create_workflow")["default_user_id"], "owner@example.com")

    def test_create_defaults_to_the_creator(self):
        workflows.create_workflow(workflow_name="Probe")
        self.assertEqual(self._sent("create_workflow")["default_user_id"], "owner@example.com")

    def test_update_maps_the_given_user(self):
        workflows.update_workflow(name="WF-00001", default_user_id="Administrator")
        self.assertEqual(self._sent("update_workflow")["default_user_id"], "owner@example.com")

    def test_update_with_empty_string_clears(self):
        # Regression guard: the empty string already reached AR unchanged.
        workflows.update_workflow(name="WF-00001", default_user_id="")
        self.assertEqual(self._sent("update_workflow")["default_user_id"], "")

    def test_update_without_user_leaves_it_alone(self):
        # Regression guard: an omitted default_user_id was already not sent.
        workflows.update_workflow(name="WF-00001", description="x")
        self.assertNotIn("default_user_id", self._sent("update_workflow"))

    def test_test_node_maps_the_runtime_user(self):
        workflows.test_workflow_node(
            node_json='{"id": "n1", "type": "agent"}', default_user_id="Administrator"
        )
        self.assertEqual(self._sent("test_workflow_node")["default_user_id"], "owner@example.com")

    def test_test_node_without_user_sends_none(self):
        # Regression guard: no user given was already forwarded as None.
        workflows.test_workflow_node(node_json='{"id": "n1", "type": "agent"}')
        self.assertIsNone(self._sent("test_workflow_node")["default_user_id"])

    def test_run_node_ignores_a_caller_supplied_user(self):
        # frappe.call is how /api/method dispatches: undeclared arguments are dropped,
        # exactly as they are for the SPA's request that still sends user_id.
        frappe.call(
            "frappe_assistant_core.chat.api.workflows.run_workflow_node",
            name="WF-00001",
            node_id="n1",
            user_id="Administrator",
        )
        self.assertIsNone(self._sent("run_workflow_node").get("user_id"))
