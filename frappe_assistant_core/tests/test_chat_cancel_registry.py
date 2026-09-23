"""The cancel registry must survive multi-worker gunicorn: storage is
frappe.cache (Redis), not process memory."""

import unittest
from unittest.mock import MagicMock, Mock, patch

from assistant_runtime_sdk import ARTimeoutError

from frappe_assistant_core.chat.api.chat import cancel as cancel_mod

_GET_FAC_CLOUD_CLIENT = "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client"


class TestCancelRegistryRedis(unittest.TestCase):
    def test_mark_uses_cache_with_ttl(self):
        cache = MagicMock()
        with patch.object(cancel_mod, "frappe") as fm:
            fm.cache.return_value = cache
            cancel_mod.mark_cancelled("s1")
            cache.set_value.assert_called_once_with("fac_cancel:s1", "1", expires_in_sec=120)

    def test_is_cancelled_reads_cache(self):
        cache = MagicMock()
        with patch.object(cancel_mod, "frappe") as fm:
            fm.cache.return_value = cache
            cache.get_value.return_value = "1"
            self.assertTrue(cancel_mod.is_cancelled("s1"))
            cache.get_value.return_value = None
            self.assertFalse(cancel_mod.is_cancelled("s1"))

    def test_is_cancelled_reads_with_expires_true(self):
        # frappe.cache().get_value() defaults to use_local_cache=True, which
        # memoizes a None miss into frappe.local.cache and would keep serving
        # stale "not cancelled" to a long-lived worker after a first miss.
        # expires=True on the read is the only thing that prevents that.
        cache = MagicMock()
        with patch.object(cancel_mod, "frappe") as fm:
            fm.cache.return_value = cache
            cache.get_value.return_value = "1"
            cancel_mod.is_cancelled("s1")
            cache.get_value.assert_called_with("fac_cancel:s1", expires=True)

    def test_clear_deletes_key(self):
        cache = MagicMock()
        with patch.object(cancel_mod, "frappe") as fm:
            fm.cache.return_value = cache
            cancel_mod.clear("s1")
            cache.delete_value.assert_called_once_with("fac_cancel:s1")

    def test_empty_session_id_is_noop(self):
        with patch.object(cancel_mod, "frappe") as fm:
            self.assertFalse(cancel_mod.is_cancelled(""))
            cancel_mod.mark_cancelled("")
            cancel_mod.clear("")
            fm.cache.assert_not_called()


class TestCancelStreamARPropagation(unittest.TestCase):
    """cancel_stream must reach AR, but never let AR block or break the
    local Stop the user is actually waiting on."""

    def _mock_frappe(self, fm):
        # No owning message row found -> ownership check and
        # _abort_pending_interactions's row lookup both no-op cleanly.
        fm.db.get_value.return_value = None
        fm.cache.return_value = MagicMock()

    def test_calls_ar_cancel_session(self):
        ar_client = MagicMock()
        with patch.object(cancel_mod, "frappe") as fm, patch.object(cancel_mod, "_emit_socket_event"), patch(
            _GET_FAC_CLOUD_CLIENT, return_value=ar_client
        ):
            self._mock_frappe(fm)
            cancel_mod.cancel_stream("s1", "m1")

        ar_client.cancel_session.assert_called_once_with("s1")

    def test_no_ar_client_still_returns_normally(self):
        with patch.object(cancel_mod, "frappe") as fm, patch.object(cancel_mod, "_emit_socket_event"), patch(
            _GET_FAC_CLOUD_CLIENT, return_value=None
        ):
            self._mock_frappe(fm)
            result = cancel_mod.cancel_stream("s1", "m1")

        self.assertEqual(result, {"status": "cancel_requested", "session_id": "s1"})

    def test_ar_client_raising_generic_exception_still_returns_normally(self):
        ar_client = MagicMock()
        ar_client.cancel_session.side_effect = Exception("boom")
        with patch.object(cancel_mod, "frappe") as fm, patch.object(cancel_mod, "_emit_socket_event"), patch(
            _GET_FAC_CLOUD_CLIENT, return_value=ar_client
        ):
            self._mock_frappe(fm)
            result = cancel_mod.cancel_stream("s1", "m1")

        self.assertEqual(result, {"status": "cancel_requested", "session_id": "s1"})

    def test_ar_client_timing_out_still_returns_normally(self):
        ar_client = MagicMock()
        ar_client.cancel_session.side_effect = ARTimeoutError("timed out")
        with patch.object(cancel_mod, "frappe") as fm, patch.object(cancel_mod, "_emit_socket_event"), patch(
            _GET_FAC_CLOUD_CLIENT, return_value=ar_client
        ):
            self._mock_frappe(fm)
            result = cancel_mod.cancel_stream("s1", "m1")

        self.assertEqual(result, {"status": "cancel_requested", "session_id": "s1"})

    def test_ar_call_happens_after_local_finalization(self):
        # A shared parent lets us assert the two calls' relative order —
        # not just that both happened. This is the assertion that would
        # catch a future edit hoisting the AR call back above the local
        # HITL-abort finalization.
        ar_client = MagicMock()
        parent = Mock()
        parent.attach_mock(ar_client.cancel_session, "ar_cancel_session")

        with patch.object(cancel_mod, "frappe") as fm, patch.object(
            cancel_mod, "_abort_pending_interactions"
        ) as abort_mock, patch.object(cancel_mod, "_emit_socket_event"), patch(
            _GET_FAC_CLOUD_CLIENT, return_value=ar_client
        ):
            parent.attach_mock(abort_mock, "abort_pending_interactions")
            self._mock_frappe(fm)
            cancel_mod.cancel_stream("s1", "m1")

        call_order = [call[0] for call in parent.mock_calls]
        self.assertLess(
            call_order.index("abort_pending_interactions"),
            call_order.index("ar_cancel_session"),
            f"AR cancel_session must be called after local HITL-abort finalization; got order {call_order}",
        )
