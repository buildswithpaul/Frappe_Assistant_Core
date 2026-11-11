# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
create_document and update_document with several records in one call (documents): one tool
call, so one approval card; every record checked first, then all written or none.

Frappe's own ToDo (anyone may create one; its description goes to global search) and Note
(needs a title), so these run on any site. Single-record calls are covered, unchanged, by
test_document_tools.
"""

import os
from unittest.mock import patch

import frappe
from frappe.desk.doctype.note.note import Note
from frappe.desk.doctype.todo.todo import ToDo

from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.plugins.core.tools.create_document import DocumentCreate
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils import document_batch
from frappe_assistant_core.utils.customisation import CUSTOMISATION_DOCTYPES


class TestDocumentBatch(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.registry = get_tool_registry()
        self.tag = frappe.generate_hash(length=8)

    def _run(self, tool_name, arguments):
        return self.registry.get_tool(tool_name)._safe_execute(arguments)

    def _todo(self, text):
        return {"doctype": "ToDo", "data": {"description": f"{text} {self.tag}"}}

    def _todos(self):
        return set(
            frappe.get_all("ToDo", filters={"description": ["like", f"% {self.tag}"]}, pluck="description")
        )

    def _notes(self):
        return set(frappe.get_all("Note", filters={"title": ["like", f"% {self.tag}"]}, pluck="title"))

    # -- create_document ---------------------------------------------------------------------

    def test_one_call_creates_records_of_several_doctypes(self):
        response = self._run(
            "create_document",
            {
                "documents": [
                    self._todo("Call the bank"),
                    {"doctype": "Note", "data": {"title": f"Bank details {self.tag}"}},
                    self._todo("Send the invoice"),
                ]
            },
        )

        self.assertTrue(response["success"], response)
        result = response["result"]
        self.assertEqual([c["doctype"] for c in result["created"]], ["ToDo", "Note", "ToDo"])
        self.assertEqual(self._todos(), {f"Call the bank {self.tag}", f"Send the invoice {self.tag}"})
        self.assertEqual(self._notes(), {f"Bank details {self.tag}"})
        self.assertIn("Created 3 records", result["message"])

    def test_one_record_failing_creates_none_and_says_which(self):
        logged = {"method": "Document Creation Error"}
        logs_before = frappe.db.count("Error Log", logged)

        response = self._run(
            "create_document",
            {
                "documents": [
                    self._todo("Call the bank"),
                    {"doctype": "Note", "data": {"content": "no title"}},
                ]
            },
        )

        self.assertFalse(response["success"], response)
        self.assertIn("Document 2 (Note) couldn't be created", response["result"]["error"])
        self.assertIn("Nothing was created", response["result"]["error"])
        self.assertEqual(self._todos(), set())  # the first one is undone
        self.assertEqual(frappe.db.count("Error Log", logged), logs_before + 1)

    def test_every_record_is_checked_before_any_is_written(self):
        response = self._run(
            "create_document",
            {"documents": [self._todo("Fine"), {"doctype": "ToDo"}, {"data": {"description": "x"}}, "oops"]},
        )

        self.assertFalse(response["success"], response)
        self.assertEqual([p["document"] for p in response["result"]["problems"]], [2, 3, 4])
        self.assertEqual(self._todos(), set())

    def test_a_record_the_user_may_not_create_stops_the_list_before_anything_is_written(self):
        # Language: only a System Manager creates one, and it isn't a customisation, which a
        # list refuses for everyone before permission is even looked at.
        user = self.make_desk_user("writer")
        self.assert_cannot(user, "create", "Language")
        frappe.set_user(user)

        def language(code):
            return {"doctype": "Language", "data": {"language_code": code, "language_name": code}}

        response = self._run(
            "create_document",
            {"documents": [self._todo("Mine"), language(f"xa-{self.tag}"), language(f"xb-{self.tag}")]},
        )

        self.assertFalse(response["success"], response)
        self.assertNotIn("error_type", response["result"])  # refused for permission, not as a customisation
        # Checked before anything is written, so every refused record is listed, not the first.
        self.assertEqual([p["document"] for p in response["result"]["problems"]], [2, 3])
        frappe.set_user("Administrator")
        self.assertEqual(self._todos(), set())
        self.assertFalse(frappe.db.exists("Language", f"xa-{self.tag}"))

    def test_a_restricted_field_in_a_list_is_refused(self):
        response = self._run(
            "create_document",
            {
                "documents": [
                    {"doctype": "ToDo", "data": {"description": f"x {self.tag}", "api_key": "k"}},
                    {"doctype": "ToDo", "data": {"description": f"y {self.tag}", "api_secret": "s"}},
                ]
            },
        )

        self.assertFalse(response["success"], response)
        problems = response["result"]["problems"]
        self.assertEqual([p["document"] for p in problems], [1, 2])  # both listed, before writing
        self.assertIn("api_key", problems[0]["error"])
        self.assertEqual(self._todos(), set())

    def test_more_than_a_hundred_records_are_refused(self):
        response = self._run("create_document", {"documents": [self._todo(str(i)) for i in range(101)]})

        self.assertFalse(response["success"], response)
        self.assertIn("At most 100", response["result"]["error"])
        self.assertEqual(self._todos(), set())

    def test_a_list_and_a_single_record_together_are_refused(self):
        response = self._run(
            "create_document",
            {"doctype": "ToDo", "data": {"description": "single"}, "documents": [self._todo("listed")]},
        )

        self.assertFalse(response["success"], response)
        self.assertIn("not both", response["result"]["error"])

    def test_empty_optional_inputs_are_not_given(self):
        # Clients fill optional inputs in: a single call arrives with "documents": [], and a list
        # call with "doctype": "" and "data": {}.
        single = self._run(
            "create_document",
            {"doctype": "ToDo", "data": {"description": f"One {self.tag}"}, "documents": []},
        )
        listed = self._run("create_document", {"doctype": "", "data": {}, "documents": [self._todo("Two")]})

        self.assertTrue(single["success"], single)
        self.assertTrue(listed["success"], listed)
        self.assertEqual(self._todos(), {f"One {self.tag}", f"Two {self.tag}"})

    def test_submit_is_not_for_a_list(self):
        response = self._run("create_document", {"documents": [self._todo("x")], "submit": True})

        self.assertFalse(response["success"], response)
        self.assertIn("one document at a time", response["result"]["error"])
        self.assertEqual(self._todos(), set())

    def test_validate_only_with_a_list_creates_nothing(self):
        # validate_only runs each record's own validate(), as it does for one record (which
        # doesn't check mandatory fields); either way nothing is created.
        response = self._run(
            "create_document",
            {
                "documents": [self._todo("Fine"), {"doctype": "Note", "data": {"title": f"T {self.tag}"}}],
                "validate_only": True,
            },
        )

        self.assertTrue(response["success"], response)
        result = response["result"]
        self.assertEqual([d["validation_passed"] for d in result["documents"]], [True, True])
        self.assertIn("Nothing was created", result["message"])
        self.assertEqual(self._todos(), set())
        self.assertEqual(self._notes(), set())

    def test_one_record_without_doctype_says_what_to_pass(self):
        response = self._run("create_document", {"data": {"description": "x"}})

        self.assertFalse(response["success"], response)
        self.assertIn("documents", response["result"]["error"])

    def test_records_reach_global_search_once_all_succeed(self):
        with patch("frappe.utils.global_search.sync_value_in_queue") as search_queue:
            response = self._run("create_document", {"documents": [self._todo("Searchable")]})

        self.assertTrue(response["success"], response)
        queued = [c.args[0]["doctype"] for c in search_queue.call_args_list]
        self.assertIn("ToDo", queued)

    def test_an_undone_batch_sends_nothing_out(self):
        creator = DocumentCreate()
        documents = [self._todo("Undone"), {"doctype": "Note", "data": {"content": "no title"}}]
        realtime_before = list(getattr(frappe.local, "_realtime_log", []))
        callbacks_before = len(frappe.db.after_commit._functions)

        with patch("frappe.utils.global_search.sync_value_in_queue") as search_queue:
            with self.assertRaises(document_batch.BatchProblem):
                document_batch.write_all(documents, lambda e: creator.execute(dict(e)), "created")

        self.assertEqual(search_queue.call_count, 0)  # no search entry for the undone ToDo
        self.assertEqual(list(getattr(frappe.local, "_realtime_log", [])), realtime_before)
        self.assertEqual(len(frappe.db.after_commit._functions), callbacks_before)
        self.assertEqual(self._todos(), set())

    def test_a_controller_that_commits_cannot_make_earlier_records_permanent(self):
        real_on_update = ToDo.on_update

        def commits(doc):
            real_on_update(doc)
            frappe.db.commit()  # nosemgrep: frappe-manual-commit — the controller this test imitates

        frappe.db.savepoint("fac_test_before_the_list")
        # The ToDo's own controller commits after it saves, as some apps' controllers do.
        with patch.object(ToDo, "on_update", autospec=True, side_effect=commits) as on_update:
            response = self._run(
                "create_document",
                {"documents": [self._todo("First"), {"doctype": "Note", "data": {"content": "no title"}}]},
            )

        self.assertTrue(on_update.called)
        self.assertFalse(response["success"], response)
        error = response["result"]["error"]
        self.assertIn("Document 2 (Note) couldn't be created", error)
        self.assertIn("title", error)  # record 2's own error
        self.assertEqual(self._todos(), set())
        # Nothing was committed: the savepoint opened before the list is still there to go back to.
        frappe.db.rollback(save_point="fac_test_before_the_list")

    def test_one_record_without_data_is_still_refused(self):
        # data was required before documents came in; it still is for one record.
        response = self._run("create_document", {"doctype": "ToDo"})

        self.assertFalse(response["success"], response)
        # Refused before any insert is tried, not by the ToDo's own missing description.
        self.assertIn("Pass doctype and data", response["result"]["error"])

    def test_an_empty_list_of_documents_says_so_with_and_without_an_import_session(self):
        # A masters batch with nothing missing is an empty list: it said "Missing doctype, data."
        # for an import session, and asked for doctype and data without one (#33992).
        for extra in ({}, {"import_session": "any-session"}):
            with self.subTest(extra=extra):
                response = self._run("create_document", {"documents": [], **extra})

                self.assertFalse(response["success"], response)
                self.assertIn("documents is empty", response["result"]["error"])
                self.assertEqual(self._todos(), set())

    def test_an_empty_list_beside_one_record_still_creates_the_record(self):
        # Clients fill optional inputs with empty values: [] beside doctype and data reads as not given.
        response = self._run("create_document", {"documents": [], **self._todo("Single")})

        self.assertTrue(response["success"], response)

    def test_a_callers_own_commit_stand_in_is_given_back(self):
        creator = DocumentCreate()

        def stand_in(*args, **kwargs):
            return None

        frappe.db.commit = stand_in  # as the dry run's held_back sets one
        try:
            document_batch.write_all([self._todo("Kept")], lambda e: creator.execute(dict(e)), "created")
            self.assertIs(vars(frappe.db).get("commit"), stand_in)
        finally:
            del frappe.db.commit

    def test_a_search_entry_that_fails_does_not_report_the_written_records_as_failed(self):
        with patch.object(
            document_batch, "update_global_search", autospec=True, side_effect=RuntimeError("redis down")
        ):
            response = self._run("create_document", {"documents": [self._todo("Written")]})

        self.assertTrue(response["success"], response)  # a retry would create it twice
        self.assertEqual(self._todos(), {f"Written {self.tag}"})

    # -- customisation and schema-changing records (#34396) ----------------------------------

    def _custom_field_on_todo(self):
        fieldname = f"fac_batch_{self.tag.lower()}"
        self.addCleanup(frappe.clear_cache, doctype="ToDo")
        entry = {
            "doctype": "Custom Field",
            "data": {
                "dt": "ToDo",
                "label": f"FAC batch {self.tag}",
                "fieldname": fieldname,
                "fieldtype": "Data",
                "insert_after": "description",
            },
        }
        return fieldname, entry

    def _assert_no_column(self, fieldname):
        # Read from the table itself, not from Frappe's cached column list.
        columns = frappe.db.sql_list(
            "select column_name from information_schema.columns"
            " where table_schema = database() and table_name = 'tabToDo'"
        )
        self.assertNotIn(fieldname, columns)
        self.assertFalse(frappe.db.exists("Custom Field", {"dt": "ToDo", "fieldname": fieldname}))
        self.assertFalse(frappe.get_meta("ToDo").has_field(fieldname))

    def test_every_customisation_doctype_in_a_create_list_is_refused_before_anything_is_written(self):
        doctypes = sorted(CUSTOMISATION_DOCTYPES)
        documents = [self._todo("Plain")] + [{"doctype": doctype, "data": {}} for doctype in doctypes]

        response = self._run("create_document", {"documents": documents})

        self.assertFalse(response["success"], response)
        result = response["result"]
        self.assertEqual(result["error_type"], "one_at_a_time")
        refused = {p["document"]: p["doctype"] for p in result["problems"]}
        self.assertNotIn(1, refused)  # the ToDo is fine
        for number, doctype in enumerate(doctypes, start=2):
            with self.subTest(doctype=doctype):
                self.assertEqual(refused.get(number), doctype)
        self.assertEqual(self._todos(), set())

    def test_a_customisation_record_in_an_update_list_is_refused(self):
        (todo,) = self._make_todos("Keep me")
        guest_disabled = frappe.db.get_value("Role", "Guest", "disabled")

        response = self._run(
            "update_document",
            {
                "documents": [
                    {"doctype": "ToDo", "name": todo, "data": {"description": f"Changed {self.tag}"}},
                    {"doctype": "Role", "name": "Guest", "data": {"disabled": 1}},
                ]
            },
        )

        self.assertFalse(response["success"], response)
        self.assertEqual(response["result"]["error_type"], "one_at_a_time")
        self.assertEqual(
            [(p["document"], p["doctype"], p.get("name")) for p in response["result"]["problems"]],
            [(2, "Role", "Guest")],
        )
        self.assertEqual(frappe.db.get_value("ToDo", todo, "description"), f"Keep me {self.tag}")
        self.assertEqual(frappe.db.get_value("Role", "Guest", "disabled"), guest_disabled)

    def test_a_validate_only_list_with_a_customisation_record_is_refused(self):
        response = self._run(
            "create_document",
            {
                "documents": [
                    self._todo("Fine"),
                    {"doctype": "Role", "data": {"role_name": f"R {self.tag}"}},
                ],
                "validate_only": True,
            },
        )

        self.assertFalse(response["success"], response)
        self.assertEqual(response["result"]["error_type"], "one_at_a_time")
        self.assertEqual([p["document"] for p in response["result"]["problems"]], [2])

    def test_the_refusal_says_to_make_each_customisation_on_its_own(self):
        _fieldname, custom_field = self._custom_field_on_todo()
        created = self._run(
            "create_document",
            {
                "documents": [
                    self._todo("Fine"),
                    {"doctype": "Role", "data": {"role_name": f"R {self.tag}"}},
                    custom_field,
                ]
            },
        )
        (todo,) = self._make_todos("Keep me")
        updated = self._run(
            "update_document",
            {
                "documents": [
                    {"doctype": "Role", "name": "Guest", "data": {"desk_access": 0}},
                    {"doctype": "ToDo", "name": todo, "data": {"priority": "High"}},
                ]
            },
        )

        error = created["result"]["error"]
        self.assertEqual([p["document"] for p in created["result"]["problems"]], [2, 3])
        self.assertIn("on its own", error)
        self.assertIn("doctype and data", error)
        self.assertIn("one call each", error)
        self.assertIn("other records", error)  # they may still go as a list
        self.assertIn("doctype, name and data", updated["result"]["error"])
        self.assertFalse(frappe.db.exists("Role", f"R {self.tag}"))

    def test_a_known_schema_changing_doctype_in_a_list_is_refused_up_front(self):
        if "erpnext" not in frappe.get_installed_apps():
            self.skipTest("Inventory Dimension is ERPNext's")
        name = f"FAC Dimension {self.tag}"

        response = self._run(
            "create_document",
            {
                "documents": [
                    self._todo("Fine"),
                    {
                        "doctype": "Inventory Dimension",
                        "data": {"dimension_name": name, "reference_document": "Project"},
                    },
                ]
            },
        )

        self.assertFalse(response["success"], response)
        self.assertEqual(response["result"]["error_type"], "one_at_a_time")
        self.assertEqual(
            [(p["document"], p["doctype"]) for p in response["result"]["problems"]],
            [(2, "Inventory Dimension")],
        )
        self.assertIn("on its own", response["result"]["error"])
        self.assertEqual(self._todos(), set())
        self.assertFalse(frappe.db.exists("Inventory Dimension", name))

    def test_a_schema_change_inside_a_list_is_stopped_and_the_list_undone(self):
        # Direct, past the up-front refusal: the Custom Field's own on_update reaches updatedb,
        # as a doctype that changes the schema without being on any list would.
        creator = DocumentCreate()
        fieldname, custom_field = self._custom_field_on_todo()

        with self.assertRaises(document_batch.BatchProblem) as raised:
            document_batch.write_all(
                [self._todo("Before it"), custom_field], lambda e: creator.execute(dict(e)), "created"
            )

        error = str(raised.exception)
        self.assertEqual(raised.exception.error_type, "schema_change_in_list")
        self.assertIn("Document 2 (Custom Field)", error)
        self.assertIn("on its own", error)
        self.assertIn("Nothing was created", error)
        self.assertNotRegex(error, "(?i)savepoint|implicit commit")
        self._assert_no_column(fieldname)
        self.assertEqual(self._todos(), set())

    def test_nothing_before_the_list_is_committed_by_a_schema_change(self):
        creator = DocumentCreate()
        fieldname, custom_field = self._custom_field_on_todo()
        frappe.db.savepoint("fac_test_before_the_list")
        (before,) = self._make_todos("Written before the list")

        with self.assertRaises(document_batch.BatchProblem) as raised:
            document_batch.write_all([custom_field], lambda e: creator.execute(dict(e)), "created")

        self.assertIn("on its own", str(raised.exception))
        self._assert_no_column(fieldname)
        self.assertTrue(frappe.db.exists("ToDo", before))
        # Not committed: the savepoint opened before it is still there, and going back to it
        # takes the ToDo away.
        frappe.db.rollback(save_point="fac_test_before_the_list")
        self.assertFalse(frappe.db.exists("ToDo", before))

    def test_a_real_error_after_a_record_is_saved_undoes_the_whole_list(self):
        saved = []

        def fails_after_saving(doc):
            saved.append(bool(frappe.db.exists("Note", doc.name)))
            frappe.throw(frappe._("This note can't be kept"))

        # Note has no on_update of its own, so there is nothing to autospec: create=True adds one,
        # which Document.run_method calls after the row is inserted, as any controller's would.
        with patch.object(Note, "on_update", fails_after_saving, create=True):
            response = self._run(
                "create_document",
                {
                    "documents": [
                        self._todo("A"),
                        {"doctype": "Note", "data": {"title": f"B {self.tag}"}},
                        self._todo("C"),
                    ]
                },
            )

        self.assertEqual(saved, [True])  # B's row was in the table when its controller raised
        self.assertFalse(response["success"], response)
        error = response["result"]["error"]
        self.assertIn("Document 2 (Note)", error)
        self.assertIn("can't be kept", error)
        self.assertIn("Nothing was created", error)
        self.assertEqual(self._todos(), set())
        self.assertEqual(self._notes(), set())

    def test_an_undone_list_sends_nothing_out_after_a_real_error(self):
        # Direct, so the only events are the list's own: the tool adds an Error Log and an audit
        # row after the list is undone, which are kept and announced.
        creator = DocumentCreate()
        documents = [self._todo("Undone"), {"doctype": "Note", "data": {"title": f"B {self.tag}"}}]
        realtime_before = list(getattr(frappe.local, "_realtime_log", []))
        callbacks_before = len(frappe.db.after_commit._functions)

        def fails_after_saving(doc):
            frappe.throw(frappe._("This note can't be kept"))

        with patch("frappe.utils.global_search.sync_value_in_queue") as search_queue:
            with patch.object(Note, "on_update", fails_after_saving, create=True):
                with self.assertRaises(document_batch.BatchProblem):
                    document_batch.write_all(documents, lambda e: creator.execute(dict(e)), "created")

        self.assertEqual(search_queue.call_count, 0)
        self.assertEqual(list(getattr(frappe.local, "_realtime_log", [])), realtime_before)
        self.assertEqual(len(frappe.db.after_commit._functions), callbacks_before)
        self.assertEqual(self._todos(), set())

    def test_a_controller_rollback_fails_the_list_and_keeps_what_came_before(self):
        (before,) = self._make_todos("Written before the list")
        rolled_back = []

        def rolls_back(doc):
            rolled_back.append(doc.name)
            frappe.db.rollback()  # a full rollback, then carries on as if nothing happened

        with patch.object(Note, "on_update", rolls_back, create=True):
            response = self._run(
                "create_document",
                {"documents": [self._todo("A"), {"doctype": "Note", "data": {"title": f"B {self.tag}"}}]},
            )

        self.assertEqual(len(rolled_back), 1)
        self.assertFalse(response["success"], response)
        self.assertEqual(response["result"]["error_type"], "rollback_in_list")
        error = response["result"]["error"]
        self.assertIn("Document 2 (Note)", error)
        self.assertIn("Nothing was created", error)
        self.assertNotIn("Created", error)
        self.assertTrue(frappe.db.exists("ToDo", before))  # no real ROLLBACK ran
        self.assertEqual(self._todos(), {f"Written before the list {self.tag}"})
        self.assertEqual(self._notes(), set())

    # -- Frappe's own transaction control (v16) ----------------------------------------------

    def _needs_transaction_control(self):
        if not hasattr(frappe.db, "_disable_transaction_control"):
            self.skipTest("This Frappe has no _disable_transaction_control (v15)")

    def test_a_list_is_written_with_transaction_control_disabled_on_v16(self):
        self._needs_transaction_control()
        creator = DocumentCreate()
        before = frappe.db._disable_transaction_control
        seen = []

        def write(entry):
            seen.append((frappe.db._disable_transaction_control, "commit" in vars(frappe.db)))
            return creator.execute(dict(entry))

        document_batch.write_all([self._todo("One"), self._todo("Two")], write, "created")

        self.assertEqual(len(seen), 2)
        for counter, commit_replaced in seen:
            self.assertGreater(counter, before)
            self.assertFalse(commit_replaced)
        self.assertEqual(frappe.db._disable_transaction_control, before)

    def test_transaction_control_is_given_back_after_a_failed_list(self):
        self._needs_transaction_control()
        creator = DocumentCreate()
        before = frappe.db._disable_transaction_control

        with self.assertRaises(document_batch.BatchProblem):
            document_batch.write_all(
                [self._todo("One"), {"doctype": "Note", "data": {"content": "no title"}}],
                lambda e: creator.execute(dict(e)),
                "created",
            )
        self.assertEqual(frappe.db._disable_transaction_control, before)

        def raises(entry):
            raise RuntimeError("the write itself raised")

        with self.assertRaises(RuntimeError):
            document_batch.write_all([self._todo("One")], raises, "created")
        self.assertEqual(frappe.db._disable_transaction_control, before)

    def test_a_callers_raised_transaction_control_is_kept(self):
        self._needs_transaction_control()
        creator = DocumentCreate()
        frappe.db._disable_transaction_control += 1  # as Frappe does around a doc_events hook
        try:
            raised = frappe.db._disable_transaction_control
            seen = []

            def write(entry):
                seen.append(frappe.db._disable_transaction_control)
                return creator.execute(dict(entry))

            document_batch.write_all([self._todo("Inside a hook")], write, "created")

            self.assertGreater(seen[0], raised)
            self.assertEqual(frappe.db._disable_transaction_control, raised)
        finally:
            frappe.db._disable_transaction_control -= 1

    # -- the audit trail and single records (#34396) -----------------------------------------

    def test_a_batch_call_is_audited_with_its_doctypes(self):
        def target_of_last_call(tool_name):
            return frappe.get_all(
                "Assistant Audit Log",
                filters={"tool_name": tool_name, "input_data": ["like", f"%{self.tag}%"]},
                fields=["target_doctype", "target_name"],
                order_by="creation desc",
                limit=1,
            )[0]

        created = self._run(
            "create_document",
            {
                "documents": [
                    self._todo("One"),
                    {"doctype": "Note", "data": {"title": f"Two {self.tag}"}},
                    self._todo("Three"),
                ]
            },
        )
        self.assertTrue(created["success"], created)
        self.assertEqual(target_of_last_call("create_document").target_doctype, "ToDo, Note")

        (todo,) = self._make_todos("Keep me")
        not_a_status = {"status": f"Not A Status {self.tag}"}
        failed = self._run(
            "update_document", {"documents": [{"doctype": "ToDo", "name": todo, "data": not_a_status}]}
        )
        self.assertFalse(failed["success"], failed)
        row = target_of_last_call("update_document")
        self.assertEqual((row.target_doctype, row.target_name), ("ToDo", todo))

    def test_one_customisation_record_on_its_own_is_still_created(self):
        role = f"FAC Single {self.tag}"

        response = self._run("create_document", {"doctype": "Role", "data": {"role_name": role}})

        self.assertTrue(response["success"], response)
        self.assertEqual(response["result"]["name"], role)
        self.assertTrue(frappe.db.exists("Role", role))

    def test_one_customisation_record_on_its_own_is_still_updated(self):
        role = frappe.get_doc({"doctype": "Role", "role_name": f"FAC Single {self.tag}", "desk_access": 1})
        role.insert()

        response = self._run(
            "update_document", {"doctype": "Role", "name": role.name, "data": {"desk_access": 0}}
        )

        self.assertTrue(response["success"], response)
        self.assertEqual(frappe.db.get_value("Role", role.name, "desk_access"), 0)

    def test_the_list_descriptions_say_customisations_go_one_at_a_time(self):
        for tool_name in ("create_document", "update_document"):
            tool = self.registry.get_tool(tool_name)
            texts = {
                "description": tool.description,
                "documents": tool.inputSchema["properties"]["documents"]["description"],
            }
            for where, text in texts.items():
                with self.subTest(tool=tool_name, where=where):
                    self.assertIn("one at a time", text)
                    self.assertIn("customisation", text.lower())
                    self.assertIn("schema", text.lower())
                    self.assertNotIn("any doctypes", text.lower())

    def test_create_document_description_says_a_file_goes_through_the_import_tools(self):
        description = self.registry.get_tool("create_document").description

        self.assertIn("not a way to import a user's file", description)
        self.assertIn("start_import_session", description)
        self.assertIn("if they fail, stop and tell the user", description)
        self.assertIn("import_session", description.replace("start_import_session", ""))

    # -- update_document ---------------------------------------------------------------------

    def _make_todos(self, *texts):
        return [
            frappe.get_doc({"doctype": "ToDo", "description": f"{t} {self.tag}"}).insert().name for t in texts
        ]

    def test_one_call_updates_several_records(self):
        first, second = self._make_todos("Old one", "Old two")

        response = self._run(
            "update_document",
            {
                "documents": [
                    {"doctype": "ToDo", "name": first, "data": {"description": f"New one {self.tag}"}},
                    {"doctype": "ToDo", "name": second, "data": {"priority": "High"}},
                ]
            },
        )

        self.assertTrue(response["success"], response)
        self.assertEqual(
            response["result"]["updated"],
            [{"doctype": "ToDo", "name": first}, {"doctype": "ToDo", "name": second}],
        )
        self.assertEqual(frappe.db.get_value("ToDo", first, "description"), f"New one {self.tag}")
        self.assertEqual(frappe.db.get_value("ToDo", second, "priority"), "High")

    def test_validate_only_with_an_update_list_changes_nothing(self):
        # The approval card words a validate_only call as a check, so the user approves a check:
        # a list must be checked record by record, as one record is, and none saved.
        first, second = self._make_todos("Old one", "Old two")

        def refuses_high_priority(doc, *args, **kwargs):
            if doc.priority == "High":
                frappe.throw(frappe._("No high priority here"))

        with patch.object(ToDo, "validate", refuses_high_priority):
            response = self._run(
                "update_document",
                {
                    "documents": [
                        {"doctype": "ToDo", "name": first, "data": {"description": f"New one {self.tag}"}},
                        {"doctype": "ToDo", "name": second, "data": {"priority": "High"}},
                    ],
                    "validate_only": True,
                },
            )

        self.assertFalse(response["success"], response)
        self.assertIn("No high priority here", response["result"]["documents"][1]["error"])
        result = response["result"]
        self.assertEqual(
            [(d["document"], d["name"], d["validation_passed"]) for d in result["documents"]],
            [(1, first, True), (2, second, False)],
        )
        self.assertIn("Nothing was changed", result["message"])
        self.assertEqual(frappe.db.get_value("ToDo", first, "description"), f"Old one {self.tag}")
        self.assertEqual(frappe.db.get_value("ToDo", second, "priority"), "Medium")

    def test_validate_only_with_an_update_list_that_passes_saves_nothing(self):
        first, second = self._make_todos("Old one", "Old two")

        response = self._run(
            "update_document",
            {
                "documents": [
                    {"doctype": "ToDo", "name": first, "data": {"description": f"New one {self.tag}"}},
                    {"doctype": "ToDo", "name": second, "data": {"priority": "High"}},
                ],
                "validate_only": True,
            },
        )

        self.assertTrue(response["success"], response)
        self.assertTrue(response["result"]["validation_passed"])
        self.assertNotIn("updated", response["result"])
        self.assertEqual(frappe.db.get_value("ToDo", first, "description"), f"Old one {self.tag}")
        self.assertEqual(frappe.db.get_value("ToDo", second, "priority"), "Medium")

    def test_one_update_failing_changes_none(self):
        (first,) = self._make_todos("Keep me")

        response = self._run(
            "update_document",
            {
                "documents": [
                    {"doctype": "ToDo", "name": first, "data": {"description": f"Changed {self.tag}"}},
                    {"doctype": "ToDo", "name": first, "data": {"status": "Not A Status"}},
                ]
            },
        )

        self.assertFalse(response["success"], response)
        self.assertIn("Document 2 (ToDo", response["result"]["error"])
        self.assertEqual(frappe.db.get_value("ToDo", first, "description"), f"Keep me {self.tag}")

    def test_a_failed_update_list_puts_a_moved_file_back(self):
        # Making a File public moves it on disk, and Frappe moves it back after a rollback
        file_doc = frappe.get_doc(
            {"doctype": "File", "file_name": f"batch-{self.tag}.txt", "content": b"secret", "is_private": 1}
        ).insert()
        (todo,) = self._make_todos("Keep me")
        try:
            response = self._run(
                "update_document",
                {
                    "documents": [
                        {"doctype": "File", "name": file_doc.name, "data": {"is_private": 0}},
                        {"doctype": "ToDo", "name": todo, "data": {"status": "Not A Status"}},
                    ]
                },
            )

            self.assertFalse(response["success"], response)
            file_doc.reload()
            self.assertEqual(file_doc.is_private, 1)
            self.assertTrue(os.path.exists(file_doc.get_full_path()), file_doc.get_full_path())
            public = frappe.get_site_path("public", "files", f"batch-{self.tag}.txt")
            self.assertFalse(os.path.exists(public), "the file is still served publicly")
        finally:
            frappe.delete_doc("File", file_doc.name, force=True, ignore_permissions=True)

    def test_an_update_list_is_checked_before_anything_is_written(self):
        (first,) = self._make_todos("Keep me")

        response = self._run(
            "update_document",
            {
                "documents": [
                    {"doctype": "ToDo", "name": first, "data": {"description": f"Changed {self.tag}"}},
                    {"doctype": "ToDo", "data": {"priority": "High"}},
                    {"doctype": "ToDo", "name": "no-such-todo", "data": {"priority": "High"}},
                ]
            },
        )

        self.assertFalse(response["success"], response)
        self.assertEqual(response["result"]["problems"][0]["document"], 2)
        self.assertEqual(frappe.db.get_value("ToDo", first, "description"), f"Keep me {self.tag}")

    def test_an_update_without_data_is_still_refused(self):
        (first,) = self._make_todos("Untouched")
        modified = frappe.db.get_value("ToDo", first, "modified")

        response = self._run("update_document", {"doctype": "ToDo", "name": first})

        self.assertFalse(response["success"], response)
        self.assertEqual(frappe.db.get_value("ToDo", first, "modified"), modified)  # not saved

    def test_an_update_list_and_a_single_record_together_are_refused(self):
        (first,) = self._make_todos("Keep me")

        response = self._run(
            "update_document",
            {
                "doctype": "ToDo",
                "name": first,
                "data": {"priority": "High"},
                "documents": [{"doctype": "ToDo", "name": first, "data": {"priority": "Low"}}],
            },
        )

        self.assertFalse(response["success"], response)
        self.assertIn("not both", response["result"]["error"])

    def test_an_update_list_with_edits_is_refused_not_saved_without_them(self):
        # edits work on one record (with name): beside documents they would be dropped and the
        # list saved without them, so the call is refused as documents beside name is.
        (first,) = self._make_todos("Keep me")
        modified = frappe.db.get_value("ToDo", first, "modified")

        response = self._run(
            "update_document",
            {
                "documents": [{"doctype": "ToDo", "name": first, "data": {"priority": "Low"}}],
                "edits": [{"field": "description", "find": "Keep", "replace": "Lost"}],
            },
        )

        self.assertFalse(response["success"], response)
        self.assertIn("not both", response["result"]["error"])
        self.assertEqual(frappe.db.get_value("ToDo", first, "modified"), modified)  # not saved

    def test_an_update_list_of_more_than_a_hundred_is_refused(self):
        documents = [{"doctype": "ToDo", "name": f"x{i}", "data": {"priority": "High"}} for i in range(101)]

        response = self._run("update_document", {"documents": documents})

        self.assertFalse(response["success"], response)
        self.assertIn("At most 100", response["result"]["error"])

    def test_a_record_the_user_may_not_change_stops_the_update_list(self):
        (others,) = self._make_todos("Administrator's")
        # Language "en" is on every site; only a System Manager may change it.
        english = frappe.db.get_value("Language", "en", "language_name")
        user = self.make_desk_user("updater")
        self.assert_cannot(user, "write", "Language", "en")
        frappe.set_user(user)
        # A user may create a ToDo that names them.
        mine = (
            frappe.get_doc({"doctype": "ToDo", "description": f"Mine {self.tag}", "allocated_to": user})
            .insert()
            .name
        )

        response = self._run(
            "update_document",
            {
                "documents": [
                    {"doctype": "ToDo", "name": mine, "data": {"priority": "High"}},
                    {"doctype": "Language", "name": "en", "data": {"language_name": f"Changed {self.tag}"}},
                    {"doctype": "Language", "name": "en", "data": {"enabled": 0}},
                ]
            },
        )

        self.assertFalse(response["success"], response)
        self.assertNotIn("error_type", response["result"])  # refused for permission, not as a customisation
        self.assertEqual([p["document"] for p in response["result"]["problems"]], [2, 3])
        frappe.set_user("Administrator")
        self.assertNotEqual(frappe.db.get_value("ToDo", mine, "priority"), "High")
        self.assertEqual(frappe.db.get_value("Language", "en", "language_name"), english)
        self.assertTrue(others)

    # -- keys that start with an underscore ------------------------------------------------------
    # As Administrator: the Assistant User role check refuses _assign and the like, but a System
    # Manager's call reaches the document with them (#34411).

    def _assert_refused_for_internal_keys(self, response):
        self.assertFalse(response["success"], response)
        self.assertEqual(response["result"].get("error_type"), "internal_key", response)
        self.assertIn("can't be set", response["result"]["error"])
        return response["result"]["problems"]

    def test_an_underscore_key_in_a_create_list_is_refused_before_anything_is_written(self):
        response = self._run(
            "create_document",
            {
                "documents": [
                    self._todo("Fine"),
                    {
                        "doctype": "ToDo",
                        "data": {"description": f"Assigned {self.tag}", "_assign": '["a@x.com"]'},
                    },
                ]
            },
        )

        self._assert_refused_for_internal_keys(response)
        self.assertEqual(self._todos(), set())

    def test_an_underscore_key_on_one_record_is_refused_too(self):
        # #34541: only a list's records were checked; one record still set _assign and the like
        response = self._run(
            "create_document",
            {"doctype": "ToDo", "data": {"description": f"Assigned {self.tag}", "_assign": '["a@x.com"]'}},
        )
        self._assert_refused_for_internal_keys(response)
        self.assertEqual(self._todos(), set())

        (todo,) = self._make_todos("Keep me")
        response = self._run(
            "update_document", {"doctype": "ToDo", "name": todo, "data": {"_liked_by": '["a@x.com"]'}}
        )
        self._assert_refused_for_internal_keys(response)
        self.assertFalse(frappe.db.get_value("ToDo", todo, "_liked_by"))

    def test_an_underscore_key_in_an_update_list_is_refused(self):
        first, second = self._make_todos("Keep one", "Keep two")

        response = self._run(
            "update_document",
            {
                "documents": [
                    {"doctype": "ToDo", "name": first, "data": {"description": f"Changed {self.tag}"}},
                    {"doctype": "ToDo", "name": second, "data": {"_liked_by": '["Administrator"]'}},
                ]
            },
        )

        problems = self._assert_refused_for_internal_keys(response)
        self.assertEqual([p["document"] for p in problems], [2])
        self.assertEqual(frappe.db.get_value("ToDo", first, "description"), f"Keep one {self.tag}")

    def test_an_underscore_key_in_a_child_row_is_refused(self):
        response = self._run(
            "create_document",
            {
                "documents": [
                    self._todo("Fine"),
                    {
                        "doctype": "Note",
                        "data": {
                            "title": f"Seen {self.tag}",
                            "seen_by": [{"user": "Administrator", "_comments": "[]"}],
                        },
                    },
                ]
            },
        )

        problems = self._assert_refused_for_internal_keys(response)
        self.assertEqual([p["document"] for p in problems], [2])
        self.assertIn("seen_by", problems[0]["error"])
        self.assertIn("_comments", problems[0]["error"])
        self.assertEqual(self._todos(), set())
        self.assertEqual(self._notes(), set())

    def test_the_refusal_names_the_record_and_the_key(self):
        response = self._run(
            "create_document",
            {
                "documents": [
                    self._todo("Fine"),
                    {"doctype": "ToDo", "data": {"description": f"x {self.tag}", "_user_tags": "urgent"}},
                    {
                        "doctype": "Note",
                        "data": {"title": f"y {self.tag}", "_assign": "[]", "_comments": "[]"},
                    },
                ]
            },
        )

        problems = self._assert_refused_for_internal_keys(response)
        self.assertEqual([(p["document"], p["doctype"]) for p in problems], [(2, "ToDo"), (3, "Note")])
        self.assertIn("_user_tags", problems[0]["error"])
        self.assertIn("_assign", problems[1]["error"])
        self.assertIn("_comments", problems[1]["error"])

    def test_newname_in_a_create_list_still_names_the_record(self):
        # Color is named by Prompt, as the masters plan's __newname records are.
        color = f"FAC Color {self.tag}"

        response = self._run(
            "create_document",
            {
                "documents": [
                    {"doctype": "Color", "data": {"color": "#123456", "__newname": color}},
                    self._todo("x"),
                ]
            },
        )

        self.assertTrue(response["success"], response)
        self.assertEqual(response["result"]["created"][0], {"doctype": "Color", "name": color})
        self.assertTrue(frappe.db.exists("Color", color))

    def test_delete_marker_in_an_update_list_still_removes_the_row(self):
        note = frappe.get_doc(
            {
                "doctype": "Note",
                "title": f"Seen {self.tag}",
                "seen_by": [{"user": "Administrator"}, {"user": "Guest"}],
            }
        ).insert()
        guest_row = next(row.name for row in note.seen_by if row.user == "Guest")
        (todo,) = self._make_todos("Also")

        response = self._run(
            "update_document",
            {
                "documents": [
                    {
                        "doctype": "Note",
                        "name": note.name,
                        "data": {"seen_by": [{"name": guest_row, "_delete": True}]},
                    },
                    {"doctype": "ToDo", "name": todo, "data": {"priority": "High"}},
                ]
            },
        )

        self.assertTrue(response["success"], response)
        self.assertEqual([row.user for row in frappe.get_doc("Note", note.name).seen_by], ["Administrator"])
