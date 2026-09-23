# FACO - Orphaned chat attachment sweep
# Copyright (C) 2025 Paul Clinton
#
# AGPL-3.0 License

"""Daily job. Chat composer uploads happen on file *selection*, not on send, so
a user who attaches a file and then closes the tab leaves a private File behind
that no message and no retention policy will ever reach.

`upload_message_file` marks every such upload with `fac_pending_chat_attachment`;
`send_message` clears the flag when it links the file to a FAC Chat Message.
Anything still flagged after 24h was never sent, so it is deleted.

Idempotent; per-file delete errors are swallowed so one bad file cannot wedge
the batch.
"""

from __future__ import annotations

import frappe
from frappe.utils import add_to_date, now_datetime

ORPHAN_TTL_HOURS = 24
BATCH_SIZE = 1000


def sweep_orphan_chat_attachments() -> dict:
    """Daily scheduler entry point. Returns a summary for the operator log."""
    from frappe_assistant_core.chat.gate import is_chat_enabled

    if not is_chat_enabled():
        return {"status": "chat_module_disabled", "files_deleted": 0}

    cutoff = add_to_date(now_datetime(), hours=-ORPHAN_TTL_HOURS)
    stale = frappe.get_all(
        "File",
        filters={
            "fac_pending_chat_attachment": 1,
            "creation": ["<", cutoff],
            # Defence in depth: the flag alone is not a safe delete key. A file
            # that did get linked to a message backs a live conversation, even
            # if clearing the flag failed.
            "attached_to_name": ["is", "not set"],
        },
        pluck="name",
        limit=BATCH_SIZE,
    )

    deleted = 0
    for name in stale:
        try:
            frappe.delete_doc("File", name, ignore_permissions=True, force=True)
            deleted += 1
        except Exception as e:
            frappe.log_error(
                title="FACO Orphan Attachment Sweep",
                message=f"Failed to delete File {name}: {e}",
            )

    if deleted:
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — scheduled background job, not a request handler.

    frappe.logger("faco.retention").info(
        f"FACO orphan attachment sweep: cutoff={cutoff} candidates={len(stale)} deleted={deleted}"
    )

    return {"status": "success", "cutoff": str(cutoff), "files_deleted": deleted}
