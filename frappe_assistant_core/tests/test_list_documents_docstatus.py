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
Regression tests for: https://github.com/buildswithpaul/Frappe_Assistant_Core/issues/227

list_documents applied no docstatus filter unless one was passed explicitly, so
cancelled (docstatus=2) and draft (docstatus=0) documents were returned alongside
submitted ones with their monetary fields intact. Anything aggregating the result
set produced a silently wrong total.

Submittable DocTypes now default to docstatus=1. An explicit docstatus — including
a bare list of values — is still honoured exactly as passed, and non-submittable
DocTypes are untouched.
"""

from contextlib import ExitStack, contextmanager
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.plugins.core.tools.list_documents import (
    DocumentList,
    apply_default_docstatus,
    filters_reference_docstatus,
    is_submittable,
    normalize_docstatus_filter,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest


@contextmanager
def list_documents_harness(submittable=True, rows=None):
    """Run DocumentList.execute() against mocked permissions and queries.

    Yields the patched frappe.get_list so the caller can assert on the filters
    that actually reached the database layer.
    """
    rows = [{"name": "REC-0001", "grand_total": 100}] if rows is None else rows

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
        stack.enter_context(
            patch(
                "frappe_assistant_core.plugins.core.tools.list_documents.frappe.get_meta",
                return_value=MagicMock(is_submittable=1 if submittable else 0),
            )
        )
        get_list = stack.enter_context(
            patch("frappe_assistant_core.plugins.core.tools.list_documents.frappe.get_list")
        )
        get_list.side_effect = [rows, [{"count": len(rows)}]]

        yield get_list


def data_call_filters(get_list):
    """Filters passed to the data query."""
    return get_list.call_args_list[0].kwargs["filters"]


def count_call_filters(get_list):
    """Filters passed to the pagination count query."""
    return get_list.call_args_list[1].kwargs["filters"]


class TestDocstatusHelpers(BaseAssistantTest):
    """The filter-inspection helpers must recognise every form Frappe accepts."""

    def test_dict_filter_docstatus_detected(self):
        self.assertTrue(filters_reference_docstatus({"docstatus": 2}))
        self.assertFalse(filters_reference_docstatus({"status": "Paid"}))

    def test_list_filter_docstatus_detected(self):
        self.assertTrue(filters_reference_docstatus([["docstatus", "=", 1]]))
        self.assertTrue(filters_reference_docstatus([["Sales Invoice", "docstatus", "=", 1]]))
        self.assertFalse(filters_reference_docstatus([["status", "=", "Paid"]]))

    def test_unwrapped_list_condition_detected(self):
        """A single condition passed without an enclosing list is still a condition."""
        self.assertTrue(filters_reference_docstatus(["docstatus", "=", 1]))
        self.assertFalse(filters_reference_docstatus(["status", "=", "Paid"]))

    def test_empty_filters_reference_nothing(self):
        self.assertFalse(filters_reference_docstatus({}))
        self.assertFalse(filters_reference_docstatus([]))
        self.assertFalse(filters_reference_docstatus(None))

    def test_bare_value_list_normalized_to_in_operator(self):
        """Frappe reads [0, 1] as [operator, value], so it has to become an `in`."""
        self.assertEqual(
            normalize_docstatus_filter({"docstatus": [0, 1]}),
            {"docstatus": ["in", [0, 1]]},
        )

    def test_operator_list_left_alone(self):
        for value in (["in", [0, 1]], ["!=", 2], [">=", 1]):
            self.assertEqual(normalize_docstatus_filter({"docstatus": value}), {"docstatus": value})

    def test_scalar_docstatus_left_alone(self):
        self.assertEqual(normalize_docstatus_filter({"docstatus": 2}), {"docstatus": 2})

    def test_caller_filters_are_not_mutated(self):
        original = {"status": "Paid"}
        with patch(
            "frappe_assistant_core.plugins.core.tools.list_documents.frappe.get_meta",
            return_value=MagicMock(is_submittable=1),
        ):
            defaulted, applied = apply_default_docstatus("Sales Invoice", original)

        self.assertTrue(applied)
        self.assertEqual(defaulted, {"status": "Paid", "docstatus": 1})
        self.assertEqual(original, {"status": "Paid"}, "caller's dict must not be mutated")

    def test_list_filters_gain_a_docstatus_condition(self):
        with patch(
            "frappe_assistant_core.plugins.core.tools.list_documents.frappe.get_meta",
            return_value=MagicMock(is_submittable=1),
        ):
            defaulted, applied = apply_default_docstatus("Sales Invoice", [["status", "=", "Paid"]])

        self.assertTrue(applied)
        self.assertEqual(defaulted, [["status", "=", "Paid"], ["docstatus", "=", 1]])

    def test_unknown_doctype_is_not_submittable(self):
        """A meta lookup failure must not break the query path."""
        self.assertFalse(is_submittable("No Such DocType 227"))

    def test_real_doctype_submittability(self):
        """Sanity-check the helper against live metadata rather than a mock."""
        self.assertFalse(is_submittable("ToDo"))
        if not frappe.db.exists("DocType", "Sales Invoice"):
            self.skipTest("ERPNext not installed")
        self.assertTrue(is_submittable("Sales Invoice"))


class TestListDocumentsDocstatusDefault(BaseAssistantTest):
    """End-to-end behaviour of list_documents for submittable DocTypes."""

    def test_unfiltered_query_returns_submitted_only(self):
        """Regression: cancelled and draft documents used to be returned by default."""
        with list_documents_harness(submittable=True) as get_list:
            result = DocumentList().execute(
                {"doctype": "Purchase Invoice", "fields": ["name", "outstanding_amount"]}
            )

        self.assertTrue(result.get("success"), result)
        self.assertEqual(data_call_filters(get_list), {"docstatus": 1})

    def test_applied_default_is_visible_in_filters_applied(self):
        with list_documents_harness(submittable=True) as get_list:
            result = DocumentList().execute({"doctype": "Purchase Invoice"})

        self.assertEqual(result["filters_applied"].get("docstatus"), 1)
        self.assertIn("docstatus=1 applied by default", result["message"])

    def test_count_query_uses_the_same_filters(self):
        """A count that disagrees with the data query is its own reporting bug."""
        with list_documents_harness(submittable=True) as get_list:
            DocumentList().execute({"doctype": "Purchase Invoice"})

        self.assertEqual(count_call_filters(get_list), {"docstatus": 1})
        self.assertEqual(data_call_filters(get_list), count_call_filters(get_list))

    def test_explicit_cancelled_is_honoured(self):
        with list_documents_harness(submittable=True) as get_list:
            result = DocumentList().execute({"doctype": "Purchase Invoice", "filters": {"docstatus": 2}})

        self.assertEqual(data_call_filters(get_list), {"docstatus": 2})
        self.assertEqual(result["filters_applied"], {"docstatus": 2})
        self.assertNotIn("applied by default", result["message"])

    def test_explicit_draft_and_submitted_list_is_honoured(self):
        with list_documents_harness(submittable=True) as get_list:
            result = DocumentList().execute({"doctype": "Purchase Invoice", "filters": {"docstatus": [0, 1]}})

        self.assertEqual(data_call_filters(get_list), {"docstatus": ["in", [0, 1]]})
        self.assertEqual(result["filters_applied"], {"docstatus": ["in", [0, 1]]})

    def test_explicit_docstatus_alongside_other_filters(self):
        with list_documents_harness(submittable=True) as get_list:
            DocumentList().execute(
                {
                    "doctype": "Purchase Invoice",
                    "filters": {"supplier": "SUP-0001", "docstatus": 0},
                }
            )

        self.assertEqual(data_call_filters(get_list), {"supplier": "SUP-0001", "docstatus": 0})

    def test_other_filters_are_preserved_when_defaulting(self):
        with list_documents_harness(submittable=True) as get_list:
            DocumentList().execute({"doctype": "Purchase Invoice", "filters": {"status": "Unpaid"}})

        self.assertEqual(data_call_filters(get_list), {"status": "Unpaid", "docstatus": 1})

    def test_list_style_filters_get_the_default(self):
        with list_documents_harness(submittable=True) as get_list:
            DocumentList().execute({"doctype": "Purchase Invoice", "filters": [["status", "=", "Unpaid"]]})

        self.assertEqual(data_call_filters(get_list), [["status", "=", "Unpaid"], ["docstatus", "=", 1]])

    def test_non_submittable_doctype_is_untouched(self):
        with list_documents_harness(submittable=False) as get_list:
            result = DocumentList().execute(
                {"doctype": "Customer", "filters": {"customer_group": "Commercial"}}
            )

        self.assertEqual(data_call_filters(get_list), {"customer_group": "Commercial"})
        self.assertNotIn("applied by default", result["message"])

    def test_non_submittable_doctype_without_filters_is_untouched(self):
        with list_documents_harness(submittable=False) as get_list:
            DocumentList().execute({"doctype": "Customer"})

        self.assertEqual(data_call_filters(get_list), {})
