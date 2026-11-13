"""Every turn's relay starts through _start_relay: an RQ job on faco_relay, or the in-process pool."""

import time
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import frappe
from frappe.utils.background_jobs import get_job, get_queue, get_redis_conn
from rq.worker import Worker

from frappe_assistant_core.chat.api.chat import (
    live_turn,
    messages,
    relay,
    relay_dispatch,
    relay_job,
    relay_shutdown,
)
from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import FACChatMessage
from frappe_assistant_core.chat.doctype.fac_chat_session_state.fac_chat_session_state import (
    FACChatSessionState,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest

QUEUES = {"short": 300, "default": 300, "long": 1500, "faco_relay": 2100}
RESUME = '[{"interruptId": "i1", "response": "approve"}]'
PRE_TURN = {"blob": "H4sI-pre", "sig": "sig-pre", "format_version": 1, "turn_seq": 3}


def _event(name, **data):
    return {"event": name, "data": data}


STREAM = [
    _event("stream_start", message_id="m1"),
    _event("stream_chunk", content="Hi"),
    _event("stream_complete", full_response="Hi", message_id="m1"),
]


class TestRelayInBackgroundJob(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.sid = f"jobturn-{frappe.generate_hash(length=8)}"
        relay_dispatch._probe_cache.clear()
        self.addCleanup(relay_dispatch._probe_cache.clear)
        # Production: the operator adds faco_relay to `workers` in common_site_config.json.
        queues = patch("frappe.utils.background_jobs.get_queues_timeout", return_value=QUEUES)
        queues.start()
        self.addCleanup(queues.stop)
        # Chat access is a seat on FAC Cloud; this site has no AR to ask.
        access = patch("frappe_assistant_core.chat.api.settings.can_use_faco", return_value={"can_use": True})
        access.start()
        self.addCleanup(access.stop)
        # Socket.IO is not under test.
        publish = patch("frappe.publish_realtime")
        publish.start()
        self.addCleanup(publish.stop)
        self.client = MagicMock()
        self.client.stream_chat.side_effect = lambda *a, **kw: iter(STREAM)
        cloud = patch(
            "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=self.client
        )
        cloud.start()
        self.addCleanup(cloud.stop)
        self.addCleanup(relay_shutdown._draining.clear)
        self.addCleanup(live_turn.clear, self.sid)
        self.workers, self.job_ids = [], []
        self.addCleanup(self._cleanup_rq)
        enqueue_relay = relay_dispatch.enqueue_relay

        def record(fn, args, kwargs, *, job_id):
            # Every job a test enqueues is deleted, even when the test fails before reading it.
            self.job_ids.append(job_id)
            return enqueue_relay(fn, args, kwargs, job_id=job_id)

        recording = patch.object(relay_dispatch, "enqueue_relay", record)
        recording.start()
        self.addCleanup(recording.stop)
        if relay_dispatch.relay_worker_counts(fresh=True).live:
            self.skipTest("a real faco_relay worker is running on this bench")
        relay_dispatch._probe_cache.clear()

    def _cleanup_rq(self):
        for job_id in self.job_ids:
            job = get_job(job_id)
            if job is not None:
                job.delete()
        for worker in self.workers:
            worker.register_death()

    def _on_with_worker(self):
        # Production: an admin ticks the setting in FAC Admin and runs `bench worker --queue faco_relay`,
        # which registers itself like this on start.
        frappe.db.set_single_value("FAC Chat Settings", "relay_in_background_job", 1)
        worker = Worker(
            [get_queue("faco_relay")],
            connection=get_redis_conn(),
            name=f"t-{frappe.generate_hash(length=8)}",
        )
        worker.register_birth()
        self.workers.append(worker)
        return worker

    def _job(self, turn):
        return get_job(relay_dispatch.relay_job_id(turn))

    def _turn_job(self):
        """The job named by the session's current live-turn entry."""
        return self._job(live_turn.get(self.sid)["turn"])

    def _user_rows(self) -> int:
        return frappe.db.count("FAC Chat Message", {"session_id": self.sid, "role": "user"})

    def _run_job_inline(self, job):
        """Run the job's relay in this process, as an RQ worker would run it."""
        with ExitStack() as stack:
            enter = stack.enter_context
            # The real set_user resets the running test session.
            enter(patch("frappe.set_user"))
            enter(patch.object(relay, "_update_subscription_cache"))
            enter(
                patch(
                    "frappe_assistant_core.chat.quota_cache.get_quota_snapshot",
                    return_value={"quota_used": 0, "quota_total": 100},
                )
            )
            relay_job.run(**job.kwargs["kwargs"])

    def test_setting_off_submits_to_the_pool_and_never_touches_rq(self):
        frappe.db.set_single_value("FAC Chat Settings", "relay_in_background_job", 0)
        with (
            patch.object(messages._relay_pool, "submit") as submit,
            patch("frappe.utils.background_jobs.get_redis_conn", side_effect=AssertionError) as redis_conn,
            patch("frappe.enqueue", side_effect=AssertionError) as enqueue,
        ):
            ack = messages.send_message(session_id=self.sid, message="hi")
        self.assertEqual(ack["status"], "processing")
        self.assertIs(submit.call_args.args[0], relay._relay_ar_stream)
        self.assertIsNone(live_turn.get(self.sid)["relay"])
        # Both would be swallowed (probe failure, enqueue failure) and fall back to the pool.
        redis_conn.assert_not_called()
        enqueue.assert_not_called()

    def test_a_failing_dispatch_decision_falls_back_to_the_pool(self):
        # Production: new code is served before `bench migrate` adds the relay_in_background_job field.
        with (
            patch.object(
                relay_dispatch,
                "job_relay_enabled",
                autospec=True,
                side_effect=frappe.db.InternalError("Field relay_in_background_job does not exist"),
            ),
            patch.object(messages._relay_pool, "submit") as submit,
            patch("frappe.enqueue", side_effect=AssertionError) as enqueue,
        ):
            ack = messages.send_message(session_id=self.sid, message="hi")
        self.assertEqual(ack["status"], "processing")
        self.assertIs(submit.call_args.args[0], relay._relay_ar_stream)
        self.assertIsNone(live_turn.get(self.sid)["relay"])
        enqueue.assert_not_called()

    def test_send_enqueues_one_job_named_by_the_turn(self):
        self._on_with_worker()
        with patch.object(messages._relay_pool, "submit", side_effect=AssertionError):
            messages.send_message(session_id=self.sid, message="hi")
        entry = live_turn.get(self.sid)
        self.assertEqual(entry["relay"], "job")
        job = self._job(entry["turn"])
        self.assertEqual(job.kwargs["kwargs"]["relay"], "stream")
        self.assertEqual(job.kwargs["user"], frappe.session.user)
        self.assertEqual(job.kwargs["kwargs"]["relay_kwargs"]["live_turn_token"], entry["turn"])

    def test_continue_and_resume_enqueue_their_relays(self):
        self._on_with_worker()
        with patch.object(messages._relay_pool, "submit", side_effect=AssertionError):
            ack = messages.continue_response(session_id=self.sid, message_id="m1")
            self.assertEqual(ack["status"], "processing")
            job = self._turn_job()
            self.assertEqual(job.kwargs["kwargs"]["relay"], "stream")
            self.assertEqual(job.kwargs["kwargs"]["relay_kwargs"]["continue_from_message_id"], "m1")

            ack = messages.resume_interrupt(session_id=self.sid, interrupt_response=RESUME, message_id="m1")
            self.assertEqual(ack["status"], "processing")
            job = self._turn_job()
            self.assertEqual(job.kwargs["kwargs"]["relay"], "resume")
            relay_kwargs = job.kwargs["kwargs"]["relay_kwargs"]
            self.assertEqual(relay_kwargs["message_id"], "m1")
            self.assertEqual(
                relay_kwargs["interrupt_response"], [{"interruptId": "i1", "response": "approve"}]
            )
        self.assertEqual(live_turn.get(self.sid)["relay"], "job")

    def test_retry_enqueues_after_a_lost_job_or_falls_back_when_no_worker(self):
        worker = self._on_with_worker()
        # A sent message as start_turn leaves it: the user row, and the state before its turn.
        FACChatSessionState.upsert(self.sid, frappe.session.user, PRE_TURN)
        user = FACChatMessage.create_message(session_id=self.sid, role="user", content="What is overdue?")
        FACChatSessionState.snapshot_pre_turn(self.sid, frappe.session.user, user.name)
        submitted = []
        with patch.object(messages._relay_pool, "submit", side_effect=lambda *a, **kw: submitted.append(kw)):
            ack = messages.retry_turn(session_id=self.sid, user_message=user.name)
            self.assertEqual(ack["status"], "processing")
            first = live_turn.get(self.sid)
            self.assertEqual(first["relay"], "job")
            self.assertEqual(
                self._job(first["turn"]).kwargs["kwargs"]["relay_kwargs"]["message_name"], user.name
            )
            self.assertEqual(submitted, [])

            # Production: the relay worker is killed with the job still queued, and 20 s pass.
            worker.register_death()
            relay_dispatch._probe_cache.clear()
            first["last_progress_at"] = time.time() - 20
            frappe.cache().set_value(
                live_turn._key(self.sid), first, expires_in_sec=live_turn.ENTRY_TTL_SECONDS
            )

            ack = messages.retry_turn(session_id=self.sid, user_message=user.name)

        self.assertEqual(ack["status"], "processing")
        self.assertEqual(len(submitted), 1)
        second = live_turn.get(self.sid)
        self.assertNotEqual(second["turn"], first["turn"])
        self.assertIsNone(second["relay"])
        self.assertEqual(submitted[0]["live_turn_token"], second["turn"])

    def test_no_worker_falls_back_to_the_pool(self):
        # Production: an admin ticks the setting before any faco_relay worker runs.
        frappe.db.set_single_value("FAC Chat Settings", "relay_in_background_job", 1)
        with patch.object(messages._relay_pool, "submit") as submit:
            messages.send_message(session_id=self.sid, message="hi")
        submit.assert_called_once()
        self.assertIsNone(live_turn.get(self.sid).get("relay"))

    def test_failed_enqueue_falls_back_and_unmarks_the_entry(self):
        self._on_with_worker()
        with (
            patch.object(relay_dispatch, "enqueue_relay", side_effect=relay_dispatch.RelayQueueUnavailable),
            patch.object(messages._relay_pool, "submit") as submit,
            patch.object(messages.frappe, "logger", wraps=frappe.logger) as logger,
        ):
            messages.send_message(session_id=self.sid, message="hi")
        submit.assert_called_once()
        self.assertIsNone(live_turn.get(self.sid).get("relay"))
        self.assertEqual(submit.call_args.kwargs["live_turn_token"], live_turn.get(self.sid)["turn"])
        logger.assert_any_call("faco.relay")

    def test_failed_enqueue_on_a_draining_web_worker_asks_for_a_resend(self):
        self._on_with_worker()
        # Production: gunicorn's graceful exit sets this flag (relay_shutdown._begin_drain).
        relay_shutdown._draining.set()
        with (
            patch.object(relay_dispatch, "enqueue_relay", side_effect=relay_dispatch.RelayQueueUnavailable),
            patch.object(messages._relay_pool, "submit") as submit,
        ):
            ack = messages.send_message(session_id=self.sid, message="hi")
        self.assertEqual(ack["status"], "retry")
        submit.assert_not_called()
        self.assertEqual(self._user_rows(), 0)
        self.assertIsNone(live_turn.get(self.sid))

    def test_draining_web_worker_still_enqueues_in_job_mode(self):
        self._on_with_worker()
        # Production: gunicorn's graceful exit sets this flag (relay_shutdown._begin_drain).
        relay_shutdown._draining.set()
        with patch.object(messages._relay_pool, "submit", side_effect=AssertionError):
            ack = messages.send_message(session_id=self.sid, message="hi")
        self.assertEqual(ack["status"], "processing")
        self.assertEqual(self._user_rows(), 1)
        self.assertIsNotNone(self._turn_job())

    def test_draining_retry_still_enqueues_in_job_mode(self):
        self._on_with_worker()
        # A sent message as start_turn leaves it: the user row, and the state before its turn.
        FACChatSessionState.upsert(self.sid, frappe.session.user, PRE_TURN)
        user = FACChatMessage.create_message(session_id=self.sid, role="user", content="What is overdue?")
        FACChatSessionState.snapshot_pre_turn(self.sid, frappe.session.user, user.name)
        # Production: gunicorn's graceful exit sets this flag (relay_shutdown._begin_drain).
        relay_shutdown._draining.set()
        with patch.object(messages._relay_pool, "submit", side_effect=AssertionError):
            ack = messages.retry_turn(session_id=self.sid, user_message=user.name)
        self.assertEqual(ack["status"], "processing")
        self.assertIsNotNone(self._turn_job())

    def test_restricted_user_never_runs_as_a_job(self):
        self._on_with_worker()
        # Production: the user asked for GDPR Article 18 processing restriction.
        with (
            patch.object(messages, "_is_processing_restricted", return_value=True),
            patch.object(relay_dispatch, "use_job_relay", wraps=relay_dispatch.use_job_relay) as use_job,
            patch("frappe.enqueue", side_effect=AssertionError) as enqueue,
            patch.object(messages._relay_pool, "submit") as submit,
        ):
            ack = messages.send_message(session_id=self.sid, message="hi")
        self.assertEqual(ack["status"], "processing")
        submit.assert_called_once()
        self.assertTrue(submit.call_args.args[13])  # restricted
        self.assertIsNone(submit.call_args.kwargs["live_turn_token"])
        # A swallowed enqueue failure would fall back to the pool too, so the calls are checked.
        enqueue.assert_not_called()
        use_job.assert_not_called()
        self.assertIsNone(live_turn.get(self.sid))

    def test_overloaded_queue_falls_back_without_an_error_message(self):
        self._on_with_worker()
        # Production: faco_relay holds more queued jobs than max_queued_jobs allows, so the real
        # _check_queue_size throws QueueOverloaded; a negative limit makes an empty queue "full".
        with (
            patch.dict(frappe.local.conf, {"max_queued_jobs": -(10**6)}),
            patch.object(messages._relay_pool, "submit") as submit,
        ):
            logged = len(frappe.local.message_log)
            ack = messages.send_message(session_id=self.sid, message="hi")
        self.assertEqual(ack["status"], "processing")
        submit.assert_called_once()
        self.assertEqual(len(frappe.local.message_log), logged)
        self.assertIsNone(live_turn.get(self.sid)["relay"])

    def test_double_send_runs_ar_only_for_the_newest_turn(self):
        self._on_with_worker()
        older, newer = [], []
        for job, text in ((older, "hi"), (newer, "hi, and which are overdue?")):
            messages.send_message(session_id=self.sid, message=text, client_turn_id="c1")
            job.append(self._turn_job())
        older, newer = older[0], newer[0]
        self.assertNotEqual(older.id, newer.id)

        self._run_job_inline(older)  # oldest first, as RQ would
        self.client.stream_chat.assert_not_called()

        self._run_job_inline(newer)
        self.client.stream_chat.assert_called_once()
        self.assertEqual(self.client.stream_chat.call_args.args[:2], (self.sid, "hi, and which are overdue?"))

    def test_toggle_on_leaves_a_running_pool_turn_alone(self):
        with patch.object(messages._relay_pool, "submit"):
            messages.send_message(session_id=self.sid, message="hi")  # setting off: a pool turn
        entry = live_turn.get(self.sid)
        self._on_with_worker()
        # 30 s into the turn: past the job grace, well inside the starting bound.
        self.assertFalse(live_turn.is_stale(entry, now=entry["last_progress_at"] + 30))
        self.assertEqual(live_turn.get(self.sid)["turn"], entry["turn"])
