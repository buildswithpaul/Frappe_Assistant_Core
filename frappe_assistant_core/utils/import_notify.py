# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.


"""
FACO says so in the chat when a background check, import or migration plan ends (#34416 AC3): a
message in the conversation that started it, and the open chat reloads to show it. The user no
longer has to ask. Only a job's end posts: a check or import that ran in the request (developer
mode, tests) answered in the tool call itself.
"""

import frappe
from frappe import _

EVENT = "faco_message_stream"  # the chat's own socket event; "message_posted" reloads it


def post(chat: str, text: str) -> None:
    """Post ``text`` in the FAC Chat conversation ``chat``, once the job commits."""
    if not chat or not text or not getattr(frappe.local, "job", None):
        return
    # The id came from the caller's X-AR-Session-Id header: post only in a conversation of the job's user
    if frappe.db.get_value("FAC Chat Conversation", chat, "user") != frappe.session.user:
        return
    from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import FACChatMessage

    try:
        FACChatMessage.create_message(chat, "assistant", text)
        frappe.publish_realtime(
            event=EVENT,
            message={"event": "message_posted", "session_id": chat},
            room=f"task_progress:{chat}",
            after_commit=True,  # the chat re-reads its messages: this one must be saved by then
        )
    except Exception:
        # The import is done and recorded either way; only the message is lost.
        frappe.log_error(title=_("FAC Import: posting the result failed"), message=frappe.get_traceback())


def check_ended(session) -> None:
    summary = frappe.parse_json(session.validation_summary or "{}") or {}
    if summary.get("ready") is None:
        return
    text = _("The check of {0} has finished: {1} rows ready, {2} would fail.").format(
        session.file_name, summary.get("ready") or 0, summary.get("failed") or 0
    )
    text += " " + (
        _("Ask me to go through the rows that would fail.")
        if summary.get("failed")
        else _("Say when to import them.")
    )
    post(session.get("chat_session_id"), text)


def import_ended(session, data_import: str) -> None:
    from frappe_assistant_core.utils import import_run

    post(session.get("chat_session_id"), import_run.result_of(session, data_import).get("message"))


def plan_ended(plan, status: str, message: str) -> None:
    from frappe_assistant_core.utils import import_plan

    lines = [_("Migration plan {0} has ended: {1}. {2}").format(plan.name, _(status), message)]
    for entry in import_plan.result(plan).get("files") or []:
        lines.append(
            _("- {0} ({1}): {2}, {3} created, {4} left out.").format(
                entry.get("file_name"),
                _(entry.get("doctype") or ""),
                _(entry.get("status") or ""),
                entry.get("created") or 0,
                entry.get("left_out") or 0,
            )
        )
    # A plan is kept on its first file's session, which has the conversation
    chat = frappe.db.get_value(import_plan.SESSION_DOCTYPE, plan.name, "chat_session_id")
    post(chat, "\n".join(lines))
