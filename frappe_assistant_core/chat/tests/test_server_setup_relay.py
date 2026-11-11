# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""The server-setup check reports whether chat relay workers can carry the expected chatters."""

from unittest.mock import patch

import frappe
from frappe.utils.background_jobs import get_queue, get_redis_conn
from rq.results import Result
from rq.worker import Worker, WorkerStatus

from frappe_assistant_core.chat import server_setup
from frappe_assistant_core.chat.api.chat import relay_dispatch
from frappe_assistant_core.chat.api.settings.registration import run_diagnostics
from frappe_assistant_core.chat.server_setup import RELAY_WORKER_FIX, get_server_setup, relay_report
from frappe_assistant_core.tests.base_test import BaseAssistantTest

QUEUES = {"short": 300, "default": 300, "long": 1500, "faco_relay": 2100}
QUEUES_WITHOUT_RELAY = {"short": 300, "default": 300, "long": 1500}


class TestRelayReport(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        relay_dispatch._probe_cache.clear()
        # Production: the operator adds faco_relay to `workers` in common_site_config.json.
        self.queues = patch("frappe.utils.background_jobs.get_queues_timeout", return_value=QUEUES)
        self.queues.start()
        self.workers, self.jobs = [], []
        self.real_workers = relay_dispatch.relay_worker_counts(fresh=True).live
        relay_dispatch._probe_cache.clear()

    def tearDown(self):
        for job in self.jobs:
            try:
                Result.delete_all(job)
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

    def _turn_on(self):
        # Production: an admin ticks the setting in FAC Admin -> Settings -> Chat & Widget.
        frappe.db.set_single_value("FAC Chat Settings", "relay_in_background_job", 1)

    def _report_on(self, expected=10):
        self._turn_on()
        return relay_report(expected)

    def _skip_if_real_worker(self):
        if self.real_workers:
            self.skipTest("a real faco_relay worker is running on this bench")

    def test_off_reports_off_without_reasons(self):
        frappe.db.set_single_value("FAC Chat Settings", "relay_in_background_job", 0)
        report = relay_report(10)
        self.assertEqual(report["status"], "off")
        self.assertFalse(report["enabled"])
        self.assertEqual(report["reasons"], [])
        self.assertIsNone(report["fix"])

    def test_on_without_configured_queue_warns_and_names_the_config(self):
        self.queues.stop()
        with patch("frappe.utils.background_jobs.get_queues_timeout", return_value=QUEUES_WITHOUT_RELAY):
            report = self._report_on()
        self.assertEqual(report["status"], "warning")
        self.assertFalse(report["queue_configured"])
        self.assertIsNone(report["queued"])
        self.assertIn("common_site_config.json", report["reasons"][0])
        self.queues.start()

    def test_on_without_a_worker_warns_and_gives_the_command(self):
        self._skip_if_real_worker()
        report = self._report_on()
        self.assertEqual(report["status"], "warning")
        self.assertIn("bench worker --queue faco_relay", report["reasons"][0])
        self.assertEqual(report["fix"], RELAY_WORKER_FIX)
        self.assertEqual(RELAY_WORKER_FIX, "bench worker --queue faco_relay")

    def test_fewer_workers_than_chatters_warns(self):
        self._skip_if_real_worker()
        self._worker()
        # Production: a worker mid-turn reports BUSY to RQ.
        self._worker(busy=True)
        report = self._report_on(expected=3)
        self.assertEqual(report["status"], "warning")
        self.assertEqual((report["workers"], report["busy"], report["required_workers"]), (2, 1, 3))
        self.assertIn("2 relay workers can carry 2 chats at once", report["reasons"][0])
        self.assertIn("3 people", report["reasons"][0])
        self.assertEqual(report["fix"], RELAY_WORKER_FIX)

    def test_enough_workers_is_ok_and_counts_the_queue(self):
        self._skip_if_real_worker()
        self._worker()
        self._worker()
        before = get_queue("faco_relay").count
        # Production: a turn waiting for a free relay worker sits on the queue.
        job = get_queue("faco_relay").enqueue("frappe.utils.now")
        self.jobs.append(job)
        report = self._report_on(expected=2)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["reasons"], [])
        self.assertIsNone(report["fix"])
        self.assertEqual(report["workers"], 2)
        self.assertEqual(report["queued"], before + 1)

    def test_diagnostics_and_get_server_setup_carry_the_relay_row(self):
        frappe.set_user("Administrator")
        with patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=None):
            self.assertIn("relay", run_diagnostics()["server_setup"])
        self.assertIn("relay", get_server_setup())
        self.assertIn("relay", server_setup.server_setup_report())
