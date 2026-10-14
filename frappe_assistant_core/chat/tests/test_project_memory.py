# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Project memory: list, clear, cleanup on project delete and the GDPR export count."""

import json
from unittest.mock import Mock, create_autospec, patch

import frappe
from assistant_runtime_sdk import AssistantRuntimeClient

from frappe_assistant_core.chat.api import init, memories, privacy
from frappe_assistant_core.chat.api.auth import _ar_user_id
from frappe_assistant_core.chat.api.chat import projects
from frappe_assistant_core.chat.tests.test_chat_projects_api import OTHER_USER, ensure_user, make_project
from frappe_assistant_core.tests.base_test import BaseAssistantTest

CLIENT = "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client"
OWNER = "fac-project-memory-owner@example.com"


def _set_capability(enabled: bool) -> None:
    # Production gets this flag from AR's get_capabilities: initialize_spa caches the blob
    # in FAC Chat Settings.cached_capabilities, which project_memory_enabled() reads.
    frappe.db.set_single_value(
        "FAC Chat Settings",
        "cached_capabilities",
        json.dumps({"features": {"project_memory": enabled, "project_documents": enabled}}),
    )


class _Base(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        ensure_user(OWNER)
        ensure_user(OTHER_USER)
        # nosemgrep: frappe-setuser — runs as a throwaway user so no destructive call touches Administrator
        frappe.set_user(OWNER)
        # nosemgrep: frappe-setuser — restore the bootstrap user
        self.addCleanup(frappe.set_user, "Administrator")
        self.client = create_autospec(AssistantRuntimeClient, instance=True)
        patcher = patch(CLIENT, return_value=self.client)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.project = make_project(OWNER)
        self.ar_user = _ar_user_id(OWNER)


class TestListMemories(_Base):
    def setUp(self):
        super().setUp()
        _set_capability(True)
        self.client.list_memories.return_value = {"memories": [], "pagination": {"total": 0}}

    def test_project_is_passed_as_project_id_with_the_owner(self):
        memories.list_memories(memory_type="fact", limit=10, offset=5, project=self.project)
        self.client.list_memories.assert_called_once_with(
            user_id=self.ar_user, memory_type="fact", limit=10, offset=5, project_id=self.project
        )

    def test_without_project_no_project_id_is_sent(self):
        memories.list_memories()
        self.assertNotIn("project_id", self.client.list_memories.call_args.kwargs)

    def test_foreign_project_is_refused(self):
        theirs = make_project(OTHER_USER)
        with self.assertRaises(frappe.DoesNotExistError):
            memories.list_memories(project=theirs)
        self.client.list_memories.assert_not_called()

    def test_refused_when_ar_lacks_the_capability(self):
        _set_capability(False)
        with self.assertRaises(frappe.ValidationError):
            memories.list_memories(project=self.project)
        self.client.list_memories.assert_not_called()


class TestClearProjectMemories(_Base):
    def setUp(self):
        super().setUp()
        _set_capability(True)

    def test_clears_the_owners_project(self):
        self.client.delete_project_memories.return_value = {"status": "deleted", "count": 2}
        result = memories.clear_project_memories(self.project)
        self.assertEqual(result, {"status": "deleted", "count": 2})
        self.client.delete_project_memories.assert_called_once_with(
            user_id=self.ar_user, project_id=self.project
        )

    def test_foreign_project_is_refused(self):
        theirs = make_project(OTHER_USER)
        with self.assertRaises(frappe.DoesNotExistError):
            memories.clear_project_memories(theirs)
        self.client.delete_project_memories.assert_not_called()

    def test_refused_when_ar_lacks_the_capability(self):
        _set_capability(False)
        with self.assertRaises(frappe.ValidationError):
            memories.clear_project_memories(self.project)
        self.client.delete_project_memories.assert_not_called()


class TestDeleteProject(_Base):
    def setUp(self):
        super().setUp()
        _set_capability(True)

    def test_memories_are_deleted_after_the_documents_unlink(self):
        calls = Mock()
        self.client.unlink_project_documents.side_effect = lambda **kw: calls("unlink", kw["project_id"])
        self.client.delete_project_memories.side_effect = lambda **kw: calls(
            "memories", kw["user_id"], kw["project_id"]
        )
        projects.delete_project(self.project)
        self.assertEqual(
            [c.args for c in calls.call_args_list],
            [("unlink", self.project), ("memories", self.ar_user, self.project)],
        )
        self.assertFalse(frappe.db.exists("FAC Chat Project", self.project))

    def test_delete_refused_when_memory_delete_fails(self):
        self.client.delete_project_memories.side_effect = Exception("down")
        with patch.object(frappe, "log_error"), self.assertRaises(frappe.ValidationError) as ctx:
            projects.delete_project(self.project)
        self.assertIn("Couldn't delete this project's memories; try again", str(ctx.exception))
        self.assertTrue(frappe.db.exists("FAC Chat Project", self.project))

    def test_delete_skips_memories_when_capability_off(self):
        _set_capability(False)
        projects.delete_project(self.project)
        self.client.delete_project_memories.assert_not_called()
        self.assertFalse(frappe.db.exists("FAC Chat Project", self.project))


class TestExport(_Base):
    def _row(self) -> dict:
        self.client.export_user_data.return_value = {"status": "success", "data": {}}
        with patch.object(privacy, "_get_client", return_value=self.client):
            rows = privacy.export_my_data()["data"]["faco"]["faco_projects"]
        return next(p for p in rows if p["name"] == self.project)

    def test_export_counts_project_memories(self):
        _set_capability(True)
        self.client.list_documents.return_value = {"documents": []}
        self.client.list_memories.return_value = {"memories": [{"id": "a"}, {"id": "b"}]}
        self.assertEqual(self._row()["memory_count"], 2)
        self.client.list_memories.assert_called_once_with(
            user_id=self.ar_user, project_id=self.project, limit=500
        )

    def test_export_memory_count_is_none_when_listing_fails(self):
        _set_capability(True)
        self.client.list_documents.return_value = {"documents": []}
        self.client.list_memories.side_effect = Exception("down")
        with patch.object(frappe, "log_error"):
            self.assertIsNone(self._row()["memory_count"])

    def test_export_memory_count_is_none_when_capability_off(self):
        _set_capability(False)
        self.assertIsNone(self._row()["memory_count"])
        self.client.list_memories.assert_not_called()


class TestDefaults(BaseAssistantTest):
    def test_default_capabilities_report_project_memory_off(self):
        self.assertIs(init._default_capabilities()["features"]["project_memory"], False)
