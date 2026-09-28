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

    def test_mark_names_the_request_it_stops(self):
        cache = MagicMock()
        with patch.object(cancel_mod, "frappe") as fm:
            fm.cache.return_value = cache
            cancel_mod.mark_cancelled("s1", "req-7")
            cache.set_value.assert_called_once_with("fac_cancel:s1", "turn:req-7", expires_in_sec=120)

    def test_clear_keeps_a_stop_that_names_the_accepted_request(self):
        cache = MagicMock()
        with patch.object(cancel_mod, "frappe") as fm:
            fm.cache.return_value = cache
            cache.get_value.return_value = "turn:req-7"
            cancel_mod.clear("s1", keep_turn="req-7")
            cache.get_value.assert_called_once_with("fac_cancel:s1", expires=True)
            cache.delete_value.assert_not_called()

    def test_clear_drops_a_stop_that_names_another_request_or_none(self):
        for flag in ("turn:req-6", "1", None):
            with self.subTest(flag=flag):
                cache = MagicMock()
                with patch.object(cancel_mod, "frappe") as fm:
                    fm.cache.return_value = cache
                    cache.get_value.return_value = flag
                    cancel_mod.clear("s1", keep_turn="req-7")
                    cache.delete_value.assert_called_once_with("fac_cancel:s1")

    def test_an_id_at_the_length_limit_names_its_request(self):
        at_limit = "r" * cancel_mod.CLIENT_TURN_ID_MAX_LENGTH
        cache = MagicMock()
        with patch.object(cancel_mod, "frappe") as fm:
            fm.cache.return_value = cache
            cache.get_value.return_value = f"turn:{at_limit}"
            cancel_mod.mark_cancelled("s1", at_limit)
            cancel_mod.clear("s1", keep_turn=at_limit)
        cache.set_value.assert_called_once_with("fac_cancel:s1", f"turn:{at_limit}", expires_in_sec=120)
        cache.delete_value.assert_not_called()

    def test_an_id_over_the_length_limit_names_no_request(self):
        """Its Stop still stops, as an unnamed one, and its accept keeps nothing."""
        too_long = "r" * (cancel_mod.CLIENT_TURN_ID_MAX_LENGTH + 1)
        cache = MagicMock()
        with patch.object(cancel_mod, "frappe") as fm:
            fm.cache.return_value = cache
            cache.get_value.return_value = f"turn:{too_long}"
            cancel_mod.mark_cancelled("s1", too_long)
            cancel_mod.clear("s1", keep_turn=too_long)
        cache.set_value.assert_called_once_with("fac_cancel:s1", "1", expires_in_sec=120)
        cache.get_value.assert_not_called()
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

    def test_names_the_request_the_stop_is_for(self):
        with patch.object(cancel_mod, "frappe") as fm, patch.object(cancel_mod, "_emit_socket_event"), patch(
            _GET_FAC_CLOUD_CLIENT, return_value=None
        ):
            self._mock_frappe(fm)
            cancel_mod.cancel_stream("s1", "m1", client_turn_id="req-7")

        fm.cache.return_value.set_value.assert_called_once_with(
            "fac_cancel:s1", "turn:req-7", expires_in_sec=120
        )

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

    def test_stream_cancel_requested_names_ar_id_when_the_finalizer_found_one(self):
        """The optimistic stream_cancel_requested ping must name AR's own id
        for the turn, not the caller's, when _abort_pending_interactions
        resolved a row: the caller's id can be a client-side uuid another
        client watching the same session has never seen."""
        emitted = []
        with patch.object(cancel_mod, "frappe") as fm, patch.object(
            cancel_mod, "_abort_pending_interactions", return_value="ar-real-id"
        ), patch.object(
            cancel_mod, "_emit_socket_event", side_effect=lambda _sid, payload: emitted.append(payload)
        ), patch(_GET_FAC_CLOUD_CLIENT, return_value=None):
            self._mock_frappe(fm)
            cancel_mod.cancel_stream("s1", "client-side-uuid")

        ping = next(p for p in emitted if p["event"] == "stream_cancel_requested")
        self.assertEqual(ping["message_id"], "ar-real-id")

    def test_stream_cancel_requested_falls_back_to_the_callers_id_when_nothing_resolved(self):
        """No row applied (a Stop before any turn has a row, or one that
        already finished): the ping still names whatever the caller sent,
        the same as before this id was ever cross-checked against a row."""
        emitted = []
        with patch.object(cancel_mod, "frappe") as fm, patch.object(
            cancel_mod, "_abort_pending_interactions", return_value=None
        ), patch.object(
            cancel_mod, "_emit_socket_event", side_effect=lambda _sid, payload: emitted.append(payload)
        ), patch(_GET_FAC_CLOUD_CLIENT, return_value=None):
            self._mock_frappe(fm)
            cancel_mod.cancel_stream("s1", "client-side-uuid")

        ping = next(p for p in emitted if p["event"] == "stream_cancel_requested")
        self.assertEqual(ping["message_id"], "client-side-uuid")

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
