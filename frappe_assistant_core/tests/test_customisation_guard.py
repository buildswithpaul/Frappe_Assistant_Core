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

"""Refusing active Server Scripts on a site where server scripts are switched off."""

from unittest.mock import patch

import frappe

from frappe_assistant_core.core.security_config import validate_document_access
from frappe_assistant_core.plugins.core.tools.create_document import DocumentCreate
from frappe_assistant_core.plugins.core.tools.get_doctype_info import GetDoctypeInfo
from frappe_assistant_core.plugins.core.tools.update_document import DocumentUpdate
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.customisation import (
    CUSTOMISATION_DOCTYPES,
    applies_to,
    desk_url,
    script_report_warning,
    server_script_guard,
)

SCRIPTS_ENABLED = "frappe_assistant_core.utils.customisation.server_scripts_enabled"
SCRIPT_NAME = "FAC Guard Probe Script"


def _script_data(**overrides) -> dict:
    data = {
        "name": SCRIPT_NAME,
        "script_type": "DocType Event",
        "reference_doctype": "ToDo",
        "doctype_event": "Before Save",
        "script": "pass",
    }
    data.update(overrides)
    return data


class TestServerScriptGuard(BaseAssistantTest):
    def tearDown(self):
        # The tool test must leave no Server Script behind even when it fails
        if frappe.db.exists("Server Script", SCRIPT_NAME):
            frappe.delete_doc("Server Script", SCRIPT_NAME, force=True, ignore_permissions=True)
        super().tearDown()

    def test_customisation_doctypes_include_server_script(self):
        self.assertIn("Server Script", CUSTOMISATION_DOCTYPES)
        self.assertEqual(len(CUSTOMISATION_DOCTYPES), 13)

    def test_create_enabled_server_script_refused_when_disabled(self):
        with patch(SCRIPTS_ENABLED, return_value=False):
            result = server_script_guard("Server Script", _script_data())

        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "server_scripts_disabled")
        self.assertIn("switched off", result["error"])
        self.assertIn("ToDo", result["error"])
        self.assertTrue(result["guidance"])

    def test_create_disabled_server_script_allowed_when_disabled(self):
        with patch(SCRIPTS_ENABLED, return_value=False):
            self.assertIsNone(server_script_guard("Server Script", _script_data(disabled=1)))

    def test_update_enabling_server_script_refused_when_disabled(self):
        with patch(SCRIPTS_ENABLED, return_value=False):
            result = server_script_guard("Server Script", {"disabled": 0}, current_disabled=1)

        self.assertEqual(result["error_type"], "server_scripts_disabled")

    def test_string_zero_disabled_counts_as_enabled_on_create(self):
        with patch(SCRIPTS_ENABLED, return_value=False):
            result = server_script_guard("Server Script", _script_data(disabled="0"))

        self.assertEqual(result["error_type"], "server_scripts_disabled")

    def test_string_zero_disabled_counts_as_enabled_on_update(self):
        with patch(SCRIPTS_ENABLED, return_value=False):
            result = server_script_guard("Server Script", {"disabled": "0"}, current_disabled=1)

        self.assertEqual(result["error_type"], "server_scripts_disabled")

    def test_non_event_script_gets_neutral_wording(self):
        with patch(SCRIPTS_ENABLED, return_value=False):
            result = server_script_guard(
                "Server Script", {"script_type": "Scheduler Event", "reference_doctype": "ToDo"}
            )

        self.assertIn("would not run", result["error"])
        self.assertNotIn("ToDo", result["error"])

    def test_update_uses_stored_script_type_for_wording(self):
        with patch(SCRIPTS_ENABLED, return_value=False):
            result = server_script_guard(
                "Server Script",
                {"disabled": 0},
                current_disabled=1,
                current_reference_doctype="ToDo",
                current_script_type="Scheduler Event",
            )

        self.assertEqual(result["error_type"], "server_scripts_disabled")
        self.assertIn("would not run", result["error"])

    def test_update_falls_back_to_stored_reference_doctype(self):
        with patch(SCRIPTS_ENABLED, return_value=False):
            result = server_script_guard(
                "Server Script", {"disabled": 0}, current_disabled=1, current_reference_doctype="ToDo"
            )

        self.assertIn("every ToDo", result["error"])

    def test_update_document_tool_refuses_enabling_script(self):
        # Production reaches this state on a site with scripts off: a script saved disabled
        # earlier (the guard allows it), which the model later tries to switch on.
        with patch(SCRIPTS_ENABLED, return_value=True):
            frappe.get_doc({"doctype": "Server Script", **_script_data(disabled=1)}).insert()

        with patch(SCRIPTS_ENABLED, return_value=False):
            result = DocumentUpdate().execute(
                {"doctype": "Server Script", "name": SCRIPT_NAME, "data": {"disabled": 0}}
            )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "server_scripts_disabled")
        self.assertIn("every ToDo", result["error"])
        self.assertEqual(frappe.db.get_value("Server Script", SCRIPT_NAME, "disabled"), 1)

    def test_update_leaving_server_script_disabled_allowed(self):
        with patch(SCRIPTS_ENABLED, return_value=False):
            self.assertIsNone(server_script_guard("Server Script", {"script": "pass"}, current_disabled=1))

    def test_other_doctype_unaffected(self):
        with patch(SCRIPTS_ENABLED, return_value=False):
            self.assertIsNone(server_script_guard("Client Script", _script_data()))

    def test_enabled_scripts_allow_everything(self):
        with patch(SCRIPTS_ENABLED, return_value=True):
            self.assertIsNone(server_script_guard("Server Script", _script_data()))

    def test_create_document_tool_returns_guard_error(self):
        with patch(SCRIPTS_ENABLED, return_value=False):
            result = DocumentCreate().execute({"doctype": "Server Script", "data": _script_data()})
            validated = DocumentCreate().execute(
                {"doctype": "Server Script", "data": _script_data(), "validate_only": True}
            )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "server_scripts_disabled")
        self.assertFalse(validated["success"])
        self.assertFalse(frappe.db.exists("Server Script", SCRIPT_NAME))

    def test_get_doctype_info_reports_server_script_flag(self):
        with patch(SCRIPTS_ENABLED, return_value=False):
            result = GetDoctypeInfo().execute({"doctype": "Server Script"})

        self.assertTrue(result["success"])
        self.assertIs(result["server_scripts_enabled"], False)

    def test_get_doctype_info_omits_flag_for_other_doctypes(self):
        result = GetDoctypeInfo().execute({"doctype": "ToDo"})

        self.assertNotIn("server_scripts_enabled", result)


NON_SM_USER = "test-cust-nonsm@example.com"
SM_USER = "test-cust-sm@example.com"
TEST_FIELD = "custom_test_plan_x"
TEST_FIELD_NAME = f"ToDo-{TEST_FIELD}"


def _make_user(email: str, role: str) -> None:
    if frappe.db.exists("User", email):
        return
    user = frappe.get_doc(
        {
            "doctype": "User",
            "email": email,
            "first_name": "Cust Probe",
            "send_welcome_email": 0,
            "roles": [{"role": role}],
        }
    )
    user.flags.ignore_permissions = True
    user.insert()


class TestAppliesToHelper(BaseAssistantTest):
    def test_maps_each_customisation_doctype_to_its_target_field(self):
        cases = {
            "Custom Field": {"dt": "ToDo"},
            "Property Setter": {"doc_type": "ToDo"},
            "Client Script": {"dt": "ToDo"},
            "Server Script": {"reference_doctype": "ToDo"},
            "Print Format": {"doc_type": "ToDo"},
            "Notification": {"document_type": "ToDo"},
        }
        for doctype, values in cases.items():
            with self.subTest(doctype=doctype):
                result = applies_to(doctype, values)
                self.assertEqual(result["doctype"], "ToDo")
                self.assertTrue(result["url"].endswith("/todo/new"))

    def test_url_shares_the_record_url_scheme(self):
        record = desk_url("ToDo", "x")
        target = applies_to("Custom Field", {"dt": "ToDo"})["url"]

        self.assertEqual(record.rsplit("/", 2)[0], target.rsplit("/", 2)[0])

    def test_slug_uses_hyphens(self):
        result = applies_to("Custom Field", {"dt": "Sales Invoice"})

        self.assertTrue(result["url"].endswith("/sales-invoice/new"))

    def test_none_for_other_doctypes_or_missing_target(self):
        self.assertIsNone(applies_to("ToDo", {"dt": "ToDo"}))
        self.assertIsNone(applies_to("Custom Field", {}))


class TestWriteResultLinks(BaseAssistantTest):
    def tearDown(self):
        frappe.flags.in_create_custom_fields = False
        if frappe.db.exists("Custom Field", TEST_FIELD_NAME):
            frappe.delete_doc("Custom Field", TEST_FIELD_NAME, force=True, ignore_permissions=True)
        for name in frappe.get_all("ToDo", filters={"description": "FAC link probe"}, pluck="name"):
            frappe.delete_doc("ToDo", name, force=True, ignore_permissions=True)
        super().tearDown()

    def _create_todo(self) -> dict:
        return DocumentCreate().execute({"doctype": "ToDo", "data": {"description": "FAC link probe"}})

    def test_create_result_has_url(self):
        result = self._create_todo()

        self.assertTrue(result["success"], result)
        self.assertTrue(result["url"].endswith(f"/todo/{result['name']}"))
        self.assertNotIn("applies_to", result)

    def test_custom_field_result_has_applies_to(self):
        # Production adds the ToDo column here; the base class no-ops commit(), which Frappe's
        # DDL needs, so the flag skips only that schema step. The result shape is unaffected.
        frappe.flags.in_create_custom_fields = True
        result = DocumentCreate().execute(
            {
                "doctype": "Custom Field",
                "data": {"dt": "ToDo", "fieldname": TEST_FIELD, "label": "Plan X", "fieldtype": "Data"},
            }
        )

        self.assertTrue(result["success"], result)
        self.assertEqual(result["applies_to"]["doctype"], "ToDo")
        self.assertTrue(result["applies_to"]["url"].endswith("/todo/new"))

    def test_update_result_has_url(self):
        name = self._create_todo()["name"]

        result = DocumentUpdate().execute(
            {"doctype": "ToDo", "name": name, "data": {"description": "FAC link probe"}}
        )

        self.assertTrue(result["success"], result)
        self.assertTrue(result["url"].endswith(f"/todo/{name}"))


class TestPlainLanguageErrors(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        _make_user(NON_SM_USER, "Desk User")
        _make_user(SM_USER, "System Manager")

    def tearDown(self):
        frappe.set_user("Administrator")
        for email in (NON_SM_USER, SM_USER):
            if frappe.db.exists("User", email):
                frappe.delete_doc("User", email, force=True, ignore_permissions=True)
        super().tearDown()

    def test_guard_error_is_plain_and_typed(self):
        result = validate_document_access(NON_SM_USER, "Server Script", None, "create")

        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "permission_error")
        self.assertNotIn("over MCP", result["error"])
        self.assertIn("System Manager", result["error"])

    def test_missing_script_manager_named(self):
        frappe.set_user(SM_USER)

        result = DocumentCreate().execute({"doctype": "Server Script", "data": _script_data()})

        self.assertFalse(result["success"])
        self.assertIn("Script Manager", result["error"])
        self.assertEqual(result["error_type"], "permission_error")

    def test_other_missing_permission_does_not_name_script_manager(self):
        result = validate_document_access(NON_SM_USER, "Workflow", None, "read")

        if not result["success"]:
            self.assertNotIn("Script Manager", result["error"])

    def test_validate_only_description_is_honest(self):
        description = DocumentCreate().inputSchema["properties"]["validate_only"]["description"]

        self.assertIn("does not check mandatory fields", description)


REPORT_NAME = "FAC Warning Probe Report"
SCRIPT_REPORT_WARNING = (
    "Server scripts are switched off on this site, so this report will show an error when "
    "someone runs it until an administrator switches them on (on Frappe Cloud this needs a "
    "private bench)."
)


def _report_data(**overrides) -> dict:
    data = {
        "report_name": REPORT_NAME,
        "ref_doctype": "ToDo",
        "report_type": "Script Report",
        "is_standard": "No",
        "report_script": "result = [], []",
    }
    data.update(overrides)
    return data


class TestScriptReportWarning(BaseAssistantTest):
    def tearDown(self):
        if frappe.db.exists("Report", REPORT_NAME):
            frappe.delete_doc("Report", REPORT_NAME, force=True, ignore_permissions=True)
        super().tearDown()

    def _create(self, **overrides) -> dict:
        return DocumentCreate().execute({"doctype": "Report", "data": _report_data(**overrides)})

    def test_create_warns_but_still_saves_when_scripts_off(self):
        with patch(SCRIPTS_ENABLED, return_value=False):
            result = self._create()

        self.assertTrue(result["success"], result)
        self.assertEqual(result["warning"], SCRIPT_REPORT_WARNING)
        self.assertTrue(frappe.db.exists("Report", REPORT_NAME))

    def test_create_omitting_is_standard_still_warns(self):
        # Report.validate stores "No" for a non-Administrator, so a create that leaves
        # is_standard out reaches the same stored state as one that sets it.
        data = _report_data()
        del data["is_standard"]
        with patch(SCRIPTS_ENABLED, return_value=False):
            result = DocumentCreate().execute({"doctype": "Report", "data": data})

        self.assertTrue(result["success"], result)
        self.assertEqual(result["warning"], SCRIPT_REPORT_WARNING)

    def test_no_warning_when_scripts_on(self):
        with patch(SCRIPTS_ENABLED, return_value=True):
            result = self._create()

        self.assertTrue(result["success"], result)
        self.assertNotIn("warning", result)

    def test_query_report_gets_no_warning(self):
        with patch(SCRIPTS_ENABLED, return_value=False):
            result = self._create(
                report_type="Query Report", query="SELECT name FROM `tabToDo`", report_script=None
            )

        self.assertTrue(result["success"], result)
        self.assertNotIn("warning", result)

    def test_update_of_stored_script_report_still_warns(self):
        with patch(SCRIPTS_ENABLED, return_value=True):
            self._create()

        with patch(SCRIPTS_ENABLED, return_value=False):
            result = DocumentUpdate().execute(
                {"doctype": "Report", "name": REPORT_NAME, "data": {"report_script": "result = [], [], 1"}}
            )

        self.assertTrue(result["success"], result)
        self.assertEqual(result["warning"], SCRIPT_REPORT_WARNING)

    def test_helper_ignores_other_doctypes_and_standard_reports(self):
        with patch(SCRIPTS_ENABLED, return_value=False):
            self.assertIsNone(script_report_warning("ToDo", _report_data()))
            self.assertIsNone(script_report_warning("Report", _report_data(is_standard="Yes")))


class TestValidateOnlyWritesNothing(BaseAssistantTest):
    """A validate_only dry run must undo whatever validate() wrote."""

    def setUp(self):
        super().setUp()
        self.setter = frappe.get_doc(
            {
                "doctype": "Property Setter",
                "doc_type": "ToDo",
                "doctype_or_field": "DocField",
                "field_name": "description",
                "property": "bold",
                "property_type": "Check",
                "value": "1",
            }
        ).insert()

    def tearDown(self):
        frappe.db.delete("Property Setter", {"doc_type": "ToDo", "field_name": "description"})
        super().tearDown()

    def _dry_run_property_setter(self) -> dict:
        return DocumentCreate().execute(
            {
                "doctype": "Property Setter",
                "data": {
                    "doc_type": "ToDo",
                    "doctype_or_field": "DocField",
                    "field_name": "description",
                    "property": "bold",
                    "property_type": "Check",
                    "value": "0",
                },
                "validate_only": True,
            }
        )

    def test_dry_run_keeps_the_property_setter_validate_would_delete(self):
        # Property Setter.validate deletes the setters it replaces; execute() returns inside
        # this test, so only the savepoint rollback can have put the row back.
        result = self._dry_run_property_setter()

        self.assertTrue(result["success"], result)
        self.assertTrue(frappe.db.exists("Property Setter", self.setter.name))

    def test_failed_dry_run_returns_the_error_and_writes_nothing(self):
        # Production reaches this with a Before Save script or app hook that writes, then throws.
        def writes_then_refuses(doc, *args, **kwargs):
            frappe.db.delete("Property Setter", {"name": self.setter.name})
            frappe.throw(frappe._("refused by validate"))

        with patch("frappe.desk.doctype.todo.todo.ToDo.validate", writes_then_refuses):
            result = DocumentCreate().execute(
                {"doctype": "ToDo", "data": {"description": "fac dry run"}, "validate_only": True}
            )

        self.assertFalse(result["success"])
        self.assertIn("refused by validate", result["error"])
        self.assertEqual(result["doctype"], "ToDo")
        self.assertTrue(frappe.db.exists("Property Setter", self.setter.name))
        self.assertFalse(frappe.db.exists("ToDo", {"description": "fac dry run"}))

    def test_dry_run_drops_commit_work_validate_queued(self):
        # A Before Save script or hook that does frappe.enqueue(..., enqueue_after_commit=True)
        # or db.after_commit.add(...) queues work the request's commit would otherwise run.
        def queued():
            pass

        def queues_work(doc, *args, **kwargs):
            frappe.db.after_commit.add(queued)

        with patch("frappe.desk.doctype.todo.todo.ToDo.validate", queues_work):
            DocumentCreate().execute(
                {"doctype": "ToDo", "data": {"description": "fac dry run"}, "validate_only": True}
            )

        self.assertNotIn(queued, frappe.db.after_commit._functions)


class TestValidateOnlyRunsInsertPreparation(BaseAssistantTest):
    """A dry run must do what Document.insert does before validate, then undo it."""

    def tearDown(self):
        frappe.db.delete("Custom Field", {"dt": "ToDo", "label": "Fac Dry Run Label"})
        super().tearDown()

    def _dry_run_custom_field(self) -> dict:
        return DocumentCreate().execute(
            {
                "doctype": "Custom Field",
                "data": {"dt": "ToDo", "label": "Fac Dry Run Label", "fieldtype": "Data"},
                "validate_only": True,
            }
        )

    def test_custom_field_dry_run_passes_and_leaves_nothing(self):
        # Frappe's Custom Field derives fieldname in before_insert, so validate() alone
        # always throws "Fieldname not set"; the agent sends exactly these three fields.
        errors_before = frappe.db.count("Error Log")

        result = self._dry_run_custom_field()

        self.assertTrue(result["success"], result)
        self.assertTrue(result["validation_passed"])
        self.assertFalse(frappe.db.exists("Custom Field", {"dt": "ToDo", "label": "Fac Dry Run Label"}))
        self.assertEqual(frappe.db.count("Error Log"), errors_before)

    @staticmethod
    def _series_counter(key: str):
        series = frappe.qb.DocType("Series")
        rows = frappe.qb.from_(series).select(series.current).where(series.name == key).run()
        return rows[0][0] if rows else None

    def test_dry_run_does_not_advance_a_naming_series(self):
        # Event is named EV.#####; Frappe bumps tabSeries while naming, in the same transaction
        # the dry run's savepoint covers. Production reaches this with any series-named doctype.
        before = self._series_counter("EV")

        result = DocumentCreate().execute(
            {
                "doctype": "Event",
                "data": {
                    "subject": "fac dry run",
                    "starts_on": "2030-01-01 10:00:00",
                    "event_type": "Private",
                },
                "validate_only": True,
            }
        )

        self.assertTrue(result["success"], result)
        self.assertEqual(self._series_counter("EV"), before)

    def test_dry_run_names_the_document_before_validate(self):
        seen = {}

        def records_name(doc, *args, **kwargs):
            seen["name"] = doc.name

        with patch("frappe.desk.doctype.event.event.Event.validate", records_name):
            DocumentCreate().execute(
                {
                    "doctype": "Event",
                    "data": {
                        "subject": "fac dry run",
                        "starts_on": "2030-01-01 10:00:00",
                        "event_type": "Private",
                    },
                    "validate_only": True,
                }
            )

        self.assertRegex(seen["name"], r"^EV\d{5}$")

    def test_dry_run_runs_before_validate_in_insert_mode(self):
        # Document.insert runs before_validate with flags.in_insert set, ahead of validate;
        # controllers and Before Validate scripts prepare state validate then checks.
        def before_validate(doc, *args, **kwargs):
            doc.flags.fac_prepared = bool(doc.flags.in_insert)

        def validate(doc, *args, **kwargs):
            if not doc.flags.fac_prepared:
                frappe.throw(frappe._("before_validate did not run in insert mode"))

        with (
            patch("frappe.desk.doctype.todo.todo.ToDo.before_validate", before_validate, create=True),
            patch("frappe.desk.doctype.todo.todo.ToDo.validate", validate),
        ):
            result = DocumentCreate().execute(
                {"doctype": "ToDo", "data": {"description": "fac dry run"}, "validate_only": True}
            )

        self.assertTrue(result["success"], result)

    def test_dry_run_does_not_run_before_save(self):
        calls = []

        with patch(
            "frappe.desk.doctype.todo.todo.ToDo.before_save",
            lambda doc, *a, **k: calls.append(1),
            create=True,
        ):
            DocumentCreate().execute(
                {"doctype": "ToDo", "data": {"description": "fac dry run"}, "validate_only": True}
            )

        self.assertEqual(calls, [])

    def test_real_create_failing_validation_is_still_logged(self):
        errors_before = frappe.db.count("Error Log")

        def refuses(doc, *args, **kwargs):
            frappe.throw(frappe._("refused by validate"))

        with patch("frappe.desk.doctype.todo.todo.ToDo.validate", refuses):
            result = DocumentCreate().execute({"doctype": "ToDo", "data": {"description": "fac real"}})

        self.assertFalse(result["success"])
        self.assertEqual(frappe.db.count("Error Log"), errors_before + 1)

    def test_failed_validation_in_a_dry_run_is_not_logged_as_an_error(self):
        errors_before = frappe.db.count("Error Log")

        def refuses(doc, *args, **kwargs):
            frappe.throw(frappe._("refused by validate"))

        with patch("frappe.desk.doctype.todo.todo.ToDo.validate", refuses):
            result = DocumentCreate().execute(
                {"doctype": "ToDo", "data": {"description": "fac dry run"}, "validate_only": True}
            )

        self.assertFalse(result["success"])
        self.assertIn("refused by validate", result["error"])
        self.assertEqual(frappe.db.count("Error Log"), errors_before)

    def test_unexpected_error_in_a_dry_run_is_still_logged(self):
        errors_before = frappe.db.count("Error Log")

        def explodes(doc, *args, **kwargs):
            raise RuntimeError("boom")

        with patch("frappe.desk.doctype.todo.todo.ToDo.validate", explodes):
            result = DocumentCreate().execute(
                {"doctype": "ToDo", "data": {"description": "fac dry run"}, "validate_only": True}
            )

        self.assertFalse(result["success"])
        self.assertEqual(frappe.db.count("Error Log"), errors_before + 1)
