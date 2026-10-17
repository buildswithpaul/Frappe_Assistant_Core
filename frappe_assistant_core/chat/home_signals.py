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
from frappe.utils import get_datetime, now_datetime, today

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
    frappe.log_error(title=f"Home signal failed: {signal_id}")


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
    rows = frappe.get_list(
        doctype, filters=filters, fields=[{"COUNT": "name", "as": "n"}], order_by="", user=user
    )
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


def _approvals_waiting(user: str, company: str | None) -> SignalResult | None:
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
        detail=_("Mostly {0}; the oldest has waited {1} days.").format(_(top_doctype), days),
        ask=_("Show the documents waiting for my approval"),
        source=_("Workflow · {0}").format(_(top_doctype)),
    )


def _todos_due(user: str, company: str | None) -> SignalResult | None:
    count = count_visible("ToDo", {"allocated_to": user, "status": "Open", "date": ["<=", today()]}, user)
    return SignalResult(
        count=count,
        title=_("task due") if count == 1 else _("tasks due"),
        detail=_("Open ToDos due today or overdue"),
        ask=_("Show my open ToDos that are due today or overdue"),
        source=_("ToDo"),
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
]
