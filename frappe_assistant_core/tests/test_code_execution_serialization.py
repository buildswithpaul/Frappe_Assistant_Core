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
from unittest.mock import patch

import frappe
import numpy as np
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


class TestNumpyTimeValues(unittest.TestCase):
    """``tolist()`` turns datetime64/timedelta64 into integer nanoseconds."""

    def test_datetime64_scalar_is_a_date_string_not_nanoseconds(self):
        dates = pd.Series(pd.to_datetime(["2026-01-01", "2026-02-01"])).values

        self.assertEqual(child._serialize_variable(dates.max()), "2026-02-01 00:00:00")

    def test_datetime64_array_is_a_list_of_date_strings(self):
        dates = pd.Series(pd.to_datetime(["2026-01-01", "2026-02-01"])).values

        self.assertEqual(child._serialize_variable(dates), ["2026-01-01 00:00:00", "2026-02-01 00:00:00"])

    def test_timedelta64_is_a_readable_duration(self):
        gap = np.timedelta64(86400 * 10**9, "ns")

        self.assertEqual(child._serialize_variable(gap), "1 day, 0:00:00")

    def test_nat_is_null(self):
        self.assertIsNone(child._serialize_variable(np.datetime64("NaT", "ns")))


class _LimitHitOnSerialize:
    def to_dict(self):
        raise child.CPUTimeLimitError("Code execution exceeded the CPU time limit and was terminated.")


def _raise(error):
    raise error


class TestRunUserCode(unittest.TestCase):
    """Printed output must survive every way the user's code can end."""

    def _run(self, code, env=None, return_variables=None):
        execution_globals = {"__builtins__": __builtins__, "_raise": _raise, "child": child, **(env or {})}
        with patch.object(child.signal, "alarm") as alarm:
            result = child._run_user_code(code, execution_globals, {}, True, return_variables or [])
        return result, alarm

    def test_success_returns_output_and_variables(self):
        result, _ = self._run("print('Grand total: 1234')\ntotal = 1234", return_variables=["total"])

        self.assertTrue(result["success"])
        self.assertEqual(result["output"], "Grand total: 1234\n")
        self.assertEqual(result["variables"], {"total": 1234})

    def test_exception_keeps_printed_output(self):
        result, _ = self._run("print('Grand total: 1234')\n1/0")

        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "runtime")
        self.assertEqual(result["output"], "Grand total: 1234\n")

    def test_limit_errors_keep_printed_output(self):
        cases = {
            "timeout": "child.ExecutionTimeoutError('timed out')",
            "cpu_limit": "child.CPUTimeLimitError('cpu')",
            "memory": "MemoryError()",
            "recursion": "RecursionError()",
        }
        for error_type, error in cases.items():
            with self.subTest(error_type=error_type):
                result, _ = self._run(f"print('partial: 99')\n_raise({error})")

                self.assertFalse(result["success"])
                self.assertEqual(result["error_type"], error_type)
                self.assertEqual(result["output"], "partial: 99\n")

    def test_output_is_capped_on_failure_too(self):
        result, _ = self._run("print('x' * (2 * 1024 * 1024))\n1/0")

        self.assertLess(len(result["output"]), 1024 * 1024 + 500)
        self.assertIn("OUTPUT TRUNCATED", result["output"])

    def test_alarm_is_cancelled_when_user_code_raises(self):
        _, alarm = self._run("1/0")

        alarm.assert_called_with(0)

    def test_alarm_is_cancelled_before_serialization(self):
        calls = []
        with patch.object(
            child.signal, "alarm", side_effect=lambda s: calls.append(("alarm", s))
        ), patch.object(
            child, "_extract_variables", side_effect=lambda *a: calls.append(("serialize",)) or ({}, [])
        ):
            child._run_user_code("x = 1", {"__builtins__": __builtins__}, {}, True, [])

        self.assertEqual(calls, [("alarm", 0), ("serialize",)])

    def test_limit_hit_while_serializing_is_a_failure_not_a_dropped_variable(self):
        result, _ = self._run("print('total: 5')\nframe = Slow()", env={"Slow": _LimitHitOnSerialize})

        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "cpu_limit")
        self.assertEqual(result["output"], "total: 5\n")


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

    def test_serialization_error_leaves_retry_guidance_to_the_parent(self):
        stream = io.StringIO()

        child._write_result({"success": True, "output": "", "variables": {"bad": {("A", 1): 1}}}, stream)

        self.assertNotIn("Re-run the calculation", json.loads(stream.getvalue())["error"])


if __name__ == "__main__":
    unittest.main()
