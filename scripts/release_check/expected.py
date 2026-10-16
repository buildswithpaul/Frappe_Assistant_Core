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

from frappe_assistant_core.plugins.core.tools.list_documents import run_grouped_query

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
    """Net sales before tax (base_net_total) of submitted Sales Invoices in the previous calendar month.

    Questions say "net sales (before tax)": a company default Sales Taxes template makes grand total differ.
    """
    start, end = month_window(getdate(nowdate()), 1)
    rows = _sales_invoices(start, end, ["base_net_total"])
    return flt(sum(row.base_net_total for row in rows), 2)


def top_customers_quarter() -> list:
    """Top customers by net sales before tax (base_net_total), current calendar quarter to date."""
    today = getdate(nowdate())
    rows = _sales_invoices(quarter_start(today), today, ["customer", "base_net_total"])
    totals = defaultdict(float)
    for row in rows:
        totals[row.customer] += row.base_net_total
    ranked = sorted(totals.items(), key=lambda pair: (-pair[1], pair[0]))
    return [(name, flt(value, 2)) for name, value in ranked[:TOP_N]]


def _receivable_balance() -> float:
    """Customer receivable balance as on today, from the party ledger.

    GL debit minus credit on Receivable accounts for rows that carry a Customer party, up to today,
    excluding cancelled entries. Accounts Receivable nets unallocated payments and credit journals
    (the ERPNext demo posts both) and ignores future-dated invoices, which a sum of Sales Invoice
    outstanding_amount would not.
    """
    receivable_accounts = frappe.get_list(
        "Account",
        filters={"account_type": "Receivable", "is_group": 0},
        pluck="name",
        limit_page_length=0,
    )
    if not receivable_accounts:
        return 0.0
    specs = [
        {"function": "sum", "field": "debit", "alias": "sum_debit"},
        {"function": "sum", "field": "credit", "alias": "sum_credit"},
    ]
    filters = {
        "account": ["in", receivable_accounts],
        "party_type": "Customer",
        "is_cancelled": 0,
        "posting_date": ["<=", getdate(nowdate())],
    }
    totals = run_grouped_query("GL Entry", filters, None, specs, 1)[0]
    return flt(flt(totals.get("sum_debit")) - flt(totals.get("sum_credit")), 2)


def receivables_ageing() -> float:
    """Total receivable owed by customers as on today (the total of Accounts Receivable).

    The question asks only for this total; the age of the debt is not scored.
    """
    return _receivable_balance()


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
    """Customer receivable balance as on today, read from the ledger.

    Same definition as receivables_ageing, on the large site, where the answer comes from a
    prepared Accounts Receivable / General Ledger run instead of being computed by it.
    """
    return _receivable_balance()
