# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Start Import Tool for Core Plugin (#33993).

Imports an import session's checked file through Frappe's own Data Import, after one approval,
and continues an import that was interrupted.
"""

import random
import time
from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool, exception_message, permission_error_result
from frappe_assistant_core.utils import import_plan, import_run
from frappe_assistant_core.utils.import_mapping import SESSION_DOCTYPE, load_session
from frappe_assistant_core.utils.import_session import FileProblem


class StartImport(BaseTool):
    """Import a checked session's file through Data Import, or continue its import."""

    def __init__(self):
        super().__init__()
        self.name = "start_import"
        self.description = (
            "Import an import session's file into ERPNext through Frappe's Data Import, once the "
            "user approves. Only after dry_run_import said the file is ready, and only when the "
            "user asks to import. Pass doctype, rows (the check's 'ready' count), import_type and "
            "validated_fingerprint exactly as the last check reported them, with the session's "
            "file_name and submit_after_import: the approval card shows them, and they must "
            "match, so what is imported is what the user saw checked. The import runs in the background: "
            "don't poll it. FAC Chat shows its progress by itself; say it is running, and when the user "
            "asks how far it is, read list_documents on 'Data Import Log' filtered by data_import once "
            "(total_count with success 1 is the count imported) against the reply's total. It has "
            "ended only when the session's status "
            "(get_document) is no longer Importing: then its last step gives created, failed and "
            "left-out counts with row numbers. If it stopped (Data Import status Timed Out, or no "
            "progress for minutes), call again to continue, with rows the rows still to import (the "
            "refusal says how many): records already imported are skipped, never duplicated. If rows failed, the reply groups and explains "
            "them, with what to do next: once the user has fixed the causes and asks to try those "
            "again, check them with dry_run_import (it checks only the rows not imported yet), "
            "then call this with its counts: a new Data Import imports just those rows, with the "
            "fixes, and the session reports every run. Not for a session in a migration plan: "
            "run_migration_plan imports the plan's files."
        )
        self.requires_permission = None  # checked on the session, the DocType and Data Import
        # what the user's file says reaches the model fenced (#34003)
        self.untrusted_fields = ("failed_rows", "left_out", "message", "error")

        self.inputSchema = {
            "type": "object",
            "properties": {
                "session": {"type": "string", "description": "The import session id"},
                "doctype": {"type": "string", "description": "The DocType imported, as the last check said"},
                "rows": {
                    "type": "integer",
                    "description": "Rows to import: the last check's 'ready'; continuing an "
                    "interrupted import, the rows still to import",
                },
                "import_type": {
                    "type": "string",
                    "enum": ["Insert New Records", "Update Existing Records"],
                    "description": "New records or updates, as the last check said",
                },
                "validated_fingerprint": {
                    "type": "string",
                    "description": "The last check's validated_fingerprint, from dry_run_import's "
                    "reply: 12 characters, as given",
                },
                "file_name": {"type": "string", "description": "The session's file_name: the file imported"},
                "submit_after_import": {
                    "type": "boolean",
                    "description": "The session's submit_after_import: whether imported records are submitted",
                },
            },
            # validated_fingerprint, file_name and submit_after_import are required by check_card,
            # with its own message: a session imported another way is pointed to its tool first.
            "required": ["session", "doctype", "rows", "import_type"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        # A start that collided with another import saving at the same moment was undone whole
        # by the database, and nothing before it in this call wrote anything: the call runs
        # again from the start, after a short random wait, so the user isn't asked to (BT-17).
        for attempt in range(1, import_run.START_ATTEMPTS + 1):
            try:
                return self._execute(arguments)
            except import_run.StartCollided as e:
                if attempt == import_run.START_ATTEMPTS:
                    return {"success": False, "error": str(e), "session": arguments.get("session")}
                time.sleep(random.uniform(0.1, 0.5))

    def _execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        session_name = arguments.get("session")
        try:
            session = load_session(session_name)
        except frappe.DoesNotExistError:
            return {"success": False, "error": _("Import session '{0}' not found.").format(session_name)}
        except frappe.PermissionError as e:
            return permission_error_result(SESSION_DOCTYPE, exception_message(e), name=session_name)
        refused = import_plan.imported_by_its_plan(session)
        if refused:
            return {"success": False, "error": refused, "session": session_name}

        from frappe_assistant_core.utils.import_dry_run import special_engine

        engine = special_engine(session)
        if engine:
            return {
                "success": False,
                "error": _("This session is imported with {0}, not through Data Import.").format(
                    engine.IMPORT_TOOL
                ),
                "session": session_name,
            }

        try:
            resuming = session.status == import_run.IMPORTING
            if not resuming or import_run.continues(session):  # else it only reports: nothing starts
                import_run.check_card(
                    session,
                    arguments.get("doctype"),
                    arguments.get("rows"),
                    arguments.get("import_type"),
                    arguments.get("validated_fingerprint"),
                    arguments.get("file_name"),
                    arguments.get("submit_after_import"),
                    left=import_run.rows_left(session) if resuming else None,
                )
            problem = import_run.cannot_import(
                session.target_doctype, session.import_type or "Insert New Records"
            )
            if problem:
                raise import_run.ImportProblem(problem)
            if session.status == "Completed":
                raise import_run.ImportProblem(
                    _("This file was already imported, in Data Import {0}.").format(
                        session.data_imports[-1].data_import
                    )
                )
            if session.status == import_run.IMPORTING:
                data_import, state = import_run.resume(session)
            else:
                data_import, state = import_run.start(session), "started"
        except import_run.StartCollided:
            raise
        except import_run.NothingToChange as e:
            return {"success": True, "session": session_name, "status": "Completed", "message": str(e)}
        except (import_run.ImportProblem, FileProblem) as e:
            return {"success": False, "error": str(e), "session": session_name}
        except frappe.QueryDeadlockError:
            raise  # the database undid the call: _safe_execute runs it again or says so
        except Exception as e:
            frappe.log_error(title=_("Start Import Error"), message=frappe.get_traceback())
            return {"success": False, "error": exception_message(e), "session": session_name}

        session.reload()
        result = import_run.result_of(session, data_import)
        queued = state == "running" or (state in ("started", "continued") and not import_run._runs_now())
        if queued:
            # Queued or still running in the background: what the Data Import shows now is from
            # before this run (a retry's old counts, say), not its end.
            result["state"] = state
            result["message"] = _(
                "Importing {0} {1} records in the background ({2} done so far). Follow it with "
                "get_document on Data Import {3}."
            ).format(
                # A queued Data Import hasn't counted its records yet: the check has.
                result["total"] or arguments.get("rows"),
                _(session.target_doctype),
                result["created"],
                data_import,
            )
        return {"success": True, "session": session.name, **result}


# Make sure class name matches file name for discovery
start_import = StartImport
