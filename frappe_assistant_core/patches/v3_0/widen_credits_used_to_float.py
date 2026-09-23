# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Widen FAC Chat Message.credits_used from Int to Float and backfill fractions.

Credits are fractional (a cheap turn can cost 0.4 credits), but the column was
Int, so every sub-1.0 turn stored as 0 and the Usage page under-reported totals.
The doctype JSON is now Float; reload it so the column widens even on a
schema-only migrate.

Historical single-model rows already lost their fractions on the original Int
write — unrecoverable, left as-is (non-destructive). Multi-model (delegating)
turns kept exact per-model floats in the ``model_breakdown`` JSON, so for those
rows we recompute ``credits_used`` as the sum of those floats — recovering the
precision the Int column had discarded.
"""

import json

import frappe


def execute():
    if not frappe.db.table_exists("FAC Chat Message"):
        return

    # Widen the column (Int -> Float) from the updated doctype JSON.
    frappe.reload_doc("chat", "doctype", "fac_chat_message", force=True)

    rows = frappe.get_all(
        "FAC Chat Message",
        filters={"model_breakdown": ["is", "set"]},
        fields=["name", "credits_used", "model_breakdown"],
    )

    repaired = 0
    for row in rows:
        exact = _sum_breakdown_credits(row.model_breakdown)
        if exact is None:
            continue
        # Only rewrite when the stored (truncated) value actually differs, so we
        # don't churn rows that were already whole numbers.
        if abs((row.credits_used or 0) - exact) < 0.005:
            continue
        frappe.db.set_value(
            "FAC Chat Message",
            row.name,
            "credits_used",
            round(exact, 2),
            update_modified=False,
        )
        repaired += 1

    frappe.logger().info(
        f"widen_credits_used_to_float: backfilled {repaired} delegating-turn rows from model_breakdown"
    )


def _sum_breakdown_credits(raw):
    """Sum per-model ``credits`` floats from a model_breakdown JSON value.

    Returns None for missing/malformed data so the caller skips the row.
    """
    if not raw:
        return None
    try:
        data = raw if isinstance(raw, list) else json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, list):
        return None
    total = 0.0
    seen = False
    for entry in data:
        if isinstance(entry, dict) and entry.get("credits") is not None:
            try:
                total += float(entry["credits"])
                seen = True
            except (TypeError, ValueError):
                return None
    return total if seen else None
