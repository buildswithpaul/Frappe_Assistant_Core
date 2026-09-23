# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Tests for the wildcard doc_events dispatcher's guard ordering.

The dispatcher fires on every doc save site-wide (``doc_events = {"*": ...}``),
including the DocType saves Frappe performs during ``bench migrate``. It must
check the migrate/install/patch flags BEFORE reading the FAC Chat gate —
otherwise, when upgrading from a build that predates ``enable_fac_chat``, the
gate read raises mid-migration and crashes every doc save.
"""

from contextlib import contextmanager
from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.workflows.triggers import dispatcher
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class _FakeDoc:
    """Minimal stand-in for a Frappe doc — the dispatcher only reads .doctype."""

    def __init__(self, doctype="ToDo"):
        self.doctype = doctype


@contextmanager
def _flag(name, value):
    """Set a frappe.flags entry for the duration of the block, then restore.

    frappe.flags is a _dict whose keys may be absent by default, so we restore
    the prior value (or remove the key) rather than assume it existed.
    """
    sentinel = object()
    prev = frappe.flags.get(name, sentinel)
    frappe.flags[name] = value
    try:
        yield
    finally:
        if prev is sentinel:
            frappe.flags.pop(name, None)
        else:
            frappe.flags[name] = prev


class TestDispatcherMigrateGuard(BaseAssistantTest):
    def test_skips_during_migrate_without_reading_gate(self):
        # If the gate is reached during migrate it would raise on a half-applied
        # schema. Patch it to blow up so the test fails loudly if the ordering
        # regresses — the migrate guard must short-circuit first.
        def _boom():
            raise AssertionError("gate must not be read during migrate")

        with _flag("in_migrate", True), patch.object(dispatcher, "is_chat_enabled", side_effect=_boom):
            # Should return cleanly — no exception, no gate read.
            dispatcher._dispatch_inner(_FakeDoc(), "on_update")

    def test_skips_during_install_without_reading_gate(self):
        def _boom():
            raise AssertionError("gate must not be read during install")

        with _flag("in_install", True), patch.object(dispatcher, "is_chat_enabled", side_effect=_boom):
            dispatcher._dispatch_inner(_FakeDoc(), "after_insert")

    def test_reads_gate_when_not_a_schema_operation(self):
        # Outside migrate/install/patch the gate IS consulted; chat off → return.
        called = {"gate": False}

        def _gate_off():
            called["gate"] = True
            return False

        with _flag("in_migrate", False), _flag("in_install", False), _flag("in_patch", False), _flag(
            "in_import", False
        ), patch.object(dispatcher, "is_chat_enabled", side_effect=_gate_off):
            dispatcher._dispatch_inner(_FakeDoc(), "on_update")

        self.assertTrue(called["gate"], "gate must be consulted outside schema ops")
