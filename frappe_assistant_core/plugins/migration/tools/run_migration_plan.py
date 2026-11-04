# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Run Migration Plan Tool for Core Plugin (#33995).

The one approval of a migration plan: creates its masters and imports every file in order in the
background, with no questions after it. Called again, it reports how far the plan got.
"""

from typing import Any, Dict

import frappe
from frappe import _
from frappe.utils import cstr

from frappe_assistant_core.core.base_tool import BaseTool, exception_message, permission_error_result
from frappe_assistant_core.utils import import_plan
from frappe_assistant_core.utils.untrusted_output import as_fenced, unfenced


class RunMigrationPlan(BaseTool):
    """Run an approved migration plan, or report a running one."""

    def __init__(self):
        super().__init__()
        self.name = "run_migration_plan"
        self.description = (
            "Run a migration plan that is Ready to Run, once the user approves: creates the "
            "masters the plan planned, then imports every file in order in the background, each "
            "checked again just before its import, rows that would fail then handled by the plan's "
            "failure rule. Nothing asks the user again. Pass the plan check's last `approval` "
            "exactly: files, rows, masters, cut_off and decisions, so the approval card shows the "
            "user every decision before anything is imported; anything else is refused. Called "
            "again for a plan that is running or done, it only reports: each file's status, "
            "created and left-out counts. Stopping keeps what is imported (stop_migration_plan)."
        )
        self.requires_permission = None  # checked on the plan; each file's import checks its own
        # File names and messages quote the user's files (#34003).
        # The files' names, and each decision line, which quotes the files (#34438).
        self.untrusted_fields = (
            "files[].file_name",
            "files[].reason",
            "message",
            "error",
            "approval.decisions[]",
        )

        self.inputSchema = {
            "type": "object",
            "properties": {
                "plan": {"type": "string", "description": "The migration plan id"},
                "files": {"type": "integer", "description": "How many files the plan imports."},
                "rows": {
                    "type": "integer",
                    "description": "How many rows are ready to import, all files together.",
                },
                "masters": {
                    "type": "integer",
                    "description": "How many missing records the plan creates first.",
                },
                "cut_off": {
                    "type": "string",
                    "description": "The cut-off date of its opening files, '' when it has none.",
                },
                "decisions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Every decision of the plan, one line each, as dry_run_import's "
                    "approval gives them: the user reads them on the approval card.",
                },
            },
            "required": ["plan", "files", "rows", "masters", "cut_off", "decisions"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        plan_name = arguments.get("plan")
        try:
            plan = import_plan.load_plan(plan_name)
        except frappe.DoesNotExistError:
            return {"success": False, "error": _("Migration plan '{0}' not found.").format(plan_name)}
        except frappe.PermissionError as e:
            return permission_error_result(import_plan.SESSION_DOCTYPE, exception_message(e), name=plan_name)
        if plan.status not in import_plan.OPEN:
            # Running or ended: the report, saying nothing was started. Its message would be the
            # last step ("Approved: N files."), which reads as a new approval.
            report = import_plan.result(plan)
            if plan.status == "Running":
                message = _("Plan {0} is already running: nothing was started again.")
            else:
                message = _("Plan {0} already finished ({1}): nothing was started again.")
            report["message"] = message.format(plan.name, _(plan.status))
            return {"success": True, **report, "already": plan.status}

        problem = import_plan.run_problem(plan)
        if not problem:
            figures = import_plan.card_figures(plan)
            asked = {key: arguments.get(key) for key in figures}
            # A line comes back as the model read it: in its fence, a closing tag in it escaped
            asked["decisions"] = [
                as_fenced(unfenced(cstr(line)).strip()) for line in asked["decisions"] or []
            ]
            if asked != {**figures, "decisions": [as_fenced(line) for line in figures["decisions"]]}:
                return {
                    "success": False,
                    "error": _(
                        "The plan imports {files} files, {rows} rows, creates {masters} records first, "
                        "with the cut-off '{cut_off}' and the decisions in approval. Pass approval "
                        "exactly, so the approval card shows the user all of it."
                    ).format(**figures),
                    "plan": plan.name,
                    "approval": figures,
                }
        if problem:
            return {"success": False, "error": problem, "plan": plan.name}
        try:
            import_plan.start(plan)
        except import_plan.PlanProblem as e:
            return {"success": False, "error": str(e), "plan": plan.name}
        except Exception as e:
            frappe.log_error(title=_("Run Migration Plan Error"), message=frappe.get_traceback())
            return {"success": False, "error": exception_message(e), "plan": plan.name}
        plan.reload()
        return {"success": True, **import_plan.result(plan)}


# Make sure class name matches file name for discovery
run_migration_plan = RunMigrationPlan
