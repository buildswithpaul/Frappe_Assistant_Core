# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Import through Frappe's Data Import with one approval (#33993): a session whose file passed the
dry run is imported as a Data Import, from a cleaned copy of the file, with one approval card;
it ends with created, failed and skipped counts, shows in Desk like any import, and an
interrupted import continues without duplicates.

Customer again, as in the dry run's tests. The file has a value mapped ("Retial" to the
existing group) and a row left out, so the cleaned file is not the user's file.
"""

import io
import json
import os
import unittest
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe import _
from frappe.core.doctype.data_import.importer import Importer
from rq.timeouts import JobTimeoutException

from frappe_assistant_core.assistant_core.doctype.fac_import_session.fac_import_session import engine_session
from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils import import_dry_run, import_failures, import_fixes, import_run

MAPPING = {
    "Customer Name": "customer_name",
    "Customer Group": "customer_group",
    "Customer Type": "customer_type",
}
INSERT = "Insert New Records"


def approval_card(session, checked, doctype, import_type, **changes):
    """What FACO passes start_import after a check, and the approval card shows (#34402): the
    check's own counts and fingerprint, and the session's file name and submit setting."""
    return {
        "session": session,
        "doctype": doctype,
        "rows": checked["ready"],
        "import_type": import_type,
        "validated_fingerprint": checked.get("validated_fingerprint"),
        "file_name": frappe.db.get_value("FAC Import Session", session, "file_name"),
        "submit_after_import": bool(
            frappe.db.get_value("FAC Import Session", session, "submit_after_import")
        ),
        **changes,
    }


class WorkerStopped(BaseException):
    """A worker killed mid-import: not an Exception, so the importer can't catch it as a row's."""


class ImportRunCase(BaseAssistantTest):
    """A Customer Group and a session ready to import, for the import's tests and #33994's."""

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.registry = get_tool_registry()
        self.track_test_files()
        self.tag = frappe.generate_hash(length=6)
        self.group = f"Imported {self.tag}"
        frappe.get_doc(
            {
                "doctype": "Customer Group",
                "customer_group_name": self.group,
                "parent_customer_group": "All Customer Groups",
            }
        ).insert()

    def tearDown(self):
        frappe.set_user("Administrator")
        self.delete_test_files()
        super().tearDown()

    # -- helpers -----------------------------------------------------------------------

    def _run(self, tool_name, arguments):
        return self.registry.get_tool(tool_name)._safe_execute(arguments)

    def _names(self):
        t = self.tag
        return {"alpha": f"Alpha {t}", "beta": f"Beta {t}", "gamma": f"Gamma {t}", "delta": f"Delta {t}"}

    def _ready_session(self, file_doc=None, sheet=None, map_to=None):
        """A session whose file passed the dry run: a value mapped (to ``map_to``, else the
        group) and a row left out."""
        n = self._names()
        if not file_doc:
            lines = [",".join(MAPPING)]
            lines += [
                f"{n['alpha']},{self.group},Company",  # row 2
                f"{n['beta']},Nowhere {self.tag},Company",  # row 3: left out
                f"{n['gamma']},Retial {self.tag},Company",  # row 4: mapped to the group
                f"{n['delta']},{self.group},Company",  # row 5
            ]
            file_doc = self._file("customers.csv", ("\n".join(lines) + "\n").encode())
        arguments = {"file_url": file_doc.file_url}
        if sheet:
            arguments["sheet"] = sheet
        session = self._run("start_import_session", arguments)["result"]["session_id"]
        mapped = self._run(
            "set_column_mapping", {"session": session, "mapping": MAPPING, "doctype": "Customer"}
        )
        self.assertTrue(mapped["success"], mapped)
        checked = self._run("dry_run_import", {"session": session})["result"]
        groups = {g["value"]: g["id"] for g in checked["groups"] if g.get("value")}
        fixes = []
        if f"Retial {self.tag}" in groups:
            fixes.append({"group": groups[f"Retial {self.tag}"], "action": "map", "to": map_to or self.group})
        if f"Nowhere {self.tag}" in groups:
            fixes.append(
                {"group": groups[f"Nowhere {self.tag}"], "action": "leave_out", "reason": "Closed shop"}
            )
        if fixes:
            checked = self._run("dry_run_import", {"session": session, "fixes": fixes})["result"]
        self.assertEqual(checked["status"], "Ready to Import", checked)
        return session, checked

    def _file(self, name, content):
        return frappe.get_doc(
            {"doctype": "File", "file_name": name, "content": content, "is_private": 1}
        ).insert()

    def _card(self, session, checked, **changes):
        """What FACO passes, and the approval card shows."""
        return approval_card(session, checked, **{"doctype": "Customer", "import_type": INSERT, **changes})

    def _import(self, session, checked, **changes):
        return self._run("start_import", self._card(session, checked, **changes))

    def _doc(self, session):
        # The session as the import tools hold it (load_session): the engine's own copy, so a
        # test can set up what an earlier step writes (#34400).
        return engine_session(session)

    def _imported(self):
        return set(
            frappe.get_all(
                "Customer", filters={"customer_name": ["like", f"% {self.tag}"]}, pluck="customer_name"
            )
        )

    @contextmanager
    def _each_row_commits(self):
        """In production the importer commits each record and rolls back only a failed one. A
        test can't commit, so a savepoint taken at each commit stands in for it."""
        real_rollback = frappe.db.rollback

        def commit(*args, **kwargs):
            frappe.db.savepoint("fac_test_row")
            frappe.db.value_cache.clear()  # as a commit does: a record committed is seen as there

        def rollback(*, save_point=None):
            real_rollback(save_point=save_point or "fac_test_row")

        frappe.db.savepoint("fac_test_row")
        with patch.object(frappe.db, "commit", side_effect=commit), patch.object(
            frappe.db, "rollback", side_effect=rollback
        ):
            yield


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Customer")
class TestImportRun(ImportRunCase):
    # -- registration ------------------------------------------------------------------

    def test_importing_is_a_write_tool_so_it_asks_for_approval(self):
        from frappe_assistant_core.utils.tool_category_detector import detect_tool_category

        tool = self.registry.get_tool("start_import")

        self.assertEqual(detect_tool_category(tool), "write")
        self.assertEqual(tool.inputSchema["required"], ["session", "doctype", "rows", "import_type"])

    # -- criterion 1: one approval card with the doctype, the rows, new or updates ----------

    def test_the_card_must_say_what_was_checked(self):
        session, checked = self._ready_session()

        for wrong in (
            {"rows": checked["ready"] + 1},
            {"doctype": "Supplier"},
            {"import_type": "Update Existing Records"},
        ):
            response = self._import(session, checked, **wrong)
            self.assertFalse(response["success"], (wrong, response))
            self.assertIn("last check", response["result"]["error"])

        self.assertFalse(self._doc(session).data_imports)
        self.assertEqual(self._imported(), set())

    def test_a_file_that_has_not_passed_the_dry_run_is_not_imported(self):
        session, checked = self._ready_session()
        self._run("set_column_mapping", {"session": session, "mapping": MAPPING, "doctype": "Customer"})

        response = self._import(session, checked)

        self.assertFalse(response["success"], response)
        self.assertIn("dry_run_import", response["result"]["error"])
        self.assertEqual(self._imported(), set())

    def test_a_session_changed_since_its_check_is_not_imported(self):
        session, checked = self._ready_session()
        # Edited after the check (update_document can), but not checked again.
        self._doc(session).db_set("excluded_rows", "[2, 3]")

        response = self._import(session, checked)

        self.assertFalse(response["success"], response)
        self.assertEqual(self._imported(), set())

    def test_rows_erpnext_would_refuse_now_stop_the_import_before_it_starts(self):
        session, checked = self._ready_session()
        # The group the rows use was deleted after the check.
        frappe.delete_doc("Customer Group", self.group, force=True)

        response = self._import(session, checked)

        self.assertFalse(response["success"], response)
        self.assertIn("dry_run_import", response["result"]["error"])
        self.assertFalse(self._doc(session).data_imports)

    # -- criteria 2 and 3: it runs, ends with the counts, and shows in Desk ------------------

    def test_an_approved_import_runs_as_a_data_import_and_ends_with_the_counts(self):
        session, checked = self._ready_session()
        n = self._names()

        response = self._import(session, checked)

        self.assertTrue(response["success"], response)
        result = response["result"]
        self.assertEqual(self._imported(), {n["alpha"], n["gamma"], n["delta"]})
        self.assertEqual(
            frappe.db.get_value("Customer", {"customer_name": n["gamma"]}, "customer_group"), self.group
        )
        self.assertEqual((result["created"], result["failed"], result["skipped"]), (3, 0, 1))
        self.assertIn("Imported 3 Customer records", result["message"])
        self.assertIn("1 row left out (Closed shop: row 3)", result["message"])
        doc = self._doc(session)
        self.assertEqual(doc.status, "Completed")
        link = doc.data_imports[-1]
        self.assertEqual(
            (link.data_import, link.purpose, link.success_count, link.failed_count),
            (result["data_import"], "Import", 3, 0),
        )
        self.assertEqual(doc.steps[-1].step, "Import")

    def test_a_customers_phone_and_email_become_its_primary_contact(self):
        name = f"Phone {self.tag}"
        email = f"phone-{self.tag}@example.com".lower()
        lines = [",".join([*MAPPING, "Mobile", "Email"]), f"{name},{self.group},Company,9845012345,{email}"]
        file_doc = self._file("customers.csv", ("\n".join(lines) + "\n").encode())
        session = self._run("start_import_session", {"file_url": file_doc.file_url})["result"]["session_id"]
        # where the schema offers them: on the Customer (Frappe 15) or its contacts table (16)
        schema = self._run("get_import_schema", {"doctype": "Customer"})["result"]
        table = (
            "contacts." if any(t["fieldname"] == "contacts" for t in schema.get("child_tables", [])) else ""
        )
        mapping = {**MAPPING, "Mobile": f"{table}mobile_no", "Email": f"{table}email_id"}
        mapped = self._run(
            "set_column_mapping", {"session": session, "mapping": mapping, "doctype": "Customer"}
        )
        self.assertTrue(mapped["success"], mapped)
        checked = self._run("dry_run_import", {"session": session})["result"]
        self.assertEqual(checked["status"], "Ready to Import", checked)

        response = self._import(session, checked)

        self.assertTrue(response["success"], response)
        customer = frappe.get_doc("Customer", {"customer_name": name})
        self.assertEqual((customer.mobile_no, customer.email_id), ("9845012345", email))
        self.assertTrue(customer.customer_primary_contact)
        contact = frappe.get_doc("Contact", customer.customer_primary_contact)
        self.assertEqual((contact.mobile_no, contact.email_id), ("9845012345", email))

    # -- #34414: one customer sheet into Customer, Contact and Address together ------------------

    def _linked_tables(self):
        schema = self._run("get_import_schema", {"doctype": "Customer"})["result"]
        return {t["fieldname"] for t in schema.get("child_tables", [])}

    def _party_session(self, header, rows, extra):
        """A customer sheet's session, mapped where this ERPNext takes a contact's columns."""
        prefix = "contacts." if "contacts" in self._linked_tables() else ""
        lines = [",".join([*MAPPING, *header]), *rows]
        file_doc = self._file("customers.csv", ("\n".join(lines) + "\n").encode())
        session = self._run("start_import_session", {"file_url": file_doc.file_url})["result"]["session_id"]
        mapping = {
            **MAPPING,
            **{
                column: f"{prefix}{field}" if field in ("mobile_no", "email_id") else field
                for column, field in extra.items()
            },
        }
        mapped = self._run(
            "set_column_mapping", {"session": session, "mapping": mapping, "doctype": "Customer"}
        )
        self.assertTrue(mapped["success"], mapped)
        return session

    def test_a_row_whose_contact_fails_fails_as_a_whole(self):
        name = f"Bad Mail {self.tag}"
        session = self._party_session(
            ["Email"], [f"{name},{self.group},Company,not an email"], {"Email": "email_id"}
        )

        checked = self._run("dry_run_import", {"session": session})["result"]

        self.assertEqual((checked["ready"], checked["failed"]), (0, 1), checked)
        self.assertFalse(frappe.db.exists("Customer", {"customer_name": name}))

    def test_a_row_without_phone_or_email_makes_no_contact(self):
        name = f"No Contact {self.tag}"
        session = self._party_session(
            ["Mobile", "Email"],
            [f"{name},{self.group},Company,,"],
            {"Mobile": "mobile_no", "Email": "email_id"},
        )
        checked = self._run("dry_run_import", {"session": session})["result"]
        self.assertEqual(checked["status"], "Ready to Import", checked)

        self.assertTrue(self._import(session, checked)["success"])

        customer = frappe.get_doc("Customer", {"customer_name": name})
        self.assertFalse(customer.customer_primary_contact)
        self.assertFalse(
            frappe.get_all(
                "Dynamic Link",
                {"link_doctype": "Customer", "link_name": customer.name, "parenttype": "Contact"},
            )
        )

    def test_deleting_an_imported_customer_deletes_its_contact(self):
        # what an undo does: the customer goes, and ERPNext takes the contact made with it
        name = f"Undo Me {self.tag}"
        session = self._party_session(
            ["Mobile"], [f"{name},{self.group},Company,9845012399"], {"Mobile": "mobile_no"}
        )
        checked = self._run("dry_run_import", {"session": session})["result"]
        self.assertTrue(self._import(session, checked)["success"])
        customer = frappe.get_doc("Customer", {"customer_name": name})
        contact = customer.customer_primary_contact
        self.assertTrue(contact)

        frappe.delete_doc("Customer", customer.name)

        self.assertFalse(frappe.db.exists("Contact", contact))

    def test_the_address_comes_with_the_party_where_erpnext_takes_it(self):
        if "addresses" not in self._linked_tables():
            self.skipTest("Frappe 15: a party has no address fields; addresses are their own import")
        name = f"With Address {self.tag}"
        session = self._party_session(
            # India Compliance refuses an Indian address without its state, failing the whole row
            ["Street", "City", "State", "Country"],
            [f"{name},{self.group},Company,12 MG Road,Bengaluru,Karnataka,India"],
            {
                "Street": "addresses.address_line1",
                "City": "addresses.city",
                "State": "addresses.state",
                "Country": "addresses.country",
            },
        )
        checked = self._run("dry_run_import", {"session": session})["result"]
        self.assertEqual(checked["status"], "Ready to Import", checked)

        self.assertTrue(self._import(session, checked)["success"])

        customer = frappe.get_doc("Customer", {"customer_name": name})
        links = frappe.get_all(
            "Dynamic Link",
            {"link_doctype": "Customer", "link_name": customer.name, "parenttype": "Address"},
            pluck="parent",
        )
        self.assertEqual(len(links), 1)
        self.assertEqual(frappe.db.get_value("Address", links[0], "city"), "Bengaluru")

    def test_a_phone_mapped_to_the_hidden_party_field_is_pointed_at_the_contact(self):
        if "contacts" not in self._linked_tables():
            self.skipTest("Frappe 15: the party's phone and email are importable on it")
        lines = [",".join([*MAPPING, "Email"]), f"Hint {self.tag},{self.group},Company,a@example.com"]
        file_doc = self._file("customers.csv", ("\n".join(lines) + "\n").encode())
        session = self._run("start_import_session", {"file_url": file_doc.file_url})["result"]["session_id"]

        mapped = self._run(
            "set_column_mapping",
            {"session": session, "mapping": {**MAPPING, "Email": "email_id"}, "doctype": "Customer"},
        )

        self.assertIn("contacts.email_id", frappe.as_json(mapped))

    def test_the_data_import_is_like_any_other_in_desk(self):
        session, checked = self._ready_session()

        data_import = self._import(session, checked)["result"]["data_import"]

        di = frappe.get_doc("Data Import", data_import)
        self.assertEqual(
            (di.reference_doctype, di.import_type, di.status, di.mute_emails),
            ("Customer", INSERT, "Success", 1),
        )
        self.assertEqual(
            json.loads(di.template_options)["column_to_field_map"],
            {"0": "customer_name", "1": "customer_group", "2": "customer_type"},
        )
        self.assertEqual(frappe.db.count("File", {"file_url": di.import_file}), 1)  # one file, the import's
        file_doc = frappe.get_doc("File", {"file_url": di.import_file})
        self.assertTrue(file_doc.is_private)
        self.assertEqual(
            (file_doc.attached_to_doctype, file_doc.attached_to_name), ("Data Import", data_import)
        )
        self.assertEqual(frappe.db.count("Data Import Log", {"data_import": data_import, "success": 1}), 3)

    def test_a_data_import_that_cannot_be_saved_leaves_no_file_behind(self):
        from frappe.core.doctype.data_import.data_import import DataImport

        session, checked = self._ready_session()
        files_before = self.new_files()

        with patch.object(
            DataImport, "validate", autospec=True, side_effect=frappe.ValidationError("refused")
        ):
            response = self._import(session, checked)

        self.assertFalse(response["success"], response)
        self.assertEqual(self.new_files(), files_before)
        self.assertEqual(self._doc(session).status, "Ready to Import")

    def test_the_cleaned_file_keeps_the_users_row_numbers(self):
        session, checked = self._ready_session()

        data_import = self._import(session, checked)["result"]["data_import"]

        content = frappe.get_doc(
            "File", {"file_url": frappe.db.get_value("Data Import", data_import, "import_file")}
        ).get_content()
        lines = (content.decode() if isinstance(content, bytes) else content).splitlines()
        self.assertEqual(lines[2], ",,")  # row 3, left out, is blank
        self.assertIn(self.group, lines[3])  # row 4, "Retial" mapped
        logged = {
            json.loads(log.row_indexes)[0]
            for log in frappe.get_all(
                "Data Import Log", filters={"data_import": data_import}, fields=["row_indexes"]
            )
        }
        self.assertEqual(logged, {2, 4, 5})

    def test_the_sheet_the_user_chose_is_imported_not_the_first(self):
        openpyxl = __import__("openpyxl")
        n = self._names()
        book = openpyxl.Workbook()
        book.active.title = "Notes"
        book.active.append(["Anything"])
        book.active.append(["not customers"])
        sheet = book.create_sheet("Customers")
        sheet.append(list(MAPPING))
        sheet.append([n["alpha"], self.group, "Company"])
        buffer = io.BytesIO()
        book.save(buffer)
        file_doc = self._file("customers.xlsx", buffer.getvalue())
        session, checked = self._ready_session(file_doc, sheet="Customers")

        response = self._import(session, checked)

        self.assertTrue(response["success"], response)
        self.assertEqual(self._imported(), {n["alpha"]})

    def test_records_erpnext_refuses_while_importing_are_a_partial_success_with_their_rows(self):
        session, checked = self._ready_session()
        n = self._names()
        real_process = Importer.process_doc

        def on_hold(importer, doc):
            # The first record too: its rollback must not undo the Data Import and the session.
            if doc.get("customer_name") in (n["alpha"], n["gamma"]):
                frappe.throw(_("Customer is on hold"))
            return real_process(importer, doc)

        with self._each_row_commits(), patch.object(
            Importer, "process_doc", autospec=True, side_effect=on_hold
        ):
            response = self._import(session, checked)

        self.assertTrue(response["success"], response)
        result = response["result"]
        self.assertEqual((result["created"], result["failed"], result["skipped"]), (1, 2, 1))
        self.assertIn("rows 2, 4: Customer is on hold", result["message"])  # the user's row numbers
        self.assertEqual(self._doc(session).status, "Partially Completed")
        self.assertEqual(self._imported(), {n["delta"]})

    # -- criterion 4: an interrupted import continues without duplicates ------------------------

    def test_an_interrupted_import_continues_without_duplicates(self):
        session, checked = self._ready_session()
        n = self._names()
        real_process = Importer.process_doc
        calls = []

        def worker_stops_on_the_second(importer, doc):
            calls.append(doc.get("customer_name"))
            if len(calls) == 2:
                raise WorkerStopped  # a restart: nothing after this line runs, as for a killed worker
            return real_process(importer, doc)

        with self._each_row_commits(), patch.object(
            Importer, "process_doc", autospec=True, side_effect=worker_stops_on_the_second
        ):
            with self.assertRaises(WorkerStopped):
                self._import(session, checked)
        self.assertEqual(self._imported(), {n["alpha"]})
        self.assertEqual(self._doc(session).status, "Importing")

        # The approval card of a continue shows the rows it still imports, not every row checked
        stale = self._import(session, checked)
        self.assertFalse(stale["success"], stale)
        self.assertIn("2 of its 3", stale["result"]["error"])
        with self._each_row_commits():
            second = self._import(session, checked, rows=2)

        self.assertTrue(second["success"], second)
        self.assertEqual(second["result"]["state"], "finished")
        self.assertEqual(self._imported(), {n["alpha"], n["gamma"], n["delta"]})
        self.assertEqual(frappe.db.count("Customer", {"customer_name": n["alpha"]}), 1)
        doc = self._doc(session)
        self.assertEqual(doc.status, "Completed")
        self.assertEqual([d.purpose for d in doc.data_imports], ["Import", "Continue"])
        self.assertEqual(len({d.data_import for d in doc.data_imports}), 1)  # the same Data Import
        # One Data Import continued is one run: its records aren't counted twice.
        self.assertNotIn("runs", second["result"])
        self.assertNotIn("In all", second["result"]["message"])

    def _killed_after_a_rows_log(self, session, checked):
        """Import the session, its worker killed after the second record's success log is
        written and before that record is committed. Frappe's Data Import Log is MyISAM, so
        its log stays though the record is rolled back with the dead worker's transaction."""
        from frappe.core.doctype.data_import import importer

        real_log = importer.create_import_log
        logged = []

        def log_then_die(data_import, log_index, details):
            real_log(data_import, log_index, details)
            if details.get("success"):
                logged.append(details["docname"])
            if len(logged) == 2:
                # The worker dies before frappe.db.commit(): its open transaction (the record) is
                # lost, the MyISAM log row isn't. A test's commits are savepoints: roll back to it.
                frappe.db.rollback(save_point="fac_test_row")
                raise WorkerStopped
            return None

        with self._each_row_commits(), patch.object(importer, "create_import_log", side_effect=log_then_die):
            with self.assertRaises(WorkerStopped):
                self._import(session, checked)
        return logged

    def test_a_row_logged_but_not_saved_when_the_worker_died_is_imported_on_continue(self):
        # QA 2026-11-04 #2: the Data Import Log said row 101 created "QW Bulk Customer 0100", but
        # no such customer existed; resume skipped the row as imported, so it was lost for good.
        session, checked = self._ready_session()
        n = self._names()
        logged = self._killed_after_a_rows_log(session, checked)

        lost = logged[1]
        self.assertFalse(frappe.db.exists("Customer", lost))  # logged as created, not in ERPNext
        self.assertEqual(self._imported(), {n["alpha"]})

        # The lost row is still to import: the card counts it, and the continue imports it.
        self.assertEqual(import_run.rows_left(self._doc(session)), 2)
        with self._each_row_commits():
            second = self._import(session, checked, rows=2)

        self.assertTrue(second["success"], second)
        self.assertEqual(self._imported(), {n["alpha"], n["gamma"], n["delta"]})
        self.assertEqual(frappe.db.count("Customer", {"customer_name": n["alpha"]}), 1)
        self.assertEqual(self._doc(session).status, "Completed")

    def test_a_row_deleted_after_a_finished_import_still_counts_as_imported(self):
        # Only an import cut short can have a log without its record: a record deleted later from
        # a finished import was imported, and isn't imported again.
        session, checked = self._ready_session()
        n = self._names()
        with self._each_row_commits():
            self._import(session, checked)
        frappe.delete_doc("Customer", n["alpha"], force=True)

        self.assertEqual(import_run.rows_left(self._doc(session)), 0)

    def test_an_import_whose_file_is_gone_still_records_its_result(self):
        # #34538: the Data Import's file can go from disk. Its counts are on the Data Import Log,
        # but record_result raised on the file each time resume() called it, so the session could
        # never leave Importing.
        session, checked = self._ready_session()
        with self._each_row_commits():
            data_import = self._import(session, checked)["result"]["data_import"]
        file_url = frappe.db.get_value("Data Import", data_import, "import_file")
        os.remove(frappe.get_doc("File", {"file_url": file_url}).get_full_path())

        result = import_run.record_result(session, data_import)

        self.assertEqual(result["created"], 3)
        self.assertEqual(self._doc(session).status, "Completed")

    def test_a_timed_out_import_says_to_continue(self):
        session, checked = self._ready_session()
        with patch.object(import_run, "enqueue", autospec=True):  # queued, not run yet
            data_import = self._import(session, checked)["result"]["data_import"]
        frappe.db.set_value("Data Import", data_import, "status", "Timed Out")  # what Frappe's job sets

        result = import_run.record_result(session, data_import)

        self.assertIn("continue", result["message"])
        self.assertEqual(self._doc(session).status, "Importing")

    def test_continuing_while_it_still_runs_starts_nothing(self):
        session, checked = self._ready_session()
        with patch.object(import_run, "enqueue", autospec=True):  # queued, not run yet
            self._import(session, checked)

        with patch(
            "frappe.utils.background_jobs.is_job_enqueued", autospec=True, return_value=True
        ), patch.object(import_run, "enqueue", autospec=True) as enqueue:
            response = self._import(session, checked)

        self.assertTrue(response["success"], response)
        self.assertEqual(response["result"]["state"], "running")
        enqueue.assert_not_called()

    def test_a_finished_import_is_not_imported_again(self):
        session, checked = self._ready_session()
        self._import(session, checked)

        response = self._import(session, checked)

        self.assertFalse(response["success"], response)
        self.assertIn("already imported", response["result"]["error"])
        self.assertEqual(len(self._doc(session).data_imports), 1)

    def test_a_failed_import_can_be_tried_again(self):
        session, checked = self._ready_session()
        n = self._names()
        real_process = Importer.process_doc

        def all_on_hold(importer, doc):
            frappe.throw(_("Customer is on hold"))

        with self._each_row_commits(), patch.object(
            Importer, "process_doc", autospec=True, side_effect=all_on_hold
        ):
            first = self._import(session, checked)["result"]
        self.assertEqual((first["created"], first["failed"]), (0, 3))
        self.assertEqual(self._doc(session).status, "Failed")

        rechecked = self._run("dry_run_import", {"session": session})["result"]
        self.assertEqual((rechecked["ready"], rechecked["imported"]), (3, 0), rechecked)
        with self._each_row_commits(), patch.object(
            Importer, "process_doc", autospec=True, side_effect=real_process
        ):
            again = self._import(session, rechecked)

        self.assertTrue(again["success"], again)
        self.assertEqual(self._imported(), {n["alpha"], n["gamma"], n["delta"]})
        doc = self._doc(session)
        self.assertEqual(doc.status, "Completed")
        self.assertEqual([d.purpose for d in doc.data_imports], ["Import", "Retry"])

    def test_a_retry_queued_in_the_background_is_not_reported_as_the_old_result(self):
        session, checked = self._ready_session()
        n = self._names()
        real_process = Importer.process_doc

        def gamma_on_hold(importer, doc):
            if doc.get("customer_name") == n["gamma"]:
                frappe.throw(_("Customer is on hold"))
            return real_process(importer, doc)

        with self._each_row_commits(), patch.object(
            Importer, "process_doc", autospec=True, side_effect=gamma_on_hold
        ):
            self._import(session, checked)
        self.assertEqual(self._doc(session).status, "Partially Completed")
        rechecked = self._run("dry_run_import", {"session": session})["result"]

        with patch.object(import_run, "_runs_now", autospec=True, return_value=False), patch.object(
            import_run, "is_scheduler_inactive", autospec=True, return_value=False
        ), patch.object(import_run, "enqueue", autospec=True):
            response = self._import(session, rechecked)

        self.assertTrue(response["success"], response)
        self.assertEqual(response["result"]["state"], "started")
        # Its count is the rows left (from the check), not the old Data Import's, nor 0.
        self.assertIn("Importing 1 Customer records in the background", response["result"]["message"])

    def test_a_continue_that_erpnext_refuses_says_why_instead_of_asking_again(self):
        session, checked = self._ready_session()
        real_process = Importer.process_doc
        calls = []

        def worker_stops_on_the_second(importer, doc):
            calls.append(doc)
            if len(calls) == 2:
                raise WorkerStopped
            return real_process(importer, doc)

        with self._each_row_commits(), patch.object(
            Importer, "process_doc", autospec=True, side_effect=worker_stops_on_the_second
        ):
            with self.assertRaises(WorkerStopped):
                self._import(session, checked)
        # The group the remaining rows use is deleted before the user asks to continue.
        frappe.delete_doc("Customer Group", self.group, force=True)

        with self._each_row_commits():
            response = self._import(session, checked, rows=2)

        result = response["result"]
        self.assertEqual(result["state"], "refused")
        self.assertIn("can't continue", result["message"])
        self.assertEqual(self._doc(session).status, "Importing")

    def test_a_record_spread_over_rows_is_left_out_whole(self):
        # A Customer with two Sales Team rows: row 3 continues the record on row 2.
        n = self._names()
        people = []
        for i in (1, 2):
            people.append(
                frappe.get_doc(
                    {
                        "doctype": "Sales Person",
                        "sales_person_name": f"Seller {i} {self.tag}",
                        "parent_sales_person": "Sales Team",
                    }
                )
                .insert()
                .name
            )
        mapping = {
            **MAPPING,
            "Sales Person": "sales_team.sales_person",
            "Contribution": "sales_team.allocated_percentage",
        }
        lines = [",".join(mapping)]
        lines += [
            f"{n['alpha']},{self.group},Company,{people[0]},50",
            f",,,{people[1]},50",
            f"{n['delta']},{self.group},Company,,",
        ]
        file_doc = self._file("customers-team.csv", ("\n".join(lines) + "\n").encode())
        session = self._run("start_import_session", {"file_url": file_doc.file_url})["result"]["session_id"]
        self.assertTrue(
            self._run("set_column_mapping", {"session": session, "mapping": mapping, "doctype": "Customer"})[
                "success"
            ]
        )
        # A remap after a leave-out can leave only some of a record's rows in excluded_rows.
        self._doc(session).db_set("excluded_rows", "[2]")
        checked = self._run("dry_run_import", {"session": session})["result"]
        self.assertEqual((checked["status"], checked["ready"]), ("Ready to Import", 1), checked)

        response = self._import(session, checked)

        self.assertTrue(response["success"], response)
        self.assertEqual((response["result"]["created"], response["result"]["failed"]), (1, 0))
        self.assertEqual(self._imported(), {n["delta"]})
        self.assertFalse(frappe.get_doc("Customer", {"customer_name": n["delta"]}).sales_team)

    def test_failed_counts_are_records_like_created(self):
        session, _checked = self._ready_session()
        trace = "Traceback (most recent call last):\n  ...\nfrappe.exceptions.ValidationError: On hold"
        logs = [
            frappe._dict(row_indexes="[2, 3]", messages='[{"message": "On hold"}]', exception=trace),
            frappe._dict(row_indexes="[4, 5]", messages='[{"message": "On hold"}]', exception=trace),
        ]

        groups = import_failures.failure_groups(self._doc(session), logs)

        self.assertEqual(
            [(g["reason"], g["error"], g["count"], g["rows"]) for g in groups],
            [("On hold", "ValidationError", 2, [2, 3, 4, 5])],
        )
        self.assertEqual(groups[0]["explanation"], "4 rows rejected by ERPNext: On hold")

    def test_a_start_that_fails_half_way_leaves_no_data_import_behind(self):
        session, checked = self._ready_session()
        imports_before = frappe.db.count("Data Import")
        files_before = self.new_files()

        with patch.object(
            import_run, "_record_start", autospec=True, side_effect=frappe.TimestampMismatchError
        ):
            response = self._import(session, checked)

        self.assertFalse(response["success"], response)
        self.assertEqual(frappe.db.count("Data Import"), imports_before)
        self.assertEqual(self.new_files(), files_before)
        # The rollback takes the File row; its content on disk goes too.
        self.assertFalse(os.path.exists(frappe.get_site_path("private", "files", f"{session}-import.csv")))

    def test_an_import_run_to_its_end_elsewhere_is_recorded_not_run_again(self):
        from frappe.core.doctype.data_import.data_import import start_import

        session, checked = self._ready_session()
        with patch.object(import_run, "enqueue", autospec=True):  # queued, not run by us
            data_import = self._import(session, checked)["result"]["data_import"]
        start_import(data_import)  # run from Desk's Start Import instead

        response = self._import(session, checked)

        self.assertTrue(response["success"], response)
        self.assertEqual((response["result"]["state"], response["result"]["created"]), ("finished", 3))
        doc = self._doc(session)
        self.assertEqual(doc.status, "Completed")
        self.assertEqual([d.purpose for d in doc.data_imports], ["Import"])

    def test_a_partial_import_run_to_its_end_elsewhere_is_recorded_not_tried_again(self):
        from frappe.core.doctype.data_import.data_import import start_import

        session, checked = self._ready_session()
        n = self._names()
        real_process = Importer.process_doc

        def gamma_on_hold(importer, doc):
            if doc.get("customer_name") == n["gamma"]:
                frappe.throw(_("Customer is on hold"))
            return real_process(importer, doc)

        with patch.object(import_run, "enqueue", autospec=True):  # queued, not run by us
            data_import = self._import(session, checked)["result"]["data_import"]
        with self._each_row_commits(), patch.object(
            Importer, "process_doc", autospec=True, side_effect=gamma_on_hold
        ):
            start_import(data_import)  # run to its end from Desk; the session still says Importing

        response = self._import(session, checked)

        self.assertEqual((response["result"]["state"], response["result"]["failed"]), ("finished", 1))
        doc = self._doc(session)
        self.assertEqual(doc.status, "Partially Completed")
        self.assertEqual([d.purpose for d in doc.data_imports], ["Import"])  # recorded, not run again

    # -- who can import, and when it can't start ----------------------------------------------

    def test_a_user_who_cannot_use_data_import_is_told_before_anything_is_written(self):
        # May create and import Customers, but Data Import is for System Managers.
        frappe.set_user(self.make_throwaway_user("seller", roles=("Sales Master Manager",)))

        self.assertIn("Data Import", import_run.cannot_import("Customer"))

    def test_without_the_scheduler_the_import_is_refused(self):
        with patch.object(import_run, "_runs_now", autospec=True, return_value=False), patch.object(
            import_run, "is_scheduler_inactive", autospec=True, return_value=True
        ):
            self.assertIn("scheduler", import_run.cannot_import("Customer"))

    def test_the_job_waits_for_the_data_import_to_be_saved(self):
        session, checked = self._ready_session()

        with patch.object(import_run, "_runs_now", autospec=True, return_value=False), patch.object(
            import_run, "is_scheduler_inactive", autospec=True, return_value=False
        ), patch.object(import_run, "enqueue", autospec=True) as enqueue:
            response = self._import(session, checked)

        self.assertTrue(response["success"], response)
        self.assertEqual(response["result"]["state"], "started")
        kwargs = enqueue.call_args.kwargs
        self.assertTrue(kwargs["enqueue_after_commit"])

    def test_desk_sees_the_import_as_running_while_the_job_is_queued(self):
        """The job FAC queues is the one Desk's Start Import and Stop look up (#34397): Frappe's
        own id for the Data Import, not FAC's string for it."""
        from frappe.utils import background_jobs

        session, checked = self._ready_session()
        real_enqueue = import_run.enqueue

        def queued_now(*args, **kwargs):  # the job queued here, not after a commit
            kwargs["enqueue_after_commit"] = False
            self.addCleanup(self._remove_queued_job, kwargs["job_id"])
            return real_enqueue(*args, **kwargs)

        with patch.object(import_run, "_runs_now", autospec=True, return_value=False), patch.object(
            import_run, "is_scheduler_inactive", autospec=True, return_value=False
        ), patch.object(import_run, "enqueue", side_effect=queued_now):
            data_import = self._import(session, checked)["result"]["data_import"]

        # What Desk's Start Import asks: Frappe's own check, for the id Frappe's own run would use.
        asked = []
        with patch(
            "frappe.core.doctype.data_import.data_import.is_job_enqueued",
            side_effect=lambda job_id: asked.append(job_id) or background_jobs.is_job_enqueued(job_id),
        ):
            started = frappe.get_doc("Data Import", data_import).start_import()

        self.assertEqual(len(asked), 1)
        self.assertTrue(background_jobs.is_job_enqueued(asked[0]), "Desk can't see FAC's job")
        self.assertFalse(started, "Desk started a second importer")

    def _remove_queued_job(self, job_id: str) -> None:
        from frappe.utils import background_jobs

        job = background_jobs.get_job(job_id)
        if job:
            job.delete()

    def test_another_users_session_is_refused(self):
        session, checked = self._ready_session()
        frappe.set_user(self.make_throwaway_user("other", roles=("Sales Manager",)))

        response = self._import(session, checked)

        self.assertFalse(response["success"])
        frappe.set_user("Administrator")
        self.assertEqual(self._imported(), set())


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Customer")
class TestTheApprovalNamesTheCheck(ImportRunCase):
    """#34402: the import's approval is of one check, and the card names the file."""

    def test_the_check_names_itself_for_the_approval(self):
        # 12 characters, which FACO copies onto the card: it dropped one of 64 twice (#34545)
        session, checked = self._ready_session()

        self.assertEqual(len(checked["validated_fingerprint"]), 12)
        self.assertTrue(self._doc(session).validated_fingerprint.startswith(checked["validated_fingerprint"]))

    def test_the_card_takes_the_checks_id_or_its_whole_fingerprint_and_nothing_less(self):
        session, checked = self._ready_session()
        full = self._doc(session).validated_fingerprint

        for given in (full[:11], "0" * 12, ""):
            with self.subTest(given=given):
                reply = self._import(session, checked, validated_fingerprint=given)
                self.assertFalse(reply["success"], reply)
        with self._each_row_commits():
            reply = self._import(session, checked, validated_fingerprint=full.upper())
        self.assertTrue(reply["success"], reply)

    def test_an_approval_of_an_earlier_check_imports_nothing(self):
        session, checked = self._ready_session()
        approved = self._card(session, checked)
        # Another tab, or a parallel call, maps the file again and checks it: as many rows are
        # ready, but it is another check, of another mapping.
        mapping = {**MAPPING, "Customer Type": "Don't Import"}
        remapped = self._run(
            "set_column_mapping", {"session": session, "mapping": mapping, "doctype": "Customer"}
        )
        self.assertTrue(remapped["success"], remapped)
        again = self._run("dry_run_import", {"session": session})["result"]
        self.assertEqual((again["status"], again["ready"]), ("Ready to Import", checked["ready"]), again)

        reply = self._run("start_import", approved)

        self.assertFalse(reply["success"], reply)
        self.assertIn("validated_fingerprint", reply["result"]["error"])
        self.assertFalse(self._imported())

    def test_a_card_without_the_check_is_refused(self):
        session, checked = self._ready_session()
        card = self._card(session, checked)
        del card["validated_fingerprint"]

        reply = self._run("start_import", card)

        self.assertFalse(reply["success"], reply)
        self.assertIn("validated_fingerprint", reply["result"]["error"])
        self.assertFalse(self._imported())

    def test_the_card_names_the_file_and_whether_records_are_submitted(self):
        session, checked = self._ready_session()

        for change in ({"file_name": "other.csv"}, {"submit_after_import": True}):
            with self.subTest(change=change):
                reply = self._import(session, checked, **change)
                self.assertFalse(reply["success"], reply)
                self.assertIn("file_name", reply["result"]["error"])
        self.assertFalse(self._imported())

    def test_a_card_that_leaves_out_submit_imports_a_session_that_doesnt_submit(self):
        # BT-18: FACO leaves an optional false out, and the card is right without it; refused
        # after the user approved, 6 files took 12 approvals.
        session, checked = self._ready_session()
        card = self._card(session, checked)
        del card["submit_after_import"]

        with self._each_row_commits():
            reply = self._run("start_import", card)

        self.assertTrue(reply["success"], reply)

    def test_a_card_that_leaves_out_submit_is_refused_when_the_session_submits(self):
        # The user must see on the card that the records are submitted.
        session, _checked = self._ready_session()
        frappe.db.set_value("FAC Import Session", session, "submit_after_import", 1)
        checked = self._run("dry_run_import", {"session": session})["result"]
        card = self._card(session, checked)
        del card["submit_after_import"]

        reply = self._run("start_import", card)

        self.assertFalse(reply["success"], reply)
        self.assertIn("submit_after_import true", reply["result"]["error"])
        self.assertFalse(self._imported())

    @contextmanager
    def _starts_that_collide(self, times):
        """The first ``times`` starts deadlock: the database undoes the victim's whole transaction
        (here, all since the call began) and raises. Yields the cleaned files removed from disk."""
        real_rollback, real_record, real_remove = (
            frappe.db.rollback,
            import_run._record_start,
            import_run._remove_from_disk,
        )
        collided, removed = [], []

        def record(*args, **kwargs):
            if len(collided) < times:
                collided.append(1)
                real_rollback(save_point="fac_test_row")  # what the server does to the victim
                raise frappe.QueryDeadlockError("Deadlock found when trying to get lock")
            return real_record(*args, **kwargs)

        def remove(file_doc):
            removed.append(file_doc.file_url)
            real_remove(file_doc)

        with self._each_row_commits(), patch.object(
            import_run, "_record_start", side_effect=record
        ), patch.object(import_run, "_remove_from_disk", side_effect=remove), patch(
            "frappe_assistant_core.plugins.migration.tools.start_import.time.sleep"
        ):
            yield removed

    def test_a_start_that_collides_runs_again_by_itself(self):
        # BT-17: six imports started at once, two deadlocked, and the user was asked to try again.
        # The database had undone the start whole, so start_import runs it again itself.
        session, checked = self._ready_session()

        with self._starts_that_collide(1) as removed:
            reply = self._import(session, checked)

        self.assertTrue(reply["success"], reply)
        self.assertEqual(
            self._imported(), {self._names()["alpha"], self._names()["gamma"], self._names()["delta"]}
        )
        self.assertEqual(len(removed), 1, "the collided start's cleaned file stays on disk")
        self.assertEqual(len(self._doc(session).data_imports), 1)

    def test_a_start_that_keeps_colliding_says_try_again_and_leaves_no_file(self):
        # Before: "SAVEPOINT fac_start_import does not exist" hid the deadlock, and the cleaned
        # file stayed on disk.
        session, checked = self._ready_session()

        with self._starts_that_collide(import_run.START_ATTEMPTS) as removed:
            reply = self._import(session, checked)

        self.assertFalse(reply["success"], reply)
        self.assertIn("try again", reply["result"]["error"])
        self.assertNotIn("SAVEPOINT", reply["result"]["error"])
        self.assertEqual(len(removed), import_run.START_ATTEMPTS)
        self.assertFalse(self._imported())


class TestOnlyWhatWasMappedAndChecked(ImportRunCase):
    """Review fixes: a column the user left unmapped is not imported (#33993), and the mapping
    can't change under an import that runs or was cancelled (#33989)."""

    def test_a_column_left_unmapped_is_not_imported(self):
        territory = f"Unmapped {self.tag}"
        frappe.get_doc(
            {"doctype": "Territory", "territory_name": territory, "parent_territory": "All Territories"}
        ).insert()
        name = f"Alpha {self.tag}"
        lines = [",".join([*MAPPING, "Territory"]), f"{name},{self.group},Company,{territory}"]
        file_doc = self._file("customers.csv", ("\n".join(lines) + "\n").encode())
        session = self._run("start_import_session", {"file_url": file_doc.file_url})["result"]["session_id"]
        self._run("set_column_mapping", {"session": session, "mapping": MAPPING, "doctype": "Customer"})
        checked = self._run("dry_run_import", {"session": session})["result"]
        self.assertEqual(checked["status"], "Ready to Import", checked)

        imported = self._import(session, checked)

        self.assertTrue(imported["success"], imported)
        self.assertNotEqual(frappe.db.get_value("Customer", {"customer_name": name}, "territory"), territory)

    def test_the_mapping_is_kept_while_an_import_runs_or_once_it_was_cancelled(self):
        session, _checked = self._ready_session()
        for status in ("Importing", "Cancelled", "Undoing", "Undone", "Partially Undone"):
            with self.subTest(status):
                # start_import leaves the session Importing while its Data Import is queued or
                # running. The undo statuses are legacy: sessions from before the undo was
                # removed may hold them, and still refuse a new mapping.
                frappe.db.set_value("FAC Import Session", session, "status", status)

                reply = self._run(
                    "set_column_mapping", {"session": session, "mapping": {"Customer Type": "customer_type"}}
                )

                self.assertFalse(reply["success"], reply)
                self.assertEqual(self._doc(session).status, status)

    def test_a_session_that_can_be_checked_again_can_be_remapped(self):
        session, _checked = self._ready_session()

        reply = self._run(
            "set_column_mapping", {"session": session, "mapping": {"Customer Type": "customer_type"}}
        )

        self.assertTrue(reply["success"], reply)
        self.assertEqual(self._doc(session).status, "Mapped")


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Customer")
class TestWhileACheckRuns(ImportRunCase):
    """A file of more than 500 rows is checked in a background job, which stores its result on
    the session when it ends. Until then the mapping and the import wait."""

    def _checking(self, session):
        # Production: dry_run_import queues the check of a large file and marks the session so.
        frappe.db.set_value(
            "FAC Import Session", session, "progress", import_dry_run._progress("queued", 0, 600)
        )

    def test_mapping_and_importing_wait_for_the_check(self):
        session, checked = self._ready_session()
        self._checking(session)
        for tool, arguments in (
            ("set_column_mapping", {"session": session, "mapping": {"Customer Type": "customer_type"}}),
            ("start_import", self._card(session, checked)),
        ):
            reply = self._run(tool, arguments)
            self.assertFalse(reply["success"], (tool, reply))
            self.assertIn("is being checked", json.dumps(reply), tool)
        doc = self._doc(session)
        self.assertEqual((doc.status, len(doc.data_imports)), ("Ready to Import", 0))

    def test_a_change_saved_while_the_check_runs_is_not_taken_as_checked(self):
        session, _checked = self._ready_session()
        real_check = import_dry_run._Checker.check

        def check_while_remapped(checker, *args, **kwargs):
            # Another request remaps a column while this check is running
            doc = self._doc(session)
            options = frappe.parse_json(doc.template_options)
            options["column_to_field_map"]["2"] = "Don't Import"
            frappe.db.set_value("FAC Import Session", session, "template_options", frappe.as_json(options))
            return real_check(checker, *args, **kwargs)

        with patch.object(import_dry_run._Checker, "check", autospec=True, side_effect=check_while_remapped):
            import_dry_run.run(session)

        self.assertFalse(import_fixes.checked_as_is(self._doc(session)))
        self.assertFalse(self._import(session, {"ready": 3})["success"])


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Customer")
@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Customer")
class TestAWorkerKilledMidImport(ImportRunCase):
    """#33993: a worker killed mid-import leaves its RQ job "started" until another worker's
    clean-up finds it; the import goes on, and can be released, once the worker is gone."""

    def _started_job(self, session, worker):
        # What RQ holds for a job a worker took: the job's hash, "started", naming that worker
        from frappe.utils.background_jobs import create_job_id, get_redis_conn
        from rq.job import Job, JobStatus

        data_import = self._doc(session).data_imports[-1].data_import
        job = Job.create(
            "frappe.ping", id=create_job_id(import_run._job_id(data_import)), connection=get_redis_conn()
        )
        job.worker_name = worker
        job.save()
        job.set_status(JobStatus.STARTED)
        self.addCleanup(job.connection.delete, job.key)
        return job

    def _queued(self):
        session, checked = self._ready_session()
        with patch.object(import_run, "enqueue", autospec=True):  # queued, not run yet
            self._import(session, checked)
        return session, checked

    def test_a_job_its_dead_worker_left_started_is_continued(self):
        session, checked = self._queued()
        self._started_job(session, f"fac-test-gone-{self.tag}")

        self.assertFalse(import_run.job_running(self._doc(session)))
        with self._each_row_commits():
            response = self._import(session, checked)

        self.assertTrue(response["success"], response)
        self.assertNotEqual(response["result"]["state"], "running", response)
        self.assertEqual(len(self._imported()), 3)

    def test_a_job_whose_dead_workers_execution_expired_is_continued(self):
        # Final round, 2026-11-06, v16: a worker killed mid-import (kill -9, then a new worker) left
        # its job "started" and its execution listed, but the execution's own record had expired
        # with the worker's heartbeat. RQ 2's job.delete() raised "Execution ... not found in
        # Redis" and continuing failed every time. This is what RQ 2 holds then.
        from rq.job import Job

        if not hasattr(Job, "execution_registry"):
            self.skipTest("RQ 1 (Frappe v15) keeps no executions apart")
        from rq.executions import Execution

        session, checked = self._queued()
        job = self._started_job(session, f"fac-test-gone-{self.tag}")
        lost = Execution(id=f"lost{self.tag}", job_id=job.id, connection=job.connection)
        job.connection.zadd(job.execution_registry.key, {lost.id: 9999999999})
        job.connection.zadd(job.started_job_registry.key, {lost.composite_key: 9999999999})
        self.addCleanup(job.connection.delete, job.execution_registry.key)
        self.addCleanup(job.connection.zrem, job.started_job_registry.key, lost.composite_key)

        with self._each_row_commits():
            response = self._import(session, checked)

        self.assertTrue(response["success"], response)
        self.assertNotEqual(response["result"]["state"], "running", response)
        self.assertEqual(len(self._imported()), 3)
        self.assertIsNone(job.connection.zscore(job.started_job_registry.key, lost.composite_key))

    def test_a_job_its_live_worker_runs_is_left_running(self):
        session, checked = self._queued()
        job = self._started_job(session, f"fac-test-alive-{self.tag}")
        worker_key = f"rq:worker:fac-test-alive-{self.tag}"
        job.connection.set(worker_key, 1, ex=60)  # the worker's key, kept while it lives
        self.addCleanup(job.connection.delete, worker_key)

        with patch.object(import_run, "enqueue", autospec=True) as enqueue:
            response = self._import(session, checked)

        self.assertEqual(response["result"]["state"], "running", response)
        enqueue.assert_not_called()


class TestRemapAfterAnImport(ImportRunCase):
    def test_a_session_whose_every_row_is_in_is_neither_remapped_nor_checked_again(self):
        # #34402: Completed with nothing left out, a remap set it back to Mapped for nothing
        n = self._names()
        lines = [",".join(MAPPING), f"{n['alpha']},{self.group},Company", f"{n['beta']},{self.group},Company"]
        session, checked = self._ready_session(self._file("all_in.csv", ("\n".join(lines) + "\n").encode()))
        with self._each_row_commits():
            self.assertTrue(self._import(session, checked)["success"])
        self.assertEqual(self._doc(session).status, "Completed")

        remap = self._run(
            "set_column_mapping", {"session": session, "mapping": MAPPING, "doctype": "Customer"}
        )
        check = self._run("dry_run_import", {"session": session})

        for reply in (remap, check):
            self.assertFalse(reply["success"], reply)
            self.assertIn(
                "Every row of this file is imported", reply.get("error") or reply["result"]["error"]
            )
        self.assertEqual(self._doc(session).status, "Completed")

    def test_rows_left_out_of_a_completed_session_can_still_be_checked_again(self):
        session, checked = self._ready_session()  # row 3 is left out
        with self._each_row_commits():
            self.assertTrue(self._import(session, checked)["success"])

        remap = self._run(
            "set_column_mapping", {"session": session, "mapping": MAPPING, "doctype": "Customer"}
        )

        self.assertTrue(remap["success"], remap)

    def test_rows_imported_as_one_doctype_keep_the_session_to_it(self):
        session, checked = self._ready_session()
        with self._each_row_commits():
            self.assertTrue(self._import(session, checked)["success"])

        # "These are suppliers": the rows already in are Customers, and are known as imported by
        # their row numbers, so another DocType would skip them. That takes a new session.
        for change in (
            {"doctype": "Supplier", "mapping": {"Customer Name": "supplier_name"}},
            {
                "import_type": "Update Existing Records",
                "mapping": {"Customer Type": "customer_type"},
                "match_on": ["customer_name"],
            },
        ):
            reply = self._run("set_column_mapping", {"session": session, **change})
            self.assertFalse(reply["success"], (change, reply))
            self.assertIn("start a new import session", reply["error"])
        doc = self._doc(session)
        self.assertEqual((doc.target_doctype, doc.import_type, doc.status), ("Customer", INSERT, "Completed"))


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Customer")
class TestRepeatedHeadings(ImportRunCase):
    def test_a_column_mapped_by_position_under_a_repeated_heading_is_imported(self):
        # Exports often repeat a heading ("Name" for the customer and for the contact). Frappe's
        # importer skips a column whose heading it has seen, even when it is mapped.
        name = f"Rep {self.tag}"
        content = f"Name,Group,Type,Name\n{name},{self.group},Company,Call before noon\n".encode()
        session = self._run("start_import_session", {"file_url": self._file("rep.csv", content).file_url})
        session = session["result"]["session_id"]
        mapping = {"0": "customer_name", "1": "customer_group", "2": "customer_type", "3": "customer_details"}
        mapped = self._run(
            "set_column_mapping", {"session": session, "mapping": mapping, "doctype": "Customer"}
        )
        self.assertTrue(mapped["success"], mapped)
        checked = self._run("dry_run_import", {"session": session})["result"]
        self.assertEqual(checked["status"], "Ready to Import", checked)

        with self._each_row_commits():
            self.assertTrue(self._import(session, checked)["success"])

        details = frappe.db.get_value("Customer", {"customer_name": name}, "customer_details")
        self.assertEqual(details, "Call before noon")


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Item Group")
class TestATreeFile(ImportRunCase):
    def test_a_tree_whose_parents_are_rows_of_the_file_is_imported_a_level_at_a_time(self):
        # Data Import refuses a whole file whose row links to a record not in ERPNext yet, as a
        # child row does to its parent row higher up the file.
        top, mid, leaf = (f"{level} {self.tag}" for level in ("Top", "Mid", "Leaf"))
        content = (
            "Item Group Name,Parent Item Group,Is Group\n"
            f"{top},All Item Groups,1\n"  # row 2
            f"{mid},{top},1\n"  # row 3: its parent is row 2
            f"{leaf},{mid},0\n"  # row 4: its parent is row 3
        ).encode()
        started = self._run("start_import_session", {"file_url": self._file("groups.csv", content).file_url})
        session = started["result"]["session_id"]
        mapping = {
            "Item Group Name": "item_group_name",
            "Parent Item Group": "parent_item_group",
            "Is Group": "is_group",
        }
        mapped = self._run(
            "set_column_mapping", {"session": session, "mapping": mapping, "doctype": "Item Group"}
        )
        self.assertTrue(mapped["success"], mapped)
        checked = self._run("dry_run_import", {"session": session})["result"]
        self.assertEqual((checked["ready"], checked["status"]), (3, "Ready to Import"), checked)

        with self._each_row_commits():
            response = self._import(session, checked, doctype="Item Group")

        self.assertTrue(response["success"], response)
        parents = dict(
            frappe.get_all(
                "Item Group",
                filters={"name": ["in", [top, mid, leaf]]},
                fields=["name", "parent_item_group"],
                as_list=True,
            )
        )
        self.assertEqual(parents, {top: "All Item Groups", mid: top, leaf: mid})
        doc = self._doc(session)
        self.assertEqual(doc.status, "Completed")
        self.assertEqual(
            [(link.purpose, link.success_count, link.failed_count) for link in doc.data_imports],
            [("Import", 1, 0)] * 3,
        )
        self.assertEqual(response["result"]["created_in_all"], 3)

    def test_a_tree_whose_last_level_fails_is_partly_imported(self):
        top, leaf = f"Top {self.tag}", f"Leaf {self.tag}"
        content = (
            f"Item Group Name,Parent Item Group,Is Group\n{top},All Item Groups,1\n{leaf},{top},0\n".encode()
        )
        started = self._run("start_import_session", {"file_url": self._file("tree.csv", content).file_url})
        session = started["result"]["session_id"]
        mapping = {
            "Item Group Name": "item_group_name",
            "Parent Item Group": "parent_item_group",
            "Is Group": "is_group",
        }
        self._run("set_column_mapping", {"session": session, "mapping": mapping, "doctype": "Item Group"})
        checked = self._run("dry_run_import", {"session": session})["result"]
        from erpnext.setup.doctype.item_group.item_group import ItemGroup

        real = ItemGroup.validate

        def leaf_refused(doc, *args, **kwargs):
            if doc.name == leaf:
                frappe.throw(frappe._("Leaf refused for the test"))
            return real(doc, *args, **kwargs)

        with self._each_row_commits(), patch.object(
            ItemGroup, "validate", autospec=True, side_effect=leaf_refused
        ):
            self._import(session, checked, doctype="Item Group")

        self.assertTrue(frappe.db.exists("Item Group", top))
        self.assertEqual(self._doc(session).status, "Partially Completed")
