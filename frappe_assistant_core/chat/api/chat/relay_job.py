"""RQ entry point: runs one chat turn's relay inside a ``faco_relay`` job."""

from __future__ import annotations

import frappe
from frappe import _

from frappe_assistant_core.chat.api.chat import relay as _relay_module
from frappe_assistant_core.chat.api.chat import relay_shutdown
from frappe_assistant_core.chat.api.chat.relay_dispatch import RELAYS


def run(relay: str, relay_kwargs: dict) -> None:
    """Run the relay named ``relay`` in this job's main thread, in the job's Frappe context.

    The relay applies ``frappe.set_user(user)`` itself, so it runs as the asker even though
    the job starts as Administrator. Running in the main thread lets RQ's timeout signal land
    in the relay's own ``try/finally``, which saves the partial answer.
    """
    fn = getattr(_relay_module, RELAYS[relay])
    if relay_kwargs.get("site") != frappe.local.site:
        raise ValueError(_("Relay job for another site"))
    relay_shutdown.watch_rq_worker()
    fn(**relay_kwargs, own_context=False)
