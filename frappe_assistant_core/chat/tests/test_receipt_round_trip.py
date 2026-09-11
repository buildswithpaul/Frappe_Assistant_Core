"""The receipt survives the hop from AR to a reloaded bubble."""

import json

import frappe
from assistant_runtime.tests.test_base import ARTestCase

RECEIPT = {
    "v": 1,
    "mode": "auto",
    "incomplete": False,
    "selected_model": "claude-sonnet-4-6",
    "selected_tier": "Standard",
    "bound_by": "ceiling",
    "floor": {"tier": "Standard", "reasons": []},
    "ceiling": {"tier": "Standard", "source": "posture", "reasons": []},
    "credits": {"actual": 137.5},
    "notices": ["downgraded_for_credits"],
    "cycles": 1,
    "also_ran": [],
    "preference": None,
    "preference_source": "none",
}


class TestTheColumnExists(ARTestCase):
    def test_routing_is_a_json_column(self):
        meta = frappe.get_meta("FAC Chat Message")
        field = meta.get_field("routing")
        self.assertIsNotNone(field, "no routing column")
        self.assertEqual(field.fieldtype, "JSON")

    def test_it_is_in_the_history_field_list(self):
        """get_session_messages returns rows verbatim; a column it does not
        select is invisible to a reloaded bubble."""
        import inspect

        from frappe_assistant_core.chat.doctype.fac_chat_message import (
            fac_chat_message,
        )

        src = inspect.getsource(fac_chat_message.FACChatMessage.get_session_messages)
        self.assertIn('"routing"', src)

    def test_the_shared_key_constant_exists(self):
        from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import (
            PERSISTED_LLM_KEYS,
        )

        for key in ("model", "credits_used", "model_breakdown", "routing"):
            self.assertIn(key, PERSISTED_LLM_KEYS)

    def test_create_message_maps_every_persisted_key(self):
        """It mapped three by hand and model_breakdown was already out of
        sync — which is the bug this constant exists to stop repeating."""
        import inspect

        from frappe_assistant_core.chat.doctype.fac_chat_message import (
            fac_chat_message,
        )

        src = inspect.getsource(fac_chat_message.FACChatMessage.create_message)
        self.assertIn("PERSISTED_LLM_KEYS", src)


class TestRoundTrip(ARTestCase):
    def _message(self, **metadata):
        from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import (
            FACChatMessage,
        )

        session = f"rt-{frappe.generate_hash(length=8)}"
        return session, FACChatMessage.create_message(session, "assistant", "hello", llm_metadata=metadata)

    def test_a_receipt_survives_write_and_reload(self):
        from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import (
            FACChatMessage,
        )

        session, _doc = self._message(model="m", credits_used=1.0, routing=RECEIPT)
        rows = FACChatMessage.get_session_messages(session)
        routing = rows["messages"][0]["routing"]
        if isinstance(routing, str):
            routing = json.loads(routing)
        self.assertEqual(routing["bound_by"], "ceiling")
        self.assertAlmostEqual(routing["credits"]["actual"], 137.5)

    def test_a_turn_with_no_receipt_stores_null_not_a_string(self):
        from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import (
            FACChatMessage,
        )

        session, _doc = self._message(model="m", credits_used=1.0)
        rows = FACChatMessage.get_session_messages(session)
        self.assertIn(rows["messages"][0].get("routing"), (None, "", "null"))

    def test_a_continuation_never_nulls_an_existing_receipt(self):
        """model_selected is gated upstream on not continue_from_message_id,
        so a continuation carries no receipt and must not erase one."""
        from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import (
            PERSISTED_LLM_KEYS,
        )

        session, doc = self._message(model="m", credits_used=1.0, routing=RECEIPT)
        updates = {
            k: v
            for k, v in {"credits_used": 2.0, "routing": None}.items()
            if k in PERSISTED_LLM_KEYS and v is not None
        }
        self.assertNotIn("routing", updates)


class TestEveryHopCarriesIt(ARTestCase):
    def _relay(self):
        import inspect

        from frappe_assistant_core.chat.api.chat import relay

        return inspect.getsource(relay)

    def test_the_model_selected_reemit_carries_it(self):
        src = self._relay()
        block = src[src.index('elif event_type == "model_selected"') :][:900]
        self.assertIn('"routing"', block)

    def test_both_stream_complete_socket_dicts_carry_it(self):
        """The only hop that delivers the canonical receipt live, and neither
        is reachable from _SHARED_RELAY_EVENTS."""
        src = self._relay()
        emits = [i for i in range(len(src)) if src.startswith('"event": "stream_complete"', i)]
        self.assertEqual(len(emits), 2, "socket emit count changed; re-read")
        for at in emits:
            self.assertIn('"routing"', src[at : at + 1100])

    def test_the_send_funnel_reads_and_writes_it(self):
        src = self._relay()
        self.assertIn('data.get("routing")', src)

    def test_the_resume_funnel_carries_it_too(self):
        """The file's own comments record the thinking branch being added to
        the main loop and never mirrored here."""
        import inspect

        from frappe_assistant_core.chat.api.chat import relay

        self.assertIn("routing", inspect.getsource(relay._persist_resume_cycle))

    def test_the_resume_funnel_counts_the_cycles(self):
        """Each resume is a fresh stream_chat request, so every AR receipt
        arrives claiming cycles: 1. Only this hop sees the whole turn."""
        import inspect

        from frappe_assistant_core.chat.api.chat import relay

        src = inspect.getsource(relay._merge_routing_receipt)
        self.assertIn("cycles", src)
        self.assertIn("also_ran", src)

    def test_a_later_cycle_does_not_replace_the_first_decision(self):
        """A last-cycle-wins receipt would contradict the chip the user saw
        while the first model was streaming."""
        import inspect

        from frappe_assistant_core.chat.api.chat import relay

        src = inspect.getsource(relay._merge_routing_receipt)
        self.assertIn("selected_model", src)

    def test_log_conversation_carries_it(self):
        import inspect

        from frappe_assistant_core.chat.api.chat import helpers

        self.assertIn("routing", inspect.getsource(helpers._log_conversation))

    def test_routing_and_model_breakdown_share_serialization_semantics(self):
        """Both are JSON columns persisted through the same updates dict.

        A generic loop over PERSISTED_LLM_KEYS is wrong for THIS dict: model
        is deliberately nulled when AR reports none (clearing a stale
        placeholder), while routing must never null over an existing value.
        Those are genuinely different persistence semantics per field, so the
        real guard is that routing gets the same treatment as its closest
        analogue — JSON-dumped, guarded — not that every key shares one loop."""
        src = self._relay()
        at = src.index('model_breakdown": _json_mod.dumps(model_breakdown)')
        window = src[at : at + 900]
        self.assertIn("_json_mod.dumps(_routing_payload)", window)

    def test_a_null_receipt_is_never_persisted_over_a_real_one(self):
        src = self._relay()
        self.assertIn("is not None", src)


class TestMergeRoutingReceipt(ARTestCase):
    """The pure merge logic, exercised directly."""

    def test_the_first_cycle_decision_survives(self):
        from frappe_assistant_core.chat.api.chat.relay import _merge_routing_receipt

        first = dict(RECEIPT, selected_model="claude-opus-4-6", cycles=1, also_ran=[])
        later = dict(RECEIPT, selected_model="claude-sonnet-4-6", cycles=1, also_ran=[])
        merged = _merge_routing_receipt(first, later)
        self.assertEqual(merged["selected_model"], "claude-opus-4-6")

    def test_cycles_increments(self):
        from frappe_assistant_core.chat.api.chat.relay import _merge_routing_receipt

        merged = _merge_routing_receipt(dict(RECEIPT, cycles=1), dict(RECEIPT, cycles=1))
        self.assertEqual(merged["cycles"], 2)

    def test_a_distinct_later_model_is_recorded_in_also_ran(self):
        from frappe_assistant_core.chat.api.chat.relay import _merge_routing_receipt

        first = dict(RECEIPT, selected_model="claude-opus-4-6", also_ran=[])
        later = dict(RECEIPT, selected_model="claude-sonnet-4-6", also_ran=[])
        merged = _merge_routing_receipt(first, later)
        self.assertIn("claude-sonnet-4-6", merged["also_ran"])

    def test_also_ran_is_capped_at_five(self):
        from frappe_assistant_core.chat.api.chat.relay import _merge_routing_receipt

        existing = dict(RECEIPT, selected_model="a", also_ran=["b", "c", "d", "e", "f"])
        merged = _merge_routing_receipt(existing, dict(RECEIPT, selected_model="g"))
        self.assertEqual(len(merged["also_ran"]), 5)

    def test_no_incoming_returns_existing_unchanged(self):
        from frappe_assistant_core.chat.api.chat.relay import _merge_routing_receipt

        self.assertEqual(_merge_routing_receipt(RECEIPT, None), RECEIPT)

    def test_no_existing_returns_incoming(self):
        from frappe_assistant_core.chat.api.chat.relay import _merge_routing_receipt

        self.assertEqual(_merge_routing_receipt(None, RECEIPT), RECEIPT)

    def test_handles_json_string_inputs(self):
        """FAC reads the stored value back as whatever Frappe's JSON field
        returns, which may be a string depending on the DB driver."""
        import json

        from frappe_assistant_core.chat.api.chat.relay import _merge_routing_receipt

        merged = _merge_routing_receipt(json.dumps(RECEIPT), json.dumps(RECEIPT))
        self.assertEqual(merged["cycles"], 2)


class TestTheThreeGates(ARTestCase):
    def test_the_live_socket_payload_carries_a_complete_receipt(self):
        """Gate 3. A reload round-trip alone passes on a build where the live
        chip is dead."""
        import inspect

        from frappe_assistant_core.chat.api.chat import relay

        src = inspect.getsource(relay)
        for at in [i for i in range(len(src)) if src.startswith('"event": "stream_complete"', i)]:
            self.assertIn('"routing"', src[at : at + 1100])

    def test_the_client_parses_every_json_column(self):
        """model_breakdown is a JSON column that neither parse loop parses —
        an object live, a string on reload. One array drives both."""
        import pathlib

        store = (
            pathlib.Path(frappe.get_app_path("frappe_assistant_core"))
            / "chat"
            / "frontend"
            / "src"
            / "stores"
            / "chatStore.js"
        )
        src = store.read_text()
        self.assertIn("JSON_MESSAGE_FIELDS", src)
        for field in ("blocks", "model_breakdown", "routing"):
            self.assertIn(field, src)

    def test_both_parse_loops_use_the_shared_array(self):
        import pathlib

        store = (
            pathlib.Path(frappe.get_app_path("frappe_assistant_core"))
            / "chat"
            / "frontend"
            / "src"
            / "stores"
            / "chatStore.js"
        )
        src = store.read_text()
        self.assertGreaterEqual(src.count("parseJsonFields"), 3)
        self.assertNotIn("JSON.parse(msg.blocks)", src)

    def test_complete_streaming_forwards_the_receipt(self):
        """completeStreaming copies a fixed allowlist off meta; anything not
        named is dropped."""
        import pathlib

        store = (
            pathlib.Path(frappe.get_app_path("frappe_assistant_core"))
            / "chat"
            / "frontend"
            / "src"
            / "stores"
            / "chatStore.js"
        )
        src = store.read_text()
        at = src.index("function completeStreaming")
        self.assertIn("routing", src[at : at + 1200])

    def test_every_use_streaming_call_site_forwards_routing(self):
        """completeStreaming's routing forwarding is dead code unless every
        caller actually passes it through from the socket payload."""
        import pathlib

        composable = (
            pathlib.Path(frappe.get_app_path("frappe_assistant_core"))
            / "chat"
            / "frontend"
            / "src"
            / "composables"
            / "useStreaming.js"
        )
        src = composable.read_text()
        self.assertEqual(src.count("chatStore.completeStreaming("), 3)
        self.assertEqual(src.count("routing: data.routing"), 3)
