# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""list_documents pages with offset and says where the next page starts.

Real ToDo rows through the real tool: has_more used to compare total_count to
limit, which is only right for the first page. Pages must also tile the result
set when the caller sorts on a column that ties, so each page order ends in a
unique tie-breaker.
"""

import uuid
from unittest.mock import patch

import frappe

from frappe_assistant_core.plugins.core.tools.list_documents import DocumentList
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestListDocumentsOffset(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Rows are inserted once per class: the base class rolls back per class, so
        # inserting in setUp would multiply them. Each run gets a unique marker so
        # only these probe rows are counted. Every probe row has the same status
        # (ToDo's default "Open"), so ordering by status ties across all of them.
        cls.marker = f"fac-offset-probe-{uuid.uuid4().hex[:12]}"
        cls.probe_names = [
            frappe.get_doc({"doctype": "ToDo", "description": f"{cls.marker}-{i}"}).insert().name
            for i in range(3)
        ]

    def setUp(self):
        super().setUp()
        self.tool = DocumentList()

    def _page(self, order_by="description asc", **extra):
        args = {
            "doctype": "ToDo",
            "filters": {"description": ["like", f"{self.marker}-%"]},
            "fields": ["name", "description"],
            "limit": 2,
            "order_by": order_by,
        }
        args.update(extra)
        return self.tool.execute(args)

    def _walk_all_pages(self, order_by):
        rows, offset = [], 0
        for _ in range(10):
            page = self._page(order_by=order_by, offset=offset)
            self.assertTrue(page["success"])
            rows.extend(page["data"])
            if not page["has_more"]:
                break
            offset = page["next_offset"]
        return rows

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

    def test_tied_sort_pages_are_disjoint_and_complete(self):
        rows = self._walk_all_pages(order_by="status asc")
        names = [row["name"] for row in rows]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(set(names), set(self.probe_names))

    def test_order_by_gets_a_unique_tie_breaker(self):
        # Ties on status make page boundaries arbitrary unless name orders the rows.
        real_get_list = frappe.get_list
        with patch("frappe.get_list", side_effect=real_get_list) as get_list:
            self._page(order_by="status asc")
        paged_calls = [c for c in get_list.call_args_list if "limit_start" in c.kwargs]
        self.assertEqual(len(paged_calls), 1)
        self.assertEqual(paged_calls[0].kwargs["order_by"], "status asc, name asc")

    def test_default_order_gets_a_unique_tie_breaker(self):
        real_get_list = frappe.get_list
        with patch("frappe.get_list", side_effect=real_get_list) as get_list:
            self._page(order_by=None)
        paged_calls = [c for c in get_list.call_args_list if "limit_start" in c.kwargs]
        self.assertTrue(paged_calls[0].kwargs["order_by"].endswith(", name asc"))

    def test_name_in_order_by_is_not_repeated(self):
        real_get_list = frappe.get_list
        with patch("frappe.get_list", side_effect=real_get_list) as get_list:
            self._page(order_by="name desc")
        paged_calls = [c for c in get_list.call_args_list if "limit_start" in c.kwargs]
        self.assertEqual(paged_calls[0].kwargs["order_by"], "name desc")

    def test_negative_offset_is_refused(self):
        result = self._page(offset=-1)
        self.assertFalse(result["success"])
        self.assertIn("offset", result["error"])

    def test_non_integer_offsets_are_refused(self):
        for bad in ["abc", 2.7, True, [1]]:
            with self.subTest(offset=bad):
                result = self._page(offset=bad)
                self.assertFalse(result["success"])
                self.assertIn("offset", result["error"])

    def test_offset_past_the_end_is_empty_without_next_offset(self):
        result = self._page(offset=10)
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)
        self.assertFalse(result["has_more"])
        self.assertNotIn("next_offset", result)

    def test_offset_is_in_the_schema(self):
        self.assertEqual(self.tool.inputSchema["properties"]["offset"]["minimum"], 0)
