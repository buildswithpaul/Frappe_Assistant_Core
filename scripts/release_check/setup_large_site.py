"""Build the "large" release-check site: enough volume that ledger reports become prepared reports.

Targets at --scale 1.0 (the brief's minimums):
  * >= 20,000 submitted Sales Invoices (6 income lines each -> 7 GL rows apiece)
  * ~60% of them paid by a submitted Payment Entry (2 GL rows apiece)
  * Journal Entries (one debit row per customer, one credit row) topping GL Entry up to >= 200,000
  * a few hundred Material Receipts so Stock Balance has a real ledger

Real submitted documents are used throughout, so GL Entry / Stock Ledger Entry
are written by ERPNext exactly as in production and the reports compute from
them. It commits every BATCH documents and is resumable and idempotent: each
step counts what exists (by the remarks tag) and creates only the shortfall.

    cd <bench>/sites
    ../env/bin/python <fac-repo>/scripts/release_check/setup_large_site.py --site large.test
    ... --scale 0.01       # smoke test: ~200 invoices, ~2,000 GL rows
    ... --dry-run          # print the plan only, no database needed

Runtime at scale 1.0 is an estimate, not a measurement: about 3-6 hours on a
laptop (about 0.3-0.5 s per submitted invoice, ~1 s per payment, ~2-3 s per
Journal Entry). Calibrate with --scale 0.01 first and multiply.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import frappe  # noqa: E402
from frappe.utils import add_days, nowdate  # noqa: E402
from site_common import (  # noqa: E402
    clamp_to_fiscal_years,
    count_tagged,
    ensure_customer,
    ensure_fiscal_years,
    ensure_income_account,
    ensure_item,
    ensure_territory,
    make_material_receipt,
    make_payment_for,
    make_sales_invoice,
    print_counts,
    rng,
    run_cli,
    scaled,
)

TAG = "release-check:large"
CUSTOMERS = 200
INCOME_LINES = 6
SALES_INVOICES = 20_000
PAID_FRACTION = 0.6
GL_ENTRIES = 200_000
STOCK_RECEIPTS = 300
STOCK_ITEMS = 20
BATCH = 200
PREPARED_REPORTS = ["Accounts Receivable", "General Ledger", "Stock Balance"]
REGIONS = ["RC North", "RC South", "RC East", "RC West"]


def plan(scale: float) -> list:
    return [
        ("Fiscal Years covering the last 365 days", "gaps filled"),
        ("Territories / customers", f"{len(REGIONS)} / {scaled(CUSTOMERS, scale, 10)}"),
        (f"Income accounts and service items ({INCOME_LINES} each)", INCOME_LINES),
        ("Submitted tagged Sales Invoices (6 lines, 7 GL rows each)", scaled(SALES_INVOICES, scale, 10)),
        ("Submitted tagged Payment Entries", scaled(round(SALES_INVOICES * PAID_FRACTION), scale, 5)),
        (f"Stock items ({STOCK_ITEMS}) and Material Receipts", scaled(STOCK_RECEIPTS, scale, 5)),
        (
            "Journal Entries until GL Entry rows reach the target",
            f">= {scaled(GL_ENTRIES, scale, 100)} GL rows",
        ),
        (f"Flag {', '.join(PREPARED_REPORTS)} as prepared reports", len(PREPARED_REPORTS)),
    ]


def run(scale: float = 1.0) -> None:
    today = frappe.utils.getdate(nowdate())
    company = frappe.db.get_single_value("Global Defaults", "default_company")
    if not company:
        raise RuntimeError("No default company; complete the setup wizard first")
    frappe.db.set_single_value("Stock Settings", "allow_negative_stock", 1)
    ensure_fiscal_years(today)
    customers = ensure_masters(scale)
    income_accounts, items = ensure_income_lines(company)
    ensure_invoices(company, customers, items, income_accounts, today, scale)
    ensure_payments(today, scale)
    ensure_stock(company, today, scale)
    ensure_journal_entries(company, customers, income_accounts[0], today, scale)
    flag_prepared_reports()
    # CLI setup script, not a request: batch commits keep it resumable
    frappe.db.commit()  # nosemgrep
    print_counts(
        "Large site",
        [
            ("GL Entry", None),
            ("Sales Invoice", {"docstatus": 1}),
            ("Payment Entry", {"docstatus": 1}),
            ("Journal Entry", {"docstatus": 1}),
            ("Stock Ledger Entry", None),
        ],
    )


def progress(label: str, done: int, total: int, started: float) -> None:
    elapsed = time.monotonic() - started
    print(f"  {label}: {done}/{total} ({elapsed:.0f}s elapsed)", flush=True)


def ensure_masters(scale: float) -> list:
    territories = [ensure_territory(name) for name in REGIONS]
    names = []
    for number in range(1, scaled(CUSTOMERS, scale, 10) + 1):
        names.append(
            ensure_customer(f"RC Large Customer {number:04d}", territories[number % len(territories)])
        )
    # CLI setup script, not a request: batch commits keep it resumable
    frappe.db.commit()  # nosemgrep
    return names


def ensure_income_lines(company: str) -> tuple:
    accounts, items = [], []
    for number in range(1, INCOME_LINES + 1):
        accounts.append(ensure_income_account(company, f"RC Income {number}"))
        items.append(ensure_item(f"RC Service {number}", 0))
    # CLI setup script, not a request: batch commits keep it resumable
    frappe.db.commit()  # nosemgrep
    return accounts, items


def ensure_invoices(company, customers, items, accounts, today, scale) -> None:
    target = scaled(SALES_INVOICES, scale, 10)
    have = count_tagged("Sales Invoice", TAG)
    generator = rng()
    # advance the generator past what earlier runs consumed so a resume does not repeat the same rows
    for _ in range(have * 2):
        generator.random()
    started = time.monotonic()
    for done in range(have, target):
        posting = clamp_to_fiscal_years(add_days(today, -generator.randint(0, 364)), today)
        lines = [
            (item, generator.randint(1, 10), generator.randint(50, 500), account)
            for item, account in zip(items, accounts)
        ]
        make_sales_invoice(company, generator.choice(customers), lines, posting, TAG)
        if (done + 1) % BATCH == 0:
            # CLI setup script, not a request: batch commits keep it resumable
            frappe.db.commit()  # nosemgrep
            progress("Sales Invoices", done + 1, target, started)
    # CLI setup script, not a request: batch commits keep it resumable
    frappe.db.commit()  # nosemgrep
    print(f"Sales Invoices: target {target}, had {have}")


def ensure_payments(today, scale: float) -> None:
    target = scaled(round(SALES_INVOICES * PAID_FRACTION), scale, 5)
    have = count_tagged("Payment Entry", TAG)
    needed = max(0, target - have)
    if not needed:
        print(f"Payment Entries: target {target}, had {have}")
        return
    unpaid = frappe.get_all(
        "Sales Invoice",
        filters={"remarks": TAG, "docstatus": 1, "outstanding_amount": [">", 0]},
        fields=["name", "posting_date"],
        order_by="posting_date asc, name asc",
        limit=needed,
    )
    started = time.monotonic()
    for done, invoice in enumerate(unpaid, 1):
        make_payment_for("Sales Invoice", invoice.name, min(add_days(invoice.posting_date, 10), today), TAG)
        if done % BATCH == 0:
            # CLI setup script, not a request: batch commits keep it resumable
            frappe.db.commit()  # nosemgrep
            progress("Payment Entries", done, len(unpaid), started)
    # CLI setup script, not a request: batch commits keep it resumable
    frappe.db.commit()  # nosemgrep
    print(f"Payment Entries: target {target}, had {have}, created {len(unpaid)}")


def ensure_stock(company: str, today, scale: float) -> None:
    items = [ensure_item(f"RC Stock Item {number:02d}", 1) for number in range(1, STOCK_ITEMS + 1)]
    target = scaled(STOCK_RECEIPTS, scale, 5)
    have = count_tagged("Stock Entry", TAG)
    generator = rng()
    for _ in range(have):
        generator.random()
    for done in range(have, target):
        posting = clamp_to_fiscal_years(add_days(today, -generator.randint(0, 364)), today)
        make_material_receipt(
            company,
            generator.choice(items),
            generator.randint(10, 200),
            generator.randint(5, 80),
            posting,
            TAG,
        )
        if (done + 1) % BATCH == 0:
            # CLI setup script, not a request: batch commits keep it resumable
            frappe.db.commit()  # nosemgrep
    # CLI setup script, not a request: batch commits keep it resumable
    frappe.db.commit()  # nosemgrep
    print(f"Stock Entries: target {target}, had {have}")


def ensure_journal_entries(company, customers, credit_account, today, scale) -> None:
    """Top GL Entry up to the target with wide Journal Entries.

    Each JE debits Debtors once per customer (distinct party, so ERPNext's
    similar-entry merge keeps every row) against one income credit: len(customers)+1 GL rows.
    """
    target = scaled(GL_ENTRIES, scale, 100)
    receivable = frappe.get_cached_value("Company", company, "default_receivable_account")
    cost_center = frappe.get_cached_value("Company", company, "cost_center")
    generator = rng()
    started = time.monotonic()
    created = 0
    while frappe.db.count("GL Entry") < target:
        posting = clamp_to_fiscal_years(add_days(today, -generator.randint(0, 364)), today)
        accounts = [
            {
                "account": receivable,
                "party_type": "Customer",
                "party": customer,
                "debit_in_account_currency": generator.randint(10, 100),
                "cost_center": cost_center,
            }
            for customer in customers
        ]
        total = sum(row["debit_in_account_currency"] for row in accounts)
        accounts.append(
            {"account": credit_account, "credit_in_account_currency": total, "cost_center": cost_center}
        )
        entry = frappe.get_doc(
            {
                "doctype": "Journal Entry",
                "voucher_type": "Journal Entry",
                "company": company,
                "posting_date": posting,
                "user_remark": TAG,
                "accounts": accounts,
            }
        )
        entry.insert(ignore_permissions=True)
        entry.submit()
        created += 1
        if created % 10 == 0:
            # CLI setup script, not a request: batch commits keep it resumable
            frappe.db.commit()  # nosemgrep
            progress("GL Entry rows", frappe.db.count("GL Entry"), target, started)
    # CLI setup script, not a request: batch commits keep it resumable
    frappe.db.commit()  # nosemgrep
    print(f"GL Entry rows now >= {target} ({created} Journal Entries created)")


def flag_prepared_reports() -> None:
    """Set prepared_report on the heavy reports.

    Frappe also flips this automatically once a run exceeds 15 seconds
    (Report.execute_script_report); setting it makes the release check
    deterministic instead of depending on the machine's speed.
    """
    for report in PREPARED_REPORTS:
        if frappe.db.get_value("Report", report, "prepared_report") != 1:
            frappe.db.set_value("Report", report, "prepared_report", 1)
            print(f"Flagged '{report}' as a prepared report")


if __name__ == "__main__":
    run_cli("Build the large release-check site", plan, run)
