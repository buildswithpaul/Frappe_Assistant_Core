"""A live turn whose relay runs as an RQ job is judged stale by the job's state too."""

import time
from unittest.mock import MagicMock, patch

import frappe
from frappe.utils.background_jobs import get_job, get_queue, get_redis_conn
from rq.job import JobStatus
from rq.worker import Worker, WorkerStatus

from frappe_assistant_core.chat.api.block_builder import BlockBuilder
from frappe_assistant_core.chat.api.chat import live_turn, relay, relay_dispatch, relay_job
from frappe_assistant_core.tests.base_test import BaseAssistantTest

QUEUES = {"short": 300, "default": 300, "long": 1500, "faco_relay": 2100}
RETRY_COPY = "This answer was interrupted before it finished. Retry to run it again."


class TestLiveTurnJobRelay(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        relay_dispatch._probe_cache.clear()
        # Production: the operator adds faco_relay to `workers` in common_site_config.json.
        queues = patch("frappe.utils.background_jobs.get_queues_timeout", return_value=QUEUES)
        queues.start()
        self.addCleanup(queues.stop)
        self.addCleanup(relay_dispatch._probe_cache.clear)
        self.owner = self.make_throwaway_user("job-owner")
        self.sid = f"jobrelay-{frappe.generate_hash(length=8)}"
        # Production: send_message saves the user row before the relay is queued.
        frappe.get_doc(
            {
                "doctype": "FAC Chat Message",
                "session_id": self.sid,
                "user": self.owner,
                "role": "user",
                "content": "hello",
            }
        ).insert(ignore_permissions=True)
        frappe.set_user(self.owner)
        self.addCleanup(frappe.set_user, "Administrator")
        self.addCleanup(live_turn.clear, self.sid)
        self.addCleanup(live_turn.unbind, self.sid)
        publish = patch("frappe.publish_realtime")
        publish.start()
        self.addCleanup(publish.stop)
        self.workers, self.jobs = [], []
        self.addCleanup(self._cleanup_rq)

    def _cleanup_rq(self):
        for job in self.jobs:
            try:
                job.delete()
            except Exception:
                pass
        for worker in self.workers:
            worker.register_death()

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
            (self.sid, "hi", "hi", None, None, self.owner, frappe.local.site),
            {"live_turn_token": turn},
            job_id=job_id,
        )
        job = get_job(job_id)
        self.jobs.append(job)
        return job

    def _age_entry(self, age):
        entry = live_turn.get(self.sid)
        entry["last_progress_at"] = time.time() - age
        # Written straight to the cache: _write would stamp the time as now.
        frappe.cache().set_value(live_turn._key(self.sid), entry, expires_in_sec=live_turn.ENTRY_TTL_SECONDS)
        return entry

    def _job_entry(self, status, age, entry_status="starting"):
        # Production: _start_relay enqueues this job right after live_turn.start writes this entry.
        turn = frappe.generate_hash(length=12)
        if status != "missing":
            job = self._enqueue(turn)
            if status is not None:
                job.set_status(status)
        return {
            "turn": turn,
            "status": entry_status,
            "relay": "job",
            "last_progress_at": time.time() - age,
        }

    def test_entry_keeps_its_relay_mark_through_heartbeats(self):
        turn = live_turn.start(self.sid, relay="job")
        live = live_turn.bind(self.sid, BlockBuilder(), turn=turn)
        live.record({"event": "heartbeat"})
        live._written_at = -1e9
        live.record({"event": "heartbeat"})
        self.assertEqual(live_turn.get(self.sid)["relay"], "job")

    def test_queued_job_with_no_live_worker_is_stale_at_once(self):
        entry = self._job_entry(status=None, age=11)
        self.assertTrue(live_turn.is_stale(entry))

    def test_queued_job_behind_busy_workers_is_stale_only_after_180s(self):
        self._worker(busy=True)
        self.assertFalse(live_turn.is_stale(self._job_entry(status=None, age=170)))
        self.assertTrue(live_turn.is_stale(self._job_entry(status=None, age=181)))

    def test_failed_job_with_a_live_entry_is_stale_at_once(self):
        # Production: RQ marks the job FAILED when an OOM kill or SIGKILL takes its horse mid-turn.
        entry = self._job_entry(status=JobStatus.FAILED, age=11, entry_status="streaming")
        self.assertTrue(live_turn.is_stale(entry))

    def test_running_job_is_judged_by_heartbeat_alone(self):
        started = self._job_entry(status=JobStatus.STARTED, age=50, entry_status="streaming")
        self.assertFalse(live_turn.is_stale(started))
        started = self._job_entry(status=JobStatus.STARTED, age=61, entry_status="streaming")
        self.assertTrue(live_turn.is_stale(started))

    def test_fresh_entry_is_not_judged_by_job_state(self):
        # The entry is written just before the enqueue; a probe in that window finds no job yet.
        self.assertFalse(live_turn.is_stale(self._job_entry(status="missing", age=2)))

    def test_rq_read_failure_never_ends_a_turn(self):
        with patch.object(relay_dispatch, "relay_job_lost", side_effect=ConnectionError):
            self.assertFalse(live_turn.is_stale(self._job_entry(status=None, age=30)))

    def test_stale_check_follows_the_entry_not_the_setting(self):
        # Production: an admin switches the setting off while a job turn waits in the queue.
        frappe.db.set_single_value("FAC Chat Settings", "relay_in_background_job", 0)
        self.assertTrue(live_turn.is_stale(self._job_entry(status=None, age=11)))

    def test_pool_entry_never_reads_rq(self):
        with patch.object(relay_dispatch, "relay_job_lost", side_effect=AssertionError):
            live_turn.is_stale({"turn": "t", "status": "streaming", "last_progress_at": time.time() - 30})

    def test_lost_job_turn_is_interrupted_with_retry_copy_and_a_late_job_does_nothing(self):
        # Production: _start_relay writes the entry with relay="job", then enqueues; no worker runs.
        turn = live_turn.start(self.sid, relay="job")
        job = self._enqueue(turn)
        self._age_entry(11)

        result = live_turn.mark_turn_interrupted(self.sid)

        self.assertTrue(result["interrupted"])
        self.assertEqual(result["error"], RETRY_COPY)
        row = frappe.db.get_value(
            "FAC Chat Message", {"session_id": self.sid, "role": "assistant"}, "errored"
        )
        self.assertEqual(row, 1)
        # The worker comes back and picks the job up late: holds() is false, so AR is never called.
        client = MagicMock()
        with (
            patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client),
            patch.object(relay_job.relay_shutdown, "watch_rq_worker"),
            patch("frappe.set_user"),
        ):
            relay_job.run(
                relay=job.kwargs["kwargs"]["relay"], relay_kwargs=job.kwargs["kwargs"]["relay_kwargs"]
            )
        client.stream_chat.assert_not_called()
