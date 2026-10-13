# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Relay events → one Raven message, edited in place while FACO writes."""

import time
from collections.abc import Callable

import frappe
from frappe import _
from frappe.utils import escape_html

from frappe_assistant_core.integrations.raven import formatting

SAVE_EVERY = 1.0
TERMINAL = ("stream_complete", "stream_error", "stream_aborted", "approval_required")


class ReplyWriter:
    """Where the sink writes: the Raven message and Raven's bot status strip."""

    def update(self, html: str) -> None:
        raise NotImplementedError

    def status(self, text: str | None) -> None:
        raise NotImplementedError


class RavenReplyWriter(ReplyWriter):
    """Edits the bot's reply from the relay thread, committing so Raven's realtime edit fires."""

    def __init__(self, reply_name: str, channel_id: str, bot_user: str):
        self.reply_name, self.channel_id, self.bot_user = reply_name, channel_id, bot_user

    def update(self, html: str) -> None:
        if not frappe.db.exists("Raven Message", self.reply_name):
            return  # deleted by the asker: that was their Stop
        doc = frappe.get_doc("Raven Message", self.reply_name)
        doc.text = html
        doc.flags.is_ai_streaming = True  # not marked "edited"
        doc.flags.editing_metadata = True  # Raven publishes message_edited only with this set
        doc.save(ignore_permissions=True)
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — relay thread, not a request; each edit must reach Raven.

    def status(self, text: str | None) -> None:
        if text:
            event, payload = "ai_event", {"text": text, "channel_id": self.channel_id, "bot": self.bot_user}
        else:
            event, payload = "ai_event_clear", {"channel_id": self.channel_id}
        frappe.publish_realtime(
            event, payload, doctype="Raven Channel", docname=self.channel_id, after_commit=True
        )


class ReplySink:
    """Follows one turn's relay events; saves at most once per SAVE_EVERY, and always at the end."""

    def __init__(self, writer: ReplyWriter, session_url: str, *, clock: Callable[[], float] = time.monotonic):
        self.writer, self.session_url, self.clock = writer, session_url, clock
        self.text, self.last_save, self.done = "", None, False

    def __call__(self, event: dict) -> None:
        if self.done:
            return
        kind = event.get("event")
        if kind == "stream_chunk":
            self.text = event.get("accumulated") or self.text + (event.get("chunk") or "")
            due = self.last_save is None or self.clock() - self.last_save >= SAVE_EVERY
            if self.text.strip() and due:
                self._save(self.text)
        elif kind == "tool_call_start":
            self.writer.status(_describe_tool(event.get("input") or {}))
        elif kind == "thinking":
            self.writer.status(_("FAC Bot is thinking…"))
        elif kind in TERMINAL:
            self._finish(kind, event)

    def _save(self, markdown: str, extra_html: str = "") -> None:
        text_html = formatting.to_raven_html(markdown, self.session_url) if markdown.strip() else ""
        self.writer.update(text_html + extra_html)
        self.last_save = self.clock()

    def _finish(self, kind: str, event: dict) -> None:
        if kind == "stream_complete":
            self._save(event.get("full_response") or self.text)
        elif kind == "approval_required":
            handoff = formatting.handoff_html(
                event.get("tool_name") or "", event.get("input") or {}, self.session_url
            )
            self._save(self.text, handoff)
        elif kind == "stream_aborted":
            self._save(f"{event.get('partial_response') or self.text}\n\n_{formatting.STOPPED}_")
        else:
            self.writer.update(f"<p>{escape_html(formatting.error_text(event))}</p>")
        self.writer.status(None)
        self.done = True


def _describe_tool(tool_input: dict) -> str:
    target = " ".join(str(v) for v in (tool_input.get("doctype"), tool_input.get("name")) if v)
    return _("FAC Bot is reading {0}…").format(target) if target else _("FAC Bot is working…")
