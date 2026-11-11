"""The AR breaker opens on consecutive transport failures only, and logs each transition once.

Runs against the real site cache: the breaker is Redis state in production too.
"""

from unittest.mock import MagicMock, patch

import frappe
from assistant_runtime_sdk import ARAPIError, ARConnectionError, ARTimeoutError

from frappe_assistant_core.chat import ar_breaker
from frappe_assistant_core.tests.base_test import BaseAssistantTest

_KEYS = (ar_breaker._FAILURES_KEY, ar_breaker._OPEN_KEY, ar_breaker._WAS_OPEN_KEY)


class TestARBreaker(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self._clear()
        self.addCleanup(self._clear)
        self.log = MagicMock()
        patcher = patch.object(frappe, "logger", return_value=self.log)
        patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def _clear():
        for name in _KEYS:
            frappe.cache.delete(ar_breaker._key(name))

    def _open(self):
        for _ in range(ar_breaker.FAILURE_THRESHOLD):
            ar_breaker.record_failure()

    def test_three_consecutive_failures_open_with_one_log(self):
        for _ in range(ar_breaker.FAILURE_THRESHOLD - 1):
            ar_breaker.record_failure()
        self.assertFalse(ar_breaker.is_open())
        ar_breaker.record_failure()
        self.assertTrue(ar_breaker.is_open())
        ar_breaker.record_failure()
        self.assertEqual(self.log.warning.call_count, 1)
        self.assertIn("AR breaker opened", self.log.warning.call_args.args[0])

    def test_alternating_failures_never_open(self):
        for _ in range(6):
            ar_breaker.record_failure()
            ar_breaker.record_success()
        self.assertFalse(ar_breaker.is_open())

    def test_half_open_failure_reopens_quietly(self):
        self._open()
        # In production the open key's 60 s TTL lapsing lets one probe through; delete it here.
        frappe.cache.delete(ar_breaker._key(ar_breaker._OPEN_KEY))
        self.assertFalse(ar_breaker.is_open())
        ar_breaker.record_failure()
        self.assertTrue(ar_breaker.is_open())
        self.assertEqual(self.log.warning.call_count, 1)
        self.assertEqual(self.log.info.call_count, 0)

    def test_success_after_open_logs_closed_once(self):
        self._open()
        ar_breaker.record_success()
        ar_breaker.record_success()
        self.assertEqual(self.log.info.call_count, 1)
        self.assertEqual(self.log.info.call_args.args[0], "AR breaker closed")

    def test_4xx_is_not_a_transport_failure(self):
        self.assertFalse(ar_breaker.is_transport_failure(ARAPIError("bad", status_code=400)))
        self.assertTrue(ar_breaker.is_transport_failure(ARTimeoutError("slow")))
        self.assertTrue(ar_breaker.is_transport_failure(ARConnectionError("down")))

    def test_call_records_only_transport_failures(self):
        def raise_4xx():
            raise ARAPIError("bad", status_code=400)

        def raise_timeout():
            raise ARTimeoutError("slow")

        for _ in range(ar_breaker.FAILURE_THRESHOLD):
            with self.assertRaises(ARAPIError):
                ar_breaker.call(raise_4xx)
        self.assertFalse(ar_breaker.is_open())
        for _ in range(ar_breaker.FAILURE_THRESHOLD):
            with self.assertRaises(ARTimeoutError):
                ar_breaker.call(raise_timeout)
        self.assertTrue(ar_breaker.is_open())
        with self.assertRaises(ar_breaker.BreakerOpen):
            ar_breaker.call(lambda: 1)
