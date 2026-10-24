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

"""check_build_plan: a build plan checked against the site before FAC Cloud shows it."""

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.customisation import check_plan_changes

UNKNOWN_DOCTYPE = "FAC Plan Check Missing Doctype"


def _change(doctype: str, action: str = "create", goes_live: bool = False, **extra) -> dict:
    return {"doctype": doctype, "action": action, "goes_live": goes_live, **extra}


class TestCheckPlanChanges(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Production reaches these rows when a builder saves a Server Script switched on or off.
        # A direct insert is enough: the server-script guard is a tool-level check, not a doc hook.
        # Rolled back with the class-level transaction.
        cls.on_script = cls._insert_script("FAC Plan Check On Script", disabled=0)
        cls.off_script = cls._insert_script("FAC Plan Check Off Script", disabled=1)

    @staticmethod
    def _insert_script(name: str, disabled: int) -> str:
        doc = frappe.get_doc(
            {
                "doctype": "Server Script",
                "name": name,
                "script_type": "API",
                "api_method": name.lower().replace(" ", "_"),
                "script": "pass",
                "disabled": disabled,
            }
        )
        doc.insert(ignore_permissions=True)
        return doc.name

    def test_has_role_points_at_an_update_of_each_user(self):
        [result] = check_plan_changes([_change("Has Role", goes_live=True)])
        self.assertIn("child table", result["problem"])
        self.assertIn("User", result["problem"])

    def test_other_child_table_names_no_user(self):
        [result] = check_plan_changes([_change("DocField", goes_live=True)])
        self.assertIn("child table", result["problem"])
        self.assertNotIn("role assignment", result["problem"])

    def test_unknown_doctype_points_at_a_doctype_create(self):
        [result] = check_plan_changes([_change(UNKNOWN_DOCTYPE, goes_live=True)])
        self.assertIn(UNKNOWN_DOCTYPE, result["problem"])
        self.assertIn('"DocType"', result["problem"])

    def test_unknown_doctype_created_in_the_same_plan_is_fine(self):
        results = check_plan_changes(
            [
                _change(UNKNOWN_DOCTYPE, goes_live=True),
                _change("DocType", name=UNKNOWN_DOCTYPE),
            ]
        )
        self.assertEqual([r["problem"] for r in results], [None, None])

    def test_a_doctype_named_in_an_update_does_not_count_as_created(self):
        results = check_plan_changes(
            [_change(UNKNOWN_DOCTYPE), _change("DocType", action="update", name=UNKNOWN_DOCTYPE)]
        )
        self.assertIsNotNone(results[0]["problem"])

    def test_role_and_doctype_creates_can_never_be_dormant(self):
        results = check_plan_changes([_change("Role"), _change("DocType", name=UNKNOWN_DOCTYPE)])
        self.assertEqual([r["goes_live"] for r in results], [True, True])

    def test_server_script_create_marked_dormant_stays_dormant(self):
        [result] = check_plan_changes([_change("Server Script")])
        self.assertFalse(result["goes_live"])
        self.assertIsNone(result["problem"])

    def test_update_of_an_enabled_script_goes_live(self):
        [result] = check_plan_changes([_change("Server Script", "update", name=self.on_script)])
        self.assertTrue(result["goes_live"])

    def test_update_and_delete_of_a_disabled_script_stay_dormant(self):
        results = check_plan_changes(
            [
                _change("Server Script", "update", name=self.off_script),
                _change("Server Script", "delete", name=self.off_script),
            ]
        )
        self.assertEqual([r["goes_live"] for r in results], [False, False])

    def test_update_of_a_missing_script_is_unchanged(self):
        [result] = check_plan_changes([_change("Server Script", "update", name="FAC Plan Check Nowhere")])
        self.assertFalse(result["goes_live"])

    def test_goes_live_true_is_never_turned_false(self):
        results = check_plan_changes(
            [
                _change("Server Script", goes_live=True),
                _change("Server Script", "update", goes_live=True, name=self.off_script),
                _change("ToDo", goes_live=True),
            ]
        )
        self.assertEqual([r["goes_live"] for r in results], [True, True, True])

    def test_non_customisation_entries_keep_their_flag(self):
        [result] = check_plan_changes([_change("ToDo")])
        self.assertFalse(result["goes_live"])
        self.assertIsNone(result["problem"])

    def test_one_result_per_change_in_order(self):
        results = check_plan_changes([_change("ToDo"), _change("Has Role"), _change("Role")])
        self.assertEqual([r["index"] for r in results], [0, 1, 2])
        self.assertIsNone(results[0]["problem"])
        self.assertIsNotNone(results[1]["problem"])

    def test_a_doctype_that_is_not_a_plain_name_is_not_looked_up(self):
        [result] = check_plan_changes([_change({"name": "ToDo"})])
        self.assertIsNotNone(result["problem"])
        self.assertFalse(result["goes_live"])


class TestCheckBuildPlanTool(BaseAssistantTest):
    @staticmethod
    def _tool():
        from frappe_assistant_core.plugins.faco.tools.check_build_plan import CheckBuildPlan

        return CheckBuildPlan()

    def test_returns_one_result_per_change(self):
        result = self._tool().execute({"changes": [_change("Role"), _change("Has Role", goes_live=True)]})
        self.assertTrue(result["success"])
        self.assertEqual(
            [(r["index"], r["goes_live"]) for r in result["results"]],
            [(0, True), (1, True)],
        )
        self.assertIsNone(result["results"][0]["problem"])
        self.assertIn("User", result["results"][1]["problem"])

    def test_rejects_changes_that_are_not_a_list_of_objects(self):
        for changes in ("x", None, ["x"]):
            with self.subTest(changes=changes):
                result = self._tool().execute({"changes": changes})
                self.assertFalse(result["success"])
                self.assertTrue(result["error"])

    def test_refuses_a_user_without_system_manager(self):
        user = self.make_throwaway_user("plan-check", roles=("Employee",))
        # Error Log is MyISAM, so the permission-denied row survives the test rollback.
        self.addCleanup(frappe.db.delete, "Error Log", {"owner": user})
        # nosemgrep: frappe-setuser — tests run in an isolated transaction
        self.addCleanup(frappe.set_user, "Administrator")
        # nosemgrep: frappe-setuser — tests run in an isolated transaction
        frappe.set_user(user)

        response = self._tool()._safe_execute({"changes": [_change("Role")]})

        self.assertFalse(response["success"])
        self.assertEqual(response["error_type"], "PermissionError")

    def test_is_read_only_and_fac_cloud_only(self):
        from frappe_assistant_core.plugins.faco.plugin import FacoPlugin
        from frappe_assistant_core.utils.tool_category_detector import detect_tool_category

        # It never writes, and AR calls it before showing a plan card, so gating it behind an
        # approval would ask for approval of the approval.
        self.assertEqual(detect_tool_category(self._tool()), "read_only")
        plugin = FacoPlugin()
        self.assertTrue(plugin.is_fac_cloud_only())
        self.assertIn("check_build_plan", plugin.get_tools())
