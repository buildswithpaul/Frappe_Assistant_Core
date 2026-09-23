# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Tests for AR prompt catalog cache invalidation.

`get_prompt_templates` caches the merged AR catalog per user for an hour.
The catalog includes this site's own Prompt Template rows, so a local write
must drop those cached entries — otherwise a template the user just created
is missing from the slash menu until the TTL expires.

Invalidation is site-wide (every user's key), not just the author's: a
template flipping to Published or Public changes what *other* users see.
"""

import frappe

from frappe_assistant_core.chat.api.prompts import _CATALOG_CACHE_PREFIX
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestPromptCatalogCache(BaseAssistantTest):
    """Prompt Template writes must invalidate the cached AR prompt catalog."""

    # Cache keys only — these need not be real Users.
    AUTHOR = "catalog-author@example.com"
    OTHER_USER = "catalog-other@example.com"
    OWNER = "Administrator"

    def setUp(self):
        super().setUp()
        self.template = None
        self._seed_catalog_cache()

    def tearDown(self):
        if self.template and frappe.db.exists("Prompt Template", self.template.name):
            self.template.delete(ignore_permissions=True)
        frappe.cache.delete_keys(_CATALOG_CACHE_PREFIX)
        super().tearDown()

    def _seed_catalog_cache(self):
        """Populate cached catalogs for two different users."""
        for user in (self.AUTHOR, self.OTHER_USER):
            frappe.cache.set_value(f"{_CATALOG_CACHE_PREFIX}{user}", {"prompts": []}, expires_in_sec=3600)

    def _cached_users(self):
        """Users whose catalog is still cached."""
        return [
            user
            for user in (self.AUTHOR, self.OTHER_USER)
            if frappe.cache.get_value(f"{_CATALOG_CACHE_PREFIX}{user}") is not None
        ]

    def _make_template(self, prompt_id="catalog_cache_probe"):
        doc = frappe.get_doc(
            {
                "doctype": "Prompt Template",
                "prompt_id": prompt_id,
                "title": "Catalog Cache Probe",
                "description": "Fixture template for catalog cache invalidation tests.",
                "template_content": "Summarise {{ subject }}.",
                "rendering_engine": "Jinja2",
                "status": "Published",
                "visibility": "Private",
                "owner_user": self.OWNER,
                "arguments": [{"argument_name": "subject", "argument_type": "string", "is_required": 1}],
            }
        )
        doc.flags.ignore_permissions = True
        doc.insert()
        return doc

    def test_insert_clears_every_users_catalog(self):
        self.assertEqual(len(self._cached_users()), 2, "cache seeding failed")

        self.template = self._make_template()

        self.assertEqual(
            self._cached_users(),
            [],
            "inserting a Prompt Template must drop every user's cached catalog",
        )

    def test_update_clears_catalog(self):
        self.template = self._make_template("catalog_cache_probe_update")
        self._seed_catalog_cache()

        self.template.status = "Draft"
        self.template.save(ignore_permissions=True)

        self.assertEqual(
            self._cached_users(),
            [],
            "publishing or unpublishing a template must invalidate the catalog",
        )

    def test_delete_clears_catalog(self):
        template = self._make_template("catalog_cache_probe_delete")
        self._seed_catalog_cache()

        template.delete(ignore_permissions=True)

        self.assertEqual(
            self._cached_users(),
            [],
            "deleting a template must invalidate the catalog",
        )

    def test_skill_writes_do_not_touch_the_prompt_catalog(self):
        """FAC Skills reach the agent via resources/list, not this cache."""
        skill = frappe.get_doc(
            {
                "doctype": "FAC Skill",
                "skill_id": "catalog-cache-probe-skill",
                "title": "Catalog Cache Probe Skill",
                "description": "Fixture skill.",
                "content": "# Probe",
                "skill_type": "Workflow",
                "status": "Published",
                "visibility": "Private",
                "owner_user": self.OWNER,
            }
        )
        skill.flags.ignore_permissions = True
        skill.insert()
        try:
            self.assertEqual(
                len(self._cached_users()),
                2,
                "skill writes must not invalidate the prompt catalog",
            )
        finally:
            skill.delete(ignore_permissions=True)
