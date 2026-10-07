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

_clock = time.monotonic
_bound = threading.local()


def _key(session_id: str) -> str:
    return f"fac_live_turn:{session_id}"


def _logger():
    return frappe.logger("fac_live_turn")


def _write(session_id: str, entry: dict) -> None:
    frappe.cache().set_value(_key(session_id), entry, expires_in_sec=ENTRY_TTL_SECONDS)


def get(session_id: str) -> dict | None:
    return frappe.cache().get_value(_key(session_id), expires=True)


def start(session_id: str, *, message_id: str | None = None) -> str:
    """Mark a turn as accepted before its relay runs.

    ``blocks`` and ``text`` stay None: a joining client keeps what the row shows
    until the relay writes its first snapshot.
    """
    turn = uuid.uuid4().hex
    _write(
        session_id,
        {
            "turn": turn,
            "message_id": message_id,
            "status": "starting",
            "started_at": frappe.utils.now(),
            "seq": 0,
            "text": None,
            "blocks": None,
            "active_thinking_id": None,
        },
    )
    return turn


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

    def __init__(self, session_id: str, builder, message_id: str | None = None):
        self.session_id = session_id
        self.builder = builder
        self.message_id = message_id
        self.turn = uuid.uuid4().hex
        self.seq = 0
        self._written_at = None
        self._save()

    def stamp(self, data: dict) -> None:
        self.seq += 1
        data["turn"] = self.turn
        data["seq"] = self.seq

    def record(self, data: dict) -> None:
        """Fold an emitted event into the snapshot. Never raises."""
        try:
            event = data.get("event")
            if event in TERMINAL_EVENTS:
                clear(self.session_id, self.turn)
                return
            if event == "stream_start" and data.get("message_id"):
                self.message_id = data["message_id"]
            if event in _THROTTLED_EVENTS and _clock() - self._written_at < TEXT_WRITE_INTERVAL:
                return
            self._save()
        except Exception as e:
            _logger().warning(f"live turn snapshot skipped for {self.session_id}: {e!s}")

    def _save(self) -> None:
        blocks = _trimmed(self.builder.snapshot())
        _write(
            self.session_id,
            {
                "turn": self.turn,
                "message_id": self.message_id,
                "status": "streaming",
                "started_at": frappe.utils.now(),
                "seq": self.seq,
                "text": "".join(b.get("content") or "" for b in blocks if b.get("type") == "text"),
                "blocks": blocks,
                "active_thinking_id": self.builder.active_thinking_id,
            },
        )
        self._written_at = _clock()


def _registry() -> dict:
    if not hasattr(_bound, "turns"):
        _bound.turns = {}
    return _bound.turns


def bind(session_id: str, builder, *, message_id: str | None = None, enabled: bool = True) -> LiveTurn | None:
    """Start keeping this relay run's snapshot; None (and nothing written) when disabled."""
    if not enabled:
        return None
    try:
        live = LiveTurn(session_id, builder, message_id)
    except Exception as e:
        _logger().warning(f"live turn not started for {session_id}: {e!s}")
        return None
    _registry()[session_id] = live
    return live


def unbind(session_id: str) -> None:
    live = _registry().pop(session_id, None)
    if live is None:
        return
    try:
        clear(session_id, live.turn)
    except Exception as e:
        _logger().warning(f"live turn not cleared for {session_id}: {e!s}")


def current(session_id: str) -> LiveTurn | None:
    return _registry().get(session_id)
