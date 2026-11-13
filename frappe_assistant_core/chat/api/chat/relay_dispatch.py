"""Decides whether a chat turn's relay runs as an RQ job on the faco_relay queue.

The web side of the relay-in-a-job path: probe for live faco_relay workers,
enqueue a turn's relay with a per-turn job id, and read the job's state back.
This module sits under ``live_turn`` and ``relay`` imports ``live_turn``, so it
must not import either at module level.
"""

from __future__ import annotations

import inspect
import time
import uuid
from collections.abc import Callable
from typing import NamedTuple

import frappe
from frappe.utils import background_jobs, cint
from rq.job import JobStatus
from rq.worker import Worker, WorkerStatus

RELAY_QUEUE = "faco_relay"
# relay.RELAY_MAX_TURN_SECONDS + 300; a test pins the sum.
RELAY_JOB_TIMEOUT_SECONDS = 2100
JOB_METHOD = "frappe_assistant_core.chat.api.chat.relay_job.run"
PROBE_TTL_SECONDS = 15
FAILED_PROBE_TTL_SECONDS = 30

RELAYS: dict[str, str] = {"stream": "_relay_ar_stream", "resume": "_relay_ar_interrupt_resume"}

_GONE_STATUSES = frozenset({JobStatus.FINISHED, JobStatus.FAILED, JobStatus.STOPPED, JobStatus.CANCELED})
_WAITING_STATUSES = frozenset({JobStatus.QUEUED, JobStatus.DEFERRED, JobStatus.SCHEDULED})

# (expires_at, WorkerCounts, probe_succeeded) per process
_probe_cache: dict[str, tuple[float, WorkerCounts, bool]] = {}
_PROBE_KEY = "counts"


class RelayQueueUnavailable(Exception):
    """The relay job could not be put on the queue."""


class WorkerCounts(NamedTuple):
    live: int
    busy: int


def job_relay_enabled() -> bool:
    return bool(cint(frappe.db.get_single_value("FAC Chat Settings", "relay_in_background_job")))


def relay_queue_configured() -> bool:
    return RELAY_QUEUE in background_jobs.get_queues_timeout()


def _probe_workers() -> WorkerCounts:
    """Read the relay queue's workers from RQ; a Redis failure raises.

    A worker in warm shutdown stays registered until its job ends but never takes another.
    """
    workers = [
        worker
        for worker in Worker.all(queue=background_jobs.get_queue(RELAY_QUEUE))
        if worker.shutdown_requested_date is None
    ]
    return WorkerCounts(
        live=len(workers),
        busy=sum(1 for worker in workers if worker.get_state() == WorkerStatus.BUSY),
    )


def relay_worker_counts(*, fresh: bool = False) -> WorkerCounts:
    """Live and busy workers on the relay queue; (0, 0) when unconfigured or the probe fails."""
    now = time.monotonic()
    cached = _probe_cache.get(_PROBE_KEY)
    if not fresh and cached and cached[0] > now:
        return cached[1]

    if not relay_queue_configured():
        return WorkerCounts(0, 0)

    try:
        counts = _probe_workers()
        ttl, ok = PROBE_TTL_SECONDS, True
    except Exception:
        frappe.logger("faco.relay").exception("faco_relay worker probe failed")
        counts = WorkerCounts(0, 0)
        ttl, ok = FAILED_PROBE_TTL_SECONDS, False

    _probe_cache[_PROBE_KEY] = (now + ttl, counts, ok)
    return counts


def _live_workers_or_raise() -> int:
    """Live worker count for a staleness verdict: a cached success, else a probe that raises.

    A failed probe's cached (0, 0) must never read as "no workers".
    """
    cached = _probe_cache.get(_PROBE_KEY)
    if cached and cached[2] and cached[0] > time.monotonic():
        return cached[1].live
    return _probe_workers().live


def use_job_relay() -> bool:
    return job_relay_enabled() and relay_queue_configured() and relay_worker_counts().live > 0


def relay_job_id(turn: str | None) -> str:
    return f"{RELAY_QUEUE}|{turn or uuid.uuid4().hex}"


def enqueue_relay(fn: Callable, args: tuple, kwargs: dict, *, job_id: str) -> None:
    """Enqueue ``fn(*args, **kwargs)`` as the relay job for one turn.

    A second call with the same ``job_id`` while the first is queued or running
    is a no-op. Any failure to enqueue is raised as ``RelayQueueUnavailable``, and
    leaves no message for the request to show: the turn falls back to the pool.
    """
    relay = next((key for key, name in RELAYS.items() if name == fn.__name__), None)
    if relay is None:
        raise ValueError(f"{fn.__name__} is not a relay function")

    relay_kwargs = dict(inspect.signature(fn).bind(*args, **kwargs).arguments)
    messages_before = len(frappe.local.message_log)
    try:
        frappe.enqueue(
            JOB_METHOD,
            queue=RELAY_QUEUE,
            timeout=RELAY_JOB_TIMEOUT_SECONDS,
            job_id=job_id,
            deduplicate=True,
            on_success=relay_job_succeeded,
            on_failure=relay_job_failed,
            relay=relay,
            relay_kwargs=relay_kwargs,
        )
    except Exception as exc:
        # frappe.throw (e.g. QueueOverloaded) logs a message before raising.
        del frappe.local.message_log[messages_before:]
        raise RelayQueueUnavailable(str(exc)) from exc


# The job's kwargs hold the user's message, attachments and context. RQ re-saves the job after
# these callbacks run, so they change what RQ keeps rather than deleting the key themselves.
def relay_job_succeeded(job, connection, result, *args, **kwargs) -> None:
    """RQ success callback: a result TTL of 0 makes RQ delete the job instead of keeping it."""
    job.result_ttl = 0


def relay_job_failed(job, connection, exc_type, exc_value, tb) -> None:
    """RQ failure callback: keep the failed record, without the turn's content."""
    job.kwargs = {**job.kwargs, "kwargs": {"relay": job.kwargs.get("kwargs", {}).get("relay")}}
    job.description = JOB_METHOD
    # Frappe's own failure callback, which this one replaces.
    background_jobs.truncate_failed_registry(job, connection, exc_type, exc_value, tb)


def relay_job_lost(job_id: str) -> bool:
    """True when the turn's job is gone, finished, or queued with nobody to run it."""
    status = background_jobs.get_job_status(job_id)
    if status is None or status in _GONE_STATUSES:
        return True
    if status in _WAITING_STATUSES:
        return _live_workers_or_raise() == 0
    return False
