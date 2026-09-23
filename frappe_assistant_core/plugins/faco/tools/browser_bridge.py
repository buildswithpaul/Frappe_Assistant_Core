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


def send_browser_tool_call(
    user: str,
    call_id: str,
    tool_name: str,
    params: dict[str, Any],
    session_id: str | None = None,
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
    """
    # Record ownership first so submit_browser_tool_result can enforce it.
    _remember_call_owner(call_id, user)

    # 1. Store in Redis pending queue (durable, survives page navigation)
    call_data = json.dumps(
        {
            "call_id": call_id,
            "tool_name": tool_name,
            "params": params,
            "session_id": session_id,
            "created_at": time.time(),
        }
    )
    pending_key = _pending_calls_key(user, session_id)
    frappe.cache.lpush(pending_key, call_data)
    # Auto-expire the list after 60 seconds (cleanup if widget never picks up)
    try:
        frappe.cache.expire_key(pending_key, 60)
    except AttributeError:
        # Fallback for Frappe v15 and older without expire_key
        frappe.cache.expire(frappe.cache.make_key(pending_key), 60)

    # 2. Also send Socket.IO (fast-path if widget is already listening)
    message = {
        "call_id": call_id,
        "tool_name": tool_name,
        "params": params,
        "session_id": session_id,
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
    try:
        frappe.cache.expire_key(key, CALL_OWNER_TTL)
    except AttributeError:
        frappe.cache.expire(frappe.cache.make_key(key), CALL_OWNER_TTL)


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
