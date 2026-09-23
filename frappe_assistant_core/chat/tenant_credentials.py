# Copyright (C) 2026 Paul Clinton
# AGPL-3.0 License

"""Safe read/write helpers for FAC Chat Settings.tenant_secret (Password field).

Frappe Password values live in ``__Auth``. The Singles row only holds a dummy
``*****`` mask. Two footguns caused first-connect decrypt failures:

1. ``Document.save()`` with an empty Singles value calls
   ``remove_encrypted_password`` and wipes a valid ``__Auth`` row.
2. ``db_set`` / ``set_single_value`` on a Password field bypasses encryption
   entirely and leave Singles out of sync with ``__Auth``.

All registration / client paths must go through these helpers.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils.password import (
    get_decrypted_password,
    remove_encrypted_password,
    set_encrypted_password,
)

SETTINGS_DOCTYPE = "FAC Chat Settings"
SETTINGS_NAME = "FAC Chat Settings"
SECRET_FIELD = "tenant_secret"
MIN_SECRET_LEN = 32
MAX_SECRET_LEN = 256


def ensure_encryption_key() -> str:
    """Ensure ``encryption_key`` exists before any Password write.

    Frappe mints and persists a key on first encrypt via ``get_encryption_key``.
    Calling it explicitly before registration avoids a first-write race where
    ciphertext is stored under a key that is not yet durable in site_config.
    """
    from frappe.utils.password import get_encryption_key

    return get_encryption_key()


def store_tenant_secret(secret: str) -> None:
    """Encrypt ``secret`` into ``__Auth`` and keep the Singles mask in sync."""
    if not isinstance(secret, str) or not (MIN_SECRET_LEN <= len(secret) <= MAX_SECRET_LEN):
        frappe.throw(
            _("Tenant secret must be a string between {0} and {1} characters").format(
                MIN_SECRET_LEN, MAX_SECRET_LEN
            ),
            frappe.ValidationError,
        )

    ensure_encryption_key()
    set_encrypted_password(SETTINGS_DOCTYPE, SETTINGS_NAME, secret, SECRET_FIELD)
    # Dummy mask so a later Document.save() does not treat the field as cleared.
    frappe.db.set_single_value(
        SETTINGS_DOCTYPE,
        SECRET_FIELD,
        "*" * len(secret),
        update_modified=False,
    )
    frappe.clear_document_cache(SETTINGS_DOCTYPE, SETTINGS_NAME)

    got = get_decrypted_password(SETTINGS_DOCTYPE, SETTINGS_NAME, SECRET_FIELD, raise_exception=False)
    if got != secret:
        remove_encrypted_password(SETTINGS_DOCTYPE, SETTINGS_NAME, SECRET_FIELD)
        frappe.db.set_single_value(SETTINGS_DOCTYPE, SECRET_FIELD, "", update_modified=False)
        frappe.clear_document_cache(SETTINGS_DOCTYPE, SETTINGS_NAME)
        frappe.throw(
            _(
                "Failed to store tenant credentials securely. "
                "Please try again, or contact support if this persists."
            ),
            frappe.ValidationError,
        )


def clear_tenant_secret() -> None:
    """Remove the encrypted secret and clear the Singles mask."""
    remove_encrypted_password(SETTINGS_DOCTYPE, SETTINGS_NAME, SECRET_FIELD)
    frappe.db.set_single_value(SETTINGS_DOCTYPE, SECRET_FIELD, "", update_modified=False)
    frappe.clear_document_cache(SETTINGS_DOCTYPE, SETTINGS_NAME)


def read_tenant_secret(*, raise_exception: bool = True) -> str | None:
    """Decrypt the stored tenant secret, or None / throw if missing."""
    return get_decrypted_password(
        SETTINGS_DOCTYPE,
        SETTINGS_NAME,
        SECRET_FIELD,
        raise_exception=raise_exception,
    )


def preserve_tenant_secret_on_save(doc) -> None:
    """DocType hook: don't wipe ``__Auth`` when Singles mask is blank.

    Call from ``FACChatSettings.before_save``. If the caller intentionally
    clears the secret, set ``doc.flags.clear_tenant_secret = True`` first
    (or call :func:`clear_tenant_secret` and leave the field empty).
    """
    if getattr(doc.flags, "clear_tenant_secret", False):
        return

    current = doc.get(SECRET_FIELD)
    if current and not doc.is_dummy_password(current):
        # Real plaintext assignment — Document._save_passwords will encrypt it.
        ensure_encryption_key()
        return

    if current and doc.is_dummy_password(current):
        return

    existing = get_decrypted_password(SETTINGS_DOCTYPE, SETTINGS_NAME, SECRET_FIELD, raise_exception=False)
    if existing:
        doc.set(SECRET_FIELD, "*" * len(existing))
