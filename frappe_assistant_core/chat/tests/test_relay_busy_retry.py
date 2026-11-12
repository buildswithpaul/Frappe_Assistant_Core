# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""AR answers 503 when it is busy; FAC re-opens the stream instead of failing the turn.

SDK 1.14.0 turns that 503 into a lone ``stream_error`` coded ``AR_BUSY`` with the
``Retry-After`` seconds. The helper retries up to ``MAX_BUSY_RETRIES`` times, tells the
client it is waiting, and gives up with one friendly error. Stand-ins below are plain
generators: ``sleep`` is injected, and ``_emit_socket_event`` is the only patched boundary.
"""

import unittest
from contextlib import ExitStack
from unittest.mock import create_autospec, patch

import frappe
from assistant_runtime_sdk import AssistantRuntimeClient
from frappe import _

from frappe_assistant_core.chat.api.chat import busy_retry, relay
from frappe_assistant_core.chat.api.chat.busy_retry import MAX_BUSY_RETRIES, stream_with_busy_retry
from frappe_assistant_core.tests.base_test import BaseAssistantTest

SESSION = "s-busy"
EMIT = "frappe_assistant_core.chat.api.chat.busy_retry._emit_socket_event"


def _busy(retry_after: float = 5.0) -> dict:
    """SDK 1.14.0 yields exactly this (and nothing else) when AR answers 503."""
    return {
        "event": "stream_error",
        "data": {
            "error": "The assistant is busy right now. Retrying shortly.",
            "error_code": "AR_BUSY",
            "retryable": True,
            "retry_after": retry_after,
        },
    }


def _stream(*events):
    yield from events


class _Opener:
    """open_stream stand-in: each call returns the next scripted stream."""

    def __init__(self, *streams):
        self.streams = list(streams)
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return _stream(*self.streams.pop(0))


class TestBusyRetry(unittest.TestCase):
    def run_helper(self, opener, cancelled=lambda: False):
        sleeps = []
        with patch(EMIT) as emit:
            events = list(stream_with_busy_retry(opener, SESSION, cancelled=cancelled, sleep=sleeps.append))
        return events, emit, sleeps

    def test_busy_then_ok_retries_and_streams(self):
        ok = [{"event": "stream_start", "data": {}}, {"event": "stream_complete", "data": {}}]
        opener = _Opener([_busy(5.0)], ok)

        events, emit, sleeps = self.run_helper(opener)

        self.assertEqual(events, ok)
        self.assertEqual(opener.calls, 2)
        emit.assert_called_once_with(
            SESSION,
            {
                "event": "stream_status",
                "session_id": SESSION,
                "status": "busy_retrying",
                "attempt": 1,
                "retry_after": 5.0,
            },
        )
        self.assertAlmostEqual(sum(sleeps), 5.0)
        self.assertTrue(all(s <= 0.5 for s in sleeps))

    def test_three_refusals_then_gives_up_with_busy_message(self):
        opener = _Opener(*[[_busy(1.0)] for _i in range(MAX_BUSY_RETRIES + 1)])

        events, emit, _sleeps = self.run_helper(opener)

        self.assertEqual(opener.calls, 4)
        self.assertEqual(emit.call_count, MAX_BUSY_RETRIES)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "stream_error")
        self.assertEqual(events[0]["data"]["error_code"], "AR_BUSY")
        self.assertEqual(events[0]["data"]["error"], _("FAC Cloud is busy. Try again in a minute."))

    def test_stop_during_wait_ends_without_reopening(self):
        opener = _Opener([_busy(5.0)], [{"event": "stream_complete", "data": {}}])
        polls = iter([False, True])

        events, _emit, _sleeps = self.run_helper(opener, cancelled=lambda: next(polls, True))

        self.assertEqual(opener.calls, 1)
        self.assertNotIn("stream_complete", [e["event"] for e in events])

    def test_busy_retry_spends_no_credits(self):
        usage = {"event": "stream_complete", "data": {"credits_used": 3}}
        opener = _Opener([_busy(0.5)], [usage])

        events, _emit, _sleeps = self.run_helper(opener)

        # The refused attempt yields nothing: no usage event reaches the relay before success.
        self.assertEqual(events, [usage])

    def test_wait_is_capped(self):
        opener = _Opener([_busy(500.0)], [{"event": "stream_complete", "data": {}}])

        _events, emit, sleeps = self.run_helper(opener)

        self.assertAlmostEqual(sum(sleeps), busy_retry.MAX_WAIT_SECONDS)
        self.assertEqual(emit.call_args.args[1]["retry_after"], busy_retry.MAX_WAIT_SECONDS)

    def test_nan_retry_after_is_treated_as_invalid(self):
        opener = _Opener([_busy(float("nan"))], [{"event": "stream_complete", "data": {}}])

        _events, emit, sleeps = self.run_helper(opener)

        self.assertAlmostEqual(sum(sleeps), 1.0)
        self.assertEqual(emit.call_args.args[1]["retry_after"], 1.0)

    def test_other_first_event_passes_through_without_retry(self):
        evs = [{"event": "stream_error", "data": {"error_code": "RATE_LIMITED"}}]
        opener = _Opener(evs)

        events, emit, _sleeps = self.run_helper(opener)

        self.assertEqual(events, evs)
        self.assertEqual(opener.calls, 1)
        emit.assert_not_called()


class TestRelayUsesBusyRetry(unittest.TestCase):
    def _run_send(self, streams, cancelled=None):
        # Autospec of the real SDK client: a renamed or missing stream_chat fails here,
        # which a bare MagicMock would let through.
        client = create_autospec(AssistantRuntimeClient, instance=True)
        client.stream_chat.side_effect = lambda *a, **k: _stream(*streams.pop(0))
        emitted = []
        with ExitStack() as stack:
            enter = stack.enter_context
            enter(
                patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client)
            )
            for name in ("init", "connect", "set_user", "destroy", "log_error"):
                enter(patch(f"frappe.{name}"))
            enter(patch("frappe.db.get_value", return_value=None))
            enter(patch("frappe.db.commit"))
            enter(patch.object(relay, "is_cancelled", side_effect=cancelled or (lambda _sid: False)))
            enter(patch.object(relay, "_ensure_assistant_msg"))
            enter(patch.object(relay, "_persist_session_blob"))
            self.persist_partial = enter(patch.object(relay, "_persist_partial_assistant_turn"))
            enter(patch.object(busy_retry.time, "sleep"))
            enter(patch.object(relay, "_emit_socket_event", side_effect=lambda _s, p: emitted.append(p)))
            enter(patch.object(busy_retry, "_emit_socket_event", side_effect=lambda _s, p: emitted.append(p)))
            relay._relay_ar_stream(
                session_id="s1",
                full_prompt="hi",
                original_message="hi",
                context=None,
                message_name=None,
                user="member@example.com",
                site="site",
            )
        return client, emitted

    def test_send_funnel_reopens_the_stream_when_busy(self):
        streams = [[_busy(0.5)], [{"event": "stream_error", "data": {"error": "boom"}}]]

        client, emitted = self._run_send(streams)

        self.assertEqual(client.stream_chat.call_count, 2)
        statuses = [p for p in emitted if p["event"] == "stream_status"]
        self.assertEqual([p["status"] for p in statuses], ["busy_retrying"])

    def test_send_funnel_ends_with_the_busy_error_after_the_last_refusal(self):
        streams = [[_busy(0.5)] for _i in range(MAX_BUSY_RETRIES + 1)]

        client, emitted = self._run_send(streams)

        self.assertEqual(client.stream_chat.call_count, MAX_BUSY_RETRIES + 1)
        errors = [p for p in emitted if p["event"] == "stream_error"]
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["error_code"], "AR_BUSY")
        self.assertEqual(errors[0]["error"], _("FAC Cloud is busy. Try again in a minute."))

    def test_the_last_busy_refusal_records_an_empty_errored_answer(self):
        streams = [[_busy(0.5)] for _i in range(MAX_BUSY_RETRIES + 1)]

        self._run_send(streams)

        # AR never named the turn, so the latest row belongs to an earlier turn: a new one is made.
        self.persist_partial.assert_called_once_with(
            "s1", None, "", [], [], "", "errored", fall_back_to_latest=False, continued_turn=None
        )

    def test_another_refusal_before_anything_streamed_records_nothing(self):
        streams = [[{"event": "stream_error", "data": {"error": "x", "error_code": "RATE_LIMITED"}}]]

        self._run_send(streams)

        self.persist_partial.assert_not_called()

    def test_stop_during_a_busy_wait_aborts_the_turn_without_reopening(self):
        streams = [[_busy(5.0)], [{"event": "stream_complete", "data": {}}]]
        polls = iter([False, False, True])

        client, emitted = self._run_send(streams, cancelled=lambda _sid: next(polls, True))

        self.assertEqual(client.stream_chat.call_count, 1)
        self.assertEqual(emitted[-1]["event"], "stream_aborted")


class TestBusyRefusalRow(BaseAssistantTest):
    """The row the relay writes after the last busy refusal, against the real table."""

    def setUp(self):
        super().setUp()
        self.user = self.make_throwaway_user("busy-refusal")
        frappe.set_user(self.user)
        self.sid = f"busy-refusal-{frappe.generate_hash(length=8)}"
        # An earlier answered turn, then the user's new message that AR refused.
        self.earlier = self._message("assistant", "An earlier answer")
        self._message("user", "A new question")

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _message(self, role, content):
        return (
            frappe.get_doc(
                {
                    "doctype": "FAC Chat Message",
                    "session_id": self.sid,
                    "user": self.user,
                    "role": role,
                    "content": content,
                }
            )
            .insert(ignore_permissions=True)
            .name
        )

    def test_a_new_empty_errored_answer_follows_the_refused_question(self):
        relay._persist_partial_assistant_turn(
            self.sid, None, "", [], [], None, "errored", fall_back_to_latest=False
        )

        rows = frappe.get_all(
            "FAC Chat Message",
            filters={"session_id": self.sid},
            fields=["name", "role", "content", "errored"],
            order_by="idx asc, creation asc",
        )
        self.assertEqual([r.role for r in rows], ["assistant", "user", "assistant"])
        self.assertEqual((rows[-1].content or "", rows[-1].errored), ("", 1))
        self.assertEqual(frappe.db.get_value("FAC Chat Message", self.earlier, "errored"), 0)


if __name__ == "__main__":
    unittest.main()
