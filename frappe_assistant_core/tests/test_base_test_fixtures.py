# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""The shared test fixtures hold on every site the suite runs on (#34430): Frappe v15 and v16,
with or without India Compliance. A fixture that only works on one of them fails here first."""

import importlib
import os
import unittest
from unittest.mock import patch

import frappe
from frappe.model.meta import Meta
from frappe.query_builder import DocType

from frappe_assistant_core.tests.base_test import NO_RIGHTS_ROLE, BaseAssistantTest, item_hsn_fields

# Doctypes the "someone else" users of the import tests must not touch.
GUARDED = ("Customer", "Supplier", "Customer Group", "Item", "Role", "Data Import")

# The test cases that delete the Files they made, in their tearDown (#34606).
FILE_CLEANING_CASES = (
    "test_apply_import_preset.PresetToolCase",
    "test_import_dry_run.TestDryRunImport",
    "test_import_file_intake.TestFileIntake",
    "test_import_file_intake.TestFileIntakeImport",
    "test_import_fixes.TestImportFixes",
    "test_import_google_sheet.TestStartFromGoogleSheet",
    "test_import_google_sheet.TestCheckGoogleSheetAgain",
    "test_import_mapping.ImportToolTestCase",
    "test_import_masters.TestImportMasters",
    "test_import_opening_balances.OpeningBalancesCase",
    "test_import_opening_invoices.OpeningInvoicesCase",
    "test_import_opening_stock.OpeningStockCase",
    "test_import_plan.ImportPlanCase",
    "test_import_run.ImportRunCase",
    "test_import_session.TestImportSession",
    "test_import_tally_xml.XmlCase",
)


class TestTheThrowawayUser(BaseAssistantTest):
    def test_the_throwaway_role_exists_on_this_site(self):
        self.make_desk_user("role")

        self.assertEqual(frappe.db.get_value("Role", NO_RIGHTS_ROLE, "desk_access"), 1)
        # it grants nothing: no permission rule anywhere names it
        self.assertFalse(frappe.get_all("DocPerm", filters={"role": NO_RIGHTS_ROLE}, limit=1))
        self.assertFalse(frappe.get_all("Custom DocPerm", filters={"role": NO_RIGHTS_ROLE}, limit=1))

    def test_a_throwaway_user_is_a_desk_user(self):
        user = self.make_desk_user("desk")

        self.assertEqual(frappe.db.get_value("User", user, "user_type"), "System User")
        own_roles = frappe.get_all("Has Role", filters={"parent": user, "parenttype": "User"}, pluck="role")
        self.assertEqual(own_roles, [NO_RIGHTS_ROLE])

    def test_a_throwaway_user_cannot_read_or_create_import_doctypes(self):
        user = self.make_desk_user("nothing")

        for doctype in (d for d in GUARDED if frappe.db.exists("DocType", d)):
            for ptype in ("read", "create", "write"):
                with self.subTest(doctype=doctype, ptype=ptype):
                    self.assert_cannot(user, ptype, doctype)
        # every desk user may keep Contacts of their own (the All rule), but none may import them
        self.assert_cannot(user, "import", "Contact")


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Item")
class TestTheItemFixture(BaseAssistantTest):
    def _item(self):
        return frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": f"FIXTURE-{frappe.generate_hash(length=6)}",
                "item_group": frappe.db.get_value("Item Group", {"is_group": 0}),
                "stock_uom": "Nos",
                **item_hsn_fields(),
            }
        ).insert()

    def test_an_item_fixture_inserts_on_this_site(self):
        item = self._item()

        self.assertTrue(frappe.db.exists("Item", item.name))
        self.assertEqual(item.get("gst_hsn_code"), item_hsn_fields().get("gst_hsn_code"))

    def test_an_item_fixture_has_a_valid_hsn_when_india_compliance_is_installed(self):
        fields = item_hsn_fields()

        if frappe.get_meta("Item").has_field("gst_hsn_code"):
            from india_compliance.gst_india.utils import get_hsn_settings

            code = fields["gst_hsn_code"]
            self.assertTrue(frappe.db.exists("GST HSN Code", code))
            self.assertIn(len(code), get_hsn_settings()[1])
        else:
            self.assertEqual(fields, {})

    def test_an_item_fixture_sets_no_hsn_without_india_compliance(self):
        # Item has gst_hsn_code only where India Compliance added it; on such a site, report it
        # absent as a site without India Compliance would (fac.localhost has none to begin with).
        real = Meta.has_field

        def has_field(meta, fieldname):
            return fieldname != "gst_hsn_code" and real(meta, fieldname)

        with patch.object(Meta, "has_field", autospec=True, side_effect=has_field):
            self.assertEqual(item_hsn_fields(), {})


class TestTheTestsLeaveOtherFiles(BaseAssistantTest):
    """The suite runs on a dev or demo site while people use it: a test deletes only its own Files."""

    def _upload_elsewhere(self, name: str) -> None:
        """A user's upload, committed by another process while a test runs. Not through File's
        insert: a test notes the Files inserted in its own process."""
        file_name = f"{name}.csv"
        with open(frappe.get_site_path("private", "files", file_name), "w") as f:
            f.write("Customer Name\nA real customer\n")
        file, now = DocType("File"), frappe.utils.now()
        with self.secondary_connection():
            frappe.qb.into(file).columns(
                file.name,
                file.file_name,
                file.file_url,
                file.is_private,
                file.folder,
                file.owner,
                file.modified_by,
                file.creation,
                file.modified,
            ).insert(
                name,
                file_name,
                f"/private/files/{file_name}",
                1,
                "Home",
                "Administrator",
                "Administrator",
                now,
                now,
            ).run()
            frappe.db.sql("commit")  # commit() does nothing in these tests

    def _remove_elsewhere(self, name: str, path: str) -> None:
        file = DocType("File")
        with self.secondary_connection():
            frappe.qb.from_(file).delete().where(file.name == name).run()
            frappe.db.sql("commit")
        if os.path.exists(path):
            os.remove(path)

    def test_no_import_test_deletes_a_file_uploaded_while_it_runs(self):
        # #34606: each took a snapshot of every File on the site in setUp and deleted the rest in
        # tearDown, so a user's upload meanwhile lost its file on disk.
        for case_path in FILE_CLEANING_CASES:
            module, class_name = case_path.rsplit(".", 1)
            # Imported here, so the runner doesn't collect the cases' own tests into this module.
            case_class = getattr(importlib.import_module(f"frappe_assistant_core.tests.{module}"), class_name)
            if getattr(case_class, "__unittest_skip__", False):
                continue
            with self.subTest(case=case_path):
                name = f"fac-34606-{frappe.generate_hash(length=8)}"
                path = frappe.get_site_path("private", "files", f"{name}.csv")
                case = case_class()
                try:
                    case.setUp()
                    self._upload_elsewhere(name)
                    # An import rolls back on the way (import_run, import_dry_run), and from then
                    # on the test reads what others committed: the upload too.
                    frappe.db.rollback()
                    case.tearDown()

                    self.assertTrue(frappe.db.exists("File", name))
                    self.assertTrue(os.path.exists(path))
                finally:
                    case.doCleanups()
                    frappe.db.rollback()
                    self._remove_elsewhere(name, path)
                    frappe.set_user("Administrator")


# The tests that run chat retention's daily clean-up (#34606).
RETENTION_TESTS = (
    "test_import_file_intake.TestFileIntake.test_retention_deletes_an_ended_sessions_files_and_keeps_the_session",
    "test_import_file_intake.TestFileIntake.test_retention_cancels_an_abandoned_failed_session",
    "test_import_keys.TestKeysOutliveChatRetention.test_the_daily_retention_clean_up_leaves_the_rows",
)


class TestTheTestsLeaveOtherSessions(BaseAssistantTest):
    """Retention deletes an ended session's files on disk, which no rollback brings back: a test
    that runs it may purge only the sessions it made, never the site's real ones (#34606)."""

    def _a_real_ended_session(self) -> str:
        """A session someone ended long ago on this site: retention's daily run would pick it.
        Written straight to the table, so it is no test's own."""
        name, then = (
            f"IMP-REAL-{frappe.generate_hash(length=8)}",
            frappe.utils.add_days(frappe.utils.now(), -400),
        )
        session = DocType("FAC Import Session")
        frappe.qb.into(session).columns(
            session.name,
            session.status,
            session.owner,
            session.modified_by,
            session.creation,
            session.modified,
        ).insert(name, "Completed", "Administrator", "Administrator", then, then).run()
        return name

    def test_no_retention_test_purges_the_sites_real_sessions(self):
        from frappe_assistant_core.utils import import_retention

        for test_path in RETENTION_TESTS:
            module, class_name, test_name = test_path.rsplit(".", 2)
            case_class = getattr(importlib.import_module(f"frappe_assistant_core.tests.{module}"), class_name)
            if getattr(case_class, "__unittest_skip__", False):
                continue
            with self.subTest(test=test_path):
                real = self._a_real_ended_session()
                purged = []
                # Notes what each purge is given and deletes nothing, so the check itself is safe.
                spy = lambda names, *args, **kwargs: purged.extend(names) or 0  # noqa: E731
                case = case_class(test_name)
                try:
                    with patch.object(import_retention, "purge", spy):
                        case.setUp()
                        getattr(case, test_name)()
                except AssertionError:
                    pass  # the test's own checks fail without a real purge: only what it purged matters
                finally:
                    case.doCleanups()
                    frappe.db.rollback()
                    frappe.set_user("Administrator")
                self.assertNotIn(real, purged)

    def test_no_test_module_runs_retention_on_the_whole_site(self):
        # The guard above lists the retention tests it knows: a new one calling
        # purge_old_sessions() itself, as test_import_keys did, would slip past it.
        tests_dir = os.path.dirname(__file__)
        offenders = []
        for file_name in sorted(os.listdir(tests_dir)):
            if not file_name.startswith("test_") or not file_name.endswith(".py"):
                continue
            with open(os.path.join(tests_dir, file_name)) as f:
                for number, line in enumerate(f, 1):
                    # fmt: off
                    if "purge_old_sessions()" in line and "def " not in line and "#" not in line.split("purge_old_sessions()")[0]:
                        offenders.append(f"{file_name}:{number}")
                    # fmt: on
        self.assertEqual(
            offenders, [], "use run_retention_on(...) so only the test's own sessions are purged"
        )
