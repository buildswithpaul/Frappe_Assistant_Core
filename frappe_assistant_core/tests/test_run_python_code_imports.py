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
Imports of pre-loaded modules must bind the names they introduce.

The sandbox has no import statement, so run_python_code rewrites imports of
modules that are already in scope. It used to turn ``from collections import
Counter`` into a comment, leaving ``Counter`` undefined at run time.
"""

from frappe_assistant_core.tests.base_test import BaseAssistantTest


def _run(code):
    from frappe_assistant_core.plugins.data_science.tools.run_python_code import ExecutePythonCode

    return ExecutePythonCode().execute({"code": code})


class TestPreloadedImportRewrite(BaseAssistantTest):
    """The line rewrite, without running anything."""

    def test_rewrites(self):
        from frappe_assistant_core.plugins.data_science.tools.run_python_code import (
            _rewrite_preloaded_import,
        )

        ref = '_preloaded_modules["{}"]'.format
        cases = {
            "from collections import Counter": f"Counter = {ref('collections')}.Counter",
            "from datetime import datetime as dt, timedelta": (
                f"dt, timedelta = {ref('datetime')}.datetime, {ref('datetime')}.timedelta"
            ),
            "from frappe.utils import flt": f"flt = {ref('frappe')}.utils.flt",
            "import numpy as np": f"np = {ref('numpy')}",
            "import collections  # counting": "pass  # import collections (pre-loaded)",
        }
        for statement, expected in cases.items():
            with self.subTest(statement=statement):
                self.assertEqual(_rewrite_preloaded_import(statement), expected)

    def test_unsupported_imports_are_not_rewritten(self):
        from frappe_assistant_core.plugins.data_science.tools.run_python_code import (
            _rewrite_preloaded_import,
        )

        for statement in (
            "import os",
            "from os import path",
            "import operator",
            "from collections import *",
            "from . import x",
            "from collections import (Counter,",
            "import json; import os",
        ):
            with self.subTest(statement=statement):
                self.assertIsNone(_rewrite_preloaded_import(statement))


class TestPreloadedImportsRun(BaseAssistantTest):
    """End to end through the subprocess, the way the model calls the tool."""

    def assertPrints(self, code, expected):
        result = _run(code)
        self.assertTrue(result.get("success"), result.get("error"))
        self.assertEqual(result["output"].strip(), expected)

    def test_from_collections_import_binds_names(self):
        self.assertPrints(
            "from collections import Counter, defaultdict\n"
            "c = Counter(['a', 'a', 'b'])\n"
            "d = defaultdict(int)\n"
            "print(c['a'], d['missing'])",
            "2 0",
        )

    def test_import_module_then_attribute(self):
        self.assertPrints("import collections\nprint(collections.Counter('aab')['b'])", "1")

    def test_from_datetime_import_class_shadowing_module(self):
        # Two from-imports of the same module must both resolve, even though the
        # first rebinds the name `datetime` to the class, as real Python allows.
        self.assertPrints(
            "from datetime import datetime\n"
            "from datetime import timedelta\n"
            "print((datetime(2026, 1, 1) + timedelta(days=1)).day)",
            "2",
        )

    def test_other_helper_modules(self):
        self.assertPrints(
            "from itertools import groupby\n"
            "from functools import reduce\n"
            "import heapq, bisect, copy, string\n"
            "runs = [k for k, _g in groupby('aabbb')]\n"
            "print(runs, reduce(lambda a, b: a + b, [1, 2, 3]), heapq.nsmallest(1, [3, 1]),"
            " bisect.bisect([1, 3], 2), copy.deepcopy([1])[0], string.digits[:2])",
            "['a', 'b'] 6 [1] 1 1 01",
        )

    def test_import_inside_a_function(self):
        self.assertPrints(
            "def top(xs):\n"
            "    from collections import Counter\n"
            "    return Counter(xs).most_common(1)[0][0]\n"
            "print(top('abb'))",
            "b",
        )

    def test_frappe_utils_from_import(self):
        self.assertPrints("from frappe.utils import flt\nprint(flt('2.50'))", "2.5")

    def test_unavailable_module_is_reported_not_silently_dropped(self):
        result = _run("import operator\nprint(operator.add(1, 2))")
        self.assertFalse(result.get("success"))
        self.assertIn("operator", result.get("error") or "")
