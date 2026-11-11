"""Tests for relay_dispatch: when a turn's relay runs as an RQ job on faco_relay."""

import pickle
from unittest.mock import patch

import frappe
from frappe.utils.background_jobs import get_job, get_queue, get_redis_conn
from rq.job import JobStatus
from rq.worker import Worker, WorkerStatus

from frappe_assistant_core.chat.api.chat import relay, relay_dispatch
from frappe_assistant_core.tests.base_test import BaseAssistantTest

QUEUES = {"short": 300, "default": 300, "long": 1500, "faco_relay": 2100}


class TestRelayDispatch(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        relay_dispatch._probe_cache.clear()
        # Production: the operator adds faco_relay to `workers` in common_site_config.json.
        self.queues = patch("frappe.utils.background_jobs.get_queues_timeout", return_value=QUEUES)
        self.queues.start()
        self.workers, self.jobs = [], []

    def tearDown(self):
        for job in self.jobs:
            try:
                job.delete()
            except Exception:
                pass
        for worker in self.workers:
            worker.register_death()
        self.queues.stop()
        relay_dispatch._probe_cache.clear()
        super().tearDown()

    def _worker(self, busy=False):
        # Production: `bench worker --queue faco_relay` registers itself like this on start.
        worker = Worker(
            [get_queue("faco_relay")],
            connection=get_redis_conn(),
            name=f"t-{frappe.generate_hash(length=8)}",
        )
        worker.register_birth()
        if busy:
            worker.set_state(WorkerStatus.BUSY)
        self.workers.append(worker)
        return worker

    def _enqueue(self, turn):
        job_id = relay_dispatch.relay_job_id(turn)
        relay_dispatch.enqueue_relay(
            relay._relay_ar_stream,
            ("s-" + turn, "hi", "hi", None, None, "a@x.com", frappe.local.site),
            {"live_turn_token": turn},
            job_id=job_id,
        )
        job = get_job(job_id)
        self.jobs.append(job)
        return job_id, job

    def test_job_timeout_covers_the_longest_turn(self):
        self.assertEqual(relay_dispatch.RELAY_JOB_TIMEOUT_SECONDS, relay.RELAY_MAX_TURN_SECONDS + 300)

    def test_setting_off_never_touches_rq(self):
        frappe.db.set_single_value("FAC Chat Settings", "relay_in_background_job", 0)
        with patch("frappe.utils.background_jobs.get_redis_conn") as redis_conn:
            self.assertFalse(relay_dispatch.use_job_relay())
        redis_conn.assert_not_called()

    def test_on_with_no_worker_is_not_used(self):
        # Production: an admin ticks the setting in FAC Admin -> Settings -> Chat & Widget.
        frappe.db.set_single_value("FAC Chat Settings", "relay_in_background_job", 1)
        self.assertFalse(relay_dispatch.use_job_relay())

    def test_on_with_unconfigured_queue_is_not_used(self):
        frappe.db.set_single_value("FAC Chat Settings", "relay_in_background_job", 1)
        self.queues.stop()
        self.queues = patch(
            "frappe.utils.background_jobs.get_queues_timeout",
            return_value={k: v for k, v in QUEUES.items() if k != "faco_relay"},
        )
        self.queues.start()
        self.assertFalse(relay_dispatch.use_job_relay())

    def test_on_with_a_live_worker_is_used(self):
        frappe.db.set_single_value("FAC Chat Settings", "relay_in_background_job", 1)
        self._worker()
        self.assertTrue(relay_dispatch.use_job_relay())

    def test_worker_counts_split_live_and_busy(self):
        self._worker()
        self._worker(busy=True)
        self.assertEqual(relay_dispatch.relay_worker_counts(fresh=True), (2, 1))

    def test_probe_failure_reads_no_workers_and_is_cached(self):
        with patch.object(relay_dispatch, "Worker") as worker_cls:
            worker_cls.all.side_effect = ConnectionError("queue redis down")
            self.assertEqual(relay_dispatch.relay_worker_counts(), (0, 0))
            relay_dispatch.relay_worker_counts()
            self.assertEqual(worker_cls.all.call_count, 1)

    def test_enqueue_names_queue_timeout_and_binds_every_argument(self):
        job_id, job = self._enqueue("tok1")
        self.assertEqual(job.origin.split(":")[-1], "faco_relay")
        self.assertEqual(job.timeout, 2100)
        relay_kwargs = job.kwargs["kwargs"]["relay_kwargs"]
        self.assertEqual(job.kwargs["kwargs"]["relay"], "stream")
        self.assertEqual(
            (
                relay_kwargs["session_id"],
                relay_kwargs["user"],
                relay_kwargs["site"],
                relay_kwargs["live_turn_token"],
            ),
            ("s-tok1", "a@x.com", frappe.local.site, "tok1"),
        )
        pickle.loads(pickle.dumps(relay_kwargs))

    def test_same_turn_enqueued_twice_is_one_job(self):
        job_id = relay_dispatch.relay_job_id("tok2")
        for _attempt in range(2):
            relay_dispatch.enqueue_relay(
                relay._relay_ar_stream,
                ("s2", "hi", "hi", None, None, "a@x.com", frappe.local.site),
                {},
                job_id=job_id,
            )
            self.jobs.append(get_job(job_id))
        queued = [j for j in get_queue("faco_relay").jobs if j.id.endswith(job_id)]
        self.assertEqual(len(queued), 1)

    def test_unknown_function_is_refused(self):
        with self.assertRaises(ValueError):
            relay_dispatch.enqueue_relay(print, (), {}, job_id=relay_dispatch.relay_job_id(None))

    def test_queue_overload_raises_relay_queue_unavailable(self):
        with patch("frappe.utils.background_jobs._check_queue_size", side_effect=frappe.QueueOverloaded):
            with self.assertRaises(relay_dispatch.RelayQueueUnavailable):
                relay_dispatch.enqueue_relay(
                    relay._relay_ar_stream,
                    ("s3",) + ("x",) * 6,
                    {},
                    job_id=relay_dispatch.relay_job_id(None),
                )

    def test_job_lost_by_state(self):
        job_id, job = self._enqueue("tok3")

        # Production: a worker sets STARTED when it picks the job up.
        job.set_status(JobStatus.STARTED)
        self.assertFalse(relay_dispatch.relay_job_lost(job_id))

        # Production: RQ sets FAILED when the work horse dies or the job raises.
        job.set_status(JobStatus.FAILED)
        self.assertTrue(relay_dispatch.relay_job_lost(job_id))

        # Production: a job still QUEUED with nobody on faco_relay (worker crashed or never started).
        job.set_status(JobStatus.QUEUED)
        relay_dispatch._probe_cache.clear()
        self.assertTrue(relay_dispatch.relay_job_lost(job_id))

        # Production: same QUEUED job, a faco_relay worker is alive and will pick it up.
        self._worker()
        relay_dispatch._probe_cache.clear()
        self.assertFalse(relay_dispatch.relay_job_lost(job_id))

        # Production: the job hash expired or was removed (result TTL, purge).
        job.delete()
        self.assertTrue(relay_dispatch.relay_job_lost(job_id))
