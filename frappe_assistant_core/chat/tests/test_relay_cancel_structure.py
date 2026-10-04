"""Structural pins for the Redis cancel flag in both relay funnels. The
flag lives in frappe.cache(), so every gunicorn worker sees it. Only
the endpoint that accepts a turn clears it (pinned at runtime by
test_early_stop_is_honoured.py), and a funnel only reads it: once before
it contacts AR, then between events. A funnel that cleared it again, at
its top or in its `finally`, would erase a Stop pressed while it waited
in the relay pool, or the next turn's Stop. Nothing at runtime marks the
difference until a stopped turn runs and bills, so only a source-level
check catches a future edit that adds the call back.

Also pins which finalizer each funnel's cancellation branches call —
the check above the event loop, the local `if is_cancelled(session_id):`
poll inside it and the `elif event_type == "stream_cancelled":` branch
that reacts to AR's own authoritative cancel confirmation. The send
funnel's `full_response` holds the whole turn, so its branches must call
`_handle_stream_aborted` (replace semantics). The resume funnel's
`full_response` holds only the current resume cycle, so its branches in
the loop must call `_persist_resume_cycle` (append semantics) and never
`_handle_stream_aborted` — using the replace helper there would erase
every earlier resume cycle's text. Its check above the loop runs before
anything of the resume has, so it stops the paused turn exactly as
cancel_stream does during the pause (`_abort_pending_interactions`).
Each branch gets its own scoped assertion (not a whole-function scan) so
a mutation in one branch can't hide behind a correct call in the other.

Uses AST rather than substring position (inspect.getsource + assertIn,
the pattern in test_relay_event_passthrough.py / test_relay_workflow_
created.py) because ordering matters here, not just presence, and
substring position is brittle under reformatting.
"""

from __future__ import annotations

import ast
import inspect
import unittest


def _call_linenos(tree: ast.AST, func_name: str) -> list[int]:
    """Line numbers of every call to a bare-name function, anywhere in
    the tree (including inside try/for/if bodies)."""
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == func_name
    ]


def _stream_iter_for_linenos(tree: ast.AST) -> list[int]:
    """Line numbers of `for event in stream_iter:`-shaped loops."""
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.For) and isinstance(node.iter, ast.Name) and node.iter.id == "stream_iter"
    ]


def _attr_call_linenos(tree: ast.AST, attr: str) -> list[int]:
    """Line numbers of every `<anything>.attr(...)` call in the tree."""
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == attr
    ]


def _is_cancelled_ifs(func) -> tuple[list[ast.If], int]:
    """Every `if is_cancelled(...):` node in func, in source order, and the
    line of func's `for event in stream_iter:` loop."""
    tree = ast.parse(inspect.getsource(func))
    checks = sorted(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Call)
            and isinstance(node.test.func, ast.Name)
            and node.test.func.id == "is_cancelled"
        ),
        key=lambda node: node.lineno,
    )
    return checks, min(_stream_iter_for_linenos(tree))


def _is_cancelled_branch(func) -> ast.If:
    """The `if is_cancelled(session_id):` poll at the top of func's event loop."""
    checks, loop_line = _is_cancelled_ifs(func)
    for node in checks:
        if node.lineno > loop_line:
            return node
    raise AssertionError(f"no `if is_cancelled(...):` poll found in {func.__name__}'s event loop")


def _pre_start_check(func) -> ast.If:
    """The `if is_cancelled(session_id):` check above func's event loop."""
    checks, loop_line = _is_cancelled_ifs(func)
    for node in checks:
        if node.lineno < loop_line:
            return node
    raise AssertionError(f"no `if is_cancelled(...):` check found above {func.__name__}'s event loop")


def _stream_cancelled_branch(func) -> ast.If:
    """The `elif event_type == "stream_cancelled":` node in func's elif
    chain (an `ast.If` nested in the parent `If`'s `orelse`)."""
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
    """Calls to a bare-name function within `branch`'s own body only —
    not any sibling/nested branch reached via the same `If` node's
    `orelse` chain."""
    return [
        node
        for stmt in branch.body
        for node in ast.walk(stmt)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == func_name
    ]


class TestCancelWiringPresentAndOrderedInBothFunnels(unittest.TestCase):
    def _tree(self, func) -> ast.AST:
        return ast.parse(inspect.getsource(func))

    def test_neither_funnel_clears_the_cancel_flag(self):
        from frappe_assistant_core.chat.api.chat import relay

        for func in (relay._relay_ar_stream, relay._relay_ar_interrupt_resume):
            with self.subTest(funnel=func.__name__):
                tree = self._tree(func)
                self.assertFalse(
                    _call_linenos(tree, "clear_cancel") + _call_linenos(tree, "clear"),
                    "only the endpoint that accepts a turn clears the flag: a relay-side "
                    "clear erases a Stop pressed while the relay waited to start, or, "
                    "from its finally, the next turn's Stop",
                )

    def test_both_funnels_check_the_flag_before_they_call_ar(self):
        from frappe_assistant_core.chat.api.chat import relay

        for func in (relay._relay_ar_stream, relay._relay_ar_interrupt_resume):
            with self.subTest(funnel=func.__name__):
                self.assertLess(
                    _pre_start_check(func).lineno,
                    min(_attr_call_linenos(self._tree(func), "stream_chat")),
                    "a Stop pressed after the endpoint accepted the turn, before the relay "
                    "started, must stop it before AR runs (and bills) it",
                )

    def test_send_funnel_polls_is_cancelled(self):
        from frappe_assistant_core.chat.api.chat import relay

        tree = self._tree(relay._relay_ar_stream)
        self.assertTrue(_call_linenos(tree, "is_cancelled"), "_relay_ar_stream must call is_cancelled")

    def test_resume_funnel_polls_is_cancelled(self):
        from frappe_assistant_core.chat.api.chat import relay

        tree = self._tree(relay._relay_ar_interrupt_resume)
        self.assertTrue(
            _call_linenos(tree, "is_cancelled"), "_relay_ar_interrupt_resume must call is_cancelled"
        )

    def _assert_branch_finalizes_via(
        self, branch: ast.If, expected: str, forbidden: str, reason: str
    ) -> None:
        """Shared shape for the six funnel x branch finalizer pins below:
        each cancellation branch must call its funnel's correct helper and
        must not call the other funnel's helper."""
        self.assertTrue(_calls_in_branch(branch, expected), f"branch must call {expected}")
        self.assertFalse(
            _calls_in_branch(branch, forbidden),
            f"branch must NOT call {forbidden} ({reason})",
        )

    def test_resume_funnel_local_poll_branch_uses_append_aware_persist_not_replace_helper(self):
        # _handle_stream_aborted replaces a row's content wholesale — correct
        # for the send funnel, where full_response holds the whole turn, but
        # wrong here: the resume funnel's full_response holds only the
        # current resume cycle's text, and one logical turn can span several
        # cycles. Calling it from this funnel's cancellation branch is
        # exactly the content-clobbering regression fixed by
        # _persist_resume_cycle — this pins the call site, not just the
        # helper's own append-and-guard behavior (already pinned by
        # test_relay_resume_abort_persistence.py).
        from frappe_assistant_core.chat.api.chat import relay

        branch = _is_cancelled_branch(relay._relay_ar_interrupt_resume)
        self._assert_branch_finalizes_via(
            branch,
            "_persist_resume_cycle",
            "_handle_stream_aborted",
            "replace semantics; belongs to the send funnel only",
        )

    def test_resume_funnel_stream_cancelled_branch_uses_append_aware_persist_not_replace_helper(self):
        # Same invariant as the local-poll branch above, pinned separately:
        # AR's own authoritative stream_cancelled confirmation must also
        # finalize through the append-aware helper, not the send funnel's
        # replace helper — a mutation scoped to just this branch can't hide
        # behind the local-poll branch calling the right thing.
        from frappe_assistant_core.chat.api.chat import relay

        branch = _stream_cancelled_branch(relay._relay_ar_interrupt_resume)
        self._assert_branch_finalizes_via(
            branch,
            "_persist_resume_cycle",
            "_handle_stream_aborted",
            "replace semantics; belongs to the send funnel only",
        )

    def test_send_funnel_local_poll_branch_uses_replace_helper(self):
        # Mirror of the resume-funnel pins: the send funnel's full_response
        # holds the WHOLE turn, so replace semantics (_handle_stream_aborted)
        # are correct here, and calling the resume funnel's append-only
        # helper instead would silently produce a row with no content at all
        # (no existing row to append onto, on a fresh send).
        from frappe_assistant_core.chat.api.chat import relay

        branch = _is_cancelled_branch(relay._relay_ar_stream)
        self._assert_branch_finalizes_via(
            branch,
            "_handle_stream_aborted",
            "_persist_resume_cycle",
            "append semantics; belongs to the resume funnel only",
        )

    def test_send_funnel_pre_start_check_uses_replace_helper(self):
        # Before AR is called the turn has no row: _handle_stream_aborted with
        # no AR message_id writes the Stop on a row of its own (tier 3).
        from frappe_assistant_core.chat.api.chat import relay

        self._assert_branch_finalizes_via(
            _pre_start_check(relay._relay_ar_stream),
            "_handle_stream_aborted",
            "_persist_resume_cycle",
            "append semantics; belongs to the resume funnel only",
        )

    def test_resume_funnel_pre_start_check_stops_the_pause_as_it_stands(self):
        # Nothing of the resume has run: the paused turn's pending cards become
        # aborted and it gets the marker, as cancel_stream does during a pause.
        # The replace helper would overwrite the paused turn's text.
        from frappe_assistant_core.chat.api.chat import relay

        self._assert_branch_finalizes_via(
            _pre_start_check(relay._relay_ar_interrupt_resume),
            "_abort_pending_interactions",
            "_handle_stream_aborted",
            "replace semantics would overwrite the paused turn",
        )

    def test_send_funnel_stream_cancelled_branch_uses_replace_helper(self):
        # Same invariant as the local-poll branch above, pinned separately
        # for AR's own authoritative stream_cancelled confirmation.
        from frappe_assistant_core.chat.api.chat import relay

        branch = _stream_cancelled_branch(relay._relay_ar_stream)
        self._assert_branch_finalizes_via(
            branch,
            "_handle_stream_aborted",
            "_persist_resume_cycle",
            "append semantics; belongs to the resume funnel only",
        )


if __name__ == "__main__":
    unittest.main()
