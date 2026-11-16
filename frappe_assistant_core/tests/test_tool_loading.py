# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""The per-user "Load tools as needed" preference reads on unless the user switched it off (#34608)."""

from unittest.mock import patch

import frappe

from frappe_assistant_core.chat import tool_loading
from frappe_assistant_core.chat.api.tool_loading import get_tool_loading, set_tool_loading
from frappe_assistant_core.tests.base_test import BaseAssistantTest


def _has_column() -> bool:
    return frappe.db.has_column(tool_loading.PREFERENCES_DOCTYPE, tool_loading.TOOL_LOADING_FIELD)


class TestToolLoadingDefault(BaseAssistantTest):
    """Reads that must hold whether or not the column has been migrated onto the site."""

    def test_user_without_a_row_is_dynamic(self):
        self.assertTrue(tool_loading.load_tools_as_needed("nobody-has-a-row@example.com"))
        self.assertEqual(tool_loading.tool_loading_mode("nobody-has-a-row@example.com"), "dynamic")

    def test_unmigrated_site_is_dynamic(self):
        # Between deploying the code and running migrate the column does not exist yet.
        with patch.object(frappe.db, "has_column", return_value=False):
            self.assertTrue(tool_loading.load_tools_as_needed("a@example.com"))

    def test_existing_row_with_unset_value_is_dynamic(self):
        # A row created before the field existed reads NULL until migrate backfills the default.
        with patch.object(frappe.db, "has_column", return_value=True), patch.object(
            frappe.db, "get_value", return_value=None
        ):
            self.assertTrue(tool_loading.load_tools_as_needed("a@example.com"))

    def test_only_an_explicit_zero_means_all(self):
        for stored, expected in ((0, "all"), ("0", "all"), (1, "dynamic"), ("1", "dynamic")):
            with patch.object(frappe.db, "has_column", return_value=True), patch.object(
                frappe.db, "get_value", return_value=stored
            ):
                self.assertEqual(tool_loading.tool_loading_mode("a@example.com"), expected, stored)


class TestToolLoadingEndpoint(BaseAssistantTest):
    """The real column round trip; needs the migrated column, so only a migrated site (CI) runs it."""

    def setUp(self):
        super().setUp()
        if not _has_column():
            self.skipTest("load_tools_as_needed is not migrated onto this site")

    def test_set_then_get_round_trips(self):
        self.assertTrue(get_tool_loading()["load_tools_as_needed"])
        self.assertFalse(set_tool_loading(load_as_needed="0")["load_tools_as_needed"])
        self.assertFalse(get_tool_loading()["load_tools_as_needed"])
        self.assertEqual(tool_loading.tool_loading_mode(frappe.session.user), "all")
        self.assertTrue(set_tool_loading(load_as_needed="1")["load_tools_as_needed"])
