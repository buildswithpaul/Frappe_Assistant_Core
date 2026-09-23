import unittest

import frappe

from frappe_assistant_core.chat.api._attachment_validation import (
    TICKET_MAX_SIZE,
    validate_ticket_attachment,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PDF = b"%PDF-1.7\n" + b"0" * 32


class TestTicketAttachmentValidation(unittest.TestCase):
    def test_accepts_png_returns_sanitized_name_and_mime(self):
        name, mime = validate_ticket_attachment(PNG, "my shot.png", "image/png")
        self.assertTrue(name.endswith(".png"))
        self.assertNotIn(" ", name)
        self.assertEqual(mime, "image/png")

    def test_accepts_pdf(self):
        name, mime = validate_ticket_attachment(PDF, "report.pdf", "application/pdf")
        self.assertEqual(mime, "application/pdf")

    def test_rejects_disallowed_extension(self):
        with self.assertRaises(frappe.ValidationError):
            validate_ticket_attachment(b"hello", "notes.txt", "text/plain")

    def test_rejects_oversize(self):
        big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (TICKET_MAX_SIZE + 1)
        with self.assertRaises(frappe.ValidationError):
            validate_ticket_attachment(big, "big.png", "image/png")

    def test_rejects_magic_byte_mismatch(self):
        with self.assertRaises(frappe.ValidationError):
            validate_ticket_attachment(b"not-a-real-png", "fake.png", "image/png")

    def test_falls_back_to_extension_mime_when_octet_stream(self):
        name, mime = validate_ticket_attachment(PNG, "shot.png", "application/octet-stream")
        self.assertEqual(mime, "image/png")
