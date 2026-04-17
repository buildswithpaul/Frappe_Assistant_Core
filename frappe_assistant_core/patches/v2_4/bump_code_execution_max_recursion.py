# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Raise `code_execution_max_recursion` to 500 on existing sites.

The original default of 100 is too tight for Frappe internals — even a
plain `frappe.get_doc(...)` inside `run_python_code` overflows it and
surfaces as a misleading "Recursion limit exceeded" error.

Follows the ERPNext pattern for Single DocType defaults: set
unconditionally in a one-time patch. Runtime checks cannot reliably
distinguish "admin intentionally set 100" from "never touched — still
on the old default", so we don't try.
"""

import frappe


def execute():
    frappe.reload_doc("assistant_core", "doctype", "assistant_core_settings")
    frappe.db.set_single_value("Assistant Core Settings", "code_execution_max_recursion", 500)
