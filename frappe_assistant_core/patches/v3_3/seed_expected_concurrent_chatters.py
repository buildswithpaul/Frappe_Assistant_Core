# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Seed FAC Chat Settings.expected_concurrent_chatters on sites that predate the field.

A Single field added after the site's row existed reads back 0, not its schema default,
so the server-setup check would otherwise size for zero chatters. A value an administrator
has already set is left alone.
"""

import frappe

from frappe_assistant_core.chat.server_setup import DEFAULT_EXPECTED_CHATTERS


def execute():
    if not frappe.db.get_single_value("FAC Chat Settings", "expected_concurrent_chatters"):
        frappe.db.set_single_value(
            "FAC Chat Settings", "expected_concurrent_chatters", DEFAULT_EXPECTED_CHATTERS
        )
