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
UTF-16 exports pass the upload check, so extraction has to read them as UTF-16:
latin-1 accepts any bytes and would hand the model NUL-riddled headers.

Nothing here touches the database.
"""

import unittest

from frappe_assistant_core.plugins.data_science.tools.extract_file_content import ExtractFileContent

CSV = "Customer Name,Territory\r\nMüller GmbH,Zürich\r\nAcme,India\r\n"
BOMS = ((b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be"))


class TestUtf16Extraction(unittest.TestCase):
    def test_utf16_csv_extracts_headers_and_rows(self):
        for bom, codec in BOMS:
            with self.subTest(codec=codec):
                result = ExtractFileContent()._extract_csv_content(bom + CSV.encode(codec))

                self.assertTrue(result["success"], result.get("error"))
                data = result["structured_data"]
                self.assertEqual(data["columns"], ["Customer Name", "Territory"])
                self.assertEqual(data["row_count"], 2)
                self.assertEqual(
                    data["sample_data"],
                    [
                        {"Customer Name": "Müller GmbH", "Territory": "Zürich"},
                        {"Customer Name": "Acme", "Territory": "India"},
                    ],
                )

    def test_utf16_text_decodes(self):
        for bom, codec in BOMS:
            with self.subTest(codec=codec):
                result = ExtractFileContent()._extract_text_content(bom + CSV.encode(codec))

                self.assertTrue(result["success"])
                self.assertEqual(result["content"], CSV)
                self.assertEqual(result["encoding"], "utf-16")
