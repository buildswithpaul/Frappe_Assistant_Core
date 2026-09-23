# FACO - Data Retention Scheduler
# Copyright (C) 2025 Paul Clinton
#
# AGPL-3.0 License

"""
Daily scheduler that enforces the conversation retention window configured
in FACO Settings.

Addresses FACO-H13 from the 2026-04-21 security audit: unbounded growth of
`FACO Message` and `FACO Usage Log` tables because `archive_session` /
`delete_session` only soft-delete and no scheduler ever reaps them.

Policy (scope decision documented in branch `security/medium-remediation`):
    - Only archived sessions are purged. Active conversations are never
      auto-deleted — users rely on `archive_session` / GDPR erase to opt in.
    - Default window is 180 days; minimum enforced is 30 days so an
      operator cannot accidentally wipe last-week data.
    - Attached File documents are deleted through the ORM so the on_trash
      hook removes the backing bytes from disk.
    - FACO Usage Log is purged on the same window for all users
      (not linked to is_archived — usage log is always historical).
"""

from __future__ import annotations

import frappe
from frappe.utils import add_days, now_datetime

DEFAULT_RETENTION_DAYS = 180
MIN_RETENTION_DAYS = 30
CHUNK_SIZE = 1000


def cleanup_old_messages() -> dict:
    """Daily scheduler entry point. Purges archived messages past retention.

    Returns a dict summarising the deletion counts — useful for the operator
    audit trail written to Error Log.
    """
    # Master gate: nothing to clean up if FAC Chat has never been enabled
    # (and turning it off shouldn't trigger surprise mass deletes).
    from frappe_assistant_core.chat.gate import is_chat_enabled

    if not is_chat_enabled():
        return {"status": "chat_module_disabled"}

    settings = frappe.get_cached_doc("FAC Chat Settings")

    if not getattr(settings, "enable_retention_cleanup", 1):
        return {"status": "disabled"}

    retention_days = int(getattr(settings, "message_retention_days", 0) or 0)
    if retention_days < MIN_RETENTION_DAYS:
        retention_days = DEFAULT_RETENTION_DAYS

    cutoff = add_days(now_datetime(), -retention_days)
    delete_attachments = bool(getattr(settings, "retention_deletes_attachments", 1))

    summary = {
        "status": "success",
        "cutoff": str(cutoff),
        "retention_days": retention_days,
        "messages_deleted": 0,
        "files_deleted": 0,
        "usage_log_deleted": 0,
    }

    summary["messages_deleted"], summary["files_deleted"] = _purge_archived_messages(
        cutoff, delete_attachments
    )
    summary["usage_log_deleted"] = _purge_old_usage_log(cutoff)

    frappe.logger("faco.retention").info(
        f"FACO retention cleanup: cutoff={cutoff} "
        f"retention_days={retention_days} "
        f"messages={summary['messages_deleted']} "
        f"files={summary['files_deleted']} "
        f"usage_log={summary['usage_log_deleted']}"
    )

    return summary


def _purge_archived_messages(cutoff, delete_attachments: bool) -> tuple[int, int]:
    from frappe_assistant_core.chat.doctype.fac_chat_session_state.fac_chat_session_state import (
        FACChatSessionState,
    )

    total_messages = 0
    total_files = 0

    while True:
        rows = frappe.get_all(
            "FAC Chat Message",
            filters={"is_archived": 1, "creation": ["<", cutoff]},
            fields=["name", "session_id"],
            limit_page_length=CHUNK_SIZE,
            order_by="creation asc",
        )
        if not rows:
            break

        message_names = [r.name for r in rows]
        purged_session_ids = list({r.session_id for r in rows if r.session_id})

        if delete_attachments:
            file_names = frappe.get_all(
                "File",
                filters={
                    "attached_to_doctype": "FAC Chat Message",
                    "attached_to_name": ["in", message_names],
                },
                pluck="name",
                limit_page_length=0,
            )
            for fname in file_names:
                try:
                    frappe.delete_doc("File", fname, force=True, ignore_permissions=True)
                    total_files += 1
                except Exception as e:
                    frappe.log_error(
                        title="FACO Retention Cleanup",
                        message=f"Failed to delete File {fname} during retention purge: {e}",
                    )

        frappe.db.delete("FAC Chat Message", {"name": ["in", message_names]})
        total_messages += len(message_names)

        # Delete-with-messages: drop the zero-retention session blob for every
        # purged session so it never outlives its messages (no separate TTL).
        FACChatSessionState.delete_for_sessions(purged_session_ids)

        if len(message_names) < CHUNK_SIZE:
            break

    return total_messages, total_files


def _purge_old_usage_log(cutoff) -> int:
    try:
        deleted = frappe.db.count("FAC Chat Usage Log", {"creation": ["<", cutoff]})
        frappe.db.delete("FAC Chat Usage Log", {"creation": ["<", cutoff]})
        return deleted
    except Exception as e:
        frappe.log_error(
            title="FACO Retention Cleanup", message=f"FACO Usage Log retention purge failed: {e}"
        )
        return 0
