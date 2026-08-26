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
Regression tests for:
- Bug: count query causes "Unknown column 'table.scalar' in WHERE" on MariaDB
  when filters include docstatus (all submittable DocTypes).
- Bug: order_by="" passes empty string to frappe.get_list;
  "creation desc" hardcode overrides Frappe's own smart default ordering.
"""

from contextlib import ExitStack, contextmanager
from unittest.mock import patch

from frappe_assistant_core.plugins.core.tools.list_documents import DocumentList
from frappe_assistant_core.tests.base_test import BaseAssistantTest


@contextmanager
def list_harness(submittable=False, rows=None):
    """Minimal harness: mock permissions + frappe.get_list, yield the mock."""
    rows = rows if rows is not None else [{"name": "REC-0001"}]
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
                side_effect=lambda doc, *a, **kw: doc,
            )
        )
        stack.enter_context(
            patch(
                "frappe_assistant_core.plugins.core.tools.list_documents.is_submittable",
                return_value=submittable,
            )
        )
        gl = stack.enter_context(patch("frappe.get_list"))
        # First call → document rows; second call → count result
        gl.side_effect = [rows, [{"count": len(rows)}]]
        yield gl


class TestCountQueryNoDict(BaseAssistantTest):
    """Bug A: dict-in-fields on count call causes MariaDB scalar column error.

    The old code used fields=[{"COUNT": "name", "as": "count"}] which fails on
    MariaDB with: (1054) Unknown column 'table.scalar' in 'WHERE'
    whenever filters include docstatus (applied automatically for submittable
    DocTypes like Item Price and Sales Invoice).
    """

    def test_count_field_is_string_not_dict(self):
        """Count query fields must be strings, never dicts."""
        tool = DocumentList()
        with list_harness() as gl:
            tool.execute({"doctype": "Customer"})
            # The second get_list call is the count query
            count_fields = gl.call_args_list[1][1].get("fields", [])
            for f in count_fields:
                self.assertIsInstance(
                    f,
                    str,
                    f"Count field must be str, not {type(f).__name__}: {f!r}. "
                    "Dict-in-fields causes 'Unknown column table.scalar' on MariaDB.",
                )

    def test_count_does_not_raise_on_submittable_doctype(self):
        """Item Price + docstatus filter previously triggered the scalar error."""
        tool = DocumentList()
        with list_harness(submittable=True) as gl:
            result = tool.execute(
                {
                    "doctype": "Item Price",
                    "filters": {"item_code": "MSE1070"},
                }
            )
            self.assertTrue(result.get("success"), f"Got: {result}")

    def test_count_does_not_raise_on_sales_invoice(self):
        """Sales Invoice is submittable, so docstatus is appended to filters."""
        tool = DocumentList()
        with list_harness(submittable=True) as gl:
            result = tool.execute({"doctype": "Sales Invoice"})
            self.assertTrue(result.get("success"), f"Got: {result}")

    def test_count_string_aggregate_form(self):
        """The count query must use the 'count(name) as count' string form."""
        tool = DocumentList()
        with list_harness() as gl:
            tool.execute({"doctype": "Customer"})
            count_fields = gl.call_args_list[1][1].get("fields", [])
            self.assertIn(
                "count(name) as count",
                count_fields,
                "Expected 'count(name) as count' string in count query fields.",
            )

    def test_count_query_failure_logs_error_and_degrades_has_more_conservatively(self):
        """When count query fails, log error, set total_count=None, and degrade has_more to True for a full page."""
        tool = DocumentList()
        # Full page of 20 rows
        full_page = [{"name": f"REC-{i:04d}"} for i in range(20)]
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
                    side_effect=lambda doc, *a, **kw: doc,
                )
            )
            stack.enter_context(
                patch(
                    "frappe_assistant_core.plugins.core.tools.list_documents.is_submittable",
                    return_value=False,
                )
            )
            log_error_mock = stack.enter_context(
                patch("frappe_assistant_core.plugins.core.tools.list_documents.frappe.log_error")
            )
            gl = stack.enter_context(
                patch("frappe_assistant_core.plugins.core.tools.list_documents.frappe.get_list")
            )
            # First call succeeds with full page; second call (count) raises Exception
            gl.side_effect = [full_page, Exception("Database connection error")]

            result = tool.execute({"doctype": "Customer", "limit": 20})

            self.assertTrue(result.get("success"))
            self.assertIsNone(result.get("total_count"))
            # On a full page (20 >= limit), has_more must degrade conservatively to True
            self.assertTrue(result.get("has_more"))
            log_error_mock.assert_called_once()

    def test_count_query_failure_partial_page_has_more_false(self):
        """When count query fails on a partial page (< limit), has_more is False."""
        tool = DocumentList()
        partial_page = [{"name": f"REC-{i:04d}"} for i in range(5)]
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
                    side_effect=lambda doc, *a, **kw: doc,
                )
            )
            stack.enter_context(
                patch(
                    "frappe_assistant_core.plugins.core.tools.list_documents.is_submittable",
                    return_value=False,
                )
            )
            stack.enter_context(
                patch("frappe_assistant_core.plugins.core.tools.list_documents.frappe.log_error")
            )
            gl = stack.enter_context(
                patch("frappe_assistant_core.plugins.core.tools.list_documents.frappe.get_list")
            )
            gl.side_effect = [partial_page, Exception("Database connection error")]

            result = tool.execute({"doctype": "Customer", "limit": 20})

            self.assertTrue(result.get("success"))
            self.assertIsNone(result.get("total_count"))
            # Partial page (5 < 20), has_more is False
            self.assertFalse(result.get("has_more"))


class TestOrderByBehaviour(BaseAssistantTest):
    """Bug B: empty/missing order_by must not override Frappe's default ordering.

    The old code hardcoded "creation desc", overriding Frappe's own smart default
    (idx desc, creation desc from list view config). Additionally, an empty string
    from API clients bypassed the default and caused potential SQL issues.
    """

    def test_empty_string_order_by_uses_frappe_default(self):
        """order_by='' must NOT reach frappe.get_list as empty string."""
        tool = DocumentList()
        with list_harness() as gl:
            tool.execute({"doctype": "Customer", "order_by": ""})
            actual = gl.call_args_list[0][1].get("order_by", "")
            self.assertNotEqual(
                actual,
                "",
                "Empty string order_by must be replaced with a valid default, "
                "not passed through as empty string to frappe.get_list.",
            )

    def test_omitted_order_by_uses_frappe_sentinel(self):
        """When order_by is not supplied, KEEP_DEFAULT_ORDERING must be used."""
        tool = DocumentList()
        with list_harness() as gl:
            tool.execute({"doctype": "Customer"})
            actual = gl.call_args_list[0][1].get("order_by", "")
            self.assertEqual(
                actual,
                "KEEP_DEFAULT_ORDERING",
                f"Expected 'KEEP_DEFAULT_ORDERING', got: {actual!r}",
            )

    def test_explicit_order_by_is_honoured(self):
        """A non-empty order_by must still be passed through unchanged."""
        tool = DocumentList()
        with list_harness() as gl:
            tool.execute({"doctype": "Customer", "order_by": "modified desc"})
            actual = gl.call_args_list[0][1].get("order_by")
            self.assertEqual(actual, "modified desc")

    def test_none_order_by_uses_frappe_sentinel(self):
        """Explicitly passing order_by=None must fall back to KEEP_DEFAULT_ORDERING."""
        tool = DocumentList()
        with list_harness() as gl:
            tool.execute({"doctype": "Customer", "order_by": None})
            actual = gl.call_args_list[0][1].get("order_by", "")
            self.assertEqual(
                actual,
                "KEEP_DEFAULT_ORDERING",
                f"Expected 'KEEP_DEFAULT_ORDERING', got: {actual!r}",
            )
