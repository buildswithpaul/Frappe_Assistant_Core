# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""FAC Chat Project: ownership, validation, and the project endpoints."""

import frappe

from frappe_assistant_core.chat.doctype.fac_chat_project.fac_chat_project import (
    INSTRUCTIONS_MAX_LENGTH,
    FACChatProject,
    project_addendum,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest

OTHER_USER = "fac-projects-other@example.com"


def ensure_user(email: str) -> str:
    if not frappe.db.exists("User", email):
        frappe.get_doc(
            {"doctype": "User", "email": email, "first_name": "Other", "send_welcome_email": 0}
        ).insert(ignore_permissions=True)
    return email


def make_project(user: str, title: str = "Q3 Close", instructions: str = "") -> str:
    return (
        frappe.get_doc(
            {"doctype": "FAC Chat Project", "user": user, "title": title, "instructions": instructions}
        )
        .insert(ignore_permissions=True)
        .name
    )


class TestFACChatProjectDocType(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; runs in an isolated transaction
        frappe.set_user("Administrator")
        ensure_user(OTHER_USER)

    def test_instructions_over_limit_are_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            make_project("Administrator", instructions="x" * (INSTRUCTIONS_MAX_LENGTH + 1))

    def test_blank_title_is_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            make_project("Administrator", title="   ")

    def test_owned_refuses_another_users_project_like_a_missing_one(self):
        theirs = make_project(OTHER_USER)
        with self.assertRaises(frappe.DoesNotExistError):
            FACChatProject.owned(theirs, user="Administrator")
        with self.assertRaises(frappe.DoesNotExistError):
            FACChatProject.owned("no-such-project", user="Administrator")

    def test_project_addendum_is_none_without_instructions(self):
        self.assertIsNone(project_addendum(make_project("Administrator", instructions="  ")))

    def test_project_addendum_renders_the_block(self):
        name = make_project("Administrator", title="Q3 Close", instructions="Amounts in INR.")
        self.assertEqual(
            project_addendum(name),
            "\n\n## Project: Q3 Close\n"
            "The user is working inside this project. Follow these project instructions:\n"
            "Amounts in INR.\n",
        )
