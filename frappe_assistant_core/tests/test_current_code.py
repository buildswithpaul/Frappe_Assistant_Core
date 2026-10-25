# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""get_current_code: the approval card diffs new code against what is stored, never leaking more."""

import frappe

from frappe_assistant_core.chat.api.current_code import (
    CODE_KEYS,
    GO_LIVE_KEYS,
    GO_LIVE_KEYS_BY_DOCTYPE,
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
        for key in GO_LIVE_KEYS:
            self.assertNotIn(key, CODE_KEYS)
