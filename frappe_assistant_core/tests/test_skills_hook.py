# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Tests for the assistant_skills hook + MCP resources handlers.

Covers:
- `_install_app_skills` discovery, content loading, update path, and
  obsolete-skill cleanup.
- `handle_resources_list` visibility filtering.
- `handle_resources_read` URI parsing and permission enforcement.
- `before_app_uninstall` cleanup of third-party app skills.
"""

import json
import os
import tempfile
from unittest.mock import patch

import frappe

from frappe_assistant_core.api.handlers.resources import (
    SkillManager,
    handle_resources_list,
    handle_resources_read,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.migration_hooks import (
    _install_app_skills,
    before_app_uninstall,
)

TEST_APP = "frappe_assistant_core"  # reuse a real installed app for get_app_path()


def _patch_assistant_skills_hook(entries):
    """
    Patch frappe.get_hooks to return ``entries`` only for "assistant_skills".
    All other hook lookups fall through to the real implementation — Frappe
    itself calls get_hooks during DB queries, so a blanket patch breaks it.
    """
    real_get_hooks = frappe.get_hooks

    def fake_get_hooks(hook=None, *args, **kwargs):
        if hook == "assistant_skills":
            return list(entries)
        return real_get_hooks(hook, *args, **kwargs)

    return patch("frappe.get_hooks", side_effect=fake_get_hooks)


def _ensure_user(email):
    """Ensure a minimal User exists so Link validation on owner_user passes."""
    if frappe.db.exists("User", email):
        return
    user = frappe.get_doc(
        {
            "doctype": "User",
            "email": email,
            "first_name": email.split("@")[0],
            "enabled": 1,
            "user_type": "System User",
        }
    )
    user.flags.ignore_permissions = True
    user.insert()


def _make_skill(
    skill_id,
    *,
    title="Test Skill",
    description="desc",
    content="# hello",
    status="Published",
    visibility="Public",
    is_system=0,
    owner_user="Administrator",
    source_app=None,
    shared_roles=None,
    skill_type="Workflow",
    linked_tool=None,
):
    doc = frappe.new_doc("FAC Skill")
    doc.skill_id = skill_id
    doc.title = title
    doc.description = description
    doc.content = content
    doc.status = status
    doc.visibility = visibility
    doc.is_system = is_system
    doc.owner_user = owner_user
    doc.source_app = source_app
    doc.skill_type = skill_type
    doc.linked_tool = linked_tool
    if shared_roles:
        for role in shared_roles:
            doc.append("shared_with_roles", {"role": role})
    doc.flags.ignore_permissions = True
    doc.insert()
    return doc


def _delete_skill(skill_id):
    name = frappe.db.get_value("FAC Skill", {"skill_id": skill_id}, "name")
    if not name:
        return
    doc = frappe.get_doc("FAC Skill", name)
    doc.flags.allow_system_delete = True
    doc.delete(ignore_permissions=True)


class TestSkillsHook(BaseAssistantTest):
    """Tests covering the assistant_skills registration hook."""

    def setUp(self):
        super().setUp()
        self._created_ids = []

    def tearDown(self):
        for sid in self._created_ids:
            try:
                _delete_skill(sid)
            except Exception:
                pass
        super().tearDown()

    def _track(self, skill_id):
        self._created_ids.append(skill_id)
        return skill_id

    def _write_manifest(self, tmpdir, entries):
        manifest_path = os.path.join(tmpdir, "manifest.json")
        with open(manifest_path, "w") as f:
            json.dump(entries, f)
        return manifest_path

    def _fake_hook(self, manifest_rel, content_dir_rel):
        return [{"app": TEST_APP, "manifest": manifest_rel, "content_dir": content_dir_rel}]

    def test_install_creates_and_updates_skills(self):
        """Re-running the hook updates manifest-owned fields on existing skills."""
        app_path = frappe.get_app_path(TEST_APP)
        with tempfile.TemporaryDirectory(dir=app_path) as tmp_abs:
            rel = os.path.relpath(tmp_abs, app_path)
            skill_id = self._track("hook_test_create")
            content_path = os.path.join(tmp_abs, "s.md")
            with open(content_path, "w") as f:
                f.write("# original")

            self._write_manifest(
                tmp_abs,
                [
                    {
                        "skill_id": skill_id,
                        "title": "Original",
                        "description": "d1",
                        "content_file": "s.md",
                        "status": "Published",
                        "visibility": "Public",
                        "skill_type": "Workflow",
                    }
                ],
            )
            manifest_rel = os.path.join(rel, "manifest.json")

            with _patch_assistant_skills_hook(self._fake_hook(manifest_rel, rel)):
                _install_app_skills()

            name = frappe.db.get_value("FAC Skill", {"skill_id": skill_id}, "name")
            self.assertTrue(name)
            doc = frappe.get_doc("FAC Skill", name)
            self.assertEqual(doc.title, "Original")
            self.assertEqual(doc.is_system, 1)
            self.assertEqual(doc.source_app, TEST_APP)
            self.assertEqual(doc.content, "# original")

            # Update manifest — change title, visibility (to Private, which has
            # no extra required fields), description, and content.
            with open(content_path, "w") as f:
                f.write("# updated")
            self._write_manifest(
                tmp_abs,
                [
                    {
                        "skill_id": skill_id,
                        "title": "Renamed",
                        "description": "d2",
                        "content_file": "s.md",
                        "status": "Published",
                        "visibility": "Private",
                        "skill_type": "Workflow",
                    }
                ],
            )

            with _patch_assistant_skills_hook(self._fake_hook(manifest_rel, rel)):
                _install_app_skills()

            frappe.clear_document_cache("FAC Skill", name)
            doc = frappe.get_doc("FAC Skill", name)
            self.assertEqual(doc.title, "Renamed")
            self.assertEqual(doc.visibility, "Private")
            self.assertEqual(doc.description, "d2")
            self.assertEqual(doc.content, "# updated")

    def test_install_removes_obsolete_skills(self):
        """Skills no longer in the manifest are removed for that app."""
        app_path = frappe.get_app_path(TEST_APP)
        with tempfile.TemporaryDirectory(dir=app_path) as tmp_abs:
            rel = os.path.relpath(tmp_abs, app_path)
            old_id = self._track("hook_test_obsolete")
            kept_id = self._track("hook_test_kept")

            for sid in (old_id, kept_id):
                with open(os.path.join(tmp_abs, f"{sid}.md"), "w") as f:
                    f.write(f"# {sid}")

            self._write_manifest(
                tmp_abs,
                [
                    {
                        "skill_id": old_id,
                        "title": "Old",
                        "description": "x",
                        "content_file": f"{old_id}.md",
                    },
                    {
                        "skill_id": kept_id,
                        "title": "Kept",
                        "description": "x",
                        "content_file": f"{kept_id}.md",
                    },
                ],
            )
            manifest_rel = os.path.join(rel, "manifest.json")

            with _patch_assistant_skills_hook(self._fake_hook(manifest_rel, rel)):
                _install_app_skills()

            self.assertTrue(frappe.db.exists("FAC Skill", {"skill_id": old_id}))
            self.assertTrue(frappe.db.exists("FAC Skill", {"skill_id": kept_id}))

            # Remove old_id from manifest.
            self._write_manifest(
                tmp_abs,
                [
                    {
                        "skill_id": kept_id,
                        "title": "Kept",
                        "description": "x",
                        "content_file": f"{kept_id}.md",
                    }
                ],
            )

            with _patch_assistant_skills_hook(self._fake_hook(manifest_rel, rel)):
                _install_app_skills()

            self.assertFalse(frappe.db.exists("FAC Skill", {"skill_id": old_id}))
            self.assertTrue(frappe.db.exists("FAC Skill", {"skill_id": kept_id}))


class TestResourcesHandlers(BaseAssistantTest):
    """Tests for handle_resources_list / handle_resources_read."""

    def setUp(self):
        super().setUp()
        self._created_ids = []

    def tearDown(self):
        for sid in self._created_ids:
            try:
                _delete_skill(sid)
            except Exception:
                pass
        super().tearDown()

    def _make(self, skill_id, **kwargs):
        self._created_ids.append(skill_id)
        return _make_skill(skill_id, **kwargs)

    def test_list_includes_published_public(self):
        self._make("list_pub", title="Pub", status="Published", visibility="Public")
        result = handle_resources_list()
        uris = {r["uri"] for r in result["resources"]}
        self.assertIn("fac://skills/list_pub", uris)

    def test_list_excludes_drafts_from_other_users(self):
        _ensure_user("someone_else@example.com")
        self._make(
            "list_other_draft",
            status="Draft",
            visibility="Public",
            owner_user="someone_else@example.com",
        )
        result = handle_resources_list()
        uris = {r["uri"] for r in result["resources"]}
        self.assertNotIn("fac://skills/list_other_draft", uris)

    def test_read_valid_published(self):
        self._make("read_pub", content="# content", status="Published", visibility="Public")
        result = handle_resources_read({"uri": "fac://skills/read_pub"})
        self.assertEqual(result["contents"][0]["text"], "# content")
        self.assertEqual(result["contents"][0]["mimeType"], "text/markdown")

    def test_read_unknown_uri_scheme(self):
        with self.assertRaises(ValueError):
            handle_resources_read({"uri": "http://skills/foo"})

    def test_read_invalid_skill_id(self):
        with self.assertRaises(ValueError):
            handle_resources_read({"uri": "fac://skills/bad id!"})

    def test_read_missing_skill_id(self):
        with self.assertRaises(ValueError):
            handle_resources_read({"uri": "fac://skills/"})

    def test_read_nonexistent_skill(self):
        with self.assertRaises(ValueError):
            handle_resources_read({"uri": "fac://skills/does_not_exist"})

    def test_read_other_users_draft_denied(self):
        """Draft owned by another user must not be readable."""
        _ensure_user("someone_else@example.com")
        _ensure_user("random@example.com")
        self._make(
            "draft_other",
            status="Draft",
            visibility="Public",
            owner_user="someone_else@example.com",
        )

        # Act as a non-admin, non-owner user. System Manager would bypass.
        with patch("frappe.session") as mock_session, patch(
            "frappe.get_roles", return_value=["Assistant User"]
        ):
            mock_session.user = "random@example.com"
            with self.assertRaises(frappe.PermissionError):
                handle_resources_read({"uri": "fac://skills/draft_other"})

    def test_read_own_draft_allowed(self):
        """Owner can read their own Draft."""
        owner = "owner@example.com"
        _ensure_user(owner)
        self._make("draft_own", status="Draft", visibility="Public", owner_user=owner)

        with patch("frappe.session") as mock_session, patch(
            "frappe.get_roles", return_value=["Assistant User"]
        ):
            mock_session.user = owner
            result = handle_resources_read({"uri": "fac://skills/draft_own"})
            self.assertIn("contents", result)


class TestBeforeAppUninstall(BaseAssistantTest):
    """Tests for before_app_uninstall cleanup."""

    def setUp(self):
        super().setUp()
        self._created_ids = []

    def tearDown(self):
        for sid in self._created_ids:
            try:
                _delete_skill(sid)
            except Exception:
                pass
        super().tearDown()

    def test_removes_only_source_app_skills(self):
        other_app = "some_fake_app"
        self._created_ids.extend(["uninstall_other_app_skill", "uninstall_fac_skill"])
        _make_skill(
            "uninstall_other_app_skill",
            is_system=1,
            source_app=other_app,
        )
        _make_skill(
            "uninstall_fac_skill",
            is_system=1,
            source_app="frappe_assistant_core",
        )

        before_app_uninstall(other_app)

        self.assertFalse(frappe.db.exists("FAC Skill", {"skill_id": "uninstall_other_app_skill"}))
        self.assertTrue(frappe.db.exists("FAC Skill", {"skill_id": "uninstall_fac_skill"}))

    def test_fac_self_uninstall_is_noop_here(self):
        """before_app_uninstall is a no-op when FAC itself is being uninstalled."""
        self._created_ids.append("self_uninstall_skill")
        _make_skill(
            "self_uninstall_skill",
            is_system=1,
            source_app="frappe_assistant_core",
        )
        before_app_uninstall("frappe_assistant_core")
        self.assertTrue(frappe.db.exists("FAC Skill", {"skill_id": "self_uninstall_skill"}))
