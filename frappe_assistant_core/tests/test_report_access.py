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

"""Report access and origin rules shared by the report tools and report search."""

import unittest

import frappe

from frappe_assistant_core.plugins.core.tools.report_access import can_run_report, report_origin
from frappe_assistant_core.plugins.core.tools.report_requirements import ReportRequirements
from frappe_assistant_core.plugins.core.tools.report_tools import ReportTools
from frappe_assistant_core.tests.base_test import BaseAssistantTest

# Production reaches these reports the same way: a Query Report row, optionally
# with Has Role rows, read through Frappe's own report access rule.
DENIED_REF_DOCTYPE = "Language"  # System Manager has no "report" permission on it
ALLOWED_REF_DOCTYPE = "Role"  # System Manager has "report" permission on it


class TestReportAccess(BaseAssistantTest):
    def _make_report(self, ref_doctype: str, roles: tuple = (), **overrides) -> str:
        name = f"FAC Access {frappe.generate_hash(length=8)}"
        doc = frappe.get_doc(
            {
                "doctype": "Report",
                "report_name": name,
                "ref_doctype": ref_doctype,
                "report_type": "Query Report",
                "query": "select 1 as `n`",
                "is_standard": "No",
                "module": "Core",
                "roles": [{"role": role} for role in roles],
                **overrides,
            }
        )
        doc.insert(ignore_permissions=True)
        return doc.name

    def _as_system_manager(self) -> None:
        user = self.make_throwaway_user("report-access", roles=("System Manager",))
        # nosemgrep: frappe-setuser — test acts as a non-Administrator inside the test transaction
        frappe.set_user(user)

    def test_report_restricted_by_role_is_hidden(self):
        name = self._make_report(ALLOWED_REF_DOCTYPE, roles=("Accounts Manager",))
        self._as_system_manager()

        self.assertFalse(can_run_report(name))
        listed = [r.name for r in ReportTools.list_reports()["reports"]]
        self.assertNotIn(name, listed)

    def test_report_without_ref_doctype_permission_is_hidden(self):
        name = self._make_report(DENIED_REF_DOCTYPE)
        self._as_system_manager()

        self.assertFalse(can_run_report(name))
        listed = [r.name for r in ReportTools.list_reports()["reports"]]
        self.assertNotIn(name, listed)

    def test_report_user_can_run_is_listed(self):
        name = self._make_report(ALLOWED_REF_DOCTYPE, roles=("System Manager",))
        self._as_system_manager()

        self.assertTrue(can_run_report(name))
        listed = [r.name for r in ReportTools.list_reports()["reports"]]
        self.assertIn(name, listed)

    def test_disabled_report_is_hidden(self):
        name = self._make_report(ALLOWED_REF_DOCTYPE, disabled=1)
        self._as_system_manager()

        self.assertFalse(can_run_report(name))
        listed = [r.name for r in ReportTools.list_reports()["reports"]]
        self.assertNotIn(name, listed)

    def test_listing_refused_reports_queues_no_messages(self):
        self._make_report(ALLOWED_REF_DOCTYPE, roles=("Accounts Manager",))
        self._make_report(DENIED_REF_DOCTYPE)
        self._make_report(ALLOWED_REF_DOCTYPE, disabled=1)
        self._as_system_manager()
        before = len(frappe.local.message_log)

        ReportTools.list_reports()

        self.assertEqual(len(frappe.local.message_log), before)

    def test_generate_report_refuses_a_hidden_report_without_a_popup(self):
        # Desk User can read every Report row, so the role check is what hides this one.
        name = self._make_report(ALLOWED_REF_DOCTYPE, roles=("Accounts Manager",))
        self._as_system_manager()
        before = len(frappe.local.message_log)

        result = ReportTools.execute_report(name)

        self.assertFalse(result["success"])
        self.assertIn("No permission", result["error"])
        self.assertEqual(len(frappe.local.message_log), before)

    def test_report_requirements_refuses_a_hidden_report(self):
        name = self._make_report(ALLOWED_REF_DOCTYPE, roles=("Accounts Manager",))
        self._as_system_manager()
        before = len(frappe.local.message_log)

        result = ReportRequirements().execute({"report_name": name})

        self.assertFalse(result["success"])
        self.assertEqual(len(frappe.local.message_log), before)

    def test_ui_built_report_is_custom(self):
        self.assertEqual(report_origin("Any", "Accounts", "No"), "custom")

    def test_report_from_a_non_standard_app_is_custom(self):
        # "Assistant Core" is FAC's own module, owned by app frappe_assistant_core.
        self.assertEqual(report_origin("Any", "Assistant Core", "Yes"), "custom")

    def test_frappe_report_is_standard(self):
        self.assertEqual(report_origin("Permitted Documents For User", "Core", "Yes"), "standard")

    @unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "ERPNext not installed")
    def test_erpnext_report_is_standard(self):
        self.assertEqual(report_origin("Accounts Receivable", "Accounts", "Yes"), "standard")
