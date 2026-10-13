# Frappe Assistant Core - AI Assistant integration for Frappe Framework
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

"""Per-session observers of the relay's events.

A surface that is not a browser (the Raven bot) follows a turn by registering here; the relay
calls every observer from _emit_socket_event, in the relay's own thread. Process-local by design:
the observer and the relay run in the same process (the Raven job waits on the relay).
"""

import threading
from collections.abc import Callable

import frappe

_observers: dict[str, Callable[[dict], None]] = {}
_lock = threading.Lock()


def register(session_id: str, callback: Callable[[dict], None]) -> None:
    with _lock:
        _observers[session_id] = callback


def unregister(session_id: str) -> None:
    with _lock:
        _observers.pop(session_id, None)


def notify(session_id: str, data: dict) -> None:
    callback = _observers.get(session_id)
    if callback is None:
        return
    try:
        callback(data)
    except Exception:
        frappe.log_error(title="FAC turn observer failed", message=frappe.get_traceback())
