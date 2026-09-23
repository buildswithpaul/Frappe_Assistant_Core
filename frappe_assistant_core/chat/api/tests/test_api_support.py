import base64
import unittest
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.chat.api import support
from frappe_assistant_core.chat.api.auth import _ar_user_id

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
        self.assertEqual(kwargs["user_id"], _ar_user_id(frappe.session.user))
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
    def test_feedback_carries_no_conversation_reference(self, mock_get_client):
        """The feedback form never asks, so nothing about the chat may ride along."""
        client = MagicMock()
        client.submit_feedback.return_value = {"feedback_id": "f1"}
        mock_get_client.return_value = client

        support.submit_feedback(rating=5, comment="Great", category="Product")

        self.assertNotIn("conversation_id", client.submit_feedback.call_args.kwargs)

    @patch("frappe_assistant_core.chat.api.support.get_fac_cloud_client")
    def test_feedback_rejects_a_conversation_id_from_the_wire(self, mock_get_client):
        """A caller can't reinstate it by posting the field directly."""
        client = MagicMock()
        client.submit_feedback.return_value = {"feedback_id": "f1"}
        mock_get_client.return_value = client

        with self.assertRaises(TypeError):
            support.submit_feedback(rating=5, conversation_id="sess-9")

    @patch("frappe_assistant_core.chat.api.support.get_fac_cloud_client")
    def test_list_my_tickets_proxies(self, mock_get_client):
        client = MagicMock()
        client.list_tickets.return_value = [{"name": "1"}]
        mock_get_client.return_value = client
        result = support.list_my_tickets(status="Open")
        self.assertEqual(result[0]["name"], "1")
        kwargs = client.list_tickets.call_args.kwargs
        self.assertEqual(kwargs["user_id"], _ar_user_id(frappe.session.user))
        self.assertEqual(kwargs["status"], "Open")

    @patch("frappe_assistant_core.chat.api.support.get_fac_cloud_client")
    def test_get_ticket_thread_proxies(self, mock_get_client):
        client = MagicMock()
        client.get_ticket_thread.return_value = {"subject": "X", "messages": []}
        mock_get_client.return_value = client
        result = support.get_ticket_thread(ticket_id="58")
        self.assertEqual(result["subject"], "X")
        self.assertEqual(client.get_ticket_thread.call_args.kwargs["ticket_id"], "58")
        self.assertEqual(
            client.get_ticket_thread.call_args.kwargs["user_id"], _ar_user_id(frappe.session.user)
        )

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


class TestDownloadTicketAttachmentProxy(unittest.TestCase):
    @patch("frappe_assistant_core.chat.api.support.get_fac_cloud_client")
    def test_streams_the_bytes_from_ar(self, mock_get_client):
        client = MagicMock()
        client.download_ticket_attachment.return_value = (PNG_BYTES, "image/png", "shot.png")
        mock_get_client.return_value = client

        support.download_ticket_attachment(ticket_id=58, file_url="/private/files/shot.png")

        kwargs = client.download_ticket_attachment.call_args.kwargs
        self.assertEqual(kwargs["user_id"], _ar_user_id(frappe.session.user))
        self.assertEqual(kwargs["ticket_id"], "58")
        self.assertEqual(kwargs["file_url"], "/private/files/shot.png")
        self.assertEqual(frappe.local.response.filecontent, PNG_BYTES)
        self.assertEqual(frappe.local.response.content_type, "image/png")
        self.assertEqual(frappe.local.response.type, "download")

    @patch("frappe_assistant_core.chat.api.support.get_fac_cloud_client")
    def test_requires_both_a_ticket_and_a_file(self, mock_get_client):
        with self.assertRaises(frappe.ValidationError):
            support.download_ticket_attachment(ticket_id=None, file_url="/private/files/a.png")
        with self.assertRaises(frappe.ValidationError):
            support.download_ticket_attachment(ticket_id=58, file_url=None)
        mock_get_client.assert_not_called()

    @patch("frappe_assistant_core.chat.api.support.get_fac_cloud_client")
    def test_ar_refusal_surfaces_as_a_clean_error(self, mock_get_client):
        client = MagicMock()
        client.download_ticket_attachment.side_effect = Exception("not found")
        mock_get_client.return_value = client
        with self.assertRaises(frappe.ValidationError):
            support.download_ticket_attachment(ticket_id=58, file_url="/private/files/x.png")


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
        self.assertEqual(kwargs["user_id"], _ar_user_id(frappe.session.user))
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


class TestTranscriptRendering(unittest.TestCase):
    """_render_transcript turns FAC Chat Message rows into readable Markdown."""

    def _rows(self, *msgs):
        return list(msgs)

    def _msg(self, role, content, model=None, ts="2026-09-08 10:00:00"):
        return {"role": role, "content": content, "model": model, "timestamp": ts}

    @patch("frappe_assistant_core.chat.api.support.frappe.get_all")
    def test_renders_each_turn_with_its_role(self, mock_get_all):
        mock_get_all.return_value = self._rows(
            self._msg("user", "why is my invoice wrong"),
            self._msg("assistant", "Let me check.", model="claude-opus-5"),
        )
        md = support._render_transcript("sess-1")
        self.assertIn("why is my invoice wrong", md)
        self.assertIn("Let me check.", md)
        self.assertIn("User", md)
        self.assertIn("Assistant", md)
        self.assertIn("claude-opus-5", md)

    @patch("frappe_assistant_core.chat.api.support.frappe.get_all")
    def test_scopes_the_query_to_the_session_and_caller(self, mock_get_all):
        mock_get_all.return_value = []
        support._render_transcript("sess-1")
        kwargs = mock_get_all.call_args.kwargs
        self.assertEqual(kwargs["filters"]["session_id"], "sess-1")
        self.assertEqual(kwargs["filters"]["user"], frappe.session.user)
        self.assertIn("timestamp", kwargs["order_by"])

    @patch("frappe_assistant_core.chat.api.support.frappe.get_all")
    def test_empty_session_renders_nothing(self, mock_get_all):
        mock_get_all.return_value = []
        self.assertIsNone(support._render_transcript("sess-1"))

    @patch("frappe_assistant_core.chat.api.support.frappe.get_all")
    def test_oversized_transcript_is_capped_and_says_so(self, mock_get_all):
        big = "x" * 5000
        mock_get_all.return_value = [self._msg("user", big) for _ in range(200)]
        md = support._render_transcript("sess-1")
        self.assertLessEqual(len(md.encode("utf-8")), support.MAX_TRANSCRIPT_BYTES)
        self.assertIn("truncated", md.lower())

    @patch("frappe_assistant_core.chat.api.support.frappe.get_all")
    def test_no_session_id_short_circuits_without_querying(self, mock_get_all):
        self.assertIsNone(support._render_transcript(None))
        mock_get_all.assert_not_called()


class TestTranscriptPassThrough(unittest.TestCase):
    @patch("frappe_assistant_core.chat.api.support._render_transcript")
    @patch("frappe_assistant_core.chat.api.support.get_fac_cloud_client")
    def test_ticket_carries_the_transcript_when_a_conversation_is_included(
        self, mock_get_client, mock_render
    ):
        client = MagicMock()
        client.create_ticket.return_value = {"ticket_id": "1"}
        mock_get_client.return_value = client
        mock_render.return_value = "# Conversation\n\n**User:** hi"

        support.create_ticket(subject="X", description="Y", conversation_id="c1")

        mock_render.assert_called_once_with("c1")
        kwargs = client.create_ticket.call_args.kwargs
        self.assertEqual(kwargs["conversation_transcript"], "# Conversation\n\n**User:** hi")

    @patch("frappe_assistant_core.chat.api.support.frappe.get_all")
    @patch("frappe_assistant_core.chat.api.support.get_fac_cloud_client")
    def test_no_conversation_means_no_transcript_and_no_query(self, mock_get_client, mock_get_all):
        client = MagicMock()
        client.create_ticket.return_value = {"ticket_id": "1"}
        mock_get_client.return_value = client

        support.create_ticket(subject="X", description="Y", conversation_id=None)

        self.assertIsNone(client.create_ticket.call_args.kwargs["conversation_transcript"])
        mock_get_all.assert_not_called()
