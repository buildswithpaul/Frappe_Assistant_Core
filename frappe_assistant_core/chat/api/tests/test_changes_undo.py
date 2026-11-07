"""The Changes block and the Undo endpoint: undo deletes only what the chat itself created."""

import json

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
        self.message = self._make_message(self.owner, self.sid, self.message_id)
        self.created = self._make_style()
        # The relay calls add_changes_made when AR sends changes_made.
        add_changes_made(self.message, [self._change(self.created)])

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _make_message(self, user, session_id, message_id):
        # An assistant turn row, as the relay persists it at stream end.
        return (
            frappe.get_doc(
                {
                    "doctype": "FAC Chat Message",
                    "session_id": session_id,
                    "message_id": message_id,
                    "user": user,
                    "role": "assistant",
                    "content": "Created it",
                }
            )
            .insert(ignore_permissions=True)
            .name
        )

    def _make_style(self):
        # Stands in for a record the chat's own create tool made.
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
        # Something the user did after the create now points at the record.
        frappe.get_doc(
            {"doctype": "Custom DocPerm", "parent": "Note", "role": self.created, "permlevel": 0, "read": 1}
        ).insert(ignore_permissions=True)
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
