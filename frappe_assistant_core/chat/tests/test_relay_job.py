"""A turn's relay runs inside an RQ job: the job's Frappe context, the asker's identity."""

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.chat.api.auth import _ar_user_id
from frappe_assistant_core.chat.api.chat import cancel, live_turn, relay, relay_dispatch, relay_job
from frappe_assistant_core.tests.base_test import BaseAssistantTest


def _event(name, **data):
    return {"event": name, "data": data}


STREAM = [
    _event("stream_start", message_id="m1"),
    _event("stream_chunk", content="Hi"),
    _event("stream_complete", full_response="Hi", message_id="m1"),
]
RESUME_STREAM = [
    _event("stream_start", message_id="m1"),
    _event("stream_complete", full_response="Done", message_id="m1"),
]
ASKER = "relay-job-asker@example.com"


class TestRelayJob(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.sid = f"job-{frappe.generate_hash(length=8)}"
        self.asker = ASKER

    def tearDown(self):
        cancel.clear(self.sid)
        live_turn.clear(self.sid)
        super().tearDown()

    def _capture_enqueue(self, relay_name, site, user, interrupt_response):
        """Enqueue through the real enqueue_relay; frappe.enqueue only records what RQ would run."""
        turn = live_turn.start(self.sid)
        common = {"user": user, "site": site, "live_turn_token": turn}
        if relay_name == "resume":
            fn = relay._relay_ar_interrupt_resume
            args, kwargs = (self.sid, interrupt_response), {**common, "message_id": "m1"}
        else:
            fn = relay._relay_ar_stream
            args = (self.sid,)
            kwargs = {
                **common,
                "full_prompt": "hi",
                "original_message": "hi",
                "context": None,
                "message_name": None,
            }
        with patch.object(relay_dispatch.frappe, "enqueue") as enqueue:
            relay_dispatch.enqueue_relay(fn, args, kwargs, job_id=relay_dispatch.relay_job_id(turn))
        return enqueue.call_args.kwargs

    def _run_job(self, events, *, relay_name="stream", user=None, site=None, interrupt_response=None):
        job_kwargs = self._capture_enqueue(
            relay_name, site or frappe.local.site, user or self.asker, interrupt_response
        )
        client = MagicMock()
        if callable(events):
            client.stream_chat.side_effect = events
        else:
            client.stream_chat.return_value = iter(events)
        self.client = client
        published = []

        def collect(event, message, **kw):
            if event == "faco_message_stream":
                published.append(dict(message))

        with ExitStack() as stack:
            enter = stack.enter_context
            enter(
                patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client)
            )
            # The job owns the Frappe context, so the relay must never touch it.
            for name in ("init", "connect", "destroy"):
                enter(patch(f"frappe.{name}", side_effect=AssertionError(f"relay called frappe.{name}")))
            # set_user is stubbed because the real one resets the running session.
            self.set_user = enter(patch("frappe.set_user"))
            enter(patch.object(relay, "_update_subscription_cache"))
            enter(
                patch(
                    "frappe_assistant_core.chat.quota_cache.get_quota_snapshot",
                    return_value={"quota_used": 0, "quota_total": 100},
                )
            )
            enter(patch("frappe.publish_realtime", side_effect=collect))
            relay_job.run(relay=job_kwargs["relay"], relay_kwargs=job_kwargs["relay_kwargs"])
        return published

    def _row(self):
        return frappe.db.get_value(
            "FAC Chat Message", {"session_id": self.sid, "role": "assistant"}, ["content"], as_dict=True
        )

    def test_job_mode_relay_keeps_the_jobs_frappe_context(self):
        events = self._run_job(STREAM)

        self.assertEqual(events[-1]["event"], "stream_complete")
        self.assertEqual(self._row().content, "Hi")

    def test_job_runs_the_relay_as_the_asker_under_an_administrator_job(self):
        # Production: execute_job sets Administrator when an enqueue carries no user.
        frappe.set_user("Administrator")
        self._run_job(STREAM, user=self.asker)

        self.set_user.assert_any_call(self.asker)
        self.assertEqual(self.client.stream_chat.call_args.args[2], _ar_user_id(self.asker))

    def test_job_for_another_site_never_calls_ar(self):
        with self.assertRaises(ValueError):
            self._run_job(STREAM, site="other.example.com")
        self.client.stream_chat.assert_not_called()

    def test_unknown_relay_key_never_calls_ar(self):
        with self.assertRaises(KeyError):
            relay_job.run("eval", {"session_id": self.sid})

    def test_stop_pressed_while_queued_aborts_in_the_job(self):
        # Production: cancel_stream sets this flag from a web worker while the job waits in the queue.
        cancel.mark_cancelled(self.sid)
        events = self._run_job(STREAM)

        self.client.stream_chat.assert_not_called()
        self.assertEqual(events[-1]["event"], "stream_aborted")

    def test_busy_refusal_retries_inside_the_job(self):
        # Production: AR answers 503 and SDK 1.14.0 yields this lone AR_BUSY stream_error.
        busy = [{"event": "stream_error", "data": {"error_code": "AR_BUSY", "retry_after": 0.01}}]
        streams = iter([iter(busy), iter(STREAM)])
        events = self._run_job(lambda *a, **kw: next(streams))

        self.assertIn("busy_retrying", [e.get("status") for e in events])
        self.assertEqual(events[-1]["event"], "stream_complete")

    def test_resume_runs_as_a_job(self):
        events = self._run_job(
            RESUME_STREAM,
            relay_name="resume",
            interrupt_response=[{"interruptId": "i1", "response": "approve"}],
        )

        self.assertEqual(events[-1]["event"], "stream_complete")
