"""
Tally XML exports (#34001): reading a Tally masters export safely, counting its parts, and
turning ledgers and stock items into rows the #34000 Tally presets match.
"""

import time
from unittest.mock import patch

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils import import_presets as presets
from frappe_assistant_core.utils import import_tally_xml as tally
from frappe_assistant_core.utils.import_session import FileProblem


def ledger(name, parent, named=True, **tags):
    """A LEDGER record in TallyPrime's layout. Pass tag=value for the extra child tags."""
    attribute = f' NAME="{name}" RESERVEDNAME=""' if named else ""
    body = "".join(f"<{tag}>{value}</{tag}>" for tag, value in tags.items() if "." not in tag)
    lists = "".join(value for tag, value in tags.items() if "." in tag)
    return (
        f'<TALLYMESSAGE xmlns:UDF="TallyUDF"><LEDGER{attribute}>'
        f'<LANGUAGENAME.LIST><NAME.LIST TYPE="String"><NAME>{name}</NAME><NAME>{name[:2]}</NAME>'
        f"</NAME.LIST></LANGUAGENAME.LIST><PARENT>{parent}</PARENT>{body}{lists}</LEDGER></TALLYMESSAGE>"
    )


def stock_item(name, parent, units="Nos", **tags):
    body = "".join(f"<{tag}>{value}</{tag}>" for tag, value in tags.items() if "." not in tag)
    lists = "".join(value for tag, value in tags.items() if "." in tag)
    return (
        f'<TALLYMESSAGE xmlns:UDF="TallyUDF"><STOCKITEM NAME="{name}" RESERVEDNAME="">'
        f"<PARENT>{parent}</PARENT><BASEUNITS>{units}</BASEUNITS>{body}{lists}</STOCKITEM></TALLYMESSAGE>"
    )


def group(name, parent="&#4; Primary"):
    return (
        f'<TALLYMESSAGE xmlns:UDF="TallyUDF"><GROUP NAME="{name}" RESERVEDNAME="{name}">'
        f"<PARENT>{parent}</PARENT></GROUP></TALLYMESSAGE>"
    )


VOUCHER = (
    '<TALLYMESSAGE xmlns:UDF="TallyUDF"><VOUCHER VCHTYPE="Sales" ACTION="Create"><DATE>20240401</DATE>'
    "<VOUCHERNUMBER>1</VOUCHERNUMBER></VOUCHER></TALLYMESSAGE>"
)


def export(*records, company="Acme Traders", encoding="utf-16"):
    """A Tally XML export as Tally writes it: UTF-16 with a BOM, company in REQUESTDESC."""
    text = (
        "<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER><BODY><IMPORTDATA>"
        "<REQUESTDESC><REPORTNAME>All Masters</REPORTNAME>"
        f"<STATICVARIABLES><SVCURRENTCOMPANY>{company}</SVCURRENTCOMPANY></STATICVARIABLES></REQUESTDESC>"
        f"<REQUESTDATA>{''.join(records)}</REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>"
    )
    return text.encode(encoding)


GSTIN_NEW = "<LEDGSTREGDETAILS.LIST><GSTIN>29ABCDE1234F1Z5</GSTIN></LEDGSTREGDETAILS.LIST>"
MAILING = (
    "<LEDMAILINGDETAILS.LIST><MAILINGNAME>Ravi Traders Pvt Ltd</MAILINGNAME>"
    "<STATE>Karnataka</STATE></LEDMAILINGDETAILS.LIST>"
)
HSN_NEW = "<HSNDETAILS.LIST><HSNCODE>7214</HSNCODE></HSNDETAILS.LIST>"


class XmlCase(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.tag = frappe.generate_hash(length=6)
        self.track_test_files()

    def tearDown(self):
        frappe.set_user("Administrator")
        self.delete_test_files()
        super().tearDown()

    def _upload(self, content, file_name=None):
        return frappe.get_doc(
            {
                "doctype": "File",
                "file_name": file_name or f"Master-{self.tag}.xml",
                "content": content,
                "is_private": 1,
            }
        ).insert()


class TestSurvey(XmlCase):
    def test_parts_are_counted_with_samples_and_parents(self):
        doc = self._upload(
            export(
                group("Sundry Debtors"),
                group("Sundry Creditors"),
                ledger("Ravi Traders", "Sundry Debtors"),
                ledger("Mehta Supplies", "Sundry Creditors"),
                ledger("HDFC Bank", "Bank Accounts"),
                stock_item("Steel Rod 10mm", "Raw Material"),
                VOUCHER,
            )
        )
        found = tally.survey(doc)
        self.assertEqual(found.company, "Acme Traders")
        self.assertEqual(found.parts["ledgers"].count, 3)
        self.assertEqual(found.parts["ledgers"].sample, ["Ravi Traders", "Mehta Supplies", "HDFC Bank"])
        self.assertEqual(
            dict(found.parts["ledgers"].by_parent),
            {"Sundry Debtors": 1, "Sundry Creditors": 1, "Bank Accounts": 1},
        )
        self.assertEqual(found.parts["groups"].count, 2)
        self.assertEqual(dict(found.parts["groups"].by_parent), {"Primary": 2})  # &#4; dropped
        self.assertEqual(found.parts["stock_items"].count, 1)
        self.assertEqual(found.other_records, {"VOUCHER": 1})

    def test_utf8_and_namespaces_and_company_in_header(self):
        text = export(ledger("A", "Sundry Debtors"), encoding="utf-8").decode("utf-8")
        text = text.replace("<HEADER>", "<HEADER><SVCURRENTCOMPANY>Header Co</SVCURRENTCOMPANY>")
        text = text.replace(
            "<STATICVARIABLES><SVCURRENTCOMPANY>Acme Traders</SVCURRENTCOMPANY></STATICVARIABLES>", ""
        )
        found = tally.survey(self._upload(text.encode("utf-8")))
        self.assertEqual(found.company, "Header Co")
        self.assertEqual(found.parts["ledgers"].count, 1)

    def test_a_large_export_is_streamed_and_samples_stay_capped(self):
        records = [ledger(f"Party {i}", "Sundry Debtors") for i in range(5000)]
        found = tally.survey(self._upload(export(*records)))
        self.assertEqual(found.parts["ledgers"].count, 5000)
        self.assertEqual(len(found.parts["ledgers"].sample), 10)

    def test_a_file_of_too_many_elements_is_refused(self):
        # #34438: a hostile file of other elements would be held in memory whole
        noise = "<NOISE>" + "<X/>" * 50 + "</NOISE>"
        doc = self._upload(export(ledger("A", "Sundry Debtors"), noise))

        with patch.object(tally, "MAX_ELEMENTS", 40), self.assertRaises(FileProblem) as raised:
            tally.survey(doc)

        self.assertIn("more than 40 elements", str(raised.exception))

    def test_elements_outside_the_messages_are_let_go_once_read(self):
        seen = []
        text = export(ledger("A", "Sundry Debtors"), encoding="utf-8")

        for _tag, element in tally._walk(text, []):
            # what came before this message, outside it, is no longer held
            seen.append(len(element.getroottree().getroot().find("HEADER") or []))

        self.assertEqual(seen, [0])

    def test_a_message_nested_in_a_message_still_lets_later_elements_go(self):
        # #34438 (Paul's review of 49da112): a nested TALLYMESSAGE never counted itself out, so
        # every element after it was held in memory to the end of the file
        nested = "<TALLYMESSAGE>" + group("Debtors") + "</TALLYMESSAGE>"
        noise = "<NOISE>" + "<X/>" * 5 + "</NOISE>"
        text = export(nested, noise, ledger("A", "Sundry Debtors"), encoding="utf-8")
        held = []

        for tag, element in tally._walk(text, []):
            if tag == "LEDGER":
                held.append(len(element.getroottree().getroot().find(".//NOISE")))

        self.assertEqual(held, [0])

    def test_a_record_of_too_many_elements_is_refused(self):
        # #34438: a record is held whole until it ends, so one huge record inside a message could
        # fill memory up to MAX_ELEMENTS
        lists = "<NOTES.LIST>" + "<NOTE>x</NOTE>" * 30 + "</NOTES.LIST>"
        doc = self._upload(export(ledger("A", "Sundry Debtors", **{"NOTES.LIST": lists})))

        with patch.object(tally, "MAX_RECORD_ELEMENTS", 20), self.assertRaises(FileProblem) as raised:
            tally.survey(doc)

        self.assertIn("more than 20 elements", str(raised.exception))

    def test_not_a_tally_export_is_refused(self):
        for content in (
            b"<customers><customer><name>A</name></customer></customers>",
            b"<ENVELOPE><BODY></BODY></ENVELOPE>",
        ):
            with self.assertRaises(FileProblem) as raised:
                tally.survey(self._upload(content))
            self.assertEqual(str(raised.exception), tally.NOT_TALLY)

    def test_vouchers_only_is_refused_with_what_it_holds(self):
        with self.assertRaises(FileProblem) as raised:
            tally.survey(self._upload(export(VOUCHER, VOUCHER)))
        self.assertEqual(str(raised.exception), tally.NO_MASTERS.format("VOUCHER 2"))

    def test_the_tags_named_in_the_refusal_are_capped(self):
        records = [f"<TALLYMESSAGE><TAG{i:02d}/></TALLYMESSAGE>" for i in range(12)]
        with self.assertRaises(FileProblem) as raised:
            tally.survey(self._upload(export(*records)))
        message = str(raised.exception)
        self.assertIn("TAG09 1", message)
        self.assertNotIn("TAG10", message)
        self.assertIn("and 2 more", message)

    def test_external_entities_are_not_read(self):
        content = (
            b'<?xml version="1.0"?><!DOCTYPE ENVELOPE [<!ENTITY secret SYSTEM "file:///etc/passwd">]>'
            b"<ENVELOPE><BODY><IMPORTDATA><REQUESTDATA><TALLYMESSAGE>"
            b'<LEDGER NAME="X"><PARENT>&secret;</PARENT></LEDGER>'
            b"</TALLYMESSAGE></REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>"
        )
        found = tally.survey(self._upload(content))
        self.assertNotIn("root:", "".join(found.parts["ledgers"].by_parent))

    def test_wrong_extension_and_size_are_refused(self):
        doc = self._upload(export(ledger("A", "Sundry Debtors")), file_name=f"Master-{self.tag}.txt")
        with self.assertRaises(FileProblem):
            tally.survey(doc)
        doc = self._upload(export(ledger("A", "Sundry Debtors")))
        frappe.db.set_value("File", doc.name, "file_size", 51 * 1024 * 1024)
        with self.assertRaises(FileProblem) as raised:
            tally.survey(frappe.get_doc("File", doc.name))
        self.assertIn("larger than", str(raised.exception))  # the site's Max File Size (#34413)

    def test_empty_bom_only_and_garbage_files_are_refused(self):
        doc = self._upload(export(ledger("A", "Sundry Debtors")))
        # Frappe will not store an empty File, so the content is swapped in at read time.
        no_element = "Could not read the XML: no element found (line 0)"
        for label, content, message in (
            ("empty", b"", no_element),
            ("bom only", b"\xff\xfe", tally.NOT_TALLY),
            ("garbage", b"\x00\x01 not xml", tally.NOT_TALLY),
        ):
            with self.subTest(label):
                with patch.object(type(doc), "get_content", return_value=content):
                    with self.assertRaises(FileProblem) as raised:
                        tally.survey(doc)
                self.assertEqual(str(raised.exception), message)

    def test_billion_laughs_is_not_expanded(self):
        entities = '<!ENTITY a0 "lol">' + "".join(
            f'<!ENTITY a{i} "{f"&a{i - 1};" * 10}">' for i in range(1, 6)
        )
        content = (
            f'<?xml version="1.0"?><!DOCTYPE ENVELOPE [{entities}]>'
            "<ENVELOPE><BODY><IMPORTDATA><REQUESTDATA><TALLYMESSAGE>"
            '<LEDGER NAME="X"><PARENT>&a5;</PARENT></LEDGER>'
            "</TALLYMESSAGE></REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>"
        ).encode()
        started = time.monotonic()
        doc = self._upload(content)
        try:
            found = tally.survey(doc)
        except FileProblem:
            # libxml2 may stop at the amplified entity; that refusal is as safe as not expanding it.
            pass
        else:
            parent = "".join(found.parts["ledgers"].by_parent)
            self.assertLess(len(parent), 100)
            self.assertNotIn("lollol", parent)
        self.assertLess(time.monotonic() - started, 5)

    def test_text_drops_control_characters_and_spaces_out_whitespace(self):
        self.assertEqual(tally._text("Pri\x04mary"), "Primary")
        self.assertEqual(tally._text("\x04 Primary"), "Primary")
        self.assertEqual(tally._text("Ravi\nTraders\t\r\nPvt"), "Ravi Traders Pvt")

    def test_text_drops_del_and_the_c1_range(self):
        self.assertEqual(tally._text("Pri\x7fmary"), "Primary")
        self.assertEqual(tally._text("Pri\x85mary"), "Primary")  # U+0085 (NEL)
        self.assertEqual(tally._text("Pri\x80\x9fmary"), "Primary")

    def test_the_name_attribute_is_preferred_in_the_survey_sample(self):
        record = ledger("Ravi Traders", "Sundry Debtors").replace(
            "<NAME>Ravi Traders</NAME>", "<NAME>RT Old Name</NAME>"
        )
        found = tally.survey(self._upload(export(record)))
        self.assertEqual(found.parts["ledgers"].sample, ["Ravi Traders"])

    def test_an_external_dtd_is_not_loaded(self):
        # The DTD is never loaded: the document is read as if it had none, and nothing from the
        # file the DTD points at reaches the result.
        content = (
            b'<?xml version="1.0"?><!DOCTYPE ENVELOPE SYSTEM "file:///etc/passwd">'
            b"<ENVELOPE><BODY><IMPORTDATA><REQUESTDATA><TALLYMESSAGE>"
            b'<LEDGER NAME="X"><PARENT>Sundry Debtors</PARENT></LEDGER>'
            b"</TALLYMESSAGE></REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>"
        )
        found = tally.survey(self._upload(content))
        self.assertEqual(found.parts["ledgers"].count, 1)
        self.assertEqual(found.parts["ledgers"].sample, ["X"])
        self.assertEqual(dict(found.parts["ledgers"].by_parent), {"Sundry Debtors": 1})

    def test_control_character_reference_in_a_record_is_dropped(self):
        found = tally.survey(self._upload(export(group("Debtors", parent="Pri&#4;mary"))))
        self.assertEqual(dict(found.parts["groups"].by_parent), {"Primary": 1})


class TestPartSheet(XmlCase):
    def test_ledger_columns_from_every_candidate(self):
        doc = self._upload(
            export(
                ledger(
                    "Ravi Traders",
                    "Sundry Debtors",
                    EMAIL="ravi@example.com",
                    LEDGERMOBILE="9876543210",
                    INCOMETAXNUMBER="ABCDE1234F",
                    OPENINGBALANCE="-1000.00",
                    **{"LEDGSTREGDETAILS.LIST": GSTIN_NEW, "LEDMAILINGDETAILS.LIST": MAILING},
                ),
                ledger(
                    "Mehta Supplies",
                    "Sundry Creditors",
                    PARTYGSTIN="27PQRSX5678L1Z2",
                    LEDGERPHONE="022-1234",
                    LEDSTATENAME="Maharashtra",
                    OPENINGBALANCE="500.00",
                ),
                ledger("No Attr Co", "Sundry Debtors", named=False, OPENINGBALANCE="n/a"),
            )
        )
        sheet = tally.part_sheet(doc, "ledgers")
        self.assertEqual(sheet.name, "ledgers (Tally XML)")
        self.assertEqual(
            sheet.rows[0],
            [
                "Name",
                "Parent",
                "GSTIN/UIN",
                "E-mail",
                "Ledger Mobile",
                "PAN",
                "State",
                "Mailing Name",
                "Opening Balance",
            ],
        )
        self.assertEqual(
            sheet.rows[1],
            [
                "Ravi Traders",
                "Sundry Debtors",
                "29ABCDE1234F1Z5",
                "ravi@example.com",
                "9876543210",
                "ABCDE1234F",
                "Karnataka",
                "Ravi Traders Pvt Ltd",
                "1000",
            ],
        )
        self.assertEqual(sheet.rows[2][2], "27PQRSX5678L1Z2")
        self.assertEqual(sheet.rows[2][4], "022-1234")
        self.assertEqual(sheet.rows[2][6], "Maharashtra")
        self.assertEqual(sheet.rows[2][8], "-500")  # a credit in Tally XML is positive
        self.assertEqual(sheet.rows[3][0], "No Attr Co")  # from LANGUAGENAME.LIST
        self.assertEqual(sheet.rows[3][8], "n/a")  # not a number: kept as written

    def test_stock_item_columns(self):
        doc = self._upload(
            export(
                stock_item(
                    "Steel Rod 10mm",
                    "Raw Material",
                    DESCRIPTION="10mm TMT",
                    CATEGORY="Steel",
                    OPENINGBALANCE=" 10 Nos",
                    OPENINGRATE="100.00/Nos",
                    **{"HSNDETAILS.LIST": HSN_NEW},
                ),
                stock_item(
                    "Paint 1L",
                    "Finished Goods",
                    units="Ltr",
                    **{"GSTDETAILS.LIST": "<GSTDETAILS.LIST><HSNCODE>3208</HSNCODE></GSTDETAILS.LIST>"},
                ),
            )
        )
        sheet = tally.part_sheet(doc, "stock_items")
        self.assertEqual(
            sheet.rows[0],
            [
                "Name",
                "Stock Group",
                "Base Units",
                "HSN Code",
                "Description",
                "Category",
                "Opening Quantity",
                "Opening Rate",
            ],
        )
        self.assertEqual(
            sheet.rows[1],
            ["Steel Rod 10mm", "Raw Material", "Nos", "7214", "10mm TMT", "Steel", "10 Nos", "100.00/Nos"],
        )
        self.assertEqual(sheet.rows[2][3], "3208")

    def test_the_name_attribute_is_preferred_to_the_language_list(self):
        record = ledger("Ravi Traders", "Sundry Debtors").replace(
            "<NAME>Ravi Traders</NAME>", "<NAME>RT Old Name</NAME>"
        )
        sheet = tally.part_sheet(self._upload(export(record)), "ledgers")
        self.assertEqual(sheet.rows[1][0], "Ravi Traders")

    def test_a_namespaced_element_is_read_by_its_local_name(self):
        record = ledger("Ravi Traders", "Sundry Debtors", **{"UDF:GSTIN": "29ABCDE1234F1Z5"})
        self.assertIn("<UDF:GSTIN>29ABCDE1234F1Z5</UDF:GSTIN>", record)
        sheet = tally.part_sheet(self._upload(export(record)), "ledgers")
        self.assertEqual(sheet.rows[1][2], "29ABCDE1234F1Z5")

    def test_each_fallback_candidate_lands_in_its_column(self):
        mailing = "<MAILINGNAME.LIST><MAILINGNAME>Ravi Traders Pvt Ltd</MAILINGNAME></MAILINGNAME.LIST>"
        doc = self._upload(
            export(
                ledger("Plain GSTIN", "Sundry Debtors", GSTIN="29ABCDE1234F1Z5"),
                ledger("Plain State", "Sundry Debtors", STATENAME="Kerala"),
                ledger("List Mailing", "Sundry Debtors", **{"MAILINGNAME.LIST": mailing}),
                stock_item("Plain HSN", "Raw Material", HSNCODE="7214"),
            )
        )
        rows = tally.part_sheet(doc, "ledgers").rows
        self.assertEqual(rows[1][2], "29ABCDE1234F1Z5")
        self.assertEqual(rows[2][6], "Kerala")
        self.assertEqual(rows[3][7], "Ravi Traders Pvt Ltd")
        self.assertEqual(tally.part_sheet(doc, "stock_items").rows[1][3], "7214")

    def test_the_tally_presets_match_the_sheets(self):
        presets.clear_cache()
        by_id = {p["id"]: p for p in presets.load_presets()}
        doc = self._upload(export(ledger("A", "Sundry Debtors"), stock_item("B", "Raw Material")))
        for part, preset_id in tally.IMPORTABLE.items():
            sheet = tally.part_sheet(doc, part)
            found = presets.match_sheet(sheet.rows, [by_id[preset_id]])
            self.assertEqual(len(found), 1, part)
            self.assertEqual(found[0].header_row, 0, part)

    def test_a_part_over_the_row_limit_is_refused(self):
        doc = self._upload(export(*[ledger(f"P{i}", "Sundry Debtors") for i in range(6)]))
        with patch.object(tally, "MAX_PRESET_ROWS", 5), self.assertRaises(FileProblem) as raised:
            tally.part_sheet(doc, "ledgers")
        self.assertIn("more than 5", str(raised.exception))

    def test_exactly_the_row_limit_in_records_is_allowed(self):
        with patch.object(tally, "MAX_PRESET_ROWS", 5):
            doc = self._upload(export(*[ledger(f"P{i}", "Sundry Debtors") for i in range(5)]))
            self.assertEqual(len(tally.part_sheet(doc, "ledgers").rows), 6)  # header + 5 records
            doc = self._upload(export(*[ledger(f"P{i}", "Sundry Debtors") for i in range(6)]))
            with self.assertRaises(FileProblem):
                tally.part_sheet(doc, "ledgers")

    def test_hostile_opening_balances_are_kept_as_written(self):
        values = ["1E999999999", "-1E999999999", "NaN", "Infinity", "-Infinity", "1E31"]
        doc = self._upload(
            export(*[ledger(f"P{i}", "Sundry Debtors", OPENINGBALANCE=v) for i, v in enumerate(values)])
        )
        started = time.monotonic()
        sheet = tally.part_sheet(doc, "ledgers")
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual([row[8] for row in sheet.rows[1:]], values)


class TestPartsProblem(XmlCase):
    def test_each_bad_request_is_named(self):
        found = tally.survey(self._upload(export(ledger("A", "Sundry Debtors"), group("Sundry Debtors"))))
        self.assertIsNone(tally.parts_problem(["ledgers"], found))
        self.assertIn("at least one", tally.parts_problem([], found))
        self.assertIn("not imported", tally.parts_problem(["groups"], found))
        self.assertIn("ledgers, stock_items", tally.parts_problem(["vouchers"], found))
        self.assertEqual(tally.parts_problem(["stock_items"], found), "This export has no stock items.")


class TestTallyGroups(XmlCase):
    """A ledger's group under Sundry Debtors/Creditors makes it a party (#34000)."""

    def _targets(self, doc, part):
        presets.clear_cache()
        preset = {p["id"]: p for p in presets.load_presets()}[tally.IMPORTABLE[part]]
        sheet = tally.part_sheet(doc, part)
        cleaned = presets.clean(sheet, presets.match_sheet(sheet.rows, [preset])[0])
        return {t.target["name"]: t.rows for t in cleaned.targets}

    def test_a_ledger_in_a_group_under_sundry_debtors_or_creditors_is_a_party(self):
        doc = self._upload(
            export(
                ledger("Ravi Traders", "Local Debtors"),  # listed before its group, as an export may
                ledger("Kumar Stores", "Bangalore Debtors"),  # two levels down
                ledger("Mehta Supplies", "Local Creditors"),
                ledger("HDFC Bank", "Bank Accounts"),
                group("Local Debtors", "Sundry Debtors"),
                group("Bangalore Debtors", "Local Debtors"),
                group("Local Creditors", "Sundry Creditors"),
                group("Bank Accounts"),
            )
        )

        targets = self._targets(doc, "ledgers")

        self.assertEqual([row[0] for row in targets["Customers"]], ["Ravi Traders", "Kumar Stores"])
        self.assertEqual([row[0] for row in targets["Suppliers"]], ["Mehta Supplies"])
        self.assertEqual([row[0] for row in targets["Accounts"]], ["HDFC Bank"])

    def test_groups_that_loop_end_without_a_party(self):
        doc = self._upload(
            export(ledger("Odd", "Loop A"), group("Loop A", "Loop B"), group("Loop B", "Loop A"))
        )

        self.assertEqual(tally.part_sheet(doc, "ledgers").rows[1][1], "Loop A")
