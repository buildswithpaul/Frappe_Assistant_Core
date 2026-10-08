# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Run payloads reach the SPA with skipped-write data in one shape.

AR stores skipped_actions_detail as JSON text and AR releases before the
overhaul send neither field. The amber "N actions skipped" badge reads an int
and a list, so FAC normalises both on the way through.
"""

import json
from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api import workflows
from frappe_assistant_core.tests.base_test import BaseAssistantTest

CLIENT = "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client"
DETAIL = [{"node_id": "agent_1", "tool": "create_document", "reason": "Not approved for unattended runs"}]


class _RunClient:
    # Stands in for the SDK client: AR's get_run/list_runs return these rows, with skipped_actions_detail as a
    # parsed list (current AR), JSON text (older stored rows) or absent (pre-overhaul AR).
    def __init__(self, run):
        self.run = run

    def get_workflow_run(self, run_name):
        return dict(self.run, name=run_name)

    def list_workflow_runs(self, **_kwargs):
        return {"runs": [dict(self.run, name="WFR-1"), dict(self.run, name="WFR-2")], "total": 2}


class TestRunDisplayFields(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; isolated transaction
        frappe.set_user("Administrator")

    def _get(self, run):
        with patch(CLIENT, return_value=_RunClient(run)):
            return workflows.get_workflow_run(run_name="WFR-1")

    def test_json_text_detail_becomes_a_list(self):
        run = self._get(
            {"status": "Completed", "skipped_actions": 1, "skipped_actions_detail": json.dumps(DETAIL)}
        )

        self.assertEqual(run["skipped_actions"], 1)
        self.assertEqual(run["skipped_actions_detail"], DETAIL)
        self.assertEqual(run["status"], "Completed")

    def test_list_detail_passes_through(self):
        run = self._get({"status": "Completed", "skipped_actions": 1, "skipped_actions_detail": DETAIL})
        self.assertEqual(run["skipped_actions_detail"], DETAIL)

    def test_run_from_an_older_ar_has_zero_and_empty(self):
        run = self._get({"status": "Completed", "node_runs": []})

        self.assertEqual(run["skipped_actions"], 0)
        self.assertEqual(run["skipped_actions_detail"], [])
        self.assertEqual(run["node_runs"], [])

    def test_malformed_detail_is_an_empty_list(self):
        run = self._get(
            {"status": "Completed", "skipped_actions": "2", "skipped_actions_detail": "{not json"}
        )

        self.assertEqual(run["skipped_actions"], 2)
        self.assertEqual(run["skipped_actions_detail"], [])

    def test_missing_count_is_derived_from_the_detail(self):
        run = self._get({"status": "Completed", "skipped_actions_detail": json.dumps(DETAIL)})
        self.assertEqual(run["skipped_actions"], 1)

    def test_every_listed_run_is_normalised(self):
        run = {"status": "Completed", "skipped_actions": 1, "skipped_actions_detail": json.dumps(DETAIL)}
        with patch(CLIENT, return_value=_RunClient(run)):
            runs = workflows.list_workflow_runs(workflow_name="WF-00001")["runs"]

        self.assertEqual([r["skipped_actions_detail"] for r in runs], [DETAIL, DETAIL])

    def test_non_dict_detail_items_are_dropped(self):
        run = self._get(
            {"status": "Completed", "skipped_actions": 2, "skipped_actions_detail": [DETAIL[0], "junk", 3]}
        )
        self.assertEqual(run["skipped_actions_detail"], DETAIL)

    def test_explicit_null_detail_is_an_empty_list(self):
        run = self._get({"status": "Completed", "skipped_actions": None, "skipped_actions_detail": None})
        self.assertEqual(run["skipped_actions"], 0)
        self.assertEqual(run["skipped_actions_detail"], [])

    def test_non_numeric_count_falls_back_to_the_detail(self):
        run = self._get(
            {"status": "Completed", "skipped_actions": "abc", "skipped_actions_detail": json.dumps(DETAIL)}
        )
        self.assertEqual(run["skipped_actions"], 1)
