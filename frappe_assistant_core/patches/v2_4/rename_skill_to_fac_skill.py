# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Migration patch to rename Skill DocType to FAC Skill.

Avoids naming conflict with HRMS Skill DocType.
"""

import frappe


def execute():
    """Rename Skill DocType to FAC Skill for existing sites."""
    if frappe.db.exists("DocType", "Skill"):
        frappe.rename_doc("DocType", "Skill", "FAC Skill", force=True)

    frappe.reload_doc("assistant_core", "doctype", "fac_skill")
