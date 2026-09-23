# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""The model survives the round trip: out on a resume, back on the socket.

Outbound, a HITL resume has to carry the model the turn was sent with. The
resume path skips auto-mode classification, so a resume that forwards nothing
lets AR pick its own default and the approved turn can finish on a different
model than it started on. Only an explicit user choice travels — auto mode
sends nothing, because "auto" is a mode, not a model.

Inbound, AR names the model twice (``stream_start.model_id`` and
``stream_complete.model``) and the relay dropped both, so ``meta.model_id`` in
``chatStore.completeStreaming`` always read undefined and the model chip never
rendered. Both loops relay it, under the key the SPA reads: ``model_id``.
"""

import inspect
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from frappe_assistant_core.chat.api.chat import messages, relay
from frappe_assistant_core.chat.api.chat.relay import _relay_ar_interrupt_resume

MODEL = "claude-opus-4-1"


def _stream_start() -> dict:
    return {"event": "stream_start", "data": {"message_id": "AR-MSG-1", "model_id": MODEL}}


def _stream_complete() -> dict:
    # AR says "model" here and "model_id" on stream_start; the socket says
    # "model_id" on both, because that is the key the SPA reads.
    return {
        "event": "stream_complete",
        "data": {"full_response": "done", "model": MODEL, "credits_used": 3},
    }


def _run_relay(target, events, **kwargs):
    """Drive one relay loop over a canned AR event list.

    Everything outside the event loop — Frappe context, persistence, quota —
    is stubbed. Returns the AR client (to inspect the outbound call) and the
    socket payloads the loop emitted.
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
        for name in ("init", "connect", "set_user", "destroy"):
            enter(patch(f"frappe.{name}"))
        # The resume loop looks up the interrupted turn's existing row.
        enter(patch("frappe.db.get_value", return_value=None))
        enter(patch.object(relay, "clear_cancel"))
        enter(patch.object(relay, "is_cancelled", return_value=False))
        enter(patch.object(relay, "_ensure_assistant_msg", return_value="MSG-1"))
        enter(patch.object(relay, "_find_assistant_msg_by_message_id", return_value=None))
        enter(patch.object(relay, "_log_conversation"))
        enter(patch.object(relay, "_persist_resume_cycle", return_value="MSG-1"))
        enter(patch.object(relay, "_persist_session_blob"))
        enter(patch.object(relay, "_update_subscription_cache"))
        enter(
            patch(
                "frappe_assistant_core.chat.quota_cache.get_quota_snapshot",
                return_value={"quota_used": 0, "quota_total": 100},
            )
        )
        enter(
            patch.object(
                relay, "_emit_socket_event", side_effect=lambda _sid, payload: emitted.append(payload)
            )
        )
        target(**kwargs)

    return client, emitted


def _run_send(events, **extra):
    return _run_relay(
        relay._relay_ar_stream,
        events,
        session_id="s1",
        full_prompt="hi",
        original_message="hi",
        context=None,
        message_name=None,
        user="u@x.com",
        site="site",
        **extra,
    )


def _run_resume(events, **extra):
    return _run_relay(
        relay._relay_ar_interrupt_resume,
        events,
        session_id="s1",
        interrupt_response=[{"interruptId": "i1", "response": "approve"}],
        user="u@x.com",
        site="site",
        message_id="m1",
        **extra,
    )


def _last(emitted, event_name):
    """The final payload of that event type.

    The send loop emits a bare stream_start of its own before AR answers —
    the model can only be on the one AR sourced, which comes after.
    """
    matches = [p for p in emitted if p.get("event") == event_name]
    if not matches:
        raise AssertionError(f"no {event_name} emitted; got {[p.get('event') for p in emitted]}")
    return matches[-1]


class TestModelReachesTheResumeRelay(unittest.TestCase):
    def _bind(self, submit):
        call_args, call_kwargs = submit.call_args[0], submit.call_args[1]
        return inspect.signature(_relay_ar_interrupt_resume).bind(*call_args[1:], **call_kwargs)

    def _resume(self, **kwargs):
        # can_use_faco is patched — the house pattern for these endpoints — so
        # the test doesn't depend on this site's real FAC Cloud registration.
        with patch.object(messages._relay_pool, "submit") as submit, patch(
            "frappe_assistant_core.chat.api.settings.can_use_faco",
            return_value={"can_use": True},
        ), patch.object(messages, "_is_processing_restricted", return_value=False):
            messages.resume_interrupt(
                session_id="s1",
                interrupt_response='[{"interruptId": "i1", "response": "approve"}]',
                **kwargs,
            )
        return self._bind(submit)

    def test_an_explicit_choice_reaches_the_relay(self):
        bound = self._resume(model_id=MODEL)
        self.assertEqual(bound.arguments.get("model_id"), MODEL)

    def test_auto_mode_reaches_the_relay_as_absence(self):
        """The SPA omits the key entirely in auto mode rather than sending
        "auto": the resume path never classifies, so "auto" would reach AR as
        the literal name of a model that does not exist.
        """
        bound = self._resume()
        self.assertIsNone(bound.arguments.get("model_id"))

    def test_the_resume_relay_hands_the_model_to_the_sdk(self):
        """The last hop counts too, not just reaching the thread."""
        client, _ = _run_resume([], model_id=MODEL)
        self.assertEqual(client.stream_chat.call_args.kwargs["model_id"], MODEL)

    def test_absence_stays_absence_on_the_sdk_hop(self):
        # The SDK omits the wire key on a falsy model_id, so None here is
        # exactly the absence AR needs to fall back to its own selection.
        client, _ = _run_resume([])
        self.assertIsNone(client.stream_chat.call_args.kwargs.get("model_id"))


class TestStreamStartCarriesTheModel(unittest.TestCase):
    def test_send_loop_relays_it(self):
        _, emitted = _run_send([_stream_start()])
        self.assertEqual(_last(emitted, "stream_start").get("model_id"), MODEL)

    def test_resume_loop_relays_it(self):
        _, emitted = _run_resume([_stream_start()])
        self.assertEqual(_last(emitted, "stream_start").get("model_id"), MODEL)


class TestStreamCompleteCarriesTheModel(unittest.TestCase):
    def test_send_loop_relays_it(self):
        _, emitted = _run_send([_stream_start(), _stream_complete()])
        self.assertEqual(_last(emitted, "stream_complete").get("model_id"), MODEL)

    def test_resume_loop_relays_it(self):
        _, emitted = _run_resume([_stream_start(), _stream_complete()])
        self.assertEqual(_last(emitted, "stream_complete").get("model_id"), MODEL)


if __name__ == "__main__":
    unittest.main()
