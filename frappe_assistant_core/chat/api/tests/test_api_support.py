import base64
import unittest
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.chat.api import support

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


class TestSupportProxy(unittest.TestCase):
    @patch("frappe_assistant_core.chat.api.support.get_fac_cloud_client")
    def test_create_ticket_proxies_to_sdk(self, mock_get_client):
        client = MagicMock()
        client.create_ticket.return_value = {"ticket_id": "1", "portal_link": "http://x/y"}
        mock_get_client.return_value = client

        result = support.create_ticket(
            subject="X",
            description="Y",
            category="Bug",
            conversation_id="c1",
            environment={"fac_version": "2.3"},
        )

        self.assertEqual(result["ticket_id"], "1")
        client.create_ticket.assert_called_once()
        kwargs = client.create_ticket.call_args.kwargs
        self.assertEqual(kwargs["user_id"], frappe.session.user)
        self.assertEqual(kwargs["subject"], "X")

    @patch("frappe_assistant_core.chat.api.support.get_fac_cloud_client")
    def test_create_ticket_clean_error_when_unconfigured(self, mock_get_client):
        mock_get_client.return_value = None
        with self.assertRaises(frappe.ValidationError):
            support.create_ticket(subject="X", description="Y")
        # _get_client() throws before the try, so no SDK call is attempted.
        mock_get_client.assert_called_once()

    @patch("frappe_assistant_core.chat.api.support.get_fac_cloud_client")
    def test_submit_feedback_proxies_to_sdk(self, mock_get_client):
        client = MagicMock()
        client.submit_feedback.return_value = {"feedback_id": "f1"}
        mock_get_client.return_value = client

        result = support.submit_feedback(rating=5, comment="Great", category="Product")
        self.assertEqual(result["feedback_id"], "f1")
        client.submit_feedback.assert_called_once()

    @patch("frappe_assistant_core.chat.api.support.get_fac_cloud_client")
    def test_list_my_tickets_proxies(self, mock_get_client):
        client = MagicMock()
        client.list_tickets.return_value = [{"name": "1"}]
        mock_get_client.return_value = client
        result = support.list_my_tickets(status="Open")
        self.assertEqual(result[0]["name"], "1")
        kwargs = client.list_tickets.call_args.kwargs
        self.assertEqual(kwargs["user_id"], frappe.session.user)
        self.assertEqual(kwargs["status"], "Open")

    @patch("frappe_assistant_core.chat.api.support.get_fac_cloud_client")
    def test_get_ticket_thread_proxies(self, mock_get_client):
        client = MagicMock()
        client.get_ticket_thread.return_value = {"subject": "X", "messages": []}
        mock_get_client.return_value = client
        result = support.get_ticket_thread(ticket_id="58")
        self.assertEqual(result["subject"], "X")
        self.assertEqual(client.get_ticket_thread.call_args.kwargs["ticket_id"], "58")
        self.assertEqual(client.get_ticket_thread.call_args.kwargs["user_id"], frappe.session.user)

    @patch("frappe_assistant_core.chat.api.support.get_fac_cloud_client")
    def test_get_ticket_thread_requires_id(self, mock_get_client):
        with self.assertRaises(frappe.ValidationError):
            support.get_ticket_thread(ticket_id=None)

    @patch("frappe_assistant_core.chat.api.support.get_fac_cloud_client")
    def test_reply_to_ticket_proxies(self, mock_get_client):
        client = MagicMock()
        client.reply_to_ticket.return_value = {"success": True}
        mock_get_client.return_value = client
        result = support.reply_to_ticket(ticket_id="58", message="hi")
        self.assertTrue(result["success"])
        kwargs = client.reply_to_ticket.call_args.kwargs
        self.assertEqual(kwargs["ticket_id"], "58")
        self.assertEqual(kwargs["message"], "hi")

    @patch("frappe_assistant_core.chat.api.support.get_fac_cloud_client")
    def test_reply_requires_message(self, mock_get_client):
        with self.assertRaises(frappe.ValidationError):
            support.reply_to_ticket(ticket_id="58", message="   ")

    @patch("frappe_assistant_core.chat.api.support.get_fac_cloud_client")
    def test_get_ticket_thread_coerces_int_id_to_str(self, mock_get_client):
        client = MagicMock()
        client.get_ticket_thread.return_value = {"subject": "X", "messages": []}
        mock_get_client.return_value = client
        support.get_ticket_thread(ticket_id=58)  # int, as it arrives from the wire
        self.assertEqual(client.get_ticket_thread.call_args.kwargs["ticket_id"], "58")

    @patch("frappe_assistant_core.chat.api.support.get_fac_cloud_client")
    def test_reply_to_ticket_coerces_int_id_to_str(self, mock_get_client):
        client = MagicMock()
        client.reply_to_ticket.return_value = {"success": True}
        mock_get_client.return_value = client
        support.reply_to_ticket(ticket_id=58, message="hi")
        self.assertEqual(client.reply_to_ticket.call_args.kwargs["ticket_id"], "58")


class TestGetEnvironment(unittest.TestCase):
    """The metadata support reads first on every ticket.

    This used to be scraped from `<meta name="fac-version">` tags the SPA shell
    never rendered, so every ticket arrived stamped "unknown".
    """

    def test_reports_real_versions_not_unknown(self):
        env = support.get_environment()
        self.assertNotEqual(env["fac_version"], "unknown")
        self.assertNotEqual(env["frappe_version"], "unknown")
        self.assertEqual(env["frappe_version"], frappe.__version__)

    def test_lists_every_installed_app_with_a_version(self):
        env = support.get_environment()
        for app in frappe.get_installed_apps():
            self.assertIn(app, env["installed_apps"])
        self.assertIn(f"frappe {frappe.__version__}", env["installed_apps"])

    def test_carries_tenant_id_for_support_lookup(self):
        env = support.get_environment()
        expected = frappe.db.get_single_value("FAC Chat Settings", "tenant_id") or "unregistered"
        self.assertEqual(env["tenant_id"], expected)

    def test_drops_ar_version(self):
        # AR runs server-side; a client can't know its version and shouldn't guess.
        self.assertNotIn("ar_version", support.get_environment())

    def test_app_without_dunder_version_degrades_to_unknown(self):
        with patch.object(frappe, "get_installed_apps", return_value=["frappe", "no_such_app"]):
            versions = support._installed_app_versions()
        self.assertEqual(versions["no_such_app"], "unknown")
        self.assertEqual(versions["frappe"], frappe.__version__)

    def test_bench_version_unknown_when_cli_missing(self):
        support._bench_version.clear_cache()
        self.addCleanup(support._bench_version.clear_cache)
        with patch("importlib.metadata.version", side_effect=Exception("not installed")):
            with patch("frappe_assistant_core.chat.api.support.shutil.which", return_value=None):
                self.assertEqual(support._bench_version(), "unknown")


class TestUploadTicketAttachmentProxy(unittest.TestCase):
    @patch("frappe_assistant_core.chat.api.support.get_fac_cloud_client")
    def test_upload_base64_forwards_to_sdk(self, mock_get_client):
        client = MagicMock()
        client.upload_ticket_attachment.return_value = {
            "file_id": "F1",
            "file_url": "/private/files/x.png",
            "file_name": "x.png",
            "is_image": True,
        }
        mock_get_client.return_value = client

        result = support.upload_ticket_attachment(
            file_data=base64.b64encode(PNG_BYTES).decode(),
            file_name="x.png",
            content_type="image/png",
        )
        self.assertEqual(result["file_id"], "F1")
        self.assertTrue(result["is_image"])
        kwargs = client.upload_ticket_attachment.call_args.kwargs
        self.assertEqual(kwargs["user_id"], frappe.session.user)
        self.assertEqual(kwargs["file_name"], "x.png")
        self.assertEqual(kwargs["file_data"], PNG_BYTES)

    @patch("frappe_assistant_core.chat.api.support.get_fac_cloud_client")
    def test_upload_rejects_bad_type_before_sdk(self, mock_get_client):
        client = MagicMock()
        mock_get_client.return_value = client
        with self.assertRaises(frappe.ValidationError):
            support.upload_ticket_attachment(
                file_data=base64.b64encode(b"hello").decode(),
                file_name="notes.txt",
                content_type="text/plain",
            )
        client.upload_ticket_attachment.assert_not_called()

    @patch("frappe_assistant_core.chat.api.support.get_fac_cloud_client")
    def test_upload_requires_file(self, mock_get_client):
        mock_get_client.return_value = MagicMock()
        with self.assertRaises(frappe.ValidationError):
            support.upload_ticket_attachment()

    @patch("frappe_assistant_core.chat.api.support.get_fac_cloud_client")
    def test_upload_rejects_malformed_base64(self, mock_get_client):
        client = MagicMock()
        mock_get_client.return_value = client
        with self.assertRaises(frappe.ValidationError):
            support.upload_ticket_attachment(
                file_data="not-valid-base64!!!",
                file_name="x.png",
                content_type="image/png",
            )
        client.upload_ticket_attachment.assert_not_called()


class TestAttachmentIdsPassThrough(unittest.TestCase):
    @patch("frappe_assistant_core.chat.api.support.get_fac_cloud_client")
    def test_create_ticket_threads_attachment_ids(self, mock_get_client):
        client = MagicMock()
        client.create_ticket.return_value = {"ticket_id": "1", "portal_link": "http://x"}
        mock_get_client.return_value = client
        support.create_ticket(subject="S", description="D", attachment_ids=["F1", "F2"])
        self.assertEqual(client.create_ticket.call_args.kwargs["attachment_ids"], ["F1", "F2"])

    @patch("frappe_assistant_core.chat.api.support.get_fac_cloud_client")
    def test_create_ticket_parses_json_string_ids(self, mock_get_client):
        client = MagicMock()
        client.create_ticket.return_value = {"ticket_id": "1", "portal_link": "http://x"}
        mock_get_client.return_value = client
        support.create_ticket(subject="S", description="D", attachment_ids='["F1"]')
        self.assertEqual(client.create_ticket.call_args.kwargs["attachment_ids"], ["F1"])

    @patch("frappe_assistant_core.chat.api.support.get_fac_cloud_client")
    def test_create_ticket_none_ids_pass_none(self, mock_get_client):
        client = MagicMock()
        client.create_ticket.return_value = {"ticket_id": "1", "portal_link": "http://x"}
        mock_get_client.return_value = client
        support.create_ticket(subject="S", description="D")
        self.assertIsNone(client.create_ticket.call_args.kwargs["attachment_ids"])

    @patch("frappe_assistant_core.chat.api.support.get_fac_cloud_client")
    def test_reply_threads_attachment_ids(self, mock_get_client):
        client = MagicMock()
        client.reply_to_ticket.return_value = {"message_id": "m1"}
        mock_get_client.return_value = client
        support.reply_to_ticket(ticket_id=58, message="hi", attachment_ids=["F9"])
        self.assertEqual(client.reply_to_ticket.call_args.kwargs["attachment_ids"], ["F9"])
