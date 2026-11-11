# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
get_import_schema and set_column_mapping (#33989).

The schema has to stay short (get_doctype_info's full metadata is cut off before the model
reads it, which is how a live test missed Delivery Note's po_no), and every mapping saved
has to be one Frappe's Data Import accepts as it stands, since #33993 copies it across.

Sessions are opened the way production opens them: a file is uploaded and
start_import_session reads it. Tools are called through _safe_execute, as the MCP
endpoint calls them.
"""

import json
import unittest

import frappe
from frappe.core.doctype.data_import.importer import get_df_for_column_header

from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.tool_category_detector import detect_tool_category

CONTACTS_CSV = "First Name,Last Name,E-mail,Mobile,Company,Notes\nAnn,Lee,ann@example.com,98450,Acme,VIP\n"
ADDRESSES_CSV = "Street,Town,Remarks\n12 MG Road,Bengaluru,Head office\n"
# India Compliance on the site, and its GST Settings refusing a sales Item without an HSN/SAC code
HSN_VALIDATED = "india_compliance" in frappe.get_installed_apps() and bool(
    frappe.db.get_single_value("GST Settings", "validate_hsn_code")
)


class ImportToolTestCase(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.registry = get_tool_registry()
        self.track_test_files()

    def tearDown(self):
        frappe.set_user("Administrator")
        self.delete_test_files()
        super().tearDown()

    def _run(self, tool_name, arguments):
        return self.registry.get_tool(tool_name)._safe_execute(arguments)

    def _session(self, csv_text=CONTACTS_CSV, file_name="contacts.csv"):
        """Upload a file as the current user, as a chat upload does, and open its session."""
        # Unique content: Frappe stores identical uploads once.
        content = f"{csv_text}{frappe.generate_hash(length=8)},,,,,\n".encode()
        file_doc = frappe.get_doc(
            {"doctype": "File", "file_name": file_name, "content": content, "is_private": 1}
        ).insert()
        response = self._run("start_import_session", {"file_url": file_doc.file_url})
        self.assertTrue(response["success"], response)
        return response["result"]["session_id"]

    def _map(self, session_id, mapping, **arguments):
        """The tool's own result, successful or not."""
        response = self._run("set_column_mapping", {"session": session_id, "mapping": mapping, **arguments})
        return response["result"]

    @staticmethod
    def _stored_map(session_id):
        doc = frappe.get_doc("FAC Import Session", session_id)
        return (frappe.parse_json(doc.template_options or "{}") or {}).get("column_to_field_map", {})


class TestGetImportSchema(ImportToolTestCase):
    def _schema(self, doctype):
        response = self._run("get_import_schema", {"doctype": doctype})
        return response["result"] if "result" in response else response

    def test_lists_importable_fields_and_child_tables_apart(self):
        schema = self._schema("Contact")

        self.assertTrue(schema["success"], schema.get("error"))
        self.assertIn("first_name", [f["fieldname"] for f in schema["fields"]])
        tables = {t["fieldname"]: t for t in schema["child_tables"]}
        self.assertEqual(tables["email_ids"]["doctype"], "Contact Email")
        email_id = next(f for f in tables["email_ids"]["fields"] if f["fieldname"] == "email_id")
        self.assertTrue(email_id["required"])

    def test_leaves_out_fields_an_import_does_not_set(self):
        meta = frappe.get_meta("Contact")
        for field in self._schema("Contact")["fields"]:
            df = meta.get_field(field["fieldname"])
            self.assertFalse(df.hidden or df.read_only, field["fieldname"])
            self.assertNotIn(df.fieldtype, ("Section Break", "Column Break", "Tab Break", "HTML", "Table"))

    @unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext")
    def test_a_customers_phone_and_email_are_offered_as_importable(self):
        # Frappe 15: on the party itself, typed "Read Only" (fetched from the primary contact);
        # listed as that, the model took them for locked fields and left a file's phone and email
        # out. Frappe 16: ERPNext's import provider takes them in a contacts table instead.
        for doctype in ("Customer", "Supplier"):
            schema = self._schema(doctype)
            fields = {f["fieldname"]: f for f in schema["fields"]}
            contacts = next((t for t in schema.get("child_tables", []) if t["fieldname"] == "contacts"), None)
            if contacts:
                self.assertEqual(contacts["doctype"], "Contact")
                self.assertTrue({"mobile_no", "email_id"} <= {f["fieldname"] for f in contacts["fields"]})
                self.assertFalse({"mobile_no", "email_id"} & set(fields), doctype)
            else:
                for fieldname in ("mobile_no", "email_id"):
                    self.assertEqual(fields[fieldname]["type"], "Data", (doctype, fieldname))
                    self.assertIn("primary contact", fields[fieldname]["note"], (doctype, fieldname))
            self.assertNotIn("Read Only", json.dumps(schema), doctype)

    @unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext")
    def test_delivery_note_includes_po_no_and_stays_short(self):
        schema = self._schema("Delivery Note")

        self.assertIn("po_no", [f["fieldname"] for f in schema["fields"]])
        size = len(json.dumps(schema, default=str))
        full = self._run("get_doctype_info", {"doctype": "Delivery Note"})
        self.assertLess(size, 20000)
        self.assertLess(size, len(json.dumps(full, default=str)) / 3)

    @unittest.skipUnless(HSN_VALIDATED, "needs India Compliance validating HSN/SAC codes")
    def test_an_item_hsn_code_is_required_where_the_site_validates_it(self):
        # India Compliance refuses a sales Item without one; only the dry run said so (e2e finding, #33989).
        hsn = next(f for f in self._schema("Item")["fields"] if f["fieldname"] == "gst_hsn_code")

        self.assertTrue(hsn.get("required"), hsn)
        self.assertIn("India Compliance", hsn["note"])

    @unittest.skipIf(HSN_VALIDATED, "this site validates HSN/SAC codes")
    def test_an_item_hsn_code_is_not_required_where_the_site_does_not_validate_it(self):
        fields = {f["fieldname"]: f for f in self._schema("Item")["fields"]}

        self.assertFalse(fields.get("gst_hsn_code", {}).get("required"))

    def test_doctypes_data_import_refuses_are_refused(self):
        for doctype, reason in (
            ("Contact Email", "child table"),
            ("System Settings", "single settings record"),
            ("Error Log", "Allow Import is turned off"),
            ("Contct", "does not exist"),
        ):
            with self.subTest(doctype=doctype):
                result = self._schema(doctype)
                self.assertFalse(result["success"])
                self.assertIn(reason, result["error"])

    def test_user_without_import_permission_is_told_before_any_work(self):
        user = self.make_desk_user("reader")
        self.assert_cannot(user, "import", "Contact")
        frappe.set_user(user)
        result = self._schema("Contact")
        self.assertFalse(result["success"])
        self.assertRegex(result["error"], r"permission.*Contact")


class TestSetColumnMapping(ImportToolTestCase):
    def test_saves_the_mapping_in_data_import_shape(self):
        session = self._session()
        result = self._map(
            session,
            {
                "First Name": "first_name",
                "Last Name": "Last Name",  # a label works too
                "E-mail": "email_ids.email_id",
                "3": "phone_nos.phone",  # so does a position
                "Notes": "Don't Import",
            },
            doctype="Contact",
        )

        self.assertTrue(result["success"], result)
        self.assertEqual(
            self._stored_map(session),
            {
                "0": "first_name",
                "1": "last_name",
                "2": "email_ids.email_id",
                "3": "phone_nos.phone",
                "5": "Don't Import",
            },
        )
        # Data Import resolves every saved value as it stands.
        for field in self._stored_map(session).values():
            if field != "Don't Import":
                self.assertIsNotNone(get_df_for_column_header("Contact", field), field)

    def test_the_session_moves_to_mapped_and_logs_the_step(self):
        session = self._session()
        result = self._map(session, {"First Name": "first_name"}, doctype="Contact")

        doc = frappe.get_doc("FAC Import Session", session)
        self.assertEqual((result["status"], doc.status, doc.target_doctype), ("Mapped", "Mapped", "Contact"))
        step = doc.steps[-1]
        self.assertEqual((step.step, step.outcome), ("Map Columns", "Success"))
        self.assertEqual(step.message, result["summary"])

    def test_a_column_left_out_is_to_be_shown_to_the_user(self):
        # "State has no direct Customer field, so I'll skip it": dropped unasked, the customers got
        # the default territory.
        result = self._map(
            self._session(), {"First Name": "first_name", "Notes": "Don't Import"}, doctype="Contact"
        )

        self.assertTrue(result["success"], result)
        self.assertEqual(result["not_imported"], ["Notes"])
        self.assertIn("ask the user about them all in one question", result["note"])
        self.assertNotIn("Notes", result["note"])  # FAC's own text names nothing from the file

    def test_a_column_that_only_numbers_the_rows_is_not_asked_about(self):
        # #34415: the user was asked about S.No on a card of its own
        session = self._session(csv_text="S.No,First Name\n1,Asha\n")
        result = self._map(session, {"First Name": "first_name", "S.No": "Don't Import"}, doctype="Contact")

        self.assertEqual(result["not_imported"], ["S.No"])  # still listed
        self.assertNotIn("note", result)

    def test_a_mapping_that_drops_nothing_has_no_note(self):
        result = self._map(self._session(), {"First Name": "first_name"}, doctype="Contact")

        self.assertTrue(result["success"], result)
        self.assertNotIn("note", result)

    def test_a_later_turn_reads_the_mapping_back(self):
        session = self._session()
        self._map(session, {"First Name": "first_name"}, doctype="Contact")

        response = self._run("get_document", {"doctype": "FAC Import Session", "name": session})

        # inside the untrusted-content fence: an opening import keeps the file's text there (#34406)
        from frappe_assistant_core.tests.test_import_session import _unfenced

        options = frappe.parse_json(_unfenced(response["result"]["data"]["template_options"]))
        self.assertEqual(options, {"column_to_field_map": {"0": "first_name"}})

    def test_child_table_fields_are_shown_apart(self):
        result = self._map(
            self._session(), {"First Name": "first_name", "E-mail": "email_ids.email_id"}, doctype="Contact"
        )

        self.assertEqual([row["field"] for row in result["mapping"]], ["first_name"])
        self.assertEqual(
            result["child_tables"],
            {
                "Email IDs (email_ids)": [
                    {"column": "E-mail", "position": 2, "field": "email_ids.email_id", "label": "Email ID"}
                ]
            },
        )

    def test_unmapped_columns_and_required_fields_without_a_column_are_marked(self):
        session = self._session(ADDRESSES_CSV, "addresses.csv")
        result = self._map(session, {"Street": "address_line1", "Town": "city"}, doctype="Address")

        self.assertTrue(result["success"], result)
        self.assertEqual(result["unmapped_columns"], ["Remarks"])
        self.assertEqual(sorted(m["field"] for m in result["missing_required"]), ["address_type", "country"])

    @unittest.skipUnless(HSN_VALIDATED, "needs India Compliance validating HSN/SAC codes")
    def test_an_items_missing_hsn_column_is_listed_for_an_insert_only(self):
        session = self._session("Code,Name\nIT-1,Widget\n", "items.csv")
        mapping = {"Code": "item_code", "Name": "item_name"}

        inserting = self._map(session, mapping, doctype="Item")
        updating = self._map(
            session,
            {"Code": "name", "Name": "item_name"},
            doctype="Item",
            import_type="Update Existing Records",
        )

        self.assertIn("gst_hsn_code", [m["field"] for m in inserting["missing_required"]], inserting)
        self.assertNotIn("gst_hsn_code", [m["field"] for m in updating["missing_required"]], updating)

    def test_a_child_tables_required_fields_count_once_it_is_used(self):
        result = self._map(self._session(), {"Mobile": "phone_nos.is_primary_mobile_no"}, doctype="Contact")

        self.assertEqual(
            result["missing_required"],
            [{"field": "phone_nos.phone", "label": "Number", "table": "Contact Numbers (phone_nos)"}],
        )

    def test_unknown_field_is_rejected_with_a_suggestion_and_nothing_is_saved(self):
        session = self._session()
        result = self._map(session, {"First Name": "frist_name", "Last Name": "last_name"}, doctype="Contact")

        self.assertFalse(result["success"])
        self.assertIn("'first_name'", result["problems"][0])
        doc = frappe.get_doc("FAC Import Session", session)
        self.assertEqual((self._stored_map(session), doc.status), ({}, "File Read"))

    def test_read_only_field_is_explained(self):
        result = self._map(self._session(), {"E-mail": "email_id"}, doctype="Contact")
        self.assertFalse(result["success"])
        self.assertIn("read-only", result["problems"][0])

    def test_unknown_column_lists_the_real_ones(self):
        result = self._map(self._session(), {"Fax": "first_name"}, doctype="Contact")
        self.assertFalse(result["success"])
        self.assertIn("First Name", result["problems"][0])

    def test_two_columns_on_one_field_are_rejected(self):
        result = self._map(
            self._session(), {"First Name": "first_name", "Last Name": "first_name"}, doctype="Contact"
        )
        self.assertFalse(result["success"])
        self.assertIn("first_name", result["problems"][0])

    def test_a_correction_changes_that_column_and_keeps_the_rest(self):
        session = self._session()
        self._map(session, {"First Name": "first_name", "Company": "company_name"}, doctype="Contact")

        result = self._map(session, {"Company": "designation"})

        self.assertTrue(result["success"], result)
        self.assertEqual(self._stored_map(session), {"0": "first_name", "4": "designation"})

    def test_changing_the_target_clears_the_old_mapping(self):
        session = self._session(ADDRESSES_CSV, "addresses.csv")
        self._map(session, {"Street": "first_name"}, doctype="Contact")

        result = self._map(session, {"Town": "city"}, doctype="Address")

        self.assertTrue(result["success"], result)
        self.assertEqual(frappe.db.get_value("FAC Import Session", session, "target_doctype"), "Address")
        self.assertEqual(self._stored_map(session), {"1": "city"})

    def test_a_session_without_a_target_asks_for_one(self):
        result = self._map(self._session(), {"First Name": "first_name"})
        self.assertFalse(result["success"])
        self.assertIn("doctype", result["error"])

    def test_target_permission_is_checked_before_anything_is_saved(self):
        # A desk user can open a session for their own upload but may not import Contacts.
        user = self.make_desk_user("importer")
        self.assert_cannot(user, "import", "Contact")
        frappe.set_user(user)
        session = self._session()

        result = self._map(session, {"First Name": "first_name"}, doctype="Contact")

        self.assertFalse(result["success"])
        self.assertRegex(result["error"], r"permission.*Contact")
        self.assertEqual(self._stored_map(session), {})

    def test_another_users_session_cannot_be_changed(self):
        session = self._session()
        other = self.make_desk_user("other")
        self.assert_cannot(other, "write", "FAC Import Session", session)
        frappe.set_user(other)

        result = self._map(session, {"First Name": "first_name"}, doctype="Contact")

        self.assertEqual(result["error_type"], "permission_error")


class TestImportToolsAreListed(ImportToolTestCase):
    def test_both_tools_are_available(self):
        names = [tool["name"] for tool in self.registry.get_available_tools()]
        self.assertIn("get_import_schema", names)
        self.assertIn("set_column_mapping", names)

    def test_both_are_read_only_so_no_approval_card_is_raised(self):
        # Like start_import_session, they write only the import session, never business data.
        for name in ("get_import_schema", "set_column_mapping"):
            with self.subTest(tool=name):
                self.assertEqual(detect_tool_category(self.registry.get_tool(name)), "read_only")


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's DocTypes")
class TestWhatAnInsertStillNeeds(ImportToolTestCase):
    """#34408: what the mapping says an insert still needs, and child fields it can't set."""

    @staticmethod
    def _required_when(result):
        return {r["field"]: r for r in result.get("required_when") or []}

    def test_a_prompt_named_doctype_needs_its_id_on_insert(self):
        # Issue Type is named by what the user types: Data Import refuses a row without it.
        session = self._session("Issue Type Name,Notes\nBilling,x\n", "issue_types.csv")

        without = self._map(
            session, {"Issue Type Name": "Don't Import", "Notes": "description"}, doctype="Issue Type"
        )
        mapped = self._map(session, {"Issue Type Name": "name", "Notes": "description"}, doctype="Issue Type")

        self.assertIn("name", [m["field"] for m in without["missing_required"]])
        self.assertNotIn("name", [m["field"] for m in mapped["missing_required"]])

    def test_a_field_required_when_the_rows_meet_its_condition_is_named(self):
        # Bank Account's account and company are required when it is a company account.
        session = self._session("Account Name,Bank,Company Account\nMain,HDFC,1\nPetty,HDFC,0\n", "banks.csv")

        result = self._map(
            session,
            {"Account Name": "account_name", "Bank": "bank", "Company Account": "is_company_account"},
            doctype="Bank Account",
        )

        when = self._required_when(result)
        self.assertEqual((when["account"]["when"], when["account"]["sample_rows"]), ("is_company_account", 1))
        self.assertIn("company", when)
        self.assertIn("may be required", result["summary"])

    def test_a_condition_no_sample_row_meets_is_not_named(self):
        session = self._session("Account Name,Bank,Company Account\nMain,HDFC,0\nPetty,HDFC,0\n", "banks.csv")

        result = self._map(
            session,
            {"Account Name": "account_name", "Bank": "bank", "Company Account": "is_company_account"},
            doctype="Bank Account",
        )

        self.assertNotIn("account", self._required_when(result))

    def test_a_condition_written_for_the_browser_is_named_as_possible(self):
        # Email Template's response: "eval:!doc.use_html" is JavaScript, not worked out here.
        session = self._session("Name,Subject,Use HTML\nWelcome,Hi,0\n", "templates.csv")

        result = self._map(
            session, {"Name": "name", "Subject": "subject", "Use HTML": "use_html"}, doctype="Email Template"
        )

        response = self._required_when(result)["response"]
        self.assertEqual((response["when"], response["sample_rows"]), ("eval:!doc.use_html", None))

    def test_the_schema_says_when_a_field_is_required(self):
        fields = {
            f["fieldname"]: f
            for f in self._run("get_import_schema", {"doctype": "Bank Account"})["result"]["fields"]
        }

        self.assertEqual(fields["account"]["required_when"], "is_company_account")

    def test_a_hidden_or_read_only_child_field_is_named_as_such(self):
        # Customer's Sales Team: Contact No is hidden, Allocated Amount read-only.
        session = self._session("Customer Name,Contact No,Allocated\nAcme,98450,10\n", "customers.csv")

        for column, field, why in (
            ("Contact No", "sales_team.contact_no", "hidden"),
            ("Allocated", "sales_team.allocated_amount", "read-only"),
        ):
            with self.subTest(field=field):
                result = self._map(
                    session, {"Customer Name": "customer_name", column: field}, doctype="Customer"
                )
                self.assertTrue(
                    any(why in p and "Sales Team" in p for p in result.get("problems") or []), result
                )
