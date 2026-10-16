# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Schema changes for test fixtures, which Frappe refuses inside a test transaction."""

from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.database.database import Database


@contextmanager
def committing_ddl():
    """Run schema changes that commit for real, and commit nothing else.

    Frappe refuses DDL inside a test transaction, and BaseAssistantTest turns commit() into a no-op.
    Pending writes are rolled back first, so the only rows that reach the database are the ones the
    block itself writes. Database.commit is the real commit that the subclass attribute shadows.
    """
    frappe.db.rollback()
    try:
        with patch.object(Database, "check_implicit_commit"):
            yield
    finally:
        Database.commit(frappe.db)
