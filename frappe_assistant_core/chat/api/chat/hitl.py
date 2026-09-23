"""HITL pause inspection — proxies AR's get_pending_interrupt.

Called by the chat frontend on ``ChatView`` mount, on socket reconnect,
and from the widget's init() so it can re-render the InteractionCard
after the user stepped away or the socket dropped.
"""

import frappe
from frappe import _

from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

from ..auth import _ar_user_id


@frappe.whitelist(methods=["GET"])
def get_pending_interrupt(session_id: str) -> dict:
    """Forward to AR. Returns ``{pending: False}`` on transport or
    configuration error so the frontend hydration path can degrade
    silently — the user can still type a new message."""
    if not session_id:
        frappe.throw(_("session_id is required"))

    client = get_fac_cloud_client()
    if client is None:
        # AR cloud not configured — nothing to hydrate.
        return {"pending": False}

    try:
        result = client.get_pending_interrupt(session_id, _ar_user_id(frappe.session.user))
    except Exception as e:
        # Transport failure or unexpected error. Degrade silently — the
        # user can still send a new message. Logged at WARN so it
        # doesn't spam the Error Log on routine AR unavailability.
        frappe.logger("fac.hitl").warning(
            f"get_pending_interrupt({session_id}) failed: {type(e).__name__}: {e}"
        )
        return {"pending": False}

    return result or {"pending": False}
