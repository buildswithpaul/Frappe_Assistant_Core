# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""The CRM tools on a real Frappe CRM install: they go through CRM's own flows.

Skipped where CRM is not installed (CI). Fixtures are built through CRM's DocTypes as
Administrator, like a sales manager setting up a lead and its history.
"""

import unittest

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest

OWNER = "test_fac_crm_owner@example.com"
OUTSIDER = "test_fac_crm_outsider@example.com"
LEAD_EMAIL = "priya.raman@acme-fac-test.example"


def installed() -> bool:
    return "crm" in frappe.get_installed_apps()


def _user(email: str, roles: list[str]) -> None:
    if not frappe.db.exists("User", email):
        frappe.get_doc(
            {"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0}
        ).insert(ignore_permissions=True)
    frappe.get_doc("User", email).add_roles(*roles)


def make_lead(**extra):
    """A lead owned by OWNER, with the history a discovery call leaves behind."""
    frappe.set_user("Administrator")
    lead = frappe.get_doc(
        {
            "doctype": "CRM Lead",
            "first_name": "Priya",
            "last_name": "Raman",
            "email": LEAD_EMAIL,
            "organization": "Acme FAC Test Retail",
            "job_title": "Head of Operations",
            "lead_owner": OWNER,
            **extra,
        }
    ).insert(ignore_permissions=True)
    ref = {"reference_doctype": "CRM Lead", "reference_docname": lead.name}
    frappe.get_doc(
        {
            "doctype": "FCRM Note",
            "title": "Discovery call",
            "content": "<p>Budget INR 18L, decision by November.</p>",
            **ref,
        }
    ).insert(ignore_permissions=True)
    frappe.get_doc(
        {
            "doctype": "CRM Task",
            "title": "Send proposal",
            "status": "Todo",
            "priority": "High",
            "assigned_to": OWNER,
            **ref,
        }
    ).insert(ignore_permissions=True)
    frappe.get_doc(
        {
            "doctype": "CRM Call Log",
            "type": "Outgoing",
            "status": "Completed",
            "from": "+910000000001",
            "to": "+910000000002",
            "duration": 420,
            **ref,
        }
    ).insert(ignore_permissions=True)
    # CRM's composer creates this through frappe.core.doctype.communication.email.make.
    frappe.get_doc(
        {
            "doctype": "Communication",
            "communication_type": "Communication",
            "communication_medium": "Email",
            "sent_or_received": "Sent",
            "subject": "Proposal follow-up",
            "content": "<p>Sharing the proposal.</p>",
            "recipients": LEAD_EMAIL,
            "reference_doctype": "CRM Lead",
            "reference_name": lead.name,
        }
    ).insert(ignore_permissions=True)
    return lead


def make_fixtures() -> None:
    frappe.set_user("Administrator")
    _user(OWNER, ["Sales User"])
    _user(OUTSIDER, ["Sales User"])


def tool(name: str):
    module = __import__(f"frappe_assistant_core.plugins.faco.tools.{name}", fromlist=["*"])
    cls = next(v for v in vars(module).values() if isinstance(v, type) and v.__module__ == module.__name__)
    return cls()


class CrmTestCase(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not installed():
            raise unittest.SkipTest("Frappe CRM is not installed")
        make_fixtures()

    def setUp(self):
        self.lead = make_lead()

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()


class TestGetCrmActivity(CrmTestCase):
    def test_the_whole_timeline_is_returned(self):
        frappe.set_user(OWNER)
        out = tool("get_crm_activity").execute({"doctype": "CRM Lead", "name": self.lead.name})
        self.assertTrue(out["success"], out)
        self.assertEqual(out["record"]["link"], f"/crm/leads/{self.lead.name}")
        self.assertIn("Budget INR 18L", out["notes"][0]["content"])
        self.assertNotIn("<p>", out["notes"][0]["content"])
        self.assertEqual(out["tasks"][0]["title"], "Send proposal")
        self.assertEqual(out["calls"][0]["type"], "Outgoing")
        self.assertEqual(out["emails"][0]["subject"], "Proposal follow-up")

    def test_a_record_the_user_cannot_read_is_not_found(self):
        # A Sales User sees only leads they own or are assigned to (CRM's org_hierarchy rule).
        frappe.set_user(OUTSIDER)
        unreadable = tool("get_crm_activity").execute({"doctype": "CRM Lead", "name": self.lead.name})
        missing = tool("get_crm_activity").execute({"doctype": "CRM Lead", "name": "CRM-LEAD-0000-99999"})
        self.assertFalse(unreadable["success"])
        self.assertEqual(
            unreadable["error"].replace(self.lead.name, "<n>"),
            missing["error"].replace("CRM-LEAD-0000-99999", "<n>"),
        )

    def test_other_doctypes_are_refused(self):
        out = tool("get_crm_activity").execute({"doctype": "Lead", "name": self.lead.name})
        self.assertFalse(out["success"])
        self.assertIn("CRM Lead", out["error"])

    def test_registered_in_faco_plugin(self):
        from frappe_assistant_core.plugins.faco.plugin import FacoPlugin

        self.assertIn("get_crm_activity", FacoPlugin().get_tools())


class TestSendCrmEmail(CrmTestCase):
    def _send(self, **args):
        return tool("send_crm_email").execute(
            {
                "doctype": "CRM Lead",
                "name": self.lead.name,
                "subject": "Inventory sync proposal",
                "message": "Hi Priya,\nAttached.",
                **args,
            }
        )

    def _comms(self):
        return frappe.get_all(
            "Communication",
            filters={
                "reference_doctype": "CRM Lead",
                "reference_name": self.lead.name,
                "subject": "Inventory sync proposal",
            },
            fields=["name", "recipients", "content", "sender"],
        )

    def test_the_email_lands_on_the_lead_and_is_queued(self):
        frappe.set_user(OWNER)
        out = self._send()
        self.assertTrue(out["success"], out)
        comms = self._comms()
        self.assertEqual([c.name for c in comms], [out["communication"]])
        self.assertIn(LEAD_EMAIL, comms[0].recipients)
        self.assertIn("Hi Priya,<br>Attached.", comms[0].content)
        self.assertTrue(out["email_queued"])

    def test_an_invalid_address_is_refused_before_anything_is_written(self):
        frappe.set_user(OWNER)
        out = self._send(recipients=["priya"])
        self.assertFalse(out["success"])
        self.assertIn("priya", out["error"])
        self.assertEqual(self._comms(), [])

    def test_a_failed_send_leaves_nothing_on_the_lead(self):
        from unittest.mock import patch

        from frappe.core.doctype.communication.communication import Communication

        frappe.set_user(OWNER)
        # An outgoing-mail failure after make() has inserted the Communication.
        with patch.object(Communication, "send_email", autospec=True, side_effect=Exception("SMTP is down")):
            out = self._send()
        self.assertFalse(out["success"])
        self.assertEqual(self._comms(), [])

    def test_a_record_the_user_cannot_read_is_not_found(self):
        frappe.set_user(OUTSIDER)
        out = self._send()
        self.assertFalse(out["success"])
        self.assertIn("not found", out["error"])
        self.assertEqual(self._comms(), [])

    def test_the_card_shows_the_sender_the_tool_uses(self):
        from frappe_assistant_core.chat.api.message_preview import get_message_preview
        from frappe_assistant_core.plugins.faco.crm.email import crm_sender

        frappe.set_user(OWNER)
        preview = get_message_preview("send_crm_email", doctype="CRM Lead", name=self.lead.name)
        self.assertTrue(preview["can_send"], preview)
        self.assertEqual(preview["sender"], crm_sender().email_id)
        self.assertEqual(preview["to"], [LEAD_EMAIL])
        self.assertIn("Priya Raman", preview["title"])
        out = self._send()
        self.assertEqual(
            frappe.db.get_value("Communication", out["communication"], "sender"), crm_sender().email_id
        )

    def test_the_card_refuses_a_user_who_cannot_email_the_record(self):
        from frappe_assistant_core.chat.api.message_preview import get_message_preview

        frappe.set_user(OUTSIDER)
        preview = get_message_preview("send_crm_email", doctype="CRM Lead", name=self.lead.name)
        self.assertFalse(preview["can_send"])
        self.assertIsNone(preview["to"])


class TestConvertCrmLead(CrmTestCase):
    def _convert(self, **args):
        return tool("convert_crm_lead").execute({"lead": self.lead.name, **args})

    def test_conversion_goes_through_crm(self):
        frappe.set_user(OWNER)
        out = self._convert(deal_fields={"next_step": "Send proposal"})
        self.assertTrue(out["success"], out)
        self.assertEqual(out["link"], f"/crm/deals/{out['deal']}")
        frappe.set_user("Administrator")
        self.assertEqual(frappe.db.get_value("CRM Lead", self.lead.name, "converted"), 1)
        deal = frappe.get_doc("CRM Deal", out["deal"])
        self.assertEqual(deal.lead, self.lead.name)
        self.assertEqual(deal.next_step, "Send proposal")
        self.assertEqual(deal.organization, "Acme FAC Test Retail")
        self.assertTrue(frappe.db.exists("Contact", {"email_id": LEAD_EMAIL}))

    def test_converting_twice_returns_the_same_deal(self):
        frappe.set_user(OWNER)
        first = self._convert()
        second = self._convert()
        self.assertEqual(first["deal"], second["deal"])
        self.assertEqual(frappe.db.count("CRM Deal", {"lead": self.lead.name}), 1)

    def test_a_lost_lead_is_refused_with_nothing_written(self):
        # A salesperson marked the lead Unqualified (a Lost-type status) in CRM.
        frappe.db.set_value("CRM Lead", self.lead.name, "status", "Unqualified")
        frappe.set_user(OWNER)
        out = self._convert()
        self.assertFalse(out["success"])
        self.assertEqual(frappe.db.count("CRM Deal", {"lead": self.lead.name}), 0)
        self.assertFalse(frappe.db.exists("Contact", {"email_id": LEAD_EMAIL}))

    def test_a_refusal_after_crm_wrote_the_contact_leaves_nothing(self):
        # Admins switch forecasting on in CRM settings; a deal then needs a value and a close date,
        # which CRM checks only after it has inserted the contact and the organization.
        before = frappe.db.get_single_value("FCRM Settings", "enable_forecasting")
        self.addCleanup(frappe.db.set_single_value, "FCRM Settings", "enable_forecasting", before)
        frappe.db.set_single_value("FCRM Settings", "enable_forecasting", 1)
        frappe.set_user(OWNER)
        out = self._convert()
        self.assertFalse(out["success"])
        frappe.set_user("Administrator")
        self.assertFalse(frappe.db.exists("Contact", {"email_id": LEAD_EMAIL}))
        self.assertFalse(frappe.db.exists("CRM Organization", "Acme FAC Test Retail"))
        self.assertEqual(frappe.db.count("CRM Deal", {"lead": self.lead.name}), 0)
        self.assertEqual(frappe.db.get_value("CRM Lead", self.lead.name, "converted"), 0)

    def test_deal_fields_cannot_override_what_crm_links(self):
        frappe.set_user(OWNER)
        out = self._convert(
            deal_fields={"lead": "CRM-LEAD-0000-00001", "naming_series": "X-", "next_step": "Call"}
        )
        self.assertTrue(out["success"], out)
        frappe.set_user("Administrator")
        self.assertEqual(frappe.db.get_value("CRM Deal", out["deal"], "lead"), self.lead.name)
        self.assertEqual(self._convert()["deal"], out["deal"])

    def test_an_existing_deal_the_user_cannot_read_is_not_named(self):
        frappe.set_user(OWNER)
        deal = self._convert()["deal"]
        # The deal was reassigned to someone else after conversion, so OWNER no longer sees it.
        frappe.set_user("Administrator")
        frappe.db.set_value("CRM Deal", deal, "deal_owner", "Administrator")
        for todo in frappe.get_all(
            "ToDo", filters={"reference_type": "CRM Deal", "reference_name": deal}, pluck="name"
        ):
            frappe.db.set_value("ToDo", todo, "status", "Cancelled")
        frappe.set_user(OWNER)
        out = self._convert()
        self.assertTrue(out["success"], out)
        self.assertNotIn(deal, str(out))

    def test_a_lead_the_user_cannot_change_is_not_found(self):
        frappe.set_user(OUTSIDER)
        out = self._convert()
        self.assertFalse(out["success"])
        self.assertIn("not found", out["error"])
        self.assertEqual(frappe.db.count("CRM Deal", {"lead": self.lead.name}), 0)
