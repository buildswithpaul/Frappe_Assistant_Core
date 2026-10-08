# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Template variables are checked on this site, where Link values live.

FAC Cloud cannot see the tenant's database, so only FAC can say whether
"Acme Ltd" is a real Company. Links use User here because it exists on every
Frappe site; production templates link to Company, Warehouse and the like.
"""

import json
from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api import marketplace
from frappe_assistant_core.chat.workflows.template_variables import (
    parse_schema,
    parse_variables,
    validate_template_variables,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest

CLIENT = "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client"

SCHEMA = {
    "owner_user": {"type": "link", "options": "User", "label": "Owner", "required": True},
    "notify_email": {"type": "email", "label": "Notify Email", "required": True},
    "aging_days": {"type": "int", "label": "Aging Days"},
    "min_amount": {"type": "float", "label": "Minimum Amount"},
    "include_drafts": {"type": "check", "label": "Include Drafts"},
    "period": {"type": "select", "options": ["Weekly", "Monthly"], "label": "Period"},
    "note": {"type": "text", "label": "Note"},
}


class TestValidateTemplateVariables(BaseAssistantTest):
    def test_valid_values_are_coerced(self):
        values = validate_template_variables(
            SCHEMA,
            {
                "owner_user": "Administrator",
                "notify_email": "finance@example.com",
                "aging_days": "30",
                "min_amount": "1000",
                "include_drafts": "true",
                "period": "Monthly",
                "note": "hello",
            },
        )
        self.assertEqual(values["aging_days"], 30)
        self.assertEqual(values["min_amount"], 1000.0)
        self.assertEqual(values["include_drafts"], 1)
        self.assertEqual(values["owner_user"], "Administrator")

    def test_every_bad_field_is_named_at_once(self):
        with self.assertRaises(frappe.ValidationError) as caught:
            validate_template_variables(
                SCHEMA,
                {
                    "owner_user": "nobody-at-all@example.invalid",
                    "notify_email": "not-an-email",
                    "aging_days": "3.5",
                    "period": "Daily",
                },
            )
        message = str(caught.exception)
        for label in ("Owner", "Notify Email", "Aging Days", "Period"):
            self.assertIn(label, message)

    def test_required_blank_is_refused(self):
        with self.assertRaises(frappe.ValidationError) as caught:
            validate_template_variables(SCHEMA, {"owner_user": "Administrator", "notify_email": "  "})
        self.assertIn("Notify Email", str(caught.exception))

    def test_blank_optional_values_are_dropped_not_defaulted(self):
        values = validate_template_variables(
            SCHEMA, {"owner_user": "Administrator", "notify_email": "a@example.com", "note": ""}
        )
        self.assertNotIn("note", values)
        self.assertNotIn("aging_days", values)

    def test_link_to_a_doctype_this_site_lacks(self):
        schema = {
            "wh": {"type": "link", "options": "No Such DocType", "label": "Warehouse", "required": True}
        }
        with self.assertRaises(frappe.ValidationError) as caught:
            validate_template_variables(schema, {"wh": "Stores"})
        self.assertIn("No Such DocType", str(caught.exception))

    def test_legacy_type_names_still_validate(self):
        # Templates exported before typed variables carry inferred types
        # (assistant_runtime_workflows engine/template_utils.py _infer_variables_schema).
        legacy = {
            "company": {"type": "string", "label": "Company", "required": True},
            "days": {"type": "integer", "label": "Days"},
            "amount": {"type": "number", "label": "Amount"},
            "flag": {"type": "boolean", "label": "Flag"},
        }
        values = validate_template_variables(
            legacy, {"company": "Acme", "days": "7", "amount": "2.5", "flag": False}
        )
        self.assertEqual(values, {"company": "Acme", "days": 7, "amount": 2.5, "flag": 0})

    def test_schema_and_variables_parse_from_json_text(self):
        self.assertEqual(parse_schema(json.dumps(SCHEMA)), SCHEMA)
        self.assertEqual(parse_schema(None), {})
        self.assertEqual(parse_variables('{"a": 1}'), {"a": 1})
        with self.assertRaises(frappe.ValidationError):
            parse_variables("[1, 2]")


class _ImportClient:
    def __init__(self, schema):
        self.schema = schema
        self.imported = []

    def get_listing(self, **_kwargs):
        # MK workflow_resolver.get_full returns variables_schema as stored: JSON text.
        return {"listing_type": "Workflow", "source": {"variables_schema": json.dumps(self.schema)}}

    def import_listing(self, **kwargs):
        self.imported.append(kwargs)
        return {"target_doctype": "AR Workflow", "target_name": "WF-00010"}


class TestImportListingValidates(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; isolated transaction
        frappe.set_user("Administrator")

    def test_import_sends_coerced_values(self):
        client = _ImportClient(SCHEMA)
        with patch(CLIENT, return_value=client):
            marketplace.import_listing(
                name="LST-1",
                variables=json.dumps(
                    {"owner_user": "Administrator", "notify_email": "a@example.com", "aging_days": "45"}
                ),
            )
        sent = json.loads(client.imported[0]["variables"])
        self.assertEqual(sent["aging_days"], 45)

    def test_import_with_a_missing_required_value_never_reaches_fac_cloud(self):
        client = _ImportClient(SCHEMA)
        with patch(CLIENT, return_value=client), self.assertRaises(frappe.ValidationError):
            marketplace.import_listing(name="LST-1", variables={"owner_user": "Administrator"})
        self.assertEqual(client.imported, [])

    def test_unreadable_template_source_fails_closed(self):
        client = _ImportClient(SCHEMA)
        client.get_listing = lambda **_kw: {"listing_type": "Workflow", "source": None}
        with patch(CLIENT, return_value=client), self.assertRaises(frappe.ValidationError):
            marketplace.import_listing(name="LST-1", variables={"owner_user": "Administrator"})
        self.assertEqual(client.imported, [])


class TestLinkWithoutOptions(BaseAssistantTest):
    def test_link_without_options_validates_as_text(self):
        schema = {"x": {"type": "link", "label": "X", "required": True}}
        self.assertEqual(validate_template_variables(schema, {"x": "anything"}), {"x": "anything"})
