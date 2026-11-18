"""A relay job's worker, asked to stop, starts the same drain gunicorn's exit hook starts."""

from unittest.mock import patch

import frappe
from frappe.utils.background_jobs import get_queue, get_redis_conn
from rq.utils import now
from rq.worker import Worker

from frappe_assistant_core.chat.api.chat import relay_dispatch, relay_shutdown
from frappe_assistant_core.chat.tests import test_relay_job
from frappe_assistant_core.tests.base_test import BaseAssistantTest


def _event(name, **data):
    return {"event": name, "data": data}


QUEUES = {"short": 300, "default": 300, "long": 1500, "faco_relay": 2100}


class TestRelayShutdownJob(BaseAssistantTest):
    # The job harness is borrowed, not inherited, so its own tests do not run twice.
    _capture_enqueue = test_relay_job.TestRelayJob._capture_enqueue
    _run_job = test_relay_job.TestRelayJob._run_job

    def setUp(self):
        super().setUp()
        self.sid = f"shutjob-{frappe.generate_hash(length=8)}"
        self.asker = test_relay_job.ASKER
        self.workers = []
        # Production: the operator adds faco_relay to `workers` in common_site_config.json.
        queues = patch("frappe.utils.background_jobs.get_queues_timeout", return_value=QUEUES)
        queues.start()
        self.addCleanup(queues.stop)
        self.addCleanup(self._reset)
        if relay_dispatch.relay_worker_counts(fresh=True).live:
            self.skipTest("a real faco_relay worker is running on this bench")

    def _reset(self):
        relay_shutdown._draining.clear()
        relay_shutdown._deadline = None
        relay_shutdown._watcher = None
        relay_shutdown._job_grace = None
        relay_shutdown._last_poll = float("-inf")
        for worker in self.workers:
            worker.register_death()
        test_relay_job.live_turn.clear(self.sid)
        test_relay_job.cancel.clear(self.sid)

    def _worker(self):
        # Production: `bench worker --queue faco_relay` registers itself like this on start.
        worker = Worker(
            [get_queue("faco_relay")],
            connection=get_redis_conn(),
            name=f"t-{frappe.generate_hash(length=8)}",
        )
        worker.register_birth()
        self.workers.append(worker)
        return worker

    @staticmethod
    def _request_shutdown(worker):
        # Production: RQ writes this when the worker gets SIGTERM while its horse runs a job.
        worker._shutdown_requested_date = now()
        worker.set_shutdown_requested_date()

    def test_pool_process_never_polls_a_worker(self):
        with patch.object(relay_shutdown, "_rq_shutdown_requested", side_effect=AssertionError):
            self.assertFalse(relay_shutdown.is_draining())

    def test_shutdown_request_on_the_workers_hash_starts_the_drain(self):
        worker = self._worker()
        self._request_shutdown(worker)
        with patch.object(relay_shutdown, "_rq_worker_key", return_value=worker.key):
            relay_shutdown.watch_rq_worker()
            self.assertTrue(relay_shutdown.is_draining())

    def test_a_worker_nobody_stopped_never_drains(self):
        worker = self._worker()
        with patch.object(relay_shutdown, "_rq_worker_key", return_value=worker.key):
            relay_shutdown.watch_rq_worker()
            self.assertFalse(relay_shutdown.is_draining())

    def test_the_poll_is_throttled(self):
        with patch.object(relay_shutdown, "_rq_shutdown_requested", return_value=False) as poll:
            relay_shutdown.watch_rq_worker()
            for _ in range(5):
                relay_shutdown.is_draining()
        self.assertEqual(poll.call_count, 1)

    def test_poll_failure_never_drains(self):
        with patch.object(relay_shutdown, "_rq_shutdown_requested", side_effect=ConnectionError):
            relay_shutdown.watch_rq_worker()
            self.assertFalse(relay_shutdown.is_draining())

    def test_outside_a_job_there_is_no_worker_key(self):
        self.assertIsNone(relay_shutdown._rq_worker_key())

    def test_worker_shutdown_request_saves_the_partial_as_interrupted(self):
        worker = self._worker()

        def stream(*args, **kwargs):
            yield _event("stream_start", message_id="m-shut")
            yield _event("stream_chunk", content="Half an ans")
            self._request_shutdown(worker)
            yield _event("heartbeat")
            yield _event("stream_chunk", content="wer.")
            yield _event("stream_complete", full_response="Half an answer.", message_id="m-shut")

        # With the job grace at MARGIN_SECONDS the deadline falls the moment the drain starts;
        # a zero poll interval stops the 5 s throttle delaying the heartbeat's check.
        with (
            patch.object(relay_shutdown, "_rq_worker_key", return_value=worker.key),
            patch.object(relay_shutdown, "_read_job_grace", return_value=relay_shutdown.MARGIN_SECONDS),
            patch.object(relay_shutdown, "WORKER_POLL_SECONDS", 0),
        ):
            events = self._run_job(stream)

        self.assertEqual(events[-1]["error_code"], "TURN_INTERRUPTED")
        row = frappe.db.get_value(
            "FAC Chat Message",
            {"session_id": self.sid, "role": "assistant"},
            ["content", "errored"],
            as_dict=True,
        )
        self.assertEqual((row.content, row.errored), ("Half an ans", 1))

    def test_grace_reads_the_site_config_key(self):
        with patch.dict(frappe.local.conf, {"faco_relay_job_shutdown_grace": 45}):
            self.assertEqual(relay_shutdown._read_job_grace(), 45)
        self.assertEqual(relay_shutdown._read_job_grace(), relay_shutdown.JOB_GRACE_SECONDS)
