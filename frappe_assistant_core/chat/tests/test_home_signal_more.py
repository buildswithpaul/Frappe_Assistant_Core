# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""The cards added by #34443: mentions, stale drafts, deliveries not billed, ticket SLA, and the
System Manager cards for failed emails and failed scheduled jobs."""

import json
import unittest

import frappe
from frappe.utils import add_days, add_to_date, now_datetime, today

from frappe_assistant_core.chat import home_signals
from frappe_assistant_core.tests.base_test import BaseAssistantTest

COMPANY = "Northwind Demo Co"
ABBR = "NDC"
WAREHOUSE = f"Stores - {ABBR}"
ITEM = "NW-OLIVEOIL-5L"


def _signal(signal_id: str) -> home_signals.Signal:
    return next(signal for signal in home_signals.CATALOGUE if signal.id == signal_id)


def _applies(signal_id: str, user: str) -> bool:
    installed = frappe.get_installed_apps()
    lenses = home_signals.resolve_lenses(frappe.get_roles(user), installed)
    return home_signals._is_applicable(_signal(signal_id), user, lenses, installed)


class TestMentions(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.user = self.make_throwaway_user("mentioned", roles=("Sales User",))

    def _mention(self, for_user: str) -> str:
        # Production path: a comment that @mentions someone creates this Notification Log for them.
        return (
            frappe.get_doc(
                {
                    "doctype": "Notification Log",
                    "for_user": for_user,
                    "from_user": "Administrator",
                    "type": "Mention",
                    "subject": "Administrator mentioned you in a comment",
                }
            )
            .insert(ignore_permissions=True)
            .name
        )

    def test_counts_unread_mentions_of_the_user(self):
        self._mention(self.user)
        result = home_signals._unread_mentions(self.user, None)
        self.assertEqual(result.count, 1)

    def test_a_read_mention_drops_out(self):
        name = self._mention(self.user)
        # Production path: opening the notification marks it read.
        frappe.db.set_value("Notification Log", name, "read", 1)
        self.assertEqual(home_signals._unread_mentions(self.user, None).count, 0)

    def test_someone_elses_mention_is_not_counted(self):
        other = self.make_throwaway_user("other", roles=("Sales User",))
        self._mention(other)
        self.assertEqual(home_signals._unread_mentions(self.user, None).count, 0)


@unittest.skipUnless(
    "erpnext" in frappe.get_installed_apps() and frappe.db.exists("Company", COMPANY),
    "needs ERPNext and the demo company",
)
class TestStaleDrafts(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.user = self.make_throwaway_user("drafter", roles=("Stock User",))

    def _draft(self, owner: str, untouched_days: int) -> str:
        doc = frappe.get_doc(
            {
                "doctype": "Material Request",
                "material_request_type": "Purchase",
                "company": COMPANY,
                "schedule_date": add_days(today(), 7),
                "items": [
                    {
                        "item_code": ITEM,
                        "qty": 1,
                        "warehouse": WAREHOUSE,
                        "schedule_date": add_days(today(), 7),
                    }
                ],
            }
        ).insert(ignore_permissions=True)
        # Manufactured: production reaches this when the owner saves a draft and leaves it for days;
        # owner and modified are stamped at insert, so they are set back to that state here.
        frappe.db.set_value(
            "Material Request",
            doc.name,
            {"owner": owner, "modified": add_days(now_datetime(), -untouched_days)},
            update_modified=False,
        )
        return doc.name

    def test_counts_an_old_draft_the_user_owns(self):
        self._draft(self.user, untouched_days=10)
        result = home_signals._stale_drafts(self.user, None)
        self.assertEqual(result.count, 1)
        self.assertIn("Material Request", result.detail)

    def test_a_recent_draft_is_not_stale(self):
        self._draft(self.user, untouched_days=2)
        self.assertIsNone(home_signals._stale_drafts(self.user, None))

    def test_another_owners_draft_is_not_counted(self):
        self._draft("Administrator", untouched_days=10)
        self.assertIsNone(home_signals._stale_drafts(self.user, None))

    def test_a_doctype_under_an_active_workflow_is_skipped(self):
        self._draft(self.user, untouched_days=10)
        # Manufactured: production reaches this when an administrator activates a workflow on the
        # DocType; only the active flag is read, so the states are not needed.
        workflow = frappe.get_doc(
            {
                "doctype": "Workflow",
                "workflow_name": f"MR Flow {frappe.generate_hash(length=6)}",
                "document_type": "Material Request",
                "is_active": 1,
                "workflow_state_field": "workflow_state",
                "states": [],
                "transitions": [],
            }
        )
        workflow.db_insert()
        # The class shares one transaction, so the next test would still see it.
        self.addCleanup(frappe.db.delete, "Workflow", {"name": workflow.name})
        self.assertIsNone(home_signals._stale_drafts(self.user, None))


@unittest.skipUnless(
    "erpnext" in frappe.get_installed_apps() and frappe.db.exists("Company", COMPANY),
    "needs ERPNext and the demo company",
)
class TestDeliveredNotBilled(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.user = self.make_throwaway_user("biller", roles=("Accounts User",))
        self.customer = (
            frappe.get_doc(
                {
                    "doctype": "Customer",
                    "customer_name": f"Signal DN Customer {frappe.generate_hash(length=6)}",
                }
            )
            .insert(ignore_permissions=True)
            .name
        )
        # Production path: stock is received before it can be delivered.
        receipt = frappe.get_doc(
            {
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Receipt",
                "company": COMPANY,
                "items": [
                    {
                        "item_code": ITEM,
                        "qty": 5,
                        "basic_rate": 10,
                        "t_warehouse": WAREHOUSE,
                        "expense_account": f"Stock Adjustment - {ABBR}",
                        "cost_center": f"Main - {ABBR}",
                    }
                ],
            }
        ).insert(ignore_permissions=True)
        receipt.submit()

    def _deliver(self):
        # Production path: a submitted Delivery Note with no invoice against it reads "To Bill".
        note = frappe.get_doc(
            {
                "doctype": "Delivery Note",
                "company": COMPANY,
                "customer": self.customer,
                "currency": "INR",
                "conversion_rate": 1,
                "items": [
                    {
                        "item_code": ITEM,
                        "qty": 1,
                        "rate": 100,
                        "warehouse": WAREHOUSE,
                        "cost_center": f"Main - {ABBR}",
                    }
                ],
            }
        ).insert(ignore_permissions=True)
        note.submit()
        return note

    def test_counts_a_submitted_delivery_with_no_invoice(self):
        self._deliver()
        self.assertGreaterEqual(home_signals._delivered_not_billed(self.user, COMPANY).count, 1)

    def test_a_closed_delivery_drops_out(self):
        before = home_signals._delivered_not_billed(self.user, COMPANY).count
        note = self._deliver()
        # Production path: closing a Delivery Note marks it as needing no invoice.
        note.update_status("Closed")
        self.assertEqual(home_signals._delivered_not_billed(self.user, COMPANY).count, before)

    def test_shows_for_accounts_and_sales_but_not_stock(self):
        seller = self.make_throwaway_user("seller", roles=("Sales User",))
        storekeeper = self.make_throwaway_user("storekeeper", roles=("Stock User",))
        self.assertTrue(_applies("delivered_not_billed", self.user))
        self.assertTrue(_applies("delivered_not_billed", seller))
        self.assertFalse(_applies("delivered_not_billed", storekeeper))


@unittest.skipUnless("helpdesk" in frappe.get_installed_apps(), "needs Helpdesk")
class TestTicketSla(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.user = self.make_throwaway_user("agent", roles=("Agent",))

    def _ticket(self, assignee: str, resolution_in_hours: float, responded: bool = True) -> str:
        ticket = frappe.get_doc(
            {"doctype": "HD Ticket", "subject": "Signal SLA ticket", "raised_by": "customer@example.com"}
        ).insert(ignore_permissions=True)
        # Manufactured: Helpdesk's SLA computes these deadlines at insert from the site's agreement,
        # and assignment writes _assign; they are fixed here so the test does not depend on the SLA.
        frappe.db.set_value(
            "HD Ticket",
            ticket.name,
            {
                "_assign": json.dumps([assignee]),
                "resolution_by": add_to_date(now_datetime(), hours=resolution_in_hours),
                "response_by": add_to_date(now_datetime(), hours=-1),
                "first_responded_on": now_datetime() if responded else None,
            },
            update_modified=False,
        )
        return ticket.name

    def test_counts_a_ticket_past_its_resolution_deadline(self):
        self._ticket(self.user, resolution_in_hours=-2)
        result = home_signals._ticket_sla_due(self.user, None)
        self.assertEqual(result.count, 1)
        self.assertEqual(result.detail, "All of them are past their SLA")

    def test_counts_a_ticket_due_within_the_window(self):
        self._ticket(self.user, resolution_in_hours=2)
        result = home_signals._ticket_sla_due(self.user, None)
        self.assertEqual(result.count, 1)
        self.assertIn("within", result.detail)

    def test_an_unanswered_ticket_counts_by_its_response_deadline(self):
        self._ticket(self.user, resolution_in_hours=48, responded=False)
        self.assertEqual(home_signals._ticket_sla_due(self.user, None).count, 1)

    def test_a_ticket_due_later_is_not_counted(self):
        self._ticket(self.user, resolution_in_hours=48)
        self.assertIsNone(home_signals._ticket_sla_due(self.user, None))

    def test_a_helpdesk_agent_gets_the_card(self):
        # Helpdesk gives its agents the "Agent" role; there is no "Helpdesk Agent" role.
        self.assertIn("support", home_signals.resolve_lenses(["Agent"], frappe.get_installed_apps()))
        self.assertTrue(_applies("ticket_sla", self.user))

    def test_a_ticket_assigned_to_someone_else_is_not_counted(self):
        self._ticket("someone-else@example.com", resolution_in_hours=-2)
        self.assertIsNone(home_signals._ticket_sla_due(self.user, None))


class TestSystemManagerSignals(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.admin = self.make_throwaway_user("sysadmin", roles=("System Manager",))

    def test_counts_an_email_that_ended_in_error(self):
        # Production path: the email queue marks a send that keeps failing as Error.
        frappe.get_doc(
            {"doctype": "Email Queue", "status": "Error", "sender": "noreply@example.com", "message": "x"}
        ).db_insert()
        self.assertEqual(home_signals._failed_emails(self.admin, None).count, 1)

    def test_counts_each_failing_job_once(self):
        # Production path: the scheduler writes one Failed log per failed run.
        for job in ("signal_job_a", "signal_job_a", "signal_job_b"):
            frappe.get_doc(
                {"doctype": "Scheduled Job Log", "scheduled_job_type": job, "status": "Failed"}
            ).db_insert()
        self.assertEqual(home_signals._failed_scheduled_jobs(self.admin, None).count, 2)

    def test_only_system_managers_get_them(self):
        # Both DocTypes are readable by System Manager alone, so the read check gates the cards.
        clerk = self.make_throwaway_user("clerk", roles=("Accounts User",))
        for signal_id in ("failed_emails", "failed_scheduled_jobs"):
            self.assertTrue(_applies(signal_id, self.admin))
            self.assertFalse(_applies(signal_id, clerk))
