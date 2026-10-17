# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Signals for the FAC Chat home "Needs you" list.

A signal is a cheap, permission-aware count of something that needs the user's
attention. Signals live in ``CATALOGUE``; ``compute_home_signals`` evaluates the
ones that apply to the user's role lens and ``rank`` orders them.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

import frappe
from frappe import _
from frappe.utils import add_days, fmt_money, get_datetime, now_datetime, today

from frappe_assistant_core.plugins.core.tools.get_pending_approvals import _open_workflow_actions

LENS_ROLES: dict[str, tuple[str, ...]] = {
    "accounts": ("Accounts Manager", "Accounts User"),
    "sales": ("Sales Manager", "Sales User"),
    "stock": ("Stock Manager", "Stock User", "Purchase Manager", "Purchase User", "Item Manager"),
    "hr": ("HR Manager", "HR User"),
    "support": ("Support Team", "Helpdesk Agent"),
}

LENS_AREA = {
    "accounts": "books",
    "sales": "pipeline",
    "stock": "stock",
    "hr": "team",
    "support": "tickets",
}
DEFAULT_AREA = "business"

TONE_RANK = {"danger": 0, "warning": 1, "neutral": 2}

ITEMS_CAP = 3
APPROVALS_LIMIT = 200
OVERDUE_DAYS = 60
PAYABLES_WINDOW_DAYS = 7
TOP_CUSTOMERS = 2
QUOTATION_WINDOW_DAYS = 7
STALE_LEAD_DAYS = 14
LEAVE_START_WINDOW_DAYS = 3
REORDER_ITEMS_LIMIT = 500
ERROR_LOG_INTERVAL = 3600
ERROR_KEY_PREFIX = "fac_home_signals_err:"

# Lenses that only exist when the app providing their DocTypes is installed.
_LENS_REQUIRES_APP = {"hr": "hrms"}


def _lens_label(lens: str) -> str:
    """Translated display name of a lens."""
    labels = {
        "accounts": _("Accounts"),
        "sales": _("Sales"),
        "stock": _("Stock & Purchase"),
        "hr": _("HR"),
        "support": _("Support"),
    }
    return labels[lens]


@dataclass
class SignalResult:
    count: int
    title: str
    detail: str
    ask: str
    action: str
    source: str
    amount: float | None = None
    currency: str | None = None


@dataclass(frozen=True)
class Signal:
    id: str
    lenses: tuple[str, ...]
    tone: str
    requires_doctypes: tuple[str, ...]
    requires_apps: tuple[str, ...]
    compute: Callable[[str, str | None], SignalResult | None]


def _lens_app_installed(lens: str, installed_apps: list[str]) -> bool:
    required = _LENS_REQUIRES_APP.get(lens)
    return required is None or required in installed_apps


def resolve_lenses(roles: list[str], installed_apps: list[str]) -> list[str]:
    """Lenses matching the user's roles, in ``LENS_ROLES`` order."""
    role_set = set(roles)
    return [
        lens
        for lens, lens_roles in LENS_ROLES.items()
        if role_set.intersection(lens_roles) and _lens_app_installed(lens, installed_apps)
    ]


def rank(results: list[tuple[Signal, SignalResult]], cap: int) -> list[dict]:
    """Drop empty results, order by tone then catalogue position, keep ``cap``."""
    order = {signal.id: index for index, signal in enumerate(CATALOGUE)}
    live = [(s, r) for s, r in results if r.count]
    live.sort(key=lambda pair: (TONE_RANK[pair[0].tone], order.get(pair[0].id, len(order))))
    return [
        {
            "id": signal.id,
            "tone": signal.tone,
            "source": result.source,
            "count": result.count,
            "title": result.title,
            "detail": result.detail,
            "ask": result.ask,
            "action": result.action,
        }
        for signal, result in live[:cap]
    ]


def _is_applicable(signal: Signal, user: str, lenses: list[str], installed_apps: list[str]) -> bool:
    if signal.lenses and not set(signal.lenses).intersection(lenses):
        return False
    if any(app not in installed_apps for app in signal.requires_apps):
        return False
    for doctype in signal.requires_doctypes:
        if not frappe.db.exists("DocType", doctype) or not frappe.has_permission(doctype, "read", user=user):
            return False
    return True


def _log_signal_error(signal_id: str) -> None:
    """Log a failing signal at most once per hour."""
    key = ERROR_KEY_PREFIX + signal_id
    last = frappe.cache.get_value(key)
    now = time.time()
    if last and now - float(last) < ERROR_LOG_INTERVAL:
        return
    frappe.cache.set_value(key, now)
    # Deferred: the home endpoint is a GET, which Frappe rolls back, so an immediate insert would vanish.
    frappe.log_error(title=f"Home signal failed: {signal_id}", defer_insert=True)


def _primary_lens(ranked_lenses: list[str], lenses: list[str]) -> str | None:
    if ranked_lenses:
        return ranked_lenses[0]
    return lenses[0] if lenses else None


def compute_home_signals(user: str) -> dict:
    """Build the home payload for ``user``."""
    installed_apps = frappe.get_installed_apps()
    lenses = resolve_lenses(frappe.get_roles(user), installed_apps)
    company = frappe.defaults.get_user_default("Company", user=user) or None

    results: list[tuple[Signal, SignalResult]] = []
    for signal in CATALOGUE:
        try:
            if not _is_applicable(signal, user, lenses, installed_apps):
                continue
            result = signal.compute(user, company)
        except Exception:
            _log_signal_error(signal.id)
            continue
        if result is not None:
            results.append((signal, result))

    items = rank(results, ITEMS_CAP)
    by_id = {signal.id: signal for signal, _result in results}
    ranked_lenses = [lens for item in items for lens in by_id[item["id"]].lenses if lens in lenses]
    lens = _primary_lens(ranked_lenses, lenses)

    return {
        "lens": lens,
        "lens_label": _lens_label(lens) if lens else None,
        "lenses": lenses,
        "area": LENS_AREA[lens] if len(lenses) == 1 else DEFAULT_AREA,
        "company": company,
        "items": items,
    }


def count_visible(doctype: str, filters: dict | list, user: str) -> int:
    """Count records of ``doctype`` that ``user`` may read (User Permissions apply)."""
    # Frappe v16 only accepts the dict aggregate and v15 only the string form.
    try:
        rows = frappe.get_list(
            doctype, filters=filters, fields=[{"COUNT": "name", "as": "n"}], order_by="", user=user
        )
    except Exception:
        rows = frappe.get_list(doctype, filters=filters, fields=["count(name) as n"], order_by="", user=user)
    return int(rows[0]["n"]) if rows else 0


def _readable_approvals(user: str, limit: int) -> list[frappe._dict]:
    """Open Workflow Actions for ``user`` whose documents ``user`` may read.

    The Workflow Action query only matches roles and users, so each reference
    DocType is re-checked through ``get_list`` to apply User Permissions.
    """
    actions = _open_workflow_actions(user, limit)
    names_by_doctype: dict[str, set[str]] = {}
    for action in actions:
        names_by_doctype.setdefault(action.reference_doctype, set()).add(action.reference_name)

    readable: set[tuple[str, str]] = set()
    for doctype, names in names_by_doctype.items():
        if not frappe.db.exists("DocType", doctype) or not frappe.has_permission(doctype, "read", user=user):
            continue
        visible = frappe.get_list(doctype, filters={"name": ["in", list(names)]}, pluck="name", user=user)
        readable.update((doctype, name) for name in visible)
    return [a for a in actions if (a.reference_doctype, a.reference_name) in readable]


def approvals_for_user(user: str, limit: int = 200) -> dict[str, list[str]]:
    """Documents awaiting ``user``'s approval, as reference DocType to readable names."""
    grouped: dict[str, list[str]] = {}
    for action in _readable_approvals(user, limit):
        names = grouped.setdefault(action.reference_doctype, [])
        if action.reference_name not in names:
            names.append(action.reference_name)
    return grouped


def _waited_detail(doctype_label: str, days: int) -> str:
    """Whole-sentence detail for the oldest waiting approval, by day count."""
    if days <= 0:
        return _("Mostly {0}; the oldest arrived today.").format(doctype_label)
    if days == 1:
        return _("Mostly {0}; the oldest has waited 1 day.").format(doctype_label)
    return _("Mostly {0}; the oldest has waited {1} days.").format(doctype_label, days)


def _approvals_waiting(user: str, company: str | None) -> SignalResult | None:
    # APPROVALS_LIMIT caps the Workflow Action rows before the permission filter, so a user
    # with more unreadable actions than the limit can see an undercount.
    actions = _readable_approvals(user, APPROVALS_LIMIT)
    documents = {(a.reference_doctype, a.reference_name) for a in actions}
    count = len(documents)
    if not count:
        return None

    doctype_counts: dict[str, int] = {}
    for doctype, _name in documents:
        doctype_counts[doctype] = doctype_counts.get(doctype, 0) + 1
    top_doctype = max(doctype_counts, key=doctype_counts.get)
    oldest = min(get_datetime(a.creation) for a in actions)
    days = (now_datetime() - oldest).days
    return SignalResult(
        count=count,
        title=_("approval waiting for you") if count == 1 else _("approvals waiting for you"),
        detail=_waited_detail(_(top_doctype), days),
        ask=_("Show the documents waiting for my approval"),
        action=_("Review them"),
        source=_("Workflow · {0}").format(_(top_doctype)),
    )


def _todos_due(user: str, company: str | None) -> SignalResult | None:
    count = count_visible("ToDo", {"allocated_to": user, "status": "Open", "date": ["<=", today()]}, user)
    return SignalResult(
        count=count,
        title=_("task due") if count == 1 else _("tasks due"),
        detail=_("Open ToDos due today or overdue"),
        ask=_("Show my open ToDos that are due today or overdue"),
        action=_("See my tasks"),
        source=_("ToDo"),
    )


def money_summary(rows: list[dict]) -> tuple[float | None, str | None]:
    """Sum ``outstanding_amount`` when every row shares one ``currency``, else ``(None, None)``."""
    currencies = {row["currency"] for row in rows}
    if len(currencies) != 1:
        return None, None
    return sum(row["outstanding_amount"] for row in rows), currencies.pop()


def _company_scoped(filters: dict, company: str | None) -> dict:
    return {**filters, "company": company} if company else filters


def _invoice_rows(doctype: str, filters: dict, user: str, extra_fields: list[str]) -> list[dict]:
    """Outstanding invoices ``user`` may read, with the figure and its own currency.

    ``outstanding_amount`` is held in the party account currency, so that field
    is read as ``currency`` rather than the document currency.
    """
    rows = frappe.get_list(
        doctype,
        filters=filters,
        fields=["outstanding_amount", "party_account_currency", *extra_fields],
        user=user,
    )
    for row in rows:
        row["currency"] = row.pop("party_account_currency")
    return rows


def _top_customers(rows: list[dict]) -> tuple[list[str], int]:
    """The ``TOP_CUSTOMERS`` customers with the most outstanding, and how many customers there are."""
    totals: dict[str, float] = {}
    for row in rows:
        name = row.get("customer_name") or row["customer"]
        totals[name] = totals.get(name, 0) + row["outstanding_amount"]
    return sorted(totals, key=totals.get, reverse=True)[:TOP_CUSTOMERS], len(totals)


def _amount_text(rows: list[dict]) -> tuple[float | None, str | None, str | None]:
    amount, currency = money_summary(rows)
    text = fmt_money(amount, currency=currency) if amount is not None else None
    return amount, currency, text


def _overdue_receivables(user: str, company: str | None) -> SignalResult | None:
    filters = _company_scoped(
        {
            "docstatus": 1,
            "outstanding_amount": [">", 0],
            "due_date": ["<", add_days(today(), -OVERDUE_DAYS)],
        },
        company,
    )
    rows = _invoice_rows("Sales Invoice", filters, user, ["customer", "customer_name"])
    count = len(rows)
    if not count:
        return None

    amount, currency, text = _amount_text(rows)
    customers, customer_count = _top_customers(rows)
    who = customers[0] if len(customers) == 1 else _("{0} and {1}").format(*customers)
    all_of_them = customer_count <= TOP_CUSTOMERS
    if text:
        template = _("{0} outstanding, all from {1}") if all_of_them else _("{0} outstanding, mostly {1}")
        detail = template.format(text, who)
    else:
        detail = _("All from {0}").format(who) if all_of_them else _("Mostly {0}").format(who)
    return SignalResult(
        count=count,
        title=_("invoice overdue by 60+ days") if count == 1 else _("invoices overdue by 60+ days"),
        detail=detail,
        ask=(
            _("Show invoices for {0} overdue by more than 60 days, by customer").format(company)
            if company
            else _("Show invoices overdue by more than 60 days, by customer")
        ),
        action=_("Draft payment reminders"),
        source=_("Sales Invoice"),
        amount=amount,
        currency=currency,
    )


def _payables_due(user: str, company: str | None) -> SignalResult | None:
    filters = _company_scoped(
        {
            "docstatus": 1,
            "outstanding_amount": [">", 0],
            "due_date": ["between", [today(), add_days(today(), PAYABLES_WINDOW_DAYS)]],
        },
        company,
    )
    rows = _invoice_rows("Purchase Invoice", filters, user, [])
    count = len(rows)
    if not count:
        return None

    amount, currency, text = _amount_text(rows)
    return SignalResult(
        count=count,
        title=_("bill due in the next 7 days") if count == 1 else _("bills due in the next 7 days"),
        detail=_("{0} falls due in the next 7 days").format(text) if text else _("Due in the next 7 days"),
        ask=(
            _("Which purchase invoices for {0} fall due in the next 7 days?").format(company)
            if company
            else _("Which purchase invoices fall due in the next 7 days?")
        ),
        action=_("See what's due"),
        source=_("Purchase Invoice"),
        amount=amount,
        currency=currency,
    )


def _unreconciled_bank(user: str, company: str | None) -> SignalResult | None:
    count = count_visible(
        "Bank Transaction", _company_scoped({"docstatus": 1, "status": "Unreconciled"}, company), user
    )
    return SignalResult(
        count=count,
        title=_("bank line unreconciled") if count == 1 else _("bank lines unreconciled"),
        detail=_("Bank transactions not yet matched to a ledger entry"),
        ask=(
            _("Which bank transactions for {0} are still unreconciled?").format(company)
            if company
            else _("Which bank transactions are still unreconciled?")
        ),
        action=_("Suggest matches"),
        source=_("Bank Transaction"),
    )


def _quotations_expiring(user: str, company: str | None) -> SignalResult | None:
    count = count_visible(
        "Quotation",
        {
            "docstatus": 1,
            "status": "Open",
            "valid_till": ["between", [today(), add_days(today(), QUOTATION_WINDOW_DAYS)]],
        },
        user,
    )
    return SignalResult(
        count=count,
        title=_("quotation expires in the next 7 days")
        if count == 1
        else _("quotations expire in the next 7 days"),
        detail=_("Open quotations whose validity ends within a week"),
        ask=_("Which quotations expire in the next 7 days?"),
        action=_("Draft follow-ups"),
        source=_("Quotation"),
    )


def _late_sales_orders(user: str, company: str | None) -> SignalResult | None:
    count = count_visible(
        "Sales Order",
        _company_scoped(
            {
                "docstatus": 1,
                "delivery_date": ["<", today()],
                "per_delivered": ["<", 100],
                "status": ["not in", ["Closed", "Completed", "On Hold"]],
            },
            company,
        ),
        user,
    )
    return SignalResult(
        count=count,
        title=_("sales order past its delivery date")
        if count == 1
        else _("sales orders past their delivery date"),
        detail=_("Submitted orders that are not fully delivered"),
        ask=(
            _("Which sales orders for {0} are past their delivery date?").format(company)
            if company
            else _("Which sales orders are past their delivery date?")
        ),
        action=_("See what's holding them"),
        source=_("Sales Order"),
    )


def _crm_installed() -> bool:
    return "crm" in frappe.get_installed_apps()


def _closed_crm_deal_statuses() -> list[str]:
    """Names of the CRM Deal Statuses that end a deal (type Won or Lost).

    ``get_all`` is deliberate: this is configuration, not a user-visible count, and
    the deals themselves are still counted through ``get_list``.
    """
    return frappe.get_all("CRM Deal Status", filters={"type": ["in", ["Won", "Lost"]]}, pluck="name")


def _stale_sources(user: str) -> list[tuple[str, Callable[[], dict]]]:
    """The (DocType, filters factory) pairs whose records ``user`` owns, before the staleness cut-off.

    Filters are built lazily so a source whose configuration lookup fails drops only itself.
    """
    sources: list[tuple[str, Callable[[], dict]]] = [
        (
            "Lead",
            lambda: {"lead_owner": user, "status": ["not in", ["Converted", "Do Not Contact"]]},
        ),
        ("Opportunity", lambda: {"opportunity_owner": user, "status": "Open"}),
    ]
    if _crm_installed():
        sources.append(("CRM Lead", lambda: {"lead_owner": user, "converted": 0}))
        if frappe.db.exists("DocType", "CRM Deal Status"):
            sources.append(
                (
                    "CRM Deal",
                    lambda: {"deal_owner": user, "status": ["not in", _closed_crm_deal_statuses()]},
                )
            )
    return sources


def _stale_leads(user: str, company: str | None) -> SignalResult | None:
    cutoff = add_days(today(), -STALE_LEAD_DAYS)
    count = 0
    for doctype, build_filters in _stale_sources(user):
        try:
            if not frappe.db.exists("DocType", doctype) or not frappe.has_permission(
                doctype, "read", user=user
            ):
                continue
            count += count_visible(doctype, {**build_filters(), "modified": ["<", cutoff]}, user)
        except Exception:
            _log_signal_error(f"stale_leads {doctype}")
    return SignalResult(
        count=count,
        title=(
            _("lead or opportunity with no activity for 14 days")
            if count == 1
            else _("leads and opportunities with no activity for 14 days")
        ),
        detail=_("Records you own that nobody has touched in two weeks"),
        ask=_("Which of my leads and opportunities have had no activity for 14 days?"),
        action=_("Plan follow-ups"),
        source=_("Leads and opportunities"),
    )


def _low_stock_item_codes(warehouses: list[str]) -> list[str]:
    """Reorderable items whose projected quantity is at or below the reorder level of a warehouse.

    ``get_list`` cannot compare a Bin column with an Item Reorder column, so this is a
    ``frappe.qb`` join, limited to ``warehouses``; the caller applies the Item permission
    filter. The Item conditions mirror ERPNext's own reorder run (``reorder_item.py``).
    """
    bin_ = frappe.qb.DocType("Bin")
    reorder = frappe.qb.DocType("Item Reorder")
    item = frappe.qb.DocType("Item")
    query = (
        frappe.qb.from_(bin_)
        .join(reorder)
        .on((reorder.parent == bin_.item_code) & (reorder.warehouse == bin_.warehouse))
        .join(item)
        .on(item.name == bin_.item_code)
        .where(reorder.parenttype == "Item")
        .where(bin_.warehouse.isin(warehouses))
        .where(bin_.projected_qty <= reorder.warehouse_reorder_level)
        .where((item.disabled == 0) & (item.is_stock_item == 1))
        .where(item.end_of_life.isnull() | (item.end_of_life > today()))
        .select(bin_.item_code)
        .distinct()
        .orderby(bin_.item_code)
        .limit(REORDER_ITEMS_LIMIT)
    )
    return query.run(pluck="item_code")


def _below_reorder(user: str, company: str | None) -> SignalResult | None:
    # Scoped to the user's company through its warehouses (Bin has no company field), and to
    # the warehouses the user may read, so User Permissions on Warehouse apply to the Bin side.
    warehouse_filters = _company_scoped({"disabled": 0}, company)
    warehouses = frappe.get_list("Warehouse", filters=warehouse_filters, pluck="name", user=user)
    if not warehouses:
        return None
    codes = _low_stock_item_codes(warehouses)
    visible = (
        frappe.get_list("Item", filters={"name": ["in", codes]}, pluck="name", limit_page_length=0, user=user)
        if codes
        else []
    )
    count = len(visible)
    return SignalResult(
        count=count,
        title=_("item below its reorder level") if count == 1 else _("items below their reorder level"),
        detail=_("Stock has fallen under the reorder level of a warehouse"),
        ask=_("Which items are below their reorder level?"),
        action=_("Raise material requests"),
        source=_("Item"),
    )


def _late_purchase_orders(user: str, company: str | None) -> SignalResult | None:
    count = count_visible(
        "Purchase Order",
        _company_scoped(
            {
                "docstatus": 1,
                "schedule_date": ["<", today()],
                "per_received": ["<", 100],
                "status": ["not in", ["Closed", "Completed", "On Hold"]],
            },
            company,
        ),
        user,
    )
    return SignalResult(
        count=count,
        title=_("purchase order is late") if count == 1 else _("purchase orders are late"),
        detail=_("Submitted orders past their required date that are not fully received"),
        ask=_("Which purchase orders are late from suppliers?"),
        action=_("Draft chasers"),
        source=_("Purchase Order"),
    )


def _pending_material_requests(user: str, company: str | None) -> SignalResult | None:
    count = count_visible(
        "Material Request", _company_scoped({"docstatus": 1, "status": "Pending"}, company), user
    )
    return SignalResult(
        count=count,
        title=_("material request still pending") if count == 1 else _("material requests still pending"),
        detail=_("Submitted requests that nobody has ordered or issued yet"),
        ask=_("Show material requests that are still pending"),
        action=_("Review them"),
        source=_("Material Request"),
    )


def _leave_to_approve(user: str, company: str | None) -> SignalResult | None:
    # Not company-scoped: the queue is the approver's own work, whatever their default company.
    filters = {"docstatus": 0, "status": "Open", "leave_approver": user}
    count = count_visible("Leave Application", filters, user)
    soon = (
        count_visible(
            "Leave Application",
            {**filters, "from_date": ["between", [today(), add_days(today(), LEAVE_START_WINDOW_DAYS)]]},
            user,
        )
        if count
        else 0
    )
    days = LEAVE_START_WINDOW_DAYS
    if soon == 0:
        detail = _("None of them start in the next {0} days").format(days)
    elif soon == 1:
        detail = _("{0} starts in the next {1} days").format(soon, days)
    else:
        detail = _("{0} start in the next {1} days").format(soon, days)
    return SignalResult(
        count=count,
        title=(
            _("leave application waiting for your approval")
            if count == 1
            else _("leave applications waiting for your approval")
        ),
        detail=detail,
        ask=_("Show leave applications waiting for my approval"),
        action=_("Review them"),
        source=_("Leave Application"),
    )


def _expense_claims_to_approve(user: str, company: str | None) -> SignalResult | None:
    # Not company-scoped: the queue is the approver's own work, whatever their default company.
    count = count_visible(
        "Expense Claim",
        {"docstatus": 0, "approval_status": "Draft", "expense_approver": user},
        user,
    )
    return SignalResult(
        count=count,
        title=(
            _("expense claim waiting for your approval")
            if count == 1
            else _("expense claims waiting for your approval")
        ),
        detail=_("Claims from your team that are waiting for your decision"),
        ask=_("Show expense claims waiting for my approval"),
        action=_("Review them"),
        source=_("Expense Claim"),
    )


CATALOGUE: list[Signal] = [
    Signal(
        id="approvals",
        lenses=(),
        tone="warning",
        requires_doctypes=(),
        requires_apps=(),
        compute=_approvals_waiting,
    ),
    Signal(
        id="todos",
        lenses=(),
        tone="neutral",
        requires_doctypes=("ToDo",),
        requires_apps=(),
        compute=_todos_due,
    ),
    Signal(
        id="overdue_receivables",
        lenses=("accounts",),
        tone="danger",
        requires_doctypes=("Sales Invoice",),
        requires_apps=(),
        compute=_overdue_receivables,
    ),
    Signal(
        id="payables_due",
        lenses=("accounts",),
        tone="warning",
        requires_doctypes=("Purchase Invoice",),
        requires_apps=(),
        compute=_payables_due,
    ),
    Signal(
        id="unreconciled_bank",
        lenses=("accounts",),
        tone="neutral",
        requires_doctypes=("Bank Transaction",),
        requires_apps=(),
        compute=_unreconciled_bank,
    ),
    Signal(
        id="quotations_expiring",
        lenses=("sales",),
        tone="warning",
        requires_doctypes=("Quotation",),
        requires_apps=(),
        compute=_quotations_expiring,
    ),
    Signal(
        id="late_sales_orders",
        lenses=("sales",),
        tone="danger",
        requires_doctypes=("Sales Order",),
        requires_apps=(),
        compute=_late_sales_orders,
    ),
    Signal(
        id="stale_leads",
        lenses=("sales",),
        tone="neutral",
        requires_doctypes=(),
        requires_apps=(),
        compute=_stale_leads,
    ),
    Signal(
        id="below_reorder",
        lenses=("stock",),
        tone="danger",
        requires_doctypes=("Item", "Warehouse"),
        requires_apps=(),
        compute=_below_reorder,
    ),
    Signal(
        id="late_purchase_orders",
        lenses=("stock",),
        tone="warning",
        requires_doctypes=("Purchase Order",),
        requires_apps=(),
        compute=_late_purchase_orders,
    ),
    Signal(
        id="pending_material_requests",
        lenses=("stock",),
        tone="neutral",
        requires_doctypes=("Material Request",),
        requires_apps=(),
        compute=_pending_material_requests,
    ),
    Signal(
        id="leave_to_approve",
        lenses=("hr",),
        tone="warning",
        requires_doctypes=("Leave Application",),
        requires_apps=("hrms",),
        compute=_leave_to_approve,
    ),
    Signal(
        id="expense_claims_to_approve",
        lenses=("hr",),
        tone="neutral",
        requires_doctypes=("Expense Claim",),
        requires_apps=("hrms",),
        compute=_expense_claims_to_approve,
    ),
]
