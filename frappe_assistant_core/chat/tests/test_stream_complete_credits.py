"""Structural pin for `credits_used` on the `stream_complete` payload.

The header credit meter scopes itself to whichever allowance governs the
caller: a member with an individual cap is metered against that cap, not
against the team pool. `quota_used`/`quota_total` on this event are
tenant-wide, so they cannot move a capped member's meter — only this
turn's own cost can. Without `credits_used` on the wire, a capped member's
meter freezes for the whole session and only corrects on a page reload.

`useStreaming.js` already reads `data.credits_used` off this event, so
until it is emitted that read silently resolves to `undefined`.

Pinned by AST (same idiom as test_relay_stream_cancelled.py) so the
assertion survives reformatting and targets the completion payload
specifically, rather than any dict that happens to mention credits.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
import unittest


def _payload_keys(dict_node: ast.Dict) -> set[str]:
    return {k.value for k in dict_node.keys if isinstance(k, ast.Constant)}


def _complete_event_payload(func) -> ast.Dict:
    """The `complete_event = {...}` dict literal built inside `func`."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "complete_event":
                    return node.value
    raise AssertionError(f"no `complete_event = {{...}}` literal found in {func.__name__}")


class TestStreamCompleteCarriesTurnCost(unittest.TestCase):
    def test_send_funnel_emits_credits_used(self):
        from frappe_assistant_core.chat.api.chat import relay

        payload = _complete_event_payload(relay._relay_ar_stream)
        self.assertIn(
            "credits_used",
            _payload_keys(payload),
            "send funnel's stream_complete must carry this turn's cost so a "
            "capped member's meter can advance",
        )

    def test_resume_funnel_emits_credits_used(self):
        from frappe_assistant_core.chat.api.chat import relay

        payload = _complete_event_payload(relay._relay_ar_interrupt_resume)
        self.assertIn(
            "credits_used",
            _payload_keys(payload),
            "resume funnel's stream_complete must carry this turn's cost — a "
            "resumed turn bills the same member as the send funnel",
        )

    def test_tenant_wide_counters_remain_on_the_web_payloads(self):
        # credits_used is additive: the pooled-member path still meters off
        # the tenant-wide snapshot, so removing these would break it.
        from frappe_assistant_core.chat.api.chat import relay

        for func in (relay._relay_ar_stream, relay._relay_ar_interrupt_resume):
            keys = _payload_keys(_complete_event_payload(func))
            self.assertIn("quota_used", keys, f"{func.__name__} must keep quota_used")
            self.assertIn("quota_total", keys, f"{func.__name__} must keep quota_total")


if __name__ == "__main__":
    unittest.main()
