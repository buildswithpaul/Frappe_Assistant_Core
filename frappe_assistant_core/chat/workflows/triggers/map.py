# Frappe Assistant Core - Powered by FAC Cloud
# Copyright (C) 2026 Paul Clinton
# AGPLv3

"""Cached trigger map: {reference_doctype: {doctype_event: [trigger_name, ...]}}.

Mirrors Frappe's Server Script pattern
(frappe/core/doctype/server_script/server_script_utils.py:get_server_script_map).
"""

import frappe

CACHE_KEY = "fac_workflow_trigger_map"


def get_workflow_trigger_map() -> dict:
    """Return the cached trigger map; lazy-builds on first access."""
    cached = frappe.cache.get_value(CACHE_KEY)
    if cached is not None:
        return cached

    trigger_map = _build_trigger_map()
    frappe.cache.set_value(CACHE_KEY, trigger_map)
    return trigger_map


def _build_trigger_map() -> dict:
    """Query all enabled triggers and bucket them by (doctype, event)."""
    try:
        rows = frappe.get_all(
            "FAC Workflow Trigger",
            filters={"enabled": 1},
            fields=["name", "reference_doctype", "doctype_event"],
        )
    except Exception:
        # Table might not exist yet during install — return empty map.
        return {}

    out: dict = {}
    for row in rows:
        if not row.reference_doctype or not row.doctype_event:
            continue
        out.setdefault(row.reference_doctype, {}).setdefault(row.doctype_event, []).append(row.name)
    return out


def invalidate() -> None:
    """Drop the cached map. Called from FAC Workflow Trigger on_update/on_trash."""
    frappe.cache.delete_value(CACHE_KEY)
