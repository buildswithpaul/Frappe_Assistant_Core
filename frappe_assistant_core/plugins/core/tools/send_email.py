# Frappe Assistant Core - Send Email Tool
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

"""
Send Email Tool — queues email via the site's configured Email Account.

Invoked by AR Workflow email nodes via MCP, ensuring emails originate
from the client's domain/SMTP rather than the AR platform.
"""

from typing import Any

import frappe
from frappe import _, _lt

from frappe_assistant_core.core.base_tool import BaseTool, one_line
from frappe_assistant_core.utils.message_body import as_html_body

#: How many recipients the confirmation question names before it says "and N more".
MAX_LISTED_RECIPIENTS = 5


class SendEmail(BaseTool):
    """
    MCP tool that sends email using the Frappe site's configured Email Account.

    Queues the email via ``frappe.sendmail()`` (EmailQueue) so delivery
    is asynchronous and uses the site owner's SMTP configuration.
    """

    def __init__(self):
        super().__init__()
        self.name = "send_email"
        self.description = (
            "Send an email from the Frappe site's configured email account. "
            "Use this when a workflow or agent needs to notify someone by email. "
            "The email is queued for delivery using the site's SMTP settings. "
            "Put the complete email in `message`: the user may see it in an approval card and "
            "choose Send or Reject. Never say it was sent until the tool returns success; if it "
            "is rejected, nothing was sent."
        )
        self.source_app = "frappe_assistant_core"
        self.category = "Communication"
        self.requires_permission = None
        # Lazy: tool instances outlive a request, so it is translated when read, in that request's language.
        self.confirmation_verb = _lt("Send")

        self.inputSchema = {
            "type": "object",
            "properties": {
                "recipients": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of recipient email addresses.",
                },
                "cc": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional CC recipient email addresses.",
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject line.",
                },
                "message": {
                    "type": "string",
                    "description": "Email body content (HTML or plain text).",
                },
                "send_as_html": {
                    "type": "boolean",
                    "default": True,
                    "description": "If true, the message is sent as HTML. If false, plain text.",
                },
            },
            "required": ["recipients", "subject", "message"],
        }

    def confirmation(self, arguments: dict[str, Any]) -> str | None:
        """Asks before every send, naming each addressee field the tool sends to (to and cc).

        None only when there is no recipient: execute() refuses that call and sends nothing.
        """
        if not isinstance(arguments, dict):
            return None
        to = self._addressees(arguments.get("recipients"))
        if not to:
            return None
        cc = self._addressees(arguments.get("cc"))
        subject = one_line(arguments.get("subject"))
        if not cc:
            return _("Send the email '{0}' to {1}?").format(subject, self._listed(to))
        return _("Send the email '{0}' to {1}, cc {2}?").format(subject, self._listed(to), self._listed(cc))

    @staticmethod
    def _addressees(value: Any) -> list[str]:
        """The addresses in a recipients/cc value (a string or a list), whatever else it holds."""
        if isinstance(value, str):
            value = [value]
        elif not isinstance(value, (list, tuple)):
            value = [] if value is None else [value]
        return [one_line(v, 60) for v in value if v and str(v).strip()]

    @staticmethod
    def _listed(addresses: list[str]) -> str:
        listed = ", ".join(addresses[:MAX_LISTED_RECIPIENTS])
        if len(addresses) > MAX_LISTED_RECIPIENTS:
            listed = _("{0} and {1} more").format(listed, len(addresses) - MAX_LISTED_RECIPIENTS)
        return listed

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Queue email via frappe.sendmail() using the site's Email Account."""
        recipients = arguments.get("recipients", [])
        cc = arguments.get("cc", [])
        subject = arguments.get("subject", "")
        message = arguments.get("message", "")

        if not recipients:
            return {"success": False, "error": _("No recipients provided")}

        if not subject.strip():
            return {"success": False, "error": _("Subject cannot be empty")}

        if not message.strip():
            return {"success": False, "error": _("Message body cannot be empty")}

        # Filter out empty strings
        recipients = [r.strip() for r in recipients if r and r.strip()]
        cc = [r.strip() for r in cc if r and r.strip()]

        if not recipients:
            return {"success": False, "error": _("No valid recipients after filtering")}

        try:
            frappe.sendmail(
                recipients=recipients,
                cc=cc or None,
                subject=subject,
                message=as_html_body(message),
                delayed=True,
            )
            return {
                "success": True,
                "message": _("Email queued to {0} recipient(s)").format(len(recipients)),
                "recipients": recipients,
                "subject": subject,
            }
        except Exception as e:
            frappe.log_error(
                title=_("Send Email Tool Error"),
                message=f"Failed to queue email: {e!s}",
            )
            return {"success": False, "error": str(e)}
