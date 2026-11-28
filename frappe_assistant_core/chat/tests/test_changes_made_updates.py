# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""A record the chat updated in auto-approve mode is listed in the reply and can never be undone:
Undo deletes, and the record existed before the chat."""

from unittest.mock import patch

from frappe_assistant_core.chat.api import block_builder
from frappe_assistant_core.chat.api.block_builder import (
    find_open_change,
    merge_changes_block,
    normalise_changes,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest

# What the runtime reports for an update it ran without a card, and for a create.
UPDATE = {"tool": "update_document", "doctype": "Task", "name": "TASK-1", "action": "update", "undo": None}
CREATE = {
    "tool": "create_document",
    "doctype": "Note",
    "name": "note-1",
    "action": "create",
    "undo": "delete",
}


class TestUpdatesInTheChangesBlock(BaseAssistantTest):
    def test_an_update_is_listed_without_undo(self):
        self.assertEqual(
            normalise_changes([UPDATE, CREATE]),
            [
                {"doctype": "Task", "name": "TASK-1", "action": "update", "undo": None},
                {"doctype": "Note", "name": "note-1", "action": "create", "undo": "delete"},
            ],
        )

    def test_an_update_that_claims_an_undo_is_dropped(self):
        for forged in (
            {**UPDATE, "undo": "delete"},
            {**CREATE, "undo": None},
            {**UPDATE, "action": "delete"},
        ):
            self.assertEqual(normalise_changes([forged]), [], forged)

    def test_undo_never_finds_an_update(self):
        blocks: list[dict] = []
        merge_changes_block(blocks, [UPDATE, CREATE])
        # Production: the relay stores these blocks on the assistant's FAC Chat Message row.
        with patch.object(block_builder, "_read_message_blocks", autospec=True, return_value=blocks):
            self.assertIsNone(find_open_change("MSG-1", "Task", "TASK-1"))
            self.assertEqual(find_open_change("MSG-1", "Note", "note-1")["action"], "create")

    def test_a_record_created_then_updated_in_one_reply_keeps_its_undo(self):
        blocks: list[dict] = []
        merge_changes_block(blocks, [CREATE])
        merge_changes_block(blocks, [{**UPDATE, "doctype": "Note", "name": "note-1"}])

        (change,) = blocks[0]["changes"]
        self.assertEqual((change["action"], change["undo"]), ("create", "delete"))
