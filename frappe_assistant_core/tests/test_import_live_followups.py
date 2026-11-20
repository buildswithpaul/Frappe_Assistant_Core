# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""What two live imports of 2026-11-20 ran into: a chart whose Parent Account was left out by the mapping
(so its check's reply grew too long to read), a project file whose own IDs were refused twice, fixes sent
again refused as unknown, "Government" recommended for 262 CSR clients, a planned_masters call answered
about documents it hadn't sent, an import session edit sent to an administrator, and the defaults after a
replace asked one by one."""

import unittest
from unittest.mock import patch

import frappe

from frappe_assistant_core.core.base_tool import permission_error_result
from frappe_assistant_core.tests.chart_case import ChartCase
from frappe_assistant_core.tests.test_import_run import ImportRunCase
from frappe_assistant_core.utils import import_chart, import_fixes

HAS_ERPNEXT = "erpnext" in frappe.get_installed_apps()


class TestWithoutData(unittest.TestCase):
    def test_a_name_narrowed_to_one_thing_is_not_a_companywide_default(self):
        for name in ("depreciation on networking equipment", "creditors for expenses", "loan - sbi"):
            self.assertTrue(import_chart.NARROWED.search(name), name)
        for name in ("sundry creditors", "depreciation", "accounts payable"):
            self.assertFalse(import_chart.NARROWED.search(name), name)

    def test_the_defaults_card_selects_the_suggestion_and_names_what_nothing_fits(self):
        proposals = [
            {
                "field": "default_payable_account",
                "label": "Default Payable Account",
                "suggested": "2100 - Sundry Creditors - X",
                "choices": ["2100 - Sundry Creditors - X", "2050 - Gratuity Payable - X"],
                "change_type": {
                    "account": "2100 - Sundry Creditors - X",
                    "from": "Current Liability",
                    "to": "Payable",
                    "note": "retype it",
                },
            },
            {"field": "write_off_account", "label": "Write Off Account", "suggested": None, "choices": []},
        ]

        card = import_chart.defaults_card("X Co", proposals)

        (question,) = card["questions"]
        self.assertEqual(question["id"], "default:default_payable_account")
        chosen = [o for o in question["options"] if o["recommended"]]
        self.assertEqual(len(chosen), 1)
        self.assertEqual(chosen[0]["set"], {"default_payable_account": "2100 - Sundry Creditors - X"})
        self.assertEqual(
            chosen[0]["change_type"], {"account": "2100 - Sundry Creditors - X", "account_type": "Payable"}
        )
        self.assertEqual(question["options"][-1]["set"], {})  # leave empty
        self.assertIn("Write Off Account", card["left_empty"])

    def test_the_group_the_sites_customers_use_is_recommended_then_commercial(self):
        values = ["Government", "Non Profit", "Commercial", "Individual"]
        with patch.object(frappe.db, "count", return_value=0):
            self.assertEqual(
                import_fixes._likeliest_first("Customer", "customer_group", values)[0], "Commercial"
            )
        with patch.object(
            frappe.db, "count", side_effect=lambda dt, f: 5 if f["customer_group"] == "Non Profit" else 0
        ):
            self.assertEqual(
                import_fixes._likeliest_first("Customer", "customer_group", values)[0], "Non Profit"
            )
        with patch.object(frappe.db, "count", return_value=0):
            self.assertEqual(
                import_fixes._likeliest_first("Supplier", "supplier_group", ["B", "A"]), ["B", "A"]
            )

    def test_an_import_session_edit_is_pointed_at_the_tools_not_an_administrator(self):
        refused = permission_error_result("FAC Import Session", "can't be set by hand", name="IMP-1")
        self.assertIn("set_column_mapping", refused["suggestion"])
        self.assertNotIn("Contact your system administrator", refused["suggestion"])
        self.assertIn("administrator", permission_error_result("Customer", "no")["suggestion"])


@unittest.skipUnless(HAS_ERPNEXT, "needs ERPNext's Account")
class TestChartKeepsItsParents(ChartCase):
    def test_the_parent_account_column_stays_mapped(self):
        session = self._chart()

        nodes = import_chart.read_chart(frappe.get_doc("FAC Import Session", session))
        self.assertTrue(any(n["parent_name"] for n in nodes))

    def test_a_flat_chart_lists_a_short_outline_and_the_card_first(self):
        rows = [f"Expense {i:03d},{7000 + i},,,Expense,0" for i in range(80)]
        checked = self._check(self._chart(rows), company=self.company)

        self.assertLessEqual(len(checked["outline"]), import_chart.OUTLINE_SHOWN)
        self.assertEqual(checked["outline_more"], 80 - import_chart.OUTLINE_SHOWN)
        keys = list(checked)
        self.assertLess(keys.index("questions"), keys.index("outline"))

    def test_a_replace_gives_the_defaults_as_one_card(self):
        rows = [
            "Client Assets,,,,,",
            "Client Cash,1020,Client Assets,Cash,,",
            "Client Liabilities,,,,,",
            "Gratuity Payable,2050,Client Liabilities,Payable,,",
            "Sundry Creditors,2100,Client Liabilities,Current Liability,,",
            "Client Expenses,,,,,",
            "Depreciation on Computers,5100,Client Expenses,Expense Account,,",
        ]
        session = self._chart(rows)
        self._clear_references()
        figures = import_chart.replace_figures(
            self.company, import_chart.read_chart(frappe.get_doc("FAC Import Session", session))
        )
        done = self._run(
            "replace_chart_of_accounts",
            {
                "session": session,
                "company": self.company,
                "source_system": self.system,
                **{k: figures[k] for k in ("accounts_removed", "accounts_created", "tax_setup_removed")},
            },
        )
        self.assertTrue(done["success"], done)

        result = done["result"]
        self.assertLess(list(result).index("card"), list(result).index("defaults_proposed"))
        ids = [q["id"] for q in result["card"]["questions"]]
        self.assertEqual(len(ids), len(set(ids)))
        depreciation = {p["field"]: p for p in result["defaults_proposed"]}.get(
            "depreciation_expense_account"
        )
        if depreciation:  # ERPNext may set it itself from the new chart
            self.assertNotIn("change_type", depreciation)  # one asset class's account isn't retyped
            self.assertNotIn(f"5100 - Depreciation on Computers - {self.abbr}", depreciation["choices"])


PROJECTS = "Project ID,Project,Stage,Company\n"


@unittest.skipUnless(HAS_ERPNEXT, "needs ERPNext's Project")
class TestProjectFileFollowups(ImportRunCase):
    def setUp(self):
        super().setUp()
        self.company = frappe.get_all("Company", pluck="name", limit=1)[0]

    def _started(self):
        c, t = self.company, self.tag
        content = PROJECTS + f"P1{t},Kolar {t},Finished,{c}\nP1{t}_01,Kolar {t},In process,{c}\n"
        started = self._run(
            "start_import_session", {"file_url": self._file("p.csv", content.encode()).file_url}
        )
        self.assertTrue(started["success"], started)
        return started["result"]["session_id"]

    def _map(self, session, mapping, **extra):
        return self._run(
            "set_column_mapping", {"session": session, "doctype": "Project", "mapping": mapping, **extra}
        )

    def test_the_project_id_is_the_id_and_the_old_id_both(self):
        mapping = {"Project ID": "name", "Project": "project_name", "Stage": "status", "Company": "company"}
        for given in (mapping, {k: v for k, v in mapping.items() if k != "Project ID"}):
            with self.subTest(mapped=list(given)):
                mapped = self._map(
                    self._started(), given, source_key_column="Project ID", source_system="legacy"
                )
                self.assertTrue(mapped["success"], mapped)

    def test_fixes_sent_again_are_said_saved_not_refused(self):
        session = self._started()
        self.assertTrue(
            self._map(
                session,
                {"Project ID": "name", "Project": "project_name", "Stage": "status", "Company": "company"},
            )["success"]
        )
        card = self._run("dry_run_import", {"session": session})["result"]["card"]
        fixes = [
            f
            for q in card["questions"]
            if q["id"].startswith("option:")
            for o in q["options"]
            if o.get("recommended")
            for f in o.get("fixes", [])
        ]
        self.assertTrue(fixes, card)

        first = self._run("dry_run_import", {"session": session, "fixes": fixes})
        self.assertTrue(first["success"], first)
        again = self._run("dry_run_import", {"session": session, "fixes": fixes})
        self.assertTrue(again["success"], again)

    def test_planned_masters_with_session_is_told_import_session(self):
        sent = self._run("create_document", {"session": "IMP-1", "planned_masters": {"count": 1}})
        self.assertFalse(sent["success"])
        error = sent.get("error") or sent["result"]["error"]
        self.assertIn("not session", error)


@unittest.skipUnless(HAS_ERPNEXT, "needs ERPNext's Project and Department")
class TestProjectFileOnTheEconomyModel(ImportRunCase):
    """Live, 2026-11-20 (IMP-2026-00094): "Legal entity" left out, so the import had no company; the mapping
    and the check sent at once; an empty masters_plan read as nothing to create."""

    def setUp(self):
        super().setUp()
        self.company = frappe.get_all("Company", pluck="name", limit=1)[0]

    def _session(self):
        t = self.tag
        content = (
            "Project ID,Project,Legal entity,Department\n"
            f"P1{t},Kolar {t},samb,D{t[:4].upper()}\nP2{t},Hosur {t},samb,D{t[:4].upper()}\n"
        )
        started = self._run(
            "start_import_session", {"file_url": self._file("p.csv", content.encode()).file_url}
        )
        return started["result"]["session_id"]

    def test_a_legal_entity_column_left_out_is_mapped_to_company(self):
        for mapping in (
            {"Project": "project_name", "Department": "department"},
            {"Project": "project_name", "Department": "department", "Legal entity": "Don't Import"},
        ):
            with self.subTest(mapping=mapping):
                mapped = self._run(
                    "set_column_mapping",
                    {"session": self._session(), "doctype": "Project", "mapping": mapping},
                )
                self.assertTrue(mapped["success"], mapped)
                fields = str(mapped["result"]["mapping"])
                self.assertIn("'company'", fields.replace('"', "'"))
                self.assertNotIn("Company", [m["label"] for m in mapped["result"]["missing_required"]])

    def test_a_check_cut_short_says_what_to_create_instead_of_an_empty_list(self):
        session = self._session()
        self._run(
            "set_column_mapping",
            {
                "session": session,
                "doctype": "Project",
                "mapping": {"Project": "project_name", "Department": "department"},
            },
        )
        with patch.object(import_fixes, "REPLY_BUDGET", 10):
            checked = self._run("dry_run_import", {"session": session})["result"]

        self.assertNotIn("masters_plan", checked)
        self.assertIn("planned_masters", checked["masters_plan_left_out"])

    def test_a_check_that_meets_a_mapping_being_saved_says_call_again_alone(self):
        from frappe_assistant_core.plugins.migration.tools.dry_run_import import SENT_TOGETHER

        session = self._session()
        self._run(
            "set_column_mapping",
            {"session": session, "doctype": "Project", "mapping": {"Project": "project_name"}},
        )
        with patch.object(import_fixes, "check", side_effect=frappe.TimestampMismatchError("changed")):
            checked = self._run("dry_run_import", {"session": session})

        self.assertFalse(checked["success"])
        self.assertIn("again now, alone", checked.get("error") or checked["result"]["error"])
        self.assertTrue(SENT_TOGETHER)


@unittest.skipUnless(HAS_ERPNEXT, "needs ERPNext's Account")
class TestChartCheckBeforeMapping(ChartCase):
    """Live, 2026-11-20: the chart check called before any mapping was refused again and again, and its
    questions were written out in a long message instead of a card."""

    def test_an_unmapped_chart_is_mapped_by_its_headings_and_checked(self):
        content = (
            # the live file's headings (ERPNext's Chart of Accounts Importer layout)
            "Account Name,Parent Account,Account Number,Parent Account Number,Is Group,Account Type,Root Type,Currency\n"
            "Client Assets,,,,1,,Asset,INR\nClient Bank,Client Assets,1010,,0,Bank,Asset,INR\n"
        )
        started = self._run(
            "start_import_session", {"file_url": self._file("coa.csv", content.encode()).file_url}
        )
        self.assertIn("session_id", started["result"], started)
        session = started["result"]["session_id"]

        checked = self._check(session, company=self.company)

        self.assertEqual(checked["accounts"], 2)
        self.assertIn("parent_account", str(checked["mapped_by_headings"]))
        self.assertEqual(list(checked)[:2], ["next", "headline"])
        self.assertIn("ONE ask_user card", checked["next"])

    def test_a_file_that_isnt_a_chart_is_still_refused(self):
        content = "Customer,City\nAcme,Pune\n"
        started = self._run(
            "start_import_session", {"file_url": self._file("c.csv", content.encode()).file_url}
        )
        checked = self._run(
            "dry_run_import", {"session": started["result"]["session_id"], "chart": {"company": self.company}}
        )
        self.assertFalse(checked["success"])
