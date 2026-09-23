# Frappe Assistant Core - Powered by FAC Cloud
# Copyright (C) 2026 Paul Clinton
# AGPLv3

"""`list_triggers` must key on the docname binding, not the display name.

The write and dispatch paths were moved onto `workflow_docname` because a
rename silently orphaned every trigger bound by the mutable display name. The
read path was left behind: it declared only `workflow_name`, so Frappe dropped
the `workflow_docname` the SPA was already sending and a renamed workflow
listed zero triggers while its triggers kept firing — and the user recreated
them as duplicates.
"""

import inspect

import frappe

from frappe_assistant_core.chat.api import workflow_triggers
from frappe_assistant_core.chat.api.workflow_triggers import list_triggers
from frappe_assistant_core.tests.base_test import BaseAssistantTest

OLD_NAME = "Trigger Binding Probe (old)"
NEW_NAME = "Trigger Binding Probe (renamed)"
DOCNAME = "WF-BINDPROBE-1"
OTHER_DOCNAME = "WF-BINDPROBE-2"


class TestListTriggersBinding(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; isolated transaction
        frappe.set_user("Administrator")

        self.bound = self._trigger("Bound by docname", OLD_NAME, DOCNAME)
        self.legacy = self._trigger("Legacy, no docname", OLD_NAME, "")
        self.other = self._trigger("Different workflow", OLD_NAME, OTHER_DOCNAME)

    def _trigger(self, title: str, workflow_name: str, workflow_docname: str):
        return frappe.get_doc(
            {
                "doctype": "FAC Workflow Trigger",
                "title": title,
                "workflow_name": workflow_name,
                "workflow_docname": workflow_docname,
                "workflow_display_name": workflow_name,
                "reference_doctype": "ToDo",
                "doctype_event": "after_insert",
                "enabled": 1,
            }
        ).insert(ignore_permissions=True)

    def _titles(self, **kwargs) -> set:
        return {row["title"] for row in list_triggers(**kwargs)["triggers"]}

    def test_endpoint_declares_workflow_docname(self):
        """Frappe drops undeclared arguments, so the parameter is the fix."""
        self.assertIn("workflow_docname", inspect.signature(list_triggers).parameters)

    def test_rename_does_not_hide_the_bound_trigger(self):
        titles = self._titles(workflow_name=NEW_NAME, workflow_docname=DOCNAME)

        self.assertIn("Bound by docname", titles)
        self.assertNotIn("Different workflow", titles)
        # The renamed workflow no longer claims the legacy display-name row.
        self.assertNotIn("Legacy, no docname", titles)

    def test_legacy_row_still_listed_before_a_rename(self):
        titles = self._titles(workflow_name=OLD_NAME, workflow_docname=DOCNAME)

        self.assertIn("Bound by docname", titles)
        self.assertIn("Legacy, no docname", titles)
        self.assertNotIn("Different workflow", titles)

    def test_docname_alone_ignores_the_display_name(self):
        titles = self._titles(workflow_docname=OTHER_DOCNAME)

        self.assertEqual(titles & self._probe_titles(), {"Different workflow"})

    def test_display_name_alone_stays_backward_compatible(self):
        titles = self._titles(workflow_name=OLD_NAME)

        self.assertEqual(
            titles & self._probe_titles(),
            {"Bound by docname", "Legacy, no docname", "Different workflow"},
        )

    def test_no_filter_lists_every_trigger(self):
        self.assertEqual(self._titles() & self._probe_titles(), self._probe_titles())

    def _probe_titles(self) -> set:
        return {"Bound by docname", "Legacy, no docname", "Different workflow"}


class TestDeleteTriggerWithLogs(BaseAssistantTest):
    """A trigger that has fired could not be deleted at all.

    FAC Workflow Trigger Log links back to the trigger, so Frappe's link check
    refused with "You can disable this instead of deleting it" — meaning the
    only removable trigger was one that had never run.
    """

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def _trigger_with_a_log(self):
        trigger = frappe.get_doc(
            {
                "doctype": "FAC Workflow Trigger",
                "title": "deletable",
                "workflow_name": "Some Agent",
                "workflow_docname": "WF-00001",
                "reference_doctype": "ToDo",
                "doctype_event": "after_insert",
                "enabled": 1,
            }
        ).insert(ignore_permissions=True)
        frappe.get_doc(
            {
                "doctype": "FAC Workflow Trigger Log",
                "trigger": trigger.name,
                "reference_doctype": "ToDo",
                "reference_docname": "TODO-0001",
                "event": "after_insert",
                "status": "dispatched",
                "fired_at": frappe.utils.now_datetime(),
            }
        ).insert(ignore_permissions=True)
        return trigger.name

    def test_a_trigger_that_has_fired_can_be_deleted(self):
        name = self._trigger_with_a_log()
        result = workflow_triggers.delete_trigger(name)

        self.assertTrue(result["deleted"])
        self.assertEqual(result["logs_deleted"], 1)
        self.assertFalse(frappe.db.exists("FAC Workflow Trigger", name))

    def test_it_takes_the_logs_with_it(self):
        """The log records that trigger's own firings; it means nothing after."""
        name = self._trigger_with_a_log()
        workflow_triggers.delete_trigger(name)

        self.assertEqual(frappe.get_all("FAC Workflow Trigger Log", filters={"trigger": name}), [])
