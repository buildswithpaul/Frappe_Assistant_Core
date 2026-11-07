"""The Changes block and the Undo endpoint: undo deletes only what the chat itself created."""

import json
from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api import changes
from frappe_assistant_core.chat.api.block_builder import add_changes_made
from frappe_assistant_core.chat.api.changes import undo_change
from frappe_assistant_core.tests.base_test import (
    CUSTOM_TEST_DOCTYPE,
    BaseAssistantTest,
    ensure_custom_test_doctype,
)

# Only records of a custom doctype (built in Desk or by chat) are created without a card.
DOCTYPE = CUSTOM_TEST_DOCTYPE


class TestChangesUndo(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        ensure_custom_test_doctype()
        super().setUpClass()

    def setUp(self):
        super().setUp()
        self.owner = self.make_throwaway_user("undo-owner", roles=("System Manager",))
        self.sid = f"undo-{frappe.generate_hash(length=8)}"
        self.message_id = f"msg-{frappe.generate_hash(length=8)}"
        # The order a real turn writes: the user's message, then the record the chat creates
        # while it runs; the assistant row is a shell made at stream_start, before the tools
        # run, and the relay calls add_changes_made on it when AR sends changes_made.
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

    def _insert_style(self, name=None):
        return (
            frappe.get_doc({"doctype": DOCTYPE, "title": "Site visit"})
            .insert(ignore_permissions=True, set_name=name)
            .name
        )

    @staticmethod
    def _change(name, doctype=DOCTYPE):
        return {
            "doctype": doctype,
            "name": name,
            "action": "create",
            "undo": "delete",
        }

    def _link_to_created(self):
        # The user later linked a Contact to the record in Desk (Contact > Links).
        return (
            frappe.get_doc(
                {
                    "doctype": "Contact",
                    "first_name": f"undo-{frappe.generate_hash(length=6)}",
                    "links": [{"link_doctype": DOCTYPE, "link_name": self.created}],
                }
            )
            .insert(ignore_permissions=True)
            .name
        )

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
        # Frappe's on_trash hook would delete a Contact linked only to this record.
        contact = self._link_to_created()
        frappe.set_user(self.owner)
        result = self._undo()
        self.assertEqual(result, {"success": False, "reason": "Something now links to it"})
        self.assertTrue(frappe.db.exists(DOCTYPE, self.created))
        self.assertTrue(frappe.db.exists("Contact", contact))
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

    def _listed_role(self):
        # A record whose doctype has a Python controller, listed on the message like a chat create.
        role = frappe.get_doc({"doctype": "Role", "role_name": f"undo-{frappe.generate_hash(length=8)}"})
        frappe.set_user(self.owner)
        role = role.insert(ignore_permissions=True).name
        frappe.set_user("Administrator")
        add_changes_made(self.message, [self._change(role, "Role")])
        return role

    def test_undo_never_runs_an_on_trash_that_cascades(self):
        from frappe.contacts.address_and_contact import delete_contact_and_address

        role = self._listed_role()
        contact = frappe.get_doc(
            {
                "doctype": "Contact",
                "first_name": f"undo-{frappe.generate_hash(length=6)}",
                "links": [{"link_doctype": "Role", "link_name": role}],
            }
        ).insert(ignore_permissions=True)

        def cascade(doc, *args, **kwargs):
            # As Customer, Supplier and Lead do: delete the Contacts linked only to this record,
            # which clears the link delete_doc checks afterwards.
            delete_contact_and_address(doc.doctype, doc.name)

        frappe.set_user(self.owner)
        with patch("frappe.core.doctype.role.role.Role.on_trash", cascade, create=True):
            result = self._undo(name=role, doctype="Role")
        self.assertEqual(result, {"success": False, "reason": "Something now links to it"})
        self.assertTrue(frappe.db.exists("Role", role))
        self.assertTrue(frappe.db.exists("Contact", contact.name))

    def test_linked_record_rolls_back_what_on_trash_did(self):
        # A link the pre-check missed (made by a concurrent request between the check and the
        # delete) refuses delete_doc after on_trash already ran.
        role = self._listed_role()
        frappe.get_doc(
            {"doctype": "Custom DocPerm", "parent": "Note", "role": role, "permlevel": 0, "read": 1}
        ).insert(ignore_permissions=True)
        marker = f"marker-{frappe.generate_hash(length=6)}"

        def on_trash_side_effect(doc, *args, **kwargs):
            # Stands in for an app whose on_trash removes related rows (Customer deletes its Contacts).
            frappe.db.set_value("FAC Chat Message", self.message, "content", marker)

        frappe.set_user(self.owner)
        with (
            patch.object(changes, "_is_linked", return_value=False),
            patch("frappe.core.doctype.role.role.Role.on_trash", on_trash_side_effect, create=True),
        ):
            result = self._undo(name=role, doctype="Role")
        self.assertFalse(result["success"])
        self.assertTrue(frappe.db.exists("Role", role))
        self.assertNotEqual(frappe.db.get_value("FAC Chat Message", self.message, "content"), marker)

    def test_undo_refuses_a_record_recreated_by_someone_else(self):
        # The user deleted the record by hand, then another user made one of the same name.
        frappe.delete_doc(DOCTYPE, self.created, force=True)
        other = self.make_throwaway_user("undo-other", roles=("System Manager",))
        frappe.set_user(other)
        self._insert_style(name=self.created)
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

    def _drop_turn_rows(self, conversation=False):
        # Retention off or pruned history: the user rows (and the conversation row) are gone.
        frappe.db.delete("FAC Chat Message", {"session_id": self.sid, "role": "user"})
        if conversation:
            frappe.db.delete("FAC Chat Conversation", {"name": self.sid})

    def test_without_a_turn_row_a_record_made_before_the_session_is_refused(self):
        earlier = self._make_style(self.owner)
        sid = f"undo-late-{frappe.generate_hash(length=8)}"
        message = self._make_message(self.owner, sid, "late")
        add_changes_made(message, [self._change(earlier)])
        frappe.set_user(self.owner)
        result = self._undo(name=earlier, session_id=sid, message_id="late")
        self.assertEqual(
            result, {"success": False, "reason": "This record has changed since the chat created it"}
        )
        self.assertTrue(frappe.db.exists(DOCTYPE, earlier))

    def test_without_a_turn_row_a_record_made_after_the_session_started_is_undone(self):
        self._drop_turn_rows()
        frappe.set_user(self.owner)
        self.assertEqual(self._undo(), {"success": True})
        self.assertFalse(frappe.db.exists(DOCTYPE, self.created))

    def test_with_no_turn_row_and_no_conversation_undo_is_refused(self):
        self._drop_turn_rows(conversation=True)
        frappe.set_user(self.owner)
        result = self._undo()
        self.assertEqual(
            result, {"success": False, "reason": "This record has changed since the chat created it"}
        )
        self.assertTrue(frappe.db.exists(DOCTYPE, self.created))
