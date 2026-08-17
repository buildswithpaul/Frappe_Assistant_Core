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
Regression tests for: https://github.com/buildswithpaul/Frappe_Assistant_Core/issues/228

A Link-field filter value that matched no record produced count: 0 with
success: true and nothing else. "Zero records" and "that entity does not exist"
were indistinguishable, so an approximate name passed straight into a filter read
as a legitimate business answer.

Zero-row results now carry unresolved_filters with ranked search_link candidates
for each Link value that resolves to nothing. Non-empty results are untouched and
pay no extra query.
"""

from contextlib import ExitStack, contextmanager
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.plugins.core.tools.list_documents import (
    DocumentList,
    equality_filter_pairs,
    link_filter_targets,
    link_suggestions,
    resolve_unmatched_link_filters,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest


def link_meta(**fields):
    """A meta stub whose get_field() answers from a {fieldname: fieldtype/options} map."""

    def get_field(fieldname):
        spec = fields.get(fieldname)
        if not spec:
            return None
        fieldtype, options = spec
        return MagicMock(fieldtype=fieldtype, options=options)

    return MagicMock(is_submittable=0, get_field=get_field)


@contextmanager
def resolution_harness(existing=(), suggestions=None, has_permission=True, meta=None):
    """Patch the metadata, existence and search_link lookups the resolver depends on.

    `existing` names the records that resolve; anything else is unmatched.
    `suggestions` maps a search_link query to the candidate values it returns.
    """
    suggestions = suggestions or {}

    def db_exists(doctype, name=None, **kwargs):
        if doctype == "DocType":
            return True
        return name in existing

    def search_link(doctype, query, filters=None):
        return {
            "success": True,
            "results": [{"value": value} for value in suggestions.get(query, [])],
        }

    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "frappe_assistant_core.plugins.core.tools.list_documents.frappe.get_meta",
                return_value=meta if meta is not None else link_meta(customer=("Link", "Customer")),
            )
        )
        stack.enter_context(
            patch(
                "frappe_assistant_core.plugins.core.tools.list_documents.frappe.db.exists",
                side_effect=db_exists,
            )
        )
        stack.enter_context(
            patch(
                "frappe_assistant_core.plugins.core.tools.list_documents.frappe.has_permission",
                return_value=has_permission,
            )
        )
        search = stack.enter_context(
            patch(
                "frappe_assistant_core.plugins.core.tools.search_tools.SearchTools.search_link",
                side_effect=search_link,
            )
        )
        yield search


@contextmanager
def list_documents_harness(rows, meta=None, existing=(), suggestions=None):
    """Run DocumentList.execute() end to end with permissions and queries mocked."""
    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "frappe_assistant_core.core.security_config.validate_document_access",
                return_value={"success": True, "role": "Default"},
            )
        )
        stack.enter_context(
            patch(
                "frappe_assistant_core.core.security_config.filter_sensitive_fields",
                side_effect=lambda doc, _doctype, _role: doc,
            )
        )
        stack.enter_context(
            patch(
                "frappe_assistant_core.plugins.core.tools.list_documents.frappe.session",
                MagicMock(user="analyst@example.com"),
            )
        )
        get_list = stack.enter_context(
            patch("frappe_assistant_core.plugins.core.tools.list_documents.frappe.get_list")
        )
        get_list.side_effect = [rows, [{"count": len(rows)}]]
        search = stack.enter_context(
            resolution_harness(existing=existing, suggestions=suggestions, meta=meta)
        )
        yield get_list, search


class TestEqualityFilterPairs(BaseAssistantTest):
    """Only equality comparisons against a single value can be existence-checked."""

    def test_plain_string_values(self):
        self.assertEqual(
            equality_filter_pairs({"customer": "Acme", "status": "Open"}),
            [("customer", "Acme"), ("status", "Open")],
        )

    def test_explicit_equality_operator(self):
        self.assertEqual(equality_filter_pairs({"customer": ["=", "Acme"]}), [("customer", "Acme")])

    def test_fuzzy_and_set_operators_excluded(self):
        """`like` and `in` already say the caller does not know the exact value."""
        for value in (["like", "%acme%"], ["in", ["A", "B"]], ["!=", "Acme"], [">", "2024-01-01"]):
            self.assertEqual(equality_filter_pairs({"customer": value}), [])

    def test_non_string_values_excluded(self):
        self.assertEqual(equality_filter_pairs({"docstatus": 1, "grand_total": 100}), [])

    def test_list_style_conditions(self):
        self.assertEqual(
            equality_filter_pairs([["customer", "=", "Acme"], ["status", "like", "%Open%"]]),
            [("customer", "Acme")],
        )

    def test_doctype_qualified_conditions(self):
        self.assertEqual(
            equality_filter_pairs([["Sales Order", "customer", "=", "Acme"]]),
            [("customer", "Acme")],
        )

    def test_unwrapped_condition(self):
        self.assertEqual(equality_filter_pairs(["customer", "=", "Acme"]), [("customer", "Acme")])

    def test_empty_filters(self):
        for filters in ({}, [], None):
            self.assertEqual(equality_filter_pairs(filters), [])


class TestLinkFilterTargets(BaseAssistantTest):
    """Only Link fields have a target DocType to resolve a value against."""

    def test_link_field_resolves_to_its_target(self):
        with patch(
            "frappe_assistant_core.plugins.core.tools.list_documents.frappe.get_meta",
            return_value=link_meta(customer=("Link", "Customer"), status=("Select", None)),
        ):
            targets = link_filter_targets("Sales Order", {"customer": "Acme", "status": "Open"})

        self.assertEqual(targets, {"customer": ("Customer", "Acme")})

    def test_dynamic_link_and_data_fields_ignored(self):
        with patch(
            "frappe_assistant_core.plugins.core.tools.list_documents.frappe.get_meta",
            return_value=link_meta(party=("Dynamic Link", "party_type"), reference=("Data", None)),
        ):
            targets = link_filter_targets("Payment Entry", {"party": "Acme", "reference": "X"})

        self.assertEqual(targets, {})

    def test_unknown_field_ignored(self):
        with patch(
            "frappe_assistant_core.plugins.core.tools.list_documents.frappe.get_meta",
            return_value=link_meta(),
        ):
            self.assertEqual(link_filter_targets("Sales Order", {"nope": "Acme"}), {})

    def test_empty_value_ignored(self):
        with patch(
            "frappe_assistant_core.plugins.core.tools.list_documents.frappe.get_meta",
            return_value=link_meta(customer=("Link", "Customer")),
        ):
            self.assertEqual(link_filter_targets("Sales Order", {"customer": ""}), {})


class TestLinkSuggestions(BaseAssistantTest):
    """Candidates come from the existing search_link resolution."""

    def test_full_value_match(self):
        with resolution_harness(suggestions={"Acme Corp": ["Acme Corporation", "Acme Corp Ltd"]}):
            self.assertEqual(
                link_suggestions("Customer", "Acme Corp"),
                ["Acme Corporation", "Acme Corp Ltd"],
            )

    def test_first_word_fallback_for_late_typos(self):
        """search_link matches on substrings, so a typo after the first word finds nothing."""
        with resolution_harness(suggestions={"Acme": ["Acme Corporation"]}) as search:
            self.assertEqual(link_suggestions("Customer", "Acme Corpp"), ["Acme Corporation"])

        self.assertEqual([call.kwargs["query"] for call in search.call_args_list], ["Acme Corpp", "Acme"])

    def test_no_fallback_when_full_value_matches(self):
        with resolution_harness(suggestions={"Acme Corp": ["Acme Corporation"]}) as search:
            link_suggestions("Customer", "Acme Corp")

        self.assertEqual(search.call_count, 1, "a successful lookup must not be retried")

    def test_single_word_value_is_looked_up_once(self):
        with resolution_harness(suggestions={}) as search:
            self.assertEqual(link_suggestions("Customer", "Acme"), [])

        self.assertEqual(search.call_count, 1)

    def test_suggestions_are_capped(self):
        many = [f"Candidate {i}" for i in range(20)]
        with resolution_harness(suggestions={"Acme": many}):
            self.assertEqual(len(link_suggestions("Customer", "Acme")), 5)

    def test_failed_search_yields_no_suggestions(self):
        with patch(
            "frappe_assistant_core.plugins.core.tools.search_tools.SearchTools.search_link",
            return_value={"success": False, "error": "No read permission"},
        ):
            self.assertEqual(link_suggestions("Customer", "Acme"), [])


class TestResolveUnmatchedLinkFilters(BaseAssistantTest):
    """The resolver reports only values that genuinely resolve to nothing."""

    def test_unmatched_value_is_reported_with_candidates(self):
        with resolution_harness(
            existing=("Acme Corporation",), suggestions={"Acme Corp": ["Acme Corporation"]}
        ):
            unresolved = resolve_unmatched_link_filters("Sales Order", {"customer": "Acme Corp"})

        self.assertEqual(
            unresolved,
            {
                "customer": {
                    "value": "Acme Corp",
                    "matched": False,
                    "target_doctype": "Customer",
                    "suggestions": ["Acme Corporation"],
                }
            },
        )

    def test_existing_value_is_not_reported(self):
        """Genuinely no matching records — the filter value itself is fine."""
        with resolution_harness(existing=("Acme Corp",), suggestions={"Acme Corp": ["Acme Corp"]}):
            unresolved = resolve_unmatched_link_filters("Sales Order", {"customer": "Acme Corp"})

        self.assertEqual(unresolved, {})

    def test_unmatched_value_without_candidates_still_reported(self):
        """Knowing the value does not exist is the useful half of the signal."""
        with resolution_harness(existing=(), suggestions={}):
            unresolved = resolve_unmatched_link_filters("Sales Order", {"customer": "Zzz"})

        self.assertEqual(unresolved["customer"]["matched"], False)
        self.assertEqual(unresolved["customer"]["suggestions"], [])

    def test_multiple_link_filters_resolved_independently(self):
        meta = link_meta(customer=("Link", "Customer"), item_code=("Link", "Item"))
        with resolution_harness(
            existing=("Widget",),
            suggestions={"Acme Corp": ["Acme Corporation"]},
            meta=meta,
        ):
            unresolved = resolve_unmatched_link_filters(
                "Sales Order", {"customer": "Acme Corp", "item_code": "Widget"}
            )

        self.assertEqual(list(unresolved), ["customer"], "only the unmatched filter is reported")
        self.assertEqual(unresolved["customer"]["suggestions"], ["Acme Corporation"])

    def test_no_read_permission_reports_nothing(self):
        """Existence of a record in an unreadable DocType is not ours to disclose."""
        with resolution_harness(existing=(), has_permission=False):
            unresolved = resolve_unmatched_link_filters("Sales Order", {"customer": "Acme Corp"})

        self.assertEqual(unresolved, {})

    def test_resolution_failure_is_swallowed(self):
        """Diagnostics must never turn a successful query into a failure."""
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "frappe_assistant_core.plugins.core.tools.list_documents.frappe.get_meta",
                    return_value=link_meta(customer=("Link", "Customer")),
                )
            )
            stack.enter_context(
                patch(
                    "frappe_assistant_core.plugins.core.tools.list_documents.frappe.db.exists",
                    side_effect=RuntimeError("boom"),
                )
            )
            stack.enter_context(
                patch("frappe_assistant_core.plugins.core.tools.list_documents.frappe.log_error")
            )
            unresolved = resolve_unmatched_link_filters("Sales Order", {"customer": "Acme Corp"})

        self.assertEqual(unresolved, {})


class TestListDocumentsUnresolvedFilters(BaseAssistantTest):
    """End-to-end behaviour of the zero-row path."""

    def test_zero_rows_with_unmatched_link_filter_returns_suggestions(self):
        with list_documents_harness(
            rows=[],
            existing=("Acme Corporation",),
            suggestions={"Acme Corp": ["Acme Corporation"]},
        ) as (_get_list, _search):
            result = DocumentList().execute({"doctype": "Sales Order", "filters": {"customer": "Acme Corp"}})

        self.assertTrue(result["success"], "an unresolved filter is not an error")
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["unresolved_filters"]["customer"]["suggestions"], ["Acme Corporation"])
        self.assertIn("unresolved filter", result["message"])

    def test_zero_rows_with_resolvable_link_filter_stays_quiet(self):
        with list_documents_harness(rows=[], existing=("Acme Corp",)) as (_get_list, _search):
            result = DocumentList().execute({"doctype": "Sales Order", "filters": {"customer": "Acme Corp"}})

        self.assertEqual(result["count"], 0)
        self.assertNotIn("unresolved_filters", result)
        self.assertNotIn("unresolved filter", result["message"])

    def test_non_empty_result_incurs_no_extra_queries(self):
        with list_documents_harness(rows=[{"name": "SO-0001", "customer": "Acme Corp"}], existing=()) as (
            get_list,
            search,
        ):
            result = DocumentList().execute({"doctype": "Sales Order", "filters": {"customer": "Acme Corp"}})

        self.assertEqual(result["count"], 1)
        self.assertNotIn("unresolved_filters", result)
        search.assert_not_called()
        self.assertEqual(get_list.call_count, 2, "only the data and count queries")

    def test_zero_rows_without_link_filters_stays_quiet(self):
        with list_documents_harness(rows=[], existing=()) as (_get_list, search):
            result = DocumentList().execute({"doctype": "Sales Order", "filters": {"status": "Closed"}})

        self.assertNotIn("unresolved_filters", result)
        search.assert_not_called()

    def test_multiple_unmatched_link_filters_in_one_call(self):
        meta = link_meta(customer=("Link", "Customer"), item_code=("Link", "Item"))
        with list_documents_harness(
            rows=[],
            meta=meta,
            existing=(),
            suggestions={"Acme Corp": ["Acme Corporation"], "Widgt": ["Widget"]},
        ) as (_get_list, _search):
            result = DocumentList().execute(
                {
                    "doctype": "Sales Order",
                    "filters": {"customer": "Acme Corp", "item_code": "Widgt"},
                }
            )

        self.assertEqual(sorted(result["unresolved_filters"]), ["customer", "item_code"])
        self.assertEqual(result["unresolved_filters"]["item_code"]["suggestions"], ["Widget"])
        self.assertEqual(result["unresolved_filters"]["customer"]["target_doctype"], "Customer")

    def test_real_metadata_link_target_lookup(self):
        """Sanity-check target resolution against live metadata rather than a mock."""
        if not frappe.db.exists("DocType", "Sales Order"):
            self.skipTest("ERPNext not installed")

        self.assertEqual(
            link_filter_targets("Sales Order", {"customer": "Whatever"}),
            {"customer": ("Customer", "Whatever")},
        )
