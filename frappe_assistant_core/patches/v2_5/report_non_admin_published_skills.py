# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Read-only audit patch for security issue #225.

Prior to this fix, any Desk User could publish an FAC Skill with
Shared/Public visibility with no admin review. This patch does not modify
any existing record — it only logs (via frappe.log_error) any pre-existing
Published + Shared/Public skill whose owner is not a System Manager /
Assistant Admin, so an administrator can manually review and, if needed,
revoke or re-scope it.
"""

import frappe

from frappe_assistant_core.utils.permissions import check_assistant_admin_permission


def execute():
    if not frappe.db.table_exists("FAC Skill"):
        return

    exposed_skills = frappe.get_all(
        "FAC Skill",
        filters={
            "status": "Published",
            "visibility": ["in", ("Shared", "Public")],
        },
        fields=["name", "skill_id", "owner_user", "visibility"],
    )

    flagged = [s for s in exposed_skills if not check_assistant_admin_permission(s.owner_user)]

    if flagged:
        frappe.log_error(
            title="FAC Skill: pre-existing non-admin published skills (issue #225)",
            message=(
                "The following FAC Skill records were published with Shared/Public "
                "visibility by a non-admin owner before the #225 permission fix. "
                "They were left untouched — review and re-scope manually if needed:\n\n"
                + "\n".join(
                    f"- {s.name} (skill_id={s.skill_id}, owner={s.owner_user}, visibility={s.visibility})"
                    for s in flagged
                )
            ),
        )
