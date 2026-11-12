# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Explain errors in plain language and fix them together (#33991): each dry-run group gets a
plain cause and its fixes; a picked fix becomes a value map or rows left out, a missing record
is created with create_document (documents, with import_session), and the file is checked again.

Customer again, as in the dry run's tests: Customer Group is a Link to a tree whose group
nodes can't be used, and Customer Type is a Select.
"""

import json
import unittest
from unittest.mock import patch

import frappe

from frappe_assistant_core.assistant_core.doctype.fac_import_session.fac_import_session import engine_session
from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils import import_dry_run, import_fixes

MAPPING = {
    "Customer Name": "customer_name",
    "Customer Group": "customer_group",
    "Customer Type": "customer_type",
    "Notes": "Don't Import",
}


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Customer")
class TestImportFixes(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.registry = get_tool_registry()
        self.track_test_files()
        self.tag = frappe.generate_hash(length=6)
        # The ticket's example: the file says "Retail", ERPNext has "Retail Customers".
        self.existing_group = f"Retail Customers {self.tag}"
        self.missing = f"Retail {self.tag}"
        frappe.get_doc(
            {
                "doctype": "Customer Group",
                "customer_group_name": self.existing_group,
                "parent_customer_group": "All Customer Groups",
            }
        ).insert()

    def tearDown(self):
        frappe.set_user("Administrator")
        self.delete_test_files()
        super().tearDown()

    # -- helpers -----------------------------------------------------------------------

    def _run(self, tool_name, arguments):
        return self.registry.get_tool(tool_name)._safe_execute(arguments)

    def _rows(self):
        t = self.tag
        return [
            [f"Alpha {t}", self.existing_group, "Company", "", self._company()],  # row 2: ready
            [f"Beta {t}", self.missing, "Company", ""],  # row 3: missing link
            [f"Gamma {t}", self.missing, "Company", ""],  # row 4: missing link, same group
            [f"Delta {t}", self.existing_group, "Robot", ""],  # row 5: not an allowed option
            # row 6: the same Represents Company as row 2, a field marked unique: a duplicate. (A
            # repeated Customer Name is no duplicate: a naming series names the customers, #34398.)
            [f"Zeta {t}", self.existing_group, "Company", "", self._company()],
        ]

    @staticmethod
    def _company():
        return frappe.get_all("Company", pluck="name", limit=1)[0]

    def _session(self, rows=None):
        """Upload a CSV, open its session, map it and check it, as the earlier steps do."""
        lines = ["Customer Name,Customer Group,Customer Type,Notes,Represents Company"]
        lines += [",".join(row + [""] * (5 - len(row))) for row in rows or self._rows()]
        file_doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": "customers.csv",
                "content": ("\n".join(lines) + "\n").encode(),
                "is_private": 1,
            }
        ).insert()
        session = self._run("start_import_session", {"file_url": file_doc.file_url})["result"]["session_id"]
        mapped = self._run(
            "set_column_mapping",
            {
                "session": session,
                "mapping": {**MAPPING, "Represents Company": "represents_company"},
                "doctype": "Customer",
            },
        )
        self.assertTrue(mapped["success"], mapped)
        checked = self._run("dry_run_import", {"session": session})
        self.assertTrue(checked["success"], checked)
        return session, checked["result"]

    def _run_job(self, session):
        """What the queue runs. The job commits when it is done, as a worker's job must: the
        commit is held here, so a test's rows never stay in the site's database (#34412)."""
        with patch.object(frappe.db.__class__, "commit", autospec=True) as commit:
            import_dry_run.run_job(session, "Administrator")
        commit.assert_called()  # the job did reach its commit: it is the patch that held it

    def _fix(self, session, *fixes):
        response = self._run("dry_run_import", {"session": session, "fixes": list(fixes)})
        self.assertTrue(response["success"], response)
        return response["result"]

    def _fix_fails(self, session, *fixes):
        response = self._run("dry_run_import", {"session": session, "fixes": list(fixes)})
        self.assertFalse(response["success"], response)
        return response["result"]

    @staticmethod
    def _group(result, cause):
        return next(g for g in result["groups"] if g["cause"] == cause)

    def _doc(self, session):
        # The session as the import tools hold it (load_session): the engine's own copy, so a
        # test can set up what an earlier step writes (#34400).
        return engine_session(session)

    def test_fixes_wait_for_a_check_of_the_file_the_session_has_now(self):
        # A corrected file is linked and its check, queued for a large file, fails: the session
        # keeps the last check's groups, of the file before. Their row numbers aren't this file's.
        session, result = self._session()
        group = self._group(result, "Not an allowed option")
        lines = [
            "Customer Name,Customer Group,Customer Type,Notes,Represents Company",
            f"Zeta {self.tag},{self.existing_group},Company,,",
        ]
        corrected = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": "again.csv",
                "content": ("\n".join(lines) + "\n").encode(),
                "is_private": 1,
            }
        ).insert()
        doc = self._doc(session)
        import_dry_run.link_site_file(doc, corrected)  # what dry_run_import does before queueing it

        response = self._fix_fails(session, {"group": group["id"], "action": "leave_out", "reason": "x"})

        self.assertIn("Check it first", response["error"])
        self.assertIsNone(self._doc(session).excluded_rows)

    UNCHECKED = "Your fixes are already applied but weren't checked yet. Check again without fixes."

    def _leave_out_robot(self, result):
        group = self._group(result, "Not an allowed option")
        return {"group": group["id"], "action": "leave_out", "reason": "Not a customer"}

    def test_fixes_whose_check_failed_are_said_to_be_applied_not_the_file_changed(self):
        # #34607: the fixes were saved, then the check failed. Sent again, the call was told the
        # file changed: it hadn't, only the fixes had, and no check had finished since.
        session, result = self._session()
        fix = self._leave_out_robot(result)
        with patch.object(import_fixes, "check", side_effect=ConnectionError("Redis went away")):
            self._fix_fails(session, fix)
        self.assertEqual(json.loads(self._doc(session).excluded_rows), [5])  # the fixes stayed

        response = self._fix_fails(session, fix)

        self.assertEqual(response["error"], self.UNCHECKED)
        # Checked again without fixes, as it says: the check is of the fixes already applied.
        checked = self._run("dry_run_import", {"session": session})
        self.assertTrue(checked["success"], checked)
        self.assertNotIn("Not an allowed option", [g["cause"] for g in checked["result"]["groups"]])
        self.assertTrue(import_fixes.checked_as_is(self._doc(session)))

    def test_fixes_whose_background_check_died_are_said_to_be_applied(self):
        session, result = self._session()
        fix = self._leave_out_robot(result)
        with (
            patch.object(import_dry_run, "check_cost", return_value=import_dry_run.BACKGROUND_ROWS + 1),
            patch.object(import_dry_run, "enqueue"),  # the worker died before it ran the check
        ):
            self.assertEqual(self._fix(session, fix)["state"], "running")

        self.assertEqual(self._fix_fails(session, fix)["error"], self.UNCHECKED)

    def test_a_new_file_after_fixes_whose_check_failed_is_still_a_changed_file(self):
        session, result = self._session()
        fix = self._leave_out_robot(result)
        with patch.object(import_fixes, "check", side_effect=ConnectionError("Redis went away")):
            self._fix_fails(session, fix)
        lines = [
            "Customer Name,Customer Group,Customer Type,Notes,Represents Company",
            f"Eta {self.tag},{self.missing},Robot,,",
        ]
        other = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": "other.csv",
                "content": ("\n".join(lines) + "\n").encode(),
                "is_private": 1,
            }
        ).insert()
        import_dry_run.link_site_file(self._doc(session), other)

        response = self._fix_fails(session, fix)

        self.assertIn("The file changed since its last check", response["error"])

    # -- registration ------------------------------------------------------------------

    def test_fixes_are_an_input_of_the_dry_run_and_raise_no_approval_card(self):
        from frappe_assistant_core.utils.tool_category_detector import detect_tool_category

        tool = self.registry.get_tool("dry_run_import")
        self.assertIn("fixes", tool.inputSchema["properties"])
        self.assertNotIn("fixes", tool.inputSchema["required"])
        self.assertEqual(detect_tool_category(tool), "read_only")

    # -- criterion 1: a plain cause and at least one fix per group ------------------------

    def test_every_group_has_a_plain_explanation_and_a_fix(self):
        _session, result = self._session()

        self.assertEqual(len(result["groups"]), 3)
        for group in result["groups"]:
            self.assertTrue(group["explanation"], group)
            self.assertGreaterEqual(len(group["fixes"]), 1, group)
        link = self._group(result, "Missing link")
        self.assertEqual(
            link["explanation"], f"2 rows: there is no Customer Group called '{self.missing}' in ERPNext."
        )

    # -- criterion 2: a missing link offers map (closest first), create, leave out -------------

    def test_a_missing_link_offers_the_closest_names_create_and_leave_out(self):
        _session, result = self._session()

        fixes = self._group(result, "Missing link")["fixes"]

        self.assertEqual([f["action"] for f in fixes], ["map", "create", "leave_out"])
        self.assertEqual(fixes[0]["closest"][0], self.existing_group)
        self.assertNotIn("All Customer Groups", fixes[0]["closest"])  # a group node fails as a link
        self.assertEqual(
            fixes[1],
            {
                "action": "create",
                "use": "create_document",
                "doctype": "Customer Group",
                "name": self.missing,
                "parent": "All Customer Groups",
            },
        )
        self.assertEqual(fixes[2], {"action": "leave_out", "rows": 2})

    def test_a_group_node_is_never_offered_however_close(self):
        frappe.get_doc(
            {
                "doctype": "Customer Group",
                "customer_group_name": f"{self.missing} Group",
                "parent_customer_group": "All Customer Groups",
                "is_group": 1,
            }
        ).insert()

        closest = import_fixes.closest_names("Customer Group", self.missing)

        self.assertIn(self.existing_group, closest)
        self.assertNotIn(f"{self.missing} Group", closest)

    def test_closest_names_are_ranked_by_the_engine_and_all_exist(self):
        candidates = ["Commercial", "Retail Customers", "Wholesale", "Retail"]

        self.assertEqual(import_fixes.rank("Retail", candidates), ["Retail", "Retail Customers"])
        self.assertEqual(import_fixes.rank("Retial", candidates)[0], "Retail")
        for name in import_fixes.closest_names("Customer Group", self.missing):
            self.assertTrue(frappe.db.exists("Customer Group", name))

    def test_a_misspelt_name_is_marked_likely_and_creating_it_says_so(self):
        # Offered as an equal choice, "create" made a misspelt Customer Group that stayed on the site.
        # Two letters off: one letter off ("Hospitls") isn't offered as a new record at all (F5).
        t = self.tag
        meant = f"Hospitals {t}"
        frappe.get_doc(
            {
                "doctype": "Customer Group",
                "customer_group_name": meant,
                "parent_customer_group": "All Customer Groups",
            }
        ).insert()

        _session, result = self._session([[f"Alpha {t}", f"Hosptls {t}", "Company", ""]])

        group = self._group(result, "Missing link")
        mapping, create = group["fixes"][0], group["fixes"][1]
        self.assertEqual((mapping["closest"][0], mapping["likely"]), (meant, meant))
        self.assertIn(f"'{meant}', misspelt", group["explanation"])
        self.assertEqual(create["action"], "create")
        self.assertIn(f"not a misspelt '{meant}'", create["note"])

    def test_a_name_far_from_the_rest_is_not_marked_likely(self):
        _session, result = self._session([[f"Alpha {self.tag}", f"Zymurgy {self.tag}", "Company", ""]])

        group = self._group(result, "Missing link")
        self.assertNotIn("likely", group["fixes"][0])
        self.assertNotIn("note", group["fixes"][1])

    def test_a_name_that_only_shares_letters_is_not_offered(self):
        # "Kerala" got "Karnataka" as its closest: mapping to it would put customers in another state.
        self.assertEqual(import_fixes.rank("Kerala", ["Karnataka", "Tamil Nadu"]), [])
        self.assertEqual(import_fixes.rank("Hospitls", ["Hospitals", "Hotels"])[0], "Hospitals")
        # and a longer name holding the value is a close match, not a misspelling
        self.assertIsNone(import_fixes.likely("Retail", ["Retail Customers"]))
        self.assertEqual(import_fixes.likely("Hospitls", ["Hospitals", "Hotels"]), "Hospitals")

    def test_a_value_outside_the_options_is_explained_with_the_choices(self):
        _session, result = self._session()

        option = self._group(result, "Not an allowed option")

        self.assertIn("isn't one of the choices for Customer Type", option["explanation"])
        self.assertIn("Company", option["fixes"][0]["closest"])

    # -- criterion 3: a fix becomes a rule or a master, rows re-checked, new count -----------

    def test_mapping_a_value_becomes_a_rule_and_the_rows_are_checked_again(self):
        session, result = self._session()
        link = self._group(result, "Missing link")

        fixed = self._fix(session, {"group": link["id"], "action": "map", "to": self.existing_group})

        self.assertEqual((fixed["ready"], fixed["failed"]), (3, 2))
        self.assertEqual(fixed["previous"], {"failed": 4, "fixed": 2})
        self.assertNotIn("Missing link", [g["cause"] for g in fixed["groups"]])
        self.assertIn(f"'{self.missing}' becomes '{self.existing_group}' in 2 rows", fixed["applied"][0])
        rules = json.loads(self._doc(session).transformation_rules)["value_maps"]
        self.assertEqual(
            [(r["field"], r["from"], r["to"]) for r in rules],
            [("customer_group", self.missing, self.existing_group)],
        )
        self.assertEqual(self._doc(session).steps[-2].step, "Fix Errors")

    def test_a_select_value_can_be_mapped_to_an_allowed_option(self):
        session, result = self._session()
        option = self._group(result, "Not an allowed option")

        fixed = self._fix(session, {"group": option["id"], "action": "map", "to": "Company"})

        self.assertNotIn("Not an allowed option", [g["cause"] for g in fixed["groups"]])

    def test_unknown_groups_territories_and_customer_type_each_get_their_fixes(self):
        # #34395's file (migtest_customers_clean.csv): groups, regions and a customer type ERPNext
        # doesn't have. On Frappe 16 each was hidden behind the same error on every row.
        t = self.tag
        region = f"Bengaluru {t}"
        frappe.get_doc(
            {"doctype": "Territory", "territory_name": region, "parent_territory": "All Territories"}
        ).insert()
        retail, wholesale, karnataka, maharashtra = (
            f"{n} {t}" for n in ("Retail", "Wholesale", "Karnataka", "Maharashtra")
        )
        lines = [
            "Cust Name,Party Group,Region,Customer Type",
            f"Alpha {t},{self.existing_group},{region},Company",  # row 2: ready
            f"Beta {t},{retail},{karnataka},Company",  # row 3
            f"Gamma {t},{wholesale},{region},Company",  # row 4
            f"Delta {t},{self.existing_group},{maharashtra},Pvt Ltd",  # row 5
            f"Eps {t},{self.existing_group},{region},Pvt Ltd",  # row 6
            f"Zeta {t},{self.existing_group},{region},Individual",  # row 7: ready
        ]
        file_doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": "migtest_customers_clean.csv",
                "content": ("\n".join(lines) + "\n").encode(),
                "is_private": 1,
            }
        ).insert()
        session = self._run("start_import_session", {"file_url": file_doc.file_url})["result"]["session_id"]
        mapping = {
            "Cust Name": "customer_name",
            "Party Group": "customer_group",
            "Region": "territory",
            "Customer Type": "customer_type",
        }
        mapped = self._run(
            "set_column_mapping", {"session": session, "mapping": mapping, "doctype": "Customer"}
        )
        self.assertTrue(mapped["success"], mapped)

        result = self._fix(session)

        self.assertNotIn("SimpleNamespace", frappe.as_json(result))
        self.assertEqual((result["ready"], result["failed"]), (2, 4), result["groups"])
        found = {
            (g["cause"], g["field"], g["value"]): (
                [e["row"] for e in g["examples"]],
                [f["action"] for f in g["fixes"]],
            )
            for g in result["groups"]
        }
        link_fixes = ["map", "create", "leave_out"]
        self.assertEqual(
            found,
            {
                ("Missing link", "customer_group", retail): ([3], link_fixes),
                ("Missing link", "customer_group", wholesale): ([4], link_fixes),
                ("Missing link", "territory", karnataka): ([3], link_fixes),
                ("Missing link", "territory", maharashtra): ([5], link_fixes),
                ("Not an allowed option", "customer_type", "Pvt Ltd"): ([5, 6], ["map", "leave_out"]),
            },
        )
        option = self._group(result, "Not an allowed option")
        self.assertIn("Company", option["fixes"][0]["closest"])

        fixed = self._fix(session, {"group": option["id"], "action": "map", "to": "Company"})

        self.assertNotIn("Not an allowed option", [g["cause"] for g in fixed["groups"]])
        # row 6 is ready now; row 5 still has its region
        self.assertEqual((fixed["ready"], fixed["failed"]), (3, 3))

    def test_mapping_to_a_name_that_does_not_exist_is_refused_and_nothing_is_saved(self):
        session, result = self._session()
        link = self._group(result, "Missing link")

        response = self._fix_fails(session, {"group": link["id"], "action": "map", "to": "Made Up Group"})

        self.assertIn("There is no Customer Group called 'Made Up Group'", response["problems"][0]["error"])
        self.assertFalse(self._doc(session).transformation_rules)

    def test_one_wrong_fix_saves_none(self):
        session, result = self._session()
        link = self._group(result, "Missing link")
        option = self._group(result, "Not an allowed option")

        response = self._fix_fails(
            session,
            {"group": link["id"], "action": "map", "to": self.existing_group},
            {"group": option["id"], "action": "map", "to": "Robotic"},
        )

        self.assertEqual([p["group"] for p in response["problems"]], [option["id"]])
        doc = self._doc(session)
        self.assertFalse(doc.transformation_rules)
        self.assertEqual(doc.status, "Dry Run Failed")

    # -- criterion 4: rows left out are excluded and listed ----------------------------------

    def test_rows_left_out_are_skipped_and_listed_with_their_reason(self):
        session, result = self._session()
        link = self._group(result, "Missing link")

        fixed = self._fix(session, {"group": link["id"], "action": "leave_out", "reason": "Old shop"})

        self.assertEqual((fixed["ready"], fixed["failed"], fixed["excluded"]), (1, 2, 2))
        self.assertEqual(fixed["left_out"], [{"reason": "Old shop", "count": 2, "rows": "3-4"}])
        doc = self._doc(session)
        self.assertEqual(json.loads(doc.excluded_rows), [3, 4])  # the dry run's own format
        self.assertEqual(json.loads(doc.transformation_rules)["left_out"], {"3": "Old shop", "4": "Old shop"})

    # -- criterion 5: every group handled, the file is ready with the final count -------------

    def test_once_every_group_is_handled_the_file_is_ready_with_the_final_count(self):
        session, result = self._session()
        link = self._group(result, "Missing link")

        # "Create" is done the way FACO does it: the approved plan, then check again.
        documents = [{"doctype": m["doctype"], "data": m["data"]} for m in result["masters_plan"]]
        created = self._run("create_document", {"documents": documents, "import_session": session})
        self.assertTrue(created["success"], created)
        rechecked = self._run("dry_run_import", {"session": session})["result"]
        self.assertEqual((rechecked["ready"], rechecked["failed"]), (3, 2))
        groups = {g["cause"]: g["id"] for g in rechecked["groups"]}

        fixed = self._fix(
            session,
            {"group": groups["Not an allowed option"], "action": "map", "to": "Company"},
            {"group": groups["Duplicate in the file"], "action": "leave_out", "reason": "Repeated"},
        )

        self.assertEqual((fixed["ready"], fixed["failed"], fixed["excluded"]), (4, 0, 1))
        self.assertEqual(fixed["status"], "Ready to Import")
        self.assertIn("The file is ready: 4 rows will be imported. 1 row left out", fixed["message"])
        self.assertEqual(fixed["left_out"], [{"reason": "Repeated", "count": 1, "rows": "6"}])
        self.assertEqual(fixed["groups"], [])
        doc = self._doc(session)
        self.assertEqual((doc.steps[-1].step, doc.steps[-1].outcome), ("Dry Run", "Success"))

    # -- when a fix can't be applied ---------------------------------------------------------

    def test_a_session_not_checked_yet_is_refused(self):
        session, _result = self._session()
        self._run("set_column_mapping", {"session": session, "mapping": {"Notes": "Don't Import"}})

        response = self._fix_fails(session, {"group": "G1", "action": "leave_out"})

        self.assertIn("Check the file first", response["error"])

    def test_a_group_from_an_older_check_is_refused(self):
        session, _result = self._session()

        response = self._fix_fails(session, {"group": "G99", "action": "leave_out"})

        self.assertIn("no group G99", response["problems"][0]["error"])

    def test_fixes_sent_while_a_background_check_runs_are_refused_not_dropped(self):
        session, result = self._session()
        link = self._group(result, "Missing link")
        with patch.object(import_dry_run, "BACKGROUND_ROWS", 2), patch("frappe.enqueue"):
            self._run("dry_run_import", {"session": session})  # now running in the background

            response = self._fix_fails(session, {"group": link["id"], "action": "leave_out"})

        self.assertIn("still being checked", response["error"])
        self.assertFalse(self._doc(session).excluded_rows)

    def test_a_large_file_saves_the_fixes_and_checks_again_in_the_background(self):
        session, result = self._session()
        link = self._group(result, "Missing link")

        with patch.object(import_dry_run, "BACKGROUND_ROWS", 2), patch("frappe.enqueue") as enqueue:
            started = self._fix(session, {"group": link["id"], "action": "map", "to": self.existing_group})

        self.assertEqual(started["state"], "running")
        self.assertIn(f"'{self.missing}' becomes '{self.existing_group}'", started["applied"][0])
        self.assertEqual(enqueue.call_args.kwargs["session_name"], session)

        self._run_job(session)  # what the queued job runs

        summary = json.loads(self._doc(session).validation_summary)
        self.assertEqual((summary["ready"], summary["failed"]), (3, 2))

    def test_a_background_check_leaves_the_same_explained_reply_for_the_model(self):
        session, result = self._session()

        with patch.object(import_dry_run, "BACKGROUND_ROWS", 2), patch("frappe.enqueue"):
            started = self._run("dry_run_import", {"session": session})["result"]
        self.assertEqual(started["state"], "running")
        self._run_job(session)  # what the queued job runs

        # FACO reads it with get_document: the explanations and fixes are there, as they are
        # in a reply that came back at once.
        summary = json.loads(self._doc(session).validation_summary)
        link = self._group(summary, "Missing link")
        self.assertEqual(
            link["explanation"], f"2 rows: there is no Customer Group called '{self.missing}' in ERPNext."
        )
        self.assertEqual(link["fixes"][0]["closest"][0], self.existing_group)
        self.assertEqual(summary["message"], result["message"])

    def test_a_background_check_with_nothing_failing_says_the_file_is_ready(self):
        session, _result = self._session([[f"Clean {self.tag}", self.existing_group, "Company", ""]])

        with patch.object(import_dry_run, "BACKGROUND_ROWS", 0), patch("frappe.enqueue"):
            self._run("dry_run_import", {"session": session})
        self._run_job(session)

        summary = json.loads(self._doc(session).validation_summary)
        self.assertIn("The file is ready: 1 row will be imported.", summary["message"])

    def test_a_group_keeps_its_id_so_a_fix_from_an_earlier_reply_hits_the_same_rows(self):
        session, first = self._session()
        link = self._group(first, "Missing link")
        option = self._group(first, "Not an allowed option")
        self._fix(session, {"group": link["id"], "action": "map", "to": self.existing_group})

        # The user's next answer, acted on with the id from the first reply.
        self._fix(session, {"group": option["id"], "action": "leave_out", "reason": "Robots"})

        self.assertEqual(json.loads(self._doc(session).excluded_rows), [5])

    def test_the_id_of_a_group_already_fixed_is_refused(self):
        session, first = self._session()
        link = self._group(first, "Missing link")
        self._fix(session, {"group": link["id"], "action": "map", "to": self.existing_group})

        response = self._fix_fails(session, {"group": link["id"], "action": "leave_out"})

        self.assertIn(f"no group {link['id']}", response["problems"][0]["error"])
        self.assertFalse(self._doc(session).excluded_rows)

    def test_a_different_file_puts_the_rows_left_out_back_to_be_checked(self):
        session, result = self._session()
        link = self._group(result, "Missing link")
        self._fix(session, {"group": link["id"], "action": "leave_out", "reason": "Old shop"})
        # The corrected export: same columns, but other rows are at rows 3 and 4 now.
        lines = ["Customer Name,Customer Group,Customer Type,Notes,Represents Company"]
        lines += [",".join(row + [""] * (5 - len(row))) for row in reversed(self._rows())]
        corrected = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": "customers-corrected.csv",
                "content": ("\n".join(lines) + "\n").encode(),
                "is_private": 1,
            }
        ).insert()

        response = self._run("dry_run_import", {"session": session, "file_url": corrected.file_url})

        self.assertTrue(response["success"], response)
        self.assertEqual(response["result"]["excluded"], 0)
        self.assertIn("2 rows left out before are checked again", response["result"]["notice"])
        doc = self._doc(session)
        self.assertFalse(doc.excluded_rows)
        self.assertNotIn("left_out", json.loads(doc.transformation_rules or "{}"))

    def test_the_same_file_linked_again_keeps_the_rows_left_out(self):
        session, result = self._session()
        link = self._group(result, "Missing link")
        self._fix(session, {"group": link["id"], "action": "leave_out", "reason": "Old shop"})
        same = frappe.db.get_value("File", self._doc(session).source_file, "file_url")

        response = self._run("dry_run_import", {"session": session, "file_url": same})

        self.assertTrue(response["success"], response)
        self.assertEqual(response["result"]["excluded"], 2)
        self.assertEqual(json.loads(self._doc(session).excluded_rows), [3, 4])

    def test_fixes_sent_with_the_sessions_own_file_url_are_applied(self):
        session, result = self._session()
        link = self._group(result, "Missing link")
        own = frappe.db.get_value("File", self._doc(session).source_file, "file_url")

        # What FACO sent in a live demo: the fixes, with the file_url the session already has.
        response = self._run(
            "dry_run_import",
            {
                "session": session,
                "file_url": own,
                "fixes": [{"group": link["id"], "action": "map", "to": self.existing_group}],
            },
        )

        self.assertTrue(response["success"], response)
        self.assertNotIn("Missing link", [g["cause"] for g in response["result"]["groups"]])
        self.assertNotIn("Link File", [step.step for step in self._doc(session).steps])  # nothing re-linked

    def test_a_new_file_and_fixes_in_one_call_are_refused(self):
        session, result = self._session()
        link = self._group(result, "Missing link")
        other = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": "customers-other.csv",
                "content": f"Customer Name,Customer Group,Customer Type,Notes\nZeta {self.tag},x,Company,\n".encode(),
                "is_private": 1,
            }
        ).insert()

        response = self._run(
            "dry_run_import",
            {
                "session": session,
                "file_url": other.file_url,
                "fixes": [{"group": link["id"], "action": "leave_out"}],
            },
        )

        self.assertFalse(response["success"], response)
        doc = self._doc(session)
        self.assertFalse(doc.excluded_rows)
        self.assertNotEqual(frappe.db.get_value("File", doc.source_file, "file_url"), other.file_url)

    def test_closest_names_are_empty_for_a_doctype_the_user_cannot_read(self):
        user = self.make_desk_user("noread")
        self.assert_cannot(user, "read", "Customer Group")
        frappe.set_user(user)

        self.assertEqual(import_fixes.closest_names("Customer Group", self.missing), [])

    def test_an_empty_fixes_list_is_a_plain_check(self):
        session, _result = self._session()

        # FAC Cloud fills optional inputs in: a plain check arrives with "fixes": [] and file_url "".
        response = self._run("dry_run_import", {"session": session, "file_url": "", "fixes": []})

        self.assertTrue(response["success"], response)
        self.assertEqual((response["result"]["ready"], response["result"]["failed"]), (1, 4))

    def test_create_is_not_a_fix_it_is_done_with_create_document(self):
        session, result = self._session()
        link = self._group(result, "Missing link")

        response = self._fix_fails(session, {"group": link["id"], "action": "create"})

        self.assertIn("create_document", response["problems"][0]["error"])
        self.assertFalse(frappe.db.exists("Customer Group", self.missing))

    def test_a_duplicate_can_only_be_left_out(self):
        session, result = self._session()
        duplicate = self._group(result, "Duplicate in the file")

        self.assertEqual([f["action"] for f in duplicate["fixes"]], ["leave_out"])
        response = self._fix_fails(session, {"group": duplicate["id"], "action": "map", "to": "x"})
        self.assertIn("Only a missing link", response["problems"][0]["error"])

    def test_a_child_table_value_is_mapped_on_the_child_table_not_the_parent(self):
        # Sales Invoice has project on the invoice and on each item line (items.project).
        company = next(iter(frappe.get_all("Company", pluck="name", limit=1)), None)
        if not company:
            self.skipTest("needs a Company for the Project")
        project = frappe.get_doc(
            {"doctype": "Project", "project_name": f"Site {self.tag}", "company": company}
        ).insert()
        ghost = f"Ghost {self.tag}"
        lines = ["Customer,Project,Item Code,Quantity,Item Project"]
        lines += [
            f"Cust {self.tag},{project.name},Item {self.tag},1,{ghost}",
            f"Cust {self.tag},{project.name},Item {self.tag},1,{ghost}",
        ]
        file_doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": "invoices.csv",
                "content": ("\n".join(lines) + "\n").encode(),
                "is_private": 1,
            }
        ).insert()
        session = self._run("start_import_session", {"file_url": file_doc.file_url})["result"]["session_id"]
        mapping = {
            "Customer": "customer",
            "Project": "project",
            "Item Code": "items.item_code",
            "Quantity": "items.qty",
            "Item Project": "items.project",
        }
        mapped = self._run(
            "set_column_mapping", {"session": session, "mapping": mapping, "doctype": "Sales Invoice"}
        )
        self.assertTrue(mapped["success"], mapped)
        checked = self._run("dry_run_import", {"session": session})["result"]
        item_project = next(g for g in checked["groups"] if g.get("value") == ghost)

        fixed = self._fix(session, {"group": item_project["id"], "action": "map", "to": project.name})

        self.assertNotIn(ghost, [g.get("value") for g in fixed["groups"]])
        rule = json.loads(self._doc(session).transformation_rules)["value_maps"][0]
        self.assertEqual((rule["parent"], rule["field"]), ("Sales Invoice Item", "project"))

    def test_another_users_session_is_refused(self):
        session, result = self._session()
        other = self.make_desk_user("other")
        self.assert_cannot(other, "write", "FAC Import Session", session)
        frappe.set_user(other)

        response = self._run(
            "dry_run_import", {"session": session, "fixes": [{"group": "G1", "action": "leave_out"}]}
        )

        self.assertFalse(response["success"])
        frappe.set_user("Administrator")
        self.assertFalse(self._doc(session).excluded_rows)


class TestGroupNodes(BaseAssistantTest):
    """PR #392, F5: "Karnatka" found no match while the group territory "Karnataka" exists, and FACO
    offered to create "Karnatka". ERPNext takes a group Territory on a Customer: only the trees
    whose group nodes it refuses (a Customer's group, an Account, a Cost Center, a Warehouse) leave
    them out."""

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.tag = frappe.generate_hash(length=5)
        self.state = f"Karnataka{self.tag}"
        frappe.get_doc(
            {
                "doctype": "Territory",
                "territory_name": self.state,
                "parent_territory": "All Territories",
                "is_group": 1,
            }
        ).insert()
        self.group = f"Wholesale{self.tag}"
        frappe.get_doc(
            {
                "doctype": "Customer Group",
                "customer_group_name": self.group,
                "parent_customer_group": "All Customer Groups",
                "is_group": 1,
            }
        ).insert()

    def test_a_group_territory_is_a_close_name(self):
        self.assertIn(self.state, import_fixes.closest_names("Territory", f"Karnatka{self.tag}"))

    def test_a_group_customer_group_is_not(self):
        self.assertNotIn(self.group, import_fixes.closest_names("Customer Group", f"Wholsale{self.tag}"))

    def test_a_tree_s_parent_may_be_a_group(self):
        self.assertIn(
            self.group, import_fixes.closest_names("Customer Group", f"Wholsale{self.tag}", groups=True)
        )

    def test_a_value_one_letter_from_a_record_is_mapped_never_created(self):
        session = frappe._dict(target_doctype="Customer", migration_plan=None, name=None)
        group = {
            "cause": import_dry_run.CAUSE_MISSING_LINK,
            "link_doctype": "Territory",
            "parent": "Customer",
            "field": "territory",
            "label": "Territory",
            "value": f"Karnatka{self.tag}",
            "count": 2,
        }
        with patch.object(import_fixes, "_with_target", lambda session, group: group):
            advice = import_fixes.advise(session, group)

        actions = [fix["action"] for fix in advice["fixes"]]
        self.assertNotIn("create", actions, advice)
        self.assertEqual(advice["fixes"][0]["likely"], self.state)
        self.assertIn(self.state, advice["cannot_create"])

    def test_no_default_territory_doesnt_say_a_group_cant_hold_records(self):
        df = frappe.get_meta("Customer").get_field("territory")
        checker = import_dry_run._Checker.__new__(import_dry_run._Checker)
        checker.party_gaps = [df]

        ((key, info),) = checker._party_gap_problems()

        self.assertNotIn("hold records", info["message"])


class TestRowRanges(BaseAssistantTest):
    def test_short_lists_are_given_in_full(self):
        self.assertEqual(import_fixes.row_ranges([2, 3, 4, 9]), "2-4, 9")

    def test_a_long_list_of_scattered_rows_is_capped(self):
        # 20,000 rows left out every other row would otherwise send ~150 KB in every reply
        rows = list(range(2, 40002, 2))
        text = import_fixes.row_ranges(rows)
        self.assertLess(len(text), 300, text)
        self.assertTrue(text.startswith("2, 4, 6"), text)
        self.assertTrue(text.endswith("and 19980 more rows"), text)


class TestCurrencyWords(BaseAssistantTest):
    def test_a_currency_written_as_a_word_or_symbol_is_offered_first(self):
        # "RS" isn't close to "INR" by spelling, so a file's Rs would be left out instead of mapped.
        if not frappe.db.get_value("Currency", "INR", "enabled"):
            self.skipTest("INR is switched off on this site")
        for written in ("RS", "Rs.", "Rupees", "₹"):
            self.assertEqual(import_fixes.closest_names("Currency", written)[:1], ["INR"], written)


class TestUnitWords(BaseAssistantTest):
    def test_a_unit_written_short_is_the_likely_one_not_a_new_unit(self):
        # #34001, live: Tally's "Mtr" (0.75 like "Meter", under the 0.8 a likely spelling needs)
        # was advised as a new UOM to create
        if not frappe.db.get_value("UOM", "Meter", "enabled"):
            self.skipTest("Meter is switched off on this site")
        session = frappe._dict(
            name="IMP-TEST", target_doctype="Item", template_options="{}", transformation_rules=None
        )
        group = {
            "cause": import_dry_run.CAUSE_MISSING_LINK,
            "link_doctype": "UOM",
            "label": "Default Unit of Measure",
            "parent": "Item",
            "field": "stock_uom",
            "value": "Mtr",
            "count": 3,
        }

        advice = import_fixes.advise(session, group)

        mapped = next(fix for fix in advice["fixes"] if fix["action"] == "map")
        self.assertEqual((mapped["closest"][:1], mapped.get("likely")), (["Meter"], "Meter"))
        self.assertIn("written short", advice["explanation"])
        # Offered with a note, it was still created (live, 2026-11-06): it isn't offered at all
        self.assertNotIn("create", [fix["action"] for fix in advice["fixes"]])
        self.assertIn("written short", advice["cannot_create"])


class TestSwitchedOffRecords(BaseAssistantTest):
    def test_a_record_switched_off_by_its_enabled_field_is_never_offered_or_taken(self):
        # UOM and Currency are switched off by "enabled", not "disabled"
        tag = frappe.generate_hash(length=6)
        off = frappe.get_doc({"doctype": "UOM", "uom_name": f"Kilogram {tag}", "enabled": 0}).insert().name
        on = frappe.get_doc({"doctype": "UOM", "uom_name": f"Kilogramme {tag}"}).insert().name
        group = {
            "cause": import_dry_run.CAUSE_MISSING_LINK,
            "link_doctype": "UOM",
            "label": "UOM",
            "parent": "Item",
            "field": "stock_uom",
            "value": f"Kilogrm {tag}",
        }

        closest = import_fixes.closest_names("UOM", f"Kilogrm {tag}")
        with self.assertRaises(import_fixes.FixProblem) as refused:
            import_fixes._map(frappe._dict(template_options="{}"), group, {"to": off}, [])

        self.assertIn(on, closest)
        self.assertNotIn(off, closest)
        self.assertIn("switched off", str(refused.exception))
        self.assertEqual(
            import_fixes._map(frappe._dict(template_options="{}"), group, {"to": on}, [])[0]["to"], on
        )


class TestKnownRefusals(BaseAssistantTest):
    """#34417: a refusal ERPNext or India Compliance says in its own words, explained in the user's."""

    def _explained(self, message):
        group = {"cause": import_dry_run.CAUSE_REJECTED, "message": message, "count": 3}
        return import_fixes.advise(frappe._dict(target_doctype="Item"), group)["explanation"]

    def test_known_refusals_are_said_in_business_words(self):
        cases = {
            "HSN/SAC Code is mandatory for item ABC": "HSN/SAC code",
            "Invalid GSTIN: 29ABCDE1234": "GSTIN isn't one India Compliance accepts",
            "Date 2025-01-01 is not in any active Fiscal Year": "isn't in a fiscal year",
            "1 units of Item X needed in Warehouse Y: Insufficient Stock": "isn't enough stock",
            "Customer Acme is disabled": "is disabled in ERPNext",
        }
        for message, words in cases.items():
            with self.subTest(message=message):
                explanation = self._explained(message)
                self.assertTrue(explanation.startswith("3 rows"), explanation)
                self.assertIn(words, explanation)

    def test_an_unknown_refusal_keeps_erpnexts_message(self):
        explanation = self._explained("Something only ERPNext knows about")
        self.assertIn("Something only ERPNext knows about", explanation)


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Item")
class TestOneValueForEveryRow(BaseAssistantTest):
    """#34415: a required field the file leaves blank, or has no column for, gets one value for
    every row (one Item Group for a file of items), not only leave the rows out."""

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.registry = get_tool_registry()
        self.track_test_files()
        self.tag = frappe.generate_hash(length=6)
        self.group = (
            frappe.get_doc(
                {
                    "doctype": "Item Group",
                    "item_group_name": f"Fasteners {self.tag}",
                    "parent_item_group": "All Item Groups",
                }
            )
            .insert()
            .name
        )

    def tearDown(self):
        frappe.set_user("Administrator")
        self.delete_test_files()
        super().tearDown()

    def _run(self, tool_name, arguments):
        return self.registry.get_tool(tool_name)._safe_execute(arguments)

    def _session(self):
        from frappe_assistant_core.tests.base_test import item_hsn_fields

        hsn = list(item_hsn_fields().values())  # India Compliance refuses an Item without one
        header = ["Code", "Name", "UOM"] + (["HSN"] if hsn else [])
        lines = [",".join(header)] + [
            ",".join([f"F{i} {self.tag}", f"Bolt {i}", "Nos", *hsn]) for i in (1, 2)
        ]
        file_doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": "items.csv",
                "content": ("\n".join(lines) + "\n").encode(),
                "is_private": 1,
            }
        ).insert()
        session = self._run("start_import_session", {"file_url": file_doc.file_url})["result"]["session_id"]
        mapping = {
            "Code": "item_code",
            "Name": "item_name",
            "UOM": "stock_uom",
            **({"HSN": "gst_hsn_code"} if hsn else {}),
        }
        self.assertTrue(
            self._run("set_column_mapping", {"session": session, "doctype": "Item", "mapping": mapping})[
                "success"
            ]
        )
        return session

    def test_a_field_the_file_has_no_column_for_is_filled_in_and_imported(self):
        session = self._session()
        checked = self._run("dry_run_import", {"session": session})["result"]
        group = next(g for g in checked["groups"] if any(f["action"] == "fill" for f in g["fixes"]))
        self.assertEqual(next(f for f in group["fixes"] if f["action"] == "fill")["field"], "item_group")

        fixed = self._run(
            "dry_run_import",
            {"session": session, "fixes": [{"group": group["id"], "action": "fill", "value": self.group}]},
        )
        self.assertTrue(fixed["success"], fixed)
        result = fixed["result"]
        self.assertEqual((result["ready"], result["failed"]), (2, 0), result.get("groups"))

        doc = engine_session(session)
        imported = self._run(
            "start_import",
            {
                "session": session,
                "doctype": "Item",
                "rows": 2,
                "import_type": "Insert New Records",
                "validated_fingerprint": result.get("validated_fingerprint"),
                "file_name": doc.file_name,
            },
        )
        self.assertTrue(imported["success"], imported)
        groups = frappe.get_all("Item", filters={"item_code": ["like", f"% {self.tag}"]}, pluck="item_group")
        self.assertEqual(groups, [self.group, self.group])

    def test_a_field_an_app_says_is_required_in_its_own_words_is_filled_in(self):
        # PR #392, F4: India Compliance refuses an Item with "HSN/SAC Code is required. Please enter
        # a valid HSN/SAC code." (a MandatoryError, not Frappe's "Value missing for Item: ..."), so
        # fill was refused and FACO could only leave the items out. A hook that refuses so stands in.
        from erpnext.stock.doctype.item.item import Item

        from frappe_assistant_core.tests.base_test import item_hsn_fields

        brand = frappe.get_doc({"doctype": "Brand", "brand": f"Acme {self.tag}"}).insert().name
        hsn = list(item_hsn_fields().values())  # India Compliance refuses an Item without one
        lines = ["Code,Name,UOM,Group" + (",HSN" if hsn else "")] + [
            ",".join([f"B{i} {self.tag}", f"Bolt {i}", "Nos", self.group, *hsn]) for i in (1, 2)
        ]
        file_doc = frappe.get_doc(
            {"doctype": "File", "file_name": "items.csv", "content": "\n".join(lines) + "\n", "is_private": 1}
        ).insert()
        session = self._run("start_import_session", {"file_url": file_doc.file_url})["result"]["session_id"]
        mapping = {"Code": "item_code", "Name": "item_name", "UOM": "stock_uom", "Group": "item_group"}
        if hsn:
            mapping["HSN"] = "gst_hsn_code"
        self.assertTrue(
            self._run("set_column_mapping", {"session": session, "doctype": "Item", "mapping": mapping})[
                "success"
            ]
        )
        real_validate = Item.validate

        def validate(item):
            if not item.brand:
                # nosemgrep: frappe-missing-translate-function-python — a test stand-in for an app's refusal
                frappe.throw("Brand is required. Please enter a valid brand.", frappe.MandatoryError)
            return real_validate(item)

        with patch.object(Item, "validate", validate):
            checked = self._run("dry_run_import", {"session": session})["result"]
            group = next(g for g in checked["groups"] if g["error"] == "MandatoryError")
            fill = [f for f in group["fixes"] if f["action"] == "fill"]
            self.assertEqual([f["field"] for f in fill], ["brand"], group)

            fixed = self._run(
                "dry_run_import",
                {"session": session, "fixes": [{"group": group["id"], "action": "fill", "value": brand}]},
            )

        self.assertTrue(fixed["success"], fixed)
        self.assertEqual((fixed["result"]["ready"], fixed["result"]["failed"]), (2, 0))

    def test_an_app_message_naming_no_field_of_the_doctype_offers_no_fill(self):
        session = self._session()
        group = {
            "cause": import_dry_run.CAUSE_REJECTED,
            "error": "MandatoryError",
            "message": "Something else is required first.",
        }

        self.assertIsNone(import_fixes._fill_field(engine_session(session), group))

    def test_hsn_explanation_offers_one_code_for_every_item(self):
        explanation = import_fixes.known_refusal("HSN/SAC Code is required.", "3 rows")

        self.assertNotIn("give the items their code first", explanation)
        self.assertIn("one code for every item", explanation)

    def test_a_value_that_isnt_a_record_is_refused(self):
        session = self._session()
        checked = self._run("dry_run_import", {"session": session})["result"]
        group = next(g for g in checked["groups"] if any(f["action"] == "fill" for f in g["fixes"]))

        fixed = self._run(
            "dry_run_import",
            {
                "session": session,
                "fixes": [{"group": group["id"], "action": "fill", "value": f"Nowhere {self.tag}"}],
            },
        )

        self.assertFalse(fixed["success"], fixed)
        self.assertIn("There is no Item Group", json.dumps(fixed))
