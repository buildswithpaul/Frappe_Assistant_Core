# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""list_documents pages with offset and says where the next page starts.

Real ToDo rows through the real tool: has_more used to compare total_count to
limit, which is only right for the first page.
"""

import uuid

import frappe

from frappe_assistant_core.plugins.core.tools.list_documents import DocumentList
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestListDocumentsOffset(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Rows are inserted once per class: the base class rolls back per class, so
        # inserting in setUp would multiply them. Each run gets a unique marker so
        # only these probe rows are counted.
        cls.marker = f"fac-offset-probe-{uuid.uuid4().hex[:12]}"
        for i in range(3):
            frappe.get_doc({"doctype": "ToDo", "description": f"{cls.marker}-{i}"}).insert()

    def setUp(self):
        super().setUp()
        self.tool = DocumentList()

    def _page(self, **extra):
        args = {
            "doctype": "ToDo",
            "filters": {"description": ["like", f"{self.marker}-%"]},
            "fields": ["name", "description"],
            "limit": 2,
            "order_by": "description asc",
        }
        args.update(extra)
        return self.tool.execute(args)

    def test_first_page_points_at_the_second(self):
        first = self._page()
        self.assertTrue(first["success"])
        self.assertEqual(first["count"], 2)
        self.assertTrue(first["has_more"])
        self.assertEqual(first["next_offset"], 2)

    def test_last_page_has_no_next_offset(self):
        last = self._page(offset=2)
        self.assertEqual(last["count"], 1)
        self.assertFalse(last["has_more"])
        self.assertNotIn("next_offset", last)

    def test_pages_do_not_overlap_and_cover_everything(self):
        first = self._page()
        second = self._page(offset=first["next_offset"])
        seen = [d["description"] for d in first["data"] + second["data"]]
        self.assertEqual(seen, [f"{self.marker}-0", f"{self.marker}-1", f"{self.marker}-2"])

    def test_negative_offset_is_refused(self):
        result = self._page(offset=-1)
        self.assertFalse(result["success"])
        self.assertIn("offset", result["error"])

    def test_offset_is_in_the_schema(self):
        self.assertEqual(self.tool.inputSchema["properties"]["offset"]["minimum"], 0)
