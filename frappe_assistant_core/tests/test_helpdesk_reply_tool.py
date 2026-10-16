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

"""reply_to_helpdesk_ticket on a real Helpdesk install: the reply goes through Helpdesk's own flow.

Skipped where Helpdesk is not installed (CI). Fixtures are built through Helpdesk's
own DocTypes as Administrator, like an admin setting up agents and a customer raising a ticket.
"""

import unittest
from unittest.mock import patch

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest

AGENT = "test_fac_hd_agent@example.com"
NON_AGENT = "test_fac_hd_nonagent@example.com"
CUSTOMER = "test_fac_hd_customer@example.com"
TOOL_MODULE = "frappe_assistant_core.plugins.faco.tools.reply_to_helpdesk_ticket"


def installed() -> bool:
    return "helpdesk" in frappe.get_installed_apps()


def _user(email: str, roles: list[str]) -> None:
    if not frappe.db.exists("User", email):
        frappe.get_doc(
            {"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0}
        ).insert(ignore_permissions=True)
    frappe.get_doc("User", email).add_roles(*roles)


def make_fixtures() -> None:
    """An active agent, a non-agent desk user and an outgoing account, as an admin sets them up."""
    frappe.set_user("Administrator")
    _user(AGENT, ["Agent"])
    if not frappe.db.exists("HD Agent", AGENT):
        frappe.get_doc({"doctype": "HD Agent", "user": AGENT, "agent_name": "FAC Agent"}).insert(
            ignore_permissions=True
        )
    _user(NON_AGENT, ["System Manager"])
    if not frappe.db.exists("Email Account", {"email_id": "fac-hd-test@example.com"}):
        frappe.get_doc(
            {
                "doctype": "Email Account",
                "email_account_name": "FAC HD Reply Test",
                "email_id": "fac-hd-test@example.com",
                "enable_outgoing": 1,
                "default_outgoing": 1,
                "smtp_server": "localhost",
                "no_smtp_authentication": 1,
            }
        ).insert(ignore_permissions=True)


def make_ticket():
    """A ticket a customer raised by email."""
    frappe.set_user("Administrator")
    return frappe.get_doc(
        {
            "doctype": "HD Ticket",
            "subject": "Invoice PDF shows wrong tax total",
            "description": "The tax total is off.",
            "raised_by": CUSTOMER,
        }
    ).insert(ignore_permissions=True)


class TestHelpdeskReplyTool(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not installed():
            raise unittest.SkipTest("Helpdesk is not installed")
        make_fixtures()

    def setUp(self):
        self.ticket = make_ticket()

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _tool(self):
        from frappe_assistant_core.plugins.faco.tools.reply_to_helpdesk_ticket import ReplyToHelpdeskTicket

        return ReplyToHelpdeskTicket()

    def _replies(self):
        return frappe.get_all(
            "Communication",
            filters={
                "reference_doctype": "HD Ticket",
                "reference_name": str(self.ticket.name),
                "sent_or_received": "Sent",
            },
            fields=["name", "recipients", "cc", "content"],
        )

    def test_reply_creates_linked_sent_communication(self):
        frappe.set_user(AGENT)
        out = self._tool().execute(
            {"ticket": str(self.ticket.name), "message": "<p>Hi</p>", "cc": ["ops@example.com"]}
        )
        self.assertTrue(out["success"], out)
        replies = self._replies()
        self.assertEqual(len(replies), 1)
        self.assertEqual(out["communication"], replies[0].name)
        self.assertIn(CUSTOMER, replies[0].recipients)
        self.assertIn("ops@example.com", replies[0].cc)
        self.assertTrue(frappe.db.get_value("HD Ticket", self.ticket.name, "first_responded_on"))

    def test_reply_queues_the_email_on_the_communication(self):
        # On by default in HD Settings; pinned so the test does not depend on this site's choice.
        before = frappe.db.get_single_value("HD Settings", "enable_reply_email_via_agent")
        self.addCleanup(frappe.db.set_single_value, "HD Settings", "enable_reply_email_via_agent", before)
        frappe.db.set_single_value("HD Settings", "enable_reply_email_via_agent", 1)
        frappe.set_user(AGENT)
        out = self._tool().execute({"ticket": str(self.ticket.name), "message": "<p>Hi</p>"})
        self.assertTrue(out["success"], out)
        self.assertTrue(out["email_queued"])
        self.assertEqual(
            len(frappe.get_all("Email Queue", filters={"communication": out["communication"]}, pluck="name")),
            1,
        )

    def test_non_agent_refused(self):
        # A non-agent reads a ticket only as its raiser (Helpdesk has_permission), e.g. staff raising an IT ticket.
        frappe.db.set_value("HD Ticket", self.ticket.name, "raised_by", NON_AGENT)
        frappe.set_user(NON_AGENT)
        out = self._tool().execute({"ticket": str(self.ticket.name), "message": "<p>Hi</p>"})
        self.assertFalse(out["success"])
        self.assertIn("agent", out["error"].lower())
        self.assertEqual(self._replies(), [])

    def test_missing_ticket_is_not_found(self):
        frappe.set_user(AGENT)
        out = self._tool().execute({"ticket": "999999999", "message": "<p>Hi</p>"})
        self.assertFalse(out["success"])
        self.assertIn("999999999", out["error"])

    def test_email_not_queued_when_helpdesk_skips(self):
        # Admins switch this off in HD Settings; production reaches it there.
        before = frappe.db.get_single_value("HD Settings", "enable_reply_email_via_agent")
        self.addCleanup(frappe.db.set_single_value, "HD Settings", "enable_reply_email_via_agent", before)
        frappe.db.set_single_value("HD Settings", "enable_reply_email_via_agent", 0)
        frappe.set_user(AGENT)
        out = self._tool().execute({"ticket": str(self.ticket.name), "message": "<p>Hi</p>"})
        self.assertTrue(out["success"], out)
        self.assertFalse(out["email_queued"])
        self.assertEqual(len(self._replies()), 1)

    def test_dependency_gate(self):
        with patch("frappe_assistant_core.plugins.faco.helpdesk.tool.helpdesk_installed", return_value=False):
            self.assertFalse(self._tool().validate_dependencies()[0])
        self.assertTrue(self._tool().validate_dependencies()[0])

    def test_registered_in_faco_plugin(self):
        from frappe_assistant_core.plugins.faco.plugin import FacoPlugin

        self.assertIn("reply_to_helpdesk_ticket", FacoPlugin().get_tools())
