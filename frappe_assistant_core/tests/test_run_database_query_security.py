# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""run_database_query refuses file, lock and privilege statements.

Validation is pure string analysis, so these need no database rows.
"""

from frappe.tests.utils import FrappeTestCase

from frappe_assistant_core.plugins.data_science.tools.run_database_query import QueryAndAnalyse


class TestRunDatabaseQuerySecurity(FrappeTestCase):
    def setUp(self):
        super().setUp()
        self.tool = QueryAndAnalyse()

    def assertRefused(self, query, construct):
        result = self.tool._validate_query_security(query)
        self.assertFalse(result["is_valid"], query)
        self.assertIn(construct, result["error"].upper(), query)

    def test_file_writes_are_refused(self):
        self.assertRefused("SELECT name FROM tabToDo INTO OUTFILE '/tmp/x'", "INTO OUTFILE")
        self.assertRefused("SELECT name FROM tabToDo INTO\n  DUMPFILE '/tmp/x'", "INTO DUMPFILE")

    def test_file_reads_are_refused(self):
        self.assertRefused("SELECT LOAD_FILE('/etc/passwd')", "LOAD_FILE")
        self.assertRefused("SELECT name FROM tabToDo WHERE x = load_file ('/etc/passwd')", "LOAD_FILE")
        self.assertRefused("SELECT 1 FROM (LOAD DATA INFILE 'x' INTO TABLE t) q", "LOAD DATA")
        self.assertRefused("SELECT 1 FROM (LOAD XML INFILE 'x' INTO TABLE t) q", "LOAD XML")

    def test_privilege_statements_are_refused(self):
        self.assertRefused("SELECT 1 FROM (GRANT ALL ON *.* TO x) q", "GRANT")
        self.assertRefused("SELECT 1 FROM (REVOKE ALL ON *.* FROM x) q", "REVOKE")

    def test_locking_is_refused(self):
        self.assertRefused("SELECT 1 FROM (LOCK TABLES tabToDo WRITE) q", "LOCK TABLES")
        self.assertRefused("SELECT 1 FROM (UNLOCK TABLES) q", "UNLOCK TABLES")
        self.assertRefused("SELECT name FROM tabToDo LOCK IN SHARE MODE", "LOCK IN SHARE MODE")
        self.assertRefused("SELECT name FROM tabToDo FOR UPDATE", "FOR UPDATE")
        self.assertRefused("SELECT name FROM tabToDo FOR /* x */ SHARE", "FOR SHARE")

    def test_variable_and_procedure_statements_are_refused(self):
        self.assertRefused("SELECT 1 FROM (SET @a = 1) q", "SET")
        self.assertRefused("SELECT 1 FROM (SET GLOBAL x = 1) q", "SET")
        self.assertRefused("SELECT 1 FROM (HANDLER tabToDo OPEN) q", "HANDLER")
        self.assertRefused("SELECT 1 FROM (DO SLEEP(1)) q", "DO")
        self.assertRefused("SELECT 1 FROM (CALL p()) q", "CALL")

    def test_keywords_in_comments_are_ignored(self):
        for query in (
            "SELECT name FROM tabToDo -- grant access\n LIMIT 5",
            "SELECT name FROM tabToDo /* lock tables, for update */ LIMIT 5",
            "SELECT name FROM tabToDo # into outfile\n LIMIT 5",
        ):
            self.assertTrue(self.tool._validate_query_security(query)["is_valid"], query)

    def test_allowed_queries_pass(self):
        for query in (
            "SELECT name FROM tabToDo WHERE description = 'grant access' LIMIT 5",
            "SELECT name FROM tabToDo WHERE description = 'load data for update' LIMIT 5",
            "SELECT granted_on, locked, set_name, calls, do_not_contact, handlers FROM tabX",
            "SELECT `do`, `call` FROM tabX",
            "SELECT name FROM tabToDo ORDER BY modified LIMIT 5",
        ):
            self.assertTrue(self.tool._validate_query_security(query)["is_valid"], query)
