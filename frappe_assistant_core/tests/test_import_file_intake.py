# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
How start_import_session takes a file in (#34403, #34404, #34405).

The sheet is read once, into a private CSV the session owns, and every later step reads that
copy: the headings found below a title row (#34403), the text decoded by its byte-order mark and
split on its own delimiter (#34404), repeated headings made unique, and the chat's own file free
to be deleted by chat retention mid-migration (#34405).

Files are uploaded through upload_message_file, the way FAC Chat attaches them.
"""

import base64
import codecs
import csv
import io
import os
import unittest
from unittest.mock import patch

import frappe
from openpyxl import Workbook

from frappe_assistant_core.chat.api.settings.uploads import upload_message_file
from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils import import_session
from frappe_assistant_core.utils.import_session import read_sheet_rows, readable_session_file

HEADINGS = ["Cust Name", "Group", "Territory", "GSTIN", "Phone", "Email", "City"]
CSV_MIME = "text/csv"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _tally_rows(count=33):
    """A Tally Prime export: a title, a blank row, then the headings on row 3."""
    rows = [["Customer Master - exported from Tally Prime"], [], HEADINGS]
    for i in range(1, count + 1):
        rows.append([f"Party {i}", "Retail", "India", "", f"98450{i:05d}", f"p{i}@example.com", "Pune"])
    return rows


def _xlsx(rows) -> bytes:
    wb = Workbook()
    for row in rows:
        wb.active.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _csv(rows, delimiter=",") -> str:
    buf = io.StringIO()
    csv.writer(buf, delimiter=delimiter, lineterminator="\r\n").writerows(rows)
    return buf.getvalue()


class TestFileIntake(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.registry = get_tool_registry()
        # A plain desk user: owns the files they upload, holds no import rights.
        self.user = self.make_desk_user("intake")
        frappe.set_user(self.user)
        self.track_test_files()
        self.sessions_before = frappe.db.count("FAC Import Session")

    def tearDown(self):
        frappe.set_user("Administrator")
        self.delete_test_files()
        super().tearDown()

    # -- helpers ---------------------------------------------------------------------------

    def _upload(self, file_name: str, content: bytes, content_type: str = CSV_MIME):
        """The File a FAC Chat attachment makes."""
        with patch(
            "frappe_assistant_core.chat.api.settings.access.can_use_faco",
            return_value={"can_use": True},
        ):
            response = upload_message_file(
                file_data=base64.b64encode(content).decode(),
                file_name=file_name,
                content_type=content_type,
            )
        return frappe.get_doc("File", response["file"]["name"])

    def _run(self, tool_name, arguments):
        return self.registry.get_tool(tool_name)._safe_execute(arguments)

    def _start(self, **arguments):
        response = self._run("start_import_session", arguments)
        self.assertTrue(response["success"], response)
        return response["result"]

    def _start_fails(self, expected_text, **arguments):
        response = self._run("start_import_session", arguments)
        self.assertFalse(response["success"], response)
        self.assertIn(expected_text, response["error"])
        return response

    def _new_sessions(self):
        return frappe.db.count("FAC Import Session") - self.sessions_before

    @staticmethod
    def _session_rows(session_id):
        """The rows every later step reads: the session's own file."""
        doc = frappe.get_doc("FAC Import Session", session_id)
        return read_sheet_rows(readable_session_file(doc), doc.sheet or None)

    # -- #34403: a title row above the headings -----------------------------------------------

    def test_a_title_row_above_the_headings_is_left_out(self):
        original = self._upload("migtest_customers_tally.xlsx", _xlsx(_tally_rows()), XLSX_MIME)

        result = self._start(file_id=original.name)

        self.assertEqual(result["columns"], HEADINGS)
        self.assertEqual(result["row_count"], 33)
        self.assertEqual(result["sample_rows"][0][0], "Party 1")
        self.assertEqual(result["header_row"], 3)
        self.assertIn("row 3", result["note"])
        rows = self._session_rows(result["session_id"])
        self.assertEqual(rows[0], HEADINGS)
        self.assertEqual(rows[1][0], "Party 1")
        self.assertEqual(len(rows), 34)

    def test_a_title_row_in_a_csv_is_left_out(self):
        original = self._upload("customers.csv", _csv(_tally_rows(3)).encode())

        result = self._start(file_id=original.name)

        self.assertEqual((result["columns"], result["row_count"], result["header_row"]), (HEADINGS, 3, 3))

    def test_a_one_column_file_with_semicolons_in_its_cells_is_one_column(self):
        # #34536, Paul's live file: "Steel rod; 12mm" is a name, not two columns. Read with ";",
        # the heading "Cust Name" was taken for a title row and the first name became the heading.
        content = "Cust Name\r\nMIGTEST Semi; One\r\nMIGTEST Semi; Two\r\nSharma & Sons; Pune\r\n"
        original = self._upload("migtest_onecol.csv", content.encode())

        result = self._start(file_id=original.name)

        self.assertEqual((result["columns"], result["row_count"]), (["Cust Name"], 3))
        self.assertNotIn("header_row", result)
        # every later step reads the session's copy, written with commas: read as written
        rows = self._session_rows(result["session_id"])
        self.assertEqual(
            rows, [["Cust Name"], ["MIGTEST Semi; One"], ["MIGTEST Semi; Two"], ["Sharma & Sons; Pune"]]
        )

    def test_a_csv_read_as_windows_1252_says_so(self):
        # #34541: a file that isn't UTF-8 is read by a guess, which the user checks
        original = self._upload(
            "customers.csv", _csv([HEADINGS[:3], ["Crème", "Señor", "£5"]]).encode("cp1252")
        )

        result = self._start(file_id=original.name)

        self.assertEqual(result["sample_rows"][0][:3], ["Crème", "Señor", "£5"])
        self.assertIn("windows-1252", result["note"])
        steps = frappe.get_all(
            "FAC Import Session Step", filters={"parent": result["session_id"]}, pluck="message"
        )
        self.assertTrue(any("windows-1252" in message for message in steps), steps)

    def test_a_single_value_over_two_columns_is_asked_about(self):
        # #34536: "Cust Name" over rows of two values is a title only by a guess; it may be the
        # heading of a one-column file whose cells hold the delimiter. The user is asked.
        original = self._upload("names.csv", b"Cust Name\r\nAcme;Pune\r\nRavi;Delhi\r\n")

        response = self._start_fails("header_row", file_id=original.name)

        self.assertEqual(response["result"]["header_row_guess"], 2)

    def test_headings_on_row_1_are_read_as_before(self):
        original = self._upload("customers.csv", _csv([HEADINGS, ["A", "Retail", "India"]]).encode())

        result = self._start(file_id=original.name)

        self.assertEqual(result["columns"], HEADINGS)
        self.assertNotIn("header_row", result)
        self.assertNotIn("note", result)

    def test_rows_above_the_headings_that_hold_several_values_are_asked_about(self):
        # "Company: Acme / Period: ..." could be a heading row too: guessing may read the wrong one.
        rows = [["Company", "Acme Traders"], ["Period", "2026-27"], HEADINGS, ["A", "Retail", "India"]]
        original = self._upload("customers.csv", _csv(rows).encode())

        response = self._start_fails("header_row", file_id=original.name)

        result = response["result"]
        self.assertEqual(
            result["first_rows"][:3], [["Company", "Acme Traders"], ["Period", "2026-27"], HEADINGS]
        )
        self.assertEqual(result["header_row_guess"], 3)
        self.assertEqual(self._new_sessions(), 0)
        self.assertEqual(self.new_files(), {original.name})

    def test_header_row_names_the_heading_row(self):
        rows = [["Company", "Acme Traders"], ["Period", "2026-27"], HEADINGS, ["A", "Retail", "India"]]
        original = self._upload("customers.csv", _csv(rows).encode())

        result = self._start(file_id=original.name, header_row=3)

        self.assertEqual((result["columns"], result["row_count"]), (HEADINGS, 1))
        self.assertEqual(self._session_rows(result["session_id"])[0], HEADINGS)

    def test_header_row_on_a_blank_row_is_refused(self):
        original = self._upload("customers.xlsx", _xlsx(_tally_rows(2)), XLSX_MIME)

        self._start_fails("Row 2", file_id=original.name, header_row=2)

        self.assertEqual(self._new_sessions(), 0)

    # -- #34404: the text's encoding and delimiter -----------------------------------------------

    def test_a_utf16_tab_separated_file_is_read(self):
        # Excel's "Save as Unicode Text": UTF-16 with a byte-order mark, tab-separated.
        rows = [HEADINGS[:3], ["Müller GmbH", "Retail", "Deutschland"], ["東京商事", "Retail", "Japan"]]
        for codec, bom in (("utf-16-le", codecs.BOM_UTF16_LE), ("utf-16-be", codecs.BOM_UTF16_BE)):
            with self.subTest(codec=codec):
                original = self._upload(f"customers-{codec}.csv", bom + _csv(rows, "\t").encode(codec))

                result = self._start(file_id=original.name)

                self.assertEqual(result["columns"], HEADINGS[:3])
                self.assertEqual(result["sample_rows"], rows[1:])
                self.assertEqual(self._session_rows(result["session_id"]), rows)

    def test_a_semicolon_separated_file_is_read(self):
        # Europe's Excel and some accounting packages: a comma inside a value stays in it.
        rows = [HEADINGS[:3], ["Acme, Inc", "Retail", "France"], ["Zeta SA", "Retail", "Belgique"]]
        original = self._upload("customers.csv", _csv(rows, ";").encode())

        result = self._start(file_id=original.name)

        self.assertEqual((result["columns"], result["sample_rows"]), (HEADINGS[:3], rows[1:]))

    def test_a_pipe_separated_file_is_read(self):
        rows = [HEADINGS[:3], ["Acme", "Retail", "India"]]
        original = self._upload("customers.csv", _csv(rows, "|").encode())

        self.assertEqual(self._start(file_id=original.name)["columns"], HEADINGS[:3])

    def test_a_utf8_byte_order_mark_is_not_part_of_the_first_heading(self):
        original = self._upload("customers.csv", _csv([HEADINGS[:3], ["A", "B", "C"]]).encode("utf-8-sig"))

        self.assertEqual(self._start(file_id=original.name)["columns"][0], "Cust Name")

    def test_a_preset_reads_a_utf16_export_too(self):
        # The presets read the same files, through their own CSV reader.
        from frappe_assistant_core.utils import import_presets

        original = self._upload(
            "daybook.csv", codecs.BOM_UTF16_LE + _csv(_tally_rows(2), "\t").encode("utf-16-le")
        )

        rows = import_presets.read_heads(original)[0].rows

        self.assertEqual([list(row) for row in rows[2:4]], [HEADINGS, _tally_rows(1)[3]])

    # -- #34405: the session's own copy ------------------------------------------------------

    def test_the_session_reads_its_own_private_copy_of_the_sheet(self):
        original = self._upload("customers.xlsx", _xlsx(_tally_rows(3)), XLSX_MIME)

        session_id = self._start(file_id=original.name)["session_id"]

        doc = frappe.get_doc("FAC Import Session", session_id)
        self.assertEqual(
            (doc.original_file, doc.file_name, doc.file_source),
            (original.name, "customers.xlsx", "Site File"),
        )
        self.assertNotEqual(doc.source_file, original.name)
        copy = frappe.get_doc("File", doc.source_file)
        self.assertEqual((copy.is_private, copy.owner), (1, self.user))
        self.assertEqual(
            (copy.attached_to_doctype, copy.attached_to_name), ("FAC Import Session", session_id)
        )
        self.assertTrue(copy.file_name.endswith(".csv"))
        self.assertEqual(self.new_files(), {original.name, copy.name})

    def test_repeated_headings_are_made_unique(self):
        rows = [["Name", "Name", "Group"], ["Acme", "Acme Traders", "Retail"]]
        original = self._upload("customers.csv", _csv(rows).encode())

        result = self._start(file_id=original.name)

        self.assertEqual(result["columns"], ["Name", "Name (2)", "Group"])
        self.assertEqual(self._session_rows(result["session_id"])[0], ["Name", "Name (2)", "Group"])

    def test_blank_rows_keep_their_place_in_the_copy(self):
        # A row's number is its line under the headings, as Data Import and the user count it.
        rows = [HEADINGS[:3], ["A", "Retail", "India"], [], ["B", "Retail", "India"], [], []]
        original = self._upload("customers.csv", _csv(rows).encode())

        result = self._start(file_id=original.name)

        self.assertEqual(result["row_count"], 2)
        self.assertEqual(
            self._session_rows(result["session_id"]),
            [HEADINGS[:3], ["A", "Retail", "India"], ["", "", ""], ["B", "Retail", "India"]],
        )

    def test_the_chat_file_stays_held_while_its_session_is_open(self):
        # The model reads a held file through the import tools only, never all its rows (#34003).
        original = self._upload("customers.xlsx", _xlsx(_tally_rows(3)), XLSX_MIME)

        session_id = self._start(file_id=original.name)["session_id"]

        self.assertEqual(import_session.holding_session(original.name), session_id)

    def test_a_copy_with_the_same_bytes_outlives_the_chat_file(self):
        # A clean UTF-8 CSV comes out byte for byte the same: Frappe keeps one file on disk for
        # both, and deletes it only with the last File that holds it.
        content = _csv([HEADINGS[:3], ["A", "Retail", "India"]]).replace("\r\n", "\n").encode()
        original = self._upload("customers.csv", content)
        session_id = self._start(file_id=original.name)["session_id"]

        # What chat retention does to a purged message's attachments (chat/scheduler/retention.py)
        frappe.delete_doc("File", original.name, force=True, ignore_permissions=True)

        self.assertEqual(self._session_rows(session_id), [HEADINGS[:3], ["A", "Retail", "India"]])

    def test_a_corrected_file_is_read_into_a_copy_of_its_own_too(self):
        # dry_run_import links a corrected file the user uploads again (#33994): read the same way.
        from frappe_assistant_core.assistant_core.doctype.fac_import_session.fac_import_session import (
            engine_session,
        )
        from frappe_assistant_core.utils import import_dry_run

        first = self._upload("customers.xlsx", _xlsx(_tally_rows(3)), XLSX_MIME)
        session_id = self._start(file_id=first.name)["session_id"]
        first_copy = frappe.db.get_value("FAC Import Session", session_id, "source_file")
        corrected = self._upload("customers-fixed.xlsx", _xlsx(_tally_rows(4)), XLSX_MIME)

        import_dry_run.link_site_file(engine_session(session_id), frappe.get_doc("File", corrected.name))

        doc = frappe.get_doc("FAC Import Session", session_id)
        self.assertEqual(doc.original_file, corrected.name)
        self.assertNotIn(doc.source_file, (first_copy, corrected.name))
        self.assertEqual(frappe.db.get_value("File", doc.source_file, "attached_to_name"), session_id)
        self.assertEqual(self._session_rows(session_id), [HEADINGS] + _tally_rows(4)[3:])
        # the copy it replaced, which no Data Import read, doesn't stay on disk (#34539)
        self.assertFalse(frappe.db.exists("File", first_copy))

    # -- #34539: a session's copies don't outlive retention ------------------------------------

    def _ended_session(self, days_ago=0):
        """A session whose import ended ``days_ago`` days ago, with its copy attached."""
        session_id = self._start(
            file_id=self._upload("customers.csv", _csv([HEADINGS[:3], ["A", "B", "C"]]).encode()).name
        )["session_id"]
        frappe.db.set_value(
            "FAC Import Session",
            session_id,
            {
                "status": "Completed",
                "modified": frappe.utils.add_days(frappe.utils.now_datetime(), -days_ago),
            },
            update_modified=False,
        )
        return session_id

    def _files_of(self, session_id):
        return frappe.get_all(
            "File", filters={"attached_to_doctype": "FAC Import Session", "attached_to_name": session_id}
        )

    def test_retention_deletes_an_ended_sessions_files_and_keeps_the_session(self):
        old, recent = self._ended_session(days_ago=400), self._ended_session()
        still_open = self._start(
            file_id=self._upload("open.csv", _csv([HEADINGS[:3], ["D", "E", "F"]]).encode()).name
        )["session_id"]
        frappe.set_user("Administrator")
        frappe.db.set_value(
            "FAC Import Session",
            still_open,
            "modified",
            frappe.utils.add_days(frappe.utils.now_datetime(), -400),
            update_modified=False,
        )

        self.run_retention_on(old, recent, still_open)

        self.assertFalse(self._files_of(old))
        self.assertEqual(frappe.get_doc("FAC Import Session", old).steps[-1].step, "Retention")
        self.assertTrue(self._files_of(recent))
        self.assertTrue(self._files_of(still_open))  # not ended: the user may carry on with it

    def test_retention_cancels_an_abandoned_failed_session(self):
        # #34541: a Failed session is held for a retry, but nothing ended one nobody came back to
        session_id = self._ended_session(days_ago=400)
        frappe.set_user("Administrator")
        frappe.db.set_value("FAC Import Session", session_id, "status", "Failed", update_modified=False)

        self.run_retention_on(session_id)

        self.assertEqual(frappe.db.get_value("FAC Import Session", session_id, "status"), "Cancelled")
        self.assertFalse(self._files_of(session_id))

    def test_the_retention_tests_leave_the_sites_own_sessions(self):
        # #34606: they purged every ended session on the site. The rollback brings the rows back,
        # not the files on disk, so a user's session was left pointing at files that were gone.
        theirs = self._ended_session(days_ago=400)
        on_disk = [frappe.get_doc("File", f.name).get_full_path() for f in self._files_of(theirs)]

        self.test_retention_deletes_an_ended_sessions_files_and_keeps_the_session()
        self.test_retention_cancels_an_abandoned_failed_session()

        self.assertTrue(self._files_of(theirs))
        self.assertTrue(on_disk)
        self.assertTrue(all(os.path.exists(path) for path in on_disk))

    def test_a_personal_data_deletion_deletes_the_users_session_files(self):
        from frappe_assistant_core.utils import import_retention

        session_id = self._ended_session()
        frappe.set_user("Administrator")
        # What Frappe's Personal Data Deletion Request is when it ends: it only redacts text, so
        # the files with the user's customers in them would stay.
        request = frappe._dict(
            doctype="Personal Data Deletion Request", status="Deleted", email=self.user, name="anon"
        )

        import_retention.purge_user_sessions(request, "on_update")

        self.assertFalse(self._files_of(session_id))

    def test_a_corrected_file_is_read_on_the_sessions_header_row_when_the_guess_misses(self):
        # #34541: link_site_file guessed the headings again, and a corrected file whose title row
        # holds several values was read from that row ("columns don't match")
        from frappe_assistant_core.assistant_core.doctype.fac_import_session.fac_import_session import (
            engine_session,
        )
        from frappe_assistant_core.utils import import_dry_run

        session_id = self._start(
            file_id=self._upload("customers.xlsx", _xlsx(_tally_rows(3)), XLSX_MIME).name
        )["session_id"]
        corrected_rows = _tally_rows(3)
        corrected_rows[0] = ["Customer Master", "exported", "from", "Tally Prime", "on", "26-10-2026"]
        corrected = self._upload("customers-fixed.xlsx", _xlsx(corrected_rows), XLSX_MIME)

        import_dry_run.link_site_file(engine_session(session_id), frappe.get_doc("File", corrected.name))

        self.assertEqual(self._session_rows(session_id)[0], HEADINGS)

    def test_a_copy_is_never_named_like_a_file_the_session_writes(self):
        # The failed-rows CSV (#33994) is replaced by its name, and it comes back corrected.
        original = self._upload(
            "IMP-2026-00012-failed-rows.csv", _csv([HEADINGS[:3], ["A", "B", "C"]]).encode()
        )

        session_id = self._start(file_id=original.name)["session_id"]

        copy = frappe.db.get_value("FAC Import Session", session_id, "source_file")
        self.assertEqual(
            frappe.db.get_value("File", copy, "file_name"), "IMP-2026-00012-failed-rows - session copy.csv"
        )

    def test_the_file_the_user_gave_counts_as_the_sessions_file(self):
        # Passed again to dry_run_import, it is no new file: nothing is linked or copied again.
        from frappe_assistant_core.plugins.migration.tools.dry_run_import import _is_sessions_file

        original = self._upload("customers.xlsx", _xlsx(_tally_rows(3)), XLSX_MIME)
        other = self._upload("other.xlsx", _xlsx(_tally_rows(5)), XLSX_MIME)
        doc = frappe.get_doc("FAC Import Session", self._start(file_id=original.name)["session_id"])

        self.assertTrue(_is_sessions_file(doc, original))
        self.assertTrue(_is_sessions_file(doc, frappe.get_doc("File", doc.source_file)))
        self.assertFalse(_is_sessions_file(doc, other))

    def test_a_file_only_in_the_chat_is_refused_with_how_to_upload_it(self):
        response = self._start_fails(
            "upload", file_name="customers.xlsx", columns=["Customer Name"], row_count=15
        )

        self.assertNotIn("row_count", response["error"])
        self.assertEqual(self._new_sessions(), 0)

    def test_a_start_refused_after_reading_leaves_no_copy(self):
        original = self._upload(
            "customers.csv", _csv([HEADINGS[:3], ["A", "B", "C"], ["D", "E", "F"]]).encode()
        )

        with patch.object(import_session, "max_import_rows", autospec=True, return_value=1):
            self._start_fails("more than the 1 one import may have", file_id=original.name)

        self.assertEqual(self.new_files(), {original.name})
        self.assertEqual(self._new_sessions(), 0)


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Customer")
class TestFileIntakeImport(BaseAssistantTest):
    """The whole way through, while the chat's file is deleted by chat retention mid-migration."""

    GROUP = "FAC Intake Group"

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.registry = get_tool_registry()
        self.track_test_files()
        self.tag = frappe.generate_hash(length=6)
        if not frappe.db.exists("Customer Group", self.GROUP):
            frappe.get_doc(
                {
                    "doctype": "Customer Group",
                    "customer_group_name": self.GROUP,
                    "parent_customer_group": "All Customer Groups",
                    "is_group": 0,
                }
            ).insert()

    def tearDown(self):
        frappe.set_user("Administrator")
        self.delete_test_files()
        super().tearDown()

    def _run(self, tool_name, arguments):
        response = self.registry.get_tool(tool_name)._safe_execute(arguments)
        self.assertTrue(response["success"], response)
        return response["result"]

    def test_the_import_carries_on_after_chat_retention_deletes_the_file(self):
        names = [f"Intake {i} {self.tag}" for i in range(1, 4)]
        rows = [["Customer Master - exported from Tally Prime"], [], ["Cust Name", "Group", "Cust Name"]]
        rows += [[name, self.GROUP, "duplicate heading, not imported"] for name in names]
        content = b"\xff\xfe" + _csv(rows, "\t").encode("utf-16-le")
        with patch(
            "frappe_assistant_core.chat.api.settings.access.can_use_faco",
            return_value={"can_use": True},
        ):
            upload = upload_message_file(
                file_data=base64.b64encode(content).decode(), file_name="tally.csv", content_type=CSV_MIME
            )
        original = upload["file"]["name"]

        session = self._run("start_import_session", {"file_id": original})["session_id"]
        self._run(
            "set_column_mapping",
            {
                "session": session,
                "doctype": "Customer",
                "mapping": {
                    "Cust Name": "customer_name",
                    "Group": "customer_group",
                    "Cust Name (2)": "Don't Import",
                },
            },
        )
        # What chat retention does to a purged message's attachments (chat/scheduler/retention.py)
        frappe.delete_doc("File", original, force=True, ignore_permissions=True)

        checked = self._run("dry_run_import", {"session": session})
        self.assertEqual((checked["ready"], checked["failed"]), (3, 0), checked)
        from frappe_assistant_core.tests.test_import_run import approval_card

        self._run("start_import", approval_card(session, checked, "Customer", "Insert New Records"))

        imported = frappe.get_all("Customer", {"customer_name": ["in", names]}, pluck="customer_name")
        self.assertEqual(sorted(imported), sorted(names))
