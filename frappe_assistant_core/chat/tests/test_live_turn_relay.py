"""The relay numbers its events and keeps the live snapshot; the endpoints mark a turn as started."""

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.chat.api.chat import live_turn, messages, relay
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestRelayKeepsTheLiveTurn(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.user = self.make_throwaway_user("live-relay")
        frappe.set_user(self.user)
        self.sid = f"live-relay-{frappe.generate_hash(length=8)}"

    def tearDown(self):
        live_turn.clear(self.sid)
        frappe.set_user("Administrator")
        super().tearDown()

    def _run(self, events, *, restricted=False, publish=None):
        """Drive _relay_ar_stream over ``events`` (a generator may peek at the
        snapshot between events). Returns the payloads that reached publish_realtime."""
        client = MagicMock()
        client.stream_chat.return_value = events
        published = []

        def collect(event, message, **kw):
            # Document inserts publish their own realtime events; only the relay's stream counts.
            if event == "faco_message_stream":
                published.append(dict(message))

        with ExitStack() as stack:
            enter = stack.enter_context
            enter(
                patch(
                    "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client",
                    return_value=client,
                )
            )
            # set_user is stubbed because the real one resets the running session.
            for name in ("init", "connect", "set_user", "destroy"):
                enter(patch(f"frappe.{name}"))
            enter(patch.object(relay, "is_cancelled", return_value=False))
            enter(patch.object(relay, "_update_subscription_cache"))
            enter(
                patch(
                    "frappe_assistant_core.chat.quota_cache.get_quota_snapshot",
                    return_value={"quota_used": 0, "quota_total": 100},
                )
            )
            enter(
                patch(
                    "frappe.publish_realtime",
                    side_effect=publish or collect,
                )
            )
            relay._relay_ar_stream(
                self.sid,
                full_prompt="hi",
                original_message="hi",
                context=None,
                message_name=None,
                user=self.user,
                site=frappe.local.site,
                restricted=restricted,
            )
        return published

    def _turn(self, peeks):
        yield {"event": "stream_start", "data": {"message_id": "m-live"}}
        yield {
            "event": "tool_call_start",
            "data": {"tool_id": "toolu_1", "tool_name": "get_list", "input": {}},
        }
        yield {"event": "stream_chunk", "data": {"content": "Here "}}
        peeks.append(live_turn.get(self.sid))
        yield {"event": "stream_chunk", "data": {"content": "it is."}}
        yield {
            "event": "stream_complete",
            "data": {"full_response": "Here it is.", "message_id": "m-live"},
        }

    def test_every_relay_event_carries_the_turn_and_a_rising_seq(self):
        published = self._run(self._turn([]))
        turns = {p["turn"] for p in published}
        self.assertEqual(len(turns), 1)
        self.assertEqual([p["seq"] for p in published], list(range(1, len(published) + 1)))

    def test_a_joiner_mid_turn_reads_the_tool_and_the_text_so_far(self):
        peeks = []
        self._run(self._turn(peeks))
        mid = peeks[0]
        self.assertEqual(mid["message_id"], "m-live")
        self.assertEqual([b["type"] for b in mid["blocks"]][:1], ["tool_call"])
        self.assertTrue(mid["seq"] >= 2)

    def test_the_entry_is_gone_when_the_turn_ends(self):
        self._run(self._turn([]))
        self.assertIsNone(live_turn.get(self.sid))
        self.assertIsNone(live_turn.current(self.sid))

    def test_the_entry_is_gone_when_the_relay_crashes(self):
        def crash():
            yield {"event": "stream_start", "data": {"message_id": "m-live"}}
            raise RuntimeError("AR went away")

        with patch("frappe.log_error"):
            self._run(crash())
        self.assertIsNone(live_turn.get(self.sid))
        # The crash path clears the stored entry itself; only unbind drops the binding.
        self.assertIsNone(live_turn.current(self.sid))

    def test_a_restricted_user_leaves_no_entry_and_unnumbered_events(self):
        peeks = []
        published = self._run(self._turn(peeks), restricted=True)
        self.assertIsNone(peeks[0])
        self.assertTrue(all("seq" not in p for p in published))

    def test_a_redis_failure_never_stops_the_stream(self):
        # Redis answers the bind, then goes down mid-turn.
        real_write, calls = live_turn._write, []

        def flaky_write(session_id, entry):
            calls.append(1)
            if len(calls) > 1:
                raise ConnectionError("redis down")
            real_write(session_id, entry)

        with patch.object(live_turn, "_write", side_effect=flaky_write):
            published = self._run(self._turn([]))
        self.assertIn("stream_complete", [p["event"] for p in published])
        self.assertGreater(len(calls), 1, "the failure must hit a mid-turn write, not the bind")


class TestEndpointsMarkTheTurnStarted(BaseAssistantTest):
    """send / continue / resume write the starting entry before the relay is queued."""

    def setUp(self):
        super().setUp()
        self.sid = f"live-start-{frappe.generate_hash(length=8)}"
        self.seen_at_submit = []

    def tearDown(self):
        live_turn.clear(self.sid)
        super().tearDown()

    def _patched(self, restricted=False, submit_error=None):
        def submit(*args, **kwargs):
            self.seen_at_submit.append(live_turn.get(self.sid))
            if submit_error:
                raise submit_error

        user_msg = MagicMock()
        user_msg.name = "MSG-1"
        stack = ExitStack()
        self.submit_mock = stack.enter_context(
            patch.object(messages._relay_pool, "submit", side_effect=submit)
        )
        stack.enter_context(
            patch("frappe_assistant_core.chat.api.settings.can_use_faco", return_value={"can_use": True})
        )
        stack.enter_context(
            patch(
                "frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message.FACChatMessage.create_message",
                return_value=user_msg,
            )
        )
        stack.enter_context(patch.object(messages, "_is_processing_restricted", return_value=restricted))
        return stack

    def test_send_marks_the_turn_starting_before_the_relay_is_queued(self):
        with self._patched():
            messages.send_message(session_id=self.sid, message="hello")
        self.assertEqual(self.seen_at_submit[0]["status"], "starting")
        self.assertIsNone(self.seen_at_submit[0]["message_id"])

    def test_continue_and_resume_name_the_turn_they_extend(self):
        with self._patched():
            messages.continue_response(session_id=self.sid, message_id="m1")
        self.assertEqual(self.seen_at_submit[-1]["message_id"], "m1")
        live_turn.clear(self.sid)
        with self._patched():
            messages.resume_interrupt(
                session_id=self.sid,
                interrupt_response='[{"interruptId": "i1", "response": "approve"}]',
                message_id="m2",
            )
        self.assertEqual(self.seen_at_submit[-1]["message_id"], "m2")

    def test_a_restricted_user_gets_no_entry(self):
        with self._patched(restricted=True):
            messages.send_message(session_id=self.sid, message="hello")
        self.assertIsNone(self.seen_at_submit[0])

    def test_a_turn_that_never_queued_leaves_no_entry(self):
        # send_message re-raises a submit failure via frappe.throw.
        with self._patched(submit_error=RuntimeError("pool full")), self.assertRaises(frappe.ValidationError):
            messages.send_message(session_id=self.sid, message="hello")
        self.assertIsNone(live_turn.get(self.sid))

    def test_a_redis_outage_at_send_still_queues_the_relay(self):
        with self._patched():
            with patch.object(live_turn, "start", side_effect=ConnectionError("redis down")):
                messages.send_message(session_id=self.sid, message="hello")
        self.assertEqual(self.submit_mock.call_count, 1)
