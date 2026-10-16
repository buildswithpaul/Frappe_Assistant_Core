"""What the Helpdesk tools share: they load only on a site that has Helpdesk installed."""

from typing import Optional, Tuple

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool


def helpdesk_installed() -> bool:
    # Installed on this site, not merely present on the bench.
    return "helpdesk" in frappe.get_installed_apps() and bool(frappe.db.exists("DocType", "HD Ticket"))


def reply_emails_customer() -> bool:
    """Whether Helpdesk emails an agent reply, or only records it on the ticket.

    Mirrors the two settings `HD Ticket.reply_via_agent` checks before it sends.
    """
    if frappe.utils.cint(frappe.db.get_single_value("HD Settings", "skip_email_workflow")):
        return False
    return bool(frappe.utils.cint(frappe.db.get_single_value("HD Settings", "enable_reply_email_via_agent")))


class HelpdeskTool(BaseTool):
    """Base for the Helpdesk tools. Abstract, so the plugin loader never registers it as a tool."""

    def validate_dependencies(self) -> Tuple[bool, Optional[str]]:
        if not helpdesk_installed():
            return False, _("Helpdesk is not installed")
        return super().validate_dependencies()
