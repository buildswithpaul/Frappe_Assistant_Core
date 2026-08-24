# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Test suite for the unified search_documents tool.

Covers argument routing across the three search modes, and the permission
invariants those modes must hold (issue #189).
"""

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.plugins.core.tools import search_tools
from frappe_assistant_core.plugins.core.tools.search_documents import SearchDocuments
from frappe_assistant_core.plugins.core.tools.search_tools import SearchTools
from frappe_assistant_core.tests.base_test import BaseAssistantTest


def stub_meta(search_fields="", title_field=None, fields=None):
    """A frappe.get_meta stand-in carrying only what search needs."""
    meta = MagicMock()
    meta.search_fields = search_fields
    meta.title_field = title_field
    meta.fields = fields or []

    by_name = {field.fieldname: field for field in meta.fields}
    meta.get_field.side_effect = by_name.get

    return meta


def stub_field(fieldname, fieldtype="Data", hidden=False):
    return MagicMock(fieldname=fieldname, fieldtype=fieldtype, hidden=hidden)


class TestSearchToolRegistration(BaseAssistantTest):
    """The merge collapsed three tools into one — the registry should agree."""

    def setUp(self):
        super().setUp()
        self.registry = get_tool_registry()

    def test_search_documents_is_registered(self):
        tool_names = [tool["name"] for tool in self.registry.get_available_tools()]
        self.assertIn("search_documents", tool_names, f"Available: {tool_names}")

    def test_merged_away_tools_are_gone(self):
        """search_doctype and search_link are now modes of search_documents."""
        tool_names = [tool["name"] for tool in self.registry.get_available_tools()]
        self.assertNotIn("search_doctype", tool_names)
        self.assertNotIn("search_link", tool_names)

    def test_schema_exposes_the_routing_arguments(self):
        properties = SearchDocuments().inputSchema["properties"]

        for argument in ("query", "doctype", "purpose", "filters", "limit"):
            self.assertIn(argument, properties)

        self.assertEqual(properties["purpose"]["enum"], ["documents", "link_value"])


class TestSearchDocumentsRouting(BaseAssistantTest):
    """Each mode must be reachable from arguments alone."""

    def setUp(self):
        super().setUp()
        self.tool = SearchDocuments()

    def test_no_doctype_routes_to_global_search(self):
        with patch.object(SearchTools, "global_search", return_value={"success": True}) as global_search:
            self.tool.execute({"query": "Grant"})

        global_search.assert_called_once_with(query="Grant", limit=20)

    def test_doctype_routes_to_doctype_search(self):
        with patch.object(SearchTools, "search_doctype", return_value={"success": True}) as doctype_search:
            self.tool.execute({"query": "Grant", "doctype": "Customer", "filters": {"disabled": 0}})

        doctype_search.assert_called_once_with(
            doctype="Customer", query="Grant", limit=20, filters={"disabled": 0}
        )

    def test_link_purpose_routes_to_link_search(self):
        with patch.object(SearchTools, "search_link", return_value={"success": True}) as link_search:
            self.tool.execute(
                {"query": "com", "doctype": "Customer Group", "purpose": "link_value", "limit": 5}
            )

        link_search.assert_called_once_with(doctype="Customer Group", query="com", filters={}, limit=5)

    def test_link_purpose_without_doctype_is_rejected(self):
        result = self.tool.execute({"query": "com", "purpose": "link_value"})

        self.assertFalse(result.get("success"))
        self.assertIn("doctype", result.get("error", ""))

    def test_filters_without_doctype_are_rejected_not_dropped(self):
        """Silently ignoring filters would return a broader set than requested."""
        with patch.object(SearchTools, "global_search") as global_search:
            result = self.tool.execute({"query": "Grant", "filters": {"status": "Active"}})

        self.assertFalse(result.get("success"))
        global_search.assert_not_called()

    def test_limit_is_clamped_to_the_maximum(self):
        with patch.object(SearchTools, "global_search", return_value={"success": True}) as global_search:
            self.tool.execute({"query": "Grant", "limit": 5000})

        self.assertEqual(global_search.call_args.kwargs["limit"], 100)

    def test_unusable_limit_falls_back_to_the_default(self):
        with patch.object(SearchTools, "global_search", return_value={"success": True}) as global_search:
            self.tool.execute({"query": "Grant", "limit": "many"})

        self.assertEqual(global_search.call_args.kwargs["limit"], 20)


class TestGlobalSearch(BaseAssistantTest):
    """Global search reads the full-text index, then re-checks row access."""

    def test_indexed_hits_are_filtered_by_row_permissions(self):
        """Regression guard for #189, extended to the full-text index.

        frappe.utils.global_search.search filters by DocType-level read access
        only, so a hit the user cannot read row-wise must be dropped here.
        """
        indexed = [
            {"doctype": "Sales Invoice", "name": "SINV-0001", "content": "customer || Allowed Co"},
            {"doctype": "Sales Invoice", "name": "SINV-0002", "content": "customer || Blocked Co"},
        ]

        with ExitStack() as stack:
            stack.enter_context(patch("frappe.utils.global_search.search", return_value=indexed))
            get_all = stack.enter_context(
                patch.object(
                    search_tools.frappe,
                    "get_all",
                    side_effect=AssertionError("frappe.get_all bypasses permissions"),
                )
            )
            get_list = stack.enter_context(patch.object(search_tools.frappe, "get_list"))
            # Only the first invoice survives the permission-aware re-query.
            get_list.return_value = [{"name": "SINV-0001"}]

            result = SearchTools.global_search(query="Co", limit=20)

        self.assertTrue(result.get("success"), result)
        get_all.assert_not_called()
        self.assertEqual(result["index"], "__global_search")
        self.assertEqual([hit["name"] for hit in result["results"]], ["SINV-0001"])
        self.assertFalse(get_list.call_args.kwargs.get("ignore_permissions", True))

    def test_unreadable_doctype_fails_closed(self):
        """If the re-query errors, the hit is dropped rather than trusted."""
        indexed = [{"doctype": "Salary Slip", "name": "SAL-0001", "content": "secret"}]

        with ExitStack() as stack:
            stack.enter_context(patch("frappe.utils.global_search.search", return_value=indexed))
            stack.enter_context(
                patch.object(search_tools.frappe, "get_list", side_effect=Exception("no permission"))
            )

            result = SearchTools.global_search(query="secret", limit=20)

        self.assertTrue(result.get("success"), result)
        self.assertEqual(result["results"], [])

    def test_duplicate_index_hits_are_collapsed(self):
        """The index yields a row per matched word, so multi-word queries repeat."""
        indexed = [
            {"doctype": "Customer", "name": "CUST-0001", "content": "Grant Plastics"},
            {"doctype": "Customer", "name": "CUST-0001", "content": "Grant Plastics"},
        ]

        with ExitStack() as stack:
            stack.enter_context(patch("frappe.utils.global_search.search", return_value=indexed))
            get_list = stack.enter_context(patch.object(search_tools.frappe, "get_list"))
            get_list.return_value = [{"name": "CUST-0001"}]

            result = SearchTools.global_search(query="Grant&Plastics", limit=20)

        self.assertEqual(len(result["results"]), 1)

    def test_falls_back_to_name_scan_when_index_is_unavailable(self):
        """Regression guard for #189: the fallback scan must stay permission-aware."""
        with ExitStack() as stack:
            stack.enter_context(
                patch("frappe.utils.global_search.search", side_effect=Exception("no such table"))
            )
            # Exactly one DocType exists and is readable, so one query runs.
            stack.enter_context(
                patch.object(search_tools.frappe.db, "exists", side_effect=lambda *a, **k: "Employee" in a)
            )
            stack.enter_context(
                patch.object(
                    search_tools.frappe,
                    "has_permission",
                    side_effect=lambda doctype, *a, **k: doctype == "Employee",
                )
            )
            get_all = stack.enter_context(
                patch.object(
                    search_tools.frappe,
                    "get_all",
                    side_effect=AssertionError("frappe.get_all bypasses DocType permissions"),
                )
            )
            get_list = stack.enter_context(patch.object(search_tools.frappe, "get_list"))
            get_list.return_value = [{"name": "EMP-0001"}]

            result = SearchTools.global_search(query="EMP", limit=20)

        self.assertTrue(result.get("success"), result)
        get_all.assert_not_called()
        self.assertEqual(result["index"], "name_scan")
        self.assertTrue(get_list.called, "the fallback scan must query via frappe.get_list")
        for call in get_list.call_args_list:
            self.assertFalse(
                call.kwargs.get("ignore_permissions", True),
                "the fallback scan must pass ignore_permissions=False",
            )

    def test_index_hit_removed_by_permissions_does_not_trigger_the_fallback(self):
        """An empty-after-filtering result is the right answer, not a reason to rescan."""
        indexed = [{"doctype": "Sales Invoice", "name": "SINV-0002", "content": "blocked"}]

        with ExitStack() as stack:
            stack.enter_context(patch("frappe.utils.global_search.search", return_value=indexed))
            db_exists = stack.enter_context(patch.object(search_tools.frappe.db, "exists"))
            get_list = stack.enter_context(patch.object(search_tools.frappe, "get_list"))
            get_list.return_value = []

            result = SearchTools.global_search(query="blocked", limit=20)

        self.assertEqual(result["results"], [])
        self.assertEqual(result["index"], "__global_search")
        db_exists.assert_not_called()

    def test_empty_fallback_result_explains_itself(self):
        """An empty name_scan must not read as proof the record does not exist."""
        with ExitStack() as stack:
            stack.enter_context(
                patch("frappe.utils.global_search.search", side_effect=Exception("no such table"))
            )
            stack.enter_context(patch.object(search_tools.frappe.db, "exists", return_value=False))

            result = SearchTools.global_search(query="Nothing", limit=10)

        self.assertTrue(result.get("success"), result)
        self.assertEqual(result["index"], "name_scan")
        self.assertEqual(result["count"], 0)
        self.assertIn("full-text index", result.get("message", ""))

    def test_successful_search_carries_no_caveat(self):
        """The caveat is for empty fallbacks only — no noise on a real hit."""
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "frappe.utils.global_search.search",
                    return_value=[{"doctype": "Customer", "name": "CUST-0001", "content": "x"}],
                )
            )
            get_list = stack.enter_context(patch.object(search_tools.frappe, "get_list"))
            get_list.return_value = [{"name": "CUST-0001"}]

            result = SearchTools.global_search(query="x", limit=10)

        self.assertEqual(result["count"], 1)
        self.assertNotIn("message", result)

    def test_empty_query_is_rejected(self):
        result = SearchTools.global_search(query="   ")

        self.assertFalse(result.get("success"))


class TestDoctypeSearch(BaseAssistantTest):
    """Doctype-scoped search matches the DocType's own declared search fields."""

    def test_uses_permission_aware_query(self):
        """Regression guard for #189: never frappe.get_all."""
        with ExitStack() as stack:
            stack.enter_context(patch.object(search_tools.frappe.db, "exists", return_value=True))
            stack.enter_context(patch.object(search_tools.frappe, "has_permission", return_value=True))
            stack.enter_context(
                patch.object(
                    search_tools.frappe,
                    "get_meta",
                    return_value=stub_meta(fields=[stub_field("employee_name")]),
                )
            )
            get_all = stack.enter_context(
                patch.object(
                    search_tools.frappe,
                    "get_all",
                    side_effect=AssertionError("frappe.get_all bypasses DocType permissions"),
                )
            )
            get_list = stack.enter_context(patch.object(search_tools.frappe, "get_list"))
            get_list.return_value = [{"name": "EMP-0001", "employee_name": "Allowed"}]

            result = SearchTools.search_doctype(doctype="Employee", query="All", limit=20)

        self.assertTrue(result.get("success"), result)
        get_all.assert_not_called()
        self.assertEqual(get_list.call_count, 1)
        call = get_list.call_args_list[0]
        self.assertEqual(call.args[0], "Employee")
        self.assertFalse(call.kwargs.get("ignore_permissions", True))

    def test_declared_search_fields_beat_the_fieldtype_heuristic(self):
        meta = stub_meta(
            search_fields="customer_name,tax_id",
            title_field="customer_name",
            fields=[
                stub_field("customer_name"),
                stub_field("tax_id"),
                stub_field("some_other_field"),
            ],
        )

        fields = search_tools.resolve_search_fields(meta)

        self.assertEqual(fields, ["customer_name", "tax_id"])

    def test_heuristic_applies_only_when_nothing_is_declared(self):
        meta = stub_meta(fields=[stub_field("first_field"), stub_field("second_field")])

        self.assertEqual(search_tools.resolve_search_fields(meta), ["first_field", "second_field"])

    def test_search_field_count_is_capped(self):
        meta = stub_meta(fields=[stub_field(f"field_{i}") for i in range(20)])

        self.assertEqual(len(search_tools.resolve_search_fields(meta)), search_tools.MAX_SEARCH_FIELDS)

    def test_bulky_text_fields_are_matched_but_not_returned(self):
        """Matching a Text Editor field is useful; echoing its HTML back is not."""
        meta = stub_meta(
            search_fields="description",
            fields=[stub_field("description", fieldtype="Text Editor")],
        )

        self.assertIn("description", search_tools.resolve_search_fields(meta))
        self.assertEqual(search_tools.returnable_fields(meta, ["description"]), ["name"])

    def test_missing_doctype_is_reported(self):
        with patch.object(search_tools.frappe.db, "exists", return_value=False):
            result = SearchTools.search_doctype(doctype="Nonexistent", query="x")

        self.assertFalse(result.get("success"))
        self.assertIn("Nonexistent", result.get("error", ""))

    def test_filters_alone_are_enough(self):
        """No query text is fine when the caller is filtering."""
        with ExitStack() as stack:
            stack.enter_context(patch.object(search_tools.frappe.db, "exists", return_value=True))
            stack.enter_context(patch.object(search_tools.frappe, "has_permission", return_value=True))
            stack.enter_context(
                patch.object(
                    search_tools.frappe, "get_meta", return_value=stub_meta(fields=[stub_field("title")])
                )
            )
            get_list = stack.enter_context(patch.object(search_tools.frappe, "get_list"))
            get_list.return_value = []

            result = SearchTools.search_doctype(doctype="Task", query="", filters={"status": "Open"})

        self.assertTrue(result.get("success"), result)
        self.assertIsNone(get_list.call_args.kwargs["or_filters"])
        self.assertEqual(get_list.call_args.kwargs["filters"], {"status": "Open"})


class TestLinkSearch(BaseAssistantTest):
    """Link resolution delegates to Frappe so custom queries and labels apply."""

    def test_limit_reaches_frappe_as_page_length(self):
        """The old wrapper exposed no limit, pinning results to Frappe's default 10."""
        with ExitStack() as stack:
            stack.enter_context(patch.object(search_tools.frappe.db, "exists", return_value=True))
            stack.enter_context(patch.object(search_tools.frappe, "has_permission", return_value=True))
            frappe_search_link = stack.enter_context(patch("frappe.desk.search.search_link"))
            frappe_search_link.return_value = [{"value": "Commercial", "label": "Commercial"}]

            result = SearchTools.search_link(doctype="Customer Group", query="com", limit=25)

        self.assertTrue(result.get("success"), result)
        self.assertEqual(frappe_search_link.call_args.kwargs["page_length"], 25)
        self.assertEqual(result["search_mode"], "link_value")

    def test_no_read_permission_is_reported(self):
        with ExitStack() as stack:
            stack.enter_context(patch.object(search_tools.frappe.db, "exists", return_value=True))
            stack.enter_context(patch.object(search_tools.frappe, "has_permission", return_value=False))

            result = SearchTools.search_link(doctype="Customer", query="x")

        self.assertFalse(result.get("success"))
        self.assertIn("permission", result.get("error", "").lower())

    def test_list_documents_link_suggestions_still_work(self):
        """list_documents reads `value` off these results for unresolved_filters."""
        from frappe_assistant_core.plugins.core.tools import list_documents

        with patch.object(
            SearchTools,
            "search_link",
            return_value={"success": True, "results": [{"value": "Grant Plastics Ltd."}]},
        ):
            suggestions = list_documents.link_suggestions("Customer", "Grant Plastic")

        self.assertEqual(suggestions, ["Grant Plastics Ltd."])
