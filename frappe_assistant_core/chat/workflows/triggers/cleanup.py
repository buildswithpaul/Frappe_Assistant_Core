# Frappe Assistant Core - Powered by FAC Cloud
# Copyright (C) 2026 Paul Clinton
# AGPLv3

"""Daily cleanup of FAC Workflow Trigger Log rows.

Retention: keep rows newer than 30 days. Per-trigger cap of 1000 rows is
enforced when the 30-day window would leave more than that.
"""

import frappe
from frappe.query_builder.functions import Count
from frappe.utils import add_days, now

RETENTION_DAYS = 30
PER_TRIGGER_CAP = 1000


def prune_trigger_logs() -> None:
    """Scheduled daily job — keep logs bounded."""
    # Master gate: no logs accumulate when FAC Chat is off, so skip the
    # delete/sql sweep entirely.
    from frappe_assistant_core.chat.gate import is_chat_enabled

    if not is_chat_enabled():
        return

    cutoff = add_days(now(), -RETENTION_DAYS)

    try:
        # 1) Delete rows older than RETENTION_DAYS.
        frappe.db.delete("FAC Workflow Trigger Log", {"fired_at": ["<", cutoff]})

        # 2) Per-trigger cap: any trigger that still has > PER_TRIGGER_CAP rows
        #    loses the oldest ones beyond the cap. (`trigger` is a reserved word
        #    in MariaDB — Query Builder quotes it correctly.)
        log = frappe.qb.DocType("FAC Workflow Trigger Log")
        rows = (
            frappe.qb.from_(log).select(log.trigger).groupby(log.trigger).having(Count("*") > PER_TRIGGER_CAP)
        ).run()
        triggers = [r[0] for r in rows]
        for trigger_name in triggers:
            keep_names = frappe.get_all(
                "FAC Workflow Trigger Log",
                filters={"trigger": trigger_name},
                fields=["name"],
                order_by="fired_at desc",
                limit=PER_TRIGGER_CAP,
            )
            keep_set = {row.name for row in keep_names}
            all_names = frappe.get_all(
                "FAC Workflow Trigger Log",
                filters={"trigger": trigger_name},
                fields=["name"],
            )
            to_delete = [row.name for row in all_names if row.name not in keep_set]
            if to_delete:
                for name in to_delete:
                    frappe.delete_doc(
                        "FAC Workflow Trigger Log",
                        name,
                        ignore_permissions=True,
                        force=True,
                    )
        frappe.db.commit()
    except Exception:
        frappe.log_error(
            title="FAC Workflow Trigger Log cleanup failed",
            message=frappe.get_traceback(),
        )
