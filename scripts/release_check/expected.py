"""Expected answers for the release-check questions.

Every function takes no arguments, must run inside a connected Frappe site
(`frappe.init` + `frappe.connect`, as the runner does), and derives its answer
from the site's data with `frappe.get_list` at call time. Nothing here is a
hand-typed number, so the same function is correct on either site and after
the setup scripts are re-run.

Return shapes by `expect.kind` in questions.json:
  total    -> float
  top_n    -> list of (name, value) pairs, best first (ties broken by name)
  mentions -> list of strings the answer must contain; an element that is a
              list is a set of alternatives of which any one satisfies it
"""

from collections import defaultdict

import frappe
from frappe.utils import flt, getdate, nowdate
from site_common import month_window, quarter_start

TOP_N = 5
BOOKING_DOCTYPE = "Booking"
STOCK_ITEM = "RC Widget"
VENDOR = "RC Vendor Alpha"


def _sales_invoices(start, end, fields):
    return frappe.get_list(
        "Sales Invoice",
        filters={"docstatus": 1, "posting_date": ["between", [start, end]]},
        fields=fields,
        limit_page_length=0,
    )


def sales_last_month() -> float:
    """Net sales (base_net_total) of submitted Sales Invoices in the previous calendar month."""
    start, end = month_window(getdate(nowdate()), 1)
    rows = _sales_invoices(start, end, ["base_net_total"])
    return flt(sum(row.base_net_total for row in rows), 2)


def top_customers_quarter() -> list:
    """Top customers by net sales, current calendar quarter to date."""
    today = getdate(nowdate())
    rows = _sales_invoices(quarter_start(today), today, ["customer", "base_net_total"])
    totals = defaultdict(float)
    for row in rows:
        totals[row.customer] += row.base_net_total
    ranked = sorted(totals.items(), key=lambda pair: (-pair[1], pair[0]))
    return [(name, flt(value, 2)) for name, value in ranked[:TOP_N]]


def receivables_ageing() -> float:
    """Total outstanding receivable: sum of outstanding_amount over submitted Sales Invoices."""
    rows = frappe.get_list(
        "Sales Invoice",
        filters={"docstatus": 1, "outstanding_amount": ["!=", 0]},
        fields=["outstanding_amount"],
        limit_page_length=0,
    )
    return flt(sum(row.outstanding_amount for row in rows), 2)


def vendor_payment_history() -> list:
    """Payment Entries to the setup's dedicated vendor: the entry names and paid amounts."""
    rows = frappe.get_list(
        "Payment Entry",
        filters={"docstatus": 1, "party_type": "Supplier", "party": VENDOR},
        fields=["name", "paid_amount"],
        order_by="posting_date asc, name asc",
        limit_page_length=0,
    )
    mentions = [VENDOR]
    for row in rows:
        amount = flt(row.paid_amount, 2)
        # an answer may print the amount with or without separators or decimals
        mentions.append([row.name, f"{amount:,.2f}", f"{amount:.2f}", f"{amount:,.0f}", f"{amount:.0f}"])
    return mentions


def stock_position() -> float:
    """Units of the setup's stock item on hand across warehouses (Bin.actual_qty)."""
    rows = frappe.get_list(
        "Bin", filters={"item_code": STOCK_ITEM}, fields=["actual_qty"], limit_page_length=0
    )
    return flt(sum(row.actual_qty for row in rows), 2)


def sales_by_region_custom_report() -> list:
    """Regions ranked by net sales, from invoices and each customer's territory.

    Independent of the Query Report's SQL on purpose: it is the number the report should show.
    """
    invoices = frappe.get_list(
        "Sales Invoice",
        filters={"docstatus": 1},
        fields=["customer", "base_net_total"],
        limit_page_length=0,
    )
    territory_of = {
        row.name: row.territory
        for row in frappe.get_list("Customer", fields=["name", "territory"], limit_page_length=0)
    }
    totals = defaultdict(float)
    for invoice in invoices:
        totals[territory_of.get(invoice.customer)] += invoice.base_net_total
    ranked = sorted(totals.items(), key=lambda pair: (-pair[1], str(pair[0])))
    return [(name, flt(value, 2)) for name, value in ranked[:TOP_N]]


def bookings_this_month_custom_doctype() -> float:
    """Sum of Booking.amount for submitted bookings dated in the current calendar month."""
    today = getdate(nowdate())
    start, _ = month_window(today, 0)
    rows = frappe.get_list(
        BOOKING_DOCTYPE,
        filters={"docstatus": 1, "booking_date": ["between", [start, today]]},
        fields=["amount"],
        limit_page_length=0,
    )
    return flt(sum(row.amount for row in rows), 2)


def ledger_heavy_report() -> float:
    """Net receivable balance today: GL debit minus credit on Receivable accounts.

    This is what the Accounts Receivable report totals, taken straight from
    the ledger so it is checked against the (prepared) report, not computed by it.
    """
    receivable_accounts = frappe.get_list(
        "Account", filters={"account_type": "Receivable", "is_group": 0}, pluck="name", limit_page_length=0
    )
    if not receivable_accounts:
        return 0.0
    totals = frappe.get_list(
        "GL Entry",
        filters={"account": ["in", receivable_accounts], "is_cancelled": 0},
        fields=["sum(debit) as debit", "sum(credit) as credit"],
    )[0]
    return flt(flt(totals.debit) - flt(totals.credit), 2)
