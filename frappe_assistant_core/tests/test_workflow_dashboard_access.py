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

"""
run_workflow and list_user_dashboards must show a user only what Desk shows them (review of PR #412).

run_workflow loaded the record with no read check and, when the action was not open, returned its
workflow state. list_user_dashboards read Dashboard and DocShare through frappe.get_all, which
skips the user's permissions and the Dashboard permission query, took any `user` for the shares,
and matched DocShare.share_name against the user, so no shared dashboard was ever found.
"""

import json

import frappe
from frappe.share import add as share

from frappe_assistant_core.plugins.core.tools.run_workflow import RunWorkflow
from frappe_assistant_core.plugins.visualization.tools.list_user_dashboards import ListUserDashboards
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.tests.test_document_action_real_workflow import (
    APPROVE,
    DOCTYPE,
    RealWorkflowTestCase,
)


class TestRunWorkflowReadCheck(RealWorkflowTestCase):
    def test_a_record_the_user_cannot_read_gives_away_no_workflow_state(self):
        self.make_workflow()
        doc = self.make_transaction()
        outsider = self.make_desk_user("fac-wf-outsider")

        # nosemgrep: frappe-setuser — runs as a real user; tearDown restores Administrator
        frappe.set_user(outsider)
        self.assertFalse(frappe.has_permission(DOCTYPE, "read", doc=doc.name))
        result = RunWorkflow().execute({"doctype": DOCTYPE, "name": doc.name, "action": APPROVE})

        self.assertFalse(result.get("success"), result)
        self.assertEqual(result.get("error_type"), "permission_error", result)
        self.assertNotIn(self.states["Draft"], json.dumps(result, default=str))
        self.assertNotIn("available_actions", result)


class TestListUserDashboardsAccess(BaseAssistantTest):
    def tearDown(self):
        # nosemgrep: frappe-setuser — tests run in an isolated transaction
        frappe.set_user("Administrator")
        super().tearDown()

    def make_dashboard(self, module=None):
        dashboard = frappe.get_doc(
            {
                "doctype": "Dashboard",
                "dashboard_name": f"FAC Test {frappe.generate_hash(length=6)}",
                "module": module,
            }
        )
        dashboard.flags.ignore_mandatory = True
        return dashboard.insert(ignore_permissions=True)

    def list_as(self, viewer, **arguments):
        # nosemgrep: frappe-setuser — tests run in an isolated transaction
        frappe.set_user(viewer)
        return ListUserDashboards().execute(arguments)

    def test_a_dashboard_shared_with_the_user_is_listed(self):
        dashboard = self.make_dashboard()
        viewer = self.make_desk_user("fac-dash-viewer")
        share(
            "Dashboard", dashboard.name, user=viewer, read=1, notify=0, flags={"ignore_share_permission": 1}
        )

        result = self.list_as(viewer)

        self.assertTrue(result.get("success"), result)
        shared = [d for d in result["dashboards"] if d["access_type"] == "shared"]
        self.assertEqual([d["name"] for d in shared], [dashboard.name], result)

    def test_another_users_shares_are_refused(self):
        viewer = self.make_desk_user("fac-dash-viewer")
        other = self.make_desk_user("fac-dash-other")

        result = self.list_as(viewer, user=other)

        self.assertFalse(result.get("success"), result)
        self.assertEqual(result.get("error_type"), "permission_error", result)

    def test_a_dashboard_the_permission_query_hides_is_not_listed(self):
        # Frappe lists a module's dashboards only to a user who may open that module.
        hidden = self.make_dashboard(module="Website")
        viewer = self.make_desk_user("fac-dash-viewer")
        user = frappe.get_doc("User", viewer)
        user.append("block_modules", {"module": "Website"})
        user.save(ignore_permissions=True)

        result = self.list_as(viewer, user="Administrator", include_shared=False)

        self.assertNotIn(hidden.name, [d["name"] for d in result.get("dashboards") or []], result)
