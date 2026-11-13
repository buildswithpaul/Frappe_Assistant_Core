# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Create missing masters in one approved batch (#33992): the dry run plans every missing master
that can be created from its name; create_document creates them all in one call (its documents
list, with import_session: one approval card) or none, and links each to the import session.

Customer again: Customer Group and Territory are trees (a parent each), Market Segment is a
plain list, and Currency is a system record that is never created here.
"""

import json
import unittest
from unittest.mock import patch

import frappe

from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.plugins.core.tools.create_document import DocumentCreate
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils import import_fixes

PARENT_FIELDS = {"Customer Group": "parent_customer_group", "Territory": "parent_territory"}

MAPPING = {
    "Customer Name": "customer_name",
    "Customer Group": "customer_group",
    "Territory": "territory",
    "Market Segment": "market_segment",
    "Currency": "default_currency",
}


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Customer")
class TestImportMasters(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.registry = get_tool_registry()
        self.track_test_files()
        self.tag = frappe.generate_hash(length=6)
        self.group = f"Wholesale {self.tag}"
        self.territory = f"North {self.tag}"
        self.segment = f"Retail Chains {self.tag}"
        self.currency = f"ZZ{self.tag}"

    def tearDown(self):
        frappe.set_user("Administrator")
        self.delete_test_files()
        super().tearDown()

    # -- helpers -----------------------------------------------------------------------

    def _run(self, tool_name, arguments):
        return self.registry.get_tool(tool_name)._safe_execute(arguments)

    def _session(self):
        """Upload a CSV, open its session, map it and check it, as the earlier steps do."""
        t = self.tag
        lines = [",".join(MAPPING)]
        lines += [
            f"Alpha {t},{self.group},{self.territory},{self.segment},INR",
            f"Beta {t},{self.group},{self.territory},,INR",
            f"Gamma {t},{self.group},,,{self.currency}",
        ]
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
            "set_column_mapping", {"session": session, "mapping": MAPPING, "doctype": "Customer"}
        )
        self.assertTrue(mapped["success"], mapped)
        checked = self._run("dry_run_import", {"session": session})
        self.assertTrue(checked["success"], checked)
        return session, checked["result"]

    @staticmethod
    def _planned(result, doctype):
        return next(m for m in result["masters_plan"] if m["doctype"] == doctype)

    @staticmethod
    def _records(result, **parents):
        """The plan as FACO passes it to create_document once the user approves it, with any
        parent the user changed."""
        documents = []
        for m in result["masters_plan"]:
            data = dict(m["data"])
            if m["doctype"] in parents:
                data[PARENT_FIELDS[m["doctype"]]] = parents[m["doctype"]]
            documents.append({"doctype": m["doctype"], "data": data})
        return documents

    def _create(self, session, documents):
        return self._run("create_document", {"documents": documents, "import_session": session})

    def _doc(self, session):
        return frappe.get_doc("FAC Import Session", session)

    def _group_node(self, name):
        return frappe.get_doc(
            {
                "doctype": "Customer Group",
                "customer_group_name": name,
                "parent_customer_group": "All Customer Groups",
                "is_group": 1,
            }
        ).insert()

    # -- registration ------------------------------------------------------------------

    def test_creating_masters_is_create_document_so_one_approval_card(self):
        from frappe_assistant_core.utils.tool_category_detector import detect_tool_category

        tool = self.registry.get_tool("create_document")

        self.assertEqual(detect_tool_category(tool), "write")
        self.assertIn("documents", tool.inputSchema["properties"])
        self.assertIn("import_session", tool.inputSchema["properties"])
        self.assertIsNone(self.registry.get_tool("create_missing_masters"))

    # -- criterion 1: one plan listing every record ---------------------------------------------

    def test_the_dry_run_plans_every_missing_master_that_can_be_created(self):
        _session, result = self._session()

        plan = {(m["doctype"], m["name"]): m for m in result["masters_plan"]}

        self.assertEqual(
            set(plan),
            {("Customer Group", self.group), ("Territory", self.territory), ("Market Segment", self.segment)},
        )
        self.assertEqual(plan[("Customer Group", self.group)]["rows"], 3)
        self.assertEqual(plan[("Territory", self.territory)]["rows"], 2)

    def test_a_master_that_cannot_be_created_is_not_offered_and_says_why(self):
        _session, result = self._session()

        currency = next(g for g in result["groups"] if g.get("value") == self.currency)

        self.assertNotIn("create", [f["action"] for f in currency["fixes"]])
        self.assertIn("system record", currency["cannot_create"])
        self.assertNotIn("Currency", [m["doctype"] for m in result["masters_plan"]])

    def test_a_missing_link_that_can_be_created_points_to_the_batch_tool(self):
        _session, result = self._session()

        group = next(g for g in result["groups"] if g.get("value") == self.group)

        # A "misspelt?" note is added when a like-named group already exists on the site (#26), so
        # only the fields this test is about are compared.
        fields = ("action", "use", "doctype", "name", "parent")
        self.assertIn(
            {
                "action": "create",
                "use": "create_document",
                "doctype": "Customer Group",
                "name": self.group,
                "parent": "All Customer Groups",
            },
            [{key: fix.get(key) for key in fields} for fix in group["fixes"]],
        )

    # -- criterion 3: a parent is shown and can be changed ---------------------------------------

    def test_the_plan_shows_each_tree_masters_parent(self):
        _session, result = self._session()

        self.assertEqual(self._planned(result, "Customer Group")["parent"], "All Customer Groups")
        self.assertEqual(self._planned(result, "Territory")["parent"], "All Territories")
        self.assertIsNone(self._planned(result, "Market Segment")["parent"])

    def test_the_user_can_choose_another_parent(self):
        session, result = self._session()
        commercial = self._group_node(f"Commercial {self.tag}")

        response = self._create(session, self._records(result, **{"Customer Group": commercial.name}))

        self.assertTrue(response["success"], response)
        self.assertEqual(
            frappe.db.get_value("Customer Group", self.group, "parent_customer_group"), commercial.name
        )

    def test_a_parent_that_cannot_hold_records_is_refused_and_nothing_is_created(self):
        session, result = self._session()
        leaf = frappe.get_doc(
            {
                "doctype": "Customer Group",
                "customer_group_name": f"Leaf {self.tag}",
                "parent_customer_group": "All Customer Groups",
            }
        ).insert()

        response = self._create(session, self._records(result, **{"Customer Group": leaf.name}))

        self.assertFalse(response["success"], response)
        self.assertIn(f"'{leaf.name}' isn't a Customer Group", response["result"]["problems"][0]["error"])
        self.assertFalse(frappe.db.exists("Territory", self.territory))  # all or nothing

    # -- #34409: a missing parent is created first, as a group ------------------------------------

    def _under(self, result, *chain):
        """The plan's records, with the Customer Group under ``chain`` (top first) and the chain's
        records added before it, each under the one before (the first under the root)."""
        records = self._records(result, **{"Customer Group": chain[-1]})
        parent = "All Customer Groups"
        for name in chain:
            # sent as it is created, a group, so the approval card shows it (Paul's review of 49da112)
            data = {"customer_group_name": name, "parent_customer_group": parent, "is_group": 1}
            records.append({"doctype": "Customer Group", "data": data})
            parent = name
        return records

    def test_a_missing_parent_sent_with_its_child_is_created_first_as_a_group(self):
        # The ticket's "Retail > Online": the rows need Online, under a Retail that isn't there.
        session, result = self._session()
        retail = f"Retail {self.tag}"

        response = self._create(session, self._under(result, retail))

        self.assertTrue(response["success"], response)
        self.assertEqual(
            frappe.db.get_value("Customer Group", retail, ["is_group", "parent_customer_group"]),
            (1, "All Customer Groups"),
        )
        self.assertEqual(
            frappe.db.get_value("Customer Group", self.group, ["is_group", "parent_customer_group"]),
            (0, retail),
        )
        created = [r["name"] for r in response["result"]["created"]]
        self.assertLess(created.index(retail), created.index(self.group))
        records = {r.record_name: r.parent_record for r in self._doc(session).created_records}
        self.assertEqual((records[retail], records[self.group]), ("All Customer Groups", retail))

    def test_a_missing_chain_is_created_top_down_whatever_order_it_is_sent_in(self):
        session, result = self._session()
        chain = [f"Retail {self.tag}", f"Online {self.tag}", f"Marketplaces {self.tag}"]
        records = self._under(result, *chain)

        response = self._create(session, list(reversed(records)))

        self.assertTrue(response["success"], response)
        created = [r["name"] for r in response["result"]["created"] if r["doctype"] == "Customer Group"]
        self.assertEqual(created, [*chain, self.group])
        for parent, child in zip(chain, chain[1:] + [self.group]):
            self.assertEqual(frappe.db.get_value("Customer Group", child, "parent_customer_group"), parent)
        self.assertEqual([frappe.db.get_value("Customer Group", n, "is_group") for n in chain], [1, 1, 1])

    def test_a_record_not_sent_as_it_is_created_is_refused(self):
        # The approval card shows what FACO sends: a group or a root parent added here was created
        # unseen (#34409, Paul's review of 49da112). The refusal says what to send instead.
        session, result = self._session()
        retail = f"Retail {self.tag}"
        cases = {
            "a parent without is_group": lambda records: records[-1]["data"].pop("is_group"),
            "no parent": lambda records: records[-1]["data"].pop("parent_customer_group"),
        }
        for case, change in cases.items():
            with self.subTest(case=case):
                records = self._under(result, retail)
                change(records)

                response = self._create(session, records)

                self.assertFalse(response["success"], response)
                error = response["result"]["problems"][0]["error"]
                self.assertIn(f"Customer Group '{retail}' is created as", error)
                self.assertIn('"is_group": 1', error)
                self.assertIn('"parent_customer_group": "All Customer Groups"', error)
                self.assertFalse(frappe.db.exists("Customer Group", retail))

    def test_a_record_nothing_goes_under_cannot_be_made_a_group(self):
        session, result = self._session()
        records = self._records(result)
        records[0]["data"]["is_group"] = 1  # the rows' own group, with nothing under it

        response = self._create(session, records)

        self.assertFalse(response["success"], response)
        self.assertIn("goes under it", response["result"]["problems"][0]["error"])

    def test_a_record_the_rows_dont_need_and_nothing_goes_under_is_still_refused(self):
        session, result = self._session()
        records = self._records(result) + [
            {
                "doctype": "Customer Group",
                "data": {
                    "customer_group_name": f"Retail {self.tag}",
                    "parent_customer_group": "All Customer Groups",
                },
            }
        ]

        response = self._create(session, records)

        self.assertFalse(response["success"], response)
        self.assertIn("isn't one of the masters", response["result"]["problems"][0]["error"])

    def test_records_under_each_other_are_refused_and_nothing_is_created(self):
        session, result = self._session()
        loop = f"Loop {self.tag}"
        records = self._records(result, **{"Customer Group": loop}) + [
            {
                "doctype": "Customer Group",
                "data": {"customer_group_name": loop, "parent_customer_group": self.group},
            }
        ]
        for record in records:  # each holds the other, so each is sent as a group
            if record["doctype"] == "Customer Group":
                record["data"]["is_group"] = 1

        response = self._create(session, records)

        self.assertFalse(response["success"], response)
        self.assertIn("under each other", str(response["result"]))
        self.assertFalse(frappe.db.exists("Customer Group", loop))
        self.assertFalse(frappe.db.exists("Territory", self.territory))

    # -- one approval, all created, linked to the session (criterion 2) -----------------------------

    def test_one_call_creates_every_master_and_links_it_to_the_session(self):
        session, result = self._session()

        response = self._create(session, self._records(result))

        self.assertTrue(response["success"], response)
        self.assertEqual(len(response["result"]["created"]), 3)
        for doctype, name in [
            ("Customer Group", self.group),
            ("Territory", self.territory),
            ("Market Segment", self.segment),
        ]:
            self.assertTrue(frappe.db.exists(doctype, name), (doctype, name))
        doc = self._doc(session)
        self.assertEqual(
            {(r.record_doctype, r.record_name, r.parent_record or None) for r in doc.created_records},
            {
                ("Customer Group", self.group, "All Customer Groups"),
                ("Territory", self.territory, "All Territories"),
                ("Market Segment", self.segment, None),
            },
        )
        self.assertEqual((doc.steps[-1].step, doc.steps[-1].outcome), ("Create Masters", "Success"))

        # The rows that needed them now pass: only the Currency still fails.
        rechecked = self._run("dry_run_import", {"session": session})["result"]
        self.assertEqual([g.get("value") for g in rechecked["groups"]], [self.currency])
        self.assertEqual(rechecked["masters_plan"], [])

    def test_one_master_sent_without_documents_is_checked_and_linked_too(self):
        session, result = self._session()
        segment = self._planned(result, "Market Segment")

        response = self._run(
            "create_document",
            {"doctype": "Market Segment", "data": segment["data"], "import_session": session},
        )

        self.assertTrue(response["success"], response)
        self.assertEqual(
            [(r.record_doctype, r.record_name) for r in self._doc(session).created_records],
            [("Market Segment", self.segment)],
        )

    def test_one_record_the_file_does_not_need_is_refused_even_without_documents(self):
        session, _result = self._session()

        response = self._run(
            "create_document",
            {"doctype": "UOM", "data": {"uom_name": f"Box {self.tag}"}, "import_session": session},
        )

        self.assertFalse(response["success"], response)
        self.assertFalse(frappe.db.exists("UOM", f"Box {self.tag}"))

    def test_one_record_failing_creates_none_and_says_which(self):
        session, result = self._session()
        real_execute = DocumentCreate.execute

        def territory_fails(tool, arguments):
            if arguments.get("doctype") == "Territory":
                return {"success": False, "error": "Territory is locked"}
            return real_execute(tool, arguments)

        logged = {"method": "Document Creation Error"}
        logs_before = frappe.db.count("Error Log", logged)
        with (
            patch.object(DocumentCreate, "execute", autospec=True, side_effect=territory_fails),
            patch("frappe.utils.global_search.sync_value_in_queue") as search_queue,
        ):
            response = self._create(session, self._records(result))

        self.assertFalse(response["success"], response)
        self.assertEqual(frappe.db.count("Error Log", logged), logs_before + 1)
        self.assertIn("Territory", response["result"]["error"])
        self.assertIn("Territory is locked", response["result"]["error"])
        self.assertFalse(frappe.db.exists("Customer Group", self.group))
        self.assertFalse(self._doc(session).created_records)
        # The record that was undone never reaches global search.
        self.assertEqual(search_queue.call_count, 0)

    def test_a_controller_that_commits_cannot_end_the_batch(self):
        session, result = self._session()
        real_execute = DocumentCreate.execute
        commit_held = []
        # The batch holds a commit with Frappe's own flag where it has one (v16), else a stand-in (v15).
        flag_before = getattr(frappe.db, "_disable_transaction_control", 0)

        def commits(tool, arguments):
            # A controller's own frappe.db.commit() would make the records before it permanent.
            if arguments.get("doctype"):  # a record's own call, not the list call around them
                commit_held.append(
                    "commit" in vars(frappe.db)
                    or getattr(frappe.db, "_disable_transaction_control", 0) > flag_before
                )
            frappe.db.commit()  # nosemgrep: frappe-manual-commit — the controller this test imitates
            return real_execute(tool, arguments)

        with patch.object(DocumentCreate, "execute", autospec=True, side_effect=commits):
            response = self._create(session, self._records(result))

        self.assertTrue(response["success"], response)
        self.assertEqual(commit_held, [True, True, True])
        self.assertNotIn("commit", vars(frappe.db))  # given back afterwards
        self.assertEqual(getattr(frappe.db, "_disable_transaction_control", 0), flag_before)

    def test_records_created_reach_global_search_once_all_succeed(self):
        session, result = self._session()

        with patch("frappe.utils.global_search.sync_value_in_queue") as search_queue:
            response = self._create(session, self._records(result))

        self.assertTrue(response["success"], response)
        queued = {(c.args[0]["doctype"], c.args[0]["name"]) for c in search_queue.call_args_list}
        self.assertIn(("Customer Group", self.group), queued)

    def test_a_record_erpnext_would_name_differently_is_refused(self):
        session, result = self._session()
        real_execute = DocumentCreate.execute

        def renamed(tool, arguments):
            out = real_execute(tool, arguments)
            if arguments.get("doctype") == "Market Segment":
                out["name"] = f"{out['name']} - X"
            return out

        with patch.object(DocumentCreate, "execute", autospec=True, side_effect=renamed):
            response = self._create(session, self._records(result))

        self.assertFalse(response["success"], response)
        self.assertIn("name", response["result"]["error"])
        self.assertFalse(frappe.db.exists("Customer Group", self.group))

    # -- the model never invents what is created ----------------------------------------------

    def test_a_name_that_is_not_the_groups_value_is_refused(self):
        session, result = self._session()
        records = self._records(result)
        records[0]["data"]["customer_group_name"] = "Made Up"

        response = self._create(session, records)

        self.assertFalse(response["success"], response)
        self.assertIn("isn't one of the masters", response["result"]["problems"][0]["error"])
        self.assertFalse(frappe.db.exists("Territory", self.territory))

    def test_a_record_the_file_does_not_need_is_refused(self):
        session, result = self._session()

        response = self._create(
            session, [{"doctype": "Customer Group", "data": {"customer_group_name": f"Unneeded {self.tag}"}}]
        )

        self.assertFalse(response["success"], response)
        self.assertIn("isn't one of the masters", response["result"]["problems"][0]["error"])
        self.assertFalse(frappe.db.exists("Customer Group", f"Unneeded {self.tag}"))

    def test_a_master_with_more_than_its_name_and_parent_is_refused(self):
        session, result = self._session()
        records = self._records(result)
        records[0]["data"]["default_price_list"] = "Standard Selling"

        response = self._create(session, records)

        self.assertFalse(response["success"], response)
        error = response["result"]["problems"][0]["error"]
        self.assertIn("default_price_list", error)
        self.assertIn("customer_group_name and parent_customer_group", error)  # what it does take

    def test_a_master_that_already_exists_is_refused(self):
        session, result = self._session()
        frappe.get_doc({"doctype": "Market Segment", "market_segment": self.segment}).insert()

        response = self._create(session, self._records(result))

        self.assertFalse(response["success"], response)
        self.assertIn("already exists", response["result"]["problems"][0]["error"])

    def test_a_currency_sent_anyway_is_refused(self):
        session, result = self._session()
        currency = next(g for g in result["groups"] if g.get("value") == self.currency)

        response = self._create(session, [{"doctype": "Currency", "data": {"currency_name": self.currency}}])

        self.assertFalse(response["success"], response)
        self.assertIn("can't be created here", response["result"]["problems"][0]["error"])
        self.assertFalse(frappe.db.exists("Currency", self.currency))

    def test_masters_are_not_created_after_the_mapping_changed(self):
        session, result = self._session()
        self._run("set_column_mapping", {"session": session, "mapping": MAPPING, "doctype": "Customer"})

        response = self._create(session, self._records(result))

        self.assertFalse(response["success"], response)
        self.assertIn("Check it with dry_run_import first", response["result"]["error"])
        self.assertFalse(frappe.db.exists("Customer Group", self.group))

    def test_masters_are_not_created_from_a_check_the_session_no_longer_matches(self):
        session, result = self._session()
        # The session edited after its check (update_document can), but not checked again.
        self._doc(session).db_set("excluded_rows", "[2]")

        response = self._create(session, self._records(result))

        self.assertFalse(response["success"], response)
        self.assertFalse(frappe.db.exists("Customer Group", self.group))

    def test_another_users_session_is_refused(self):
        session, result = self._session()
        frappe.set_user(self.make_throwaway_user("other", roles=("Sales Manager",)))

        response = self._create(session, self._records(result))

        self.assertFalse(response["success"])
        frappe.set_user("Administrator")
        self.assertFalse(frappe.db.exists("Customer Group", self.group))

    # -- which masters can be created ---------------------------------------------------------

    def test_only_masters_named_by_their_name_alone_can_be_created(self):
        can = import_fixes.cannot_create

        for doctype in ("Customer Group", "Territory", "Market Segment", "UOM", "Brand"):
            self.assertEqual(can(doctype), "", doctype)
        self.assertIn("names it itself", can("Customer"))  # a naming series
        self.assertIn("names it itself", can("Warehouse"))  # the company's abbreviation is added
        self.assertIn("more than a name", can("Item"))
        self.assertIn("isn't a master", can("Sales Invoice"))
        self.assertIn("system record", can("Currency"))
        self.assertIn("chart of accounts", can("Company"))

    def test_a_master_needing_a_table_row_or_named_after_another_record_is_not_offered(self):
        can = import_fixes.cannot_create

        self.assertIn("more than a name", can("Tax Withholding Category"))  # a rate table row
        self.assertIn("must be an existing", can("Supplier Scorecard"))  # named after a Supplier

    def test_a_record_of_the_doctype_the_file_imports_is_not_planned(self):
        # A Territory file whose row 3 names a parent that is neither in ERPNext nor in the file.
        # (A parent higher up the file is fine: the import takes such a file a level at a time.)
        t = self.tag
        lines = ["Territory Name,Parent Territory,Is Group", f"FacNorth {t},All Territories,1"]
        lines.append(f"FacSouth-1 {t},FacSouth {t},0")
        file_doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": "territories.csv",
                "content": ("\n".join(lines) + "\n").encode(),
                "is_private": 1,
            }
        ).insert()
        session = self._run("start_import_session", {"file_url": file_doc.file_url})["result"]["session_id"]
        mapping = {
            "Territory Name": "territory_name",
            "Parent Territory": "parent_territory",
            "Is Group": "is_group",
        }
        mapped = self._run(
            "set_column_mapping", {"session": session, "mapping": mapping, "doctype": "Territory"}
        )
        self.assertTrue(mapped["success"], mapped)

        result = self._run("dry_run_import", {"session": session})["result"]

        self.assertEqual(result["masters_plan"], [])
        parent = next(g for g in result["groups"] if g.get("value") == f"FacSouth {t}")
        self.assertNotIn("create", [f["action"] for f in parent["fixes"]])
        self.assertIn("imports Territory records itself", parent["cannot_create"])

    def test_the_default_parent_is_never_a_root_that_cannot_hold_records(self):
        leaf = frappe.get_doc(
            {
                "doctype": "Customer Group",
                "customer_group_name": f"Leaf {self.tag}",
                "parent_customer_group": "All Customer Groups",
            }
        ).insert()

        # A tree with several roots: get_root_of may return any of them, a leaf too.
        with patch.object(import_fixes, "get_root_of", autospec=True, return_value=leaf.name):
            self.assertIsNone(import_fixes.default_parent("Customer Group"))

    def test_creating_is_off_where_create_document_is_off(self):
        from frappe_assistant_core.core.tool_registry import ToolRegistry

        def create_document_off(registry, tool_name, user):
            return tool_name != "create_document"

        with patch.object(
            ToolRegistry, "_is_tool_accessible", autospec=True, side_effect=create_document_off
        ):
            self.assertIn("turned off", import_fixes.cannot_create("Customer Group"))

    def test_a_site_can_keep_more_doctypes_from_being_created(self):
        with patch.dict(frappe.local.conf, {"fac_import_never_create_doctypes": ["Brand"]}):
            self.assertIn("doesn't allow", import_fixes.cannot_create("Brand"))

    def test_a_user_who_cannot_create_it_is_not_offered_it(self):
        user = self.make_desk_user("reader")
        self.assert_cannot(user, "create", "Customer Group")
        frappe.set_user(user)

        self.assertIn("aren't allowed", import_fixes.cannot_create("Customer Group"))
