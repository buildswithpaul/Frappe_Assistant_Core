# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Stop Migration Plan Tool for Core Plugin (#33995).

Stops a running migration plan once the file importing now is done. What is imported stays.
"""

from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool, exception_message, permission_error_result
from frappe_assistant_core.utils import import_plan


class StopMigrationPlan(BaseTool):
    """Stop a running migration plan after its current file."""

    def __init__(self):
        super().__init__()
        self.name = "stop_migration_plan"
        self.description = (
            "Stop a running migration plan when the user asks: the file importing now finishes, "
            "the files after it aren't imported. What is already imported stays."
        )
        self.requires_permission = None  # checked on the plan
        self.untrusted_fields = ("message", "error")
        self.inputSchema = {
            "type": "object",
            "properties": {"plan": {"type": "string", "description": "The migration plan id"}},
            "required": ["plan"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        plan_name = arguments.get("plan")
        try:
            plan = import_plan.load_plan(plan_name)
        except frappe.DoesNotExistError:
            return {"success": False, "error": _("Migration plan '{0}' not found.").format(plan_name)}
        except frappe.PermissionError as e:
            return permission_error_result(import_plan.SESSION_DOCTYPE, exception_message(e), name=plan_name)
        if plan.status != "Running":
            return {
                "success": False,
                "error": _("Plan {0} is {1}, not running.").format(plan.name, _(plan.status)),
            }
        current = frappe.db.get_value(
            "FAC Import Session", (frappe.parse_json(plan.progress or "{}") or {}).get("current"), "file_name"
        )
        # Written on its own: the run saves the plan between files, and must not find it changed.
        import_plan.request_stop(plan.name)
        if not import_plan.alive(plan):
            # Nothing is running to see the flag (a job that died): the plan ends here.
            import_plan._end(plan.name, "Stopped", _("Stopped, as asked."))
            plan.reload()
            return {
                "success": True,
                "plan": plan.name,
                "status": plan.status,
                "message": _("The plan is stopped. What's imported stays."),
            }
        return {
            "success": True,
            "plan": plan.name,
            "status": plan.status,
            "message": _("The plan stops once {0} is imported. What's imported stays.").format(
                current or _("the current file")
            ),
        }


# Make sure class name matches file name for discovery
stop_migration_plan = StopMigrationPlan
