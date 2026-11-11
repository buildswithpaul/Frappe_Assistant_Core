# Frappe Assistant Core - JSON/XML chat attachment extraction tests
# Copyright (C) 2025 Paul Clinton
#
# AGPL-3.0 License

"""JSON and XML pass the upload allowlist, so they have to reach FACO too.
They used to fall through _detect_file_type as "unknown": dropped from the
prompt, and — now that failed extractions are logged — an Error Log per send.
XML is a data export (Tally writes XML), so like a spreadsheet only its summary
goes into the prompt; the full file stays on the server.
"""

import base64
from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api.chat.conversation_files import _describe, _file_text
from frappe_assistant_core.chat.api.chat.helpers import _attach_files_to_message
from frappe_assistant_core.chat.api.settings.uploads import upload_message_file
from frappe_assistant_core.tests.base_test import BaseAssistantTest


def _message_files_text(message_name: str) -> str:
    """What the model is shown for the files attached to one message."""
    files = frappe.get_all(
        "File",
        filters={"attached_to_doctype": "FAC Chat Message", "attached_to_name": message_name},
        fields=["name", "file_name", "file_url", "file_size"],
    )
    return "\n\n".join(_describe(f, f"Content:\n{_file_text(f)}") for f in files)


class TestJsonXmlAttachments(BaseAssistantTest):
    def _assert_reaches_faco(
        self, file_name: str, content_type: str, text: str, message_name: str, expected: tuple = ()
    ) -> str:
        with patch(
            "frappe_assistant_core.chat.api.settings.access.can_use_faco",
            return_value={"can_use": True},
        ):
            result = upload_message_file(
                file_data=base64.b64encode(text.encode()).decode(),
                file_name=file_name,
                content_type=content_type,
            )
        _attach_files_to_message([result["file"]["file_url"]], message_name)
        logs_before = frappe.db.count("Error Log")

        extracted = _message_files_text(message_name)

        self.assertEqual(frappe.db.count("Error Log"), logs_before)
        self.assertIn(f"File: {file_name}", extracted)
        for snippet in expected or (text,):
            self.assertIn(snippet, extracted)
        return extracted

    def test_json_attachment_reaches_faco(self):
        # Unique per run: Frappe content-addresses uploads.
        tag = frappe.generate_hash(length=8)
        self._assert_reaches_faco(
            "customers.json",
            "application/json",
            f'[{{"customer_name": "Acme {tag}", "territory": "India"}}]',
            "FACMSG-TEST-JSON",
        )

    def test_xml_attachment_reaches_faco_as_a_summary(self):
        tag = frappe.generate_hash(length=8)
        customers = "".join(
            f'<customer territory="India"><name>Acme {tag} {i}</name></customer>' for i in range(12)
        )
        extracted = self._assert_reaches_faco(
            "customers.xml",
            "text/xml",
            f"<customers>{customers}</customers>",
            "FACMSG-TEST-XML",
            expected=("=== Records: customer ===", "Columns: territory, name", "Rows: 12", f"Acme {tag} 9"),
        )
        self.assertNotIn(f"Acme {tag} 10", extracted)
        self.assertNotIn("<customer", extracted)
