"""A script's steps travel from the runtime's event onto the tool block and to the browser."""

import json
from unittest.mock import patch

from frappe_assistant_core.chat.api.block_builder import (
    MAX_SCRIPT_STEPS,
    MAX_SCRIPT_STEPS_CHARS,
    BlockBuilder,
    clean_script_steps,
)
from frappe_assistant_core.chat.api.chat import relay
from frappe_assistant_core.tests.base_test import BaseAssistantTest

# What the runtime sends for one call a script made (assistant_runtime agent/script_steps.py).
STEP = {
    "tool_name": "list_documents",
    "input": {"doctype": "Company", "limit": 5},
    "status": "success",
    "duration_ms": 42,
    "count": 3,
    "returned": 3,
    "result": {"data": [{"name": "Northwind"}], "total_count": 3},
    "error": None,
}


def _relay(data: dict) -> tuple[dict, list]:
    """One steps event through the relay, as both loops hand it over: the block and what was emitted."""
    builder = BlockBuilder()
    builder.add_tool_call_start("tu-1", "run_script", {"code": "print(3)"})
    with patch.object(relay, "_emit_socket_event", autospec=True) as emit:
        handled = relay._dispatch_relay_event(
            "tool_call_steps", {"tool_id": "tu-1", **data}, "s1", builder, ar_message_id="m1"
        )
    assert handled
    return builder.snapshot()[0], [call.args[1] for call in emit.call_args_list]


class TestScriptSteps(BaseAssistantTest):
    def test_a_scripts_steps_are_stored_on_its_block_and_sent_to_the_browser(self):
        block, sent = _relay({"steps": [STEP], "calls": 1})

        self.assertEqual(block["steps"], [STEP])
        self.assertNotIn("calls", block)
        self.assertEqual(
            sent,
            [
                {
                    "event": "tool_call_steps",
                    "session_id": "s1",
                    "message_id": "m1",
                    "tool_id": "tu-1",
                    "steps": [STEP],
                }
            ],
        )
        # The script is still running as far as the block knows: its result comes in its own event.
        self.assertEqual(block["status"], "running")

    def test_the_steps_survive_the_result_that_follows(self):
        builder = BlockBuilder()
        builder.add_tool_call_start("tu-1", "run_script", {"code": "print(3)"})
        with patch.object(relay, "_emit_socket_event", autospec=True):
            relay._dispatch_relay_event(
                "tool_call_steps", {"tool_id": "tu-1", "steps": [STEP]}, "s1", builder
            )
        builder.add_tool_call_result("tu-1", [{"text": "3"}], "success")

        (block,) = builder.snapshot()
        self.assertEqual((block["status"], block["steps"]), ("success", [STEP]))

    def test_a_script_that_looped_past_the_list_says_how_many_calls_it_made(self):
        block, sent = _relay({"steps": [STEP], "calls": 300})

        self.assertEqual((block["calls"], sent[0]["calls"]), (300, 300))

    def test_malformed_steps_and_steps_for_an_unknown_call_change_nothing(self):
        for steps in ("not a list", [], [None, 7, {"input": {}}], {"tool_name": "x"}, None):
            block, sent = _relay({"steps": steps})

            self.assertNotIn("steps", block, steps)
            self.assertEqual(sent, [], steps)
        block, sent = _relay({"tool_id": "tu-other", "steps": [STEP]})
        self.assertNotIn("steps", block)
        self.assertEqual(sent, [])

    def test_only_known_keys_and_the_first_steps_are_kept(self):
        many = [{**STEP, "secret": "x", "duration_ms": i} for i in range(MAX_SCRIPT_STEPS + 5)]

        cleaned = clean_script_steps(many)

        self.assertEqual(len(cleaned), MAX_SCRIPT_STEPS)
        self.assertEqual(set(cleaned[0]), set(STEP))
        self.assertEqual(cleaned[-1]["duration_ms"], MAX_SCRIPT_STEPS - 1)

    def test_steps_too_large_for_a_socket_frame_keep_their_counts_only(self):
        # A runtime that does not hold the size limit this one does.
        big = [{**STEP, "result": {"data": [{"remarks": "x" * 5000}]}} for _ in range(10)]

        cleaned = clean_script_steps(big)

        self.assertLessEqual(len(json.dumps(cleaned)), MAX_SCRIPT_STEPS_CHARS)
        self.assertEqual(
            [(step["count"], step["result"], step["input"]) for step in cleaned], [(3, None, {})] * 10
        )

    def test_a_run_in_another_script_is_measured_as_the_runtime_measures_it(self):
        # Twelve lookups of five Hindi records: under the runtime's 16,000 characters, and several
        # times that if each character were counted as the six of its JSON escape.
        rows = [{"name": f"SINV-{i}", "remarks": "ग्राहक को माल भेजा गया " * 8} for i in range(5)]
        run = [{**STEP, "result": {"data": rows}} for _ in range(12)]
        self.assertLess(len(json.dumps(run, ensure_ascii=False)), 16000)
        self.assertGreater(len(json.dumps(run)), MAX_SCRIPT_STEPS_CHARS)

        self.assertEqual(clean_script_steps(run), run)

    def test_a_failed_step_keeps_its_reason_when_the_previews_are_dropped(self):
        failed = {**STEP, "status": "error", "result": None, "error": "No permission for Salary Slip"}
        big = [{**STEP, "result": {"data": [{"remarks": "x" * 5000}]}} for _ in range(10)]

        cleaned = clean_script_steps([failed, *big])

        self.assertEqual(cleaned[0]["error"], "No permission for Salary Slip")
        self.assertEqual(cleaned[1]["result"], None)

    def test_a_number_json_cannot_hold_never_reaches_the_block_or_the_browser(self):
        # NaN parses in Python and breaks JSON.parse in the browser and the JSON column in MariaDB.
        cleaned = clean_script_steps([{**STEP, "result": {"data": [{"margin": float("nan")}]}}])

        self.assertEqual(cleaned[0]["result"], None)
        self.assertEqual(cleaned[0]["count"], 3)
        json.dumps(cleaned, allow_nan=False)
        self.assertEqual(clean_script_steps([{**STEP, "count": float("inf")}]), [])
