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
run_python_code data access must respect permissions the way Desk does.

The fixture is a System Manager restricted by a User Permission: two ToDos
tagged with different Roles, and a User Permission allowing only Role A.
ToDo grants read to System Manager, so only the User Permission hides ToDo B,
the same shape as a user restricted to one Company.
"""

import json
import subprocess
import sys

import frappe

from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils import sandbox_frappe
from frappe_assistant_core.utils.tool_api import FrappeAssistantAPI

RESTRICTED_USER = "fac-sandbox-restricted@example.com"
NO_ROLE_USER = "fac-sandbox-norole@example.com"
ROLE_A = "_FAC Sandbox Role A"
ROLE_B = "_FAC Sandbox Role B"


class TestSandboxPermissions(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        # Class-level: IntegrationTestCase rolls back once per class, not per test.
        super().setUpClass()
        # nosemgrep: frappe-setuser — tests run in an isolated transaction
        frappe.set_user("Administrator")
        for role in (ROLE_A, ROLE_B):
            if not frappe.db.exists("Role", role):
                frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert()
        for email, roles in ((RESTRICTED_USER, ["System Manager"]), (NO_ROLE_USER, [])):
            if not frappe.db.exists("User", email):
                frappe.get_doc(
                    {
                        "doctype": "User",
                        "email": email,
                        "first_name": "FAC Sandbox",
                        "roles": [{"role": role} for role in roles],
                    }
                ).insert(ignore_permissions=True)

        cls.todo_a = cls._todo(ROLE_A)
        cls.todo_b = cls._todo(ROLE_B)
        frappe.get_doc(
            {
                "doctype": "User Permission",
                "user": RESTRICTED_USER,
                "allow": "Role",
                "for_value": ROLE_A,
                "apply_to_all_doctypes": 1,
            }
        ).insert()

    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — tests run in an isolated transaction
        frappe.set_user(RESTRICTED_USER)
        self.sandbox = sandbox_frappe.build_sandbox_frappe(RESTRICTED_USER)

    def tearDown(self):
        # nosemgrep: frappe-setuser — tests run in an isolated transaction
        frappe.set_user("Administrator")
        super().tearDown()

    @staticmethod
    def _todo(role):
        return (
            frappe.get_doc(
                {
                    "doctype": "ToDo",
                    "description": f"fac sandbox permission test {role}",
                    "role": role,
                    "allocated_to": RESTRICTED_USER,
                }
            )
            .insert()
            .name
        )

    def _names(self, rows):
        return {row["name"] for row in rows} & {self.todo_a, self.todo_b}

    def test_list_reads_respect_user_permissions(self):
        both = {"name": ["in", [self.todo_a, self.todo_b]]}
        for get in (self.sandbox.get_list, self.sandbox.get_all, self.sandbox.db.get_all):
            with self.subTest(get=get):
                self.assertEqual(self._names(get("ToDo", filters=both, fields=["name"])), {self.todo_a})

    def test_widening_kwargs_are_ignored(self):
        rows = self.sandbox.get_all(
            "ToDo",
            filters={"name": self.todo_b},
            fields=["name"],
            ignore_permissions=True,
            user="Administrator",
        )
        self.assertEqual(rows, [])

    def test_get_doc_checks_the_document(self):
        doc = self.sandbox.get_doc("ToDo", self.todo_a)
        self.assertEqual(doc.role, ROLE_A)
        with self.assertRaises(frappe.PermissionError):
            doc.save()
        with self.assertRaises(frappe.PermissionError):
            self.sandbox.get_doc("ToDo", self.todo_b)

    def test_db_helpers_respect_user_permissions(self):
        db = self.sandbox.db
        self.assertEqual(db.count("ToDo", {"name": ["in", [self.todo_a, self.todo_b]]}), 1)
        self.assertEqual(db.get_value("ToDo", self.todo_a, "role"), ROLE_A)
        self.assertIsNone(db.get_value("ToDo", self.todo_b, "role"))
        self.assertEqual(db.exists("ToDo", self.todo_a), self.todo_a)
        self.assertIsNone(db.exists("ToDo", self.todo_b))

    def test_aggregates_respect_user_permissions_on_this_frappe_version(self):
        both = {"name": ["in", [self.todo_a, self.todo_b]]}
        for count_field in ({"COUNT": "name", "as": "n"}, "count(name) as n"):
            with self.subTest(count_field=count_field):
                rows = self.sandbox.get_list(
                    "ToDo", filters=both, fields=["role", count_field], group_by="role"
                )
                self.assertEqual([(row["role"], row["n"]) for row in rows], [(ROLE_A, 1)])

    def test_only_fields_and_filters_may_be_positional(self):
        rows = self.sandbox.get_list("ToDo", ["name"], {"name": ["in", [self.todo_a, self.todo_b]]})
        self.assertEqual(self._names(rows), {self.todo_a})
        with self.assertRaises(TypeError):
            self.sandbox.get_list("ToDo", ["name"], {}, None)

    def test_get_value_returns_values_by_field_name(self):
        role, description = self.sandbox.db.get_value("ToDo", self.todo_a, ["role", "description"])
        self.assertEqual(role, ROLE_A)
        self.assertIn(ROLE_A, description)

    def test_get_value_matches_frappe_positional_order(self):
        row = self.sandbox.db.get_value("ToDo", self.todo_a, "role", None, True)  # ignore, as_dict
        self.assertEqual(row["role"], ROLE_A)
        both = {"name": ["in", [self.todo_a, self.todo_b]]}
        self.assertEqual(self.sandbox.db.get_value("ToDo", both, {"COUNT": "name"}), 1)

    def test_raw_sql_is_unavailable(self):
        with self.assertRaises(frappe.PermissionError):
            self.sandbox.db.sql("select name from `tabToDo`")

    def test_unoffered_attributes_raise(self):
        for owner, name in (
            (self.sandbox, "get_hooks"),
            (self.sandbox.db, "set_value"),
            (self.sandbox.utils, "execute_in_shell"),
        ):
            with self.subTest(name=name), self.assertRaises(AttributeError):
                getattr(owner, name)

    def test_tools_api_respects_user_permissions(self):
        tools = FrappeAssistantAPI(RESTRICTED_USER)
        result = tools.get_documents(
            "ToDo", filters={"name": ["in", [self.todo_a, self.todo_b]]}, fields=["name"]
        )
        self.assertEqual(self._names(result["data"]), {self.todo_a})

        self.assertTrue(tools.get_document("ToDo", self.todo_a)["success"])
        self.assertFalse(tools.get_document("ToDo", self.todo_b)["success"])

        self.assertEqual(tools.search(self.todo_b, doctype="ToDo")["results"], [])

    def test_data_query_respects_user_permissions(self):
        rows = sandbox_frappe.fetch_data_query(
            {"doctype": "ToDo", "fields": ["name"], "filters": {"name": ["in", [self.todo_a, self.todo_b]]}}
        )
        self.assertEqual(self._names(rows), {self.todo_a})

    def test_role_permissions_apply(self):
        # nosemgrep: frappe-setuser — tests run in an isolated transaction
        frappe.set_user(NO_ROLE_USER)
        with self.assertRaises(frappe.PermissionError):
            sandbox_frappe.get_list("Error Log", fields=["name"])


class TestSandboxEnvironment(BaseAssistantTest):
    """The subprocess must hand user code the permission-checked objects, never the real module."""

    def test_sandbox_globals_are_permission_checked(self):
        # Avoids dunder attributes (blocked by the validator): asserts behaviour,
        # i.e. raw SQL is refused while permission-checked get_all works.
        code = (
            "try:\n"
            "    frappe.db.sql('select 1')\n"
            "    sql = 'allowed'\n"
            "except frappe.PermissionError:\n"
            "    sql = 'blocked'\n"
            "n = len(frappe.get_all('DocType', fields=['name'], limit=1))\n"
            "print(sql, n >= 1)"
        )
        request = {
            "code": code,
            "user": "Administrator",
            "site": frappe.local.site,
            "sites_path": str(frappe.local.sites_path),
            "limits": {
                "timeout_seconds": 30,
                "max_memory_mb": 1024,
                "max_cpu_seconds": 30,
                "max_recursion_depth": 500,
            },
            "data_query": None,
            "return_variables": [],
            "capture_output": True,
        }
        proc = subprocess.run(
            [sys.executable, "-m", "frappe_assistant_core.utils.code_execution_subprocess"],
            input=json.dumps(request).encode(),
            capture_output=True,
            timeout=120,
        )
        result = json.loads(proc.stdout.decode())
        self.assertTrue(result["success"], result.get("error"))
        self.assertEqual(result["output"].strip(), "blocked True")


class TestSandboxHardening(BaseAssistantTest):
    """The static validator and module wrappers reject escape-shaped code."""

    def test_validator_allows_normal_analysis(self):
        from frappe_assistant_core.utils.sandbox_ast import validate_code

        validate_code("df = pd.DataFrame(data); print(df.groupby('x')['y'].sum())")
        validate_code("rows = frappe.get_list('ToDo', fields=['name']); n = len(rows)")
        validate_code("t = frappe.utils.today(); v = math.sqrt(9)")

    def test_validator_allows_variables_named_like_builtins(self):
        from frappe_assistant_core.utils.sandbox_ast import validate_code

        validate_code("help = df.describe()\ndir = 'desc'\ninput = rows\nprint(help, dir, input)")
        validate_code("def total(vars):\n    return sum(vars)")

    def test_document_fields_win_over_dict_methods(self):
        from frappe_assistant_core.utils.sandbox_frappe import ReadOnlyDoc

        doc = ReadOnlyDoc({"name": "SINV-1", "items": [{"item_code": "A"}], "values": 5})
        self.assertEqual(doc.items, [{"item_code": "A"}])  # child table, not dict.items
        self.assertEqual(doc.values, 5)
        self.assertEqual(dict(doc)["name"], "SINV-1")
        self.assertEqual(list(ReadOnlyDoc({"a": 1}).keys()), ["a"])  # no field named keys
        with self.assertRaises(frappe.PermissionError):
            doc.save()

    def test_validator_rejects_escape_shapes(self):
        from frappe_assistant_core.utils.sandbox_ast import SandboxSecurityError, validate_code

        for code in (
            "import os",
            "from sys import argv",
            "x = ().__class__",
            "x = obj.__globals__",
            "x = obj._private",
            "y = getattr(o, 'x')",
            "y = eval('1')",
            "y = open('/etc/hostname')",
            "y = __builtins__",
        ):
            with self.subTest(code=code), self.assertRaises(SandboxSecurityError):
                validate_code(code)

    def test_module_wrapper_blocks_module_and_private_hops(self):
        import statistics

        from frappe_assistant_core.utils.code_execution_subprocess import _AttrSafeModule

        safe = _AttrSafeModule(statistics, "statistics")
        self.assertEqual(safe.mean([2, 4]), 3)  # public member still works
        self.assertRaises(AttributeError, lambda: safe.sys)  # hop to another module
        self.assertRaises(AttributeError, lambda: safe._private)  # private attribute


class TestRunDatabaseQueryAccess(BaseAssistantTest):
    """run_database_query is System-Manager-only and cannot read internal tables."""

    def setUp(self):
        super().setUp()
        self.registry = get_tool_registry()
        if not frappe.db.exists("User", NO_ROLE_USER):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": NO_ROLE_USER,
                    "first_name": "FAC No Role",
                    "send_welcome_email": 0,
                }
            ).insert(ignore_permissions=True)

    def test_declares_system_manager_only(self):
        tool = self.registry.get_tool("run_database_query")
        if tool is None:
            self.skipTest("run_database_query not available (data science plugin disabled)")
        self.assertEqual(tool.required_roles, ["System Manager"])

    def test_hidden_from_non_system_manager(self):
        if not self.registry.has_tool("run_database_query"):
            self.skipTest("run_database_query not available")
        # nosemgrep: frappe-setuser — tests run in an isolated transaction
        frappe.set_user(NO_ROLE_USER)
        try:
            names = {t["name"] for t in self.registry.get_available_tools(NO_ROLE_USER)}
        finally:
            # nosemgrep: frappe-setuser — tests run in an isolated transaction
            frappe.set_user("Administrator")
        self.assertNotIn("run_database_query", names)

    def test_execute_blocked_for_non_system_manager(self):
        if not self.registry.has_tool("run_database_query"):
            self.skipTest("run_database_query not available")
        # nosemgrep: frappe-setuser — tests run in an isolated transaction
        frappe.set_user(NO_ROLE_USER)
        try:
            with self.assertRaises(PermissionError):
                self.registry.execute_tool("run_database_query", {"query": "SELECT 1"})
        finally:
            # nosemgrep: frappe-setuser — tests run in an isolated transaction
            frappe.set_user("Administrator")

    def test_internal_tables_rejected(self):
        tool = self.registry.get_tool("run_database_query")
        if tool is None:
            self.skipTest("run_database_query not available")
        self.assertFalse(tool._validate_query_security("SELECT * FROM __Auth")["is_valid"])
        self.assertFalse(tool._validate_query_security("select name, pwd from `__Auth`")["is_valid"])
        self.assertTrue(tool._validate_query_security("SELECT name FROM `tabDocType` LIMIT 1")["is_valid"])

    def test_sql_rules_do_not_flag_normal_queries(self):
        tool = self.registry.get_tool("run_database_query")
        if tool is None:
            self.skipTest("run_database_query not available")
        valid = tool._validate_query_security
        self.assertTrue(valid("SELECT name FROM `tabItem` WHERE item_code LIKE '__A%'")["is_valid"])
        self.assertTrue(valid("SELECT SUM(actual_qty) AS __total FROM `tabBin`")["is_valid"])
        self.assertFalse(valid("SELECT name FROM `tabUser`, __Auth")["is_valid"])

    def test_internal_table_check_ignores_comment_and_join_tricks(self):
        tool = self.registry.get_tool("run_database_query")
        if tool is None:
            self.skipTest("run_database_query not available")
        valid = tool._validate_query_security
        for query in (
            "SELECT name/**/FROM/**/__Auth",
            "SELECT u.name FROM `tabUser` u STRAIGHT_JOIN __Auth a",
            "SELECT * FROM (__Auth)",
            "SELECT name, 1--1\nFROM __Auth",
            "SELECT name FROM `mydb`.`__Auth`",
        ):
            with self.subTest(query=query):
                self.assertFalse(valid(query)["is_valid"])
        self.assertTrue(
            valid("SELECT name FROM `tabToDo` WHERE description = 'it''s __x' -- note")["is_valid"]
        )

    def test_executable_comments_rejected(self):
        tool = self.registry.get_tool("run_database_query")
        if tool is None:
            self.skipTest("run_database_query not available")
        self.assertFalse(tool._validate_query_security("SELECT name FROM /*!`tabToDo` */")["is_valid"])


class TestRunPythonCodeCapability(BaseAssistantTest):
    """Hardening must not cost everyday analysis capability."""

    def test_common_imports_and_pandas_namespaces_still_work(self):
        from frappe_assistant_core.plugins.data_science.tools.run_python_code import ExecutePythonCode

        code = (
            "import pandas as pd\n"
            "import numpy as np\n"
            "s = pd.Series([1, 2, 3])\n"
            "print(pd.api.types.is_numeric_dtype(s), pd.offsets.MonthEnd() is not None, float(np.ma.mean(s)))"
        )
        result = ExecutePythonCode().execute({"code": code})
        self.assertTrue(result.get("success"), result.get("error"))
        self.assertEqual(result["output"].strip(), "True True 2.0")
