# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Plan Migration Tool for Core Plugin (#33995).

Groups the user's import sessions into one migration plan and orders them so a file comes after
the files whose records it links to. Called again with the plan, it adds sessions and orders
again.
"""

from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool, exception_message, permission_error_result
from frappe_assistant_core.utils import import_plan
from frappe_assistant_core.utils.import_mapping import SESSION_DOCTYPE, load_session


class PlanMigration(BaseTool):
    """Make or extend a migration plan from import sessions, ordered masters first."""

    def __init__(self):
        super().__init__()
        self.name = "plan_migration"
        self.description = (
            "Group the import sessions of one migration into a plan, ordered so each file comes "
            "after the files whose records it links to (Item Groups before Items, Items before Item "
            "Prices); opening stock, invoices and balances last. Use it when the user migrates "
            "several files, or wants to approve the whole migration once: open every file's session "
            "first, then pass them all. Pass plan to add sessions to an existing plan (it orders "
            "again), order to set the order yourself, and failure_rule if the user already chose it. "
            "Show the user the files in "
            "order with each reason, and any problems. opening_setup is for opening stock, invoices "
            "and balances: use its company without asking (companies: ask which); ask the cut-off "
            "once, now, on ONE ask_user single_select card of cut_off_choices (never as text to "
            "type, never a guessed year), set every opening file to it, and pass it here as cut_off "
            "(plan, no sessions). Next: map each file, then dry_run_import with the plan."
        )
        self.requires_permission = None  # checked on the plan and on each session
        # File names and reasons quote the user's files (#34003).
        self.untrusted_fields = ("files", "problems", "error")

        self.inputSchema = {
            "type": "object",
            "properties": {
                "sessions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "The import session ids to add to the plan.",
                },
                "plan": {
                    "type": "string",
                    "description": "An existing plan to add them to. Left out, a new plan is made.",
                },
                "order": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "The plan's session ids in the order to import them, when the user "
                    "wants another order than the one worked out (files that link to each other, or a "
                    "file that must come first). Files left out of it go after.",
                },
                "cut_off": {
                    "type": "string",
                    "description": "The cut-off date the user picked, YYYY-MM-DD: the plan's check then "
                    "doesn't ask it again.",
                },
                "failure_rule": {
                    "type": "string",
                    "enum": ["leave_out", "stop"],
                    "description": "What happens to rows that fail when their file comes up: leave_out "
                    "(default) leaves them out with their reason; stop stops the plan before that file.",
                },
            },
            "required": ["sessions"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        names = arguments.get("sessions")
        plan_name = arguments.get("plan")
        fixed_order = arguments.get("order")
        if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
            return {"success": False, "error": _("sessions must be a list of import session ids.")}
        if fixed_order is not None and (
            not isinstance(fixed_order, list) or not all(isinstance(n, str) for n in fixed_order)
        ):
            return {"success": False, "error": _("order must be a list of import session ids.")}
        if not names and not plan_name:
            return {"success": False, "error": _("Pass the import sessions to plan.")}

        try:
            plan = import_plan.load_plan(plan_name) if plan_name else None
        except frappe.DoesNotExistError:
            return {"success": False, "error": _("Migration plan '{0}' not found.").format(plan_name)}
        except frappe.PermissionError as e:
            return permission_error_result(SESSION_DOCTYPE, exception_message(e), name=plan_name)
        if plan_name and plan.status not in import_plan.OPEN:
            return {
                "success": False,
                "error": _("Plan {0} is {1}, so its files can't change.").format(plan.name, _(plan.status)),
            }

        sessions = []
        for name in dict.fromkeys(names):
            try:
                sessions.append(load_session(name))
            except frappe.DoesNotExistError:
                return {"success": False, "error": _("Import session '{0}' not found.").format(name)}
            except frappe.PermissionError as e:
                return permission_error_result(SESSION_DOCTYPE, exception_message(e), name=name)

        problems = import_plan.join_problems(plan.name if plan else None, sessions)
        if problems:
            return {
                "success": False,
                "error": _("The plan was not changed. Fix these and call again."),
                "problems": problems,
            }

        try:
            if not plan:
                plan = import_plan.new_plan(sessions)  # kept on its first file's session (#34351)
            if arguments.get("failure_rule"):
                plan.failure_rule = arguments["failure_rule"]
            if arguments.get("cut_off"):
                cut_off = import_plan.as_date(arguments["cut_off"])
                progress = frappe.parse_json(plan.progress or "{}") or {}
                plan.progress = frappe.as_json({**progress, "cut_off": cut_off})
                plan.log_step("Plan", "Success", _("Cut-off date: {0}.").format(cut_off))
            if fixed_order is not None:
                progress = frappe.parse_json(plan.progress or "{}") or {}
                plan.progress = frappe.as_json({**progress, "fixed_order": list(dict.fromkeys(fixed_order))})
            plan.require_open()  # before any file is linked: a plan that started meanwhile keeps its files
            for session in sessions:
                session.db_set("migration_plan", plan.name)
            plan.status = "Planning"  # a new file has questions of its own
            problems = import_plan.arrange(plan)
            plan.log_step(
                "Plan",
                "Warning" if problems else "Success",
                _("{0} files in order.").format(len(import_plan.children(plan))),
            )
            plan.save_open()
        except import_plan.PlanProblem as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            frappe.log_error(title=_("Plan Migration Error"), message=frappe.get_traceback())
            return {"success": False, "error": exception_message(e)}

        return {
            "success": True,
            **import_plan.describe(plan),
            "problems": problems,
            "opening_setup": import_plan.opening_setup(plan),
        }


# Make sure class name matches file name for discovery
plan_migration = PlanMigration
