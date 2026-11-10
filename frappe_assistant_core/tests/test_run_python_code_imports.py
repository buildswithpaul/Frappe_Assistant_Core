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

    def test_import_pandas_as_pd_with_a_dataframe(self):
        # GitHub #378: the rewritten `pd = _preloaded_modules["pandas"]` looked like a DataFrame slice
        # to the auto-fixer, which made it `..["pandas"].copy()` whenever the code said pd.DataFrame
        self.assertPrints(
            "import pandas as pd\nimport numpy as np\ndf = pd.DataFrame({'a': [1, 2]})\nprint(len(df), np.sum([1, 2]))",
            "2 3",
        )

    def test_dataframe_from_frappe_rows(self):
        # GitHub #379: frappe._dict answers any attribute with None, so pandas took the rows for an array
        self.assertPrints(
            "rows = frappe.get_all('User', fields=['name', 'enabled'], limit=2)\n"
            "df = pd.DataFrame(rows)\n"
            "print(list(df.columns), len(df) > 0, isinstance(df, pd.DataFrame),"
            " isinstance(df.head(1), pd.DataFrame), isinstance(pd.DataFrame.from_dict({'a': [1]}), pd.DataFrame))",
            "['name', 'enabled'] True True True True",
        )

    def test_dataframe_from_an_iterator_of_frappe_rows(self):
        # A generator expression or map() of frappe rows failed the same way as a list did
        self.assertPrints(
            "rows = frappe.get_all('User', fields=['name', 'enabled'], limit=2)\n"
            "a = pd.DataFrame(r for r in rows)\n"
            "b = pd.DataFrame(map(lambda r: r, rows))\n"
            "c = pd.DataFrame(data=(r for r in rows), columns=['name'])\n"
            "print(len(a) == len(rows), len(b) == len(rows), list(c.columns))",
            "True True ['name']",
        )

    def test_type_of_a_frame_is_pd_dataframe(self):
        # LLM-written code compares types as well as using isinstance: both hold, as on develop
        self.assertPrints(
            "df = pd.DataFrame({'a': [1, 2], 'b': [3, 4]})\n"
            "parts = [df, df.head(1), df[df.a > 1], pd.concat([df, df]), pd.DataFrame.from_dict({'a': [1]}),"
            " pd.DataFrame.from_records([{'a': 1}]), df.groupby('a').sum()]\n"
            "print([type(x) is pd.DataFrame for x in parts])\n"
            "print([type(x) == pd.DataFrame for x in parts])\n"
            "print([isinstance(x, pd.DataFrame) for x in parts])",
            "\n".join(["[True, True, True, True, True, True, True]"] * 3),
        )

    def test_a_frame_pandas_makes_with_its_own_class_is_still_a_dataframe(self):
        # Series.to_frame builds pandas' own DataFrame, not the sandbox's: isinstance holds, type() is not
        self.assertPrints(
            "f = pd.Series([1, 2], name='a').to_frame()\n" "print(isinstance(f, pd.DataFrame), len(f))",
            "True 2",
        )

    def test_unavailable_module_is_reported_not_silently_dropped(self):
        result = _run("import operator\nprint(operator.add(1, 2))")
        self.assertFalse(result.get("success"))
        self.assertIn("operator", result.get("error") or "")
