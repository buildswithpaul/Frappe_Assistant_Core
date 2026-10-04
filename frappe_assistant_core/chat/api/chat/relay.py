# Frappe Assistant Core - AR ↔ FACO Stream Relay
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Background-thread relay from AR's SSE stream to the SPA via Socket.IO.

These functions run in the bounded ``_relay_pool`` defined in
``messages``. They re-establish a Frappe context on entry and tear it
down on exit. Not whitelisted endpoints.

Every payload names its turn: ``message_id`` is the id AR's ``stream_start``
gave the turn (``ar_message_id``), and None until the relay has handled that
``stream_start``. After a Stop, the stopped turn's late events share the room
with the next turn's, and this id is how a client tells them apart.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import NamedTuple

import frappe
from frappe import _

from .._helpers import (
    _not_registered_error,
    _safe_error,
)


def _sdk_composer_kwargs(stream_chat, web_search, thinking_enabled, reasoning_effort) -> dict:
    """Keyword args for the SDK's stream_chat, omitting reasoning_effort when
    the installed SDK predates it (it would raise TypeError on an unknown kwarg).
    FAC pins the SDK exactly, so this only matters for editable / mispinned installs."""
    import inspect

    kwargs = {"web_search": web_search, "thinking_enabled": thinking_enabled}
    try:
        accepts = "reasoning_effort" in inspect.signature(stream_chat).parameters
    except (TypeError, ValueError):
        accepts = False
    if accepts and reasoning_effort is not None:
        kwargs["reasoning_effort"] = reasoning_effort
    return kwargs


def _set_faco_message_with_retry(name: str, updates: dict, *, attempts: int = 3) -> bool:
    """Update a FACO Message row, retrying on InnoDB record-changed (1020).

    The streaming relay and the cancel path both write to the same row
    (blocks/content). When the user presses Stop while a resume is mid-
    flight, those two writers can race; MariaDB raises
    ``QueryDeadlockError(1020, "Record has changed since last read")``
    from its optimistic concurrency check. Retrying with a fresh read
    resolves it without losing data: the second writer simply re-applies
    its updates on top of the first writer's row.

    Returns True on success, False if all attempts failed.
    """
    for attempt in range(attempts):
        try:
            frappe.db.set_value("FAC Chat Message", name, updates)
            frappe.db.commit()  # nosemgrep: frappe-manual-commit — background thread / streaming context
            return True
        except frappe.QueryDeadlockError:
            frappe.db.rollback()
            if attempt == attempts - 1:
                frappe.log_error(
                    title="FAC Chat Message write contention",
                    message=(
                        f"set_value retry exhausted for {name} after {attempts} attempts. "
                        f"Update keys: {list(updates.keys())}"
                    ),
                )
                return False
            # Brief backoff lets the other writer's transaction commit so
            # the next read sees a stable row.
            time.sleep(0.05 * (attempt + 1))
    return False


class MergedWrite(NamedTuple):
    """What ``_update_faco_message_merged`` did.

    ``written`` is True only when ``merge`` returned fields and they were
    committed: ``updates`` is then exactly what ``merge`` returned and ``row``
    the locked read it was computed from. When ``merge`` chose not to write,
    ``written`` is False, ``updates`` is None and ``row`` is the locked read it
    declined. ``row`` is None when the row does not exist, and when every
    attempt deadlocked (logged).
    """

    written: bool
    updates: dict | None
    row: frappe._dict | None


def _update_faco_message_merged(
    name: str,
    fields: list[str],
    merge: Callable[[frappe._dict | None], dict | None],
    *,
    attempts: int = 3,
) -> MergedWrite:
    """Retry a whole read-merge-write cycle for a FAC Chat Message row, with a locking read.

    ``_set_faco_message_with_retry`` retries a FIXED ``updates`` dict: on a
    deadlock it rolls back and re-applies the SAME computation, which is only
    safe when the caller's write does not depend on the row's current state.
    A finalizer whose write IS a function of the row it just read (cancel.py's
    Stop handler: it merges pending-card and marker updates onto whatever the
    row currently holds) cannot reuse that helper — re-applying a stale merge
    after a deadlock would silently overwrite whatever the other writer
    committed in the gap. This helper re-reads and re-merges on every attempt
    instead of ever re-using a stale computation.

    Each attempt:
      1. Reads the row with ``frappe.db.get_value(..., for_update=True)`` — a
         locking read. Under READ COMMITTED this blocks until any writer
         already holding this row's lock commits or rolls back, then reads
         the latest committed values: never a snapshot the other writer is
         about to overwrite. Under MariaDB's default REPEATABLE READ with
         ``innodb_snapshot_isolation`` (on by default since 11.6.2) the locked
         read instead raises 1020 when the other writer committed after this
         request's snapshot, and only the retry, in a new transaction, reads
         the latest row: the retry below is not dead code.
      2. Calls ``merge(row)``, which inspects that fresh row and returns
         either the dict of fields to write, or ``None`` for "no write
         needed" — a normal outcome (not a failure), so it is never retried.
      3. A dict return is written with ``frappe.db.set_value`` and committed.

    On ``frappe.QueryDeadlockError`` (1020, or a genuine deadlock) from
    either step, the transaction is rolled back and, after a brief backoff,
    the NEXT attempt starts over from a fresh locked read — so a retry can
    never re-apply a merge computed against data another writer has since
    replaced. Any other exception also rolls back, so the locking read's row
    lock is never left held, and then propagates: the caller may swallow it
    and go on to slow work, and until then the other writer would wait on
    that lock.

    Returns a :class:`MergedWrite`. ``written`` is False both when ``merge``
    returned ``None`` and when every attempt deadlocked (logged, with ``row``
    None), so a caller can unpack the result on every path.
    """
    for attempt in range(attempts):
        try:
            row = frappe.db.get_value("FAC Chat Message", name, fields, as_dict=True, for_update=True)
            updates = merge(row)
            if updates is None:
                frappe.db.commit()  # nosemgrep: frappe-manual-commit — release the locking read's row lock; no write needed
                return MergedWrite(False, None, row)
            # A copy: set_value stamps modified/modified_by onto the dict it is given.
            frappe.db.set_value("FAC Chat Message", name, dict(updates))
            frappe.db.commit()  # nosemgrep: frappe-manual-commit — commit before the caller emits stream_aborted; release the row lock before it calls AR
            return MergedWrite(True, updates, row)
        except frappe.QueryDeadlockError:
            frappe.db.rollback()
            if attempt == attempts - 1:
                frappe.log_error(
                    title="FAC Chat Message write contention",
                    message=(
                        f"_update_faco_message_merged retry exhausted for {name} after {attempts} attempts."
                    ),
                )
                return MergedWrite(False, None, None)
            # Brief backoff lets the other writer's transaction commit so
            # the next attempt's locked read sees a stable row.
            time.sleep(0.05 * (attempt + 1))
        except Exception:
            # Not a deadlock: release the locking read's row lock before the
            # error reaches a caller that may swallow it and carry on.
            frappe.db.rollback()
            raise
    return MergedWrite(False, None, None)


from ..block_builder import truncate_result_for_emit  # noqa: E402
from ..chat.cancel import (  # noqa: E402
    ABORT_MARKER_TEXT,
    _abort_pending_interactions,
    append_abort_marker,
    is_cancelled,
)
from ..chat.helpers import (  # noqa: E402
    _emit_socket_event,
    _ensure_assistant_msg,
    _find_assistant_msg_by_message_id,
    _load_turn_blocks,
    _log_conversation,
    _log_stream_error_detail,
    _parse_turn_blocks,
    _update_subscription_cache,
)

# Event types whose handling is identical in both the main stream loop and
# the HITL resume loop. Routing them through one function keeps the loops
# from drifting apart — the resume loop originally had no thinking branch
# at all because it was added to the main loop and never mirrored here.
_SHARED_RELAY_EVENTS = frozenset(
    {
        "context_summarized",
        "model_selected",
        "routing_notice",
        "thinking",
        "thinking_complete",
    }
)

# Events only a running agent emits. A resume keeps its answered cards pending
# until the first of these arrives: before it, AR may be unreachable or may
# refuse the resume after its stream_start (SESSION_BUSY), and it still holds
# the pause. heartbeat, sources and task_updated stay out on purpose: AR can
# emit the last two ahead of a refusal — sources can attach to the first event,
# and the task plan can update, before AR settles on the refusal.
_RESUME_PROGRESS_EVENTS = frozenset(
    {
        "stream_chunk",
        "thinking",
        "thinking_complete",
        "tool_call_start",
        "tool_result",
        "tool_call_result",
        "tool_cancelled",
        "approval_required",
        "workflow_created",
        "stream_complete",
        "stream_cancelled",
    }
)

# Resume refusals that mean the pause is gone for good: its cards can only expire.
_PAUSE_GONE_CODES = frozenset({"INTERRUPT_EXPIRED", "INTERRUPT_NOT_FOUND"})


def _dispatch_relay_event(
    event_type: str, data: dict, session_id: str, block_builder, ar_message_id: str | None = None
) -> bool:
    """Handle a relay event type shared by both loops.

    Returns True if ``event_type`` was recognized and handled (block_builder
    updated + socket event emitted), False otherwise so the caller can fall
    through to its own loop-specific branches. Every payload carries
    ``ar_message_id`` as ``message_id`` (see the module docstring).
    """
    if event_type not in _SHARED_RELAY_EVENTS:
        return False

    if event_type == "context_summarized":
        _emit_socket_event(
            session_id,
            {
                "event": "context_summarized",
                "session_id": session_id,
                "message_id": ar_message_id,
                "message": data.get("message", ""),
            },
        )

    elif event_type == "model_selected":
        _emit_socket_event(
            session_id,
            {
                "event": "model_selected",
                "session_id": session_id,
                "message_id": ar_message_id,
                "mode": data.get("mode"),
                "complexity": data.get("complexity"),
                "task_type": data.get("task_type"),
                "selected": data.get("selected"),
                "tier": data.get("tier"),
                "shortlist_size": data.get("shortlist_size", 0),
                "floor_tier": data.get("floor_tier"),
                "ceiling_tier": data.get("ceiling_tier"),
                "bound_by": data.get("bound_by"),
                "band": data.get("band"),
                "classification_source": data.get("classification_source"),
                "routing": data.get("routing"),
            },
        )

    elif event_type == "routing_notice":
        _emit_socket_event(
            session_id,
            {
                "event": "routing_notice",
                "session_id": session_id,
                "message_id": ar_message_id,
                "code": data.get("code"),
                "tier_used": data.get("tier_used"),
                "tier_wanted": data.get("tier_wanted"),
                "band": data.get("band"),
                "scope": data.get("scope"),
            },
        )

    elif event_type == "thinking":
        block_builder.add_thinking(data.get("content", ""))
        _emit_socket_event(
            session_id,
            {
                "event": "thinking",
                "session_id": session_id,
                "message_id": ar_message_id,
                "content": data.get("content", ""),
            },
        )

    elif event_type == "thinking_complete":
        block_builder.complete_thinking()
        _emit_socket_event(
            session_id,
            {
                "event": "thinking_complete",
                "session_id": session_id,
                "message_id": ar_message_id,
            },
        )

    return True


def _normalize_ar_event(event_type: str, data: dict) -> tuple[str, dict]:
    """Rename an AR event the clients cannot act on into one they can.

    AR refuses a turn it cannot route (every auto-mode model, or the chosen
    model's provider, is at its rate limit) with a lone ``rate_limited`` event
    and no ``stream_error``. The SPA, the Desk widget and the mobile app end a
    turn only on ``stream_complete``, ``stream_error`` or ``stream_aborted``,
    so a dropped ``rate_limited`` left them waiting out their activity
    timeout. Both loops call this first, so the refusal becomes a
    ``stream_error`` coded ``RATE_LIMITED`` and each loop finishes it in its
    own ``stream_error`` branch, like AR's other refusals before a turn
    starts. ``retry_after`` is kept only as a positive number of seconds.
    ``models_checked`` lists internal model ids and is dropped.
    """
    if event_type != "rate_limited":
        return event_type, data
    retry_after = data.get("retry_after")
    if not isinstance(retry_after, (int, float)) or retry_after <= 0:
        retry_after = None
    return "stream_error", {
        "error": data.get("error") or _("The assistant is busy right now. Please try again in a moment."),
        "error_code": "RATE_LIMITED",
        "retry_after": retry_after,
    }


def _persist_session_blob(session_id, user, data, zero_retention, restricted):
    """Store the signed zero-retention blob AR returned on a terminal event.

    The blob is the only copy of conversation state, so it must be stored on
    every terminal event AR carries one on — completion, interruption AND error.
    Skipping the error path silently rewound the conversation to the previous
    turn's state while the transcript kept the partial assistant reply, which is
    what strands a later HITL resume: the pause row survives, but the history it
    resumes against no longer contains the pending tool call.

    ``has_pending_interrupt`` is read straight off AR's own ``interrupted`` flag
    rather than passed in, so the send and resume funnels can never disagree
    about it (the send funnel used to omit it and mark an interrupted turn as
    having no pending interrupt).
    """
    if not zero_retention or restricted or not data.get("session_state"):
        return

    from frappe_assistant_core.chat.doctype.fac_chat_session_state.fac_chat_session_state import (
        FACChatSessionState,
    )

    FACChatSessionState.persist_safe(
        session_id,
        user,
        data["session_state"],
        has_pending_interrupt=bool(data.get("interrupted")),
    )


def _merge_model_breakdown(existing_json, incoming: list | None) -> list:
    """Sum per-model rows across the resume cycles of one logical turn.

    Each cycle reports only its own spend, so the row's stored breakdown has to
    accumulate the same way ``credits_used`` does. Rows are keyed on
    (model_id, role) — the same model can appear as both orchestrator and
    helper within a turn, and those are separate lines on the usage screen.
    """
    merged: dict[tuple, dict] = {}
    for source in (existing_json, incoming):
        if not source:
            continue
        if isinstance(source, str):
            try:
                source = json.loads(source)
            except (ValueError, TypeError):
                continue
        if not isinstance(source, list):
            continue
        for entry in source:
            if not isinstance(entry, dict):
                continue
            key = (entry.get("model_id"), entry.get("role"))
            row = merged.get(key)
            if row is None:
                merged[key] = dict(entry)
                continue
            row["credits"] = round((row.get("credits") or 0) + (entry.get("credits") or 0), 2)
            row["input_tokens"] = (row.get("input_tokens") or 0) + (entry.get("input_tokens") or 0)
            row["output_tokens"] = (row.get("output_tokens") or 0) + (entry.get("output_tokens") or 0)

    return list(merged.values())


def _continued_turn_updates(
    row,
    continuation: str,
    credits_used: float,
    model_breakdown: list | None,
    *,
    tool_calls: list | None = None,
) -> dict:
    """Row updates for a Continue, which appends to its turn rather than replacing it.

    ``row`` is the turn as it stood at the last write (the Continue's start,
    or wherever ``_persist_continued_turn`` rebased it after). ``continuation``
    is the text this relay streamed since then, never AR's ``full_response``:
    AR seeds that with its own copy of the answer, which need not match this
    row's. ``credits_used`` is only this cycle's cost. The row keeps the whole
    turn: the stored text followed directly by ``continuation`` (it resumes
    mid-answer, so no separator), the summed credits, the merged model
    breakdown and every tool call.
    """

    def stored(field):
        return getattr(row, field, None) if row else None

    updates = {
        "content": f"{stored('content') or ''}{continuation}",
        "credits_used": round((stored("credits_used") or 0) + (credits_used or 0), 2),
    }
    if model_breakdown:
        updates["model_breakdown"] = json.dumps(
            _merge_model_breakdown(stored("model_breakdown"), model_breakdown)
        )
    if tool_calls:
        updates["tool_calls"] = json.dumps(_merge_tool_calls(stored("tool_calls"), tool_calls))
    return updates


def _merge_routing_receipt(existing, incoming):
    """Fold a later resume cycle's receipt into the turn's stored one.

    Keeps the FIRST cycle's decision — it chose the model the user actually
    watched stream, and a last-cycle-wins receipt would contradict the chip
    they saw. Only ``cycles`` and ``also_ran`` accumulate. Each AR receipt
    always arrives claiming cycles: 1, because every resume is a fresh
    stream_chat request and AR cannot see the whole turn — this is the only
    hop that can.
    """
    if not incoming:
        return existing
    if isinstance(incoming, str):
        try:
            incoming = json.loads(incoming)
        except (ValueError, TypeError):
            return existing
    if not existing:
        return incoming

    if isinstance(existing, str):
        try:
            existing = json.loads(existing)
        except (ValueError, TypeError):
            return incoming

    merged = dict(existing)
    merged["cycles"] = (existing.get("cycles") or 1) + 1
    # A distinct later model, capped — the panel names the whole-turn list
    # under one honest label rather than "+2 more models ran".
    later_model = incoming.get("selected_model")
    if later_model and later_model != merged.get("selected_model"):
        also_ran = list(merged.get("also_ran") or [])
        if later_model not in also_ran and len(also_ran) < 5:
            also_ran.append(later_model)
        merged["also_ran"] = also_ran
    # The turn's real end state: whether it is still open, and this cycle's
    # own cost, both matter more than the earlier cycle's snapshot.
    merged["incomplete"] = incoming.get("incomplete", merged.get("incomplete"))
    if incoming.get("credits", {}).get("actual") is not None:
        merged["credits"] = incoming["credits"]
    return merged


def _merge_tool_calls(existing_tool_calls_json, new_calls: list | None) -> list:
    """Append this cycle's tool calls onto the turn's stored list.

    Shared by the resume and Continue append paths, so a malformed stored
    value is handled the same way in both: as an empty list rather than a
    crash.
    """
    if not new_calls:
        return []
    try:
        prior = json.loads(existing_tool_calls_json) if existing_tool_calls_json else []
    except (ValueError, TypeError):
        prior = []
    if not isinstance(prior, list):
        prior = []
    return prior + new_calls


def _persist_resume_cycle(
    session_id: str,
    ar_message_id: str | None,
    message_id: str | None,
    full_response: str,
    block_builder,
    collected_tool_calls: list,
    *,
    aborted: bool = False,
    errored: bool = False,
    model_used: str = "",
    model_breakdown: dict | None = None,
    credits_used: float = 0,
    routing: dict | None = None,
) -> str | None:
    """Persist one resume cycle's output onto the turn's existing row.

    Appends to (never replaces) whatever content is already on the row —
    one logical turn can span several resume cycles, and ``full_response``
    here only ever holds the current cycle's text, unlike the send
    funnel's ``full_response`` which holds the whole turn. A cycle that
    ends on a Stop is flagged ``aborted``, one that ends on an error
    ``errored``; either way its text is appended.

    A cycle that is NOT itself finalizing a Stop (a clean finish, or one
    that errored) is a no-op besides logging when the row is already
    ``aborted``: cancel.py's ``_abort_pending_interactions`` may have
    written the "(Stopped by user)" marker onto this same row moments ago,
    and overwriting it here would both lose that marker and, if this
    call's ``full_response`` is older, roll content itself backwards.

    A cycle that IS finalizing a Stop (``aborted=True``) never skips, even
    when the row already reads ``aborted`` — that means cancel.py's own
    Stop handler won the race and marked the row first, from the state it
    read before the approved tool ran and this cycle's text streamed.
    ``block_builder``'s snapshot already carries the real outcome (it was
    resolved onto the turn the moment this cycle saw its first progress
    event), so this write's blocks replace cancel.py's, and the marker is
    applied through the idempotent ``append_abort_marker`` so exactly one
    survives at the true end of the text — after stripping cancel.py's own
    marker suffix first, so it is not sandwiched into the middle.

    That snapshot can still hold a card as ``pending``: AR announces an
    approved tool only once, so when the user presses Stop while it is
    still running, this cycle has seen no more than ``stream_start`` and
    heartbeats, and ``pause_consumed`` never flipped the card. Taking over
    the row with a pending card would put a live Approve/Reject control
    back onto a turn cancel.py already stopped, and approving it would hit
    AR's ``INTERRUPT_NOT_FOUND`` (its pause is gone). So any card still
    ``pending`` in this snapshot is settled ``aborted`` here too, exactly
    as cancel.py settles it, before the marker is applied. A card holding
    a real decision (``approved``/``rejected``/etc.) is left untouched.

    Returns the FAC Chat Message name found for this turn, or None if no
    row exists yet (the caller should fall back to creating one).
    """
    existing_faco_msg = _find_assistant_msg_by_message_id(session_id, ar_message_id or message_id)
    if not existing_faco_msg:
        return None

    row = frappe.db.get_value(
        "FAC Chat Message",
        existing_faco_msg,
        ["content", "tool_calls", "aborted", "credits_used", "model_breakdown", "routing"],
        as_dict=True,
    )
    row_already_aborted = bool(row and row.get("aborted"))
    if row_already_aborted and not aborted:
        frappe.logger("faco.chat.resume").info(
            f"Skipping persist for {existing_faco_msg}: row aborted concurrently"
        )
        return existing_faco_msg

    current_content = (row.content if row else "") or ""
    if row_already_aborted and current_content.endswith(ABORT_MARKER_TEXT):
        # cancel.py's write is being superseded below; strip its marker so
        # it isn't left stranded ahead of this cycle's own text.
        current_content = current_content[: -len(ABORT_MARKER_TEXT)]
    if current_content and full_response:
        updated_content = f"{current_content}\n\n{full_response}"
    else:
        updated_content = current_content or full_response

    blocks_snapshot = block_builder.snapshot()
    if aborted and row_already_aborted:
        # cancel.py's finalizer already ran and marked the row: its marker is
        # the one stripped above, so re-adding it here (idempotent either way)
        # keeps the row at exactly one, now at the end of this cycle's text.
        # Never leave an actionable card behind in a row cancel.py stopped:
        # settle a still-pending card the same way cancel.py would.
        for block in blocks_snapshot:
            if block.get("type") == "interaction" and block.get("status") == "pending":
                block["status"] = "aborted"
                block["result"] = {"message": "Stopped by user"}
        updated_content, blocks_snapshot = append_abort_marker(updated_content, blocks_snapshot)

    # Accumulate credits: a single logical turn can span several resume
    # cycles, each emitting its own credits for just that cycle.
    prior_credits = (row.credits_used if row else 0) or 0
    updates = {
        "content": updated_content,
        "blocks": json.dumps(blocks_snapshot),
        "credits_used": round(prior_credits + credits_used, 2),
    }
    if aborted:
        updates["aborted"] = 1
    if errored:
        updates["errored"] = 1
    if model_used:
        updates["model"] = model_used
    if model_breakdown:
        # Merge, never replace: credits_used below is the whole turn's total, so
        # a breakdown holding only the last cycle would contradict it — the chip
        # and the usage screen would disagree on the same turn.
        updates["model_breakdown"] = json.dumps(
            _merge_model_breakdown(row.model_breakdown if row else None, model_breakdown)
        )
    if collected_tool_calls:
        updates["tool_calls"] = json.dumps(
            _merge_tool_calls(row.tool_calls if row else None, collected_tool_calls)
        )
    if routing is not None:
        merged_routing = _merge_routing_receipt(row.routing if row else None, routing)
        if merged_routing is not None:
            updates["routing"] = json.dumps(merged_routing)

    _set_faco_message_with_retry(existing_faco_msg, updates)
    return existing_faco_msg


def _persist_errored_resume_cycle(
    session_id: str,
    ar_message_id: str | None,
    message_id: str | None,
    full_response: str,
    block_builder,
    collected_tool_calls: list,
) -> None:
    """Record a resume cycle that errored after AR consumed the pause.

    Like a Stop's cycle, it is appended to the turn and the row flagged, here
    ``errored``: the send funnel's partial writer would replace the text the
    turn had before the pause with this cycle's alone. Only a turn with no row
    yet goes to that writer, which creates one.
    """
    if _persist_resume_cycle(
        session_id,
        ar_message_id,
        message_id,
        full_response,
        block_builder,
        collected_tool_calls,
        errored=True,
    ):
        return
    blocks_snapshot = block_builder.snapshot()
    if full_response or blocks_snapshot:
        _persist_partial_assistant_turn(
            session_id, ar_message_id, full_response, blocks_snapshot, collected_tool_calls, "", "errored"
        )


def _settle_unconsumed_resume(
    session_id: str, message_id: str | None, block_builder, error_code: str | None
) -> list:
    """Finish a resume that ended before AR consumed its pause; return the blocks to emit.

    This cycle produced nothing, and the turn's row already holds the pause as
    it stands, so the row is not rewritten: after a refusal or an unreachable
    AR, AR still holds the pause and the cards stay pending for any client to
    answer again. Only when AR says the pause is gone are the cards settled, as
    ``expired``, unless a concurrent Stop already finalized the row.

    Only the interaction cards' status is settled on the stored row — never
    the whole ``block_builder`` snapshot. AR can still emit a ``sources`` or
    ``plan_created``/``task_updated`` event before a refusal (both are kept
    out of ``_RESUME_PROGRESS_EVENTS`` for exactly this reason), which lands
    on ``block_builder`` in memory; writing that snapshot back would persist
    those blocks onto a row this failed cycle never actually produced.
    """
    if error_code in _PAUSE_GONE_CODES and block_builder.settle_pending_interactions("expired"):
        row_name = _find_assistant_msg_by_message_id(session_id, message_id)
        if row_name:
            row = frappe.db.get_value("FAC Chat Message", row_name, ["blocks", "aborted"], as_dict=True)
            if row and not row.aborted:
                from ..block_builder import BlockBuilder

                stored_builder = BlockBuilder(existing_blocks=_parse_turn_blocks(row.blocks))
                if stored_builder.settle_pending_interactions("expired"):
                    _set_faco_message_with_retry(row_name, {"blocks": json.dumps(stored_builder.snapshot())})
    return block_builder.snapshot()


def _relay_ar_interrupt_resume(
    session_id,
    interrupt_response,
    user,
    site,
    client_type=None,
    message_id=None,
    session_state=None,
    restricted=False,
    model_id=None,
    web_search=None,
    thinking_enabled=None,
    reasoning_effort=None,
):
    """
    Resume an interrupted AR stream by sending interrupt responses.

    Same relay pattern as _relay_ar_stream but passes interrupt_response
    instead of a new message. ``session_state`` (zero-retention) is sent to AR
    and the returned blob is persisted on stream_complete; ``restricted`` skips
    blob persistence for GDPR Article 18 users.

    ``web_search`` / ``thinking_enabled`` carry the composer toggles the turn
    was sent with. They are not optional-in-practice here: the SPA always sends
    an explicit value, so omitting them on resume reaches AR as absence, and
    absence means "search available" — every HITL approval would silently
    re-enable web search against the state the pill is showing.

    ``model_id`` carries the turn's model the same way, and is genuinely
    optional: in auto mode nothing is sent, and absence lets AR select as it
    did on the original turn. The SDK omits the wire key on a falsy value.
    """
    frappe.init(site=site)
    frappe.connect()
    # Background-thread context re-establishment: `user` propagated from the
    # outer request handler, never client input. set_user keeps the Frappe
    # DOCNAME; AR is addressed by the email identity.
    frappe.set_user(user)  # nosemgrep: frappe-setuser
    from frappe_assistant_core.chat.api.auth import _ar_user_id

    ar_user = _ar_user_id(user)

    full_response = ""
    ar_message_id = None
    collected_tool_calls = []
    model_used = ""
    block_builder = None
    pause_consumed = False

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            _emit_socket_event(
                session_id,
                {
                    "event": "stream_error",
                    "session_id": session_id,
                    "message_id": ar_message_id,
                    "error": _not_registered_error(),
                    "action_required": "register",
                },
            )
            return

        current_tool_input = {}
        zero_retention = False  # Read off the first stream_start; gates blob persistence

        # Seed the builder with the paused turn's blocks, keyed on the
        # message_id the client took from the interrupted stream's stream_start.
        from ..block_builder import BlockBuilder

        block_builder = BlockBuilder(existing_blocks=_load_turn_blocks(session_id, message_id))

        # resume_interrupt cleared any older Stop when it accepted this resume,
        # so a flag up now is a Stop pressed while this relay waited to start.
        # The approval never reaches AR: the paused turn is stopped as it
        # stands, exactly as a Stop during the pause is.
        if is_cancelled(session_id):
            _abort_pending_interactions(session_id, message_id)
            return

        # Resume stream — no message, just interrupt_response
        stream_iter = client.stream_chat(
            session_id,
            None,
            ar_user,
            client_type=client_type,
            interrupt_response=interrupt_response,
            message_id=message_id,
            session_state=session_state,
            model_id=model_id,
            **_sdk_composer_kwargs(client.stream_chat, web_search, thinking_enabled, reasoning_effort),
        )
        for event in stream_iter:
            # Cooperative cancellation: same treatment as the send funnel.
            # Without this, Stop pressed while a resume is streaming was a
            # total no-op — AR could tear the stream down and this loop
            # would fall through to normal completion, persisting a
            # cancelled turn as if it finished.
            #
            # Persistence here goes through _persist_resume_cycle, NOT
            # _handle_stream_aborted — that helper (used by the send
            # funnel) replaces the row's content wholesale, which is
            # correct there because its full_response holds the entire
            # turn. Here full_response holds only this resume cycle's
            # text; replacing would erase everything earlier cycles wrote.
            if is_cancelled(session_id):
                try:
                    stream_iter.close()
                except Exception as e:
                    frappe.logger("faco.chat.cancel").warning(
                        f"stream_iter.close() raised during resume abort for {session_id}: {e}"
                    )
                _persist_resume_cycle(
                    session_id,
                    ar_message_id,
                    message_id,
                    full_response,
                    block_builder,
                    collected_tool_calls,
                    aborted=True,
                )
                _emit_socket_event(
                    session_id,
                    {
                        "event": "stream_aborted",
                        "session_id": session_id,
                        "message_id": ar_message_id,
                        "partial_response": full_response,
                        "blocks": block_builder.snapshot(),
                    },
                )
                return

            # A rate_limited refusal arrives here as a stream_error (_normalize_ar_event).
            event_type, data = _normalize_ar_event(event.get("event"), event.get("data", {}))

            if not pause_consumed and event_type in _RESUME_PROGRESS_EVENTS:
                # AR is running the resumed turn, so it has consumed the pause.
                block_builder.resolve_pending_interactions(interrupt_response)
                pause_consumed = True

            if _dispatch_relay_event(
                event_type, data, session_id, block_builder, ar_message_id=ar_message_id
            ):
                continue

            if event_type == "heartbeat":
                _emit_socket_event(
                    session_id,
                    {
                        "event": "heartbeat",
                        "session_id": session_id,
                        "message_id": ar_message_id,
                    },
                )

            elif event_type == "stream_start":
                ar_message_id = data.get("message_id")
                zero_retention = bool(data.get("zero_retention"))
                _emit_socket_event(
                    session_id,
                    {
                        "event": "stream_start",
                        "session_id": session_id,
                        "message_id": ar_message_id,
                        "model_id": data.get("model_id"),
                        "resumed": True,
                        "zero_retention": zero_retention,
                    },
                )

            elif event_type == "sources":
                # RAG citation sources for this turn — attach to the message
                # blocks so the UI can render a footer alongside the response.
                sources_list = data.get("sources", []) or []
                block_builder.add_sources(sources_list)
                _emit_socket_event(
                    session_id,
                    {
                        "event": "sources",
                        "session_id": session_id,
                        "message_id": data.get("message_id"),
                        "sources": sources_list,
                    },
                )

            elif event_type == "stream_chunk":
                chunk = data.get("content", "")
                full_response += chunk
                block_builder.add_text(chunk)
                _emit_socket_event(
                    session_id,
                    {
                        "event": "stream_chunk",
                        "session_id": session_id,
                        "message_id": ar_message_id,
                        "chunk": chunk,
                        "accumulated": full_response,
                    },
                )

            elif event_type == "tool_call_start":
                tool_id = data.get("tool_id")
                current_tool_input[tool_id] = data.get("input", {})
                block_builder.add_tool_call_start(tool_id, data.get("tool_name"), data.get("input", {}))
                _emit_socket_event(
                    session_id,
                    {
                        "event": "tool_call_start",
                        "session_id": session_id,
                        "message_id": ar_message_id,
                        "tool_name": data.get("tool_name"),
                        "tool_id": tool_id,
                        "input": data.get("input", {}),
                    },
                )

            elif event_type in ("tool_result", "tool_call_result"):
                tool_id = data.get("tool_id")
                collected_tool_calls.append(
                    {
                        "id": tool_id,
                        "name": data.get("tool_name"),
                        "result": data.get("result"),
                        "status": data.get("status", "success"),
                        "input": current_tool_input.pop(tool_id, {}),
                    }
                )
                block_builder.add_tool_call_result(
                    tool_id,
                    data.get("result"),
                    data.get("status", "success"),
                    data.get("duration_ms"),
                    data.get("tool_name"),
                )
                _emit_socket_event(
                    session_id,
                    {
                        "event": "tool_call_result",
                        "session_id": session_id,
                        "message_id": ar_message_id,
                        "tool_id": tool_id,
                        "tool_name": data.get("tool_name"),
                        "result": truncate_result_for_emit(data.get("result")),
                        "status": data.get("status", "success"),
                    },
                )

            elif event_type == "approval_required":
                # Nested interrupt — tool approved but triggered another
                block_builder.add_approval_required(
                    data.get("tool_id"),
                    data.get("tool_name"),
                    data.get("input", {}),
                    data.get("interrupts", []),
                )
                _emit_socket_event(
                    session_id,
                    {
                        "event": "approval_required",
                        "session_id": session_id,
                        "message_id": ar_message_id,
                        "tool_id": data.get("tool_id"),
                        "tool_name": data.get("tool_name"),
                        "input": data.get("input", {}),
                        "interrupts": data.get("interrupts", []),
                        # Lets the client arm a local expiry timer: AR publishes
                        # the authoritative expiry on its OWN realtime, which a
                        # split-deployment browser never receives.
                        "expires_at": data.get("expires_at"),
                    },
                )

            elif event_type == "tool_cancelled":
                block_builder.add_tool_cancelled(data.get("tool_id"), data.get("message", "Cancelled"))
                _emit_socket_event(
                    session_id,
                    {
                        "event": "tool_cancelled",
                        "session_id": session_id,
                        "message_id": ar_message_id,
                        "tool_id": data.get("tool_id"),
                        "tool_name": data.get("tool_name"),
                        "message": data.get("message", "Cancelled"),
                    },
                )

            elif event_type in ("plan_created", "task_updated", "plan_complete"):
                plan = data.get("plan")
                if plan:
                    block_builder.set_plan(plan)
                    _emit_socket_event(
                        session_id,
                        {
                            "event": event_type,
                            "session_id": session_id,
                            "message_id": ar_message_id,
                            "plan": plan,
                        },
                    )

            elif event_type == "workflow_created":
                block_builder.add_workflow_created(data)
                _emit_socket_event(
                    session_id,
                    {
                        "event": "workflow_created",
                        "session_id": session_id,
                        "message_id": ar_message_id,
                        "workflow_name": data.get("workflow_name"),
                        "docname": data.get("docname"),
                        "link": data.get("link"),
                        "status": data.get("status"),
                        "action": data.get("action"),
                    },
                )

            elif event_type == "stream_cancelled":
                # AR confirmed the agent stopped because it was cancelled —
                # same finalization as this funnel's own is_cancelled branch
                # above: _persist_resume_cycle (append + aborted guard), NOT
                # _handle_stream_aborted (replace semantics — belongs to the
                # send funnel, whose full_response holds the whole turn).
                cancelled_response = data.get("full_response") or full_response
                try:
                    stream_iter.close()
                except Exception as e:
                    frappe.logger("faco.chat.cancel").warning(
                        f"stream_iter.close() raised during resume AR-cancel for {session_id}: {e}"
                    )
                _persist_resume_cycle(
                    session_id,
                    ar_message_id,
                    message_id,
                    cancelled_response,
                    block_builder,
                    collected_tool_calls,
                    aborted=True,
                )
                _emit_socket_event(
                    session_id,
                    {
                        "event": "stream_aborted",
                        "session_id": session_id,
                        "message_id": ar_message_id,
                        "partial_response": cancelled_response,
                        "blocks": block_builder.snapshot(),
                    },
                )
                return

            elif event_type == "stream_complete":
                tokens_used = data.get("tokens_used", 0)
                credits_used = data.get("credits_used", 0)
                model_used = data.get("model", "")
                model_breakdown = data.get("model_breakdown")
                full_response = data.get("full_response", full_response)
                # A copy for the event below, taken before the reset that
                # follows the persist — the accumulator itself is emptied
                # immediately once this cycle lands.
                ar_full_response = full_response

                # Drop the sources block if the model never emitted any [N]
                # markers — retrieved context was present but unused, and a
                # footer would imply grounding that isn't there.
                block_builder.finalize_sources()

                # Persist: update the FACO Message row for THIS turn, keyed on
                # AR's message_id (stable across resume cycles within a turn).
                # The previous "order by creation desc" fallback caused resume
                # output to land on the wrong row once a session had more than
                # one assistant turn — see 2026-04-21 audit note.
                #
                # _persist_resume_cycle appends full_response (this cycle's
                # text only) to whatever the row already holds, and bails
                # without overwriting if a concurrent cancel_stream already
                # marked the row aborted.
                existing_faco_msg = _persist_resume_cycle(
                    session_id,
                    ar_message_id,
                    message_id,
                    full_response,
                    block_builder,
                    collected_tool_calls,
                    model_used=model_used,
                    model_breakdown=model_breakdown,
                    credits_used=credits_used,
                    routing=data.get("routing"),
                )
                if not existing_faco_msg:
                    _log_conversation(
                        session_id,
                        "",
                        full_response,
                        model_used,
                        None,
                        tool_calls=collected_tool_calls if collected_tool_calls else None,
                        message_id=ar_message_id,
                        blocks=block_builder.snapshot(),
                        credits=credits_used,
                        model_breakdown=model_breakdown,
                        routing=data.get("routing"),
                    )

                # This cycle is now persisted (appended by _persist_resume_cycle,
                # which re-reads the row, or written fresh by _log_conversation
                # above). Reset immediately — before the blob/quota work and
                # the emit below, any of which can still raise into the outer
                # except — so a later write in this same relay call (a
                # Stop polled on the next event at the top of this loop, a
                # stream_error, or that except) appends only what happens
                # after this point, never this cycle again.
                full_response = ""
                collected_tool_calls = []

                # The chip must survive a reload unchanged. The row holds the
                # whole turn (every resume cycle summed); credits_used here is
                # just this cycle, so reporting it would show one number live
                # and a larger one after refresh. Read back what was stored.
                turn_credits = credits_used
                if existing_faco_msg:
                    turn_credits = (
                        frappe.db.get_value("FAC Chat Message", existing_faco_msg, "credits_used")
                        or credits_used
                    )

                # Zero-retention: persist the returned (possibly re-interrupted)
                # signed session blob. A resume can interrupt again on a nested
                # tool approval — has_pending_interrupt then records that the
                # carried state still has an open interrupt.
                _persist_session_blob(session_id, user, data, zero_retention, restricted)

                # The quota cache is an increment, so it takes this cycle's own
                # spend — never the turn total, which would count earlier cycles
                # a second time.
                _update_subscription_cache(credits_used)

                # Get updated quota info from cache
                from frappe_assistant_core.chat.quota_cache import get_quota_snapshot

                snap = get_quota_snapshot()
                quota_total = snap.get("quota_total", 0)
                is_unlimited = quota_total == -1
                quota_remaining = -1 if is_unlimited else max(0, quota_total - snap.get("quota_used", 0))

                complete_event = {
                    "event": "stream_complete",
                    "session_id": session_id,
                    "message_id": ar_message_id,
                    "full_response": ar_full_response,
                    "quota_remaining": quota_remaining,
                    # Lets the composer's credit meter move per turn instead of
                    # only on a billing-page visit. The quota_* counters are
                    # tenant-wide; credits_used is this turn's own cost — the
                    # only figure that can move a member metered against an
                    # individual cap.
                    "quota_used": snap.get("quota_used", 0),
                    "quota_total": quota_total,
                    # Turn total, matching the persisted row — see turn_credits.
                    "credits_used": turn_credits,
                    # AR names it "model"; the SPA reads meta.model_id.
                    "model_id": model_used,
                    "blocks": block_builder.snapshot(),
                    "routing": data.get("routing"),
                }
                if data.get("truncated"):
                    complete_event["truncated"] = True
                    complete_event["stop_reason"] = "max_tokens"
                if data.get("interrupted"):
                    complete_event["interrupted"] = True
                    complete_event["pending_interrupts"] = data.get("pending_interrupts", [])

                _emit_socket_event(session_id, complete_event)

            elif event_type == "stream_error":
                _log_stream_error_detail(data)
                if pause_consumed:
                    blocks_snapshot = block_builder.snapshot()
                    _persist_errored_resume_cycle(
                        session_id,
                        ar_message_id,
                        message_id,
                        full_response,
                        block_builder,
                        collected_tool_calls,
                    )
                else:
                    blocks_snapshot = _settle_unconsumed_resume(
                        session_id, ar_message_id or message_id, block_builder, data.get("error_code")
                    )
                # Store any session state AR handed back, whether or not a partial turn was
                # written above: otherwise the next turn replays a blob that has never seen
                # this resume cycle.
                _persist_session_blob(session_id, user, data, zero_retention, restricted)
                _emit_socket_event(
                    session_id,
                    {
                        "event": "stream_error",
                        "session_id": session_id,
                        "error": data.get("error", "Unknown error"),
                        "error_code": data.get("error_code", "UNKNOWN"),
                        "retry_after": data.get("retry_after"),
                        "message_id": ar_message_id,
                        "blocks": blocks_snapshot,
                        "partial_response": full_response,
                    },
                )

    except Exception as e:
        import traceback

        frappe.log_error(
            title="FACO Stream Error",
            message=f"Error in interrupt resume relay: {e!s}\n{traceback.format_exc()}",
        )
        blocks_snapshot = block_builder.snapshot() if block_builder is not None else []
        # Before AR consumed the pause the row already holds it as it stands.
        if pause_consumed:
            _persist_errored_resume_cycle(
                session_id,
                ar_message_id,
                message_id,
                full_response,
                block_builder,
                collected_tool_calls,
            )
        _emit_socket_event(
            session_id,
            {
                "event": "stream_error",
                "session_id": session_id,
                "error": _safe_error(e, "FACO Chat Error"),
                "message_id": ar_message_id,
                "blocks": blocks_snapshot,
                "partial_response": full_response,
            },
        )

    finally:
        # The cancel flag stays: the next accepting endpoint clears it
        # (cancel.clear). Clearing it here could erase the next turn's Stop.
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — background thread / streaming context (not a request handler), explicit commit required to flush progress to DB.
        frappe.destroy()


def _relay_ar_stream(
    session_id,
    full_prompt,
    original_message,
    context,
    message_name,
    user,
    site,
    model_id=None,
    attachments=None,
    system_prompt_addendum=None,
    client_type=None,
    session_state=None,
    restricted=False,
    continue_from_message_id=None,
    web_search=None,
    thinking_enabled=None,
    reasoning_effort=None,
):
    """
    Relay SSE stream from AR to frontend via Socket.IO.

    This runs in a background thread. It:
    1. Connects to AR stream_chat endpoint
    2. Iterates over SSE events
    3. Emits each event via frappe.publish_realtime
    4. Saves the assistant response to FACO Message on completion

    Args:
            session_id: Conversation session ID
            full_prompt: Prepared prompt with context
            original_message: Original user message
            context: Page context dict
            message_name: FACO Message document name
            user: Frappe user
            site: Frappe site
            model_id: Optional model ID for per-request model selection
            attachments: Optional list of attachments for Vision API
            system_prompt_addendum: Optional per-request addition to the system prompt
            session_state: Optional client-held signed session blob (zero-retention).
                    Passed to AR on the request; the updated blob comes back on
                    stream_complete and is persisted into FAC Chat Session State.
            restricted: GDPR Article 18 processing restriction (FACO-M15). When set,
                    no blob is loaded or stored — the turn runs but nothing persists.
            continue_from_message_id: When set, this is a continuation of a
                    previously truncated response rather than a new message — AR
                    is asked to pick up generation from that message. No new user
                    message is pushed; the existing assistant row for that
                    message_id is read once into ``continued_turn``, and every
                    write of this turn — the finish, an error, a Stop or AR's
                    own cancel — appends to it through ``_persist_continued_turn``.
            web_search: Optional composer toggle forwarded to AR. None means
                    "unspecified" (AR defaults to search available); an explicit
                    False turns it off.
            thinking_enabled: Optional composer toggle forwarded to AR. Same
                    None-vs-False semantics as web_search.
            reasoning_effort: Optional composer thinking level forwarded to AR when
                    the installed SDK supports it.
    """
    # Set up Frappe context for background thread
    frappe.init(site=site)
    frappe.connect()
    # Background-thread context re-establishment (see _resume_ar_stream).
    # set_user keeps the Frappe DOCNAME; AR is addressed by the email identity.
    frappe.set_user(user)  # nosemgrep: frappe-setuser
    from frappe_assistant_core.chat.api.auth import _ar_user_id

    ar_user = _ar_user_id(user)

    full_response = ""
    model_used = ""
    ar_message_id = None  # AR Message ID for event reconstruction
    collected_tool_calls = []  # Collect tool calls for persistence
    block_builder = None
    continued_turn = None  # On a Continue: its row as it stood when the Continue started
    seed_blocks = []

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            _emit_socket_event(
                session_id,
                {
                    "event": "stream_error",
                    "session_id": session_id,
                    "message_id": ar_message_id,
                    "error": _not_registered_error(),
                    "action_required": "register",
                },
            )
            return

        tokens_used = 0
        current_tool_input = {}  # Track input from tool_call_start
        zero_retention = False  # Read off the first stream_start; gates blob persistence

        from ..block_builder import BlockBuilder

        # A Continue extends the answer it continues. Every write below goes to
        # that answer's row and adds this cycle to the turn as it stood now
        # (_continued_turn_updates), and the builder starts from its blocks, so
        # each snapshot keeps the answer's first part and its tool rows.
        if continue_from_message_id:
            # One read for the whole row, blocks included — fetching blocks
            # through a second query (_load_turn_blocks) left a window between
            # the two reads that the resume path doesn't have.
            continued_turn = frappe.db.get_value(
                "FAC Chat Message",
                {"session_id": session_id, "role": "assistant", "message_id": continue_from_message_id},
                ["name", "content", "credits_used", "model_breakdown", "tool_calls", "blocks"],
                as_dict=True,
            )
            seed_blocks = _parse_turn_blocks(continued_turn.blocks if continued_turn else None)
        block_builder = BlockBuilder(existing_blocks=seed_blocks)

        # send_message or continue_response cleared any older Stop when it
        # accepted this turn, so a flag up now is a Stop pressed while this
        # relay waited to start. Finish the turn as stopped without calling
        # AR: nothing runs and nothing is billed.
        if is_cancelled(session_id):
            _handle_stream_aborted(
                session_id,
                ar_message_id,
                full_response,
                block_builder,
                collected_tool_calls,
                model_used,
                stream_iter=None,
                continued_turn=continued_turn,
                # ar_message_id is still None here (stream_start hasn't run),
                # but a Continue's turn is already named by the id it continues.
                emit_message_id=ar_message_id or continue_from_message_id,
            )
            return

        # Emit start event
        _emit_socket_event(
            session_id,
            {
                "event": "stream_start",
                "session_id": session_id,
                "message_id": ar_message_id,
            },
        )

        # Stream from AR
        # SDK signature: stream_chat(session_id, message, user_id, context=None, model_id=None,
        # attachments=None, system_prompt_addendum=None, client_type=None, interrupt_response=None,
        # message_id=None, session_state=None, continue_from_message_id=None, *, web_search=None,
        # thinking_enabled=None) — web_search/thinking_enabled are keyword-only.
        stream_iter = client.stream_chat(
            session_id,
            full_prompt,
            ar_user,
            context,
            model_id,
            attachments,
            system_prompt_addendum,
            client_type=client_type,
            session_state=session_state,
            continue_from_message_id=continue_from_message_id,
            message_id=continue_from_message_id,
            **_sdk_composer_kwargs(client.stream_chat, web_search, thinking_enabled, reasoning_effort),
        )
        for event in stream_iter:
            # Cooperative cancellation: the cancel_stream endpoint sets a
            # Redis-backed flag, visible to any gunicorn worker. We poll it
            # between events so Stop takes effect within one tool / token
            # batch (typically <1s).
            if is_cancelled(session_id):
                _handle_stream_aborted(
                    session_id,
                    ar_message_id,
                    full_response,
                    block_builder,
                    collected_tool_calls,
                    model_used,
                    stream_iter=stream_iter,
                    continued_turn=continued_turn,
                )
                return

            # A rate_limited refusal arrives here as a stream_error (_normalize_ar_event).
            event_type, data = _normalize_ar_event(event.get("event"), event.get("data", {}))

            if _dispatch_relay_event(
                event_type, data, session_id, block_builder, ar_message_id=ar_message_id
            ):
                continue

            if event_type == "heartbeat":
                # Forward keepalive to frontend so activity timeout resets during long tool executions
                _emit_socket_event(
                    session_id,
                    {
                        "event": "heartbeat",
                        "session_id": session_id,
                        "message_id": ar_message_id,
                    },
                )

            elif event_type == "stream_start":
                ar_message_id = data.get("message_id")
                # Zero-retention capability is authoritative on the AR stream_start
                # (not the global capabilities endpoint). FAC only stores the
                # returned blob when this is true.
                zero_retention = bool(data.get("zero_retention"))
                if ar_message_id:
                    # Create the assistant FACO Message row eagerly so subsequent
                    # HITL resumes can find the correct row by message_id. Without
                    # this, an interrupted stream that never reaches stream_complete
                    # (e.g. worker dies, network drop mid-stream) would leave no
                    # row for the resume path to update, and the resume's fallback
                    # lookup would append to the wrong turn's row.
                    _ensure_assistant_msg(session_id, ar_message_id, context)
                    _emit_socket_event(
                        session_id,
                        {
                            "event": "stream_start",
                            "session_id": session_id,
                            "message_id": ar_message_id,
                            # Lets the composer show the running model from the
                            # first event, not only once the turn completes.
                            "model_id": data.get("model_id"),
                            "zero_retention": zero_retention,
                        },
                    )

            elif event_type == "sources":
                # RAG citation sources for this turn — attach to the message
                # blocks so the UI can render a footer alongside the response.
                sources_list = data.get("sources", []) or []
                block_builder.add_sources(sources_list)
                _emit_socket_event(
                    session_id,
                    {
                        "event": "sources",
                        "session_id": session_id,
                        "message_id": data.get("message_id"),
                        "sources": sources_list,
                    },
                )

            elif event_type == "stream_chunk":
                chunk = data.get("content", "")
                full_response += chunk
                block_builder.add_text(chunk)

                _emit_socket_event(
                    session_id,
                    {
                        "event": "stream_chunk",
                        "session_id": session_id,
                        "message_id": ar_message_id,
                        "chunk": chunk,
                        "accumulated": full_response,
                    },
                )

            # ============================================
            # Tool Execution Events
            # ============================================
            elif event_type == "tool_call_start":
                tool_id = data.get("tool_id")
                current_tool_input[tool_id] = data.get("input", {})
                block_builder.add_tool_call_start(tool_id, data.get("tool_name"), data.get("input", {}))
                _emit_socket_event(
                    session_id,
                    {
                        "event": "tool_call_start",
                        "session_id": session_id,
                        "message_id": ar_message_id,
                        "tool_name": data.get("tool_name"),
                        "tool_id": tool_id,
                        "input": data.get("input", {}),
                    },
                )

            elif event_type in ("tool_result", "tool_call_result"):
                tool_id = data.get("tool_id")
                tool_call_record = {
                    "id": tool_id,
                    "name": data.get("tool_name"),
                    "result": data.get("result"),
                    "status": data.get("status", "success"),
                    "duration_ms": data.get("duration_ms"),
                    "input": current_tool_input.pop(tool_id, {}),
                }
                collected_tool_calls.append(tool_call_record)
                block_builder.add_tool_call_result(
                    tool_id,
                    data.get("result"),
                    data.get("status", "success"),
                    data.get("duration_ms"),
                    data.get("tool_name"),
                )
                _emit_socket_event(
                    session_id,
                    {
                        "event": "tool_call_result",
                        "session_id": session_id,
                        "message_id": ar_message_id,
                        "tool_id": tool_id,
                        "tool_name": data.get("tool_name"),
                        "result": truncate_result_for_emit(data.get("result")),
                        "status": data.get("status", "success"),
                        "duration_ms": data.get("duration_ms"),
                    },
                )

            elif event_type == "approval_required":
                # HITL: tool needs user approval before execution
                block_builder.add_approval_required(
                    data.get("tool_id"),
                    data.get("tool_name"),
                    data.get("input", {}),
                    data.get("interrupts", []),
                )
                _emit_socket_event(
                    session_id,
                    {
                        "event": "approval_required",
                        "session_id": session_id,
                        "message_id": ar_message_id,
                        "tool_id": data.get("tool_id"),
                        "tool_name": data.get("tool_name"),
                        "input": data.get("input", {}),
                        "interrupts": data.get("interrupts", []),
                        # Lets the client arm a local expiry timer: AR publishes
                        # the authoritative expiry on its OWN realtime, which a
                        # split-deployment browser never receives.
                        "expires_at": data.get("expires_at"),
                    },
                )

            elif event_type == "tool_cancelled":
                block_builder.add_tool_cancelled(data.get("tool_id"), data.get("message", "Cancelled"))
                _emit_socket_event(
                    session_id,
                    {
                        "event": "tool_cancelled",
                        "session_id": session_id,
                        "message_id": ar_message_id,
                        "tool_id": data.get("tool_id"),
                        "tool_name": data.get("tool_name"),
                        "message": data.get("message", "Cancelled"),
                    },
                )

            elif event_type in ("plan_created", "task_updated", "plan_complete"):
                plan = data.get("plan")
                if plan:
                    block_builder.set_plan(plan)
                    _emit_socket_event(
                        session_id,
                        {
                            "event": event_type,
                            "session_id": session_id,
                            "message_id": ar_message_id,
                            "plan": plan,
                        },
                    )

            elif event_type == "workflow_created":
                block_builder.add_workflow_created(data)
                _emit_socket_event(
                    session_id,
                    {
                        "event": "workflow_created",
                        "session_id": session_id,
                        "message_id": ar_message_id,
                        "workflow_name": data.get("workflow_name"),
                        "docname": data.get("docname"),
                        "link": data.get("link"),
                        "status": data.get("status"),
                        "action": data.get("action"),
                    },
                )

            elif event_type == "stream_cancelled":
                # AR confirmed the agent stopped because it was cancelled —
                # same finalization as this funnel's own is_cancelled branch
                # above (_handle_stream_aborted): its full_response holds the
                # whole turn, so replacing the row's content is correct here.
                # A Continue appends what this relay streamed instead.
                _handle_stream_aborted(
                    session_id,
                    ar_message_id,
                    full_response if continued_turn else (data.get("full_response") or full_response),
                    block_builder,
                    collected_tool_calls,
                    model_used,
                    stream_iter=stream_iter,
                    continued_turn=continued_turn,
                )
                return

            elif event_type == "stream_complete":
                tokens_used = data.get("tokens_used", 0)
                credits_used = data.get("credits_used", 0)
                model_used = data.get("model", "")
                model_breakdown = data.get("model_breakdown")
                # AR's own full_response: on a Continue, AR seeds it with its
                # stored copy of the answer, so it duplicates the row's own
                # text. Only the event below reads it — the relay's own
                # full_response accumulator, which every later write in this
                # call reads, is never reassigned to it.
                ar_full_response = data.get("full_response", full_response)
                if not continued_turn:
                    full_response = ar_full_response

                # Drop the sources block if the model never emitted any [N]
                # markers — avoids misleading "Sources" footers on answers
                # that didn't actually use the retrieved context.
                block_builder.finalize_sources()

                # Update the assistant row we created on stream_start, or
                # create one if (defensively) stream_start never set message_id.
                if continued_turn:
                    assistant_row = continued_turn.name
                else:
                    assistant_row = _find_assistant_msg_by_message_id(session_id, ar_message_id)
                if assistant_row:
                    # Don't overwrite a row that the cancel path just marked
                    # aborted (race: stream_complete event arrived after the
                    # user pressed Stop). The abort persistence is the
                    # canonical state in that case.
                    aborted_flag = frappe.db.get_value("FAC Chat Message", assistant_row, "aborted")
                    if aborted_flag:
                        frappe.logger("faco.chat.stream").info(
                            f"Skipping stream_complete persist for {assistant_row}: row aborted concurrently"
                        )
                    elif continued_turn:
                        # The event below keeps reporting AR's own text
                        # (ar_full_response) and this cycle's cost; only the
                        # row sums what this relay actually streamed.
                        _persist_continued_turn(
                            continued_turn,
                            full_response,
                            block_builder.snapshot(),
                            collected_tool_calls,
                            model_used=model_used,
                            credits_used=credits_used,
                            model_breakdown=model_breakdown,
                        )
                        # Reset immediately — before the blob/quota work and
                        # the emit below, any of which can still raise into
                        # the outer except — so a later write in this
                        # same relay call (a Stop polled on the next event, a
                        # stream_error, or that except) appends only what
                        # happens after this point, never this cycle again.
                        # _set_faco_message_with_retry above can itself raise
                        # something other than a 1020; that propagates before
                        # this line runs, so the outer except then appends
                        # exactly what this relay streamed, once.
                        full_response = ""
                        collected_tool_calls = []
                    else:
                        updates = {
                            "content": full_response,
                            "blocks": json.dumps(block_builder.snapshot()),
                            # Store the real model AR reported; never the old
                            # "ar-agent" placeholder. Empty is fine — the UI
                            # hides the chip when no model is known.
                            "model": model_used or None,
                            "model_breakdown": json.dumps(model_breakdown) if model_breakdown else None,
                            "credits_used": credits_used,
                        }
                        if collected_tool_calls:
                            updates["tool_calls"] = json.dumps(collected_tool_calls)
                        # None means the turn said nothing about it — never an
                        # instruction to erase what an earlier hop wrote. A
                        # continue_from_message_id turn emits no receipt at
                        # all (AR gates model_selected on it), so this must
                        # not null the original turn's routing.
                        _routing_payload = data.get("routing")
                        if _routing_payload is not None:
                            updates["routing"] = json.dumps(_routing_payload)
                        _set_faco_message_with_retry(assistant_row, updates)
                else:
                    _log_conversation(
                        session_id,
                        original_message,
                        full_response,
                        model_used,
                        context,
                        tool_calls=collected_tool_calls if collected_tool_calls else None,
                        message_id=ar_message_id,
                        blocks=block_builder.snapshot(),
                        credits=credits_used,
                        model_breakdown=model_breakdown,
                        routing=data.get("routing"),
                    )

                # Zero-retention: persist the returned signed session blob — the
                # only copy of conversation state. Gated on the capability AR
                # advertised on stream_start and skipped for GDPR-restricted
                # users (no blob loaded inbound, none stored outbound).
                _persist_session_blob(session_id, user, data, zero_retention, restricted)

                # Fold this turn's credits into the local quota cache (credit units)
                _update_subscription_cache(credits_used)

                # Get updated quota info from cache
                from frappe_assistant_core.chat.quota_cache import get_quota_snapshot

                snap = get_quota_snapshot()
                quota_total = snap.get("quota_total", 0)
                is_unlimited = quota_total == -1
                quota_remaining = -1 if is_unlimited else max(0, quota_total - snap.get("quota_used", 0))

                complete_event = {
                    "event": "stream_complete",
                    "session_id": session_id,
                    "message_id": ar_message_id,
                    "full_response": ar_full_response,
                    "quota_remaining": quota_remaining,
                    # Lets the composer's credit meter move per turn instead of
                    # only on a billing-page visit. The quota_* counters are
                    # tenant-wide; credits_used is this turn's own cost — the
                    # only figure that can move a member metered against an
                    # individual cap.
                    "quota_used": snap.get("quota_used", 0),
                    "quota_total": quota_total,
                    "credits_used": credits_used,
                    # AR names it "model"; the SPA reads meta.model_id.
                    "model_id": model_used,
                    "blocks": block_builder.snapshot(),
                    "routing": data.get("routing"),
                }

                # Pass through truncation state
                if data.get("truncated"):
                    complete_event["truncated"] = True
                    complete_event["stop_reason"] = "max_tokens"

                # Pass through HITL interrupt state
                if data.get("interrupted"):
                    complete_event["interrupted"] = True
                    complete_event["pending_interrupts"] = data.get("pending_interrupts", [])

                _emit_socket_event(session_id, complete_event)

            elif event_type == "stream_error":
                _log_stream_error_detail(data)
                error_msg = data.get("error", "Unknown error")
                error_code = data.get("error_code", "UNKNOWN")
                action_required = data.get("action_required")

                blocks_snapshot = block_builder.snapshot()
                # A Continue refused before it produced anything leaves its
                # answer as it stood: the clients keep it continuable.
                if full_response or blocks_snapshot != seed_blocks:
                    _persist_partial_assistant_turn(
                        session_id,
                        ar_message_id,
                        full_response,
                        blocks_snapshot,
                        collected_tool_calls,
                        model_used,
                        "errored",
                        continued_turn=continued_turn,
                    )
                # The partial turn above is now in the transcript, so the carried
                # state has to advance with it — otherwise the next turn replays a
                # blob that has never seen this turn's user message.
                _persist_session_blob(session_id, user, data, zero_retention, restricted)

                _emit_socket_event(
                    session_id,
                    {
                        "event": "stream_error",
                        "session_id": session_id,
                        "error": error_msg,
                        "error_code": error_code,
                        "retry_after": data.get("retry_after"),
                        "action_required": action_required,
                        "message_id": ar_message_id,
                        "blocks": blocks_snapshot,
                        "partial_response": full_response,
                    },
                )

    except Exception as e:
        import traceback

        error_msg = f"Error in stream relay: {e!s}\n{traceback.format_exc()}"
        frappe.log_error(title="FACO Stream Error", message=error_msg)

        blocks_snapshot = block_builder.snapshot() if block_builder is not None else []
        if block_builder is not None and (full_response or blocks_snapshot != seed_blocks):
            _persist_partial_assistant_turn(
                session_id,
                ar_message_id,
                full_response,
                blocks_snapshot,
                collected_tool_calls,
                model_used,
                "errored",
                continued_turn=continued_turn,
            )

        _emit_socket_event(
            session_id,
            {
                "event": "stream_error",
                "session_id": session_id,
                "error": _safe_error(e, "FACO Stream Error"),
                "message_id": ar_message_id,
                "blocks": blocks_snapshot,
                "partial_response": full_response,
            },
        )

    finally:
        # The cancel flag stays: the next accepting endpoint clears it
        # (cancel.clear). Clearing it here could erase the next turn's Stop.
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — background thread / streaming context (not a request handler), explicit commit required to flush progress to DB.
        frappe.destroy()


def _persist_partial_assistant_turn(
    session_id: str,
    ar_message_id: str | None,
    partial_response: str,
    blocks_snapshot: list,
    collected_tool_calls: list,
    model_used: str,
    flag_field: str,
    *,
    fall_back_to_latest: bool = True,
    continued_turn=None,
) -> str | None:
    """Persist whatever the agent produced so far, marking the row with
    ``flag_field`` (``"aborted"`` or ``"errored"``) so a reload renders the
    truncated turn instead of losing it.

    On a Continue (``continued_turn``, its row as it stood when the Continue
    started) the write goes to that row, before or after AR's stream_start,
    and adds this cycle to the turn (``_persist_continued_turn``). None of the
    tiers below applies.

    Three lookup tiers, because in practice we've observed FACO Messages
    missing ``message_id`` on the row that stream_start was supposed to
    create (stream_start either didn't carry message_id, or
    _ensure_assistant_msg silently failed). Without these fallbacks the
    write was a no-op and the reload was empty:

      1. Look up by message_id (the canonical key).
      2. Fall back to the most recent assistant row in this session, whatever
         its message_id: the row stream_start would have created (or
         stream_complete via _log_conversation). Skipped when
         ``fall_back_to_latest`` is False, for a turn AR has not named yet:
         it has no row, so the latest one belongs to an earlier turn.
      3. If no row exists at all (interruption before AR persisted anything),
         create one now so a reload still shows the partial + marker.

    Returns the FAC Chat Message name that was written, or None if nothing
    could be persisted.
    """
    if continued_turn:
        _persist_continued_turn(
            continued_turn,
            partial_response,
            blocks_snapshot,
            collected_tool_calls,
            flag_field=flag_field,
            model_used=model_used,
        )
        return continued_turn.name

    assistant_row = _find_assistant_msg_by_message_id(session_id, ar_message_id) if ar_message_id else None
    if not assistant_row and fall_back_to_latest:
        # Tier 2: most recent assistant row in this session.
        assistant_row = frappe.db.get_value(
            "FAC Chat Message",
            {"session_id": session_id, "role": "assistant"},
            "name",
            order_by="creation desc",
        )
    if not assistant_row:
        # Tier 3: no row exists yet. Create one so the partial is visible on reload.
        try:
            from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import (
                FACChatMessage,
            )

            msg = FACChatMessage.create_message(
                session_id=session_id,
                role="assistant",
                content=partial_response or "",
            )
            if msg:
                assistant_row = msg.name
                if ar_message_id:
                    frappe.db.set_value("FAC Chat Message", assistant_row, "message_id", ar_message_id)
        except Exception as e:
            frappe.log_error(
                title="FAC Stream Partial Persist",
                message=f"Failed to create FAC Chat Message for {session_id}: {e!s}",
            )

    if assistant_row:
        updates = {
            "content": partial_response,
            "blocks": json.dumps(blocks_snapshot),
            flag_field: 1,
        }
        # Backfill message_id if we have it and the row is missing it. This
        # also future-proofs against the upstream stream_start/message_id
        # bug — once the row gets the id, subsequent lookups work.
        if ar_message_id:
            updates["message_id"] = ar_message_id
        if model_used:
            updates["model"] = model_used
        if collected_tool_calls:
            updates["tool_calls"] = json.dumps(collected_tool_calls)
        _set_faco_message_with_retry(assistant_row, updates)

    return assistant_row


def _persist_continued_turn(
    continued_turn,
    continuation: str,
    blocks_snapshot: list,
    collected_tool_calls: list,
    *,
    flag_field: str | None = None,
    model_used: str = "",
    credits_used: float = 0,
    model_breakdown: list | None = None,
) -> None:
    """Write a Continue's cycle onto the answer it continues.

    ``continued_turn`` is that row as it stood at the last write (the
    Continue's start, or wherever this function rebased it after an earlier
    call in the same relay run), and ``blocks_snapshot`` starts from its
    blocks, so every write holds the whole turn and a later one supersedes an
    earlier one. That includes the marker ``cancel_stream`` may have written
    first for a Stop naming this answer: the snapshot carries the relay's own
    single marker.

    A write with no ``flag_field`` is a clean finish, so it also clears a
    stale ``errored`` flag an earlier failed Continue on this same answer may
    have left set: the clients keep an errored-but-continuable answer
    continuable, and a later successful Continue must undo it on reload too.

    Once this write lands, ``continued_turn`` is rebased in place onto it —
    its ``content``, ``credits_used`` and (when written) ``model_breakdown``/
    ``tool_calls`` become what was just persisted. A later call in the same
    relay run (a Stop polled after this event, a ``stream_error``, or the
    outer ``except``) then starts from here, so it appends only what came
    after instead of re-adding this cycle or resetting its credits.
    """
    updates = _continued_turn_updates(
        continued_turn, continuation, credits_used, model_breakdown, tool_calls=collected_tool_calls
    )
    updates["blocks"] = json.dumps(blocks_snapshot)
    if flag_field:
        updates[flag_field] = 1
    else:
        updates["errored"] = 0
    if model_used:
        updates["model"] = model_used
    _set_faco_message_with_retry(continued_turn.name, updates)

    continued_turn.content = updates["content"]
    continued_turn.credits_used = updates["credits_used"]
    if "model_breakdown" in updates:
        continued_turn.model_breakdown = updates["model_breakdown"]
    if "tool_calls" in updates:
        continued_turn.tool_calls = updates["tool_calls"]


def _handle_stream_aborted(
    session_id: str,
    ar_message_id: str | None,
    partial_response: str,
    block_builder,
    collected_tool_calls: list,
    model_used: str,
    *,
    stream_iter,
    continued_turn=None,
    emit_message_id: str | None = None,
) -> None:
    """Persist whatever the agent produced before the user pressed Stop,
    then emit ``stream_aborted`` so the SPA can finalize its UI state.
    ``continued_turn`` is a Continue's row as it stood when the Continue
    started; the Stop is then recorded on it (``_persist_partial_assistant_turn``).

    ``emit_message_id`` names the turn on the emitted event only, when it
    differs from ``ar_message_id`` — a Continue's pre-AR Stop has no
    ``ar_message_id`` yet (``stream_start`` hasn't run), but the turn it
    continues already has one. The row lookup below is unaffected: it still
    keys on ``ar_message_id``, because ``continued_turn`` already names the
    row directly in that case.

    Three things happen here, in order:

    1. Close the SDK iterator, unless the Stop came before AR was called
       (``stream_iter`` is None). ``stream_chat`` is a generator over an
       HTTP/SSE response; calling ``.close()`` drops the connection,
       which is the signal AR uses to tear down its agent loop. Without
       this, the agent keeps running on the backend and we keep paying
       for tokens we'll never show.
    2. Save the partial assistant turn with ``aborted=1``, the "(Stopped
       by user)" marker appended. The blocks snapshot already reflects
       everything received up to this point, so a reload will render the
       truncated answer correctly rather than vanishing or appearing
       "still streaming".
    3. Emit ``stream_aborted`` so the streamManager on the SPA can
       flip ``isStreaming=false``, clear its activity timeout, and
       render the "(Stopped by user)" tail.
    """
    # Step 1 — drop the upstream connection, if AR was called.
    try:
        if stream_iter is not None:
            stream_iter.close()
    except Exception as e:
        # Closing a half-drained generator can raise; don't let that
        # block the persistence + event emission we still need to do.
        frappe.logger("faco.chat.cancel").warning(
            f"stream_iter.close() raised during abort for {session_id}: {e}"
        )

    # Step 2 — persist the partial with the marker. cancel_stream's own
    # HITL-pause finalizer (cancel.py:_abort_pending_interactions) still
    # races this on the same row for a named Stop, or one that lands on a
    # row still holding a pending interaction card; append_abort_marker is
    # idempotent so whichever of the two writers gets here first adds the
    # marker and the other is a safe no-op. For a no-id Stop on a live send
    # turn it no longer races here — cancel.py's own fallback only touches
    # a row that is still open (cancel.py:_is_open_turn), and that never
    # includes the row this call is about to create or finalize.
    marked_response, blocks_snapshot = append_abort_marker(partial_response, block_builder.snapshot())
    # A Stop seen before AR's stream_start named the turn: the turn has no row
    # yet (stream_start creates it), and the session's latest assistant row
    # belongs to an earlier turn, which this replace-write would overwrite with
    # the bare marker. The Stop gets a row of its own instead (tier 3). A
    # Continue's Stop, early or late, is added to the answer it continues.
    _persist_partial_assistant_turn(
        session_id,
        ar_message_id,
        marked_response,
        blocks_snapshot,
        collected_tool_calls,
        model_used,
        "aborted",
        fall_back_to_latest=bool(ar_message_id),
        continued_turn=continued_turn,
    )

    # Step 3 — tell the SPA we're done.
    _emit_socket_event(
        session_id,
        {
            "event": "stream_aborted",
            "session_id": session_id,
            "message_id": emit_message_id if emit_message_id is not None else ar_message_id,
            "partial_response": marked_response,
            "blocks": blocks_snapshot,
        },
    )
