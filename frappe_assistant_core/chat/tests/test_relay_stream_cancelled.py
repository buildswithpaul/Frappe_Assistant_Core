"""Structural pin for the `stream_cancelled` SSE event — AR's authoritative
confirmation that an agent stopped because it was cancelled (as opposed to
the relay's own poll-based `is_cancelled` detection, which fires before AR
has said anything). Both relay funnels must treat it as a terminal abort,
not as `stream_complete`.

The two funnels finalize an abort differently (see test_relay_cancel_
structure.py's docstring for the full rationale), so this event must be
wired through each funnel's OWN existing abort path:

  * send funnel (_relay_ar_stream): `_handle_stream_aborted`, which
    replaces the row's content wholesale — correct there because its
    `full_response` holds the entire turn.
  * resume funnel (_relay_ar_interrupt_resume): `_persist_resume_cycle`
    (append + aborted guard), NEVER `_handle_stream_aborted` — the resume
    funnel's `full_response` holds only the current resume cycle's text,
    and replacing would erase everything earlier cycles wrote. This is
    the same regression test_relay_cancel_structure.py pins for the local
    is_cancelled branch; a `stream_cancelled` branch that called the wrong
    helper would reintroduce it just for a different trigger.

Uses AST rather than substring position (same idiom as
test_relay_cancel_structure.py) so the assertions survive reformatting and
target the `stream_cancelled` branch specifically, not any other branch
that happens to call these helpers elsewhere in the function.
"""

from __future__ import annotations

import ast
import inspect
import unittest


def _stream_cancelled_branch(func) -> ast.If:
    """The `elif event_type == "stream_cancelled":` node in `func`'s
    elif chain (an `ast.If` nested in the parent `If`'s `orelse`)."""
    tree = ast.parse(inspect.getsource(func))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "event_type"
            and len(node.test.ops) == 1
            and isinstance(node.test.ops[0], ast.Eq)
            and len(node.test.comparators) == 1
            and isinstance(node.test.comparators[0], ast.Constant)
            and node.test.comparators[0].value == "stream_cancelled"
        ):
            return node
    raise AssertionError(f'no `elif event_type == "stream_cancelled":` branch found in {func.__name__}')


def _calls_in_branch(branch: ast.If, func_name: str) -> list[ast.Call]:
    return [
        node
        for stmt in branch.body
        for node in ast.walk(stmt)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == func_name
    ]


class TestBothFunnelsHandleStreamCancelled(unittest.TestCase):
    def test_send_funnel_has_a_stream_cancelled_branch(self):
        from frappe_assistant_core.chat.api.chat import relay

        # Raises AssertionError (failing the test) if the branch is absent.
        _stream_cancelled_branch(relay._relay_ar_stream)

    def test_resume_funnel_has_a_stream_cancelled_branch(self):
        from frappe_assistant_core.chat.api.chat import relay

        _stream_cancelled_branch(relay._relay_ar_interrupt_resume)

    def test_send_funnel_stream_cancelled_branch_finalizes_via_handle_stream_aborted(self):
        # The send funnel's full_response holds the whole turn, so replace
        # semantics (_handle_stream_aborted) are correct here — same helper
        # its own is_cancelled branch already uses.
        from frappe_assistant_core.chat.api.chat import relay

        branch = _stream_cancelled_branch(relay._relay_ar_stream)
        self.assertTrue(
            _calls_in_branch(branch, "_handle_stream_aborted"),
            "send funnel's stream_cancelled branch must call _handle_stream_aborted",
        )

    def test_resume_funnel_stream_cancelled_branch_finalizes_via_persist_resume_cycle(self):
        from frappe_assistant_core.chat.api.chat import relay

        branch = _stream_cancelled_branch(relay._relay_ar_interrupt_resume)
        self.assertTrue(
            _calls_in_branch(branch, "_persist_resume_cycle"),
            "resume funnel's stream_cancelled branch must call _persist_resume_cycle",
        )

    def test_resume_funnel_stream_cancelled_branch_does_not_call_handle_stream_aborted(self):
        # Calling the send funnel's replace-semantics helper here would
        # erase every earlier resume cycle's text — the exact regression
        # test_relay_cancel_structure.py already pins for the local
        # is_cancelled branch, reintroduced here for a different trigger.
        from frappe_assistant_core.chat.api.chat import relay

        branch = _stream_cancelled_branch(relay._relay_ar_interrupt_resume)
        self.assertFalse(
            _calls_in_branch(branch, "_handle_stream_aborted"),
            "resume funnel's stream_cancelled branch must NOT call _handle_stream_aborted "
            "(replace semantics; belongs to the send funnel only)",
        )


if __name__ == "__main__":
    unittest.main()
