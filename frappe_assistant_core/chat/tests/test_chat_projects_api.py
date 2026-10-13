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


class TestProjectsApi(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; runs in an isolated transaction
        frappe.set_user("Administrator")
        ensure_user(OTHER_USER)

    def test_create_list_update(self):
        from frappe_assistant_core.chat.api.chat.projects import create_project, get_projects, update_project

        created = create_project("  Payroll   audit ", "Use FY 2026")
        self.assertEqual(created["title"], "Payroll audit")
        self.assertIn(created["name"], [p["name"] for p in get_projects()])
        updated = update_project(created["name"], instructions="")
        self.assertEqual(updated["instructions"], "")
        self.assertEqual(updated["title"], "Payroll audit")  # None left the title alone

    def test_get_projects_counts_only_live_conversations(self):
        from frappe_assistant_core.chat.api.chat.projects import get_projects
        from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import FACChatMessage

        name = make_project("Administrator")
        FACChatMessage.create_message("test-proj-count-1", "user", "a", project=name)
        FACChatMessage.create_message("test-proj-count-2", "user", "b", project=name)
        frappe.db.set_value("FAC Chat Conversation", "test-proj-count-2", "is_archived", 1)
        row = next(p for p in get_projects() if p["name"] == name)
        self.assertEqual(row["conversation_count"], 1)

    def test_get_projects_excludes_other_users(self):
        from frappe_assistant_core.chat.api.chat.projects import get_projects

        theirs = make_project(OTHER_USER)
        self.assertNotIn(theirs, [p["name"] for p in get_projects()])

    def test_update_and_delete_other_users_project_are_refused(self):
        from frappe_assistant_core.chat.api.chat.projects import delete_project, update_project

        theirs = make_project(OTHER_USER, title="Theirs")
        with self.assertRaises(frappe.DoesNotExistError):
            update_project(theirs, title="Hijack")
        with self.assertRaises(frappe.DoesNotExistError):
            delete_project(theirs)
        self.assertEqual(frappe.db.get_value("FAC Chat Project", theirs, "title"), "Theirs")

    def test_delete_unlinks_conversations_and_keeps_them(self):
        from frappe_assistant_core.chat.api.chat.projects import delete_project
        from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import FACChatMessage

        name = make_project("Administrator")
        FACChatMessage.create_message("test-proj-del-1", "user", "keep me", project=name)
        delete_project(name)
        self.assertFalse(frappe.db.exists("FAC Chat Project", name))
        self.assertTrue(frappe.db.exists("FAC Chat Conversation", "test-proj-del-1"))
        self.assertIsNone(frappe.db.get_value("FAC Chat Conversation", "test-proj-del-1", "project"))

    def test_boot_payload_projects_match_endpoint(self):
        from frappe_assistant_core.chat.api.chat.projects import get_projects
        from frappe_assistant_core.chat.api.init import _fetch_projects

        make_project("Administrator")
        self.assertEqual(_fetch_projects(), get_projects())

    def test_non_system_manager_can_create_list_and_update_own_project(self):
        from frappe_assistant_core.chat.api.chat.projects import create_project, get_projects, update_project

        # OTHER_USER has no roles, so Frappe treats it as a Website User: it gets neither the
        # System Manager bypass of if_owner nor of the permission query condition.
        # nosemgrep: frappe-setuser — exercising the endpoints as a non-System-Manager
        frappe.set_user(OTHER_USER)
        try:
            created = create_project("Mine", "be brief")
            self.assertIn(created["name"], [p["name"] for p in get_projects()])
            updated = update_project(created["name"], title="Mine renamed")
            self.assertEqual(updated["title"], "Mine renamed")
            self.assertEqual(frappe.db.get_value("FAC Chat Project", created["name"], "user"), OTHER_USER)
        finally:
            # nosemgrep: frappe-setuser — restore the test bootstrap user
            frappe.set_user("Administrator")

    def test_projects_order_is_most_recent_activity_first(self):
        from frappe_assistant_core.chat.api.chat.projects import get_projects

        older = make_project("Administrator", title="Older")
        newer = make_project("Administrator", title="Newer")
        frappe.db.set_value("FAC Chat Project", older, "last_activity", "2026-01-01 00:00:00")
        frappe.db.set_value("FAC Chat Project", newer, "last_activity", "2026-02-01 00:00:00")
        names = [p["name"] for p in get_projects()]
        self.assertLess(names.index(newer), names.index(older))
