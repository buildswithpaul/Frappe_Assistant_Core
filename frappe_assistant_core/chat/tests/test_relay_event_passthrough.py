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


class TestRoutingRelay(unittest.TestCase):
    """Keys are copied by name here, and an unnamed key is dropped in silence —
    so a key AR adds without a matching line below is a no-op that looks like a
    feature. These pin the routing keys to AR's emits."""

    def _dispatch(self, event_type, data):
        from frappe_assistant_core.chat.api.chat import relay

        with patch.object(relay, "_emit_socket_event") as emit:
            handled = relay._dispatch_relay_event(event_type, data, "SESSION-1", MagicMock())
        return handled, emit

    def test_model_selected_forwards_the_routing_decision(self):
        handled, emit = self._dispatch(
            "model_selected",
            {
                "mode": "auto",
                "selected": "m",
                "tier": "Standard",
                "floor_tier": "Premium",
                "ceiling_tier": "Standard",
                "bound_by": "ceiling",
                "band": "conserve",
                "classification_source": "llm",
            },
        )
        self.assertTrue(handled)
        _session, payload = emit.call_args[0]
        self.assertEqual(payload["floor_tier"], "Premium")
        self.assertEqual(payload["ceiling_tier"], "Standard")
        self.assertEqual(payload["bound_by"], "ceiling")
        self.assertEqual(payload["band"], "conserve")
        self.assertEqual(payload["classification_source"], "llm")

    def test_routing_notice_is_relayed(self):
        handled, emit = self._dispatch(
            "routing_notice",
            {
                "code": "downgraded_for_credits",
                "tier_used": "Economy",
                "tier_wanted": "Premium",
                "band": "critical",
                "scope": "tenant",
            },
        )
        self.assertTrue(handled)
        session_arg, payload = emit.call_args[0]
        self.assertEqual(session_arg, "SESSION-1")
        self.assertEqual(payload["event"], "routing_notice")
        self.assertEqual(payload["code"], "downgraded_for_credits")
        self.assertEqual(payload["tier_used"], "Economy")
        self.assertEqual(payload["tier_wanted"], "Premium")
        self.assertEqual(payload["band"], "critical")
        self.assertEqual(payload["scope"], "tenant")

    def test_routing_notice_reaches_the_resume_loop_too(self):
        """The shared set is what keeps the two loops from drifting."""
        from frappe_assistant_core.chat.api.chat import relay

        self.assertIn("routing_notice", relay._SHARED_RELAY_EVENTS)
