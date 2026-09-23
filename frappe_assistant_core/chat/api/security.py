"""FACO security endpoints — origin callback responder for AR's challenge.

AR calls this URL with (tenant_id, nonce). We compute and return
HMAC(tenant_secret, "tenant_id:nonce"). AR uses the returned digest to confirm
that whoever holds the registered domain also holds the tenant_secret — i.e.
that this FACO install really is the one AR registered.
"""

from __future__ import annotations

import hashlib
import hmac
import re

import frappe

NONCE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


@frappe.whitelist(allow_guest=True, methods=["GET"])  # nosemgrep: guest-whitelisted-method
def verify_origin_challenge(tenant_id: str, nonce: str) -> dict:
    """Return HMAC-SHA256(tenant_secret, "tenant_id:nonce").

    No rate limit (called by AR only at most every 24h per tenant). No auth
    beyond tenant_id+nonce match — the value of the response is meaningless
    to anyone who doesn't already know the secret.
    """
    if not isinstance(tenant_id, str) or not tenant_id:
        return {"error": "unknown tenant"}
    if not isinstance(nonce, str) or not NONCE_PATTERN.match(nonce):
        return {"error": "invalid nonce"}

    settings = frappe.get_single("FAC Chat Settings")
    if (settings.tenant_id or "") != tenant_id:
        return {"error": "unknown tenant"}

    from frappe_assistant_core.chat.tenant_credentials import read_tenant_secret

    secret = read_tenant_secret(raise_exception=False)
    if not secret:
        return {"error": "no secret configured"}

    sig = hmac.new(
        secret.encode(),
        f"{tenant_id}:{nonce}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return {"hmac": sig}
