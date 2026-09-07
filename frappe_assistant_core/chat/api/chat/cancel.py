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

import frappe
from frappe import _

from ..chat.helpers import (
    _emit_socket_event,
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
    """Drop the cancel marker so the same session can stream again later."""
    if not session_id:
        return
    frappe.cache().delete_value(_cache_key(session_id))


@frappe.whitelist(methods=["POST"])
def cancel_stream(session_id: str, message_id: str | None = None) -> dict:
    """User-facing endpoint: stop the current stream for ``session_id``.

    Two cancellation regimes are handled here:

    1. **Live relay.** A relay loop is iterating ``stream_chat`` right
       now. We flip the cancel flag; the loop observes it on its next
       iteration and runs the proper abort handler (closes the SDK
       iterator, persists ``aborted=1``, emits ``stream_aborted``).

    2. **HITL pause.** AR emitted ``approval_required`` followed by
       ``stream_complete interrupted=true`` — at that point the relay
       thread exited cleanly and nothing is iterating anything. The
       persisted assistant row has ``pending`` interaction blocks
       waiting for a future ``resume_interrupt`` request. Pressing Stop
       here has no relay to signal; we mark the row aborted ourselves
       so the reload renders the cards as resolved instead of live.

    ``message_id`` is accepted for forward-compat / audit but not
    required — there is at most one active stream per session.
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


def _abort_pending_interactions(session_id: str, message_id: str | None) -> None:
    """Transition pending interaction blocks on the latest assistant row to
    ``aborted`` and make sure the "(Stopped by user)" marker is present,
    then emit ``stream_aborted``.

    Primarily handles the case where Stop is pressed while the conversation
    is paused at an HITL approval — there is no relay loop alive to do this
    for us. The persisted blocks would otherwise render an active approval
    card on reload, and clicking Approve there would hit AR with a stale
    interrupt id (AR responds "These approvals were already submitted.").
    It is also the fallback marker-writer for a live relay stream: see
    :func:`append_abort_marker`.

    No-op when the row has no pending interactions and already carries the
    marker, so this is safe to call unconditionally from ``cancel_stream``.
    """
    import json as _json

    # Locate the row: prefer message_id, fall back to most recent assistant
    # row in this session (matches the lookup tiers in _handle_stream_aborted).
    row_name = None
    if message_id:
        row_name = frappe.db.get_value(
            "FAC Chat Message",
            {"session_id": session_id, "role": "assistant", "message_id": message_id},
            "name",
        )
    if not row_name:
        row_name = frappe.db.get_value(
            "FAC Chat Message",
            {"session_id": session_id, "role": "assistant"},
            "name",
            order_by="creation desc",
        )
    if not row_name:
        return

    row = frappe.db.get_value("FAC Chat Message", row_name, ["blocks", "content", "aborted"], as_dict=True)
    if not row:
        return

    try:
        blocks = _json.loads(row.blocks) if row.blocks else []
    except (ValueError, TypeError):
        blocks = []

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
        return

    updates = {
        "aborted": 1,
        "blocks": _json.dumps(blocks),
        "content": content,
    }
    _set_faco_message_with_retry(row_name, updates)

    # Emit the authoritative finalize so the SPA (if open) reconciles.
    _emit_socket_event(
        session_id,
        {
            "event": "stream_aborted",
            "session_id": session_id,
            "message_id": message_id,
            "partial_response": content,
            "blocks": blocks,
        },
    )
