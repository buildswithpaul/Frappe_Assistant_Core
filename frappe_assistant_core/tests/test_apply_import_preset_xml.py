"""
start_import_session on a Tally XML export (#34001): listing its parts (AC1), and opening one
import session per target for the parts the user chooses, with the Tally presets (AC2).
"""

from unittest.mock import patch

import frappe
from frappe.core.doctype.file.file import File

from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.tests.test_apply_import_preset import (
    assert_gstin_and_email_follow_the_site,
    mapped_columns,
)
from frappe_assistant_core.tests.test_import_tally_xml import (
    GSTIN_NEW,
    VOUCHER,
    XmlCase,
    export,
    group,
    ledger,
    stock_item,
)
from frappe_assistant_core.utils import import_presets as presets
from frappe_assistant_core.utils import import_tally_xml as tally_xml

MASTERS = (
    group("Sundry Debtors"),
    group("Sundry Creditors"),
    ledger(
        "Ravi Traders {tag}",
        "Sundry Debtors",
        EMAIL="ravi@example.com",
        OPENINGBALANCE="-1000.00",
        **{"LEDGSTREGDETAILS.LIST": GSTIN_NEW},
    ),
    ledger("Mehta Supplies {tag}", "Sundry Creditors", OPENINGBALANCE="500.00"),
    ledger("HDFC Bank {tag}", "Bank Accounts"),
    stock_item("Steel Rod {tag}", "Raw Material", OPENINGBALANCE="10 Nos", OPENINGRATE="100.00/Nos"),
    VOUCHER,
)


class TallyXmlToolCase(XmlCase):
    def setUp(self):
        super().setUp()
        self.registry = get_tool_registry()
        presets.clear_cache()

    def tearDown(self):
        presets.clear_cache()
        super().tearDown()

    def _file(self, *records):
        records = records or MASTERS
        return self._upload(export(*[r.replace("{tag}", self.tag) for r in records]))

    def _run(self, arguments):
        return self.registry.get_tool("start_import_session")._safe_execute(arguments)

    def _ok(self, arguments):
        reply = self._run(arguments)
        self.assertTrue(reply["success"], reply)
        return reply["result"]

    def _counts(self):
        return frappe.db.count("FAC Import Session"), frappe.db.count("File")


class TestListing(TallyXmlToolCase):
    def test_opening_parts_reads_the_file_once(self):
        # #34438: the survey and each part's sheet parsed the file again, in the same request
        with patch.object(tally_xml, "_walk", wraps=tally_xml._walk) as walk:
            self._ok({"file_id": self._file().name, "parts": ["ledgers", "stock_items"]})

        self.assertEqual(walk.call_count, 1)

    def test_parts_are_listed_with_counts_and_nothing_is_written(self):
        doc = self._file()
        before = self._counts()
        result = self._ok({"file_id": doc.name})
        self.assertEqual(self._counts(), before)
        self.assertEqual(result["kind"], "tally_xml")
        self.assertEqual(result["source"]["company"], "Acme Traders")
        parts = {p["part"]: p for p in result["parts"]}
        self.assertEqual(parts["ledgers"]["count"], 3)
        self.assertTrue(parts["ledgers"]["importable"])
        self.assertEqual(parts["ledgers"]["preset"], "tally_prime.ledgers")
        self.assertEqual(parts["ledgers"]["by_parent"]["Sundry Debtors"], 1)
        self.assertEqual(parts["stock_items"]["count"], 1)
        self.assertEqual(parts["groups"]["count"], 2)
        self.assertFalse(parts["groups"]["importable"])
        self.assertIn("not imported", parts["groups"]["note"])
        self.assertIn("Sundry Debtors become Customers", parts["groups"]["note"])
        self.assertIn("not checked against a real TallyPrime export", result["warnings"][0])
        self.assertEqual(result["other_records"], {"VOUCHER": 1})
        self.assertIn("3 ledgers", result["message"])

    def test_a_utf16_export_is_read_as_frappe_v16_reads_a_file_from_disk(self):
        # Frappe v16's File.get_content() decodes a file read from disk with the first encoding
        # that doesn't fail, and UTF-16 bytes pass as windows-1250 with their BOM lost. This
        # stand-in does what v16's does (frappe/core/doctype/file/file.py), so v15 runs that path.
        def v16_get_content(file_doc, encodings=None):
            file_doc.validate_file_url()
            with open(file_doc.get_full_path(), "rb") as f:
                content = f.read()
            for encoding in (
                ("utf-8-sig", "utf-8", "windows-1250", "windows-1252") if encodings is None else encodings
            ):
                try:
                    return content.decode(encoding)
                except UnicodeDecodeError:
                    continue
            return content

        doc = self._file()
        with patch.object(File, "get_content", v16_get_content):
            result = self._ok({"file_id": doc.name})
        self.assertEqual(result.get("kind"), "tally_xml", result)
        self.assertEqual({p["part"]: p["count"] for p in result["parts"]}["ledgers"], 3)

    def test_the_count_tables_are_capped(self):
        parents = [ledger(f"L{i}", f"Parent {i:03d}") for i in range(120)]
        tags = [f"<TALLYMESSAGE><TAG{i:03d}/></TALLYMESSAGE>" for i in range(120)]
        result = self._ok({"file_id": self._file(*parents, *tags).name})
        by_parent = result["parts"][0]["by_parent"]
        self.assertEqual(len(by_parent), 51)
        self.assertEqual(by_parent["(70 more)"], 70)
        self.assertEqual(len(result["other_records"]), 51)
        self.assertEqual(result["other_records"]["(70 more)"], 70)

    def test_a_blank_parent_shows_as_none(self):
        result = self._ok({"file_id": self._file(ledger("A {tag}", "")).name})
        self.assertEqual(result["parts"][0]["by_parent"], {"(none)": 1})

    def test_a_part_with_no_records_is_left_out(self):
        result = self._ok({"file_id": self._file(ledger("A {tag}", "Sundry Debtors")).name})
        self.assertEqual([p["part"] for p in result["parts"]], ["ledgers"])


class TestImport(TallyXmlToolCase):
    def test_ledgers_open_customers_and_suppliers_and_ask_for_the_company(self):
        doc = self._file()
        result = self._ok({"file_id": doc.name, "parts": ["ledgers"]})
        self.assertEqual(result["kind"], "tally_xml")
        (ledgers,) = result["results"]
        self.assertEqual(ledgers["part"], "ledgers")
        self.assertEqual(ledgers["preset"]["id"], "tally_prime.ledgers")
        by_target = {s["target"]: s for s in ledgers["sessions"]}
        self.assertEqual(set(by_target), {"Customers", "Suppliers"})
        self.assertEqual(ledgers["needs"][0]["name"], "company")
        customers = by_target["Customers"]
        mapped = mapped_columns(customers["mapping"])
        self.assertEqual(mapped["Name"], "customer_name")
        assert_gstin_and_email_follow_the_site(self, mapped, ledgers)
        session = frappe.get_doc("FAC Import Session", customers["session_id"])
        self.assertEqual(session.status, "Mapped")
        self.assertIn("ledgers (Tally XML)", session.steps[0].message)
        self.assertTrue(session.file_name.startswith(f"Master-{self.tag} - Customers"))

    def test_each_part_carries_its_warning_and_source(self):
        result = self._ok({"file_id": self._file().name, "parts": ["ledgers", "stock_items"]})
        for part in result["results"]:
            self.assertEqual(len(part["warnings"]), 1, part["part"])
            self.assertIn("not checked against a real Tally Prime export", part["warnings"][0])
            self.assertEqual(part["source"]["sheet"], f"{part['part']} (Tally XML)")
            self.assertEqual(part["source"]["header_row"], 1)

    def test_ledgers_are_routed_by_their_group(self):
        result = self._ok({"file_id": self._file().name, "parts": ["ledgers"]})
        by_target = {s["target"]: s for s in result["results"][0]["sessions"]}
        self.assertEqual([r[0] for r in by_target["Customers"]["sample_rows"]], [f"Ravi Traders {self.tag}"])
        self.assertEqual(
            [r[0] for r in by_target["Suppliers"]["sample_rows"]], [f"Mehta Supplies {self.tag}"]
        )

    def test_a_part_with_no_data_rows_left_is_an_error_and_the_others_still_open(self):
        real = presets.clean

        def clean(sheet, match):
            cleaned = real(sheet, match)
            if sheet.rows[0][1] == "Parent":
                for target in cleaned.targets:
                    target.rows = []
            return cleaned

        with patch.object(presets, "clean", side_effect=clean):
            result = self._ok({"file_id": self._file().name, "parts": ["ledgers", "stock_items"]})
        by_part = {r["part"]: r for r in result["results"]}
        self.assertEqual(by_part["ledgers"]["error"], "No data rows were left in the Tally ledgers.")
        self.assertNotIn("sessions", by_part["ledgers"])
        self.assertEqual(len(by_part["stock_items"]["sessions"]), 1)
        self.assertIn("1 import session(s) from 1 of 2 part(s)", result["message"])

    def test_a_second_call_opens_only_accounts(self):
        doc = self._file()
        self._ok({"file_id": doc.name, "parts": ["ledgers"]})
        before = frappe.db.count("FAC Import Session")
        company = frappe.get_all("Company", pluck="name", limit=1)[0]
        result = self._ok(
            {
                "file_id": doc.name,
                "parts": ["ledgers"],
                "values": {"company": company},
                "targets": ["Accounts"],
            }
        )
        self.assertEqual([s["target"] for s in result["results"][0]["sessions"]], ["Accounts"])
        self.assertEqual(frappe.db.count("FAC Import Session"), before + 1)

    def test_stock_items_open_items(self):
        result = self._ok({"file_id": self._file().name, "parts": ["stock_items"]})
        (items,) = result["results"]
        self.assertEqual(items["preset"]["id"], "tally_prime.stock_items")
        (session,) = items["sessions"]
        self.assertEqual(session["doctype"], "Item")
        mapped = {row["column"]: row["field"] for row in session["mapping"]["mapping"]}
        self.assertEqual(mapped["Units"], "stock_uom")
        self.assertEqual(mapped["Group"], "item_group")

    def test_both_parts_in_one_call(self):
        result = self._ok({"file_id": self._file().name, "parts": ["ledgers", "stock_items"]})
        self.assertEqual([r["part"] for r in result["results"]], ["ledgers", "stock_items"])
        self.assertIn("3 import session(s) from 2 of 2 part(s)", result["message"])

    def test_empty_targets_mean_all_targets(self):
        doc = self._file()
        every = self._ok({"file_id": doc.name, "parts": ["ledgers"]})
        empty = self._ok({"file_id": doc.name, "parts": ["ledgers"], "targets": []})

        def names(reply):
            return sorted(s["target"] for s in reply["results"][0]["sessions"])

        self.assertEqual(names(empty), names(every))
        self.assertTrue(names(empty))

    def test_duplicate_parts_open_once(self):
        result = self._ok({"file_id": self._file().name, "parts": ["ledgers", "ledgers"]})
        self.assertEqual([r["part"] for r in result["results"]], ["ledgers"])
        self.assertEqual(len(result["results"][0]["sessions"]), 2)

    def test_a_part_no_preset_matches_is_an_error_and_the_others_still_open(self):
        real = presets.match_sheet

        def match(rows, available):
            return [] if rows[0][1] == "Parent" else real(rows, available)

        with patch.object(presets, "match_sheet", side_effect=match), patch("frappe.log_error") as logged:
            result = self._ok({"file_id": self._file().name, "parts": ["ledgers", "stock_items"]})
        by_part = {r["part"]: r for r in result["results"]}
        self.assertIn("could not be read; please report it", by_part["ledgers"]["error"])
        self.assertTrue(logged.called)
        self.assertEqual(len(by_part["stock_items"]["sessions"]), 1)
        self.assertIn("1 import session(s) from 1 of 2 part(s)", result["message"])

    def test_a_part_over_the_row_limit_is_an_error(self):
        records = [ledger(f"L{i} {{tag}}", "Sundry Debtors") for i in range(6)]
        doc = self._file(*records)
        with patch.object(tally_xml, "MAX_PRESET_ROWS", 5):
            result = self._ok({"file_id": doc.name, "parts": ["ledgers"]})
        self.assertIn("more than 5 ledgers", result["results"][0]["error"])

    def test_targets_for_one_part_skip_the_other(self):
        doc = self._file()
        before = self._counts()
        result = self._ok({"file_id": doc.name, "parts": ["ledgers", "stock_items"], "targets": ["Items"]})
        by_part = {r["part"]: r for r in result["results"]}
        self.assertIn("skipped", by_part["ledgers"])
        self.assertEqual([s["target"] for s in by_part["stock_items"]["sessions"]], ["Items"])
        # Only the Items session (and its cleaned file) is new; nothing for the skipped ledgers.
        self.assertEqual(frappe.db.count("FAC Import Session"), before[0] + 1)
        self.assertEqual(frappe.db.count("File"), before[1] + 1)

    def test_the_dry_run_accepts_a_customers_session(self):
        result = self._ok({"file_id": self._file().name, "parts": ["ledgers"]})
        customers = next(s for s in result["results"][0]["sessions"] if s["target"] == "Customers")
        reply = self.registry.get_tool("dry_run_import")._safe_execute({"session": customers["session_id"]})
        self.assertTrue(reply["success"], reply)
        self.assertEqual(reply["result"]["total_rows"], 1)


class TestRefusals(TallyXmlToolCase):
    def _refused(self, arguments, text):
        before = self._counts()
        reply = self._run(arguments)
        self.assertFalse(reply["success"], reply)
        self.assertIn(text, reply["error"])
        self.assertEqual(self._counts(), before)

    def test_a_non_tally_xml_is_refused_and_writes_nothing(self):
        doc = self._upload(b"<customers><customer><name>A</name></customer></customers>")
        self._refused({"file_id": doc.name}, "not a Tally export")

    def test_an_xml_over_50_mb_is_refused_and_writes_nothing(self):
        doc = self._file()
        frappe.db.set_value("File", doc.name, "file_size", 51 * 1024 * 1024)
        # the site's Max File Size, at most 50 MB (#34413)
        self._refused({"file_id": doc.name}, "The file is larger than")
        self._refused({"file_id": doc.name, "parts": ["ledgers"]}, "The file is larger than")

    def test_an_unreadable_xml_is_refused_and_writes_nothing(self):
        doc = self._upload(b"\x00\x01 not xml at all")
        self._refused({"file_id": doc.name}, "not a Tally export")
        self._refused({"file_id": doc.name, "parts": ["ledgers"]}, "not a Tally export")
        # An empty read (Frappe will not store an empty File, so it is swapped in at read time).
        doc = self._file()
        before = self._counts()
        with patch.object(type(doc), "get_content", return_value=b""):
            reply = self._run({"file_id": doc.name})
        self.assertFalse(reply["success"], reply)
        self.assertIn("Could not read the XML", reply["error"])
        self.assertEqual(self._counts(), before)

    def test_a_truncated_xml_is_read_as_far_as_it_goes_and_writes_nothing(self):
        # recover=True keeps what was well formed, so this is a listing, not a refusal.
        doc = self._upload(b"<ENVELOPE><BODY><IMPORTDATA><REQUESTDATA><TALLYMESSAGE><LEDGER NAME='x'")
        before = self._counts()
        result = self._ok({"file_id": doc.name})
        self.assertEqual(result["parts"][0]["count"], 1)
        self.assertEqual(self._counts(), before)

    def test_vouchers_only_is_refused(self):
        self._refused({"file_id": self._upload(export(VOUCHER)).name}, "no ledgers, groups or stock items")

    def test_bad_parts_are_refused(self):
        doc = self._file(ledger("A {tag}", "Sundry Debtors"), group("Sundry Debtors"))
        self._refused({"file_id": doc.name, "parts": ["groups"]}, "not imported")
        self._refused({"file_id": doc.name, "parts": ["vouchers"]}, "Importable parts")
        self._refused({"file_id": doc.name, "parts": ["stock_items"]}, "no stock items")
        self._refused({"file_id": doc.name, "parts": ["ledgers"], "targets": ["Nope"]}, "No target 'Nope'")

    def test_parts_must_be_a_list(self):
        # The framework's schema check answers a string first; the tool's own guard is called directly.
        doc = self._file(ledger("A {tag}", "Sundry Debtors"))
        before = self._counts()
        reply = self.registry.get_tool("start_import_session").execute(
            {"file_id": doc.name, "parts": "ledgers"}
        )
        self.assertFalse(reply["success"], reply)
        self.assertIn("parts must be a list", reply["error"])
        self.assertEqual(self._counts(), before)

    def test_no_parts_is_refused(self):
        doc = self._file()
        self._refused(
            {"file_id": doc.name, "parts": []},
            "Give at least one part to import: ledgers, stock_items, stock_groups.",
        )

    def test_preset_and_sheet_are_refused_for_xml(self):
        doc = self._file()
        self._refused({"file_id": doc.name, "preset": "tally_prime.ledgers"}, "not used for Tally XML")
        self._refused({"file_id": doc.name, "sheet": "Sheet1"}, "not used for Tally XML")

    def test_parts_on_a_spreadsheet_is_refused(self):
        doc = self._upload(b"Name,Under\nA,Sundry Debtors\n", file_name=f"ledgers-{self.tag}.csv")
        self._refused({"file_id": doc.name, "parts": ["ledgers"]}, "only for Tally XML")

    def test_a_user_who_cannot_read_the_file_gets_the_usual_refusal(self):
        doc = self._file()
        outsider = self.make_desk_user("outsider")
        self.assert_cannot(outsider, "read", "File", doc.name)
        frappe.set_user(outsider)
        reply = self._run({"file_id": doc.name})
        self.assertFalse(reply["success"])
        self.assertIn("File not found, or you don't have access to it.", reply["error"])

    def test_a_csv_still_goes_the_spreadsheet_way(self):
        doc = self._upload(
            b"Name,Under,GSTIN/UIN\nA,Sundry Debtors,29ABCDE1234F1Z5\n", file_name=f"ledgers-{self.tag}.csv"
        )
        result = self._ok({"file_id": doc.name})
        self.assertNotIn("kind", result)
        self.assertEqual(result["preset"]["id"], "tally_prime.ledgers")
