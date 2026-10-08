# Frappe Assistant Core - Powered by FAC Cloud
# Copyright (C) 2026 Paul Clinton
# AGPLv3

"""A trigger's filter rows must reach the editor, so an edit cannot erase them.

`update_trigger` has always kept the rows when `filters` is None. The rows were
lost one step earlier: `list_triggers` never returned them, so the editor opened
every trigger with an empty filter list and sent that back on save.
"""

import json

import frappe

from frappe_assistant_core.chat.api import workflow_triggers
from frappe_assistant_core.chat.api.workflow_triggers import create_trigger, list_triggers, update_trigger
from frappe_assistant_core.tests.base_test import BaseAssistantTest

# test_trigger is called through its module: a bare `test_*` name imported into
# a test module reads as a test to some runners.
test_trigger_endpoint = workflow_triggers.test_trigger

DOCNAME = "WF-FILTERPROBE-1"
FILTERS = [
    {"fieldname": "description", "operator": "=", "value": "filter-probe-a"},
    {"fieldname": "status", "operator": "=", "value": "Open"},
]


class TestTriggerFiltersRoundTrip(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; isolated transaction
        frappe.set_user("Administrator")
        # workflow_docname is passed explicitly, so create_trigger never asks FAC Cloud to resolve it.
        created = create_trigger(
            title="Filter probe",
            workflow_name="Filter Probe",
            reference_doctype="ToDo",
            doctype_event="on_update",
            filters=json.dumps(FILTERS),
            workflow_docname=DOCNAME,
        )
        self.trigger_name = created["name"]

    def _listed(self) -> dict:
        rows = list_triggers(workflow_docname=DOCNAME)["triggers"]
        return next(r for r in rows if r["name"] == self.trigger_name)

    def test_list_returns_the_filter_rows(self):
        self.assertEqual(self._listed()["filters"], FILTERS)

    def test_title_only_edit_keeps_the_filters(self):
        update_trigger(name=self.trigger_name, title="Renamed probe")

        listed = self._listed()
        self.assertEqual(listed["title"], "Renamed probe")
        self.assertEqual(listed["filters"], FILTERS)

    def test_explicit_empty_list_still_clears(self):
        update_trigger(name=self.trigger_name, filters="[]")
        self.assertEqual(self._listed()["filters"], [])

    def test_a_trigger_without_filters_lists_an_empty_list(self):
        bare = create_trigger(
            title="No filters",
            workflow_name="Filter Probe",
            reference_doctype="ToDo",
            doctype_event="on_update",
            workflow_docname=DOCNAME,
        )["name"]
        rows = {r["name"]: r for r in list_triggers(workflow_docname=DOCNAME)["triggers"]}
        self.assertEqual(rows[bare]["filters"], [])


class TestTriggerTestWithARealDocument(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; isolated transaction
        frappe.set_user("Administrator")
        self.matching = frappe.get_doc({"doctype": "ToDo", "description": "filter-probe-a"}).insert()
        self.other = frappe.get_doc({"doctype": "ToDo", "description": "filter-probe-b"}).insert()
        self.trigger_name = create_trigger(
            title="Test-doc probe",
            workflow_name="Filter Probe",
            reference_doctype="ToDo",
            doctype_event="on_update",
            filters=json.dumps(FILTERS[:1]),
            workflow_docname=DOCNAME,
        )["name"]

    def test_named_document_that_passes(self):
        result = test_trigger_endpoint(trigger_name=self.trigger_name, reference_docname=self.matching.name)

        self.assertTrue(result["would_fire"])
        self.assertIsNone(result["failed_filter"])
        self.assertEqual(result["sample_doc"], self.matching.name)
        self.assertEqual(result["payload"]["trigger"]["docname"], self.matching.name)

    def test_named_document_that_fails_names_the_filter(self):
        result = test_trigger_endpoint(trigger_name=self.trigger_name, reference_docname=self.other.name)

        self.assertFalse(result["would_fire"])
        self.assertEqual(result["failed_filter"]["fieldname"], "description")
        self.assertEqual(result["sample_doc"], self.other.name)

    def test_unknown_document_is_an_error(self):
        with self.assertRaises(frappe.DoesNotExistError):
            test_trigger_endpoint(trigger_name=self.trigger_name, reference_docname="TODO-DOES-NOT-EXIST")
