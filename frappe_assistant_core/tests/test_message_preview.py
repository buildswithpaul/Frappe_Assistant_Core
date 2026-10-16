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

"""get_message_preview: the approval card shows what will really be sent, not what the model claims."""

import unittest

import frappe
from frappe.email.doctype.email_account.email_account import EmailAccount

from frappe_assistant_core.chat.api.message_preview import get_message_preview
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.tests.test_helpdesk_reply_tool import (
    AGENT,
    CUSTOMER,
    NON_AGENT,
    installed,
    make_fixtures,
    make_ticket,
)


def _pin_setting(test, field: str, value: int) -> None:
    before = frappe.db.get_single_value("HD Settings", field)
    test.addCleanup(frappe.db.set_single_value, "HD Settings", field, before)
    frappe.db.set_single_value("HD Settings", field, value)


class TestHelpdeskReplyPreview(BaseAssistantTest):
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

    def test_preview_reply_matches_reply_via_agent(self):
        # On by default in HD Settings; pinned so the test does not depend on this site's choice.
        _pin_setting(self, "enable_reply_email_via_agent", 1)
        frappe.set_user(AGENT)
        out = get_message_preview("reply_to_helpdesk_ticket", ticket=str(self.ticket.name))
        self.assertTrue(out["can_send"], out)
        self.assertEqual(out["to"], [CUSTOMER])
        self.assertEqual(out["subject"], "Re: Invoice PDF shows wrong tax total")
        self.assertEqual(out["sender"], self.ticket.sender_email().email_id)
        self.assertTrue(out["will_email"])
        self.assertIn(str(self.ticket.name), out["title"])
        self.assertEqual(out["context"], "Invoice PDF shows wrong tax total")

    def test_preview_non_agent_cannot_send(self):
        # A non-agent reads a ticket only as its raiser (Helpdesk has_permission), e.g. staff raising an IT ticket.
        frappe.db.set_value("HD Ticket", self.ticket.name, "raised_by", NON_AGENT)
        frappe.set_user(NON_AGENT)
        out = get_message_preview("reply_to_helpdesk_ticket", ticket=str(self.ticket.name))
        self.assertFalse(out["can_send"])
        self.assertIn("agent", out["reason"].lower())

    def test_preview_unreadable_ticket(self):
        # A System Manager who is not an agent cannot read tickets they did not raise.
        frappe.set_user(NON_AGENT)
        unreadable = get_message_preview("reply_to_helpdesk_ticket", ticket=str(self.ticket.name))
        missing = get_message_preview("reply_to_helpdesk_ticket", ticket="999999999")
        self.assertFalse(unreadable["can_send"])
        self.assertIsNone(unreadable["to"])
        self.assertEqual(
            unreadable["reason"].replace(str(self.ticket.name), "<t>"),
            missing["reason"].replace("999999999", "<t>"),
        )

    def test_preview_will_email_false_when_disabled(self):
        # Admins switch this off in HD Settings; production reaches it there.
        _pin_setting(self, "enable_reply_email_via_agent", 0)
        frappe.set_user(AGENT)
        out = get_message_preview("reply_to_helpdesk_ticket", ticket=str(self.ticket.name))
        self.assertTrue(out["can_send"], out)
        self.assertFalse(out["will_email"])
        self.assertIsNone(out["sender"])


class TestSendEmailPreview(BaseAssistantTest):
    def test_preview_send_email_sender(self):
        out = get_message_preview("send_email")
        account = EmailAccount.find_default_outgoing()
        if not account:
            raise unittest.SkipTest("No outgoing email account on this site")
        self.assertTrue(out["can_send"], out)
        self.assertEqual(out["sender"], account.email_id)
        self.assertTrue(out["will_email"])
        self.assertIsNone(out["to"])
        self.assertIsNone(out["subject"])

    def test_preview_rejects_other_tools(self):
        with self.assertRaises(frappe.ValidationError):
            get_message_preview("create_document")
