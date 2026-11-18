"""The turn in progress, for a surface that opens the conversation mid-turn.

The relay holds a turn's text and blocks in memory until the turn ends, so the
database cannot show a turn that is still running. While a turn streams, this
module keeps a snapshot of it in Redis (``fac_live_turn:<session_id>``) and
numbers every streamed event with the turn's token and a sequence number. A
surface that joins reads the snapshot (``get_live_turn``), shows it, and applies
only the events numbered after it.

The entry lives on this site only, holds only the running turn, expires after
ENTRY_TTL_SECONDS and is deleted when the turn ends. Nothing is written for
GDPR-restricted users. A Redis failure here never stops the stream.
"""

from __future__ import annotations

import threading
import time
import uuid

import frappe
from frappe import _

from frappe_assistant_core.chat.api.block_builder import truncate_result_for_emit

ENTRY_TTL_SECONDS = 600
TEXT_WRITE_INTERVAL = 0.5
TERMINAL_EVENTS = frozenset({"stream_complete", "stream_error", "stream_aborted"})
_THROTTLED_EVENTS = frozenset({"stream_chunk", "thinking"})
# AR heartbeats every 10 s, so a live relay writes at least every 20 s.
HEARTBEAT_SECONDS = 15
STALE_AFTER_SECONDS = 60
# A starting entry can wait behind a full relay pool with no heartbeat.
STARTING_STALE_SECONDS = 180
# A job turn's entry is written just before its job is enqueued: give the job time to appear.
JOB_CHECK_GRACE_SECONDS = 10

_clock = time.monotonic
_bound = threading.local()


def _key(session_id: str) -> str:
    return f"fac_live_turn:{session_id}"


def _logger():
    return frappe.logger("fac_live_turn")


def _write(session_id: str, entry: dict) -> None:
    entry["last_progress_at"] = time.time()
    frappe.cache().set_value(_key(session_id), entry, expires_in_sec=ENTRY_TTL_SECONDS)


def get(session_id: str) -> dict | None:
    return frappe.cache().get_value(_key(session_id), expires=True)


def start(
    session_id: str,
    *,
    message_id: str | None = None,
    client_turn: str | None = None,
    relay: str | None = None,
) -> str:
    """Mark a turn as accepted before its relay runs.

    ``client_turn`` is the id the requesting surface gave the request
    (``client_turn_id``); every event of the turn carries it, so that surface
    can tell its own turn from one another surface started.

    ``relay`` is ``"job"`` when the relay runs as an RQ job, so ``is_stale`` also reads the job.

    ``blocks`` and ``text`` stay None: a joining client keeps what the row shows
    until the relay writes its first snapshot.
    """
    turn = uuid.uuid4().hex
    _write(
        session_id,
        {
            "turn": turn,
            "message_id": message_id,
            "client_turn": client_turn,
            "relay": relay,
            "status": "starting",
            "started_at": frappe.utils.now(),
            "seq": 0,
            "text": None,
            "blocks": None,
            "active_thinking_id": None,
            "user": frappe.session.user,
        },
    )
    return turn


def is_stale(entry: dict, *, now: float | None = None) -> bool:
    """Whether the relay writing ``entry`` has stopped: its worker died or was killed.

    An entry from before last_progress_at existed is never stale; its TTL ends it. A job turn
    is also stale once its RQ job is lost, so a dead job shows as Interrupted without the wait.
    """
    written = entry.get("last_progress_at")
    if written is None:
        return False
    bound = STARTING_STALE_SECONDS if entry.get("status") == "starting" else STALE_AFTER_SECONDS
    age = (time.time() if now is None else now) - written
    if age > bound:
        return True
    return entry.get("relay") == "job" and age > JOB_CHECK_GRACE_SECONDS and _job_lost(entry["turn"])


def _job_lost(turn: str) -> bool:
    """Whether the turn's relay job is gone; an RQ read failure counts as not lost."""
    # Imported here: relay_dispatch sits under live_turn's import chain.
    from frappe_assistant_core.chat.api.chat import relay_dispatch

    try:
        return relay_dispatch.relay_job_lost(relay_dispatch.relay_job_id(turn))
    except Exception as e:
        _logger().warning(f"relay job state not read for turn {turn}: {e!s}")
        return False


def holds(session_id: str, turn: str) -> bool:
    """Whether the entry is still ``turn``'s. A Redis failure answers yes: it never stops a turn."""
    try:
        entry = get(session_id)
    except Exception as e:
        _logger().warning(f"live turn not read for {session_id}: {e!s}")
        return True
    return bool(entry) and entry.get("turn") == turn


def clear(session_id: str, turn: str | None = None) -> None:
    """Delete the entry; with ``turn``, only when it is still that turn's."""
    if turn is not None:
        entry = get(session_id)
        if not entry or entry.get("turn") != turn:
            return
    frappe.cache().delete_value(_key(session_id))


def _trimmed(blocks: list[dict]) -> list[dict]:
    for block in blocks:
        if block.get("type") == "tool_call" and block.get("result") is not None:
            block["result"] = truncate_result_for_emit(block["result"])
    return blocks


class LiveTurn:
    """One relay run's view of its entry: numbers events and writes snapshots."""

    def __init__(
        self,
        session_id: str,
        builder,
        message_id: str | None = None,
        turn: str | None = None,
        client_turn: str | None = None,
        relay: str | None = None,
    ):
        self.session_id = session_id
        self.client_turn = client_turn
        self.relay = relay
        self.builder = builder
        self.message_id = message_id
        self.turn = turn or uuid.uuid4().hex
        self.seq = 0
        # "starting" keeps the starting bound (is_stale) until AR sends its first event.
        self.status = "starting"
        # The entry was taken from this relay (mark_turn_interrupted, or a Retry's new turn).
        self.lost = False
        self._ended = False
        self._written_at = None
        self._save(check=False)

    def ar_responded(self) -> None:
        """AR sent its first event: from now the turn is stale after STALE_AFTER_SECONDS."""
        if self.status == "streaming" or self._ended:
            return
        self.status = "streaming"
        try:
            self._save()
        except Exception as e:
            _logger().warning(f"live turn snapshot skipped for {self.session_id}: {e!s}")

    def stamp(self, data: dict) -> None:
        self.seq += 1
        data["turn"] = self.turn
        data["seq"] = self.seq
        if self.client_turn is not None:
            data["client_turn"] = self.client_turn

    def record(self, data: dict) -> None:
        """Fold an emitted event into the snapshot. Never raises."""
        if self._ended:
            return
        try:
            event = data.get("event")
            if event in TERMINAL_EVENTS:
                self._ended = True
                clear(self.session_id, self.turn)
                return
            if event == "stream_start" and data.get("message_id"):
                self.message_id = data["message_id"]
            if event in _THROTTLED_EVENTS and _clock() - self._written_at < TEXT_WRITE_INTERVAL:
                return
            if event == "heartbeat" and _clock() - self._written_at < HEARTBEAT_SECONDS:
                return
            self._save()
        except Exception as e:
            _logger().warning(f"live turn snapshot skipped for {self.session_id}: {e!s}")

    def _save(self, check: bool = True) -> None:
        # Never revive or overwrite an entry this relay no longer holds; bind checked the first.
        if check and not holds(self.session_id, self.turn):
            self.lost = True
            self._ended = True
            return
        blocks = _trimmed(self.builder.snapshot())
        _write(
            self.session_id,
            {
                "turn": self.turn,
                "message_id": self.message_id,
                "client_turn": self.client_turn,
                "relay": self.relay,
                "status": self.status,
                "started_at": frappe.utils.now(),
                "seq": self.seq,
                "text": "".join(b.get("content") or "" for b in blocks if b.get("type") == "text"),
                "blocks": blocks,
                "active_thinking_id": self.builder.active_thinking_id,
                "user": frappe.session.user,
            },
        )
        self._written_at = _clock()


def _registry() -> dict:
    if not hasattr(_bound, "turns"):
        _bound.turns = {}
    return _bound.turns


def bind(
    session_id: str,
    builder,
    *,
    message_id: str | None = None,
    enabled: bool = True,
    turn: str | None = None,
) -> LiveTurn | None:
    """Start keeping this relay run's snapshot; None (and nothing written) when disabled.

    ``turn`` is the token the endpoint's ``start()`` returned, so one token covers
    the turn from send to finish; the client's own id for the turn is read off that
    starting entry, so ``start()`` stays its one source.
    """
    if not enabled:
        return None
    try:
        starting = get(session_id) if turn is not None else None
        if turn is not None and (not starting or starting.get("turn") != turn):
            # The turn was ended before its relay ran (mark_turn_interrupted); never revive it.
            return None
        client_turn = starting.get("client_turn") if starting else None
        relay = starting.get("relay") if starting else None
        live = LiveTurn(session_id, builder, message_id, turn, client_turn, relay)
    except Exception as e:
        _logger().warning(f"live turn not started for {session_id}: {e!s}")
        return None
    _registry()[session_id] = live
    return live


def unbind(session_id: str, turn: str | None = None) -> None:
    """Stop keeping this relay's snapshot and delete the entry it leaves behind.

    When the relay ended before ``bind`` (or bind failed), ``turn`` is the endpoint's
    token; clearing under it removes the starting entry without touching a newer turn.
    """
    live = _registry().pop(session_id, None)
    token = live.turn if live is not None else turn
    if token is None:
        return
    try:
        clear(session_id, token)
    except Exception as e:
        _logger().warning(f"live turn not cleared for {session_id}: {e!s}")


def current(session_id: str) -> LiveTurn | None:
    return _registry().get(session_id)


def ar_responded(session_id: str) -> None:
    live = current(session_id)
    if live is not None:
        live.ar_responded()


def lost(session_id: str) -> bool:
    """Whether this relay's turn was ended elsewhere; it must stop without saving."""
    live = current(session_id)
    return live is not None and live.lost


@frappe.whitelist(methods=["GET"])
def get_live_turn(session_id: str) -> dict | None:
    """The running turn of a conversation the caller owns, or None; ``stale`` when its relay died."""
    entry = _readable_entry(session_id)
    if entry:
        entry["stale"] = is_stale(entry)
    return entry


def _readable_entry(session_id: str) -> dict | None:
    if not session_id:
        frappe.throw(_("session_id is required"), frappe.ValidationError)
    from frappe_assistant_core.chat.api.chat.messages import _assert_session_owner

    _assert_session_owner(session_id)
    entry = get(session_id)
    if entry and entry.get("user") != frappe.session.user and "System Manager" not in frappe.get_roles():
        frappe.throw(_("You can only view your own conversation"), frappe.PermissionError)
    return entry


@frappe.whitelist(methods=["POST"])
def mark_turn_interrupted(session_id: str) -> dict:
    """End a turn whose relay died: keep what it streamed, flagged errored, and tell the surfaces.

    Only a stale entry qualifies, so a running turn is never cut short. A turn that died before
    its first snapshot has no answer row of its own yet; one is created for it, never the
    previous answer reused.
    """
    entry = _readable_entry(session_id)
    if not entry or not is_stale(entry):
        return {"interrupted": False}
    # Two surfaces can reconcile together; only one ends the turn.
    claim = frappe.cache().make_key(f"fac_live_turn_mark:{session_id}:{entry['turn']}")
    # nosemgrep: frappe-cache-breaks-multitenancy — the key is site-prefixed (make_key); set_value has no NX
    if not frappe.cache().set(claim, 1, nx=True, ex=ENTRY_TTL_SECONDS):
        return {"interrupted": False}
    from frappe_assistant_core.chat.api.chat import relay

    message_id = entry.get("message_id")
    # A queued continue or resume that never ran has no snapshot: its row is as it was.
    if entry.get("blocks") is not None or not message_id:
        relay._persist_partial_assistant_turn(
            session_id,
            message_id,
            entry.get("text") or "",
            entry.get("blocks") or [],
            [],
            "",
            "errored",
            fall_back_to_latest=False,
        )
    clear(session_id, entry["turn"])
    # The turn's asker spent any credits, not whoever ran this check.
    relay._end_credit_status_freshness(entry.get("user") or frappe.session.user)
    if entry.get("relay") == "job":
        error = _("This answer was interrupted before it finished. Retry to run it again.")
    else:
        error = _("This answer was interrupted by a server restart.")
    relay._emit_socket_event(
        session_id,
        {
            "event": "stream_error",
            "session_id": session_id,
            "message_id": message_id,
            "turn": entry["turn"],
            "client_turn": entry.get("client_turn"),
            "error_code": "TURN_INTERRUPTED",
            "error": error,
        },
    )
    return {"interrupted": True, "message_id": message_id, "error": error}


@frappe.whitelist(methods=["POST"])
def claim_live_turn(session_id: str) -> dict:
    """Hand a running turn's browser calls to the chat app.

    Open Full Assistant moves a conversation from the Desk widget to the chat app mid-turn. The turn
    still asks for the widget's browser tools, and the widget is gone, so its calls would time out.
    From now until the next message, this conversation's browser calls go to the chat app.
    """
    if not session_id:
        frappe.throw(_("session_id is required"), frappe.ValidationError)
    from frappe_assistant_core.chat.api.chat.messages import _assert_session_owner
    from frappe_assistant_core.plugins.faco.tools.browser_bridge import claim_session_for_spa

    _assert_session_owner(session_id)
    entry = get(session_id)
    # Only a turn that is running, and the caller's own.
    if not entry or entry.get("user") != frappe.session.user:
        return {"claimed": False}
    claim_session_for_spa(session_id)
    return {"claimed": True}
