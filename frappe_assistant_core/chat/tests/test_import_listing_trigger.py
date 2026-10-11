# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2026 Paul Clinton
# AGPL-3.0 License

"""Importing an event-driven template also creates its trigger, switched off."""

import json
from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api import marketplace
from frappe_assistant_core.tests.base_test import BaseAssistantTest

CLIENT = "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client"


class _Client:
    def __init__(self, suggested_trigger, workflow):
        self.suggested_trigger = suggested_trigger
        self.workflow = workflow

    def get_listing(self, **kwargs):
        # Production: AR get_listing returns source = workflow_resolver.get_full(), whose
        # suggested_trigger is the template's Long Text column - a JSON string (or None).
        return {
            "name": kwargs["name"],
            "listing_type": "Workflow",
            "title": "Big Order Credit Check",
            "source": {
                "variables_schema": "{}",
                "template_name": "Big Order Credit Check",
                "suggested_trigger": self.suggested_trigger,
            },
        }

    def import_listing(self, **kwargs):
        return {"target_doctype": "AR Workflow", "target_name": self.workflow}


def _suggested(**overrides):
    value = {"reference_doctype": "ToDo", "doctype_event": "after_insert", **overrides}
    return json.dumps(value)


class TestImportListingTrigger(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; isolated transaction
        frappe.set_user("Administrator")
        # The class shares one transaction, so each test needs its own workflow id.
        self.workflow = f"WF-{frappe.generate_hash(length=8)}"

    def _import(self, suggested_trigger):
        with patch(CLIENT, return_value=_Client(suggested_trigger, self.workflow)):
            return marketplace.import_listing(name="LST-1")

    def _triggers(self):
        return frappe.get_all(
            "FAC Workflow Trigger",
            filters={"workflow_docname": self.workflow},
            fields=["name", "enabled", "reference_doctype", "doctype_event", "title"],
        )

    def test_suggested_trigger_creates_a_disabled_trigger(self):
        result = self._import(_suggested())
        rows = self._triggers()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].enabled, 0)
        self.assertEqual((rows[0].reference_doctype, rows[0].doctype_event), ("ToDo", "after_insert"))
        self.assertEqual(rows[0].title, "Big Order Credit Check trigger")
        self.assertEqual(result["trigger_created"], rows[0].name)
        self.assertEqual(result["target_name"], self.workflow)

    def test_filters_are_carried_over(self):
        self._import(_suggested(filters=[{"fieldname": "status", "operator": "=", "value": "Open"}]))
        doc = frappe.get_doc("FAC Workflow Trigger", self._triggers()[0].name)
        self.assertEqual([(f.fieldname, f.operator, f.value) for f in doc.filters], [("status", "=", "Open")])

    def test_unknown_doctype_skips_the_trigger_but_the_import_succeeds(self):
        result = self._import(_suggested(reference_doctype="No Such DocType Here"))
        self.assertEqual(self._triggers(), [])
        self.assertEqual(result["target_name"], self.workflow)
        self.assertNotIn("trigger_created", result)
        self.assertTrue(result["trigger_note"])

    def test_unknown_filter_field_skips_the_trigger(self):
        result = self._import(
            _suggested(filters=[{"fieldname": "no_such_field", "operator": "=", "value": "x"}])
        )
        self.assertEqual(self._triggers(), [])
        self.assertTrue(result["trigger_note"])

    def test_invalid_event_skips_the_trigger(self):
        result = self._import(_suggested(doctype_event="on_nothing"))
        self.assertEqual(self._triggers(), [])
        self.assertTrue(result["trigger_note"])

    def test_dict_shape_is_accepted(self):
        result = self._import({"reference_doctype": "ToDo", "doctype_event": "on_update"})
        self.assertEqual(self._triggers()[0].doctype_event, "on_update")
        self.assertIn("trigger_created", result)

    def test_template_without_a_suggested_trigger_creates_none(self):
        for absent in (None, "", "null"):
            result = self._import(absent)
            self.assertEqual(self._triggers(), [], msg=repr(absent))
            self.assertNotIn("trigger_created", result)
            self.assertNotIn("trigger_note", result)
