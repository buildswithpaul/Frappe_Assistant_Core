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
update_document's validate_only dry run (Redmine #34686).

ToDo is the fixture: a core doctype on v15 and v16 whose validate reads the stored record.
The submitted-record case uses ERPNext's Telephony Call Type, as test_document_action does:
it is submittable with a single field, so it works on the CI site, which installs ERPNext
without the setup wizard.
"""

from unittest.mock import patch

import frappe

from frappe_assistant_core.plugins.core.tools.update_document import DocumentUpdate
from frappe_assistant_core.tests.base_test import BaseAssistantTest

SUBMITTABLE_DOCTYPE = "Telephony Call Type"


def _todo(description: str, **extra) -> str:
    return (
        frappe.get_doc(
            {"doctype": "ToDo", "description": description, "allocated_to": "Administrator", **extra}
        )
        .insert()
        .name
    )


def _dry_run(name: str, data: dict, doctype: str = "ToDo") -> dict:
    return DocumentUpdate().execute({"doctype": doctype, "name": name, "data": data, "validate_only": True})


def _stored(name: str) -> dict:
    return frappe.db.get_value("ToDo", name, ["description", "priority", "modified"], as_dict=True)


class TestUpdateDryRun(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.tag = f"fac-dry-update-{frappe.generate_hash(length=8)}"
        self.name = _todo(self.tag)

    def test_dry_run_passes_and_leaves_the_stored_record_unchanged(self):
        before = _stored(self.name)

        result = _dry_run(self.name, {"description": f"{self.tag} edited", "priority": "High"})

        self.assertTrue(result["success"], result)
        self.assertTrue(result["validation_passed"])
        self.assertEqual(result["name"], self.name)
        self.assertEqual(_stored(self.name), before)

    def test_validate_sees_the_change_against_the_stored_record(self):
        # A rule for edits compares the new value with the stored one; validate must run as an
        # update (not a new record) with the change applied.
        seen = {}

        def records_change(doc, *args, **kwargs):
            seen["is_new"] = doc.is_new()
            seen["new"] = doc.priority
            seen["stored"] = doc.get_doc_before_save().priority

        with patch("frappe.desk.doctype.todo.todo.ToDo.validate", records_change):
            result = _dry_run(self.name, {"priority": "High"})

        self.assertTrue(result["success"], result)
        self.assertEqual(seen, {"is_new": False, "new": "High", "stored": "Medium"})

    def test_failed_dry_run_returns_the_error_writes_nothing_and_logs_nothing(self):
        witness = _todo(f"{self.tag} witness")

        def writes_then_refuses(doc, *args, **kwargs):
            frappe.db.set_value("ToDo", witness, "description", "written by validate")
            frappe.throw(frappe._("refused by validate"))

        errors_before = frappe.db.count("Error Log")
        with patch("frappe.desk.doctype.todo.todo.ToDo.validate", writes_then_refuses):
            result = _dry_run(self.name, {"priority": "High"})

        self.assertFalse(result["success"], result)
        self.assertIn("refused by validate", result["error"])
        self.assertEqual(frappe.db.get_value("ToDo", witness, "description"), f"{self.tag} witness")
        self.assertEqual(frappe.db.get_value("ToDo", self.name, "priority"), "Medium")
        self.assertEqual(frappe.db.count("Error Log"), errors_before)

    def test_dry_run_does_not_run_before_save(self):
        calls = []

        with patch(
            "frappe.desk.doctype.todo.todo.ToDo.before_save",
            lambda doc, *a, **k: calls.append(1),
            create=True,
        ):
            _dry_run(self.name, {"priority": "High"})

        self.assertEqual(calls, [])

    def test_dry_run_drops_commit_work_validate_queued(self):
        def queued():
            pass

        def queues_work(doc, *args, **kwargs):
            frappe.db.after_commit.add(queued)

        with patch("frappe.desk.doctype.todo.todo.ToDo.validate", queues_work):
            _dry_run(self.name, {"priority": "High"})

        self.assertNotIn(queued, frappe.db.after_commit._functions)

    def test_dry_run_refuses_a_change_to_a_missing_record(self):
        result = _dry_run(f"{self.tag}-missing", {"priority": "High"})

        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"])

    def test_validate_only_description_is_honest(self):
        description = DocumentUpdate().inputSchema["properties"]["validate_only"]["description"]

        self.assertIn("does not check mandatory fields", description)


class TestUpdateDryRunWithBeforeSaveScript(BaseAssistantTest):
    """A real Before Save server script, the rule FACO builds and dry-runs."""

    def setUp(self):
        super().setUp()
        self.tag = f"fac-dry-update-{frappe.generate_hash(length=8)}"
        self.name = _todo(self.tag)
        self.witness = _todo(f"{self.tag} witness")
        script = (
            f"if doc.description and doc.description.startswith('{self.tag}') and doc.name != '{self.witness}':\n"
            f"    frappe.db.set_value('ToDo', '{self.witness}', 'description', 'touched by the rule')\n"
            f"    if doc.priority == 'High':\n"
            f"        frappe.throw('Only a manager may make a ToDo high priority')\n"
        )
        frappe.get_doc(
            {
                "doctype": "Server Script",
                "name": f"FAC Dry Update {self.tag}",
                "script_type": "DocType Event",
                "reference_doctype": "ToDo",
                "doctype_event": "Before Save",
                "script": script,
            }
        ).insert()
        # The class rollback removes the script row but not the cached script map, which would
        # then send every later ToDo save to a script that no longer exists. Deleting the script
        # clears that map through its own on_trash, on v15 and v16 alike.
        self.addCleanup(
            frappe.delete_doc,
            "Server Script",
            f"FAC Dry Update {self.tag}",
            force=True,
            ignore_permissions=True,
        )
        # Production reaches this on a bench whose common_site_config sets server_script_enabled,
        # which FACO's rule building needs; the CI bench need not set it.
        enabled = patch("frappe.utils.safe_exec.is_safe_exec_enabled", return_value=True)
        enabled.start()
        self.addCleanup(enabled.stop)

    def witness_description(self) -> str:
        return frappe.db.get_value("ToDo", self.witness, "description")

    def test_the_rule_writes_on_a_real_update(self):
        # The control for the two tests below: the rule does fire and write on this update.
        result = DocumentUpdate().execute({"doctype": "ToDo", "name": self.name, "data": {"priority": "Low"}})

        self.assertTrue(result["success"], result)
        self.assertEqual(self.witness_description(), "touched by the rule")

    def test_dry_run_rolls_back_what_the_rule_wrote(self):
        result = _dry_run(self.name, {"priority": "Low"})

        self.assertTrue(result["success"], result)
        self.assertTrue(result["validation_passed"])
        self.assertEqual(self.witness_description(), f"{self.tag} witness")
        self.assertEqual(frappe.db.get_value("ToDo", self.name, "priority"), "Medium")

    def test_dry_run_reports_the_rules_message_and_saves_nothing(self):
        result = _dry_run(self.name, {"priority": "High"})

        self.assertFalse(result["success"], result)
        self.assertIn("Only a manager may make a ToDo high priority", result["error"])
        self.assertEqual(self.witness_description(), f"{self.tag} witness")
        self.assertEqual(frappe.db.get_value("ToDo", self.name, "priority"), "Medium")


class TestUpdateDryRunPermissions(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.tag = f"fac-dry-update-{frappe.generate_hash(length=8)}"
        # A ToDo allocated to Administrator: Frappe's ToDo rule refuses its write to anyone else.
        self.name = _todo(self.tag)
        self.user = self.make_throwaway_user("fac-dry-update", roles=("Desk User",))
        log_error = patch("frappe.log_error")
        self.log_error = log_error.start()
        self.addCleanup(log_error.stop)
        # nosemgrep: frappe-setuser — the test runs as a restricted user; cleanup restores Administrator
        frappe.set_user(self.user)
        self.addCleanup(frappe.set_user, "Administrator")

    def test_user_who_may_not_write_is_refused(self):
        result = _dry_run(self.name, {"priority": "High"})

        self.assertFalse(result["success"], result)
        self.assertEqual(frappe.db.get_value("ToDo", self.name, "priority"), "Medium")

    def test_dry_run_runs_the_write_check_the_save_runs(self):
        # Production reaches a passed pre-check whenever the role may write ToDo at all; the
        # record-level refusal then comes from Frappe's own check, which the dry run must run.
        with patch(
            "frappe_assistant_core.core.security_config.validate_document_access",
            return_value={"success": True, "role": "Default"},
        ):
            result = _dry_run(self.name, {"priority": "High"})

        self.assertFalse(result["success"], result)
        self.assertEqual(result.get("error_type"), "permission_error")
        self.assertEqual(frappe.db.get_value("ToDo", self.name, "priority"), "Medium")
        self.log_error.assert_not_called()


class TestUpdateDryRunOnSubmittedRecord(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        if not frappe.db.exists("DocType", SUBMITTABLE_DOCTYPE):
            self.skipTest(f"{SUBMITTABLE_DOCTYPE} not available (ERPNext not installed)")
        self.call_type = f"_Test FAC {frappe.generate_hash(length=8)}"
        doc = frappe.get_doc({"doctype": SUBMITTABLE_DOCTYPE, "call_type": self.call_type}).insert()
        doc.submit()
        self.name = doc.name

    def stored(self):
        return frappe.db.get_value(SUBMITTABLE_DOCTYPE, self.name, ["call_type", "docstatus"])

    def test_dry_run_refuses_a_change_to_a_submitted_record(self):
        result = _dry_run(self.name, {"call_type": "changed"}, doctype=SUBMITTABLE_DOCTYPE)

        self.assertFalse(result["success"], result)
        self.assertIn("Cannot modify submitted document", result["error"])
        self.assertEqual(self.stored(), (self.call_type, 1))

    def test_real_update_refuses_the_same_change(self):
        # The dry run must agree with the write it stands in for.
        result = DocumentUpdate().execute(
            {"doctype": SUBMITTABLE_DOCTYPE, "name": self.name, "data": {"call_type": "changed"}}
        )

        self.assertFalse(result["success"], result)
        self.assertIn("Cannot modify submitted document", result["error"])
        self.assertEqual(self.stored(), (self.call_type, 1))
