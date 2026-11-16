"""
Tests for import sessions (#33988): the FAC Import Session doctype and the
start_import_session tool.

A session is the server-side record of one file moving through a data migration:
its details, the mapping, the fixes, the validation results and a log of every
step. The sheet is read once into a private copy the session owns (#34405).
"""

import base64
import datetime
import io
import json
import unittest
from unittest.mock import patch

import frappe
from openpyxl import Workbook

from frappe_assistant_core.chat.api.chat.helpers import _attach_files_to_message
from frappe_assistant_core.chat.api.settings.uploads import upload_message_file
from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import FACChatMessage
from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.tests.base_test import BaseAssistantTest

CSV_CONTENT = b"Customer Name,Customer Group,Territory\n" + b"".join(
    f"Customer {i},Retail,India\n".encode() for i in range(1, 26)
)


def _xlsx_bytes(sheets: dict) -> bytes:
    """Build an .xlsx in memory. ``sheets`` maps sheet name -> list of rows."""
    wb = Workbook()
    wb.remove(wb.active)
    for title, rows in sheets.items():
        ws = wb.create_sheet(title)
        for row in rows:
            ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestImportSession(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.registry = get_tool_registry()
        # A plain desk user: owns the files they upload, holds no import rights.
        self.user = self.make_desk_user("importer")
        self.assert_cannot(self.user, "create", "Data Import")
        frappe.set_user(self.user)
        self.track_test_files()
        self.sessions_before = frappe.db.count("FAC Import Session")

    def tearDown(self):
        frappe.local.ar_session_id = None
        frappe.set_user("Administrator")
        self.delete_test_files()
        super().tearDown()

    # -- helpers ---------------------------------------------------------------

    def _upload(self, file_name: str, content: bytes):
        """A private File owned by the current user, as a chat upload creates."""
        return frappe.get_doc(
            {"doctype": "File", "file_name": file_name, "content": content, "is_private": 1}
        ).insert()

    def _chat_upload(self, file_name: str, content: bytes) -> dict:
        """A file as a user sends it in chat: through upload_message_file, then linked to their
        FAC Chat Message, as the composer does. Returns the upload's ``file`` reply."""
        message = FACChatMessage.create_message(
            session_id=f"import-session-{frappe.generate_hash(length=8)}",
            role="user",
            content="Here is the file to import",
        )
        # The one thing not built here: the FAC Chat gate (enable_fac_chat, registration and a
        # seat), which a test site doesn't have. Everything the upload does after it is real.
        with patch(
            "frappe_assistant_core.chat.api.settings.access.can_use_faco", return_value={"can_use": True}
        ):
            uploaded = upload_message_file(
                file_data=base64.b64encode(content).decode(), file_name=file_name, content_type="text/csv"
            )
        self.assertEqual(_attach_files_to_message([uploaded["file"]["file_url"]], message.name), 1)
        return uploaded["file"]

    def _run(self, tool_name, arguments):
        """Call a tool the way the MCP endpoint does: through _safe_execute."""
        return self.registry.get_tool(tool_name)._safe_execute(arguments)

    def _start(self, **arguments):
        response = self._run("start_import_session", arguments)
        self.assertTrue(response["success"], response)
        return response["result"]

    def _start_fails(self, expected_text=None, **arguments):
        response = self._run("start_import_session", arguments)
        self.assertFalse(response["success"], response)
        if expected_text:
            self.assertIn(expected_text, response["error"])
        return response

    def _new_sessions(self):
        """Sessions created since this test began (the rollback runs per class, not per test)."""
        return frappe.db.count("FAC Import Session") - self.sessions_before

    # -- registration ------------------------------------------------------------

    def test_tool_is_registered_in_migration_plugin(self):
        from frappe_assistant_core.plugins.migration.plugin import MigrationPlugin

        self.assertIn("start_import_session", MigrationPlugin().get_tools())

    def test_tool_is_classified_read_only(self):
        # It writes only the session, never business data, so it must not raise an approval
        # card. What decides that is what the site tells its clients: tools/list's readOnlyHint
        # and the chat's tool list, both resolved from the site's tool category. The category is
        # resolved as a site with no stored FAC Tool Configuration row for it does (a stored row
        # is an administrator's choice and wins), so the test follows the tool's own code.
        from frappe_assistant_core.api.fac_endpoint import _build_tool_registry
        from frappe_assistant_core.chat.api.tools import list_available_tools

        frappe.db.delete("FAC Tool Configuration", {"tool_name": "start_import_session"})

        advertised = _build_tool_registry()["start_import_session"]
        listed = next(t for t in list_available_tools()["tools"] if t["name"] == "start_import_session")

        self.assertIs(advertised["annotations"]["readOnlyHint"], True)
        self.assertTrue(listed["read_only"], listed)
        self.assertFalse(listed["default_requires_approval"], listed)

    # -- criterion 1: open a session, show sheets, columns and row counts -----------

    def test_csv_opens_a_session_with_columns_count_and_samples(self):
        file_doc = self._upload("customers.csv", CSV_CONTENT)

        result = self._start(file_url=file_doc.file_url)

        self.assertEqual(result["columns"], ["Customer Name", "Customer Group", "Territory"])
        self.assertEqual(result["row_count"], 25)
        self.assertEqual(len(result["sample_rows"]), 10)
        self.assertEqual(result["sample_rows"][0], ["Customer 1", "Retail", "India"])
        # a CSV's one sheet has no name, and its columns and count are above already
        self.assertNotIn("sheet", result)
        self.assertNotIn("sheets", result)
        doc = frappe.get_doc("FAC Import Session", result["session_id"])
        self.assertEqual(doc.original_file, file_doc.name)
        self.assertEqual(doc.user, self.user)
        self.assertEqual(doc.status, "File Read")

    def test_session_records_the_file_name_and_when_it_started(self):
        before = frappe.utils.now_datetime().replace(microsecond=0)

        result = self._start(file_id=self._upload("customers.csv", CSV_CONTENT).name)

        doc = frappe.get_doc("FAC Import Session", result["session_id"])
        self.assertEqual(doc.file_name, "customers.csv")
        self.assertGreaterEqual(frappe.utils.get_datetime(doc.started_on), before)
        list_fields = [f.fieldname for f in frappe.get_meta("FAC Import Session").fields if f.in_list_view]
        self.assertIn("file_name", list_fields)
        self.assertIn("started_on", list_fields)

    def test_description_names_the_next_tools(self):
        # Claude and ChatGPT may never read the skill; every client gets the description.
        description = self.registry.get_tool("start_import_session").description

        self.assertIn("get_import_schema", description)
        self.assertIn("set_column_mapping", description)

    def test_session_name_follows_the_imp_year_series(self):
        file_doc = self._upload("customers.csv", CSV_CONTENT)

        session_id = self._start(file_url=file_doc.file_url)["session_id"]

        self.assertRegex(session_id, rf"^IMP-{datetime.date.today().year}-\d{{5}}$")

    def test_only_ten_sample_rows_reach_the_conversation(self):
        file_doc = self._upload("customers.csv", CSV_CONTENT)

        result = self._start(file_url=file_doc.file_url)

        self.assertNotIn("Customer 11", frappe.as_json(result))

    def test_workbook_lists_every_sheet_and_uses_the_first_with_data(self):
        content = _xlsx_bytes(
            {
                "Notes": [],
                "Customers": [["Name", "Group"], ["A", "Retail"], ["B", "Retail"]],
                "Old": [["Code"], ["X"]],
            }
        )
        file_doc = self._upload("export.xlsx", content)

        result = self._start(file_url=file_doc.file_url)

        self.assertEqual(result["sheet"], "Customers")
        self.assertEqual(
            [(s["name"], s["row_count"]) for s in result["sheets"]],
            [("Notes", 0), ("Customers", 2), ("Old", 1)],
        )
        stored = frappe.parse_json(frappe.db.get_value("FAC Import Session", result["session_id"], "sheets"))
        self.assertEqual([s["name"] for s in stored], ["Notes", "Customers", "Old"])

    def test_sheet_argument_chooses_the_sheet(self):
        content = _xlsx_bytes({"Customers": [["Name"], ["A"]], "Items": [["Code"], ["I-1"]]})
        file_doc = self._upload("export.xlsx", content)

        result = self._start(file_url=file_doc.file_url, sheet="Items")

        self.assertEqual(result["sheet"], "Items")
        self.assertEqual(result["columns"], ["Code"])

    def test_unknown_sheet_lists_the_sheets_that_exist(self):
        file_doc = self._upload("export.xlsx", _xlsx_bytes({"Customers": [["Name"], ["A"]]}))

        self._start_fails("Customers", file_url=file_doc.file_url, sheet="Suppliers")

        self.assertEqual(self._new_sessions(), 0)

    def test_file_without_rows_is_refused(self):
        file_doc = self._upload("empty.csv", b"Name,Group\n")

        self._start_fails("no rows", file_url=file_doc.file_url)

        self.assertEqual(self._new_sessions(), 0)

    def test_unsupported_file_type_is_refused(self):
        file_doc = self._upload("notes.txt", b"hello")

        self._start_fails(".csv, .xlsx or .xls", file_url=file_doc.file_url)

        self.assertEqual(self._new_sessions(), 0)

    def test_excel_dates_and_whole_numbers_read_as_plain_text(self):
        content = _xlsx_bytes({"Stock": [["Date", "Qty"], [datetime.datetime(2026, 4, 1), 12.0]]})
        file_doc = self._upload("stock.xlsx", content)

        result = self._start(file_url=file_doc.file_url)

        self.assertEqual(result["sample_rows"][0], ["2026-04-01", "12"])

    # -- the session's own copy of the sheet (#34405) ------------------------------------------

    def test_a_site_file_is_read_into_one_private_copy_for_the_session(self):
        file_doc = self._upload("customers.csv", CSV_CONTENT)

        session_id = self._start(file_url=file_doc.file_url)["session_id"]

        doc = frappe.get_doc("FAC Import Session", session_id)
        self.assertEqual(self.new_files(), {file_doc.name, doc.source_file})
        self.assertEqual((doc.original_file, doc.file_source), (file_doc.name, "Site File"))

    def test_no_row_of_the_file_is_stored_on_the_session(self):
        # The session is the audit record; the rows stay in the file. Samples go to the
        # assistant in the reply only.
        file_doc = self._upload("customers.csv", CSV_CONTENT)

        result = self._start(file_url=file_doc.file_url)

        self.assertIn(["Customer 1", "Retail", "India"], result["sample_rows"])
        stored = frappe.db.get_value("FAC Import Session", result["session_id"], "sheets")
        self.assertEqual(
            frappe.parse_json(stored),
            [{"name": None, "columns": ["Customer Name", "Customer Group", "Territory"], "row_count": 25}],
        )
        self.assertNotIn("Customer 1", stored)

    # -- a file that stays in the chat (Claude, ChatGPT) -----------------------------------

    def test_a_file_only_in_the_chat_is_refused_until_it_is_uploaded(self):
        # Its rows would reach the session only through the model reading them all (#34405).
        response = self._start_fails(
            "upload",
            file_name="customers.csv",
            columns=["Name"],
            row_count=15,
            sample_rows=[["Grant Plastics"]],
        )

        self.assertNotIn("Grant Plastics", frappe.as_json(response))
        self.assertEqual(self._new_sessions(), 0)

    def test_neither_a_file_id_nor_a_link_is_refused(self):
        self._start_fails("file_id")

    # -- criterion 4: permission on the target doctype, before any work -------------------

    def test_target_without_create_permission_is_refused_before_reading(self):
        file_doc = self._upload("currencies.csv", b"Currency Name\nXYZ\n")

        self._start_fails(
            "permission to create Currency", file_url=file_doc.file_url, target_doctype="Currency"
        )

        self.assertEqual(self._new_sessions(), 0)
        self.assertEqual(self.new_files(), {file_doc.name})

    def test_target_without_import_permission_is_refused(self):
        # Any desk user may create a Contact (role All, if owner); only System
        # Manager holds Import on it.
        file_doc = self._upload("contacts.csv", b"First Name\nAsha\n")

        self._start_fails("Import permission", file_url=file_doc.file_url, target_doctype="Contact")

        self.assertEqual(self._new_sessions(), 0)

    def test_target_that_cannot_be_imported_is_refused(self):
        file_doc = self._upload("todo.csv", b"Description\nCall\n")

        self._start_fails("can't be imported", file_url=file_doc.file_url, target_doctype="ToDo")

    def test_permitted_target_is_stored_on_the_session(self):
        frappe.set_user("Administrator")
        file_doc = self._upload("currencies.csv", b"Currency Name\nXYZ\n")

        session_id = self._start(file_url=file_doc.file_url, target_doctype="Currency")["session_id"]

        doc = frappe.get_doc("FAC Import Session", session_id)
        self.assertEqual(doc.target_doctype, "Currency")
        self.assertEqual(doc.import_type, "Insert New Records")

    # -- file access -----------------------------------------------------------------------

    def test_another_users_private_file_cannot_be_read(self):
        frappe.set_user(self.make_desk_user("other"))
        theirs = self._upload("theirs.csv", CSV_CONTENT)
        frappe.set_user(self.user)
        self.assert_cannot(self.user, "read", "File", theirs.name)

        response = self._start_fails(file_url=theirs.file_url)

        self.assertNotIn("Customer 1", frappe.as_json(response))
        self.assertEqual(self._new_sessions(), 0)

    def test_a_file_uploaded_in_file_manager_opens_by_its_id(self):
        file_doc = self._upload("customers.csv", CSV_CONTENT)

        result = self._start(file_id=file_doc.name)

        self.assertEqual((result["file_name"], result["row_count"]), ("customers.csv", 25))
        self.assertEqual(
            frappe.db.get_value("FAC Import Session", result["session_id"], "original_file"), file_doc.name
        )

    def test_another_users_private_file_cannot_be_read_by_its_id(self):
        frappe.set_user(self.make_desk_user("other"))
        theirs = self._upload("theirs.csv", CSV_CONTENT)
        frappe.set_user(self.user)
        self.assert_cannot(self.user, "read", "File", theirs.name)

        response = self._start_fails("don't have access", file_id=theirs.name)

        self.assertNotIn("Customer 1", frappe.as_json(response))
        self.assertEqual(self._new_sessions(), 0)

    def test_an_unknown_id_or_a_folder_reads_the_same_as_a_file_the_user_cannot_read(self):
        unknown = self._start_fails("don't have access", file_id="no-such-file")
        folder = self._start_fails("don't have access", file_id="Home")

        self.assertEqual(unknown["error"], folder["error"])
        self.assertEqual(self._new_sessions(), 0)

    def test_a_file_shared_with_the_user_can_be_read_by_its_id(self):
        # Frappe's own rule decides who may read a file: here, a share.
        frappe.set_user(self.make_desk_user("owner"))
        theirs = self._upload("shared.csv", CSV_CONTENT)
        frappe.set_user("Administrator")
        self.assert_cannot(self.user, "read", "File", theirs.name)
        frappe.share.add("File", theirs.name, self.user, read=1)
        frappe.set_user(self.user)

        self.assertEqual(self._start(file_id=theirs.name)["row_count"], 25)

    def test_file_id_and_file_url_of_the_same_file_are_taken(self):
        # FACO often passes both from the chat attachment: one file, said twice, isn't a mistake.
        file_doc = self._upload("customers.csv", CSV_CONTENT)

        self.assertEqual(self._start(file_id=file_doc.name, file_url=file_doc.file_url)["row_count"], 25)

    def test_file_id_and_file_url_of_different_files_are_refused(self):
        file_doc = self._upload("customers.csv", CSV_CONTENT)
        other = self._upload("suppliers.csv", b"Supplier Name\nSupplier 1\n")  # other content: another file

        self._start_fails("different files", file_id=file_doc.name, file_url=other.file_url)

        self.assertEqual(self._new_sessions(), 0)

    # -- a file sent in chat: the path production takes ------------------------------------------

    def test_a_file_sent_in_chat_opens_a_session_by_its_url_and_by_its_id(self):
        # Unique bytes: Frappe content-addresses uploads, so a body seen before would share a file.
        content = CSV_CONTENT + f"Customer 26 {frappe.generate_hash(length=8)},Retail,India\n".encode()
        upload = self._chat_upload("customers.csv", content)
        file_doc = frappe.get_doc("File", upload["name"])
        self.assertEqual(file_doc.attached_to_doctype, "FAC Chat Message")
        self.assertTrue(file_doc.is_private)

        by_url = self._start(file_url=upload["file_url"])
        by_id = self._start(file_id=upload["name"], file_url=upload["file_url"])

        copies = set()
        for result in (by_url, by_id):
            self.assertEqual((result["file_name"], result["row_count"]), ("customers.csv", 26))
            self.assertEqual(result["columns"], ["Customer Name", "Customer Group", "Territory"])
            doc = frappe.get_doc("FAC Import Session", result["session_id"])
            self.assertEqual(
                (doc.original_file, doc.user, doc.status), (upload["name"], self.user, "File Read")
            )
            copies.add(doc.source_file)
        # Each session reads its own copy of the chat's file (#34405): chat retention may delete it.
        self.assertEqual(self.new_files(), {upload["name"], *copies})
        self.assertNotIn(upload["name"], copies)

    def test_another_users_chat_file_cannot_open_a_session(self):
        frappe.set_user(self.make_desk_user("other"))
        unique = f"{frappe.generate_hash(length=8)},,\n".encode()
        theirs = self._chat_upload("theirs.csv", CSV_CONTENT + unique)
        frappe.set_user(self.user)
        self.assert_cannot(self.user, "read", "File", theirs["name"])

        by_url = self._start_fails(file_url=theirs["file_url"])
        by_id = self._start_fails("don't have access", file_id=theirs["name"])

        self.assertNotIn("Customer 1", frappe.as_json([by_url, by_id]))
        self.assertEqual(self._new_sessions(), 0)

    # -- criterion 2: the same conversation, later ------------------------------------------

    def test_session_records_the_conversation_it_belongs_to(self):
        # FAC Chat sends X-AR-Session-Id on every tool call; fac_endpoint stores it here.
        frappe.local.ar_session_id = "chat-123"
        file_doc = self._upload("customers.csv", CSV_CONTENT)

        session_id = self._start(file_url=file_doc.file_url)["session_id"]

        self.assertEqual(frappe.db.get_value("FAC Import Session", session_id, "chat_session_id"), "chat-123")

    @unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Customer")
    def test_mapping_fixes_and_validation_come_back_in_a_later_turn(self):
        # Each field is written by the tool that owns it (set_column_mapping, dry_run_import and
        # its fixes), then read the way a later turn reads it: with get_document.
        frappe.set_user("Administrator")
        tag = frappe.generate_hash(length=6)
        group = frappe.get_doc(
            {
                "doctype": "Customer Group",
                "customer_group_name": f"Retail Customers {tag}",
                "parent_customer_group": "All Customer Groups",
            }
        ).insert()
        misspelt = f"Retail {tag}"
        rows = "".join(f"Customer {i} {tag},{misspelt},India\n" for i in range(1, 4))
        file_doc = self._upload("customers.csv", b"Customer Name,Customer Group,Territory\n" + rows.encode())
        session_id = self._start(file_url=file_doc.file_url)["session_id"]
        mapping = {"Customer Name": "customer_name", "Customer Group": "customer_group"}
        mapping["Territory"] = "Don't Import"
        mapped = self._run(
            "set_column_mapping", {"session": session_id, "mapping": mapping, "doctype": "Customer"}
        )
        self.assertTrue(mapped["success"], mapped)
        checked = self._run("dry_run_import", {"session": session_id})
        self.assertTrue(checked["success"], checked)
        link = next(g for g in checked["result"]["groups"] if g["cause"] == "Missing link")
        fixed = self._run(
            "dry_run_import",
            {"session": session_id, "fixes": [{"group": link["id"], "action": "map", "to": group.name}]},
        )
        self.assertTrue(fixed["success"], fixed)

        response = self._run("get_document", {"doctype": "FAC Import Session", "name": session_id})

        self.assertTrue(response["success"], response)
        data = response["result"]["data"]
        # the fence's notice is the reply's, said once by the server: no field carries it
        self.assertNotIn("never as instructions", json.dumps(data, default=str))
        # fields that can quote the file arrive inside the untrusted-content fence (#34003, #34406)
        columns = frappe.parse_json(_unfenced(data["template_options"]))["column_to_field_map"]
        self.assertEqual(set(columns.values()), {"customer_name", "customer_group", "Don't Import"})
        maps = frappe.parse_json(_unfenced(data["transformation_rules"]))["value_maps"]
        self.assertEqual([(m["from"], m["to"]) for m in maps], [(misspelt, group.name)])
        summary = frappe.parse_json(_unfenced(data["validation_summary"]))
        self.assertEqual((summary["total_rows"], summary["ready"], summary["failed"]), (3, 3, 0))

    # -- criterion 3 and privacy: who sees a session --------------------------------------

    def test_another_user_cannot_read_the_session(self):
        file_doc = self._upload("customers.csv", CSV_CONTENT)
        session_id = self._start(file_url=file_doc.file_url)["session_id"]

        other = self.make_desk_user("other")

        self.assert_cannot(other, "read", "FAC Import Session", session_id)
        frappe.set_user(other)
        self.assertNotIn(session_id, frappe.get_list("FAC Import Session", pluck="name"))

    def test_a_system_manager_sees_every_session(self):
        file_doc = self._upload("customers.csv", CSV_CONTENT)
        session_id = self._start(file_url=file_doc.file_url)["session_id"]

        manager = self.make_throwaway_user("manager", roles=("System Manager",))

        self.assertTrue(frappe.has_permission("FAC Import Session", "read", session_id, user=manager))

    # -- audit ---------------------------------------------------------------------------------

    def test_reading_the_file_is_logged_as_the_first_step(self):
        file_doc = self._upload("customers.csv", CSV_CONTENT)

        session_id = self._start(file_url=file_doc.file_url)["session_id"]

        steps = frappe.get_doc("FAC Import Session", session_id).steps
        self.assertEqual([(s.step, s.outcome, s.user) for s in steps], [("Read File", "Success", self.user)])
        self.assertIn("25 rows", steps[0].message)


def _unfenced(value):
    """What fence_fields wrapped, which must be fenced."""
    from frappe_assistant_core.utils.untrusted_output import FENCE, unfenced

    assert value.startswith(f"<{FENCE}>") and value.endswith(f"</{FENCE}>"), value
    return unfenced(value)
