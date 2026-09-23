# Copyright (c) 2026, Clinton Paul and contributors
# For license information, please see license.txt
"""
Security headers for the Frappe Assistant Copilot SPA.

Applies CSP, X-Frame-Options, and Referrer-Policy to the ``/copilot`` SPA
routes only. Desk (``/app/*``) and API (``/api/method/*``) responses are
NOT touched — those surfaces have their own policies managed by Frappe.

The policy is intentionally conservative:
    - ``frame-ancestors 'self'`` and ``X-Frame-Options: SAMEORIGIN``
      mitigate clickjacking of the HITL approval UI.
    - ``Referrer-Policy: strict-origin-when-cross-origin`` prevents
      leaking query-string secrets (e.g. ``session_id``) to third parties.
    - ``script-src`` still allows ``'unsafe-inline'`` because the SPA
      hydrates via an inline ``<script>`` in ``copilot.html``. A follow-up
      must replace that with a nonce + tightened policy.

Headers are written to ``frappe.local.response_headers`` (a werkzeug
``Headers`` instance) which Frappe's request pipeline merges into the
final response in ``frappe/app.py``. This works transparently for both
cached and freshly-rendered pages.
"""

from __future__ import annotations

import frappe

# Kept as a single-line string so HTTP middleware doesn't choke on newlines.
#
# Google Fonts is allow-listed in style-src / font-src because the SPA's
# theme.css imports Work Sans via @import from fonts.googleapis.com. Any
# follow-up that self-hosts the font file can tighten this back to 'self'.
#
# No gateway is allow-listed here any more. Payments are collected on FAC
# Cloud's own site — a gateway is onboarded against one declared website and
# this app runs on a different customer domain every time — so nothing here
# loads a checkout script or iframes a card form. Leaving the hosts listed
# would keep a door open that nothing walks through.
#
# The redirect out is a top-level navigation, which no directive here
# governs: `form-action` restricts form submissions, not `window.location`,
# and `navigate-to` is not set. Stripe keeps its frame hosts because the
# Customer Portal is still opened directly from billing settings.
_CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://js.stripe.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "img-src 'self' data: blob: https:; "
    "font-src 'self' data: https://fonts.gstatic.com; "
    "connect-src 'self' wss: ws: https:; "
    "frame-src 'self' https://js.stripe.com https://hooks.stripe.com; "
    "frame-ancestors 'self'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

_SPA_HEADERS = {
    "X-Frame-Options": "SAMEORIGIN",
    "Content-Security-Policy": _CSP_POLICY,
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


def apply_spa_headers() -> None:
    """Attach SPA security headers to the current response.

    Safe to call from any ``www/copilot/*.py::get_context``. Idempotent —
    re-calling overwrites with the same values. Silently no-ops when
    ``frappe.local.response_headers`` isn't set (e.g. in non-request
    contexts like unit tests) rather than breaking page rendering.
    """
    headers = getattr(frappe.local, "response_headers", None)
    if headers is None:
        return

    for name, value in _SPA_HEADERS.items():
        # Headers.set() replaces any existing value for the name.
        headers.set(name, value)
