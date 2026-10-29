# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""get_current_code: the approval card diffs new code against what is stored, never leaking more."""

import frappe

from frappe_assistant_core.chat.api.current_code import (
    CARD_CODE_KEYS_BY_DOCTYPE,
    CODE_KEYS,
    GO_LIVE_KEYS,
    GO_LIVE_KEYS_BY_DOCTYPE,
    ROW_CODE_COLUMNS_BY_DOCTYPE,
    get_current_code,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest

READER = "current-code-reader@example.com"
OUTSIDER = "current-code-outsider@example.com"
STORED = "frappe.msgprint('stored')"


def _make_user(email: str, roles: list[str]) -> None:
    if frappe.db.exists("User", email):
        frappe.delete_doc("User", email, force=True, ignore_permissions=True)
    user = frappe.get_doc(
        {"doctype": "User", "email": email, "first_name": "Code", "send_welcome_email": 0}
    ).insert(ignore_permissions=True)
    user.add_roles(*roles)


class TestGetCurrentCode(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        _make_user(READER, ["System Manager"])
        _make_user(OUTSIDER, [])
        # Created as Administrator and left disabled, so the throwaway script never runs on the site.
        self.script = frappe.get_doc(
            {
                "doctype": "Client Script",
                "name": "current-code-test-script",
                "dt": "ToDo",
                "view": "Form",
                "enabled": 0,
                "script": STORED,
            }
        ).insert()

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.delete_doc("Client Script", self.script.name, force=True, ignore_permissions=True)
        for email in (READER, OUTSIDER):
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)
        super().tearDown()

    def test_returns_stored_code_for_a_user_who_can_read(self):
        frappe.set_user(READER)
        out = get_current_code("Client Script", self.script.name, ["script"])
        self.assertEqual(out, {"script": STORED})

    def test_refused_for_a_user_without_read(self):
        frappe.set_user(OUTSIDER)
        with self.assertRaises(frappe.PermissionError):
            get_current_code("Client Script", self.script.name, ["script"])

    def test_ignores_fields_that_are_not_code(self):
        out = get_current_code("Client Script", self.script.name, ["script", "dt", "enabled"])
        self.assertEqual(out, {"script": STORED})

    def test_ignores_another_doctypes_card_code_keys(self):
        out = get_current_code("Client Script", self.script.name, ["script", "depends_on", "raw_commands"])
        self.assertEqual(out, {"script": STORED})

    def test_accepts_a_json_encoded_field_list(self):
        out = get_current_code("Client Script", self.script.name, '["script", "dt"]')
        self.assertEqual(out, {"script": STORED})

    def test_code_keys_match_the_card(self):
        self.assertEqual(
            list(CODE_KEYS),
            ["script", "condition", "query", "html", "javascript", "report_script", "css", "message"],
        )


class TestGetCurrentCodeGoesLive(BaseAssistantTest):
    """A card switching a Notification on shows its stored subject, a Jinja template it emails."""

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        # Left disabled, as a dormant notification sits before the card that switches it on.
        self.notification = frappe.get_doc(
            {
                "doctype": "Notification",
                "name": "current-code-test-notification",
                "subject": "ToDo {{ doc.name }} changed",
                "document_type": "ToDo",
                "event": "New",
                "channel": "System Notification",
                "enabled": 0,
                "condition": "doc.priority == 'High'",
                "message": "Hello {{ doc.owner }}",
            }
        ).insert()

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.delete_doc("Notification", self.notification.name, force=True, ignore_permissions=True)
        super().tearDown()

    def test_returns_the_stored_subject_with_condition_and_message(self):
        out = get_current_code("Notification", self.notification.name, ["subject", "condition", "message"])
        self.assertEqual(
            out,
            {
                "subject": "ToDo {{ doc.name }} changed",
                "condition": "doc.priority == 'High'",
                "message": "Hello {{ doc.owner }}",
            },
        )

    def test_returns_a_fac_page_html_script_and_style(self):
        # Production reaches this draft when a builder saves a FAC Page before publishing it.
        page = frappe.get_doc(
            {
                "doctype": "FAC Page",
                "title": "Current code page",
                "slug": "current-code-page",
                "html": "<div id='app'></div>",
                "script": "render()",
                "style": ".x { color: red; }",
            }
        ).insert()
        out = get_current_code("FAC Page", page.name, ["html", "script", "style"])
        self.assertEqual(
            out, {"html": "<div id='app'></div>", "script": "render()", "style": ".x { color: red; }"}
        )

    def test_returns_the_roles_a_fac_page_goes_live_to(self):
        # Production reaches these drafts when a builder saves a FAC Page before publishing it;
        # the card switching it on must say who will see it.
        listed = frappe.get_doc(
            {
                "doctype": "FAC Page",
                "title": "Roles page",
                "slug": "current-code-roles",
                "roles": [{"role": "All"}, {"role": "Report Manager"}],
            }
        ).insert()
        unlisted = frappe.get_doc(
            {"doctype": "FAC Page", "title": "No roles page", "slug": "current-code-no-roles"}
        ).insert()
        _make_user(READER, ["System Manager"])
        self.addCleanup(frappe.delete_doc, "User", READER, force=True, ignore_permissions=True)
        frappe.set_user(READER)

        self.assertEqual(
            get_current_code("FAC Page", listed.name, ["html", "roles"]),
            {"html": "", "roles": ["All", "Report Manager"]},
        )
        self.assertEqual(get_current_code("FAC Page", unlisted.name, ["roles"]), {"roles": []})

        _make_user(OUTSIDER, [])
        self.addCleanup(frappe.delete_doc, "User", OUTSIDER, force=True, ignore_permissions=True)
        frappe.set_user(OUTSIDER)
        with self.assertRaises(frappe.PermissionError):
            get_current_code("FAC Page", listed.name, ["roles"])

    def test_returns_the_roles_a_report_reaches(self):
        # Production reaches this when a builder saves a Report Builder report for some roles.
        report = frappe.get_doc(
            {
                "doctype": "Report",
                "report_name": "Current code report",
                "ref_doctype": "ToDo",
                "report_type": "Report Builder",
                "is_standard": "No",
                "roles": [{"role": "System Manager"}, {"role": "Report Manager"}],
            }
        ).insert(ignore_permissions=True)
        out = get_current_code("Report", report.name, ["roles"])
        self.assertEqual(sorted(out["roles"]), ["Report Manager", "System Manager"])

    def test_go_live_keys_stay_out_of_the_code_keys(self):
        self.assertEqual(GO_LIVE_KEYS, ("subject", "style", "roles"))
        self.assertEqual(GO_LIVE_KEYS_BY_DOCTYPE["Report"], ("roles",))

    def test_every_card_code_key_is_code_on_some_doctype(self):
        from frappe_assistant_core.chat.api.current_code import CODE_KEYS_BY_DOCTYPE

        registered = {key for keys in CODE_KEYS_BY_DOCTYPE.values() for key in keys}
        self.assertLessEqual(set(CODE_KEYS), registered)
        for doctype, keys in CODE_KEYS_BY_DOCTYPE.items():
            meta = frappe.get_meta(doctype)
            for key in keys:
                self.assertIsNotNone(meta.get_field(key), (doctype, key))
        for key in GO_LIVE_KEYS:
            self.assertNotIn(key, CODE_KEYS)


class TestGetCurrentCodeCardKeys(BaseAssistantTest):
    """A card diffs a print's raw commands and a field's eval: condition against what is stored."""

    def test_returns_a_print_formats_raw_commands_and_layout(self):
        # Production reaches this when a builder saves a raw (label printer) print format.
        print_format = frappe.get_doc(
            {
                "doctype": "Print Format",
                "name": "Current code label",
                "doc_type": "ToDo",
                "raw_printing": 1,
                "raw_commands": "^XA^FD{{ doc.name }}^XZ",
                "format_data": "[]",
            }
        ).insert(ignore_permissions=True)
        out = get_current_code("Print Format", print_format.name, ["raw_commands", "format_data"])
        self.assertEqual(out, {"raw_commands": "^XA^FD{{ doc.name }}^XZ", "format_data": "[]"})

    def test_returns_a_custom_fields_conditions_but_not_another_doctypes(self):
        # Production reaches this when a builder adds a field shown only for open ToDos;
        # db_insert skips the column it would add (DDL commits, escaping the rollback).
        field = frappe.get_doc(
            {
                "doctype": "Custom Field",
                "name": "ToDo-current_code_note",
                "dt": "ToDo",
                "fieldname": "current_code_note",
                "fieldtype": "Data",
                "depends_on": "eval:doc.status == 'Open'",
            }
        )
        field.db_insert()
        out = get_current_code("Custom Field", field.name, ["depends_on", "read_only_depends_on", "label"])
        self.assertEqual(out, {"depends_on": "eval:doc.status == 'Open'", "read_only_depends_on": ""})

    def test_card_and_row_code_fields_exist_on_their_doctypes(self):
        for doctype, keys in CARD_CODE_KEYS_BY_DOCTYPE.items():
            meta = frappe.get_meta(doctype)
            for key in keys:
                self.assertIsNotNone(meta.get_field(key), (doctype, key))
        for doctype, tables in ROW_CODE_COLUMNS_BY_DOCTYPE.items():
            for table, columns in tables.items():
                child = frappe.get_meta(frappe.get_meta(doctype).get_field(table).options)
                for column in columns:
                    self.assertIsNotNone(child.get_field(column), (doctype, table, column))


class TestGetCurrentCodeRows(BaseAssistantTest):
    """A card diffs each child row's code against the stored row it stands for (#34690)."""

    def test_returns_each_transitions_identity_and_condition(self):
        for doctype, field, names in (
            ("Workflow State", "workflow_state_name", ("Pending", "Approved")),
            ("Workflow Action Master", "workflow_action_name", ("Approve",)),
        ):
            for name in names:
                if not frappe.db.exists(doctype, name):
                    frappe.get_doc({"doctype": doctype, field: name}).insert(ignore_permissions=True)
        # Production reaches this when a builder saves a Workflow whose approve move has a condition.
        # db_insert skips on_update, which would add a workflow_state column to ToDo (DDL commits).
        workflow = frappe.get_doc(
            {
                "doctype": "Workflow",
                "name": "Current code flow",
                "workflow_name": "Current code flow",
                "document_type": "ToDo",
                "workflow_state_field": "workflow_state",
                "transitions": [
                    {
                        "state": "Pending",
                        "action": "Approve",
                        "next_state": "Approved",
                        "allowed": "System Manager",
                        "condition": "doc.priority == 'High'",
                    }
                ],
            }
        )
        workflow.set_parent_in_children()
        workflow.db_insert()
        workflow.transitions[0].db_insert()
        out = get_current_code("Workflow", workflow.name, ["transitions"])
        self.assertEqual(
            out,
            {
                "transitions": [
                    {
                        "name": workflow.transitions[0].name,
                        "state": "Pending",
                        "action": "Approve",
                        "next_state": "Approved",
                        "condition": "doc.priority == 'High'",
                    }
                ]
            },
        )

    def test_returns_a_doctypes_field_conditions_and_markup_by_fieldname(self):
        # Production reaches this when a builder saves a custom DocType with a conditional field
        # and a banner; db_insert skips the table it would create (DDL commits).
        doctype = frappe.get_doc(
            {
                "doctype": "DocType",
                "name": "Current Code Fields",
                "module": "Custom",
                "custom": 1,
                "fields": [
                    {"fieldname": "notes", "fieldtype": "Data", "depends_on": "eval:doc.x"},
                    {"fieldname": "banner", "fieldtype": "HTML", "options": "<b>hi</b>"},
                ],
            }
        )
        doctype.set_parent_in_children()
        doctype.db_insert()
        for row in doctype.fields:
            row.db_insert()
        out = get_current_code("DocType", doctype.name, ["fields", "permissions"])
        blank = {"depends_on": "", "mandatory_depends_on": "", "read_only_depends_on": "", "options": ""}
        self.assertEqual(
            out,
            {
                "fields": [
                    {
                        **blank,
                        "name": doctype.fields[0].name,
                        "fieldname": "notes",
                        "fieldtype": "Data",
                        "depends_on": "eval:doc.x",
                    },
                    {
                        **blank,
                        "name": doctype.fields[1].name,
                        "fieldname": "banner",
                        "fieldtype": "HTML",
                        "options": "<b>hi</b>",
                    },
                ]
            },
        )

    def test_row_key_columns_exist_on_their_child_doctypes(self):
        from frappe_assistant_core.chat.api.current_code import (
            ROW_KEY_COLUMNS_BY_DOCTYPE,
            ROW_KIND_COLUMNS_BY_DOCTYPE,
        )

        self.assertEqual(set(ROW_KEY_COLUMNS_BY_DOCTYPE), set(ROW_CODE_COLUMNS_BY_DOCTYPE))
        for mapping in (ROW_KEY_COLUMNS_BY_DOCTYPE, ROW_KIND_COLUMNS_BY_DOCTYPE):
            for doctype, tables in mapping.items():
                for table, columns in tables.items():
                    child = frappe.get_meta(frappe.get_meta(doctype).get_field(table).options)
                    for column in columns:
                        self.assertIsNotNone(child.get_field(column), (doctype, table, column))
