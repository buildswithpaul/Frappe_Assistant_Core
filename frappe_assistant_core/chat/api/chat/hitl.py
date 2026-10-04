"""HITL pause inspection — proxies AR's get_pending_interrupt.

Called by the chat frontend on ``ChatView`` mount, on socket reconnect,
and from the widget's init() so it can re-render the InteractionCard
after the user stepped away or the socket dropped.
"""

import frappe
from frappe import _

from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

from ..auth import _ar_user_id


def _unavailable() -> dict:
    """FAC could not ask AR, so "nothing pending" proves nothing (spec §8.7)."""
    return {"pending": False, "unavailable": True}


@frappe.whitelist(methods=["GET"])
def get_pending_interrupt(session_id: str) -> dict:
    """Forward to AR.

    Returns AR's answer: the pending pause, ``{pending: False}`` when AR says
    nothing is waiting, or ``{pending: False, unavailable: True}`` for a live
    pause AR cannot rebuild (zero retention). When FAC could not ask AR (no AR client, a
    transport or API error, or an empty reply) it returns
    ``{pending: False, unavailable: True}`` instead, so a client never reads
    an outage as "answered on another device". The SPA and the Desk widget
    read only ``pending`` and ``event``, so for them the probe still degrades
    silently and the user can type a new message.
    """
    if not session_id:
        frappe.throw(_("session_id is required"))

    client = get_fac_cloud_client()
    if client is None:
        # AR cloud not configured — FAC cannot ask.
        return _unavailable()

    try:
        result = client.get_pending_interrupt(session_id, _ar_user_id(frappe.session.user))
    except Exception as e:
        # Transport failure or unexpected error. Logged at WARN so it
        # doesn't spam the Error Log on routine AR unavailability.
        frappe.logger("fac.hitl").warning(
            f"get_pending_interrupt({session_id}) failed: {type(e).__name__}: {e}"
        )
        return _unavailable()

    # AR always answers a dict; the SDK documents None as a transport error.
    return result or _unavailable()
