# Frappe Assistant Core - Powered by FAC Cloud
# Copyright (C) 2026 Paul Clinton
# AGPLv3

"""The doc-event payload: size budget, changed_fields types, child-row secrets.

Over 256 KB the payload used to collapse to name/owner/modified, throwing away
every parent field an agent needs because one child table (usually `items`)
was large. Child tables are now dropped largest-first and the parent kept.
"""

import datetime
import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.workflows.triggers.filters import build_payload
from frappe_assistant_core.tests.base_test import BaseAssistantTest

TRIGGER = SimpleNamespace(name="TRG-PAYLOAD-PROBE")
PROBE_EMAIL = "payload-probe@example.com"


def _user_with_big_roles_table():
    """An unsaved User whose `roles` table dwarfs everything else.

    Production reaches this with any document whose child table is large (a
    Sales Order with hundreds of items); User is used because it ships with
    Frappe itself and has several child tables plus a Password field. The name
    is set explicitly because User only receives one on insert.
    """
    doc = frappe.get_doc(
        {
            "doctype": "User",
            "email": PROBE_EMAIL,
            "first_name": "Payload",
            "roles": [{"role": f"Probe Role {i:04d} " + "x" * 80} for i in range(400)],
            "block_modules": [{"module": "Desk"}],
        }
    )
    doc.name = PROBE_EMAIL
    return doc


class TestPayloadBudget(BaseAssistantTest):
    def test_largest_child_table_goes_first_and_the_parent_stays(self):
        payload = build_payload(TRIGGER, _user_with_big_roles_table(), "on_update", {}, byte_cap=20_000)

        self.assertTrue(payload["doc_truncated"])
        self.assertEqual(payload["dropped_child_tables"], ["roles"])
        self.assertNotIn("roles", payload["doc"])
        self.assertEqual(payload["doc"]["block_modules"][0]["module"], "Desk")
        self.assertEqual(payload["doc"]["email"], PROBE_EMAIL)
        self.assertLessEqual(len(json.dumps(payload, default=str).encode()), 20_000)

    def test_parent_too_big_on_its_own_still_falls_back_to_minimal(self):
        user = _user_with_big_roles_table()
        user.bio = "y" * 40_000

        payload = build_payload(TRIGGER, user, "on_update", {}, byte_cap=20_000)

        self.assertTrue(payload["doc_truncated"])
        self.assertNotIn("dropped_child_tables", payload)
        self.assertNotIn("bio", payload["doc"])
        self.assertEqual(payload["doc"]["name"], PROBE_EMAIL)

    def test_payload_under_the_cap_is_untouched(self):
        """Regression guard: pins unchanged behaviour under the cap."""
        payload = build_payload(TRIGGER, _user_with_big_roles_table(), "on_update", {})

        self.assertNotIn("doc_truncated", payload)
        self.assertEqual(len(payload["doc"]["roles"]), 400)


class TestChangedFieldsAreJsonNative(BaseAssistantTest):
    def test_changed_fields_survive_strict_json(self):
        # get_changed_fields hands back raw column values: dates, Decimals, timedeltas.
        changed = {
            "transaction_date": {"old": datetime.date(2026, 10, 1), "new": datetime.date(2026, 10, 9)},
            "grand_total": {"old": Decimal("10.50"), "new": Decimal("12.00")},
            "posting_time": {"old": datetime.timedelta(hours=9), "new": None},
        }
        doc = frappe.get_doc({"doctype": "ToDo", "description": "changed-fields probe"})

        payload = build_payload(TRIGGER, doc, "on_update", changed)

        json.dumps(payload)  # strict: the SDK serialises without default=
        self.assertEqual(payload["changed_fields"]["transaction_date"]["new"], "2026-10-09")
        self.assertEqual(payload["changed_fields"]["grand_total"]["old"], 10.5)


class TestChildPasswordsAreStripped(BaseAssistantTest):
    def test_password_fieldtype_in_a_child_row_is_removed(self):
        # No child DocType in Frappe/ERPNext has a Password field, but custom apps
        # do (credential tables). Only get_meta for that one fake child DocType is
        # replaced; every other lookup goes to the real meta.
        real_get_meta = frappe.get_meta

        def fake_get_meta(doctype, *args, **kwargs):
            if doctype == "Probe Credential Row":
                return SimpleNamespace(
                    fields=[
                        SimpleNamespace(fieldname="label", fieldtype="Data"),
                        SimpleNamespace(fieldname="api_password", fieldtype="Password"),
                    ]
                )
            return real_get_meta(doctype, *args, **kwargs)

        class _Doc:
            doctype = "ToDo"
            name = "TODO-CRED-PROBE"

            def as_dict(self):
                return {
                    "name": self.name,
                    "credentials": [
                        {"doctype": "Probe Credential Row", "label": "erp", "api_password": "hunter2"}
                    ],
                }

        with patch.object(frappe, "get_meta", side_effect=fake_get_meta):
            payload = build_payload(TRIGGER, _Doc(), "on_update", {})

        row = payload["doc"]["credentials"][0]
        self.assertEqual(row["label"], "erp")
        self.assertNotIn("api_password", row)
