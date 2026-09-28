# Frappe Assistant Core - Stream cancel registry + endpoint
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Cooperative cancellation of in-flight AR streams.

When the user clicks Stop, the SPA hits :func:`cancel_stream`, which
records the cancellation against ``session_id``. The background relay
in :mod:`api.chat.relay` polls :func:`is_cancelled` between SSE events
and, on a positive hit, closes the SDK iterator (dropping the SSE
connection to AR), persists the partial response with ``aborted=1``,
and emits a final ``stream_aborted`` socket event so the SPA can stop
its activity timeout and mark the message.

Storage is ``frappe.cache()`` (Redis), not a module-level set: cancels
must be visible to whichever gunicorn worker is running the relay loop,
which may not be the worker that received this POST.
"""

from __future__ import annotations

import json

import frappe
from frappe import _

from ..chat.helpers import (
    _emit_socket_event,
    _parse_turn_blocks,
)

CANCEL_TTL_SECONDS = 120

ABORT_MARKER_TEXT = "\n\n_(Stopped by user)_"


def _has_abort_marker(blocks: list) -> bool:
    """True if ``blocks`` already carries the "(Stopped by user)" marker block."""
    return any(b.get("type") == "text" and b.get("_abortMarker") for b in blocks)


def append_abort_marker(content: str, blocks: list) -> tuple[str, list]:
    """Append the "(Stopped by user)" marker to ``content``/``blocks``, unless already present.

    Two independent writers can finalize the same aborted turn — this
    module's own HITL-pause path (:func:`_abort_pending_interactions`) and
    relay.py's live-stream abort handler (``_handle_stream_aborted``) —
    and either can win the race against the other, since they run on
    different threads/workers reacting to the same Redis cancel flag.
    Both call this, so whichever runs first appends the marker and
    whichever runs second is a safe no-op instead of silently dropping it
    or appending it twice.
    """
    if _has_abort_marker(blocks):
        return content, blocks
    marker_block = {
        "type": "text",
        "id": f"abort-marker-{frappe.utils.now_datetime().timestamp()}",
        "content": ABORT_MARKER_TEXT,
        "_abortMarker": True,
    }
    return f"{content or ''}{ABORT_MARKER_TEXT}", [*blocks, marker_block]


def _cache_key(session_id: str) -> str:
    return f"fac_cancel:{session_id}"


def mark_cancelled(session_id: str) -> None:
    """Mark ``session_id`` for cancellation. Idempotent, multi-worker-safe."""
    if not session_id:
        return
    frappe.cache().set_value(_cache_key(session_id), "1", expires_in_sec=CANCEL_TTL_SECONDS)


def is_cancelled(session_id: str) -> bool:
    """Return True if the caller should abort the relay loop."""
    if not session_id:
        return False
    # expires=True: skip frappe.local.cache, which would otherwise memoize a
    # None miss and never see a flag set by another worker.
    return bool(frappe.cache().get_value(_cache_key(session_id), expires=True))


def clear(session_id: str) -> None:
    """Drop the cancel marker. Only an endpoint accepting a turn calls this, before it queues the relay."""
    if not session_id:
        return
    frappe.cache().delete_value(_cache_key(session_id))


@frappe.whitelist(methods=["POST"])
def cancel_stream(session_id: str, message_id: str | None = None) -> dict:
    """User-facing endpoint: stop the current stream for ``session_id``.

    Two cancellation regimes are handled here:

    1. **Live relay.** A relay is iterating ``stream_chat``, or is queued
       and checks the flag before it calls AR. We flip the cancel flag;
       the relay observes it and runs the proper abort handler (closes
       the SDK iterator, persists ``aborted=1``, emits ``stream_aborted``).

    2. **HITL pause.** AR emitted ``approval_required`` followed by
       ``stream_complete interrupted=true`` — at that point the relay
       thread exited cleanly and nothing is iterating anything. The
       persisted assistant row has ``pending`` interaction blocks
       waiting for a future ``resume_interrupt`` request. Pressing Stop
       here has no relay to signal; we mark the row aborted ourselves
       so the reload renders the cards as resolved instead of live.

    ``message_id`` names the turn to stop. A Stop that names no stored turn
    finalizes only a turn still open (:func:`_abort_pending_interactions`).
    """
    if not session_id:
        frappe.throw(_("session_id is required"), frappe.ValidationError)

    # Ownership: only the session's owner (or System Manager) may cancel.
    # FACO Messages carry ``user``; check the most recent message in the
    # session belongs to the caller. Cheap query, hits the session-id index.
    owner = frappe.db.get_value(
        "FAC Chat Message",
        {"session_id": session_id},
        "user",
        order_by="creation desc",
    )
    if owner and owner != frappe.session.user and "System Manager" not in frappe.get_roles():
        frappe.throw(_("You can only cancel your own conversation"), frappe.PermissionError)

    # Regime 1: signal any live relay loop to bail at its next iteration.
    mark_cancelled(session_id)

    # Regime 2: also handle the HITL-pause case where no relay is alive.
    # Idempotent — if a live relay also fires, it'll re-snapshot blocks
    # anyway and the last writer wins; the pending → aborted transition
    # we do here is the only state change either path needs.
    #
    # Guarded: a local failure (DB error, retry-writer exhaustion) must not
    # stop the AR cancel below — otherwise AR keeps the agent running and
    # burning tokens on a turn the user already stopped.
    try:
        _abort_pending_interactions(session_id, message_id)
    except Exception:
        frappe.logger("faco.chat.cancel").warning(
            f"_abort_pending_interactions failed for {session_id}", exc_info=True
        )

    # Optimistic UI ping — the relay (or our own HITL-abort handler) will
    # emit the authoritative ``stream_aborted``. This one is just to unstick
    # the SPA in case the relay is wedged on a slow tool yield.
    _emit_socket_event(
        session_id,
        {
            "event": "stream_cancel_requested",
            "session_id": session_id,
            "message_id": message_id,
        },
    )

    # Local finalization (registry, HITL abort, socket ping) is already
    # complete at this point — the AR round-trip below only stops the
    # agent server-side and must never delay the response the user sees.
    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        ar_client = get_fac_cloud_client()
        if ar_client:
            ar_client.cancel_session(session_id)
    except Exception as e:
        frappe.logger("faco.chat.cancel").warning(
            f"AR cancel_session failed for {session_id}: {e}; relying on local abort", exc_info=True
        )

    return {"status": "cancel_requested", "session_id": session_id}


def _is_open_turn(blocks: list, aborted: int | bool | None, session_id: str, row_creation) -> bool:
    """True while a Stop that names no turn may still finalize this stored one.

    The turn holds a pending interaction card (paused at an approval, or a
    resume whose relay has not rewritten the row yet), or a relay abort
    finalizer that writes no marker (``_persist_resume_cycle``) has just
    flagged it ``aborted`` and the marker is still owed. A finished answer
    is neither.

    A stale pending card or an unmarked ``aborted`` flag can also belong to
    an *older* turn nobody ever settled — AR expired the pause, or a new
    turn started without going through the SPA's abort-then-send composer.
    A new turn's prompt always lands after the previous answer, so once a
    ``user`` row newer than this candidate exists, this row is no longer
    the open one and a no-id Stop must not reach back into it.
    """
    still_open = any(b.get("type") == "interaction" and b.get("status") == "pending" for b in blocks) or (
        bool(aborted) and not _has_abort_marker(blocks)
    )
    if not still_open:
        return False
    newer_user_row = frappe.db.exists(
        "FAC Chat Message",
        {"session_id": session_id, "role": "user", "creation": [">", row_creation]},
    )
    return not newer_user_row


def _abort_pending_interactions(session_id: str, message_id: str | None) -> str | None:
    """Finalize a Stop on the stored turn it applies to: pending interaction
    blocks become ``aborted``, the "(Stopped by user)" marker is appended
    unless present, the row is flagged ``aborted=1``, and ``stream_aborted``
    is emitted.

    Primarily handles the case where Stop is pressed while the conversation
    is paused at an HITL approval — there is no relay loop alive to do this
    for us. The persisted blocks would otherwise render an active approval
    card on reload, and clicking Approve there would hit AR with a stale
    interrupt id (AR responds "These approvals were already submitted.").
    It is also the marker-writer for a Stop during a HITL resume, whose relay
    finalizer (``_persist_resume_cycle``) writes none: see
    :func:`append_abort_marker`.

    The row is the assistant row ``message_id`` names, whatever its state.
    A Stop may name none: it can come before the turn's ``stream_start``,
    and the SPA sends an id of its own (``_requestId``). Then the session's
    latest assistant row is finalized only while it is still open
    (:func:`_is_open_turn`). Before a new turn's ``stream_start`` that row
    is the previous, finished answer, which this Stop must not mark; the
    relay's ``_handle_stream_aborted`` records the Stop on a new row instead.

    Returns the row's own ``message_id`` (AR's id for the turn) when a row
    was identified, so the caller can name it correctly even when it was
    itself called with a client-side id, or none. None when no row applied.
    """
    # Locate the row: the one message_id names, else the session's latest
    # assistant row, which is finalized only while it is still open (below).
    row_name = None
    if message_id:
        row_name = frappe.db.get_value(
            "FAC Chat Message",
            {"session_id": session_id, "role": "assistant", "message_id": message_id},
            "name",
        )
    named = bool(row_name)
    if not row_name:
        row_name = frappe.db.get_value(
            "FAC Chat Message",
            {"session_id": session_id, "role": "assistant"},
            "name",
            order_by="creation desc",
        )
    if not row_name:
        return None

    row = frappe.db.get_value(
        "FAC Chat Message",
        row_name,
        ["blocks", "content", "aborted", "creation", "message_id"],
        as_dict=True,
    )
    if not row:
        return None

    blocks = _parse_turn_blocks(row.blocks)

    if not named and not _is_open_turn(blocks, row.aborted, session_id, row.creation):
        # A finished answer (the Stop came before the next turn's
        # stream_start), or a Stop already finalized it: not this Stop's row.
        return None

    # Mark every pending interaction as aborted. The frontend renders
    # ``aborted`` status as a resolved indicator (no action buttons), so
    # the approve/reject/etc. buttons disappear on reload.
    changed = False
    for block in blocks:
        if block.get("type") == "interaction" and block.get("status") == "pending":
            block["status"] = "aborted"
            block["result"] = {"message": "Stopped by user"}
            changed = True

    # `aborted` is NOT a safe "already handled" signal here — relay.py's own
    # abort finalizer sets it too, and often wins this race since it runs on
    # the already-live relay thread while this handler is still doing its
    # first DB round trip. Bailing out on `aborted` (as this used to) meant
    # the marker was silently dropped whenever that finalizer won. Marker
    # presence, not `aborted`, is the only idempotency check both writers
    # can safely share.
    had_marker = _has_abort_marker(blocks)
    content, blocks = append_abort_marker(row.content or "", blocks)
    if not had_marker:
        changed = True

    # Use the shared retry-aware writer so a concurrent resume relay's
    # read+merge+write can't poison ours with InnoDB 1020 (record changed).
    from ..chat.relay import (
        _set_faco_message_with_retry,
    )

    if not changed:
        # No pending interaction AND a marker already existed (shouldn't
        # happen unless cancel was double-clicked). Still flip aborted=1
        # so the row's state is consistent.
        _set_faco_message_with_retry(row_name, {"aborted": 1})
        return row.message_id

    updates = {
        "aborted": 1,
        "blocks": json.dumps(blocks),
        "content": content,
    }
    _set_faco_message_with_retry(row_name, updates)

    # Emit the authoritative finalize so the SPA (if open) reconciles. Named
    # by the row's own message_id (AR's id), never the caller's — a Stop can
    # arrive naming no turn, or a client-side id another client has never seen.
    _emit_socket_event(
        session_id,
        {
            "event": "stream_aborted",
            "session_id": session_id,
            "message_id": row.message_id,
            "partial_response": content,
            "blocks": blocks,
        },
    )
    return row.message_id
