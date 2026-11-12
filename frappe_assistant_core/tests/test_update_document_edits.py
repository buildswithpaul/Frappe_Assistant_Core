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

"""update_document's ``edits`` mode and the ``apply_edits`` helper (Redmine #34890)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_assistant_core.plugins.core.tools.update_document import DocumentUpdate
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.edits import EditError, apply_edits


def _edit(find: str, replace: str, field: str = "script") -> dict:
    return {"field": field, "find": find, "replace": replace}


class TestApplyEdits(FrappeTestCase):
    def test_a_single_match_is_replaced(self):
        self.assertEqual(apply_edits({"script": "a\nold\nc"}, [_edit("old", "new")]), {"script": "a\nnew\nc"})

    def test_zero_and_two_matches_fail_with_field_and_count(self):
        for text, count in (("abc", 0), ("x x", 2)):
            with self.assertRaises(EditError) as ctx:
                apply_edits({"script": text}, [_edit("x" if count else "zz", "y")])
            self.assertEqual((ctx.exception.field, ctx.exception.count), ("script", count))

    def test_edits_apply_in_order(self):
        edits = [_edit("a", "b", "html"), _edit("b", "c", "html")]
        self.assertEqual(apply_edits({"html": "a"}, edits), {"html": "c"})

    def test_find_and_replace_are_literal(self):
        out = apply_edits({"script": "x = re.match('.*(', s)"}, [_edit(".*(", r"$&\1")])
        self.assertEqual(out["script"], r"x = re.match('$&\1', s)")

    def test_lf_find_matches_crlf_code_and_keeps_crlf(self):
        out = apply_edits({"script": "a\r\nb\r\nc"}, [_edit("b\nc", "B\nC")])
        self.assertEqual(out["script"], "a\r\nB\r\nC")

    def test_empty_find_and_non_string_value_fail(self):
        with self.assertRaises(EditError):
            apply_edits({"script": "abc"}, [_edit("", "x")])
        with self.assertRaises(EditError):
            apply_edits({"script": 5}, [_edit("5", "6")])

    def test_none_reads_as_empty(self):
        with self.assertRaises(EditError) as ctx:
            apply_edits({"script": None}, [_edit("a", "b")])
        self.assertEqual(ctx.exception.count, 0)


class TestUpdateDocumentEdits(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # Production reaches this row when a builder saves a switched-off API script. A direct
        # insert is enough: the server-script guard is a tool-level check, not a doc hook.
        tag = frappe.generate_hash(length=8)
        doc = frappe.get_doc(
            {
                "doctype": "Server Script",
                "name": f"FAC Edits {tag}",
                "script_type": "API",
                "api_method": f"fac_edits_{tag}",
                "script": "first = 1\nsecond = 2\nsecond_again = 2",
                "disabled": 1,
            }
        )
        doc.insert(ignore_permissions=True)
        self.name = doc.name

    def _update(self, **arguments) -> dict:
        return DocumentUpdate().execute({"doctype": "Server Script", **arguments})

    def _stored(self) -> str:
        return frappe.db.get_value("Server Script", self.name, "script")

    def test_tool_saves_a_single_match(self):
        result = self._update(name=self.name, edits=[_edit("first = 1", "first = 10")])
        self.assertTrue(result["success"], result)
        self.assertEqual(self._stored(), "first = 10\nsecond = 2\nsecond_again = 2")

    def test_tool_leaves_record_unchanged_on_no_match(self):
        before = self._stored()
        result = self._update(name=self.name, edits=[_edit("absent", "x")])
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "edit_not_applied")
        self.assertEqual((result["field"], result["match_count"]), ("script", 0))
        self.assertEqual(self._stored(), before)

    def test_tool_leaves_record_unchanged_on_two_matches(self):
        before = self._stored()
        result = self._update(name=self.name, edits=[_edit("second", "x")])
        self.assertEqual(result["error_type"], "edit_not_applied")
        self.assertEqual(result["match_count"], 2)
        self.assertEqual(self._stored(), before)

    def test_tool_refuses_a_field_in_both_edits_and_data(self):
        before = self._stored()
        result = self._update(name=self.name, data={"script": "x"}, edits=[_edit("first", "x")])
        self.assertFalse(result["success"])
        self.assertIn("both", result["error"])
        self.assertEqual(self._stored(), before)

    def test_tool_refuses_a_non_text_field(self):
        result = self._update(name=self.name, edits=[_edit("1", "0", "disabled")])
        self.assertFalse(result["success"])
        self.assertIn("disabled", result["error"])
        self.assertEqual(frappe.db.get_value("Server Script", self.name, "disabled"), 1)

    def test_tool_refuses_edits_with_names_or_records(self):
        edits = [_edit("first", "x")]
        for form in ({"names": [self.name]}, {"records": [{"name": self.name, "data": {}}]}):
            result = self._update(edits=edits, **form)
            self.assertFalse(result["success"])
            self.assertIn("one record at a time", result["error"])

    def test_validate_only_with_edits_leaves_record_unchanged(self):
        before = self._stored()
        result = self._update(name=self.name, edits=[_edit("first = 1", "first = 10")], validate_only=True)
        self.assertTrue(result["success"], result)
        self.assertTrue(result["validation_passed"])
        self.assertEqual(self._stored(), before)

    def test_updated_fields_lists_the_edited_field(self):
        result = self._update(
            name=self.name,
            data={"api_method": f"{self.name.lower().replace(' ', '_')}_x"},
            edits=[_edit("first", "one")],
        )
        self.assertTrue(result["success"], result)
        self.assertEqual(set(result["updated_fields"]), {"api_method", "script"})

    def test_neither_data_nor_edits_is_refused(self):
        result = self._update(name=self.name)
        self.assertEqual(result["error"], "Pass the changes in 'data'.")

    def test_second_edit_failing_leaves_the_record_unchanged(self):
        before = self._stored()
        result = self._update(name=self.name, edits=[_edit("first = 1", "first = 10"), _edit("absent", "x")])
        self.assertEqual(result["error_type"], "edit_not_applied")
        self.assertEqual(self._stored(), before)

    def test_crlf_stored_value_is_edited_through_the_tool(self):
        # Production reaches CRLF text when a script is pasted from a Windows editor into Desk.
        frappe.db.set_value("Server Script", self.name, "script", "a = 1\r\nb = 2\r\nc = 3")
        result = self._update(name=self.name, edits=[_edit("b = 2\nc = 3", "b = 20\nc = 30")])
        self.assertTrue(result["success"], result)
        self.assertEqual(self._stored(), "a = 1\r\nb = 20\r\nc = 30")

    def test_null_edits_without_data_is_the_missing_changes_refusal(self):
        result = self._update(name=self.name, edits=None)
        self.assertEqual(result["error"], "Pass the changes in 'data'.")

    def test_restricted_field_is_refused_before_any_match_is_reported(self):
        # email_signature is on the all-roles sensitive list and is a Text Editor field of User,
        # so production reaches this when an assistant is asked to edit a user's signature.
        user = self.make_throwaway_user("fac-edits-restricted", roles=("Desk User",))
        result = DocumentUpdate().execute(
            {"doctype": "User", "name": user, "edits": [_edit("no such text", "x", "email_signature")]}
        )
        self.assertFalse(result["success"], result)
        self.assertNotEqual(result.get("error_type"), "edit_not_applied")
        self.assertIn("restricted", result["error"])


class TestUpdateDocumentEditsOnSubmittedRecord(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        if not frappe.db.exists("DocType", "Telephony Call Type"):
            self.skipTest("Telephony Call Type not available (ERPNext not installed)")
        # Production reaches a submitted record when a user submits a Telephony Call Type.
        doc = frappe.get_doc({"doctype": "Telephony Call Type", "call_type": "_Test FAC edits"}).insert()
        doc.submit()
        self.name = doc.name

    def test_edit_to_a_field_not_allowed_on_submit_is_refused_by_the_tool_gate(self):
        result = DocumentUpdate().execute(
            {"doctype": "Telephony Call Type", "name": self.name, "edits": [_edit("Test", "x", "call_type")]}
        )
        self.assertFalse(result["success"], result)
        self.assertIn("Cannot modify submitted document", result["error"])
