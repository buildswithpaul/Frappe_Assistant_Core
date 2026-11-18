# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""FAC Chat Settings.relay_in_background_job: schema default, install seed, upgrade patch."""

import frappe

from frappe_assistant_core.api.admin.settings import load_settings_map, resolve_groups, unmapped_units
from frappe_assistant_core.chat.hooks import install
from frappe_assistant_core.patches.v3_3 import seed_relay_in_background_job
from frappe_assistant_core.tests.base_test import BaseAssistantTest

FIELD = "relay_in_background_job"


def _singles_row_exists(fieldname: str) -> bool:
    singles = frappe.qb.DocType("Singles")
    rows = (
        frappe.qb.from_(singles)
        .select(singles.field)
        .where((singles.doctype == "FAC Chat Settings") & (singles.field == fieldname))
        .run()
    )
    return bool(rows)


def _delete_singles_row(fieldname: str) -> None:
    singles = frappe.qb.DocType("Singles")
    frappe.qb.from_(singles).delete().where(
        (singles.doctype == "FAC Chat Settings") & (singles.field == fieldname)
    ).run()
    frappe.clear_document_cache("FAC Chat Settings")


class TestRelaySetting(BaseAssistantTest):
    def test_schema_default_is_off(self):
        df = frappe.get_meta("FAC Chat Settings").get_field(FIELD)
        self.assertEqual((df.fieldtype, df.default), ("Check", "0"))

    def test_after_install_seeds_off(self):
        # A fresh install runs after_install once; the row may already hold a stale value.
        frappe.db.set_single_value("FAC Chat Settings", FIELD, 1)
        install.after_install()
        self.assertEqual(frappe.db.get_single_value("FAC Chat Settings", FIELD), 0)

    def test_patch_writes_an_absent_row_and_keeps_an_admin_choice(self):
        # A site upgraded from before the field has no Singles row for it.
        _delete_singles_row(FIELD)
        seed_relay_in_background_job.execute()
        self.assertTrue(_singles_row_exists(FIELD))
        # An admin who already switched it on in the Settings form keeps it on through migrate.
        frappe.db.set_single_value("FAC Chat Settings", FIELD, 1)
        seed_relay_in_background_job.execute()
        self.assertEqual(frappe.db.get_single_value("FAC Chat Settings", FIELD), 1)

    def test_fac_admin_settings_serves_the_field(self):
        served = [(g["doctype"], f) for g in resolve_groups(load_settings_map()) for f in g["fields"]]
        self.assertIn(("FAC Chat Settings", FIELD), served)
        self.assertEqual(unmapped_units(load_settings_map()), {})
