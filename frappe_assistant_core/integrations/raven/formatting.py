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

"""FACO's markdown, made fit for Raven: HTML, sanitised, rich blocks reduced to words and a link."""

import html
import re

from frappe import _, _lt
from frappe.utils import md_to_html
from frappe.utils.html_utils import sanitize_html

FENCE = re.compile(r"```(chart|mermaid|callout|metric|steps|accordion|tabs)([^\n]*)\n([\s\S]*?)```")
TITLE = re.compile(r'title="([^"]*)"')
DRAWN = {"chart": "📊", "mermaid": "🔀"}

SWITCHED_OFF = _lt("FAC Bot is switched off on this site.")
NOT_A_MEMBER = _lt("Add FAC Bot to this channel to ask it here.")
INTERRUPTED = _lt("I was interrupted before I finished. Please ask again.")
STOPPED = _lt("Stopped.")
QUOTA = _lt(
    "Your workspace has used all of this month's credits. Ask your workspace admin to upgrade or "
    "buy credits. Your administrator can add credits in FAC Chat → Billing."
)
UNREGISTERED = _lt("This site isn't connected to FAC Cloud. An administrator can connect it in FAC Admin.")
UNREACHABLE = _lt("I couldn't reach FAC Cloud just now. Please try again.")
CHAT_OFF = _lt("FAC Chat is switched off on this site. An administrator can turn it on in FAC Admin.")
NOT_YET = _lt("You can't use FACO yet. Ask your administrator.")


def _fence(match: re.Match, session_url: str) -> str:
    kind, attrs, body = match.group(1), match.group(2), match.group(3)
    if kind in DRAWN:
        title = TITLE.search(attrs)
        label = html.escape(title.group(1)) if title else _("Chart")
        return f"\n\n{DRAWN[kind]} {label} — [{_('view in FAC Chat')}]({session_url})\n\n"
    return f"\n\n{body.strip()}\n\n"


def to_raven_html(markdown: str, session_url: str) -> str:
    text = FENCE.sub(lambda m: _fence(m, session_url), markdown or "")
    return sanitize_html(md_to_html(text) or "")


def _describe(tool_name: str, tool_input: dict) -> str:
    doctype = tool_input.get("doctype")
    name = tool_input.get("name") or tool_input.get("docname") or ""
    if tool_name == "ask_user":
        return _("FACO has a question for you")
    if tool_name == "create_document" and doctype:
        return _("FACO would like to create a {0}").format(doctype)
    if tool_name in ("update_document", "delete_document", "document_action") and doctype:
        verb = {"update_document": _("update"), "delete_document": _("delete")}.get(
            tool_name, tool_input.get("action") or _("change")
        )
        return _("FACO would like to {0} {1} {2}").format(verb, doctype, name).strip()
    return _("FACO would like to run {0}").format(tool_name)


def handoff_html(tool_name: str, tool_input: dict, session_url: str) -> str:
    sentence = html.escape(_describe(tool_name, tool_input or {}))
    link = html.escape(session_url, quote=True)
    label = html.escape(_("Review and approve in FAC Chat →"))
    return f'<p>{sentence}.</p><p><a href="{link}">{label}</a></p>'


def error_text(event: dict) -> str:
    """A plain sentence for a failed turn. Never the error's own text: it can carry internals."""
    if event.get("error_code") == "quota_exhausted":
        return str(QUOTA)
    if event.get("action_required") == "register":
        return str(UNREGISTERED)
    return str(UNREACHABLE)


def refusal_text(access: dict) -> str:
    """What to tell someone can_use_faco() turned away. Chat being off comes with no reason."""
    if access.get("reason"):
        return access["reason"]
    if access.get("status") == "chat_module_disabled":
        return str(CHAT_OFF)
    return str(NOT_YET)
