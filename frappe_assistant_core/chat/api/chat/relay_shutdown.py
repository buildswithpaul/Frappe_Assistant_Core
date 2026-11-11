# Frappe Assistant Core - relay pool shutdown signal
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Whether this worker process has begun shutting down its relay pool.

Process-local by design: the relay pool is per worker, so only the worker that is exiting
must stop accepting turns.
"""

from __future__ import annotations

import threading

_draining = threading.Event()


def is_draining() -> bool:
    return _draining.is_set()
