import unittest
from unittest.mock import MagicMock, patch


class TestPersistPartialAssistantTurn(unittest.TestCase):
    def test_updates_existing_row_by_message_id_with_errored_flag(self):
        from frappe_assistant_core.chat.api.chat import relay

        with patch.object(relay, "_find_assistant_msg_by_message_id", return_value="MSG-1"), patch.object(
            relay, "_set_faco_message_with_retry"
        ) as setter:
            name = relay._persist_partial_assistant_turn(
                session_id="S1",
                ar_message_id="ar-1",
                partial_response="partial text",
                blocks_snapshot=[{"type": "text", "content": "partial text"}],
                collected_tool_calls=[{"tool": "x"}],
                model_used="claude-sonnet-4-6",
                flag_field="errored",
            )
        self.assertEqual(name, "MSG-1")
        updates = setter.call_args[0][1]
        self.assertEqual(updates["errored"], 1)
        self.assertEqual(updates["content"], "partial text")
        self.assertIn("blocks", updates)
        self.assertEqual(updates["model"], "claude-sonnet-4-6")

    def test_falls_back_to_latest_assistant_row(self):
        from frappe_assistant_core.chat.api.chat import relay

        with patch.object(relay, "_find_assistant_msg_by_message_id", return_value=None), patch(
            "frappe.db.get_value", return_value="MSG-2"
        ), patch.object(relay, "_set_faco_message_with_retry") as setter:
            name = relay._persist_partial_assistant_turn("S1", "ar-1", "txt", [], [], "", "aborted")
        self.assertEqual(name, "MSG-2")
        self.assertEqual(setter.call_args[0][1]["aborted"], 1)
