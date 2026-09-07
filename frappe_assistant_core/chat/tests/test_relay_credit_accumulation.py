"""One turn's credit chip must read the same live and after a reload.

A turn that pauses for HITL approval finishes in two AR stream_complete
events: the interrupt cycle and the resume cycle. The row accumulates both;
the live event used to carry only the last cycle, so the chip changed value
on refresh. These tests pin the two halves of that contract.
"""

import json
import unittest

from frappe_assistant_core.chat.api.chat.relay import _merge_model_breakdown


class TestMergeModelBreakdown(unittest.TestCase):
    def test_sums_the_same_model_across_cycles(self):
        cycle1 = [
            {
                "model_id": "opus",
                "role": "orchestrator",
                "credits": 2000.0,
                "input_tokens": 100,
                "output_tokens": 10,
            }
        ]
        cycle2 = [
            {
                "model_id": "opus",
                "role": "orchestrator",
                "credits": 529.0,
                "input_tokens": 50,
                "output_tokens": 5,
            }
        ]
        merged = _merge_model_breakdown(json.dumps(cycle1), cycle2)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["credits"], 2529.0)
        self.assertEqual(merged[0]["input_tokens"], 150)
        self.assertEqual(merged[0]["output_tokens"], 15)

    def test_keeps_helpers_as_separate_rows(self):
        cycle1 = [{"model_id": "opus", "role": "orchestrator", "credits": 2529.0}]
        cycle2 = [
            {"model_id": "haiku", "role": "helper", "credits": 29.0},
            {"model_id": "luna", "role": "helper", "credits": 8.0},
        ]
        merged = _merge_model_breakdown(json.dumps(cycle1), cycle2)
        self.assertEqual(len(merged), 3)
        self.assertEqual(sum(r["credits"] for r in merged), 2566.0)

    def test_same_model_in_both_roles_stays_split(self):
        merged = _merge_model_breakdown(
            json.dumps([{"model_id": "opus", "role": "orchestrator", "credits": 10.0}]),
            [{"model_id": "opus", "role": "helper", "credits": 4.0}],
        )
        self.assertEqual(len(merged), 2)

    def test_first_cycle_has_no_existing_breakdown(self):
        incoming = [{"model_id": "opus", "role": "orchestrator", "credits": 12.0}]
        self.assertEqual(_merge_model_breakdown(None, incoming), incoming)

    def test_survives_corrupt_stored_json(self):
        incoming = [{"model_id": "opus", "role": "orchestrator", "credits": 12.0}]
        self.assertEqual(_merge_model_breakdown("{not json", incoming), incoming)

    def test_empty_inputs(self):
        self.assertEqual(_merge_model_breakdown(None, None), [])


class TestResumeReportsTurnTotal(unittest.TestCase):
    """The resume funnel must send the stored total, not the cycle's own spend."""

    def test_complete_event_reads_back_the_persisted_row(self):
        import inspect

        from frappe_assistant_core.chat.api.chat import relay

        src = inspect.getsource(relay._relay_ar_interrupt_resume)
        self.assertIn("turn_credits", src)
        self.assertIn('"credits_used": turn_credits', src)
        # The quota cache stays an increment of THIS cycle only.
        self.assertIn("_update_subscription_cache(credits_used)", src)
