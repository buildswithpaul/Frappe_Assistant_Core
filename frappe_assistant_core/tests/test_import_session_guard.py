# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""An import session's fields are the engine's (#34400, #34429): its user, or anyone else, can't
write them in Desk, over REST or with the document tools, and can't make a session that joins
another user's plan. Every test acts as a user Frappe checks, never as Administrator."""

import json
import unittest

import frappe
import frappe.client

from frappe_assistant_core.assistant_core.doctype.fac_import_session.fac_import_session import PLAN_FIELDS
from frappe_assistant_core.tests.test_import_run import MAPPING, ImportRunCase, approval_card
from frappe_assistant_core.utils import import_dry_run, import_run
from frappe_assistant_core.utils.import_session import readable_session_file

SESSION = "FAC Import Session"


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Customer")
class SessionGuardCase(ImportRunCase):
    def setUp(self):
        super().setUp()
        # A Sales Master Manager may import Customers; Desk User gives them their own import sessions.
        self.owner_user = self.make_throwaway_user("owner", roles=("Sales Master Manager", "Desk User"))
        self.assertNotIn("System Manager", frappe.get_roles(self.owner_user))

    def _failed_session(self, user=None):
        """The user's own session whose dry run failed: two rows ready, two failing. The user
        uploads the file and runs the tools, as in production."""
        frappe.set_user(user or self.owner_user)
        n = self._names()
        lines = [",".join(MAPPING)] + [
            f"{n['alpha']},{self.group},Company",
            f"{n['beta']},Nowhere {self.tag},Company",
            f"{n['gamma']},Retial {self.tag},Company",
            f"{n['delta']},{self.group},Company",
        ]
        file_doc = self._file("customers.csv", ("\n".join(lines) + "\n").encode())
        session = self._run("start_import_session", {"file_url": file_doc.file_url})["result"]["session_id"]
        mapped = self._run(
            "set_column_mapping", {"session": session, "mapping": MAPPING, "doctype": "Customer"}
        )
        self.assertTrue(mapped["success"], mapped)
        checked = self._run("dry_run_import", {"session": session})["result"]
        self.assertEqual(checked["status"], "Dry Run Failed", checked)
        return session, checked

    def _stored(self, session, fields=("status", "validated_fingerprint")):
        return frappe.db.get_value(SESSION, session, list(fields), as_dict=True)

    def _rows(self, session, table):
        child = frappe.get_meta(SESSION).get_field(table).options
        return frappe.get_all(
            child,
            filters={"parent": session, "parenttype": SESSION, "parentfield": table},
            fields=["*"],
            order_by="idx",
        )

    def _forge_ready(self, session):
        """What a user who can write the session sends: status Ready to Import, and the
        fingerprint recomputed the way the dry run does."""
        doc = frappe.get_doc(SESSION, session)
        doc.status = "Ready to Import"
        doc.validated_fingerprint = import_dry_run.fingerprint(doc, readable_session_file(doc))
        return doc

    def _someone_elses_data_import(self):
        """Another user's Data Import, made in Desk."""
        current = frappe.session.user
        frappe.set_user("Administrator")
        name = (
            frappe.get_doc(
                {
                    "doctype": "Data Import",
                    "reference_doctype": "Customer",
                    "import_type": "Insert New Records",
                }
            )
            .insert()
            .name
        )
        frappe.set_user(current)
        return name


class TestWritesToAnExistingSession(SessionGuardCase):
    # -- criterion 1 and 2: a forged dry-run verdict ----------------------------------------

    def test_the_owner_cannot_mark_a_session_ready_with_a_recomputed_fingerprint(self):
        session, _checked = self._failed_session()
        before = self._stored(session)

        with self.assertRaises(frappe.PermissionError):
            self._forge_ready(session).save()

        self.assertEqual(self._stored(session), before)
        self.assertEqual(before.status, "Dry Run Failed")

    def test_a_system_manager_cannot_mark_a_session_ready_either(self):
        manager = self.make_throwaway_user("manager", roles=("System Manager", "Sales Master Manager"))
        session, _checked = self._failed_session(manager)
        before = self._stored(session)

        with self.assertRaises(frappe.PermissionError):
            self._forge_ready(session).save()

        self.assertEqual(self._stored(session), before)

    def test_start_import_still_refuses_after_the_owner_tries_to_mark_it_ready(self):
        # A System Manager (not Administrator) may use Data Import, so start_import reaches the
        # dry-run check; a Desk User without Data Import is refused before it (asserted below).
        for user in (
            self.owner_user,
            self.make_throwaway_user("manager", roles=("System Manager", "Sales Master Manager")),
        ):
            with self.subTest(user=user):
                session, checked = self._failed_session(user)
                imports = frappe.db.count("Data Import")
                try:
                    self._forge_ready(session).save()
                except frappe.PermissionError:
                    pass

                reply = self._run(
                    "start_import", approval_card(session, checked, "Customer", "Insert New Records")
                )

                self.assertFalse(reply["success"], reply)
                if "System Manager" in frappe.get_roles(user):
                    self.assertIn("dry_run_import first", reply["result"]["error"])
                self.assertEqual(frappe.db.count("Data Import"), imports)
                self.assertFalse(self._rows(session, "data_imports"))
                self.assertEqual(self._imported(), set())

    # -- criterion 3: every field ------------------------------------------------------------

    def _forged_values(self, session):
        other_file = self._file("other.csv", b"Customer Name\nX\n").name
        return {
            "file_name": "forged.csv",
            "started_on": "2020-01-01 00:00:00",
            "source_file": other_file,
            "original_file": other_file,
            "file_source": "Google Sheet",
            "source_url": "https://example.com/forged.csv",
            "sheet": "Other",
            "status": "Ready to Import",
            "user": self.make_throwaway_user("other", roles=("Desk User",)),
            "chat_session_id": "forged-chat",
            "parent_session": session,
            "target_doctype": "Supplier",
            "import_type": "Update Existing Records",
            "match_key": "customer_name",
            "submit_after_import": 1,
            "sheets": '[{"name": "Other", "columns": ["Customer Name"]}]',
            "template_options": '{"column_to_field_map": {"Customer Name": "customer_details"}}',
            "transformation_rules": '{"Customer Name": "upper"}',
            "excluded_rows": "[2, 3, 4, 5]",
            "validation_summary": '{"ready": 4, "failed": 0}',
            "validation_results": "/private/files/forged.json",
            "validated_fingerprint": "forged",
            "progress": '{"step": "Import", "state": "running"}',
        }

    def test_every_engine_owned_field_refuses_a_change_from_the_owner(self):
        session, _checked = self._failed_session()
        forged = self._forged_values(session)
        meta = frappe.get_meta(SESSION)
        data_fields = {
            df.fieldname
            for df in meta.fields
            if df.fieldtype not in frappe.model.no_value_fields
            and df.fieldtype not in frappe.model.table_fields
        }
        # Every field is here, but the plan's: before_save keeps those (test_import_plan).
        self.assertEqual(set(forged), data_fields - set(PLAN_FIELDS))

        for field, value in forged.items():
            with self.subTest(field=field):
                before = frappe.db.get_value(SESSION, session, field)
                doc = frappe.get_doc(SESSION, session)
                doc.set(field, value)

                with self.assertRaises(frappe.PermissionError):
                    doc.save()

                self.assertEqual(frappe.db.get_value(SESSION, session, field), before)

    # -- criterion 4: the child tables -------------------------------------------------------

    def test_the_owner_cannot_add_a_data_import_link(self):
        session, _checked = self._failed_session()
        theirs = self._someone_elses_data_import()
        doc = frappe.get_doc(SESSION, session)
        doc.append("data_imports", {"data_import": theirs, "purpose": "Import", "status": "Success"})

        with self.assertRaises(frappe.PermissionError):
            doc.save()

        self.assertFalse(self._rows(session, "data_imports"))

    def test_the_owner_cannot_add_a_created_record(self):
        session, _checked = self._failed_session()
        doc = frappe.get_doc(SESSION, session)
        # the sign-off report and the fix links read what this table lists
        doc.append("created_records", {"record_doctype": "Customer Group", "record_name": self.group})

        with self.assertRaises(frappe.PermissionError):
            doc.save()

        self.assertFalse(self._rows(session, "created_records"))

    def test_the_owner_cannot_edit_or_remove_a_step(self):
        session, _checked = self._failed_session()
        before = self._rows(session, "steps")
        self.assertTrue(before)

        for change in ("edit", "remove"):
            with self.subTest(change=change):
                doc = frappe.get_doc(SESSION, session)
                if change == "edit":
                    doc.steps[-1].message = "Dry run passed."
                    doc.steps[-1].outcome = "Success"
                else:
                    doc.remove(doc.steps[-1])

                with self.assertRaises(frappe.PermissionError):
                    doc.save()

                self.assertEqual(self._rows(session, "steps"), before)

    # -- a row on its own (Paul's review of 49da112) -------------------------------------------

    def test_a_row_cannot_be_written_on_its_own(self):
        # PUT /api/resource/FAC Import Session Step/<row> saved the row alone, past the session's
        # guard: the session was loaded from the database and saw no change (#34400). Production
        # reaches each case below over REST: PUT and POST on the row's DocType, and a delete.
        session, _checked = self._failed_session()
        tables = ("steps", "created_records", "data_imports")
        before = {table: self._rows(session, table) for table in tables}
        step = before["steps"][-1].name

        def edit_a_step():
            row = frappe.get_doc("FAC Import Session Step", step)
            row.message = "FORGED by the owner over REST"
            row.save()

        def add_a_record():
            frappe.get_doc(
                {
                    "doctype": "FAC Import Session Record",
                    "parent": session,
                    "parenttype": SESSION,
                    "parentfield": "created_records",
                    "record_doctype": "Customer Group",
                    "record_name": self.group,
                }
            ).insert()

        for name, write in (("edit a step", edit_a_step), ("add a record", add_a_record)):
            with self.subTest(write=name), self.assertRaises(frappe.PermissionError):
                write()

        # A System Manager may delete a session, but not rewrite its audit log a row at a time.
        frappe.set_user(self.make_throwaway_user("manager", roles=("System Manager",)))
        with self.assertRaises(frappe.PermissionError):
            frappe.delete_doc("FAC Import Session Step", step)

        frappe.set_user("Administrator")
        self.assertEqual({table: self._rows(session, table) for table in tables}, before)

    # -- criterion 5 and 6: REST and the document tools -------------------------------------

    def test_frappe_client_set_value_cannot_change_the_status(self):
        session, _checked = self._failed_session()
        before = self._stored(session)

        with self.assertRaises(frappe.PermissionError):
            frappe.client.set_value(SESSION, session, "status", "Ready to Import")

        self.assertEqual(self._stored(session), before)

    def test_frappe_client_save_cannot_change_created_records(self):
        session, _checked = self._failed_session()
        # What Desk or PUT /api/resource sends: the record as JSON, with a row added.
        sent = json.loads(frappe.as_json(frappe.get_doc(SESSION, session).as_dict()))
        sent["created_records"] = [{"record_doctype": "Customer Group", "record_name": self.group}]

        with self.assertRaises(frappe.PermissionError):
            frappe.client.save(sent)

        self.assertFalse(self._rows(session, "created_records"))

    def test_update_document_cannot_change_an_import_sessions_status(self):
        session, _checked = self._failed_session()
        before = self._stored(session)

        for data in ({"status": "Ready to Import"}, {"validated_fingerprint": "forged"}):
            with self.subTest(data=data):
                reply = self._run("update_document", {"doctype": SESSION, "name": session, "data": data})

                self.assertFalse(reply["success"], reply)
                self.assertEqual(self._stored(session), before)

    # -- criterion 7: Desk's Save on a form nobody changed ----------------------------------

    def test_saving_an_unchanged_session_is_allowed(self):
        session, _checked = self._failed_session()
        before = self._stored(session, ("status", "validated_fingerprint", "template_options", "modified"))

        frappe.get_doc(SESSION, session).save()
        # Desk's Save sends the form as JSON: dates as text, JSON fields as text
        frappe.client.save(json.loads(frappe.as_json(frappe.get_doc(SESSION, session).as_dict())))

        after = self._stored(session, ("status", "validated_fingerprint", "template_options"))
        self.assertEqual(after, {k: v for k, v in before.items() if k != "modified"})

    # -- criterion 15: delete ----------------------------------------------------------------

    def test_the_owner_cannot_delete_a_session(self):
        session, _checked = self._failed_session()

        with self.assertRaises(frappe.PermissionError):
            frappe.delete_doc(SESSION, session)

        self.assertTrue(frappe.db.exists(SESSION, session))

    # -- result_of: a Data Import that isn't the session's -----------------------------------

    def test_result_of_refuses_another_users_data_import(self):
        session, _checked = self._failed_session()
        theirs = self._someone_elses_data_import()
        self.assert_cannot(self.owner_user, "read", "Data Import", theirs)

        with self.assertRaises(frappe.PermissionError):
            import_run.result_of(frappe.get_doc(SESSION, session), theirs)


class TestInserts(SessionGuardCase):
    def _plan_of_another_user(self):
        """User A's plan: A's first session, keeping the plan, as plan_migration leaves it."""
        frappe.set_user("Administrator")
        session, _checked = self._ready_session()
        reply = self._run("plan_migration", {"sessions": [session]})
        self.assertTrue(reply["success"], reply)
        plan = reply["result"]["plan"]
        self.assertEqual(frappe.db.get_value(SESSION, plan, "migration_plan"), plan)
        return plan

    # -- criterion 8: plan fields -------------------------------------------------------------

    def test_another_user_cannot_insert_a_session_into_a_plan(self):
        plan = self._plan_of_another_user()
        frappe.set_user(self.owner_user)

        with self.assertRaises(frappe.PermissionError):
            frappe.client.insert(
                {
                    "doctype": SESSION,
                    "user": self.owner_user,
                    "migration_plan": plan,
                    "plan_position": 1,
                    "status": "Ready to Import",
                    "validated_fingerprint": "recomputed",
                }
            )

        self.assertFalse(frappe.get_all(SESSION, filters={"migration_plan": plan, "user": self.owner_user}))

    def test_each_plan_field_is_refused_on_insert(self):
        plan = self._plan_of_another_user()
        values = {
            "migration_plan": plan,
            "plan_position": 1,
            "plan_reason": "Goes first.",
            "plan_settings": '{"status": "Ready to Run"}',
            "plan_status": "Ready to Run",
            "plan_failure_rule": "stop",
            "plan_cut_off": "2026-09-30",
            "plan_stop_requested": 1,
            "plan_importing_now": plan,
        }
        self.assertEqual(set(values), set(PLAN_FIELDS))
        frappe.set_user(self.owner_user)

        for field, value in values.items():
            with self.subTest(field=field):
                with self.assertRaises(frappe.PermissionError):
                    frappe.client.insert({"doctype": SESSION, "user": self.owner_user, field: value})

        self.assertFalse(frappe.get_all(SESSION, filters={"user": self.owner_user}))

    # -- criterion 9: other fields ---------------------------------------------------------

    def test_an_insert_that_sets_engine_owned_fields_is_refused(self):
        theirs = self._someone_elses_data_import()
        frappe.set_user(self.owner_user)
        for extra in (
            {"status": "Ready to Import"},
            {"validated_fingerprint": "recomputed"},
            {"template_options": '{"column_to_field_map": {"Customer Name": "customer_name"}}'},
            {"data_imports": [{"data_import": theirs, "purpose": "Import"}]},
            {"created_records": [{"record_doctype": "Customer Group", "record_name": self.group}]},
        ):
            with self.subTest(extra=list(extra)):
                with self.assertRaises(frappe.PermissionError):
                    frappe.client.insert({"doctype": SESSION, "user": self.owner_user, **extra})

        self.assertFalse(frappe.get_all(SESSION, filters={"user": self.owner_user}))

    # -- criterion 10: for another user ------------------------------------------------------

    def test_a_session_cannot_be_inserted_for_another_user(self):
        other = self.make_throwaway_user("other", roles=("Desk User",))
        frappe.set_user(self.owner_user)

        with self.assertRaises(frappe.PermissionError):
            frappe.client.insert({"doctype": SESSION, "user": other})

        self.assertFalse(frappe.get_all(SESSION, filters={"user": other}))


class TestStuckSessions(SessionGuardCase):
    """#34538: a session no tool moves on any more can be ended, through the engine."""

    def test_the_patch_ends_the_sessions_undo_left_behind(self):
        from frappe_assistant_core.patches.v3_2 import end_import_undo_sessions
        from frappe_assistant_core.utils.import_session import HOLDING_STATUSES

        sessions = [self._failed_session()[0], self._failed_session()[0]]
        frappe.set_user("Administrator")
        # What a session undoing, or partly undone, when undo was removed still holds on a site.
        for name, status in zip(sessions, ("Undoing", "Partially Undone")):
            frappe.db.set_value(SESSION, name, "status", status)

        end_import_undo_sessions.execute()

        for name in sessions:
            doc = frappe.get_doc(SESSION, name)
            self.assertEqual(doc.status, "Partially Completed")
            self.assertIn("undo", doc.steps[-1].message)
        self.assertFalse({"Undoing", "Partially Undone"} & set(HOLDING_STATUSES))

    def test_a_system_manager_can_release_a_stuck_session(self):
        from frappe_assistant_core.assistant_core.doctype.fac_import_session.fac_import_session import release

        session, _checked = self._failed_session()
        frappe.db.set_value(SESSION, session, "status", "Importing")  # its worker died mid-import

        with self.assertRaises(frappe.PermissionError):
            release(session)  # not its owner: an import's state is the engine's

        frappe.set_user(self.make_throwaway_user("manager", roles=("System Manager",)))
        release(session)

        doc = frappe.get_doc(SESSION, session)
        self.assertEqual(doc.status, "Cancelled")
        self.assertIn("Released", doc.steps[-1].message)
        with self.assertRaises(frappe.ValidationError):
            release(session)  # it has ended already
