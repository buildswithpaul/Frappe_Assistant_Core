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

"""Whether a customisation write changes anything anyone but its builder can feel yet."""

from unittest.mock import patch

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.customisation import SYSTEM_ROLES, _stored_doctype, customisation_impact

STORED_DOCTYPE = "frappe_assistant_core.utils.customisation._stored_doctype"
STORED_RECORD = "frappe_assistant_core.utils.customisation._stored_record"
DB_COUNT = "frappe.database.database.Database.count"
IS_CUSTOM = "frappe_assistant_core.utils.customisation._is_custom"
DORMANT_FACTS = {"custom": 1, "roles": ["System Manager"], "custom_roles": [], "records": 0, "in_use": False}


def _impact(tool: str, doctype: str, data: dict | None = None, name: str | None = None) -> dict:
    tool_input = {"doctype": doctype, "data": data or {}}
    if name:
        tool_input["name"] = name
    return customisation_impact(tool, tool_input)


class TestCustomisationImpact(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Production reaches these rows when a user saves a Server Script switched off or on. A
        # direct insert is enough: the server-script guard is a tool-level check, not a doc hook.
        # Rolled back with the class-level transaction.
        cls.off_script = cls._insert_script("FAC Impact Off Script", disabled=1)
        cls.on_script = cls._insert_script("FAC Impact On Script", disabled=0)
        # Production reaches these when a builder saves a FAC Page as a draft or publishes it.
        cls.draft_page = cls._insert_page("fac-impact-draft", published=0)
        cls.live_page = cls._insert_page("fac-impact-live", published=1)

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

    @staticmethod
    def _insert_page(slug: str, published: int) -> str:
        doc = frappe.get_doc(
            {
                "doctype": "FAC Page",
                "title": slug,
                "slug": slug,
                "visibility": "Shared",
                "published": published,
                "html": "<p>x</p>",
            }
        )
        doc.insert(ignore_permissions=True)
        return doc.name

    def test_unpublished_fac_page_create_and_update_are_dormant(self):
        shared = {"slug": "team-planner", "visibility": "Shared"}
        self.assertTrue(_impact("create_document", "FAC Page", shared)["dormant"])
        self.assertTrue(_impact("create_document", "FAC Page", {**shared, "published": 0})["dormant"])
        self.assertTrue(
            _impact("update_document", "FAC Page", {"html": "<p>y</p>"}, self.draft_page)["dormant"]
        )

    def test_publishing_a_fac_page_is_live(self):
        self.assertFalse(
            _impact(
                "create_document",
                "FAC Page",
                {"slug": "team-planner", "visibility": "Shared", "published": 1},
            )["dormant"]
        )
        self.assertFalse(_impact("update_document", "FAC Page", {"published": 1}, self.draft_page)["dormant"])
        publish_with_edit = {"published": 1, "html": "<p>y</p>"}
        self.assertFalse(
            _impact("update_document", "FAC Page", publish_with_edit, self.draft_page)["dormant"]
        )
        self.assertFalse(
            _impact("update_document", "FAC Page", {"html": "<p>y</p>"}, self.live_page)["dormant"]
        )

    def test_delete_of_an_unpublished_fac_page_is_dormant(self):
        self.assertTrue(_impact("delete_document", "FAC Page", name=self.draft_page)["dormant"])
        self.assertFalse(_impact("delete_document", "FAC Page", name=self.live_page)["dormant"])

    def _personal_page(self, published: int = 0) -> tuple[str, str]:
        """A personal page and its owner, built by that owner as FACO's create_document does."""
        owner = self.make_throwaway_user("fac-impact-owner", roles=("Report Manager",))
        # nosemgrep: frappe-setuser — the owner builds the page inside the test transaction
        frappe.set_user(owner)
        doc = frappe.get_doc({"doctype": "FAC Page", "title": "Mine", "slug": "mine", "html": "<p>x</p>"})
        doc.insert()
        if published:
            # Production: a System Manager may tick Published on it; it still opens only for its owner.
            frappe.db.set_value("FAC Page", doc.name, "published", 1)
        return doc.name, owner

    def test_the_owner_changing_their_personal_page_is_dormant(self):
        name, _owner = self._personal_page(published=1)

        result = _impact("update_document", "FAC Page", {"html": "<p>y</p>"}, name)

        self.assertTrue(result["dormant"])
        self.assertEqual(result["reason"], "only you can open this page")
        self.assertTrue(
            _impact("create_document", "FAC Page", {"slug": "mine-too", "published": 1})["dormant"]
        )

    def test_a_system_manager_changing_someone_elses_personal_page_is_live(self):
        name, _owner = self._personal_page()
        sysman = self.make_throwaway_user("fac-impact-sysman", roles=("System Manager",))
        # nosemgrep: frappe-setuser — a System Manager edits the page inside the test transaction
        frappe.set_user(sysman)

        # Unpublished, yet the owner sees the change: a personal page opens for them unpublished.
        self.assertFalse(_impact("update_document", "FAC Page", {"html": "<p>y</p>"}, name)["dormant"])

    def test_a_non_system_manager_creating_a_shared_page_is_live(self):
        # Frappe refuses this write; the card must not call it dormant either.
        user = self.make_throwaway_user("fac-impact-builder", roles=("Report Manager",))
        # nosemgrep: frappe-setuser — a Desk user asks for the write inside the test transaction
        frappe.set_user(user)

        self.assertFalse(
            _impact("create_document", "FAC Page", {"slug": "x", "visibility": "Shared"})["dormant"]
        )

    def test_switching_a_personal_page_to_shared_is_live(self):
        name, _owner = self._personal_page()

        self.assertFalse(_impact("update_document", "FAC Page", {"visibility": "Shared"}, name)["dormant"])

    def test_server_script_created_switched_off_is_dormant(self):
        r = _impact("create_document", "Server Script", {"name": "x", "disabled": 1})
        self.assertTrue(r["dormant"])

    def test_server_script_created_on_is_live(self):
        self.assertFalse(_impact("create_document", "Server Script", {"disabled": 0})["dormant"])
        self.assertFalse(_impact("create_document", "Server Script")["dormant"])

    def test_update_without_flag_reads_stored_script(self):
        off = _impact("update_document", "Server Script", {"script": "pass"}, self.off_script)
        on = _impact("update_document", "Server Script", {"script": "pass"}, self.on_script)
        self.assertTrue(off["dormant"])
        self.assertFalse(on["dormant"])

    def test_switching_a_stored_off_script_on_is_live(self):
        r = _impact("update_document", "Server Script", {"disabled": "0"}, self.off_script)
        self.assertFalse(r["dormant"])

    def test_flag_values_are_read_with_cint(self):
        for value, dormant in (("1", True), (True, True), ("0", False), (False, False)):
            r = _impact("create_document", "Server Script", {"disabled": value})
            self.assertEqual(r["dormant"], dormant, value)

    def test_delete_of_stored_off_script_is_dormant(self):
        self.assertTrue(_impact("delete_document", "Server Script", name=self.off_script)["dormant"])
        self.assertFalse(_impact("delete_document", "Server Script", name=self.on_script)["dormant"])

    def test_client_script_and_notification_use_enabled(self):
        for doctype in ("Client Script", "Notification"):
            self.assertTrue(_impact("create_document", doctype, {"enabled": 0})["dormant"], doctype)
            self.assertFalse(_impact("create_document", doctype, {"enabled": 1})["dormant"], doctype)

    def test_new_doctype_visible_only_to_system_manager_is_dormant(self):
        data = {"custom": 1, "permissions": [{"role": "System Manager"}, {"role": "Administrator"}]}
        self.assertTrue(_impact("create_document", "DocType", data)["dormant"])

    def test_new_doctype_granting_another_role_is_live(self):
        data = {"custom": 1, "permissions": [{"role": "System Manager"}, {"role": "Employee"}]}
        self.assertFalse(_impact("create_document", "DocType", data)["dormant"])

    def test_new_doctype_that_is_not_custom_is_live(self):
        data = {"permissions": [{"role": "System Manager"}]}
        self.assertFalse(_impact("create_document", "DocType", data)["dormant"])

    def test_stored_standard_doctype_is_live(self):
        # ToDo is a standard DocType, which is how a stored DocType is read in production
        self.assertFalse(_impact("update_document", "DocType", {"description": "x"}, "ToDo")["dormant"])

    def test_stored_dormant_doctype_update_follows_permissions_after_the_write(self):
        # "ToDo" is only a name that exists; the patch stands in for a custom DocType saved with
        # only System Manager. Creating one runs DDL, which commits and escapes the test
        # rollback, and this site has none to borrow.
        with patch(STORED_DOCTYPE, autospec=True, return_value=dict(DORMANT_FACTS)):
            quiet = _impact("update_document", "DocType", {"description": "x"}, "ToDo")
            opened = _impact("update_document", "DocType", {"permissions": [{"role": "Employee"}]}, "ToDo")
        self.assertTrue(quiet["dormant"])
        self.assertFalse(opened["dormant"])

    def test_doctype_with_records_is_live(self):
        # Production reaches this once someone saves a record of the custom DocType
        facts = dict(DORMANT_FACTS, records=3)
        with patch(STORED_DOCTYPE, autospec=True, return_value=facts):
            r = _impact("update_document", "DocType", {"description": "x"}, "ToDo")
        self.assertFalse(r["dormant"])

    def test_custom_field_on_dormant_doctype_is_dormant_and_on_sales_invoice_is_live(self):
        # The target DocType is stored in production; patch stands in for a dormant custom one
        with patch(STORED_DOCTYPE, autospec=True, return_value=dict(DORMANT_FACTS)):
            dormant = _impact("create_document", "Custom Field", {"dt": "Probe", "fieldname": "x"})
        live = _impact("create_document", "Custom Field", {"dt": "Sales Invoice", "fieldname": "x"})
        self.assertTrue(dormant["dormant"])
        self.assertFalse(live["dormant"])

    def test_property_setter_follows_its_target_doctype(self):
        with patch(STORED_DOCTYPE, autospec=True, return_value=dict(DORMANT_FACTS)):
            dormant = _impact("create_document", "Property Setter", {"doc_type": "Probe"})
        live = _impact("create_document", "Property Setter", {"doc_type": "ToDo"})
        self.assertTrue(dormant["dormant"])
        self.assertFalse(live["dormant"])

    def test_custom_docperm_granting_a_new_role_is_live(self):
        with patch(STORED_DOCTYPE, autospec=True, return_value=dict(DORMANT_FACTS)):
            system = _impact(
                "create_document", "Custom DocPerm", {"parent": "Probe", "role": "System Manager"}
            )
            other = _impact("create_document", "Custom DocPerm", {"parent": "Probe", "role": "Employee"})
        self.assertTrue(system["dormant"])
        self.assertFalse(other["dormant"])

    def test_missing_record_and_other_doctypes_and_bad_input_are_not_dormant(self):
        self.assertFalse(
            _impact("update_document", "Server Script", {"disabled": 1}, "No Such Script")["dormant"]
        )
        self.assertFalse(_impact("delete_document", "Server Script", name="No Such Script")["dormant"])
        for doctype in ("Role", "Workflow", "Report", "Print Format"):
            self.assertFalse(_impact("create_document", doctype, {"enabled": 0, "disabled": 1})["dormant"])
        self.assertFalse(customisation_impact("create_document", "Server Script")["dormant"])
        self.assertFalse(_impact("get_document", "Server Script", {"disabled": 1})["dormant"])
        self.assertFalse(_impact("create_document", "ToDo", {"disabled": 1})["dormant"])

    def test_a_name_that_is_not_a_plain_string_is_not_dormant(self):
        # A dict reaches get_value as a filter, so it would judge another record's state. Tool
        # input is model-written JSON, so production can receive this shape.
        for bad in ({"disabled": 1}, ["x"], 5, ""):
            result = _impact("update_document", "Server Script", {"disabled": 1}, bad)
            self.assertFalse(result["dormant"], bad)
            self.assertNotIn("disabled", result["reason"])

    def test_a_target_doctype_that_is_not_a_plain_string_is_not_dormant(self):
        # The stored-facts patch would call any value dormant, so only the plain-name check can
        # make these live. Data comes from model-written JSON.
        with patch(STORED_DOCTYPE, autospec=True, return_value=dict(DORMANT_FACTS)):
            for doctype, field in (
                ("Custom Field", "dt"),
                ("Property Setter", "doc_type"),
                ("Custom DocPerm", "parent"),
            ):
                data = {field: {"custom": 1}, "role": "System Manager"}
                result = _impact("create_document", doctype, data)
                self.assertFalse(result["dormant"], doctype)

    def test_reason_never_echoes_stored_values(self):
        data = {"custom": 1, "permissions": [{"role": "Secret Role"}]}
        reason = _impact("create_document", "DocType", data)["reason"]
        self.assertNotIn("Secret Role", reason)

    def test_system_roles(self):
        self.assertEqual(SYSTEM_ROLES, frozenset({"System Manager", "Administrator"}))

    # Fix round 1

    def test_create_without_the_flag_uses_the_schema_default(self):
        # A Notification saved without `enabled` is on (schema default 1); a Client Script is off
        self.assertFalse(_impact("create_document", "Notification")["dormant"])
        self.assertTrue(_impact("create_document", "Client Script")["dormant"])
        self.assertFalse(_impact("create_document", "Server Script")["dormant"])

    def test_create_with_the_flag_sent_as_none_uses_the_schema_default(self):
        # Frappe fills a None field with its schema default on insert, so this saves as enabled
        self.assertFalse(_impact("create_document", "Notification", {"enabled": None})["dormant"])
        self.assertTrue(_impact("create_document", "Client Script", {"enabled": None})["dormant"])

    def test_single_doctype_is_never_dormant_and_is_not_counted(self):
        # Production reaches a custom Single when a builder saves one; System Settings stands in
        # (no custom Single on this site) with only the custom check forced on.
        with patch(IS_CUSTOM, autospec=True, return_value=1):
            with patch(DB_COUNT, autospec=True) as count:
                r = _impact("update_document", "DocType", {"description": "x"}, "System Settings")
        self.assertFalse(r["dormant"])
        count.assert_not_called()

    def test_real_role_and_record_reads_run_for_a_custom_doctype(self):
        # ToDo stands in for a custom DocType (none on this site; creating one commits DDL)
        with patch(IS_CUSTOM, autospec=True, return_value=1):
            facts = _stored_doctype("ToDo")
            r = _impact("update_document", "DocType", {"description": "x"}, "ToDo")
        expected = frappe.get_all("DocPerm", filters={"parent": "ToDo"}, pluck="role")
        self.assertTrue(set(expected) <= set(facts["roles"]))
        self.assertIsInstance(facts["records"], int)
        self.assertFalse(r["dormant"])

    def test_data_cannot_make_a_stored_standard_doctype_custom(self):
        data = {"custom": 1, "permissions": [{"role": "System Manager"}]}
        self.assertFalse(_impact("update_document", "DocType", data, "ToDo")["dormant"])

    def test_moving_a_stored_custom_field_to_a_dormant_target_is_live(self):
        # Production holds a Custom Field row on a live DocType; inserting one runs DDL, which
        # commits and escapes the test rollback, so the stored row is patched in.
        stored = {"dt": "ToDo", "fieldname": "fac_impact_probe"}
        with patch(STORED_RECORD, autospec=True, return_value=stored):
            with patch(STORED_DOCTYPE, autospec=True, side_effect=self._dormant_only("Dormant Target")):
                r = _impact("update_document", "Custom Field", {"dt": "Dormant Target"}, "ToDo-probe")
        self.assertFalse(r["dormant"])

    def test_widening_a_stored_custom_docperm_role_is_live(self):
        # Production holds a Custom DocPerm row granting Employee; the row is patched in because
        # saving one rebuilds the DocType's permission cache.
        stored = {"parent": "ToDo", "role": "Employee"}
        with patch(STORED_RECORD, autospec=True, return_value=stored):
            with patch(STORED_DOCTYPE, autospec=True, side_effect=self._dormant_only("ToDo")):
                r = _impact("update_document", "Custom DocPerm", {"role": "System Manager"}, "perm-probe")
        self.assertFalse(r["dormant"])

    def test_supplied_permissions_do_not_hide_stored_custom_docperm_roles(self):
        # Custom DocPerm rows override DocPerm, so a stored Employee grant still counts
        facts = dict(DORMANT_FACTS, custom_roles=["Employee"])
        with patch(STORED_DOCTYPE, autospec=True, return_value=facts):
            r = _impact("update_document", "DocType", {"permissions": [{"role": "System Manager"}]}, "ToDo")
        self.assertFalse(r["dormant"])

    # Final review: a DocType other forms use

    def test_update_of_a_stored_custom_child_table_is_live(self):
        # User Workspaces stands in for a custom child table: production holds one with no
        # DocPerm rows (Frappe skips them for child tables) and no rows until a parent form saves.
        # Only the custom check and the record count are forced; istable is read for real.
        with patch(IS_CUSTOM, autospec=True, return_value=1), patch(DB_COUNT, autospec=True, return_value=0):
            r = _impact("update_document", "DocType", {"description": "x"}, "User Workspaces")
        self.assertFalse(r["dormant"])

    def test_delete_of_a_doctype_a_table_field_embeds_is_live(self):
        # Has Role is embedded by Table fields on User and others, as a custom child table is once
        # a builder adds it to a live form; deleting it would cascade to those forms.
        with patch(IS_CUSTOM, autospec=True, return_value=1), patch(DB_COUNT, autospec=True, return_value=0):
            r = _impact("delete_document", "DocType", name="Has Role")
        self.assertFalse(r["dormant"])

    def test_custom_field_on_a_doctype_other_forms_link_to_is_live(self):
        # Role Profile stands in for a custom DocType with only System Manager rows and no records
        # that a Link field on another form (User) already points at.
        with patch(IS_CUSTOM, autospec=True, return_value=1), patch(DB_COUNT, autospec=True, return_value=0):
            r = _impact("create_document", "Custom Field", {"dt": "Role Profile", "fieldname": "x"})
        self.assertFalse(r["dormant"])

    def test_real_reference_lookup_runs_for_a_linked_doctype(self):
        # Module Profile: standard, System Manager only, linked from User. Only the custom check
        # and the record count are forced; the reference lookup runs against the real schema.
        with patch(IS_CUSTOM, autospec=True, return_value=1), patch(DB_COUNT, autospec=True, return_value=0):
            facts = _stored_doctype("Module Profile")
            r = _impact("update_document", "DocType", {"description": "x"}, "Module Profile")
        self.assertTrue(facts["in_use"])
        self.assertFalse(r["dormant"])

    def test_a_property_setter_pointing_a_field_at_the_doctype_makes_it_live(self):
        # Console Log stands in for a custom DocType with only System Manager rows that no field
        # names. Production reaches the reference when Customize Form repoints a field's options
        # on another form; db_insert writes that Property Setter row without its cache hooks and
        # it rolls back with the test.
        with patch(IS_CUSTOM, autospec=True, return_value=1), patch(DB_COUNT, autospec=True, return_value=0):
            before = _impact("update_document", "DocType", {"description": "x"}, "Console Log")
            frappe.get_doc(
                {
                    "doctype": "Property Setter",
                    "name": "ToDo-description-options-fac-probe",
                    "doc_type": "ToDo",
                    "doctype_or_field": "DocField",
                    "field_name": "description",
                    "property": "options",
                    "property_type": "Text",
                    "value": "Console Log",
                }
            ).db_insert()
            after = _impact("update_document", "DocType", {"description": "x"}, "Console Log")
        self.assertTrue(before["dormant"])
        self.assertFalse(after["dormant"])

    @staticmethod
    def _dormant_only(*names):
        return lambda name: (
            dict(DORMANT_FACTS)
            if name in names
            else {"custom": 0, "roles": [], "custom_roles": [], "records": 0, "in_use": False}
        )


class TestCustomisationImpactTool(BaseAssistantTest):
    @staticmethod
    def _tool():
        from frappe_assistant_core.plugins.faco.tools.customisation_impact import CustomisationImpact

        return CustomisationImpact()

    def test_returns_rule_result(self):
        result = self._tool().execute(
            {
                "tool_name": "create_document",
                "tool_input": {"doctype": "Server Script", "data": {"disabled": 1}},
            }
        )
        self.assertTrue(result["success"])
        self.assertTrue(result["dormant"])
        self.assertTrue(result["reason"])

    def test_live_write_is_not_dormant(self):
        result = self._tool().execute({"tool_name": "send_email", "tool_input": {}})
        self.assertTrue(result["success"])
        self.assertFalse(result["dormant"])

    def test_rejects_missing_arguments(self):
        result = self._tool().execute({"tool_name": "create_document"})
        self.assertFalse(result["success"])
        self.assertTrue(result["error"])

    def test_rejects_non_object_tool_input(self):
        result = self._tool().execute({"tool_name": "create_document", "tool_input": "x"})
        self.assertFalse(result["success"])

    def test_is_read_only_and_fac_cloud_only(self):
        from frappe_assistant_core.plugins.faco.plugin import FacoPlugin
        from frappe_assistant_core.utils.tool_category_detector import detect_tool_category

        # No write to the database happens here, so approval-wise it is a read; AR calls it from
        # its approval hook, and gating the check itself behind an approval would loop.
        self.assertEqual(detect_tool_category(self._tool()), "read_only")
        plugin = FacoPlugin()
        self.assertTrue(plugin.is_fac_cloud_only())
        self.assertIn("customisation_impact", plugin.get_tools())
