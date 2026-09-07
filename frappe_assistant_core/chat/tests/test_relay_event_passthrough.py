import unittest
from unittest.mock import MagicMock, patch


class TestDispatchRelayEvent(unittest.TestCase):
    """The main and resume relay loops both funnel session-scoped,
    stateless events (context_summarized, model_selected, thinking,
    thinking_complete) through ``_dispatch_relay_event``. This is the
    seam that keeps the two loops from drifting apart — the bug this
    task fixes was exactly that drift: the resume loop never grew a
    thinking branch when the main loop did.
    """

    def test_context_summarized_is_forwarded_verbatim(self):
        from frappe_assistant_core.chat.api.chat import relay

        block_builder = MagicMock()
        with patch.object(relay, "_emit_socket_event") as emit:
            handled = relay._dispatch_relay_event(
                "context_summarized",
                {"message": "Older messages were summarized to stay within context limits"},
                "SESSION-1",
                block_builder,
            )

        self.assertTrue(handled)
        emit.assert_called_once()
        session_arg, payload = emit.call_args[0]
        self.assertEqual(session_arg, "SESSION-1")
        self.assertEqual(payload["event"], "context_summarized")
        self.assertEqual(payload["message"], "Older messages were summarized to stay within context limits")

    def test_model_selected_is_forwarded_verbatim(self):
        from frappe_assistant_core.chat.api.chat import relay

        block_builder = MagicMock()
        data = {
            "mode": "auto",
            "complexity": "moderate",
            "task_type": "coding",
            "selected": "claude-sonnet-4-6",
            "tier": "Standard",
            "shortlist_size": 3,
        }
        with patch.object(relay, "_emit_socket_event") as emit:
            handled = relay._dispatch_relay_event("model_selected", data, "SESSION-1", block_builder)

        self.assertTrue(handled)
        emit.assert_called_once()
        session_arg, payload = emit.call_args[0]
        self.assertEqual(session_arg, "SESSION-1")
        self.assertEqual(payload["event"], "model_selected")
        self.assertEqual(payload["selected"], "claude-sonnet-4-6")
        self.assertEqual(payload["tier"], "Standard")
        self.assertEqual(payload["shortlist_size"], 3)

    def test_thinking_updates_block_builder_and_emits(self):
        from frappe_assistant_core.chat.api.chat import relay

        block_builder = MagicMock()
        with patch.object(relay, "_emit_socket_event") as emit:
            handled = relay._dispatch_relay_event(
                "thinking", {"content": "considering options"}, "SESSION-1", block_builder
            )

        self.assertTrue(handled)
        block_builder.add_thinking.assert_called_once_with("considering options")
        session_arg, payload = emit.call_args[0]
        self.assertEqual(payload["event"], "thinking")
        self.assertEqual(payload["content"], "considering options")

    def test_thinking_complete_updates_block_builder_and_emits(self):
        from frappe_assistant_core.chat.api.chat import relay

        block_builder = MagicMock()
        with patch.object(relay, "_emit_socket_event") as emit:
            handled = relay._dispatch_relay_event("thinking_complete", {}, "SESSION-1", block_builder)

        self.assertTrue(handled)
        block_builder.complete_thinking.assert_called_once_with()
        session_arg, payload = emit.call_args[0]
        self.assertEqual(payload["event"], "thinking_complete")

    def test_unhandled_event_type_returns_false_without_emitting(self):
        from frappe_assistant_core.chat.api.chat import relay

        block_builder = MagicMock()
        with patch.object(relay, "_emit_socket_event") as emit:
            handled = relay._dispatch_relay_event("tool_call_start", {}, "SESSION-1", block_builder)

        self.assertFalse(handled)
        emit.assert_not_called()


class TestMainLoopUsesSharedDispatch(unittest.TestCase):
    """Regression guard: both loops must route through the same helper
    for the shared event types, so a future addition to one lands in
    both automatically instead of silently drifting again.
    """

    def test_main_loop_source_calls_shared_dispatch(self):
        import inspect

        from frappe_assistant_core.chat.api.chat import relay

        source = inspect.getsource(relay._relay_ar_stream)
        self.assertIn("_dispatch_relay_event(", source)

    def test_resume_loop_source_calls_shared_dispatch(self):
        import inspect

        from frappe_assistant_core.chat.api.chat import relay

        source = inspect.getsource(relay._relay_ar_interrupt_resume)
        self.assertIn("_dispatch_relay_event(", source)


if __name__ == "__main__":
    unittest.main()
