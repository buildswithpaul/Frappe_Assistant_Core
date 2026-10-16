"""Shared helpers for the release-check site setup scripts.

Dev tooling, not part of the app: it runs from the command line against a
bench site you built for the release check, never inside a web request, so it
commits in batches and creates documents directly.
"""

import argparse
import inspect
import os
import random
from datetime import date

import frappe
from frappe.utils import add_days, add_months, getdate

SEED = 20261016


def parse_args(description: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--site", help="Bench site name (required unless --dry-run)")
    parser.add_argument(
        "--sites-path",
        default=os.environ.get("FRAPPE_SITES_PATH"),
        help="Bench sites directory (default: $FRAPPE_SITES_PATH, else the current directory if it holds "
        "the site, else ./sites)",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="Multiplier on the document counts. 1.0 is the full dataset; use 0.01 for a smoke test.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the plan without touching the database")
    return parser.parse_args()


def run_cli(description: str, plan, run) -> None:
    """Entry point shared by both scripts: --dry-run prints plan(scale); otherwise connect and run(scale)."""
    args = parse_args(description)
    if args.dry_run:
        print_plan(plan(args.scale), args.scale)
        return
    if not args.site:
        raise SystemExit("--site is required unless --dry-run is given")
    frappe.init(args.site, sites_path=resolve_sites_path(args.sites_path, args.site))
    frappe.connect()
    try:
        # CLI setup script, runs as Administrator by design
        frappe.set_user("Administrator")  # nosemgrep
        frappe.flags.mute_emails = True
        run(args.scale)
        # CLI setup script, not a request: batch commits keep it resumable
        frappe.db.commit()  # nosemgrep
    finally:
        frappe.destroy()


def resolve_sites_path(given, site: str) -> str:
    """Run from <bench>/sites (the documented place) or from <bench>: pick the directory that holds the site."""
    candidates = [given] if given else [".", "./sites"]
    for path in candidates:
        if os.path.isdir(os.path.join(path, site)):
            return path
    raise SystemExit(f"Site {site} not found under {candidates}; run from <bench>/sites or pass --sites-path")


def print_plan(steps: list, scale: float) -> None:
    print(f"DRY RUN (scale={scale}): nothing is written. Each step is skipped if its target is already met.")
    for number, (label, target) in enumerate(steps, 1):
        print(f"  {number}. {label}: target {target}")


def scaled(base: int, scale: float, minimum: int = 1) -> int:
    return max(minimum, round(base * scale))


def rng() -> random.Random:
    return random.Random(SEED)


def print_counts(label: str, doctypes_filters: list) -> None:
    print(f"\n{label} - counts")
    for doctype, filters in doctypes_filters:
        print(f"  {doctype} {filters or ''}: {frappe.db.count(doctype, filters or {})}")


# ---- dates ---------------------------------------------------------------


def month_window(today: date, months_back: int = 0) -> tuple:
    first_of_this_month = today.replace(day=1)
    start = add_months(first_of_this_month, -months_back)
    end = add_days(add_months(start, 1), -1)
    return getdate(start), getdate(end)


def quarter_start(today: date) -> date:
    return today.replace(month=3 * ((today.month - 1) // 3) + 1, day=1)


def ensure_fiscal_years(today: date) -> None:
    """Make sure dates from one year back to today fall inside a Fiscal Year.

    ERPNext refuses to post outside a Fiscal Year, and a fresh site only has
    the current one, which would leave "last month" empty early in the year.
    """
    earliest = add_days(today, -365)
    for probe in (earliest, today):
        if covering_fiscal_year(probe):
            continue
        start, end = free_span(probe)
        year = f"RC-{probe.year}"
        if frappe.db.exists("Fiscal Year", year):
            continue
        frappe.get_doc(
            {"doctype": "Fiscal Year", "year": year, "year_start_date": start, "year_end_date": end}
        ).insert(ignore_permissions=True)
        print(f"  created Fiscal Year {year}")


def free_span(day: date) -> tuple:
    """Calendar year around `day`, trimmed so it cannot overlap an existing Fiscal Year."""
    start, end = date(day.year, 1, 1), date(day.year, 12, 31)
    previous_ends = frappe.get_all(
        "Fiscal Year",
        filters={"year_end_date": ["<", day]},
        pluck="year_end_date",
        order_by="year_end_date desc",
        limit=1,
    )
    next_starts = frappe.get_all(
        "Fiscal Year",
        filters={"year_start_date": [">", day]},
        pluck="year_start_date",
        order_by="year_start_date asc",
        limit=1,
    )
    if previous_ends:
        start = max(start, getdate(add_days(previous_ends[0], 1)))
    if next_starts:
        end = min(end, getdate(add_days(next_starts[0], -1)))
    return start, end


def covering_fiscal_year(day: date):
    rows = frappe.get_all(
        "Fiscal Year",
        filters={"year_start_date": ["<=", day], "year_end_date": [">=", day]},
        pluck="name",
        limit=1,
    )
    return rows[0] if rows else None


def clamp_to_fiscal_years(day: date, today: date) -> date:
    """Pull a date forward until it is inside some Fiscal Year (never past today)."""
    while day < today and not covering_fiscal_year(day):
        day = add_days(day, 30)
    return getdate(min(day, today))


# ---- masters -------------------------------------------------------------


def leaf_name(doctype: str, fallback_filters: dict = None) -> str:
    filters = {"is_group": 0}
    filters.update(fallback_filters or {})
    rows = frappe.get_all(doctype, filters=filters, pluck="name", limit=1, order_by="creation asc")
    if not rows:
        raise RuntimeError(f"No leaf {doctype} found; is the site's setup wizard complete?")
    return rows[0]


def ensure_territory(name: str) -> str:
    if not frappe.db.exists("Territory", name):
        frappe.get_doc(
            {
                "doctype": "Territory",
                "territory_name": name,
                "parent_territory": "All Territories",
                "is_group": 0,
            }
        ).insert(ignore_permissions=True)
    return name


def ensure_customer(name: str, territory: str) -> str:
    if frappe.db.exists("Customer", name):
        return name
    frappe.get_doc(
        {
            "doctype": "Customer",
            "customer_name": name,
            "customer_type": "Company",
            "customer_group": leaf_name("Customer Group"),
            "territory": territory,
        }
    ).insert(ignore_permissions=True)
    return name


def ensure_supplier(name: str) -> str:
    if frappe.db.exists("Supplier", name):
        return name
    frappe.get_doc(
        {
            "doctype": "Supplier",
            "supplier_name": name,
            "supplier_group": leaf_name("Supplier Group"),
        }
    ).insert(ignore_permissions=True)
    return name


def ensure_item(code: str, is_stock_item: int) -> str:
    if frappe.db.exists("Item", code):
        return code
    frappe.get_doc(
        {
            "doctype": "Item",
            "item_code": code,
            "item_name": code,
            "item_group": leaf_name("Item Group"),
            "stock_uom": "Nos",
            "is_stock_item": is_stock_item,
        }
    ).insert(ignore_permissions=True)
    return code


def ensure_income_account(company: str, name: str) -> str:
    """Create a leaf income account under the company's Direct Income (or default income) parent."""
    abbr = frappe.get_cached_value("Company", company, "abbr")
    full_name = f"{name} - {abbr}"
    if frappe.db.exists("Account", full_name):
        return full_name
    default_income = frappe.get_cached_value("Company", company, "default_income_account")
    parent = frappe.db.get_value("Account", default_income, "parent_account")
    frappe.get_doc(
        {
            "doctype": "Account",
            "account_name": name,
            "parent_account": parent,
            "company": company,
            "root_type": "Income",
            "account_type": "Income Account",
            "is_group": 0,
        }
    ).insert(ignore_permissions=True)
    return full_name


# ---- transactions --------------------------------------------------------


def make_sales_invoice(company: str, customer: str, lines: list, posting_date: date, tag: str):
    """Create and submit a Sales Invoice. lines = [(item_code, qty, rate, income_account or None)]."""
    items = []
    for item_code, qty, rate, income_account in lines:
        row = {"item_code": item_code, "qty": qty, "rate": rate}
        if income_account:
            row["income_account"] = income_account
        items.append(row)
    invoice = frappe.get_doc(
        {
            "doctype": "Sales Invoice",
            "company": company,
            "customer": customer,
            "set_posting_time": 1,
            "posting_date": posting_date,
            "due_date": add_days(posting_date, 30),
            "update_stock": 0,
            "remarks": tag,
            "items": items,
        }
    )
    invoice.insert(ignore_permissions=True)
    invoice.submit()
    return invoice


def make_payment_for(doctype: str, name: str, posting_date: date, tag: str):
    """Create and submit a full Payment Entry against an invoice, the way the Pay button does."""
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

    payment = get_payment_entry(doctype, name)
    payment.posting_date = posting_date
    payment.reference_no = name
    payment.reference_date = posting_date
    payment.remarks = tag
    # PaymentEntry.set_remarks() rewrites remarks on every validate unless custom_remarks is set
    payment.custom_remarks = 1
    if not (payment.paid_to if payment.payment_type == "Receive" else payment.paid_from):
        company = payment.company
        account = frappe.get_cached_value("Company", company, "default_bank_account") or (
            frappe.get_cached_value("Company", company, "default_cash_account")
        )
        if payment.payment_type == "Receive":
            payment.paid_to = account
        else:
            payment.paid_from = account
    payment.insert(ignore_permissions=True)
    payment.submit()
    return payment


def make_material_receipt(
    company: str, item_code: str, qty: float, rate: float, posting_date: date, tag: str
):
    warehouse = frappe.db.get_value(
        "Warehouse", {"company": company, "is_group": 0, "disabled": 0}, "name", order_by="creation asc"
    )
    row = {"item_code": item_code, "qty": qty, "basic_rate": rate, "t_warehouse": warehouse}
    difference_account = frappe.get_cached_value("Company", company, "stock_adjustment_account")
    if difference_account:
        row["expense_account"] = difference_account
    entry = frappe.get_doc(
        {
            "doctype": "Stock Entry",
            "stock_entry_type": "Material Receipt",
            "company": company,
            "set_posting_time": 1,
            "posting_date": posting_date,
            "to_warehouse": warehouse,
            "remarks": tag,
            "items": [row],
        }
    )
    entry.insert(ignore_permissions=True)
    entry.submit()
    return entry


def count_tagged(doctype: str, tag: str, docstatus: int = 1) -> int:
    return frappe.db.count(doctype, {"remarks": tag, "docstatus": docstatus})


def call_setup_demo_data(company_name: str) -> None:
    """ERPNext v16 takes the source company name; v15 takes no argument."""
    from erpnext.setup.demo import setup_demo_data

    if inspect.signature(setup_demo_data).parameters:
        setup_demo_data(company_name)
    else:
        setup_demo_data()
