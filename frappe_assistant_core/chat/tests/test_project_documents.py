# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Project documents: upload, list, unlink on delete, GDPR export and the per-turn project context."""

import inspect
import io
import json
from types import SimpleNamespace
from unittest.mock import create_autospec, patch

import frappe
from assistant_runtime_sdk import AssistantRuntimeClient

from frappe_assistant_core.chat.api import documents, privacy
from frappe_assistant_core.chat.api.auth import _ar_user_id
from frappe_assistant_core.chat.api.chat import live_turn, messages, projects
from frappe_assistant_core.chat.api.chat.relay import _relay_ar_interrupt_resume, _relay_ar_stream
from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import FACChatMessage
from frappe_assistant_core.chat.tests.test_chat_projects_api import OTHER_USER, ensure_user, make_project
from frappe_assistant_core.tests.base_test import BaseAssistantTest

CLIENT = "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client"
SID = "test-project-documents"


def _set_capability(enabled: bool) -> None:
    # Production gets this flag from AR's get_capabilities: initialize_spa caches the blob
    # in FAC Chat Settings.cached_capabilities, which project_documents_enabled() reads.
    frappe.db.set_single_value(
        "FAC Chat Settings",
        "cached_capabilities",
        json.dumps({"features": {"project_documents": enabled}}),
    )


class _Base(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; runs in an isolated transaction
        frappe.set_user("Administrator")
        ensure_user(OTHER_USER)
        self.client = create_autospec(AssistantRuntimeClient, instance=True)
        patcher = patch(CLIENT, return_value=self.client)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.project = make_project("Administrator")


class TestUploadAndList(_Base):
    def _upload(self, **form):
        upload = SimpleNamespace(filename="notes.txt", content_type="text/plain", read=io.BytesIO(b"hi").read)
        request = SimpleNamespace(files={"file": upload})
        with patch.object(frappe, "request", request, create=True), patch.object(
            frappe, "form_dict", frappe._dict(form)
        ):
            return documents.upload_document()

    def test_upload_with_project_checks_ownership_and_passes_project_id(self):
        self._upload(project=self.project, visibility="public", shared_with="x@example.com")
        kwargs = self.client.upload_document.call_args.kwargs
        self.assertEqual(kwargs["project_id"], self.project)
        self.assertNotIn("visibility", kwargs)
        self.assertNotIn("shared_with", kwargs)

    def test_upload_refuses_foreign_project(self):
        theirs = make_project(OTHER_USER)
        with self.assertRaises(frappe.DoesNotExistError):
            self._upload(project=theirs)
        self.client.upload_document.assert_not_called()

    def test_upload_without_project_is_unchanged(self):
        self._upload(visibility="private")
        kwargs = self.client.upload_document.call_args.kwargs
        self.assertNotIn("project_id", kwargs)
        self.assertEqual(kwargs["visibility"], "private")

    def test_list_with_project_passes_project_id(self):
        self.client.list_documents.return_value = {"documents": []}
        documents.list_documents(project=self.project)
        self.assertEqual(self.client.list_documents.call_args.kwargs["project_id"], self.project)

    def test_list_without_project_sends_no_project_id(self):
        self.client.list_documents.return_value = {"documents": []}
        documents.list_documents()
        self.assertNotIn("project_id", self.client.list_documents.call_args.kwargs)

    def test_list_refuses_foreign_project(self):
        theirs = make_project(OTHER_USER)
        with self.assertRaises(frappe.DoesNotExistError):
            documents.list_documents(project=theirs)
        self.client.list_documents.assert_not_called()


class TestDeleteProject(_Base):
    def test_delete_unlinks_before_deleting(self):
        _set_capability(True)
        projects.delete_project(self.project)
        self.client.unlink_project_documents.assert_called_once_with(
            user_id=_ar_user_id("Administrator"), project_id=self.project
        )
        self.assertFalse(frappe.db.exists("FAC Chat Project", self.project))

    def test_delete_refused_when_unlink_fails(self):
        _set_capability(True)
        self.client.unlink_project_documents.side_effect = Exception("down")
        with patch.object(frappe, "log_error"), self.assertRaises(frappe.ValidationError):
            projects.delete_project(self.project)
        self.assertTrue(frappe.db.exists("FAC Chat Project", self.project))

    def test_delete_skips_unlink_when_capability_off(self):
        _set_capability(False)
        projects.delete_project(self.project)
        self.client.unlink_project_documents.assert_not_called()
        self.assertFalse(frappe.db.exists("FAC Chat Project", self.project))


class TestExport(_Base):
    def _export(self) -> dict:
        self.client.export_user_data.return_value = {"status": "success", "data": {}}
        with patch.object(privacy, "_get_client", return_value=self.client):
            return privacy.export_my_data()["data"]["faco"]["faco_projects"]

    def test_export_lists_project_document_names(self):
        _set_capability(True)
        self.client.list_documents.return_value = {"documents": [{"file_name": "a.pdf"}]}
        row = next(p for p in self._export() if p["name"] == self.project)
        self.assertEqual(row["documents"], ["a.pdf"])

    def test_export_marks_documents_unavailable_when_listing_fails(self):
        _set_capability(True)
        self.client.list_documents.side_effect = Exception("down")
        with patch.object(frappe, "log_error"):
            row = next(p for p in self._export() if p["name"] == self.project)
        self.assertIsNone(row["documents"])

    def test_export_skips_documents_when_capability_off(self):
        _set_capability(False)
        row = next(p for p in self._export() if p["name"] == self.project)
        self.assertNotIn("documents", row)
        self.client.list_documents.assert_not_called()


class TestTurnContext(_Base):
    def setUp(self):
        super().setUp()
        frappe.db.delete("FAC Chat Message", {"session_id": SID})
        frappe.db.delete("FAC Chat Conversation", {"name": SID})
        self.addCleanup(live_turn.clear, SID)  # the endpoints mark the turn started in Redis

    def _submitted(self, relay, call) -> dict:
        with patch.object(messages._relay_pool, "submit", autospec=True) as submit, patch(
            "frappe_assistant_core.chat.api.settings.can_use_faco", return_value={"can_use": True}
        ), patch.object(messages, "_is_processing_restricted", autospec=True, return_value=False):
            call()
        submit.assert_called_once()
        args, kwargs = submit.call_args
        self.assertIs(args[0], relay)
        return inspect.signature(relay).bind(*args[1:], **kwargs).arguments

    def test_send_puts_project_in_context(self):
        bound = self._submitted(
            _relay_ar_stream,
            lambda: messages.send_message(
                session_id=SID,
                message="hi",
                project=self.project,
                context=json.dumps({"route": ["Form", "Customer"]}),
            ),
        )
        self.assertEqual(bound["context"]["project_id"], self.project)
        self.assertEqual(bound["context"]["route"], ["Form", "Customer"])

    def test_resume_and_continue_put_project_in_context(self):
        # The row exists because the turn being resumed/continued was sent through
        # send_message, which created it with this project.
        FACChatMessage.create_message(SID, "user", "hi", project=self.project)
        resumed = self._submitted(
            _relay_ar_interrupt_resume,
            lambda: messages.resume_interrupt(
                session_id=SID,
                interrupt_response='[{"interruptId": "int1", "response": "approve"}]',
                message_id="m-paused",
            ),
        )
        self.assertEqual(resumed["context"], {"project_id": self.project})
        live_turn.clear(SID)
        continued = self._submitted(
            _relay_ar_stream,
            lambda: messages.continue_response(session_id=SID, message_id="m-truncated"),
        )
        self.assertEqual(continued["context"], {"project_id": self.project})

    def test_no_project_no_context_key(self):
        bound = self._submitted(
            _relay_ar_stream,
            lambda: messages.send_message(
                session_id=SID, message="hi", context=json.dumps({"route": ["List", "Item"]})
            ),
        )
        self.assertNotIn("project_id", bound["context"] or {})


class TestResumeRelayHop(BaseAssistantTest):
    def test_the_resume_relay_hands_the_context_to_the_real_sdk_signature(self):
        """The last hop: the relay must pass context on to the SDK's stream_chat."""
        client = create_autospec(AssistantRuntimeClient, instance=True)
        client.stream_chat.return_value = iter(())
        with patch(CLIENT, return_value=client), patch("frappe.init"), patch("frappe.connect"), patch(
            "frappe.set_user"
        ), patch("frappe.destroy"), patch("frappe.db"), patch(
            "frappe_assistant_core.chat.api.chat.relay.is_cancelled", return_value=False
        ), patch("frappe_assistant_core.chat.api.chat.relay._emit_socket_event"):
            _relay_ar_interrupt_resume(
                "s1",
                [{"interruptId": "i1", "response": "approve"}],
                "u@x.com",
                "site",
                context={"project_id": "P-1"},
            )

        self.assertEqual(client.stream_chat.call_args.kwargs["context"], {"project_id": "P-1"})
