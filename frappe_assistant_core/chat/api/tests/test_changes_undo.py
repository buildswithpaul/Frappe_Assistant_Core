"""The Changes block and the Undo endpoint: undo deletes only what the chat itself created."""

import json
from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api.block_builder import add_changes_made
from frappe_assistant_core.chat.api.changes import undo_change
from frappe_assistant_core.tests.base_test import BaseAssistantTest

DOCTYPE = "Role"


class TestChangesUndo(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.owner = self.make_throwaway_user("undo-owner", roles=("System Manager",))
        self.sid = f"undo-{frappe.generate_hash(length=8)}"
        self.message_id = f"msg-{frappe.generate_hash(length=8)}"
        # The order a real turn writes: the user's message, then the record the chat creates
        # while it runs, then the assistant row at stream end, where the relay calls
        # add_changes_made when AR sends changes_made.
        self._make_message(self.owner, self.sid, f"user-{self.message_id}", "user")
        self.created = self._make_style(self.owner)
        self.message = self._make_message(self.owner, self.sid, self.message_id)
        add_changes_made(self.message, [self._change(self.created)])

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _make_message(self, user, session_id, message_id, role="assistant"):
        return (
            frappe.get_doc(
                {
                    "doctype": "FAC Chat Message",
                    "session_id": session_id,
                    "message_id": message_id,
                    "user": user,
                    "role": role,
                    "content": "Created it",
                }
            )
            .insert(ignore_permissions=True)
            .name
        )

    def _make_style(self, user=None):
        # Stands in for a record the chat's own create tool made, as the chat's user.
        frappe.set_user(user or self.owner)
        try:
            return self._insert_style()
        finally:
            frappe.set_user("Administrator")

    def _insert_style(self):
        return (
            frappe.get_doc({"doctype": DOCTYPE, "role_name": f"undo-{frappe.generate_hash(length=8)}"})
            .insert(ignore_permissions=True)
            .name
        )

    @staticmethod
    def _change(name, doctype=DOCTYPE):
        return {
            "tool": "create_document",
            "doctype": doctype,
            "name": name,
            "action": "create",
            "undo": "delete",
        }

    def _link_to_created(self):
        # Something the user did after the create now points at the record.
        frappe.get_doc(
            {"doctype": "Custom DocPerm", "parent": "Note", "role": self.created, "permlevel": 0, "read": 1}
        ).insert(ignore_permissions=True)

    def _block(self, message=None):
        raw = frappe.db.get_value("FAC Chat Message", message or self.message, "blocks")
        return [b for b in json.loads(raw) if b["type"] == "changes_made"]

    def _undo(self, name=None, doctype=DOCTYPE, session_id=None, message_id=None):
        return undo_change(
            session_id or self.sid, message_id or self.message_id, doctype, name or self.created
        )

    def test_undo_deletes_a_listed_create_and_marks_it(self):
        frappe.set_user(self.owner)
        self.assertEqual(self._undo(), {"success": True})
        self.assertFalse(frappe.db.exists(DOCTYPE, self.created))
        change = self._block()[0]["changes"][0]
        self.assertTrue(change["undone"])
        self.assertNotIn("tool", change)

    def test_undo_refuses_another_users_session(self):
        stranger = self.make_throwaway_user("undo-stranger")
        frappe.set_user(stranger)
        with self.assertRaises(frappe.PermissionError):
            self._undo()
        self.assertTrue(frappe.db.exists(DOCTYPE, self.created))

    def test_undo_refuses_an_unlisted_record(self):
        other = self._make_style()
        frappe.set_user(self.owner)
        with self.assertRaises(frappe.PermissionError):
            self._undo(name=other)
        self.assertTrue(frappe.db.exists(DOCTYPE, other))

    def test_undo_refuses_a_message_of_another_session(self):
        frappe.set_user(self.owner)
        with self.assertRaises(frappe.PermissionError):
            self._undo(session_id=f"other-{frappe.generate_hash(length=8)}")
        self.assertTrue(frappe.db.exists(DOCTYPE, self.created))

    def test_undo_refuses_twice(self):
        frappe.set_user(self.owner)
        self._undo()
        with self.assertRaises(frappe.PermissionError):
            self._undo()

    def test_undo_refuses_without_delete_permission(self):
        member = self.make_throwaway_user("undo-member")
        # A user who owns the session but lacks delete rights on the doctype.
        frappe.db.set_value("FAC Chat Message", self.message, "user", member)
        frappe.set_user(member)
        with self.assertRaises(frappe.PermissionError):
            self._undo()
        self.assertTrue(frappe.db.exists(DOCTYPE, self.created))
        self.assertFalse(self._block()[0]["changes"][0]["undone"])

    def test_linked_record_is_not_deleted(self):
        self._link_to_created()
        frappe.set_user(self.owner)
        result = self._undo()
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "Something now links to it")
        self.assertTrue(frappe.db.exists(DOCTYPE, self.created))
        self.assertFalse(self._block()[0]["changes"][0]["undone"])

    def test_blocks_merge_per_message(self):
        second = self._make_style()
        add_changes_made(self.message, [self._change(self.created), self._change(second)])
        blocks = self._block()
        self.assertEqual(len(blocks), 1)
        self.assertEqual([c["name"] for c in blocks[0]["changes"]], [self.created, second])

    def test_undo_refuses_a_system_manager_in_someone_elses_chat(self):
        other_admin = self.make_throwaway_user("undo-admin", roles=("System Manager",))
        frappe.set_user(other_admin)
        with self.assertRaises(frappe.PermissionError):
            self._undo()
        self.assertTrue(frappe.db.exists(DOCTYPE, self.created))

    def test_linked_record_rolls_back_what_on_trash_did(self):
        self._link_to_created()
        marker = f"marker-{frappe.generate_hash(length=6)}"

        def on_trash_side_effect(doc, *args, **kwargs):
            # Stands in for an app whose on_trash removes related rows (Customer deletes its Contacts).
            frappe.db.set_value("FAC Chat Message", self.message, "content", marker)

        frappe.set_user(self.owner)
        with patch("frappe.core.doctype.role.role.Role.on_trash", on_trash_side_effect, create=True):
            result = self._undo()
        self.assertFalse(result["success"])
        self.assertTrue(frappe.db.exists(DOCTYPE, self.created))
        self.assertNotEqual(frappe.db.get_value("FAC Chat Message", self.message, "content"), marker)

    def test_undo_refuses_a_record_recreated_by_someone_else(self):
        # The user deleted the record by hand, then another user made one of the same name.
        frappe.delete_doc(DOCTYPE, self.created, force=True)
        other = self.make_throwaway_user("undo-other", roles=("System Manager",))
        frappe.set_user(other)
        frappe.get_doc({"doctype": DOCTYPE, "role_name": self.created}).insert(ignore_permissions=True)
        frappe.set_user(self.owner)
        result = self._undo()
        self.assertEqual(
            result, {"success": False, "reason": "This record has changed since the chat created it"}
        )
        self.assertTrue(frappe.db.exists(DOCTYPE, self.created))

    def test_undo_of_a_record_already_gone_succeeds_and_marks_it(self):
        frappe.delete_doc(DOCTYPE, self.created, force=True)
        frappe.set_user(self.owner)
        self.assertEqual(self._undo(), {"success": True})
        self.assertTrue(self._block()[0]["changes"][0]["undone"])

    def test_undo_refuses_a_record_the_user_made_before_the_turn(self):
        # The user made a record by hand, then asked in a new turn; the chat's list names it.
        earlier = self._make_style(self.owner)
        self._make_message(self.owner, self.sid, "user-later", "user")
        later = self._make_message(self.owner, self.sid, "later")
        add_changes_made(later, [self._change(earlier)])
        frappe.set_user(self.owner)
        result = self._undo(name=earlier, message_id="later")
        self.assertEqual(
            result, {"success": False, "reason": "This record has changed since the chat created it"}
        )
        self.assertTrue(frappe.db.exists(DOCTYPE, earlier))
