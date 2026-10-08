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
Regression tests for: https://github.com/buildswithpaul/Frappe_Assistant_Core/issues/291

create_document and update_document decided which fields were child tables with
`fieldtype == "Table"`. Frappe has two child-table fieldtypes — `Table` and
`Table MultiSelect` (`frappe.model.table_fields`) — so every Table MultiSelect
value was assigned raw with setattr, and the insert died on `.is_new()`. That
blocked any doctype with a required Table MultiSelect (LMS Course.instructors in
the report; User Group.user_group_members here), and FAC's own FAC Skill and
Prompt Template, whose `shared_with_roles` is one too.

Around that, three neighbouring defects in the same code:

  * create_document screened restricted fields only at the top level of `data`,
    so a child row could carry `owner` or `creation`. Frappe keeps a row's own
    owner/creation (`if not d.owner: d.owner = self.owner`), so an Assistant
    User could forge a row's audit trail. update_document already screened rows.
  * A child doctype has no permissions of its own; Frappe checks it through a
    parent. Without one, a non-admin is refused with a misleading "Insufficient
    create permissions", and Administrator — whom Frappe allows before it ever
    looks at the child-table rule — inserts the row straight into any parent,
    skipping the parent's validation.
  * get_doctype_info refused a child doctype's schema outright, for the same
    reason, even to users who can read its parent.

Fixtures are core Frappe doctypes present on v15 and v16, so the suite does not
depend on LMS: User Group (required Table MultiSelect -> User Group Member.user)
and Event (plain Table -> Event Participants). Event rather than Note because a
Desk User can create an Event and all its tables sit at permlevel 0; Note's
`seen_by` is permlevel 1, so Frappe strips it from a Desk User's insert and a
screening test on it would pass whether or not FAC screened anything.
"""

import frappe

from frappe_assistant_core.plugins.core.tools.create_document import DocumentCreate
from frappe_assistant_core.plugins.core.tools.get_doctype_info import GetDoctypeInfo
from frappe_assistant_core.plugins.core.tools.update_document import DocumentUpdate
from frappe_assistant_core.tests.base_test import BaseAssistantTest


def group_name():
    return f"FAC 291 {frappe.generate_hash(length=8)}"


def members(group):
    return [row.user for row in frappe.get_doc("User Group", group).user_group_members]


def event(**extra):
    """The minimum an Event needs, plus whatever the test is about."""
    return {"subject": "FAC 291", "event_type": "Private", "starts_on": "2026-10-09 10:00:00", **extra}


def participant(user, **extra):
    return {"reference_doctype": "User", "reference_docname": user, **extra}


def make_group(*users):
    """A User Group built the way Desk builds one, to update in place."""
    name = group_name()
    frappe.get_doc(
        {
            "doctype": "User Group",
            "name": name,
            "user_group_members": [{"user": u} for u in users],
        }
    ).insert()
    return name


class TestCreateTableMultiSelect(BaseAssistantTest):
    """create_document builds Table MultiSelect rows as child documents."""

    def test_rows_as_dicts(self):
        name = group_name()
        result = DocumentCreate().execute(
            {
                "doctype": "User Group",
                "data": {"name": name, "user_group_members": [{"user": "Administrator"}]},
            }
        )

        self.assertTrue(result.get("success"), result)
        self.assertEqual(members(name), ["Administrator"])

    def test_rows_as_strings_map_to_the_link_field(self):
        """Desk sends a Table MultiSelect as its link values; so may the model."""
        name = group_name()
        result = DocumentCreate().execute(
            {
                "doctype": "User Group",
                "data": {"name": name, "user_group_members": ["Administrator", "Guest"]},
            }
        )

        self.assertTrue(result.get("success"), result)
        self.assertEqual(members(name), ["Administrator", "Guest"])

    def test_a_row_that_is_neither_string_nor_dict_is_a_structured_error(self):
        result = DocumentCreate().execute(
            {
                "doctype": "User Group",
                "data": {"name": group_name(), "user_group_members": [42]},
            }
        )

        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("error_type"), "child_table_handling_error")
        self.assertEqual(result.get("field"), "user_group_members")

    def test_a_plain_table_still_requires_dict_rows(self):
        """Only a Table MultiSelect names one link field a bare string can fill."""
        result = DocumentCreate().execute(
            {"doctype": "Event", "data": event(event_participants=["Administrator"])}
        )

        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("error_type"), "child_table_handling_error")
        self.assertEqual(result.get("field"), "event_participants")

    def test_the_callers_rows_are_not_mutated(self):
        """doc.append writes doctype/parent/idx into the dict it is given."""
        rows = [{"user": "Administrator"}]
        DocumentCreate().execute(
            {"doctype": "User Group", "data": {"name": group_name(), "user_group_members": rows}}
        )

        self.assertEqual(rows, [{"user": "Administrator"}])


class TestUpdateTableMultiSelect(BaseAssistantTest):
    """update_document's replace and patch modes cover Table MultiSelect."""

    def test_replace_mode_with_strings(self):
        name = make_group("Administrator")

        result = DocumentUpdate().execute(
            {"doctype": "User Group", "name": name, "data": {"user_group_members": ["Guest"]}}
        )

        self.assertTrue(result.get("success"), result)
        self.assertEqual(members(name), ["Guest"])

    def test_patch_mode_keeps_named_rows_and_appends_new_ones(self):
        name = make_group("Administrator")
        existing = frappe.get_doc("User Group", name).user_group_members[0].name

        result = DocumentUpdate().execute(
            {
                "doctype": "User Group",
                "name": name,
                "data": {"user_group_members": [{"name": existing}, "Guest"]},
            }
        )

        self.assertTrue(result.get("success"), result)
        self.assertEqual(members(name), ["Administrator", "Guest"])


class TestCreateScreensChildRows(BaseAssistantTest):
    """A child row is held to the same restricted-field rules as the parent."""

    def test_assistant_user_cannot_forge_a_rows_owner(self):
        # Desk User (automatic for any System User) may create an Event; Assistant
        # User is the role whose ADMIN_ONLY_FIELDS include owner and creation.
        # Before the fix this row was saved with owner=Administrator and a 2001
        # creation date: Frappe keeps a new row's own owner/creation.
        user = self.make_throwaway_user("fac291-assistant", roles=("Assistant User",))
        frappe.set_user(user)
        try:
            result = DocumentCreate().execute(
                {
                    "doctype": "Event",
                    "data": event(
                        subject="FAC 291 forged row",
                        event_participants=[
                            participant(user, owner="Administrator", creation="2001-01-01 00:00:00")
                        ],
                    ),
                }
            )
        finally:
            frappe.set_user("Administrator")

        self.assertFalse(result.get("success"), result)
        self.assertIn("owner", result.get("error", ""))
        self.assertIn("creation", result.get("error", ""))
        self.assertFalse(frappe.db.exists("Event", {"subject": "FAC 291 forged row"}))

    def test_sensitive_field_in_a_row_is_rejected_for_every_role(self):
        result = DocumentCreate().execute(
            {
                "doctype": "Event",
                "data": event(event_participants=[participant("Administrator", api_key="x")]),
            }
        )

        self.assertFalse(result.get("success"), result)
        self.assertIn("api_key", result.get("error", ""))


class TestChildDoctypeAccess(BaseAssistantTest):
    """A child doctype is reached through its parent, never on its own."""

    def test_administrator_cannot_inject_a_row_into_a_parent(self):
        name = make_group("Administrator")

        result = DocumentCreate().execute(
            {
                "doctype": "User Group Member",
                "data": {
                    "user": "Guest",
                    "parent": name,
                    "parenttype": "User Group",
                    "parentfield": "user_group_members",
                },
            }
        )

        self.assertFalse(result.get("success"), result)
        self.assertEqual(result.get("error_type"), "child_table_doctype")
        self.assertEqual(members(name), ["Administrator"])

    def test_non_admin_is_told_which_parent_to_use(self):
        user = self.make_throwaway_user("fac291-sysmgr", roles=("System Manager",))
        frappe.set_user(user)
        try:
            result = DocumentCreate().execute({"doctype": "User Group Member", "data": {"user": "Guest"}})
        finally:
            frappe.set_user("Administrator")

        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("error_type"), "child_table_doctype")
        self.assertIn(
            {"doctype": "User Group", "fieldname": "user_group_members"},
            result.get("parent_doctypes", []),
        )

    def test_doctype_info_on_a_child_follows_parent_read(self):
        user = self.make_throwaway_user("fac291-sysmgr", roles=("System Manager",))
        frappe.set_user(user)
        try:
            result = GetDoctypeInfo().execute({"doctype": "User Group Member"})
        finally:
            frappe.set_user("Administrator")

        self.assertTrue(result.get("success"), result)
        self.assertTrue(result["is_child_table"])
        self.assertIn(
            {"doctype": "User Group", "fieldname": "user_group_members"},
            result.get("parent_doctypes", []),
        )

    def test_doctype_info_on_a_child_is_refused_without_parent_read(self):
        # A Website User has no read on User Group, the only parent.
        user = self.make_throwaway_user("fac291-website")
        frappe.set_user(user)
        try:
            result = GetDoctypeInfo().execute({"doctype": "User Group Member"})
        finally:
            frappe.set_user("Administrator")

        self.assertFalse(result.get("success"))

    def test_doctype_info_names_the_multiselect_link_field(self):
        """The model needs to know which field a bare string fills."""
        result = GetDoctypeInfo().execute({"doctype": "User Group"})

        entry = next(t for t in result["child_tables"] if t["fieldname"] == "user_group_members")
        self.assertEqual(entry["fieldtype"], "Table MultiSelect")
        self.assertEqual(entry["link_field"], "user")

    def test_direct_row_update_names_the_parent_only_to_who_can_read_it(self):
        # update_document's own child-doctype guard runs before any permission check;
        # it used to name the parent document of any row, to anyone who had the row's name.
        name = make_group("Administrator")
        row = frappe.get_doc("User Group", name).user_group_members[0].name
        args = {"doctype": "User Group Member", "name": row, "data": {"user": "Guest"}}

        user = self.make_throwaway_user("fac291-website")
        frappe.set_user(user)
        try:
            outsider = DocumentUpdate().execute(args)
        finally:
            frappe.set_user("Administrator")
        insider = DocumentUpdate().execute(args)

        self.assertEqual(outsider.get("error_type"), "child_doctype_direct_update")
        self.assertNotIn("parent_name", outsider)
        self.assertNotIn(name, str(outsider))

        self.assertEqual(insider.get("error_type"), "child_doctype_direct_update")
        self.assertEqual(insider.get("parent_name"), name)
        self.assertEqual(members(name), ["Administrator"])
