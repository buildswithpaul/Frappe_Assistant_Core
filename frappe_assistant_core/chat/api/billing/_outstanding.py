# Frappe Assistant Core - Outstanding Balance Resolver
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""One answer to "does this tenant owe money", for every surface that asks.

The figure used to be reachable only through ``get_payment_instrument``, which
the SPA calls when the Payment Method tab mounts. So the billing hero, the
sidebar, the invoice list and the Users page could not show it without a second
round-trip and a second opinion about what "owing" means — and the one signal
they *could* already see, ``payment_status == "past_due"``, disagrees with it: a
stalled renewal freezes the cycle without necessarily marking the subscription
past due, which is exactly the state the notice needs to explain.

Both payloads that hydrate a surface call this, so the four cannot drift apart.
"""

from __future__ import annotations


def resolve_outstanding(client) -> dict | None:
    """The tenant's unpaid balance, or None when nothing is owed.

    Returns ``{"amount": float, "currency": str | None, "invoice": str | None}``.

    Never raises. Every caller runs this inside a parallel fan-out that
    assembles a whole page, and a billing lookup that fails must cost the
    outstanding notice, not the page around it.

    AR derives ``amount_due`` from ``owed_invoice()`` — the same narrowing that
    ``update_payment_method`` settles through — so the figure shown here is the
    figure the pay button actually charges. Stripe subscriptions are managed in
    the customer portal and AR returns no ``amount_due`` for them, so nothing is
    surfaced for those tenants.
    """
    try:
        result = client.get_payment_instrument() or {}
    except Exception:
        return None

    due = result.get("amount_due") or None
    if not due:
        return None

    try:
        amount = float(due.get("amount") or 0)
    except (TypeError, ValueError):
        return None

    # A zero or negative balance is not an outstanding payment. Returning it
    # anyway would light every surface up over nothing.
    if amount <= 0:
        return None

    return {
        "amount": amount,
        # Passed through rather than defaulted: guessing a currency here would
        # relabel a foreign amount rather than admit we do not know.
        "currency": due.get("currency"),
        "invoice": due.get("invoice"),
    }
