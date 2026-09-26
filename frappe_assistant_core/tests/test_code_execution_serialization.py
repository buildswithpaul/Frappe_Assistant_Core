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
Pure-logic tests for the run_python_code subprocess result serialization.

A value the JSON encoder cannot handle (a pandas groupby keyed by a tuple or a
date) used to abort ``json.dump`` half-way through stdout, so the parent could
not parse the result and discarded the user's printed output.
"""

import datetime
import io
import json
import unittest

import frappe
import pandas as pd

from frappe_assistant_core.utils import code_execution_subprocess as child


class _Unprintable:
    def __str__(self):
        raise RuntimeError("cannot render")


class TestSerializeVariable(unittest.TestCase):
    def test_multi_column_groupby_tuple_keys_become_strings(self):
        df = pd.DataFrame({"customer": ["A", "A", "B"], "year": [2025, 2026, 2025], "amount": [1, 2, 3]})
        totals = df.groupby(["customer", "year"])["amount"].sum()

        serialized = child._serialize_variable(totals)

        self.assertEqual(serialized, {"('A', 2025)": 1, "('A', 2026)": 2, "('B', 2025)": 3})
        json.dumps(serialized)

    def test_date_and_timestamp_keys_become_strings(self):
        by_date = pd.Series([10, 20], index=[datetime.date(2026, 1, 1), datetime.date(2026, 2, 1)])
        by_timestamp = pd.Series([5], index=pd.to_datetime(["2026-03-01"]))

        self.assertEqual(child._serialize_variable(by_date), {"2026-01-01": 10, "2026-02-01": 20})
        self.assertEqual(child._serialize_variable(by_timestamp), {"2026-03-01 00:00:00": 5})

    def test_frappe_dict_rows_serialize_as_plain_dicts(self):
        rows = [frappe._dict(name="SINV-1", grand_total=100.5, posting_date=datetime.date(2026, 1, 5))]

        self.assertEqual(
            child._serialize_variable(rows),
            [{"name": "SINV-1", "grand_total": 100.5, "posting_date": "2026-01-05"}],
        )

    def test_nested_values_are_serialized_recursively(self):
        nested = {"summary": {datetime.date(2026, 1, 1): pd.Series([1, 2]).sum()}, "ids": {3, 4}}

        serialized = child._serialize_variable(nested)

        self.assertEqual(serialized["summary"], {"2026-01-01": 3})
        self.assertEqual(sorted(serialized["ids"]), [3, 4])
        json.dumps(serialized)


class TestExtractVariables(unittest.TestCase):
    def test_unserializable_variable_is_dropped_with_a_warning(self):
        env = {"__builtins__": {}, "total": 42, "broken": _Unprintable(), "label": "ok"}

        variables, warnings = child._extract_variables(env, [])

        self.assertEqual(variables, {"total": 42, "label": "ok"})
        self.assertEqual(len(warnings), 1)
        self.assertIn("broken", warnings[0])

    def test_return_variables_limits_what_is_serialized(self):
        env = {"__builtins__": {}, "total": 42, "broken": _Unprintable()}

        variables, warnings = child._extract_variables(env, ["total"])

        self.assertEqual(variables, {"total": 42})
        self.assertEqual(warnings, [])


class TestWriteResult(unittest.TestCase):
    def test_writes_exactly_one_json_document(self):
        stream = io.StringIO()

        child._write_result({"success": True, "output": "Total: 100\n", "variables": {"x": 1}}, stream)

        self.assertEqual(json.loads(stream.getvalue())["output"], "Total: 100\n")

    def test_unencodable_result_still_yields_one_valid_document_preserving_output(self):
        stream = io.StringIO()
        result = {
            "success": True,
            "output": "Grand total: 1,234,567.00\n",
            "error": "",
            "variables": {"good": 1, "bad": {("A", 2025): 1}},
        }

        child._write_result(result, stream)

        parsed = json.loads(stream.getvalue())
        self.assertFalse(parsed["success"])
        self.assertEqual(parsed["error_type"], "serialization")
        self.assertEqual(parsed["output"], "Grand total: 1,234,567.00\n")
        self.assertEqual(parsed["unserializable_variables"], ["bad"])
        self.assertIn("bad", parsed["error"])


if __name__ == "__main__":
    unittest.main()
