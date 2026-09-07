# Frappe Assistant Core - AR ↔ FACO Stream Relay
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Background-thread relay from AR's SSE stream to the SPA via Socket.IO.

These functions run in the bounded ``_relay_pool`` defined in
``messages``. They re-establish a Frappe context on entry and tear it
down on exit. Not whitelisted endpoints.
"""

from __future__ import annotations

import time

import frappe
from frappe import _

from .._helpers import (
    _not_registered_error,
    _safe_error,
)


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


from ..block_builder import truncate_result_for_emit  # noqa: E402
from ..chat.cancel import (  # noqa: E402
    append_abort_marker,
    is_cancelled,
)
from ..chat.cancel import (  # noqa: E402
    clear as clear_cancel,
)
from ..chat.helpers import (  # noqa: E402
    _emit_socket_event,
    _ensure_assistant_msg,
    _find_assistant_msg_by_message_id,
    _log_conversation,
    _log_stream_error_detail,
    _update_subscription_cache,
)

# Event types whose handling is identical in both the main stream loop and
# the HITL resume loop. Routing them through one function keeps the loops
# from drifting apart — the resume loop originally had no thinking branch
# at all because it was added to the main loop and never mirrored here.
_SHARED_RELAY_EVENTS = frozenset({"context_summarized", "model_selected", "thinking", "thinking_complete"})


def _dispatch_relay_event(event_type: str, data: dict, session_id: str, block_builder) -> bool:
    """Handle a relay event type shared by both loops.

    Returns True if ``event_type`` was recognized and handled (block_builder
    updated + socket event emitted), False otherwise so the caller can fall
    through to its own loop-specific branches.
    """
    if event_type not in _SHARED_RELAY_EVENTS:
        return False

    if event_type == "context_summarized":
        _emit_socket_event(
            session_id,
            {
                "event": "context_summarized",
                "session_id": session_id,
                "message": data.get("message", ""),
            },
        )

    elif event_type == "model_selected":
        _emit_socket_event(
            session_id,
            {
                "event": "model_selected",
                "session_id": session_id,
                "mode": data.get("mode"),
                "complexity": data.get("complexity"),
                "task_type": data.get("task_type"),
                "selected": data.get("selected"),
                "tier": data.get("tier"),
                "shortlist_size": data.get("shortlist_size", 0),
            },
        )

    elif event_type == "thinking":
        block_builder.add_thinking(data.get("content", ""))
        _emit_socket_event(
            session_id,
            {"event": "thinking", "session_id": session_id, "content": data.get("content", "")},
        )

    elif event_type == "thinking_complete":
        block_builder.complete_thinking()
        _emit_socket_event(session_id, {"event": "thinking_complete", "session_id": session_id})

    return True


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
    import json as json_module

    merged: dict[tuple, dict] = {}
    for source in (existing_json, incoming):
        if not source:
            continue
        if isinstance(source, str):
            try:
                source = json_module.loads(source)
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


def _persist_resume_cycle(
    session_id: str,
    ar_message_id: str | None,
    message_id: str | None,
    full_response: str,
    block_builder,
    collected_tool_calls: list,
    *,
    aborted: bool = False,
    model_used: str = "",
    model_breakdown: dict | None = None,
    credits_used: float = 0,
) -> str | None:
    """Persist one resume cycle's output onto the turn's existing row.

    Appends to (never replaces) whatever content is already on the row —
    one logical turn can span several resume cycles, and ``full_response``
    here only ever holds the current cycle's text, unlike the send
    funnel's ``full_response`` which holds the whole turn. No-op (besides
    logging) when the row is already ``aborted``: cancel.py's
    ``_abort_pending_interactions`` may have written the "(Stopped by
    user)" marker onto this same row moments ago, and overwriting it here
    would both lose that marker and, if this call's ``full_response`` is
    older, roll content itself backwards.

    Returns the FAC Chat Message name found for this turn, or None if no
    row exists yet (the caller should fall back to creating one).
    """
    import json as json_module

    existing_faco_msg = _find_assistant_msg_by_message_id(session_id, ar_message_id or message_id)
    if not existing_faco_msg:
        return None

    row = frappe.db.get_value(
        "FAC Chat Message",
        existing_faco_msg,
        ["content", "tool_calls", "aborted", "credits_used", "model_breakdown"],
        as_dict=True,
    )
    if row and row.get("aborted"):
        frappe.logger("faco.chat.resume").info(
            f"Skipping persist for {existing_faco_msg}: row aborted concurrently"
        )
        return existing_faco_msg

    current_content = (row.content if row else "") or ""
    updated_content = f"{current_content}\n\n{full_response}" if current_content else full_response
    # Accumulate credits: a single logical turn can span several resume
    # cycles, each emitting its own credits for just that cycle.
    prior_credits = (row.credits_used if row else 0) or 0
    updates = {
        "content": updated_content,
        "blocks": json_module.dumps(block_builder.snapshot()),
        "credits_used": round(prior_credits + credits_used, 2),
    }
    if aborted:
        updates["aborted"] = 1
    if model_used:
        updates["model"] = model_used
    if model_breakdown:
        # Merge, never replace: credits_used below is the whole turn's total, so
        # a breakdown holding only the last cycle would contradict it — the chip
        # and the usage screen would disagree on the same turn.
        updates["model_breakdown"] = json_module.dumps(
            _merge_model_breakdown(row.model_breakdown if row else None, model_breakdown)
        )
    if collected_tool_calls:
        existing_tc = (row.tool_calls if row else None) or ""
        existing_list = json_module.loads(existing_tc) if existing_tc else []
        updates["tool_calls"] = json_module.dumps(existing_list + collected_tool_calls)

    _set_faco_message_with_retry(existing_faco_msg, updates)
    return existing_faco_msg


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

    # A cancel flag set before this resume started (Stop pressed during the
    # prior pause, or racing a turn that was already completing) can never
    # legitimately apply to a turn that hasn't started yet.
    clear_cancel(session_id)

    full_response = ""
    ar_message_id = None
    collected_tool_calls = []
    model_used = ""
    block_builder = None

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            _emit_socket_event(
                session_id,
                {
                    "event": "stream_error",
                    "session_id": session_id,
                    "error": _not_registered_error(),
                    "action_required": "register",
                },
            )
            return

        current_tool_input = {}
        zero_retention = False  # Read off the first stream_start; gates blob persistence

        # Load existing blocks from FACO Message for continuation.
        # Look up by message_id (the per-turn identifier the frontend passed
        # in from the interrupted stream's stream_start). Falling back to
        # "last assistant in session" here is exactly what caused resume
        # output to leak onto the wrong turn's row — don't fall back.
        import json as _json

        from ..block_builder import BlockBuilder

        existing_blocks = []
        _existing_row = None
        if message_id:
            _existing_row = frappe.db.get_value(
                "FAC Chat Message",
                {"session_id": session_id, "role": "assistant", "message_id": message_id},
                ["name", "blocks"],
                as_dict=True,
            )
        if _existing_row and _existing_row.blocks:
            try:
                existing_blocks = _json.loads(_existing_row.blocks)
            except (ValueError, TypeError):
                existing_blocks = []

        block_builder = BlockBuilder(existing_blocks=existing_blocks)
        block_builder.resolve_pending_interactions(interrupt_response)

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
            web_search=web_search,
            thinking_enabled=thinking_enabled,
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

            event_type = event.get("event")
            data = event.get("data", {})

            if _dispatch_relay_event(event_type, data, session_id, block_builder):
                continue

            if event_type == "heartbeat":
                _emit_socket_event(
                    session_id,
                    {
                        "event": "heartbeat",
                        "session_id": session_id,
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
                    )

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
                    "full_response": full_response,
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
                blocks_snapshot = block_builder.snapshot()
                if full_response or blocks_snapshot:
                    _persist_partial_assistant_turn(
                        session_id,
                        ar_message_id,
                        full_response,
                        blocks_snapshot,
                        collected_tool_calls,
                        "",
                        "errored",
                    )
                # The partial turn above is now in the transcript, so the carried
                # state has to advance with it — otherwise the next turn replays a
                # blob that has never seen this resume cycle.
                _persist_session_blob(session_id, user, data, zero_retention, restricted)
                _emit_socket_event(
                    session_id,
                    {
                        "event": "stream_error",
                        "session_id": session_id,
                        "error": data.get("error", "Unknown error"),
                        "error_code": data.get("error_code", "UNKNOWN"),
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
        if block_builder is not None and (full_response or blocks_snapshot):
            _persist_partial_assistant_turn(
                session_id,
                ar_message_id,
                full_response,
                blocks_snapshot,
                collected_tool_calls,
                "",
                "errored",
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
        # Clear cancel marker so the same session can stream again. Safe
        # even when no cancel was issued — delete_value() on an absent
        # Redis key is a no-op.
        clear_cancel(session_id)
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
                    message is pushed; the existing assistant row for that message_id
                    is found and appended to via the same find-or-update-by-message_id
                    persistence stream_complete already uses.
            web_search: Optional composer toggle forwarded to AR. None means
                    "unspecified" (AR defaults to search available); an explicit
                    False turns it off.
            thinking_enabled: Optional composer toggle forwarded to AR. Same
                    None-vs-False semantics as web_search.
    """
    # Set up Frappe context for background thread
    frappe.init(site=site)
    frappe.connect()
    # Background-thread context re-establishment (see _resume_ar_stream).
    # set_user keeps the Frappe DOCNAME; AR is addressed by the email identity.
    frappe.set_user(user)  # nosemgrep: frappe-setuser
    from frappe_assistant_core.chat.api.auth import _ar_user_id

    ar_user = _ar_user_id(user)

    # A cancel flag set before this turn started (Stop pressed during a
    # prior HITL pause, or racing a turn that was already completing)
    # can never legitimately apply to a turn that hasn't started yet.
    # Without this, a stale flag would abort the user's very next message.
    clear_cancel(session_id)

    full_response = ""
    model_used = ""
    ar_message_id = None  # AR Message ID for event reconstruction
    collected_tool_calls = []  # Collect tool calls for persistence
    block_builder = None

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            _emit_socket_event(
                session_id,
                {
                    "event": "stream_error",
                    "session_id": session_id,
                    "error": _not_registered_error(),
                    "action_required": "register",
                },
            )
            return

        tokens_used = 0
        current_tool_input = {}  # Track input from tool_call_start
        zero_retention = False  # Read off the first stream_start; gates blob persistence

        from ..block_builder import BlockBuilder

        block_builder = BlockBuilder()

        # Emit start event
        _emit_socket_event(session_id, {"event": "stream_start", "session_id": session_id})

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
            web_search=web_search,
            thinking_enabled=thinking_enabled,
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
                    stream_iter,
                )
                return

            event_type = event.get("event")
            data = event.get("data", {})

            if _dispatch_relay_event(event_type, data, session_id, block_builder):
                continue

            if event_type == "heartbeat":
                # Forward keepalive to frontend so activity timeout resets during long tool executions
                _emit_socket_event(session_id, {"event": "heartbeat", "session_id": session_id})

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
                _handle_stream_aborted(
                    session_id,
                    ar_message_id,
                    data.get("full_response") or full_response,
                    block_builder,
                    collected_tool_calls,
                    model_used,
                    stream_iter,
                )
                return

            elif event_type == "stream_complete":
                tokens_used = data.get("tokens_used", 0)
                credits_used = data.get("credits_used", 0)
                model_used = data.get("model", "")
                model_breakdown = data.get("model_breakdown")
                full_response = data.get("full_response", full_response)

                # Drop the sources block if the model never emitted any [N]
                # markers — avoids misleading "Sources" footers on answers
                # that didn't actually use the retrieved context.
                block_builder.finalize_sources()

                # Update the assistant row we created on stream_start, or
                # create one if (defensively) stream_start never set message_id.
                import json as _json_mod

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
                    else:
                        updates = {
                            "content": full_response,
                            "blocks": _json_mod.dumps(block_builder.snapshot()),
                            # Store the real model AR reported; never the old
                            # "ar-agent" placeholder. Empty is fine — the UI
                            # hides the chip when no model is known.
                            "model": model_used or None,
                            "model_breakdown": _json_mod.dumps(model_breakdown) if model_breakdown else None,
                            "credits_used": credits_used,
                        }
                        if collected_tool_calls:
                            updates["tool_calls"] = _json_mod.dumps(collected_tool_calls)
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
                    "full_response": full_response,
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
                if full_response or blocks_snapshot:
                    _persist_partial_assistant_turn(
                        session_id,
                        ar_message_id,
                        full_response,
                        blocks_snapshot,
                        collected_tool_calls,
                        model_used,
                        "errored",
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
        if block_builder is not None and (full_response or blocks_snapshot):
            _persist_partial_assistant_turn(
                session_id,
                ar_message_id,
                full_response,
                blocks_snapshot,
                collected_tool_calls,
                model_used,
                "errored",
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
        # Clear cancel marker so the same session can stream again.
        # Safe even when no cancel was issued — delete_value() on an absent
        # Redis key is a no-op.
        clear_cancel(session_id)
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
) -> str | None:
    """Persist whatever the agent produced so far, marking the row with
    ``flag_field`` (``"aborted"`` or ``"errored"``) so a reload renders the
    truncated turn instead of losing it.

    Three lookup tiers, because in practice we've observed FACO Messages
    missing ``message_id`` on the row that stream_start was supposed to
    create (stream_start either didn't carry message_id, or
    _ensure_assistant_msg silently failed). Without these fallbacks the
    write was a no-op and the reload was empty:

      1. Look up by message_id (the canonical key).
      2. Fall back to the most recent assistant row in this session whose
         message_id is NULL — that's the row stream_start would have
         created (or stream_complete would have created via _log_conversation).
      3. If no row exists at all (interruption before AR persisted anything),
         create one now so a reload still shows the partial + marker.

    Returns the FAC Chat Message name that was written, or None if nothing
    could be persisted.
    """
    import json as _json_mod

    assistant_row = _find_assistant_msg_by_message_id(session_id, ar_message_id) if ar_message_id else None
    if not assistant_row:
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
            "blocks": _json_mod.dumps(blocks_snapshot),
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
            updates["tool_calls"] = _json_mod.dumps(collected_tool_calls)
        _set_faco_message_with_retry(assistant_row, updates)

    return assistant_row


def _handle_stream_aborted(
    session_id: str,
    ar_message_id: str | None,
    partial_response: str,
    block_builder,
    collected_tool_calls: list,
    model_used: str,
    stream_iter,
) -> None:
    """Persist whatever the agent produced before the user pressed Stop,
    then emit ``stream_aborted`` so the SPA can finalize its UI state.

    Three things happen here, in order:

    1. Close the SDK iterator. ``stream_chat`` is a generator over an
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
    # Step 1 — drop the upstream connection.
    try:
        stream_iter.close()
    except Exception as e:
        # Closing a half-drained generator can raise; don't let that
        # block the persistence + event emission we still need to do.
        frappe.logger("faco.chat.cancel").warning(
            f"stream_iter.close() raised during abort for {session_id}: {e}"
        )

    # Step 2 — persist the partial with the marker. cancel_stream's own
    # HITL-pause finalizer (cancel.py:_abort_pending_interactions) races
    # this on the same row; append_abort_marker is idempotent so whichever
    # of the two writers gets here first adds the marker and the other is
    # a safe no-op.
    marked_response, blocks_snapshot = append_abort_marker(partial_response, block_builder.snapshot())
    _persist_partial_assistant_turn(
        session_id,
        ar_message_id,
        marked_response,
        blocks_snapshot,
        collected_tool_calls,
        model_used,
        "aborted",
    )

    # Step 3 — tell the SPA we're done.
    _emit_socket_event(
        session_id,
        {
            "event": "stream_aborted",
            "session_id": session_id,
            "message_id": ar_message_id,
            "partial_response": marked_response,
            "blocks": blocks_snapshot,
        },
    )
