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

import os
import threading
import time

# gunicorn's default graceful_timeout; neither bench nor frappe_docker overrides it.
GRACE_SECONDS = 30
# One AR heartbeat (10 s), the longest a relay waits between checks, plus the time to write.
MARGIN_SECONDS = 12

_draining = threading.Event()
_deadline: float | None = None
_grace_seconds: float | None = None
_installed = False
_install_lock = threading.Lock()


def is_draining() -> bool:
    return _draining.is_set()


def should_give_up() -> bool:
    """Whether a running relay must stop now and record its turn as interrupted."""
    return _draining.is_set() and _deadline is not None and time.monotonic() >= _deadline


def _read_grace() -> float:
    """``faco_relay_shutdown_grace`` from site config; ``FACO_GRACE`` only outside Frappe."""
    try:
        import frappe

        conf = frappe.local.conf
    except Exception:
        return float(os.environ.get("FACO_GRACE") or GRACE_SECONDS)
    return float(conf.get("faco_relay_shutdown_grace") or GRACE_SECONDS)


def _grace() -> float:
    return _grace_seconds if _grace_seconds is not None else _read_grace()


def _begin_drain() -> None:
    global _deadline
    _deadline = time.monotonic() + _grace() - MARGIN_SECONDS
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
