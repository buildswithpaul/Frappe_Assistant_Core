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
        # Production reaches get_fac_cloud_client() only on a site connected to FAC Cloud, and
        # _ar_user_id resolves the FAC user's AR identity from a registered tenant member; neither
        # exists on a test site, so both are stood in for to observe what would be sent.
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


VIEWER = "runtime-viewer@example.com"
RUNTIME = "runtime-user@example.com"


def _ensure_user(email, roles=()):
    if not frappe.db.exists("User", email):
        frappe.get_doc(
            {"doctype": "User", "email": email, "first_name": "Probe", "send_welcome_email": 0}
        ).insert(ignore_permissions=True)
    user = frappe.get_doc("User", email)
    user.set("roles", [{"role": r} for r in roles])
    user.save(ignore_permissions=True)


# Production's client is the SDK talking to FAC Cloud; this stand-in returns the response
# shape list_tools / resolve_workflow_tools have in SDK 1.11.0 so the wiring above it runs.
class _ToolClient:
    def __init__(self):
        self.calls = []

    def list_tools(self, **kwargs):
        self.calls.append(("list_tools", kwargs))
        return {"tools": [{"name": "site:list_documents"}], "servers_queried": ["site"], "errors": None}

    def resolve_workflow_tools(self, **kwargs):
        self.calls.append(("resolve_workflow_tools", kwargs))
        return {
            "resolved": [
                {"tool_name": "list_documents", "runs_unattended": True, "candidate_servers": ["site"]}
            ],
            "all_tools_available": True,
            "missing_tools": [],
            "ambiguous_tools": [],
        }


class TestToolChecksUseTheRuntimeUser(BaseAssistantTest):
    """Real users and the real _ar_user_id: only the FAC Cloud client is stubbed."""

    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; isolated transaction
        frappe.set_user("Administrator")
        _ensure_user(VIEWER)
        _ensure_user(RUNTIME)
        self.addCleanup(frappe.set_user, "Administrator")
        self.client = _ToolClient()
        p = patch(CLIENT, return_value=self.client)
        p.start()
        self.addCleanup(p.stop)

    def _user_sent(self, method):
        return next(kw["user_id"] for name, kw in self.client.calls if name == method)

    def test_admin_lists_the_runtime_users_tools(self):
        result = workflows.list_user_tools(runtime_user=RUNTIME)
        self.assertTrue(result["success"])
        self.assertEqual(self._user_sent("list_tools"), RUNTIME)

    def test_admin_resolves_against_the_runtime_user(self):
        workflows.resolve_workflow_tools(
            tool_directives='[{"tool_name": "list_documents"}]', runtime_user=RUNTIME
        )
        self.assertEqual(self._user_sent("resolve_workflow_tools"), RUNTIME)

    def test_resolve_passes_the_unattended_data_through(self):
        # Regression guard: the AR response was already returned unchanged.
        result = workflows.resolve_workflow_tools(
            tool_directives='[{"tool_name": "list_documents"}]', runtime_user=RUNTIME
        )
        self.assertTrue(result["resolved"][0]["runs_unattended"])
        self.assertEqual(result["resolved"][0]["candidate_servers"], ["site"])
        self.assertEqual(result["ambiguous_tools"], [])

    def test_without_runtime_user_the_caller_is_used(self):
        # Regression guard: the caller's identity was already what was sent.
        frappe.set_user(VIEWER)
        workflows.list_user_tools()
        self.assertEqual(self._user_sent("list_tools"), VIEWER)

    def test_viewer_may_name_themselves(self):
        frappe.set_user(VIEWER)
        workflows.list_user_tools(runtime_user=VIEWER)
        self.assertEqual(self._user_sent("list_tools"), VIEWER)

    def test_viewer_cannot_read_another_users_inventory(self):
        frappe.set_user(VIEWER)
        # list_user_tools turns every exception into a failure envelope; the
        # permission check must sit outside that, or a 403 reads as "no tools".
        with self.assertRaises(frappe.PermissionError):
            workflows.list_user_tools(runtime_user=RUNTIME)
        with self.assertRaises(frappe.PermissionError):
            workflows.resolve_workflow_tools(tool_directives='[{"tool_name": "x"}]', runtime_user=RUNTIME)
        self.assertEqual(self.client.calls, [])
