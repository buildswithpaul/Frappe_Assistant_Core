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
Every `tools.<name>` the run_python_code description offers must work in the sandbox.

Calls go through the real execution path: ExecutePythonCode spawns the subprocess
that builds the `tools` helper and runs the code, as the model's call does.
Read-only: nothing here writes to the database.
"""

import re

from frappe_assistant_core.plugins.data_science.tools.run_python_code import ExecutePythonCode
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.tool_api import FrappeAssistantAPI


class TestRunPythonCodeHelperNames(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.tool = ExecutePythonCode()

    def _run(self, code: str, returns=("out",)) -> dict:
        return self.tool._execute_code_with_timeout(code, None, 60, True, list(returns), "Administrator", {})

    def test_every_name_in_the_description_exists_on_the_helper(self):
        names = set(re.findall(r"tools\.(\w+)", self.tool.description))

        self.assertIn("list_documents", names)
        missing = sorted(n for n in names if not callable(getattr(FrappeAssistantAPI, n, None)))
        self.assertEqual(missing, [])

    def test_list_documents_runs_in_the_sandbox_with_the_mcp_arguments(self):
        result = self._run(
            "out = tools.list_documents('User', filters={'name': 'Administrator'},"
            " fields=['name'], limit=5, offset=0, order_by='name asc')"
        )

        self.assertTrue(result["success"], result)
        self.assertTrue(result["variables"]["out"]["success"], result)
        self.assertEqual([r["name"] for r in result["variables"]["out"]["data"]], ["Administrator"])

    def test_list_documents_takes_group_by_and_aggregate(self):
        result = self._run(
            "out = tools.list_documents('User', filters={'name': 'Administrator'},"
            " group_by='enabled', aggregate=[{'function': 'count', 'field': 'name'}])"
        )

        self.assertTrue(result["success"], result)
        self.assertTrue(result["variables"]["out"]["success"], result)

    def test_report_aliases_and_search_documents_run_in_the_sandbox(self):
        result = self._run(
            "lst = tools.report_list(query='sales')\n"
            "mod = tools.report_list(module='Accounts')\n"
            "req = tools.report_requirements('Accounts Receivable')\n"
            "srch = tools.search_documents('Administrator', doctype='User', limit=3)\n",
            returns=("lst", "mod", "req", "srch"),
        )

        self.assertTrue(result["success"], result)
        for name in ("lst", "mod", "req", "srch"):
            self.assertNotIn("has no attribute", str(result["variables"][name]))
        self.assertTrue(result["variables"]["srch"]["success"], result)

    def test_unknown_helper_name_still_raises(self):
        result = self._run("tools.no_such_helper()")

        self.assertFalse(result["success"])
        self.assertIn("no attribute", result["error"])
