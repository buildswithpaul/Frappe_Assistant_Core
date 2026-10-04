# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""AR's ``rate_limited`` refusal reaches the clients as a ``stream_error``.

AR refuses a turn it cannot route, because no model the plan reaches is
available or the chosen model's provider is at its rate limit, with a lone
``rate_limited`` event instead of ``stream_error``. Neither relay loop had a
branch for it, so FAC dropped it and the SPA and the mobile app waited out
their 180 s activity timeout before showing a generic timeout. Both loops now
finish it as a ``stream_error`` coded ``RATE_LIMITED``, with ``retry_after``
when AR gave one, through the branch that ends AR's other refusals before a
turn starts. Nothing is persisted, because nothing was produced.

Everything outside the event loop is stubbed, so nothing touches the site.
"""

import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from frappe import _

from frappe_assistant_core.chat.api.chat import relay

AR_REASON = "All available models are currently rate limited"
FALLBACK = "The assistant is busy right now. Please try again in a moment."


def _rate_limited(**overrides) -> dict:
    """The event as the SDK yields AR's ``_create_rate_limited_response``."""
    data = {
        "error": AR_REASON,
        "error_code": "RATE_LIMITED",
        "retry_after": 12.5,
        "models_checked": ["model-a", "model-b"],
    }
    data.update(overrides)
    return {"event": "rate_limited", "data": data}


def _run_relay(target, events, **kwargs):
    """Drive one relay loop over canned AR events.

    Returns the socket payloads it emitted and the partial-turn persist mock.
    """
    client = MagicMock()
    client.stream_chat.return_value = iter(events)
    emitted = []

    with ExitStack() as stack:
        enter = stack.enter_context
        enter(
            patch(
                "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client",
                return_value=client,
            )
        )
        # set_user is stubbed deliberately: the real one wipes the running
        # session, which would log the test runner out mid-suite.
        for name in ("init", "connect", "set_user", "destroy", "log_error"):
            enter(patch(f"frappe.{name}"))
        enter(patch("frappe.db.get_value", return_value=None))
        enter(patch("frappe.db.commit"))
        enter(patch.object(relay, "is_cancelled", return_value=False))
        enter(patch.object(relay, "_ensure_assistant_msg"))
        enter(patch.object(relay, "_persist_session_blob"))
        persist_partial = enter(patch.object(relay, "_persist_partial_assistant_turn"))
        enter(
            patch.object(
                relay, "_emit_socket_event", side_effect=lambda _sid, payload: emitted.append(payload)
            )
        )
        target(**kwargs)

    return emitted, persist_partial


def _run_send(events):
    return _run_relay(
        relay._relay_ar_stream,
        events,
        session_id="s1",
        full_prompt="hi",
        original_message="hi",
        context=None,
        message_name=None,
        user="member@example.com",
        site="site",
    )


def _run_resume(events):
    return _run_relay(
        relay._relay_ar_interrupt_resume,
        events,
        session_id="s1",
        interrupt_response=[{"interruptId": "i1", "response": "approve"}],
        user="member@example.com",
        site="site",
        message_id="m1",
    )


def _stream_errors(emitted: list) -> list:
    return [p for p in emitted if p.get("event") == "stream_error"]


class TestNormalizeArEvent(unittest.TestCase):
    def test_rate_limited_becomes_a_rate_limited_stream_error(self):
        event_type, data = relay._normalize_ar_event("rate_limited", _rate_limited()["data"])

        self.assertEqual(event_type, "stream_error")
        self.assertEqual(data, {"error": AR_REASON, "error_code": "RATE_LIMITED", "retry_after": 12.5})

    def test_a_retry_after_that_is_not_a_positive_number_is_dropped(self):
        # AR sends 0 when auto mode is off or the plan reaches no model.
        kept = [
            relay._normalize_ar_event("rate_limited", _rate_limited(retry_after=value)["data"])[1][
                "retry_after"
            ]
            for value in (0, 0.0, -1, None, "soon")
        ]

        self.assertEqual(kept, [None] * 5)

    def test_a_refusal_without_a_reason_gets_the_fallback(self):
        _event_type, data = relay._normalize_ar_event("rate_limited", {})

        self.assertEqual(data, {"error": _(FALLBACK), "error_code": "RATE_LIMITED", "retry_after": None})

    def test_every_other_event_passes_through_untouched(self):
        data = {"content": "hello"}
        event_type, same = relay._normalize_ar_event("stream_chunk", data)

        self.assertEqual(event_type, "stream_chunk")
        self.assertIs(same, data)


class TestBothLoopsEndARateLimitedTurn(unittest.TestCase):
    def _assert_refused(self, emitted, persist_partial):
        errors = _stream_errors(emitted)
        self.assertEqual(
            len(errors), 1, f"expected one stream_error; got {[p.get('event') for p in emitted]}"
        )
        error = errors[0]
        self.assertEqual(error["session_id"], "s1")
        self.assertEqual(error["error"], AR_REASON)
        self.assertEqual(error["error_code"], "RATE_LIMITED")
        self.assertEqual(error["retry_after"], 12.5)
        self.assertNotIn("models_checked", error)
        # Refused before the turn started: no AR message id, nothing produced,
        # so nothing is persisted and nothing completes.
        self.assertIsNone(error["message_id"])
        self.assertEqual(error["blocks"], [])
        self.assertEqual(error["partial_response"], "")
        persist_partial.assert_not_called()
        self.assertNotIn("stream_complete", [p.get("event") for p in emitted])

    def test_the_send_loop_ends_the_turn_with_a_stream_error(self):
        self._assert_refused(*_run_send([_rate_limited()]))

    def test_the_resume_loop_ends_the_turn_with_a_stream_error(self):
        self._assert_refused(*_run_resume([_rate_limited()]))

    def test_other_stream_errors_pass_through_with_no_retry_after(self):
        refusal = {
            "event": "stream_error",
            "data": {"error": "Your team is out of credits.", "error_code": "quota_exhausted"},
        }
        for run in (_run_send, _run_resume):
            with self.subTest(loop=run.__name__):
                emitted, _persist = run([refusal])
                error = _stream_errors(emitted)[-1]

                self.assertEqual(error["error_code"], "quota_exhausted")
                self.assertIsNone(error.get("retry_after"))
