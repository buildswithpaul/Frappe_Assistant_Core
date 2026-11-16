# Frappe Assistant Core - relay pool shutdown signal
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Graceful exit for the relay pool of a worker that is shutting down.

Process-local by design: the relay pool is per worker, so only the worker that is exiting
stops accepting turns. When the interpreter exits, ``_begin_drain`` runs before the pool's
threads are joined: new turns are refused (``is_draining``), and a relay still running gets
until ``_deadline`` to finish, then records its turn as interrupted (``should_give_up``)
before gunicorn's graceful timeout kills the worker.

This module imports without Frappe, so its exit behaviour can be tested in a bare interpreter.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable

# gunicorn's default graceful_timeout; neither bench nor frappe_docker overrides it.
GRACE_SECONDS = 30
# One AR heartbeat (10 s), the longest a relay waits between checks, plus the time to write.
MARGIN_SECONDS = 12
# A relay job runs until its turn ends, so the grace is longer than a web worker's: supervisor
# waits the queue timeout before it kills, and a turn past this is saved as interrupted.
JOB_GRACE_SECONDS = 300
# How often a relay job re-reads its worker's Redis hash for a shutdown request.
WORKER_POLL_SECONDS = 5

logger = logging.getLogger(__name__)

_draining = threading.Event()
_deadline: float | None = None
_grace_seconds: float | None = None
_watcher: Callable[[], bool] | None = None
_job_grace: float | None = None
_last_poll = float("-inf")
_installed = False
_install_lock = threading.Lock()


def is_draining() -> bool:
    if _watcher is not None and not _draining.is_set():
        _poll_watcher()
    return _draining.is_set()


def _poll_watcher() -> None:
    """Ask the worker watcher whether a stop was requested, at most every WORKER_POLL_SECONDS."""
    global _last_poll
    now = time.monotonic()
    if now - _last_poll < WORKER_POLL_SECONDS:
        return
    _last_poll = now
    try:
        requested = _watcher()
    except Exception:
        logger.exception("Could not read the RQ worker's shutdown request")
        return
    if requested:
        _begin_drain(_job_grace)


def should_give_up() -> bool:
    """Whether a running relay must stop now and record its turn as interrupted."""
    return is_draining() and _deadline is not None and time.monotonic() >= _deadline


def _read_grace() -> float:
    """``faco_relay_shutdown_grace`` from site config; ``FACO_GRACE`` only outside Frappe."""
    try:
        import frappe

        conf = frappe.local.conf
    except Exception:
        return float(os.environ.get("FACO_GRACE") or GRACE_SECONDS)
    return float(conf.get("faco_relay_shutdown_grace") or GRACE_SECONDS)


def _read_job_grace() -> float:
    """``faco_relay_job_shutdown_grace`` from site config."""
    import frappe

    return float(frappe.local.conf.get("faco_relay_job_shutdown_grace") or JOB_GRACE_SECONDS)


def _grace() -> float:
    return _grace_seconds if _grace_seconds is not None else _read_grace()


def _begin_drain(grace: float | None = None) -> None:
    global _deadline
    _deadline = time.monotonic() + (_grace() if grace is None else grace) - MARGIN_SECONDS
    _draining.set()


def install() -> None:
    """Run ``_begin_drain`` at interpreter exit, before the relay pool's threads are joined.

    ``threading._register_atexit`` callbacks run in reverse order before non-daemon threads are
    joined, and ``concurrent.futures.thread`` registers its join on import. Registered after
    that import, this runs first. A plain ``atexit`` handler would run after the join, which
    waits on the relays for ever.
    """
    global _installed, _grace_seconds
    with _install_lock:
        if _installed:
            return
        # Read now, under the request that imports the pool: at exit the site config is gone.
        _grace_seconds = _read_grace()
        threading._register_atexit(_begin_drain)
        _installed = True


def _rq_worker_key() -> str | None:
    """The Redis key of the worker running this job, or None outside a job."""
    from rq import get_current_job

    job = get_current_job()
    if job is None or not job.worker_name:
        return None
    return "rq:worker:" + job.worker_name


def _rq_shutdown_requested() -> bool:
    """Whether RQ's warm shutdown wrote ``shutdown_requested_date`` to this worker's hash."""
    from frappe.utils.background_jobs import get_redis_conn

    key = _rq_worker_key()
    return key is not None and bool(get_redis_conn().hget(key, "shutdown_requested_date"))


def watch_rq_worker() -> None:
    """Called by a relay job: poll the worker's hash so a warm shutdown starts the drain.

    The work horse gets no signal when its worker is told to stop, so the relay reads the flag.
    The grace is read now, while the job's site config is present.
    """
    global _watcher, _job_grace, _last_poll
    _job_grace = _read_job_grace()
    _last_poll = float("-inf")
    _watcher = _rq_shutdown_requested
