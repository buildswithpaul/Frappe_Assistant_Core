# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Seed defaults for the new hosted vision provider settings (Claude / OpenAI / Gemini).

Frappe's cint() casts None → 0 for Int fields, so DocType JSON defaults are not
applied when the Single DocType is created. This patch sets values for the new
fields only when they are currently empty/None, so we don't clobber anything an
admin has already configured.

API key fields are intentionally left untouched — they have no default.
"""

import frappe

DEFAULTS = {
    "claude_model": "claude-sonnet-4-6",
    "claude_request_timeout": 120,
    "openai_model": "gpt-4o-mini",
    "openai_base_url": "https://api.openai.com/v1",
    "openai_request_timeout": 120,
    "gemini_model": "gemini-2.5-flash",
    "gemini_request_timeout": 120,
}


def execute():
    frappe.reload_doc("assistant_core", "doctype", "assistant_core_settings")

    settings = frappe.get_single("Assistant Core Settings")
    for field, value in DEFAULTS.items():
        current = getattr(settings, field, None)
        if not current:
            frappe.db.set_single_value("Assistant Core Settings", field, value)
