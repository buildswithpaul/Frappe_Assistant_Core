# Frappe Assistant Core - chat upload magic-byte tests
# Copyright (C) 2025 Paul Clinton
#
# AGPL-3.0 License

"""Spreadsheet uploads are only as safe as the content check behind the
extension. A renamed .exe, image or archive must not get through as .xlsx/.xls,
and every OOXML file starts with the same zip header, so .xlsx has to be told
apart from a plain .zip or a .docx by its workbook part. Text formats have no
signature, so a NUL byte is what gives a renamed binary away.
"""

import base64
import io
import unittest
import zipfile
from unittest.mock import patch

import frappe
import openpyxl

from frappe_assistant_core.chat.api.settings.uploads import _magic_bytes_match, upload_message_file
from frappe_assistant_core.tests.base_test import BaseAssistantTest

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
XLS_MIME = "application/vnd.ms-excel"

# Compound File Binary signature every BIFF .xls starts with; nothing in the
# bench writes real .xls, and the check only reads these first bytes.
XLS = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 504
EXE = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00" + b"\x00" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
CSV = "Customer Name,Territory\nAcme,India\n"


def _xlsx() -> bytes:
    wb = openpyxl.Workbook()
    wb.active.append(["Customer Name", "Territory"])
    wb.active.append(["Acme", "India"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _zip(*names: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name in names:
            zf.writestr(name, "<x/>")
    return buf.getvalue()


class TestSpreadsheetMagicBytes(unittest.TestCase):
    def test_accepts_real_xlsx(self):
        self.assertTrue(_magic_bytes_match(_xlsx(), XLSX_MIME))

    def test_accepts_real_xls(self):
        self.assertTrue(_magic_bytes_match(XLS, XLS_MIME))

    def test_rejects_exe_renamed_to_xlsx(self):
        self.assertFalse(_magic_bytes_match(EXE, XLSX_MIME))

    def test_rejects_exe_renamed_to_xls(self):
        self.assertFalse(_magic_bytes_match(EXE, XLS_MIME))

    def test_rejects_png_renamed_to_xlsx(self):
        self.assertFalse(_magic_bytes_match(PNG, XLSX_MIME))

    def test_rejects_zip_renamed_to_xlsx(self):
        self.assertFalse(_magic_bytes_match(_zip("data.csv"), XLSX_MIME))

    def test_rejects_docx_renamed_to_xlsx(self):
        docx = _zip("[Content_Types].xml", "word/document.xml")
        self.assertFalse(_magic_bytes_match(docx, XLSX_MIME))

    def test_rejects_zip_header_without_a_readable_archive(self):
        self.assertFalse(_magic_bytes_match(b"PK\x03\x04" + b"\x00" * 64, XLSX_MIME))


class TestTextMagicBytes(unittest.TestCase):
    def test_rejects_exe_renamed_to_csv(self):
        self.assertFalse(_magic_bytes_match(EXE, "text/csv"))

    def test_accepts_normal_csv(self):
        self.assertTrue(_magic_bytes_match(CSV.encode("utf-8-sig"), "text/csv"))

    def test_accepts_utf16_csv(self):
        # Excel's "Unicode Text" export is BOM-prefixed UTF-16, so NUL-heavy.
        for bom, codec in ((b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be")):
            with self.subTest(codec=codec):
                self.assertTrue(_magic_bytes_match(bom + CSV.encode(codec), "text/csv"))

    def test_rejects_binary_behind_a_utf16_bom(self):
        # A byte-order mark alone isn't text: what follows it must read as UTF-16 text (#34404).
        for bom in (b"\xff\xfe", b"\xfe\xff"):
            with self.subTest(bom=bom):
                self.assertFalse(_magic_bytes_match(bom + EXE, "text/csv"))


class TestSpreadsheetUpload(BaseAssistantTest):
    def _upload(self, content: bytes, file_name: str, content_type: str) -> dict:
        with patch(
            "frappe_assistant_core.chat.api.settings.access.can_use_faco",
            return_value={"can_use": True},
        ):
            return upload_message_file(
                file_data=base64.b64encode(content).decode(),
                file_name=file_name,
                content_type=content_type,
            )

    def test_uploads_xlsx(self):
        result = self._upload(_xlsx(), "customers.xlsx", XLSX_MIME)
        self.assertTrue(result["success"])
        self.assertEqual(result["file"]["format"], "xlsx")

    def test_rejects_renamed_exe_with_a_clear_message(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._upload(EXE, "customers.xlsx", XLSX_MIME)
        self.assertIn("does not match its extension: .xlsx", str(ctx.exception))

    def test_rejects_exe_renamed_to_csv_with_the_same_message(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._upload(EXE, "customers.csv", "text/csv")
        self.assertIn("does not match its extension: .csv", str(ctx.exception))

    def test_text_mime_does_not_skip_the_check_for_xlsx(self):
        # The base64 path takes content_type from the client verbatim.
        with self.assertRaises(frappe.ValidationError):
            self._upload(EXE, "customers.xlsx", "text/csv")

    def test_csv_labelled_as_excel_still_uploads(self):
        # Windows browsers send .csv as application/vnd.ms-excel when Excel is
        # installed — that must not be checked as a binary .xls.
        unique = frappe.generate_hash(length=8)
        result = self._upload(f"Customer Name,Territory\n{unique},India\n".encode(), "c.csv", XLS_MIME)
        self.assertTrue(result["success"])
