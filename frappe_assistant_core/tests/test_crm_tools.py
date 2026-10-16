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
