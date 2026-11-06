# Frappe Assistant Core - Browser Tools
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Browser bridge module for handling communication between server and FACO widget.

This module provides:
- send_browser_tool_call: Send a tool call request to the browser (Socket.IO + Redis queue)
- wait_for_browser_response: Block for the browser's response, budgeting each phase
- submit_browser_tool_result: API endpoint for browser to submit results
- submit_browser_tool_ack: API endpoint for the browser to report progress, which is
  what lets the wait distinguish "widget absent" from "user still deciding"
- get_pending_browser_tool_calls: API for widget to catch up on missed calls after navigation

See the budget model below — the single flat timeout this replaced is why
screenshots failed while their approval card was still on screen.
"""

import json
import pickle
import re
import time
import uuid
from typing import Any, Optional

import frappe
from frappe import _

# FACO-M11: strict charset for client-supplied call_id values. 1-64 chars,
# alphanumeric + _ and -. Matches what the widget generates (UUID-ish).
_VALID_CALL_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")

# Redis key prefix for browser tool responses
BROWSER_TOOL_RESPONSE_PREFIX = "faco_browser_tool_response:"

# Redis list the waiter blocks on. Written alongside the response so the waiter
# wakes the instant a result lands instead of discovering it on the next poll.
BROWSER_TOOL_NOTIFY_PREFIX = "faco_browser_tool_notify:"

# Redis key holding the call's last reported progress state (see ACK_* below).
BROWSER_TOOL_ACK_PREFIX = "faco_browser_tool_ack:"

# Redis key prefix for pending tool calls (per user)
PENDING_CALLS_PREFIX = "faco_browser_pending_calls:"

# Redis key prefix mapping call_id -> owning user (prevents cross-user overwrite)
CALL_OWNER_PREFIX = "faco_browser_tool_owner:"

# --- Budget model -------------------------------------------------------------
# A browser tool call is NOT a uniform RPC. It has three phases with wildly
# different natural durations, and collapsing them into one timeout is what made
# screenshots fail: the server gave up at 45s while the user was still reading
# the approval card, so every capture-speed fix was invisible.
#
#   1. delivery   — socket hop. Milliseconds. If the widget does not acknowledge
#                   within ACK_TIMEOUT it is not listening, and waiting the full
#                   execution budget just to say so is wasted worker time.
#   2. decision   — a human reading an approval card. Unbounded in principle;
#                   USER_DECISION_TIMEOUT is what we are willing to hold for.
#   3. execution  — the actual capture/DOM work, budgeted per tool via
#                   BaseBrowserTool._timeout.
#
# MAX_TOTAL_WAIT is the hard ceiling for any single call and every other TTL is
# derived from it, so the durable queue and the owner record can never expire
# while a waiter is still legitimately waiting.
ACK_TIMEOUT = 8
USER_DECISION_TIMEOUT = 120
MAX_TOTAL_WAIT = 180

# Default execution budget once the widget reports it is actually working.
DEFAULT_TIMEOUT = 30

# How long a single blocking pop parks for. Bounds how quickly a progress
# transition is noticed; the response itself needs no polling at all.
BLOCK_INTERVAL = 1

# TTL for the call-owner mapping (seconds). Must outlive the longest wait.
CALL_OWNER_TTL = MAX_TOTAL_WAIT + 60

# Max age for pending calls (seconds) — skip calls the server has stopped
# waiting on. Must be >= MAX_TOTAL_WAIT or a call drained from the durable queue
# near the boundary executes against a caller that already gave up.
PENDING_CALL_MAX_AGE = MAX_TOTAL_WAIT

# Progress states the widget reports back. Monotonic in intent, but they travel
# as fire-and-forget calls so they can arrive out of order — the waiter only
# ever extends its deadline, never pulls it back in.
ACK_RECEIVED = "received"
ACK_AWAITING_USER = "awaiting_user"
ACK_EXECUTING = "executing"

_ACK_STATES = {ACK_RECEIVED, ACK_AWAITING_USER, ACK_EXECUTING}

# Widget JS ships unhashed behind a 12h public max-age, so after a deploy a real
# browser keeps running the PREVIOUS widget for up to half a day. That widget
# sends no progress at all, and treating its silence as "no widget here" made
# browser tools fail in 8s — strictly worse than before the phased budget.
#
# So silence is treated as an UNKNOWN client, not an absent one, and falls back
# to the legacy flat budget. The fast path is unlocked per user only once we have
# seen that user's widget speak the protocol at least once.
ACK_CAPABLE_PREFIX = "faco_browser_ack_capable:"
ACK_CAPABLE_TTL = 24 * 60 * 60


def _pending_calls_key(user: str, session_id: str | None) -> str:
    """Queue a browser call is parked on.

    Per session when the conversation is known, so a second tab cannot drain a
    call meant for the first; per user otherwise, which is what an AR that does
    not send the session header still expects.
    """
    return f"{PENDING_CALLS_PREFIX}session:{session_id}" if session_id else f"{PENDING_CALLS_PREFIX}{user}"


# Which client answers a conversation's browser calls for the rest of its running turn, set when the
# chat app takes a turn over from the Desk widget (Open Full Assistant). The widget's turn keeps
# asking for the widget's tools, and the widget is gone; the claim retypes those calls for the chat
# app. Server-side, so a widget open on the same conversation in another Desk tab cannot race it.
TURN_CLAIM_PREFIX = "faco_browser_turn_client:"
# Outlives any turn; the next message from any surface clears it first.
TURN_CLAIM_TTL = 30 * 60
SPA_CLIENT = "spa"
WIDGET_CLIENT = "widget"


def claim_session_for_spa(session_id: str) -> None:
    """Send this conversation's browser calls to the chat app, including those still in flight."""
    frappe.cache.set_value(f"{TURN_CLAIM_PREFIX}{session_id}", SPA_CLIENT, expires_in_sec=TURN_CLAIM_TTL)
    _hand_over_widget_calls(session_id)


def release_session_claim(session_id: str) -> None:
    """A new turn names its own client: forget the hand-over."""
    frappe.cache.delete_value(f"{TURN_CLAIM_PREFIX}{session_id}")


def _claimed_client(session_id: str | None) -> str | None:
    if not session_id:
        return None
    client = frappe.cache.get_value(f"{TURN_CLAIM_PREFIX}{session_id}", expires=True)
    return client.decode("utf-8") if isinstance(client, bytes) else client


def resolve_call_client(session_id: str | None, client_type: str | None) -> str | None:
    """The client that answers a browser call: the chat app once it has taken the turn over."""
    if client_type in (None, WIDGET_CLIENT) and _claimed_client(session_id) == SPA_CLIENT:
        return SPA_CLIENT
    return client_type


def desk_only_in_chat_app_error() -> str:
    """What FACO is told when a Desk-only browser tool is called on a turn the chat app holds.

    The chat app answers the tools that wait for the browser with the same words
    (chat/frontend/src/composables/useSpaBrowserTools.js).
    """
    return _(
        "This browser tool works only in the Desk widget, and the user is in the full chat app. "
        "Use browser_take_screenshot instead: it captures the page open beside the chat and returns "
        "its page_errors and page_text."
    )


def handed_over_error(tool_name: str) -> str:
    """What FACO is told about a call the widget held when the user moved to the full chat app."""
    if tool_name == "take_screenshot":
        return _(
            "The user moved this conversation to the full chat app before the Desk widget answered. "
            "Call browser_take_screenshot again: the full chat app now captures the page open beside "
            "the chat."
        )
    return _("The user moved this conversation to the full chat app before the Desk widget answered.") + (
        " " + desk_only_in_chat_app_error()
    )


# Every browser call of a conversation that a server worker is still waiting on, call_id -> call.
# The queue cannot tell the claim this: a widget drains it on load, and a call delivered over the
# socket stays on it after it has been answered (#34689).
SESSION_CALLS_PREFIX = "faco_browser_session_calls:"


def _session_calls_key(session_id: str) -> str:
    return f"{SESSION_CALLS_PREFIX}{session_id}"


def _register_call(session_id: str, call: dict[str, Any]) -> None:
    key = _session_calls_key(session_id)
    frappe.cache.hset(key, call["call_id"], call)
    _expire(key, CALL_OWNER_TTL)


def release_browser_call(session_id: str | None, call_id: str) -> None:
    """The server has stopped waiting on this call: a hand-over has nothing left to do for it."""
    if session_id:
        frappe.cache.hdel(_session_calls_key(session_id), call_id)


def _hand_over_widget_calls(session_id: str) -> None:
    """Give every widget call still being waited on to the chat app, or answer it, so none is orphaned.

    Open Full Assistant navigates the Desk tab away, which destroys the widget and any card it showed.
    A call nobody has taken yet is queued again for the chat app. A call the widget has taken
    (acknowledged) is answered at once: the widget will never answer it, and asking the user a second
    time inside the time already spent would leave them a fraction of the approval budget. A widget
    call no longer waited on is dropped from the queue, so the chat app never asks about it again.
    """
    queue_key = _pending_calls_key("", session_id)
    kept = [call for call in _drain_queue(queue_key) if call.get("client_type") not in (None, WIDGET_CLIENT)]

    for call in frappe.cache.hgetall(_session_calls_key(session_id)).values():
        if call.get("client_type") not in (None, WIDGET_CLIENT):
            continue
        call_id = call["call_id"]
        # Answered, and the waiter has yet to read it (a widget too old to report progress included).
        if frappe.cache.get_value(f"{BROWSER_TOOL_RESPONSE_PREFIX}{call_id}", expires=True) is not None:
            continue
        if read_call_progress(call_id) is None:
            kept.append({**call, "client_type": SPA_CLIENT})
        else:
            _store_response_once(call_id, {"error": handed_over_error(call.get("tool_name"))})

    # lpush onto an rpop queue: oldest first restores the order the calls were made in.
    for call in sorted(kept, key=lambda c: c.get("created_at", 0)):
        frappe.cache.lpush(queue_key, json.dumps(call))
    if kept:
        _expire(queue_key, 60)


def _drain_queue(key: str) -> list[dict[str, Any]]:
    """Pop every call off a pending queue, oldest first, skipping any that cannot be read."""
    calls = []
    while (raw := frappe.cache.rpop(key)) is not None:
        try:
            calls.append(json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw))
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue
    return calls


def _expire(key: str, seconds: int) -> None:
    try:
        frappe.cache.expire_key(key, seconds)
    except AttributeError:
        # Frappe v15 and older have no expire_key.
        frappe.cache.expire(frappe.cache.make_key(key), seconds)


def send_browser_tool_call(
    user: str,
    call_id: str,
    tool_name: str,
    params: dict[str, Any],
    session_id: str | None = None,
    client_type: str | None = None,
    awaited: bool = True,
) -> None:
    """
    Send a browser tool call request to the FACO widget.

    Uses two channels:
    1. Redis pending queue (durable) — survives page navigation, widget picks up on init
    2. Socket.IO event (fast path) — immediate delivery if widget is already listening

    Args:
        user: The user whose browser should receive the call
        call_id: Unique identifier for this call (used to match response)
        tool_name: Name of the browser tool to execute
        params: Parameters to pass to the tool handler
        session_id: Conversation the call belongs to. Absent (older AR that does
            not send the session header) delivery falls back to the user room,
            which every tab of that user receives.
        client_type: The client whose turn asked (widget, spa). The widget and the chat app can
            hold the same conversation, so each answers only its own. None from an older AR.
        awaited: Whether the caller waits for the answer. A waited-on call is registered against
            its conversation until release_browser_call, so a hand-over can reach it.
    """
    # Record ownership first so submit_browser_tool_result can enforce it.
    _remember_call_owner(call_id, user)

    # The chat app took this turn over from the widget: it answers the widget's calls now.
    client_type = resolve_call_client(session_id, client_type)

    # 1. Store in Redis pending queue (durable, survives page navigation)
    call = {
        "call_id": call_id,
        "tool_name": tool_name,
        "params": params,
        "session_id": session_id,
        "client_type": client_type,
        "created_at": time.time(),
    }
    if awaited and session_id:
        _register_call(session_id, call)
    pending_key = _pending_calls_key(user, session_id)
    frappe.cache.lpush(pending_key, json.dumps(call))
    # Auto-expire the list after 60 seconds (cleanup if widget never picks up)
    _expire(pending_key, 60)

    # 2. Also send Socket.IO (fast-path if widget is already listening)
    message = {
        "call_id": call_id,
        "tool_name": tool_name,
        "params": params,
        "session_id": session_id,
        "client_type": client_type,
    }
    if session_id:
        frappe.publish_realtime(
            event="faco_browser_tool_call",
            message=message,
            room=f"task_progress:{session_id}",
        )
    else:
        frappe.publish_realtime(
            event="faco_browser_tool_call",
            message=message,
            user=user,
        )


def _remember_call_owner(call_id: str, user: str) -> None:
    """Bind a call to the user allowed to answer it.

    Explicit TTL — the owner record MUST expire even if the response never
    comes back, or a crashed tab leaks a key per call forever.
    """
    frappe.cache.set_value(
        f"{CALL_OWNER_PREFIX}{call_id}",
        user,
        expires_in_sec=CALL_OWNER_TTL,
    )


def _notify_key(call_id: str) -> str:
    return f"{BROWSER_TOOL_NOTIFY_PREFIX}{call_id}"


def _notify_waiter(call_id: str) -> None:
    """Wake whoever is blocked on this call."""
    key = _notify_key(call_id)
    frappe.cache.lpush(key, "1")
    _expire(key, CALL_OWNER_TTL)


def _await_notification(call_id: str, block_seconds: int) -> bool:
    """Block until a result is signalled or `block_seconds` elapse.

    NOTE: ``frappe.cache`` wraps ``lpush``/``rpop`` with ``make_key`` but ships no
    ``brpop`` wrapper, so the raw command must be namespaced by hand — exactly the
    trap ``hincrby`` sets. Without ``make_key`` this blocks on an empty key
    forever and every browser tool times out.
    """
    namespaced = frappe.cache.make_key(_notify_key(call_id))
    return bool(frappe.cache.brpop(namespaced, timeout=block_seconds))


def record_call_progress(call_id: str, state: str, user: str | None = None) -> None:
    """Store the widget's latest progress state for this call."""
    frappe.cache.set_value(f"{BROWSER_TOOL_ACK_PREFIX}{call_id}", state, expires_in_sec=CALL_OWNER_TTL)
    if user:
        _mark_ack_capable(user)


def _mark_ack_capable(user: str) -> None:
    """Remember that this user's widget speaks the progress protocol."""
    frappe.cache.set_value(f"{ACK_CAPABLE_PREFIX}{user}", 1, expires_in_sec=ACK_CAPABLE_TTL)


def is_ack_capable(user: str) -> bool:
    """Whether we may assume silence means "no widget" rather than "old widget"."""
    return bool(frappe.cache.get_value(f"{ACK_CAPABLE_PREFIX}{user}", expires=True))


def read_call_progress(call_id: str) -> str | None:
    state = frappe.cache.get_value(f"{BROWSER_TOOL_ACK_PREFIX}{call_id}", expires=True)
    if isinstance(state, bytes):
        state = state.decode("utf-8")
    return state


def store_browser_tool_response(call_id: str, response: dict[str, Any]) -> None:
    """Persist a response and wake the waiter."""
    frappe.cache.set_value(
        f"{BROWSER_TOOL_RESPONSE_PREFIX}{call_id}", response, expires_in_sec=CALL_OWNER_TTL
    )
    _notify_waiter(call_id)


def _store_response_once(call_id: str, response: dict[str, Any]) -> None:
    """Store a response unless one has landed already, and wake the waiter.

    SET NX, so an answer the widget submitted a moment earlier is never overwritten. set_value has
    no NX, so the raw command takes a key namespaced by make_key, as set_value would.
    """
    key = frappe.cache.make_key(f"{BROWSER_TOOL_RESPONSE_PREFIX}{call_id}")
    # nosemgrep: frappe-cache-breaks-multitenancy — the key is namespaced by make_key above
    if frappe.cache.set(key, pickle.dumps(response), ex=CALL_OWNER_TTL, nx=True):
        _notify_waiter(call_id)


def _clear_call_state(call_id: str) -> None:
    for prefix in (
        BROWSER_TOOL_RESPONSE_PREFIX,
        BROWSER_TOOL_ACK_PREFIX,
        BROWSER_TOOL_NOTIFY_PREFIX,
    ):
        try:
            frappe.cache.delete_value(f"{prefix}{call_id}")
        except Exception:
            pass


def _deadline_for(
    state: str | None,
    started: float,
    now: float,
    *,
    ack_window: int,
    decision_window: int,
    exec_window: int,
) -> float:
    """Absolute deadline implied by the call's current progress state.

    `awaiting_user` is measured from the start of the call — a human's clock began
    when the card appeared. `executing` is measured from the moment we observed
    the transition, because that is when the work actually began.
    """
    if state == ACK_AWAITING_USER:
        return started + decision_window
    if state == ACK_EXECUTING:
        return now + exec_window
    if state == ACK_RECEIVED:
        return started + max(ack_window, exec_window)
    return started + ack_window


def wait_for_browser_response(
    call_id: str,
    timeout: int = DEFAULT_TIMEOUT,
    *,
    ack_timeout: int | None = None,
    user_decision_timeout: int | None = None,
    max_total: int | None = None,
    block_interval: int | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """
    Wait for a browser tool response, budgeting each phase separately.

    Returns ``(response, last_state)``. ``response`` is None on timeout, and
    ``last_state`` is the last progress the widget reported — which is what lets
    the caller say *why* it gave up (never delivered vs. user never answered vs.
    capture overran) instead of one undifferentiated "timed out".

    Args:
        call_id: The call ID to wait for
        timeout: Execution budget once the widget reports it is working
        ack_timeout / user_decision_timeout / max_total / block_interval:
            overrides, primarily for tests

    Returns:
        (response dict or None, last observed ACK_* state or None)
    """
    ack_window = ACK_TIMEOUT if ack_timeout is None else ack_timeout
    decision_window = USER_DECISION_TIMEOUT if user_decision_timeout is None else user_decision_timeout
    ceiling = MAX_TOTAL_WAIT if max_total is None else max_total
    block = BLOCK_INTERVAL if block_interval is None else block_interval

    response_key = f"{BROWSER_TOOL_RESPONSE_PREFIX}{call_id}"
    started = time.monotonic()
    hard_deadline = started + ceiling

    # Only fail fast on silence once this user's widget has proved it reports
    # progress. Otherwise assume a cached pre-protocol widget and keep the old
    # flat budget, so an upgrade never makes browser tools worse than before.
    fast_fail = is_ack_capable(frappe.session.user)
    deadline = started + (ack_window if fast_fail else max(ack_window, timeout))
    state = None

    # A result may already be waiting (widget answered before we started to
    # block, e.g. a cached page context). Check once before parking.
    existing = frappe.cache.get_value(response_key, expires=True)
    if existing is not None:
        state = read_call_progress(call_id)
        _clear_call_state(call_id)
        return existing, state

    while True:
        now = time.monotonic()
        if now >= deadline or now >= hard_deadline:
            return None, state

        remaining = min(deadline, hard_deadline) - now
        if _await_notification(call_id, max(1, min(block, int(remaining) or 1))):
            response = frappe.cache.get_value(response_key, expires=True)
            _clear_call_state(call_id)
            return response, state

        observed = read_call_progress(call_id)
        if observed != state:
            state = observed
            candidate = _deadline_for(
                state,
                started,
                time.monotonic(),
                ack_window=ack_window,
                decision_window=decision_window,
                exec_window=timeout,
            )
            # Extend only. Acks are fire-and-forget so an earlier state can land
            # after a later one; letting it shrink the window would strand a user
            # who is mid-decision.
            deadline = min(max(deadline, candidate), hard_deadline)


def _assert_call_ownership(call_id: str) -> None:
    """Gate every client write against a call the caller actually owns.

    Shared by the result and progress endpoints so the two can never drift —
    a progress endpoint without this check would be a free cross-user probe for
    whether a given call_id exists.
    """
    if not call_id:
        frappe.throw(_("call_id is required"))

    # FACO-M11: client-supplied call_id lands in Redis keys (response + owner).
    # Reject anything outside a conservative charset so adversarial values
    # can't pollute the key-space, bloat memory, or trip future escape bugs.
    if not _VALID_CALL_ID.fullmatch(str(call_id)):
        frappe.throw(_("Invalid call_id format"), frappe.ValidationError)

    # The owner mapping was written by send_browser_tool_call(). If it's absent,
    # either the call_id is forged/stale/expired, or the session isn't the one
    # this call was issued to. Either way, refuse.
    owner = frappe.cache.get_value(f"{CALL_OWNER_PREFIX}{call_id}", expires=True)
    if isinstance(owner, bytes):
        owner = owner.decode("utf-8")

    current_user = frappe.session.user

    if not owner:
        raise frappe.PermissionError(_("Unknown or expired browser tool call_id"))

    if owner != current_user:
        # Different user owns this call — this is the cross-user-overwrite vector.
        frappe.log_error(
            title="FACO browser_bridge: cross-user browser tool write rejected",
            message=(f"call_id={call_id} owner={owner} submitter={current_user}"),
        )
        raise frappe.PermissionError(_("You are not the owner of this browser tool call"))


@frappe.whitelist(methods=["POST"])
def submit_browser_tool_result(
    call_id: str,
    result: dict | str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """
    API endpoint for the browser widget to submit tool results.

    This is called by the FACO widget after executing a browser tool.

    Args:
        call_id: The call ID this result is for
        result: The tool execution result (if successful) - dict or None
        error: Error message (if failed) - string or None

    Returns:
        Acknowledgment of receipt
    """
    _assert_call_ownership(call_id)

    redis_key = f"{BROWSER_TOOL_RESPONSE_PREFIX}{call_id}"

    # Normalize inputs - frappe.call may pass empty string instead of None
    if result == "" or result is None:
        result = None
    if error == "" or error is None:
        error = None

    # Build response payload
    if error:
        response = {"error": str(error)}
    elif result is not None:
        # frappe.call may pass result as JSON string or as dict
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                result = {"data": result}

        if isinstance(result, dict):
            response = result
        else:
            response = {"data": result}
    else:
        response = {}

    # Check if a successful result already exists (to prevent race conditions with multiple tabs)
    existing = frappe.cache.get_value(redis_key)
    if existing is not None and "error" not in existing and error:
        return {"status": "ok", "call_id": call_id, "skipped": True}

    store_browser_tool_response(call_id, response)

    return {"status": "ok", "call_id": call_id}


@frappe.whitelist(methods=["POST"])
def submit_browser_tool_ack(call_id: str, state: str) -> dict[str, Any]:
    """
    Report progress on an in-flight browser tool call.

    This is what separates "the widget is not listening" from "the user has not
    clicked Approve yet". Without it the server cannot tell those apart and has
    to budget every call for the worst case — which is precisely why screenshots
    timed out while the approval card was still on screen.

    Args:
        call_id: The call being reported on
        state: One of `received`, `awaiting_user`, `executing`

    Returns:
        Acknowledgment of receipt
    """
    _assert_call_ownership(call_id)

    if state not in _ACK_STATES:
        frappe.throw(_("Unknown browser tool state"), frappe.ValidationError)

    record_call_progress(call_id, state, user=frappe.session.user)

    return {"status": "ok", "call_id": call_id, "state": state}


@frappe.whitelist(methods=["POST"])
def get_pending_browser_tool_calls(session_id: str | None = None) -> list[dict[str, Any]]:
    """
    Fetch and clear pending browser tool calls for the caller.

    Called by the widget on initialization to catch up on tool calls that were
    sent while the widget was not active (e.g., after page navigation from SPA).

    Returns list of pending calls and atomically removes them from Redis.
    Skips calls older than PENDING_CALL_MAX_AGE seconds (likely already timed out).

    Args:
        session_id: Drain only this conversation's queue. Omitted, the caller's
            per-user queue is drained — the pre-session-scoping behaviour.
    """
    user = frappe.session.user
    pending_key = _pending_calls_key(user, session_id)

    calls = []
    # Drain the list — rpop returns oldest first when used with lpush
    while True:
        raw = frappe.cache.rpop(pending_key)
        if raw is None:
            break

        try:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            call_data = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            continue

        # Skip stale calls (server-side poll has likely already timed out)
        created_at = call_data.get("created_at", 0)
        if time.time() - created_at > PENDING_CALL_MAX_AGE:
            continue

        calls.append(call_data)

    return calls


@frappe.whitelist(methods=["POST"])
def test_realtime_connection() -> dict[str, Any]:
    """
    Test endpoint to verify realtime connection is working.
    Call from browser console:
        frappe.call({method: 'frappe_assistant_core.plugins.faco.tools.browser_bridge.test_realtime_connection'})
    Then check browser console for the test event.
    """
    user = frappe.session.user
    test_id = str(uuid.uuid4())[:8]

    frappe.publish_realtime(
        event="faco_browser_tool_call",
        message={
            "call_id": f"TEST-{test_id}",
            "tool_name": "test_ping",
            "params": {"message": "Hello from server!", "timestamp": time.time()},
        },
        user=user,
    )

    return {
        "status": "ok",
        "message": f"Test event sent to user {user}. Check browser console for '[FACO Browser Tools] Received tool call: test_ping'",
        "test_id": test_id,
    }
