# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Re-open an AR stream that AR refused because it was busy.

AR answers HTTP 503 with ``Retry-After`` when it has no room for another turn. The SDK
(1.14.0+) surfaces that as a lone ``stream_error`` coded ``AR_BUSY`` with ``retry_after``
seconds, before any event that could cost credits. :func:`stream_with_busy_retry` waits and
re-opens the stream up to ``MAX_BUSY_RETRIES`` times, telling the client it is waiting,
then ends the turn with one friendly ``AR_BUSY`` error.
"""

import time
from collections.abc import Callable, Iterator

from frappe import _

from .helpers import _emit_socket_event

BUSY_ERROR_CODE = "AR_BUSY"
MAX_BUSY_RETRIES = 3
MAX_WAIT_SECONDS = 30
WAIT_SLICE_SECONDS = 0.5


def _busy_retry_after(event: dict) -> float | None:
    """``retry_after`` of an AR_BUSY refusal, or None when ``event`` is anything else."""
    if event.get("event") != "stream_error":
        return None
    data = event.get("data") or {}
    if data.get("error_code") != BUSY_ERROR_CODE:
        return None
    retry_after = data.get("retry_after")
    if not isinstance(retry_after, (int, float)) or not retry_after > 0:
        return 1.0
    return float(retry_after)


def _wait(seconds: float, cancelled: Callable[[], bool], sleep: Callable[[float], None]) -> bool:
    """Sleep ``seconds`` in short slices. False when ``cancelled`` turned true first."""
    remaining = seconds
    while remaining > 0:
        if cancelled():
            return False
        step = min(WAIT_SLICE_SECONDS, remaining)
        sleep(step)
        remaining -= step
    return not cancelled()


def stream_with_busy_retry(
    open_stream: Callable[[], Iterator[dict]],
    session_id: str,
    *,
    cancelled: Callable[[], bool],
    sleep: Callable[[float], None] | None = None,
) -> Iterator[dict]:
    """Yield the events of ``open_stream()``, re-opening it while AR reports busy.

    Only an attempt whose FIRST event is an AR_BUSY refusal is retried; any other first
    event passes the whole stream through. ``cancelled`` is true on a Stop or when the relay's
    worker is exiting; either during the wait yields one heartbeat and ends, so the relay's own
    Stop and shutdown checks run and finalize the turn.
    """
    sleep = sleep or time.sleep
    retries = 0
    while True:
        stream = open_stream()
        first = next(stream, None)
        if first is None:
            return
        retry_after = _busy_retry_after(first)
        if retry_after is None:
            try:
                yield first
                yield from stream
            except GeneratorExit:
                # The relay closed us early (Stop, stall): drop the AR connection too.
                _close(stream)
                raise
            return
        _close(stream)

        if retries >= MAX_BUSY_RETRIES:
            yield {
                "event": "stream_error",
                "data": {
                    "error": _("FAC Cloud is busy. Try again in a minute."),
                    "error_code": BUSY_ERROR_CODE,
                    "retryable": True,
                },
            }
            return

        retries += 1
        wait_seconds = min(retry_after, MAX_WAIT_SECONDS)
        _emit_socket_event(
            session_id,
            {
                "event": "stream_status",
                "session_id": session_id,
                "status": "busy_retrying",
                "attempt": retries,
                "retry_after": wait_seconds,
            },
        )
        if not _wait(wait_seconds, cancelled, sleep):
            yield {"event": "heartbeat", "data": {}}
            return


def _close(stream: Iterator[dict]) -> None:
    close = getattr(stream, "close", None)
    if close is not None:
        close()
