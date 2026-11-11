"""A worker that exits gives its running relays a deadline, then records them as interrupted."""

import json
import subprocess
import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.chat.api.chat import live_turn, relay, relay_shutdown
from frappe_assistant_core.tests.base_test import BaseAssistantTest

GRACE_SECONDS = relay_shutdown.GRACE_SECONDS
MODULE_PATH = Path(relay_shutdown.__file__)

# A worker process as gunicorn leaves it: a relay pool created first, the shutdown hook installed
# after it, a relay still running, then the interpreter exits.
SCRIPT = f"""
import importlib.util, threading, time
from concurrent.futures import ThreadPoolExecutor

spec = importlib.util.spec_from_file_location("relay_shutdown", {str(MODULE_PATH)!r})
relay_shutdown = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relay_shutdown)

pool = ThreadPoolExecutor(max_workers=2)
relay_shutdown.install()
relay_shutdown.install()
running = threading.Event()

def relay():
    running.set()
    while not relay_shutdown.should_give_up():
        time.sleep(0.05)

pool.submit(relay)
running.wait()
"""


def _event(name, **data):
    return {"event": name, "data": data}


class TestRelayShutdown(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.sid = f"shutdown-{frappe.generate_hash(length=8)}"

    def tearDown(self):
        relay_shutdown._draining.clear()
        relay_shutdown._deadline = None
        live_turn.clear(self.sid)
        super().tearDown()

    def _drain(self, grace):
        # Interpreter exit calls _begin_drain in production; grace sets where the deadline falls.
        with patch.object(relay_shutdown, "_grace", return_value=grace):
            relay_shutdown._begin_drain()

    def _stream(self, grace):
        yield _event("stream_start", message_id="m-shut")
        yield _event("stream_chunk", content="Half an ans")
        self._drain(grace)
        yield _event("heartbeat")
        yield _event("stream_chunk", content="wer.")
        yield _event("stream_complete", full_response="Half an answer.", message_id="m-shut")

    def _run(self, events, *, resume=False):
        client = MagicMock()
        client.stream_chat.return_value = events
        self.client = client
        published = []

        def collect(event, message, **kw):
            if event == "faco_message_stream":
                published.append(dict(message))

        turn = live_turn.start(self.sid)
        with ExitStack() as stack:
            enter = stack.enter_context
            enter(
                patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client)
            )
            # set_user is stubbed because the real one resets the running session.
            for name in ("init", "connect", "set_user", "destroy"):
                enter(patch(f"frappe.{name}"))
            enter(patch.object(relay, "is_cancelled", return_value=False))
            enter(patch.object(relay, "_update_subscription_cache"))
            enter(
                patch(
                    "frappe_assistant_core.chat.quota_cache.get_quota_snapshot",
                    return_value={"quota_used": 0, "quota_total": 100},
                )
            )
            enter(patch("frappe.publish_realtime", side_effect=collect))
            if resume:
                # resume_interrupt parses the client's JSON before queueing the relay.
                relay._relay_ar_interrupt_resume(
                    self.sid,
                    [{"interruptId": "i1", "response": "approve"}],
                    "Administrator",
                    frappe.local.site,
                    message_id="m-shut",
                    live_turn_token=turn,
                )
            else:
                relay._relay_ar_stream(
                    self.sid,
                    full_prompt="hi",
                    original_message="hi",
                    context=None,
                    message_name=None,
                    user="Administrator",
                    site=frappe.local.site,
                    live_turn_token=turn,
                )
        return published

    def _row(self):
        return frappe.db.get_value(
            "FAC Chat Message",
            {"session_id": self.sid, "role": "assistant"},
            ["content", "errored", "blocks"],
            as_dict=True,
        )

    def test_relay_gives_up_after_the_deadline_and_marks_errored(self):
        published = self._run(self._stream(grace=0))

        events = [p["event"] for p in published]
        self.assertNotIn("stream_complete", events)
        error = published[-1]
        self.assertEqual(error["event"], "stream_error")
        self.assertEqual(error["error_code"], "TURN_INTERRUPTED")
        self.assertEqual(error["message_id"], "m-shut")
        self.assertIn("Retry", error["error"])
        row = self._row()
        self.assertEqual(row.errored, 1)
        self.assertEqual(row.content, "Half an ans")
        self.assertEqual(json.loads(row.blocks)[-1]["content"], "Half an ans")
        self.assertIsNone(live_turn.get(self.sid))

    def test_relay_finishes_normally_before_the_deadline(self):
        published = self._run(self._stream(grace=GRACE_SECONDS))

        self.assertEqual(published[-1]["event"], "stream_complete")
        self.assertNotIn("stream_error", [p["event"] for p in published])
        self.assertFalse(self._row().errored)

    def test_a_resume_gives_up_after_the_deadline(self):
        published = self._run(self._stream(grace=0), resume=True)

        self.assertEqual(published[-1]["event"], "stream_error")
        self.assertEqual(published[-1]["error_code"], "TURN_INTERRUPTED")
        self.assertNotIn("stream_complete", [p["event"] for p in published])
        self.assertIsNone(live_turn.get(self.sid))

    def test_a_relay_dequeued_while_draining_never_calls_ar(self):
        # The pool joins at exit by running what is still queued; draining began before it ran.
        self._drain(GRACE_SECONDS)
        published = self._run(iter([]))

        self.client.stream_chat.assert_not_called()
        self.assertEqual(published[-1]["error_code"], "TURN_INTERRUPTED")
        self.assertEqual(self._row().errored, 1)
        self.assertIsNone(live_turn.get(self.sid))

    def test_not_draining_never_gives_up(self):
        self.assertFalse(relay_shutdown.should_give_up())
        self._drain(GRACE_SECONDS)
        self.assertTrue(relay_shutdown.is_draining())
        self.assertFalse(relay_shutdown.should_give_up())

    def test_site_config_sets_the_grace(self):
        with patch.dict(frappe.local.conf, {"faco_relay_shutdown_grace": 45}):
            self.assertEqual(relay_shutdown._read_grace(), 45)
        self.assertEqual(relay_shutdown._read_grace(), GRACE_SECONDS)

    def test_interpreter_exit_drains_a_running_relay(self):
        # Real boundary: a subprocess imports relay_shutdown, starts a pool task that loops until
        # should_give_up(), installs, then exits; it must exit within GRACE_SECONDS, not hang on join.
        proc = subprocess.run(
            [sys.executable, "-I", "-c", SCRIPT],
            timeout=GRACE_SECONDS + 5,
            env={"FACO_GRACE": "3"},
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
