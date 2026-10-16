"""Build the "realistic" release-check site: small, human-shaped business data.

ERPNext demo company + extra recently dated invoices, a UI-style Query Report
("Sales Performance by Region") and a custom DocType ("Booking").

Idempotent: every step counts what already exists and only creates the
shortfall, so re-running (for example on release day, to refresh the
current-month data) is safe.

    cd <bench>/sites
    ../env/bin/python <fac-repo>/scripts/release_check/setup_realistic_site.py --site realistic.test
    ... --dry-run          # print the plan only, no database needed
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import frappe  # noqa: E402
from frappe.utils import add_days, nowdate  # noqa: E402
from site_common import (  # noqa: E402
    call_setup_demo_data,
    clamp_to_fiscal_years,
    count_tagged,
    ensure_customer,
    ensure_fiscal_years,
    ensure_item,
    ensure_supplier,
    ensure_territory,
    make_material_receipt,
    make_payment_for,
    make_sales_invoice,
    month_window,
    print_counts,
    rng,
    run_cli,
    scaled,
)

TAG = "release-check:realistic"
REGIONS = ["RC North", "RC South", "RC East", "RC West"]
REPORT_NAME = "Sales Performance by Region"
BOOKING_DOCTYPE = "Booking"
STOCK_ITEM = "RC Widget"
SERVICE_ITEM = "RC Consulting"
VENDOR = "RC Vendor Alpha"

# Written so the report is a plain SQL Query Report, i.e. what a user builds in the UI.
REGION_REPORT_QUERY = """
SELECT
    c.territory AS "Region:Link/Territory:160",
    COUNT(si.name) AS "Invoices:Int:90",
    SUM(si.base_net_total) AS "Net Sales:Currency:140"
FROM `tabSales Invoice` si
JOIN `tabCustomer` c ON c.name = si.customer
WHERE si.docstatus = 1
GROUP BY c.territory
ORDER BY SUM(si.base_net_total) DESC
""".strip()

INVOICES_PER_WINDOW = 15
BOOKINGS_TOTAL = 60
BOOKINGS_THIS_MONTH = 12
VENDOR_PAYMENTS = 3


def plan(scale: float) -> list:
    return [
        ("ERPNext demo company (setup_demo_data) if no demo company exists", "1 company"),
        ("Fiscal Years covering the last 365 days", "gaps filled"),
        ("Territories", ", ".join(REGIONS)),
        ("Customers spread across the territories (demo customers re-assigned round-robin)", "all customers"),
        ("Submitted tagged Sales Invoices in LAST month", scaled(INVOICES_PER_WINDOW, scale, 3)),
        ("Submitted tagged Sales Invoices in the CURRENT month", scaled(INVOICES_PER_WINDOW, scale, 3)),
        (f"Query Report '{REPORT_NAME}'", "1 report"),
        (f"Custom DocType '{BOOKING_DOCTYPE}' (Customer, Date, Currency amount)", "1 doctype"),
        (f"Submitted '{BOOKING_DOCTYPE}' rows", scaled(BOOKINGS_TOTAL, scale, 50)),
        (f"'{BOOKING_DOCTYPE}' rows dated in the current month", scaled(BOOKINGS_THIS_MONTH, scale, 3)),
        (f"Stock item '{STOCK_ITEM}' received into a warehouse", "2 Material Receipts"),
        (f"Supplier '{VENDOR}' with purchase invoices each paid by a Payment Entry", VENDOR_PAYMENTS),
    ]


def run(scale: float = 1.0) -> None:
    today = frappe.utils.getdate(nowdate())
    company = ensure_demo_company()
    ensure_fiscal_years(today)
    territories = [ensure_territory(name) for name in REGIONS]
    customers = ensure_customers(territories)
    ensure_item(SERVICE_ITEM, 0)
    ensure_item(STOCK_ITEM, 1)
    ensure_recent_invoices(company, customers, today, scale)
    ensure_region_report()
    ensure_booking_doctype()
    ensure_bookings(customers, today, scale)
    ensure_stock(company, today)
    ensure_vendor_payments(company, today)
    # CLI setup script, not a request: batch commits keep it resumable
    frappe.db.commit()  # nosemgrep
    print_counts(
        "Realistic site",
        [
            ("Customer", None),
            ("Sales Invoice", {"docstatus": 1}),
            ("Purchase Invoice", {"docstatus": 1}),
            ("Payment Entry", {"docstatus": 1}),
            (BOOKING_DOCTYPE, {"docstatus": 1}),
            ("GL Entry", None),
        ],
    )


def ensure_demo_company() -> str:
    demo = frappe.db.get_single_value("Global Defaults", "demo_company")
    if demo and frappe.db.exists("Company", demo):
        print(f"Demo company already present: {demo}")
        return demo
    source = frappe.db.get_single_value("Global Defaults", "default_company")
    print(f"Creating ERPNext demo data from company {source} (takes a few minutes)")
    call_setup_demo_data(source)
    demo = frappe.db.get_single_value("Global Defaults", "demo_company")
    # setup_demo_data swallows its own exceptions into an Error Log, so verify it worked.
    if not demo or not frappe.db.exists("Company", demo):
        raise RuntimeError("Demo data creation failed; see Error Log on the site")
    return demo


def ensure_customers(territories: list) -> list:
    """Make sure there are at least 8 customers and spread them over the territories.

    Only customers still in a non-RC territory are reassigned, so a re-run keeps earlier assignments.
    """
    existing = frappe.get_all("Customer", pluck="name", order_by="name asc")
    for number in range(len(existing) + 1, 9):
        existing.append(ensure_customer(f"RC Customer {number}", territories[0]))
    for index, name in enumerate(existing):
        if frappe.db.get_value("Customer", name, "territory") not in territories:
            frappe.db.set_value("Customer", name, "territory", territories[index % len(territories)])
    return existing


def ensure_recent_invoices(company: str, customers: list, today, scale: float) -> None:
    generator = rng()
    windows = {"last month": month_window(today, 1), "current month": month_window(today, 0)}
    target = scaled(INVOICES_PER_WINDOW, scale, 3)
    for label, (start, end) in windows.items():
        end = min(end, today)
        have = frappe.db.count(
            "Sales Invoice",
            {"remarks": TAG, "docstatus": 1, "posting_date": ["between", [start, end]]},
        )
        for _ in range(max(0, target - have)):
            posting = clamp_to_fiscal_years(add_days(start, generator.randint(0, (end - start).days)), today)
            make_sales_invoice(
                company,
                generator.choice(customers),
                [(SERVICE_ITEM, generator.randint(1, 5), generator.randint(100, 900), None)],
                posting,
                TAG,
            )
        print(f"Sales Invoices {label}: target {target}, had {have}")


def ensure_region_report() -> None:
    if frappe.db.exists("Report", REPORT_NAME):
        print(f"Report '{REPORT_NAME}' already present")
        return
    frappe.get_doc(
        {
            "doctype": "Report",
            "report_name": REPORT_NAME,
            "ref_doctype": "Sales Invoice",
            "report_type": "Query Report",
            "is_standard": "No",
            "query": REGION_REPORT_QUERY,
            "roles": [{"role": "Accounts User"}, {"role": "Accounts Manager"}, {"role": "System Manager"}],
        }
    ).insert(ignore_permissions=True)
    print(f"Created Query Report '{REPORT_NAME}'")


def ensure_booking_doctype() -> None:
    if frappe.db.exists("DocType", BOOKING_DOCTYPE):
        print(f"DocType '{BOOKING_DOCTYPE}' already present")
        return
    frappe.get_doc(
        {
            "doctype": "DocType",
            "name": BOOKING_DOCTYPE,
            "module": "Custom",
            "custom": 1,
            "is_submittable": 1,
            "autoname": "format:BKG-{#####}",
            "fields": [
                {
                    "fieldname": "customer",
                    "label": "Customer",
                    "fieldtype": "Link",
                    "options": "Customer",
                    "reqd": 1,
                    "in_list_view": 1,
                },
                {
                    "fieldname": "booking_date",
                    "label": "Date",
                    "fieldtype": "Date",
                    "reqd": 1,
                    "in_list_view": 1,
                },
                {
                    "fieldname": "amount",
                    "label": "Amount",
                    "fieldtype": "Currency",
                    "reqd": 1,
                    "in_list_view": 1,
                },
            ],
            "permissions": [
                {
                    "role": "System Manager",
                    "read": 1,
                    "write": 1,
                    "create": 1,
                    "submit": 1,
                    "cancel": 1,
                    "delete": 1,
                    "report": 1,
                    "export": 1,
                }
            ],
        }
    ).insert(ignore_permissions=True)
    print(f"Created DocType '{BOOKING_DOCTYPE}'")


def ensure_bookings(customers: list, today, scale: float) -> None:
    generator = rng()
    month_start, _ = month_window(today, 0)
    total_target = scaled(BOOKINGS_TOTAL, scale, 50)
    month_target = scaled(BOOKINGS_THIS_MONTH, scale, 3)
    month_filter = {"docstatus": 1, "booking_date": ["between", [month_start, today]]}
    this_month = frappe.db.count(BOOKING_DOCTYPE, month_filter)
    for _ in range(max(0, month_target - this_month)):
        make_booking(
            customers, add_days(month_start, generator.randint(0, (today - month_start).days)), generator
        )
    total = frappe.db.count(BOOKING_DOCTYPE, {"docstatus": 1})
    for _ in range(max(0, total_target - total)):
        make_booking(customers, add_days(today, -generator.randint(0, 120)), generator)
    print(f"Bookings: {frappe.db.count(BOOKING_DOCTYPE, {'docstatus': 1})} submitted")


def make_booking(customers: list, booking_date, generator) -> None:
    doc = frappe.get_doc(
        {
            "doctype": BOOKING_DOCTYPE,
            "customer": generator.choice(customers),
            "booking_date": booking_date,
            "amount": generator.randint(5, 200) * 10,
        }
    )
    doc.insert(ignore_permissions=True)
    doc.submit()


def ensure_stock(company: str, today) -> None:
    if count_tagged("Stock Entry", TAG) >= 2:
        print("Stock receipts already present")
        return
    for days_back, qty, rate in ((40, 120, 25), (10, 60, 27)):
        make_material_receipt(
            company, STOCK_ITEM, qty, rate, clamp_to_fiscal_years(add_days(today, -days_back), today), TAG
        )


def ensure_vendor_payments(company: str, today) -> None:
    ensure_supplier(VENDOR)
    have = frappe.db.count("Payment Entry", {"remarks": TAG, "docstatus": 1, "party": VENDOR})
    expense_account = frappe.get_cached_value("Company", company, "default_expense_account")
    for number in range(have, VENDOR_PAYMENTS):
        posting = clamp_to_fiscal_years(add_days(today, -(60 - number * 15)), today)
        invoice = frappe.get_doc(
            {
                "doctype": "Purchase Invoice",
                "company": company,
                "supplier": VENDOR,
                "set_posting_time": 1,
                "posting_date": posting,
                "bill_date": posting,
                "due_date": posting,
                "remarks": TAG,
                "items": [
                    {
                        "item_code": SERVICE_ITEM,
                        "qty": 1,
                        "rate": 1000 + number * 250,
                        "expense_account": expense_account,
                    }
                ],
            }
        )
        invoice.insert(ignore_permissions=True)
        invoice.submit()
        make_payment_for("Purchase Invoice", invoice.name, posting, TAG)
    print(f"Vendor payments for {VENDOR}: {VENDOR_PAYMENTS}")


if __name__ == "__main__":
    run_cli("Build the realistic release-check site", plan, run)
