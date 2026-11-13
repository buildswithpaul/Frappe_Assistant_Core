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
Tally exports its masters and vouchers as XML, so an XML export has to reach FACO the
way a spreadsheet does: each record type with its columns, row count and first 10 rows,
never the whole file.

The sample follows a real Tally export: UTF-16 with a BOM, every record wrapped in its
own TALLYMESSAGE, a header that is not data, and "&#4;" before "Primary", which XML 1.0
forbids and a strict parser rejects.

Nothing here touches the database.
"""

import os
import tempfile
from types import SimpleNamespace

from frappe_assistant_core.plugins.data_science.tools.extract_file_content import ExtractFileContent
from frappe_assistant_core.tests.base_test import BaseAssistantTest

LEDGERS = "".join(
    f"""
    <TALLYMESSAGE xmlns:UDF="TallyUDF">
     <LEDGER NAME="Customer {i}" RESERVEDNAME="">
      <ADDRESS.LIST TYPE="String"><ADDRESS>{i} MG Road</ADDRESS><ADDRESS>Bengaluru</ADDRESS></ADDRESS.LIST>
      <PARENT>Sundry Debtors</PARENT>
      <OPENINGBALANCE>-{i}00.00</OPENINGBALANCE>
     </LEDGER>
    </TALLYMESSAGE>"""
    for i in range(12)
)

TALLY_EXPORT = f"""<ENVELOPE>
 <HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
 <BODY>
  <IMPORTDATA>
   <REQUESTDESC>
    <REPORTNAME>All Masters</REPORTNAME>
    <STATICVARIABLES><SVCURRENTCOMPANY>Acme Traders</SVCURRENTCOMPANY></STATICVARIABLES>
   </REQUESTDESC>
   <REQUESTDATA>
    <TALLYMESSAGE xmlns:UDF="TallyUDF">
     <GROUP NAME="Sundry Debtors" RESERVEDNAME="Sundry Debtors">
      <PARENT>&#4; Primary</PARENT>
      <ISBILLWISEON>Yes</ISBILLWISEON>
     </GROUP>
    </TALLYMESSAGE>{LEDGERS}
    <TALLYMESSAGE xmlns:UDF="TallyUDF">
     <VOUCHER VCHTYPE="Sales" ACTION="Create">
      <DATE>20240401</DATE>
      <VOUCHERNUMBER>1</VOUCHERNUMBER>
      <ALLLEDGERENTRIES.LIST><LEDGERNAME>Customer 1</LEDGERNAME><AMOUNT>-1180.00</AMOUNT></ALLLEDGERENTRIES.LIST>
      <ALLLEDGERENTRIES.LIST><LEDGERNAME>Sales</LEDGERNAME><AMOUNT>1180.00</AMOUNT></ALLLEDGERENTRIES.LIST>
     </VOUCHER>
    </TALLYMESSAGE>
   </REQUESTDATA>
  </IMPORTDATA>
 </BODY>
</ENVELOPE>
""".encode("utf-16")


class TestXmlExtraction(BaseAssistantTest):
    def _extract(self, content: bytes) -> dict:
        return ExtractFileContent()._extract_xml_content(content)

    def test_xml_files_are_read_as_xml(self):
        file_doc = SimpleNamespace(file_name="DayBook.xml", file_url="/private/files/DayBook.xml")
        self.assertEqual(ExtractFileContent()._detect_file_type(file_doc), "xml")

    def test_tally_export_lists_each_record_type(self):
        result = self._extract(TALLY_EXPORT)

        self.assertTrue(result["success"], result.get("error"))
        # The header and request description are not data.
        self.assertEqual(list(result["structured_data"]), ["GROUP", "LEDGER", "VOUCHER"])
        ledger = result["structured_data"]["LEDGER"]
        self.assertEqual(
            ledger["columns"], ["NAME", "RESERVEDNAME", "ADDRESS.LIST", "PARENT", "OPENINGBALANCE"]
        )
        self.assertEqual(ledger["row_count"], 12)
        self.assertIn("=== Records: LEDGER ===", result["content"])
        self.assertIn("Rows: 12", result["content"])

    def test_only_ten_sample_rows_reach_the_content(self):
        result = self._extract(TALLY_EXPORT)

        self.assertEqual(len(result["structured_data"]["LEDGER"]["sample_data"]), 10)
        self.assertIn("Customer 9", result["content"])
        self.assertNotIn("Customer 10", result["content"])
        self.assertNotIn("<LEDGER", result["content"])

    def test_tally_control_characters_are_dropped(self):
        group = self._extract(TALLY_EXPORT)["structured_data"]["GROUP"]["sample_data"][0]
        self.assertEqual(group["PARENT"], "Primary")

    def test_nested_lists_become_one_cell(self):
        data = self._extract(TALLY_EXPORT)["structured_data"]

        self.assertEqual(data["LEDGER"]["sample_data"][3]["ADDRESS.LIST"], "3 MG Road; Bengaluru")
        self.assertEqual(
            data["VOUCHER"]["sample_data"][0]["ALLLEDGERENTRIES.LIST"],
            "Customer 1; -1180.00; Sales; 1180.00",
        )

    def test_flat_export(self):
        customers = "".join(
            f'<Customer id="{i}"><Name>Acme {i}</Name><Territory>India</Territory></Customer>'
            for i in range(3)
        )
        result = self._extract(f"<Customers>{customers}</Customers>".encode())

        self.assertTrue(result["success"], result.get("error"))
        self.assertEqual(result["structured_data"]["Customer"]["columns"], ["id", "Name", "Territory"])
        self.assertEqual(result["structured_data"]["Customer"]["row_count"], 3)

    def test_external_entities_are_not_resolved(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as secret:
            secret.write("TOP-SECRET-SERVER-FILE")
        try:
            xxe = (
                f'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x SYSTEM "file://{secret.name}">]>'
                "<r><row><a>&x;</a></row><row><a>2</a></row></r>"
            ).encode()
            result = self._extract(xxe)
        finally:
            os.unlink(secret.name)

        self.assertTrue(result["success"], result.get("error"))
        self.assertNotIn("TOP-SECRET-SERVER-FILE", result["content"])

    def test_non_xml_content_is_reported(self):
        result = self._extract(b"Customer Name,Territory\nAcme,India\n")
        self.assertFalse(result["success"])
