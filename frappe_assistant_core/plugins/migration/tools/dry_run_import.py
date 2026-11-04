# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Dry Run Import Tool for Core Plugin.

Checks every row of an import session's file the way the real import would, and
writes nothing. The full per-row result goes on the session; the model gets the
grouped summary.

Given a migration plan instead (#33995), it checks every file of the plan in its order and lists
every open question of the plan in one list, with the user's answers applied in one call. Once
nothing is left, the plan is Ready to Run.
"""

from typing import Any, Dict, List

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool, exception_message, permission_error_result
from frappe_assistant_core.utils import import_dry_run as dry_run
from frappe_assistant_core.utils import import_failures, import_fixes, import_plan
from frappe_assistant_core.utils.import_mapping import SESSION_DOCTYPE, load_session
from frappe_assistant_core.utils.import_session import (
    FileProblem,
    discard_sheet_copy,
    file_from_google_sheet,
    find_site_file,
)


class DryRunImport(BaseTool):
    """Check every row of an import session's file without importing anything."""

    def __init__(self):
        super().__init__()
        self.name = "dry_run_import"
        self.description = (
            "Check every row of an import session's file the way the real import would, writing "
            "nothing: required fields, links, duplicates (in the file and already in ERPNext) and "
            "ERPNext's own rules. Call it once the columns are mapped, and again after fixes. "
            "Returns '<n> rows ready, <m> would fail' and the failures grouped by cause, each with "
            "a count and up to 3 example rows; show the user that, not row-by-row lists. Files of "
            f"more than {dry_run.BACKGROUND_ROWS} rows (fewer for invoices and other submitted "
            "documents, whose rows take longer) are checked in the background: say so, and "
            "read the session with get_document later (progress, then validation_summary, which "
            "holds this same reply). The file must be on this site: if the session's file is only "
            "in the chat, ask the user to upload it in File Manager (or attach it in FAC Chat) and "
            "pass its file_id; the user must be allowed to read it. A different file passed as "
            "file_id or file_url puts back the rows left out before. Each group comes with a plain "
            "explanation and the fixes that fit it: explain it and offer only those fixes. For an Update "
            "Existing Records session the reply also has update: records_changing, fields_changing, "
            "by_field (how many records change each field) and up to 5 samples with each field's old "
            "and new value: show the user those as a table before asking to import. Rows that change "
            "nothing are counted in unchanged and skipped. Then "
            "call again with the user's choices in fixes: they are saved on the session and every "
            "row is checked again. Per group: 'map' a value to an existing one ('to': one of the "
            "group's 'closest' names, or one the user gives; never invent one), or 'leave_out' "
            "its rows (with a reason; the import skips and lists them). To create a missing "
            "record, use create_document, then call again without fixes. Nothing is saved if any "
            "fix is wrong. A group keeps its id from check to check; once its rows pass, the id is "
            "gone. After an import that didn't get every row in, call it again once the causes are "
            "fixed: it checks only the rows not imported yet ('imported' counts the rest), and "
            "start_import then imports just those. failed_rows_file: true checks nothing; it gives "
            "the rows still not imported (failed, or left out) as an Excel file with the error for "
            "each and FACO's fix when it has one, "
            "for the user to correct and upload: show its download_url. The corrected file comes "
            "back as file_id (or file_url), and is checked like any other. When the user fixed "
            "a Google Sheet the session came from, pass its google_sheets_url again: a fresh copy "
            "is checked, and the mapping is kept. For a session in a migration plan, records the "
            "plan's earlier files create count as there, and the user's questions go through the "
            "plan: pass plan instead of session. "
            "With plan, it checks every file of a migration plan again, in the plan's order, and "
            "lists every open question of the plan, so the user answers them all before one "
            "approval: files still to map (kind structure), files that link to each other (order), "
            "each group of rows that would fail with the fixes that fit it (fix), the cut-off date "
            "of opening stock, invoices and balances (cut_off: ask the user, never guess it), and "
            "what happens to rows that still fail when their file comes up (failure_rule). Ask "
            "once: 'table' holds the plan's files in order with each one's reason, and every "
            "question with its suggested answer; show it as it is in your message's text (never "
            "only in your thinking: the user doesn't see it) and as the card's description, with "
            "what needed_by says; then ONE single-choice card (ask_user single_select, never "
            "multi_select): 'Apply all suggested answers and start (cut-off <date>)' or 'Let me "
            "change some'. 'Apply all' answers each fix question with its 'suggested'. A question "
            "with nothing suggested gets its own single-choice card. Never questions as text to "
            "type answers to. Map files yourself where you are sure. Then call again with plan and "
            "answers: [{id, ...}], a fix's fields as fixes take them (action map/leave_out/"
            "create...; create plans a missing record that the plan creates when it runs), {id: "
            "'plan:cut_off', date}, or {id: 'plan:failure_rule', rule}. All answers apply or none. "
            "When ready is true, the plan is Ready to Run: next run_migration_plan, given approval "
            "exactly."
        )
        self.requires_permission = None  # checked on the session and the target DocType
        # What the user's file says reaches the model fenced (#34003). A plan's check fences what
        # the files say: their names, columns and values. FAC's own directions in a question's
        # message are not (#34438). A fix question's message is ERPNext's refusal quoting the file;
        # an order, waiting or blocked one names the files. Each decision line of the approval is
        # fenced on its own, so it is still a list of lines run_migration_plan is given back (it
        # takes them with or without their fence).
        self.untrusted_fields = (
            "groups",
            "masters_plan",
            "left_out",
            "problems",
            "applied",
            "update",
            "error",
            "questions[kind=fix].message",
            "questions[kind=order].message",
            "questions[kind=waiting].message",
            "questions[kind=blocked].message",
            "questions[kind=fix].explanation",
            "questions[kind=fix].fixes",
            "questions[kind=fix].suggested",
            "questions[].file_name",
            "questions[].columns",
            "questions[].dates",
            "questions[].file_names_say",
            "questions[].needed_by",
            "files[].file_name",
            "files[].reason",
            "approval.decisions[]",
            "table",
        )

        self.inputSchema = {
            "type": "object",
            "properties": {
                "session": {"type": "string", "description": "The import session id: one file"},
                "plan": {
                    "type": "string",
                    "description": "Instead of session: the migration plan id, to check every file of "
                    "the plan and list all its questions",
                },
                "answers": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "With plan: the user's answers, each with the id of its question.",
                },
                "file_id": {
                    "type": "string",
                    "description": "When the session's file is just in the chat: the ID of the same "
                    "file on this site (its name in File Manager). Or of the user's corrected file of "
                    "failed rows. Its columns must match.",
                },
                "file_url": {
                    "type": "string",
                    "description": "Instead of file_id: the file's URL on this site, e.g. a FAC Chat "
                    "attachment's.",
                },
                "google_sheets_url": {
                    "type": "string",
                    "description": "Instead of a file: a Google Sheets link, to check the sheet as it "
                    "is now, e.g. after the user fixed it. Its columns must match.",
                },
                "failed_rows_file": {
                    "type": "boolean",
                    "description": "True to get the rows still not imported, with the reason for "
                    "each, as a file to download. Nothing is checked.",
                },
                "fixes": {
                    "type": "array",
                    "description": "The user's fixes for the last check's groups, one per group, "
                    "applied together before checking again.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "group": {"type": "string", "description": "Group id, e.g. 'G3fa2c1'"},
                            "action": {"type": "string", "enum": list(import_fixes.ACTIONS)},
                            "to": {
                                "type": "string",
                                "description": "For 'map': the existing value to use instead.",
                            },
                            "reason": {
                                "type": "string",
                                "description": "For 'leave_out': why, in the user's words.",
                            },
                        },
                        "required": ["group", "action"],
                    },
                },
            },
            "required": [],  # session or plan: execute says which is missing
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        session_name = arguments.get("session")
        plan_name = arguments.get("plan")
        if bool(session_name) == bool(plan_name):
            return {
                "success": False,
                "error": _(
                    "Give session to check one file, or plan to check every file of a migration plan: "
                    "session or plan, one of them."
                ),
            }
        if plan_name:
            return self._check_plan(plan_name, arguments)
        if arguments.get("answers"):
            return {
                "success": False,
                "error": _(
                    "answers are a plan's: pass plan with them. A session takes its choices as fixes."
                ),
            }
        # Clients fill optional inputs in, so an empty list means no fixes, as a missing one does.
        fixes = arguments.get("fixes") or None
        file_id = (arguments.get("file_id") or "").strip()
        file_url = (arguments.get("file_url") or "").strip()
        sheet_url = (arguments.get("google_sheets_url") or "").strip()
        if sheet_url and (file_id or file_url):
            return {
                "success": False,
                "error": _("Give only the Google Sheets link, or only a file: not both."),
            }
        if fixes is not None and (not isinstance(fixes, list) or not all(isinstance(f, dict) for f in fixes)):
            return {"success": False, "error": _("fixes must be a list of {group, action, ...}.")}
        try:
            session = load_session(session_name)
        except frappe.DoesNotExistError:
            return {"success": False, "error": _("Import session '{0}' not found.").format(session_name)}
        except frappe.PermissionError as e:
            return permission_error_result(SESSION_DOCTYPE, exception_message(e), name=session_name)

        if arguments.get("failed_rows_file"):
            if fixes or file_id or file_url or sheet_url:
                return {
                    "success": False,
                    "error": _("failed_rows_file is asked on its own, without fixes or a file."),
                }
            try:
                return {"success": True, **import_failures.failed_rows_file(session)}
            except (import_failures.FailuresProblem, FileProblem) as e:
                return {"success": False, "error": str(e), "session": session_name}
            except Exception as e:
                frappe.log_error(title=_("Failed Rows File Error"), message=frappe.get_traceback())
                return {"success": False, "error": str(e), "session": session_name}

        copy = None  # a Google Sheet's fresh download, deleted once read
        try:
            if dry_run.is_running(session):
                if fixes:
                    raise dry_run.DryRunProblem(
                        _("The file is still being checked. Apply the fixes once the check has finished.")
                    )
                return self._running(session)
            notice = None
            if sheet_url:
                new_file = copy = file_from_google_sheet(sheet_url)
            else:
                # Read access is checked here, before the file is compared or linked.
                new_file = find_site_file(file_id=file_id, file_url=file_url) if file_id or file_url else None
            # The session's own file passed again (as a client may) is no new file: nothing to link.
            if new_file and not _is_sessions_file(session, new_file):
                if fixes:
                    raise dry_run.DryRunProblem(
                        _(
                            "This file isn't the session's. Check it first, without fixes: fixes "
                            "apply to the groups its check finds."
                        )
                    )
                dry_run.check_status(session)  # a session that can't be checked keeps its file
                before = session.source_file
                # The session reads its own copy of it now (#34405): a Google Sheet's download goes.
                dry_run.link_site_file(session, new_file, sheet_url or None)
                if before and not _same_content(before, session.source_file):
                    notice = import_fixes.forget_left_out(session)
            if fixes and session.status not in import_failures.AFTER_CHECK:
                raise dry_run.DryRunProblem(
                    _("Check the file first, without fixes; fixes apply to the groups it finds.")
                )
            if fixes and not import_fixes.checked_as_is(session):
                if import_fixes.fixed_unchecked(session):
                    # The file and mapping are as checked; the fixes sent before are saved (#34607)
                    raise dry_run.DryRunProblem(
                        _(
                            "Your fixes are already applied but weren't checked yet. Check again without fixes."
                        )
                    )
                # The groups are the last check's: of another file (its check stopped), or of
                # another mapping. Their rows aren't the session's rows now.
                raise dry_run.DryRunProblem(
                    _(
                        "The file changed since its last check. Check it first, without fixes: "
                        "fixes apply to the groups that check finds."
                    )
                )
            dry_run.check_can_run(session)

            applied = None
            if fixes:
                applied = import_fixes.apply_fixes(session, import_fixes.last_groups(session), fixes)
                session.save()

            if dry_run.check_cost(session) > dry_run.BACKGROUND_ROWS:
                dry_run.enqueue(session)
                return self._running(session, applied, notice)

            reply = import_fixes.check(session.name)
        except import_fixes.FixProblems as e:
            return {"success": False, "error": str(e), "problems": e.problems, "session": session_name}
        except (import_fixes.FixProblem, dry_run.DryRunProblem, FileProblem) as e:
            return {"success": False, "error": str(e), "session": session_name}
        except Exception as e:
            frappe.log_error(title=_("Dry Run Import Error"), message=frappe.get_traceback())
            return {"success": False, "error": str(e), "session": session_name}
        finally:
            discard_sheet_copy(copy)

        result = {"success": True, **reply}
        if applied:
            result["applied"] = applied
        if notice:
            result["notice"] = notice
        return result

    def _check_plan(self, plan_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Every open question of the migration plan, its files checked again first, or the user's
        answers applied to them."""
        given = [
            name
            for name in ("fixes", "file_id", "file_url", "google_sheets_url", "failed_rows_file")
            if arguments.get(name)
        ]
        if given:
            return {
                "success": False,
                "error": _(
                    "{0} is for one file's session, not a plan: check the plan with its answers only."
                ).format(", ".join(given)),
            }
        answers = arguments.get("answers") or []
        if not isinstance(answers, list):
            return {"success": False, "error": _("answers must be a list.")}
        try:
            plan = import_plan.load_plan(plan_name)
        except frappe.DoesNotExistError:
            return {"success": False, "error": _("Migration plan '{0}' not found.").format(plan_name)}
        except frappe.PermissionError as e:
            return permission_error_result(import_plan.SESSION_DOCTYPE, exception_message(e), name=plan_name)
        if plan.status not in import_plan.OPEN:
            return {
                "success": False,
                "error": _("Plan {0} is {1}: it has no questions left.").format(plan.name, _(plan.status)),
            }
        applied = []
        try:
            applied = import_plan.apply_answers(plan, answers) if answers else []
            plan.reload()
            result = import_plan.open_questions(plan)
        except import_fixes.FixProblems as e:
            return _failed(str(e), applied, problems=e.problems)
        except (import_plan.PlanProblem, import_fixes.FixProblem) as e:
            return _failed(str(e), applied)
        except Exception as e:
            frappe.log_error(title=_("Plan Check Error"), message=frappe.get_traceback())
            return _failed(exception_message(e), applied)
        if applied:
            result["applied"] = applied
        result["next"] = _next(result, bool(answers))
        return {"success": True, **result}

    @staticmethod
    def _running(session, applied=None, notice=None) -> Dict[str, Any]:
        progress = frappe.parse_json(session.progress or "{}") or {}
        result = {
            "success": True,
            "session": session.name,
            "state": "running",
            "done": progress.get("done", 0),
            "total_rows": dry_run.row_count(session),
            "message": _(
                "Checking every row in the background. Read the session with get_document to see "
                "progress; the result will be in validation_summary."
            ),
        }
        if applied:
            result["applied"] = applied
        if notice:
            result["notice"] = notice
        return result


def _is_sessions_file(session, file_doc) -> bool:
    """Whether ``file_doc`` holds the same bytes as the session's file: its own copy, or the file
    the user gave, which the copy was read from (#34405)."""
    return any(
        name and _same_content(name, file_doc.name) for name in (session.source_file, session.original_file)
    )


def _same_content(file_a: str, file_b: str) -> bool:
    """Whether two File records hold the same bytes, so the same rows."""
    if file_a == file_b:
        return True
    hashes = [frappe.db.get_value("File", name, "content_hash") for name in (file_a, file_b)]
    return bool(hashes[0]) and hashes[0] == hashes[1]


def _failed(error: str, applied: List[Any], **extra) -> Dict[str, Any]:
    """A refusal. Answers apply_answers already applied stay applied (it releases its savepoint),
    so the reply says so, not that nothing changed (#34438)."""
    reply = {"success": False, "error": error, **extra}
    if applied:
        reply["applied"] = applied
        reply["error"] = (
            error
            + " "
            + _(
                "The answers listed in applied were applied before this; call dry_run_import with the plan again."
            )
        )
    return reply


def _next(result: Dict[str, Any], answered: bool) -> str:
    """What to do with the result: FACO otherwise asks again what the one card already asked."""
    if result.get("ready") and answered:
        return (
            "If the user chose 'Apply all suggested answers and start', call run_migration_plan now "
            "with approval exactly: they already said start, ask nothing more."
        )
    if result.get("ready"):
        return (
            "Show approval.decisions as a table in your message, then ONE ask_user single_select: "
            "'Start the migration (cut-off <date>)' or 'Not yet'."
        )
    if any(q.get("kind") in ("checking", "structure") for q in result.get("questions") or []):
        return "Map or wait for the files the questions name, then call dry_run_import with the plan again."
    return (
        "Show 'table' as it is (the text inside its fence) in your message, and as the ask_user "
        "card's description: the user can't choose on questions they haven't seen. Then ONE "
        "ask_user single_select: 'Apply all suggested answers and start (cut-off <date>)' or 'Let "
        "me change some'. No other card. 'Apply all' answers each fix question with its 'suggested'."
    )


# Make sure class name matches file name for discovery
dry_run_import = DryRunImport
