"""AR refusing a knowledge-base upload is a permission answer, not a crash.

AR answers 403 when the tenant's plan excludes the knowledge base. FAC used to
wrap that as ``Error: ...`` in a ValidationError, which the SPA received as
HTTP 417 with a message about a server error rather than about the plan.
"""

import io
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.chat.api import documents
from frappe_assistant_core.chat.fac_cloud_client import ARAPIError
from frappe_assistant_core.tests.base_test import IntegrationTestCase

CLIENT = "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client"
PLAN_MESSAGE = "Your plan does not include the knowledge base."


class TestUploadDocumentErrors(IntegrationTestCase):
    def _upload(self, error):
        client = MagicMock()
        client.upload_document.side_effect = error
        upload = SimpleNamespace(filename="notes.txt", content_type="text/plain", read=io.BytesIO(b"hi").read)
        request = SimpleNamespace(files={"file": upload})
        with patch(CLIENT, return_value=client), patch.object(frappe, "log_error"), patch.object(
            frappe, "request", request, create=True
        ):
            documents.upload_document()

    def test_ar_403_becomes_a_permission_error_with_ars_message(self):
        with self.assertRaises(frappe.PermissionError) as ctx:
            self._upload(ARAPIError(PLAN_MESSAGE, status_code=403))

        self.assertIn(PLAN_MESSAGE, str(ctx.exception))
        self.assertNotIn("HTTP_403", str(ctx.exception))

    def test_other_ar_errors_are_not_reported_as_permission_errors(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._upload(ARAPIError("boom", status_code=500))

        self.assertNotIsInstance(ctx.exception, frappe.PermissionError)
