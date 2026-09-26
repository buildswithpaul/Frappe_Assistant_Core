# Frappe Assistant Core - Billing API package
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""
Billing, Subscription, Credits & Payment APIs.

Submodule layout (kept as a package so each topical surface has its
own file, since the original flat module exceeded 1,800 lines):

- ``sync``         — sync_subscription_status + scheduled sync + AR
                     heartbeat + notification cache
- ``dashboard``    — read-only billing dashboard + plan list +
                     gateway list
- ``seats``        — per-user seat add / remove / preview / verify
- ``invoices``     — GST invoice PDF download streaming
- ``pricing``      — tax-inclusive pricing preview + promo code
                     validation
- ``checkout``     — plan upgrade / downgrade checkout, mandate
                     reauth, post-checkout payment verification
                     (Stripe + Razorpay), credit-payment verify
- ``subscription`` — cancel / reactivate / downgrade lifecycle +
                     invoices / usage history / payment-method
                     endpoints
- ``quota``        — quota status (the one user-facing endpoint;
                     the rest are admin-only)
- ``credits``      — prepaid credit balance + purchase checkout
- ``combined``     — single-call billing-page hydrator + tenant
                     billing-identity get/save

Every public function is re-exported here so the dotted whitelist
path
``frappe_assistant_core.chat.api.billing.<func>``
keeps resolving — that path is referenced literally by the SPA, by
tests, and by ``can_use_faco`` in ``api.settings.access``.

Re-export aggregator: F401 is globally ignored in this app's ruff
config, so no per-line noqa is necessary.

Test-stable surface: the package also re-exports the internal
``_fetch_live_quota`` and ``_refresh_subscription_cache`` helpers so
existing ``mock.patch("...api.billing._fetch_live_quota", ...)``
calls in the test suite keep targeting the same name. ``quota.py``
resolves ``_fetch_live_quota`` through the package namespace at
call time so those patches actually take effect on the call site.
"""

from frappe_assistant_core.chat.api.billing._internal import (
    _fetch_live_quota,
    _refresh_subscription_cache,
)
from frappe_assistant_core.chat.api.billing.checkout import (
    initiate_plan_upgrade,
    reauthorize_mandate,
    verify_payment,
    verify_razorpay_credit_payment,
    verify_razorpay_payment,
)
from frappe_assistant_core.chat.api.billing.combined import (
    get_billing_details,
    get_billing_page_data,
    save_billing_details,
)
from frappe_assistant_core.chat.api.billing.credits import (
    get_consumption_breakdown,
    get_credit_balance,
    get_expiring_credits,
    purchase_credits,
)
from frappe_assistant_core.chat.api.billing.dashboard import (
    get_available_gateways,
    get_billing_dashboard,
    get_plan_options,
)
from frappe_assistant_core.chat.api.billing.hosted import (
    create_hosted_checkout,
    verify_checkout_return,
)
from frappe_assistant_core.chat.api.billing.invoices import (
    download_invoice_pdf,
)
from frappe_assistant_core.chat.api.billing.pricing import (
    preview_plan_pricing,
    validate_promo_code,
)
from frappe_assistant_core.chat.api.billing.quota import (
    get_quota_status,
)
from frappe_assistant_core.chat.api.billing.seats import (
    add_user_seat,
    preview_seat_charge,
    remove_user_seat,
    verify_seat_payment,
)
from frappe_assistant_core.chat.api.billing.subscription import (
    cancel_scheduled_change,
    cancel_subscription,
    downgrade_to_free,
    get_billing_history,
    get_invoices,
    get_payment_instrument,
    get_payment_methods,
    get_subscription_status,
    get_usage_history,
    reactivate_subscription,
    update_payment_method,
)
from frappe_assistant_core.chat.api.billing.sync import (
    scheduled_sync_subscription,
    sync_subscription_status,
)
