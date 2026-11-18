# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""The check's decisions: every failure as the questions to ask the user at once, one per field and
cause, with a suggested answer. Live, 2026-11-17: a file of projects failed in 276 groups, the reply
showed 30, and the assistant asked the rest round by round."""

import unittest

import frappe

from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.tests.base_test import BaseAssistantTest

STATUSES = ["Finished", "In process", "Created"]


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Project")
class TestTheCheckGivesEveryDecision(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.registry = get_tool_registry()
        self.track_test_files()
        self.tag = frappe.generate_hash(length=6)
        self.company = frappe.get_all("Company", pluck="name", limit=1)[0]

    def tearDown(self):
        frappe.set_user("Administrator")
        self.delete_test_files()
        super().tearDown()

    def _run(self, tool_name, arguments):
        return self.registry.get_tool(tool_name)._safe_execute(arguments)

    def _checked(self, types=35):
        """Projects of ``types`` project types none of which exist, so the check has more groups than
        it shows, each with a status ERPNext doesn't have."""
        lines = ["Project,Type,Stage,Company"] + [
            f"Site {i} {self.tag},Kind {i} {self.tag},{STATUSES[i % 3]},{self.company}" for i in range(types)
        ]
        file_doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": "projects.csv",
                "content": ("\n".join(lines) + "\n").encode(),
                "is_private": 1,
            }
        ).insert()
        session = self._run("start_import_session", {"file_url": file_doc.file_url})["result"]["session_id"]
        mapping = {"Project": "project_name", "Type": "project_type", "Stage": "status", "Company": "company"}
        mapped = self._run(
            "set_column_mapping", {"session": session, "doctype": "Project", "mapping": mapping}
        )
        self.assertTrue(mapped["success"], mapped)
        checked = self._run("dry_run_import", {"session": session})
        self.assertTrue(checked["success"], checked)
        return session, checked["result"]

    @staticmethod
    def _decision(result, field):
        return next(d for d in result["decisions"] if d["field"] == field)

    def test_every_failure_is_a_decision_though_only_some_groups_are_shown(self):
        _session, result = self._checked()

        self.assertGreater(result["groups_total"], len(result["groups"]))
        status = self._decision(result, "status")
        self.assertEqual(sorted(v["value"] for v in status["values"]), sorted(STATUSES))
        kinds = self._decision(result, "project_type")
        self.assertEqual((kinds["values_total"], kinds["rows"]), (35, 35))

    def test_each_value_comes_with_the_answer_to_suggest(self):
        _session, result = self._checked()

        suggested = {v["value"]: v.get("suggested") for v in self._decision(result, "status")["values"]}
        self.assertEqual(suggested["Finished"], {"action": "map", "to": "Completed"})
        self.assertEqual(suggested["In process"], {"action": "map", "to": "Open"})
        self.assertEqual(suggested["Created"], {"action": "map", "to": "Open"})
        self.assertEqual(self._decision(result, "project_type")["suggested_for_all"], "create")

    def test_the_answers_to_every_decision_go_in_one_call(self):
        session, result = self._checked()
        fixes = [{"group": v["group"], **v["suggested"]} for v in self._decision(result, "status")["values"]]

        fixed = self._run("dry_run_import", {"session": session, "fixes": fixes})

        self.assertTrue(fixed["success"], fixed)
        self.assertNotIn("status", [d["field"] for d in fixed["result"].get("decisions") or []])
