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
The parent side of run_python_code must hand the model whatever the user's
code printed, whatever the outcome, and say "retry inside the tool" once.

Nothing here writes to the database; the one real-subprocess test only reads.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from frappe_assistant_core.plugins.data_science.tools.run_python_code import (
    RETRY_BY_HAND,
    ExecutePythonCode,
)


def _fake_popen(stdout: bytes, returncode: int = 0):
    proc = MagicMock()
    proc.communicate.return_value = (stdout, b"")
    proc.returncode = returncode
    return MagicMock(return_value=proc)


class TestRunPythonCodeResult(unittest.TestCase):
    def setUp(self):
        self.tool = ExecutePythonCode()

    def _execute(self, code="print(1)"):
        return self.tool._execute_code_with_timeout(code, None, 30, True, [], "Administrator", {})

    def test_unparseable_child_output_keeps_the_printed_text(self):
        with patch("subprocess.Popen", _fake_popen(b'Grand total: 1234\n{"success": tr', returncode=1)):
            result = self._execute()

        self.assertFalse(result["success"])
        self.assertIn("Grand total: 1234", result["output"])

    def test_child_failure_passes_its_output_through(self):
        child_result = {
            "success": False,
            "error_type": "runtime",
            "error": "boom",
            "output": "Grand total: 1234\n",
        }
        with patch("subprocess.Popen", _fake_popen(json.dumps(child_result).encode())):
            result = self._execute()

        self.assertEqual(result["output"], "Grand total: 1234\n")

    def test_retry_guidance_appears_exactly_once(self):
        child_result = {
            "success": False,
            "error_type": "serialization",
            "error": "Could not serialize variables: bad.",
            "output": "",
        }
        with patch("subprocess.Popen", _fake_popen(json.dumps(child_result).encode())):
            result = self._execute()

        self.assertEqual(result["error"].count(RETRY_BY_HAND), 1)

    def test_real_subprocess_keeps_output_when_user_code_raises(self):
        result = self._execute("print('Grand total: 1234')\n1/0")

        self.assertFalse(result["success"])
        self.assertEqual(result["output"], "Grand total: 1234\n")
        self.assertEqual(result["error"].count(RETRY_BY_HAND), 1)


if __name__ == "__main__":
    unittest.main()
