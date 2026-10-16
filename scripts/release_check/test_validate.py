"""Plain unittest (no Frappe): the schema checker and the shipped questions.json.

Run: python -m unittest discover -s scripts/release_check -p "test_*.py"
Exception to BaseAssistantTest is deliberate: this tests dev tooling and needs no site.
"""

import ast
import copy
import json
import unittest
from pathlib import Path

import validate

HERE = Path(__file__).resolve().parent


class TestShippedQuestions(unittest.TestCase):
    def test_questions_json_is_valid_against_expected_py(self):
        questions = json.loads((HERE / "questions.json").read_text())
        functions = validate.function_names((HERE / "expected.py").read_text())
        self.assertEqual(validate.validate_questions(questions, functions), [])

    def test_every_public_expected_function_reads_data(self):
        source = (HERE / "expected.py").read_text()
        public = [
            node
            for node in ast.parse(source).body
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
        ]
        self.assertTrue(public)
        for node in public:
            segment = ast.get_source_segment(source, node)
            reads_data = (
                "frappe.get_list" in segment
                or "_sales_invoices(" in segment
                or "_receivable_balance(" in segment
            )
            self.assertTrue(reads_data, f"{node.name} must derive its answer from data")


class TestValidator(unittest.TestCase):
    def setUp(self):
        self.functions = {"f"}
        self.good = [
            {
                "id": qid,
                "site": "realistic",
                "question": "q?",
                "expect": {"kind": "total", "source": "f"},
                "cite": ["Report"],
            }
            for qid in validate.REQUIRED_IDS
        ]

    def problems(self, mutate):
        questions = copy.deepcopy(self.good)
        mutate(questions)
        return validate.validate_questions(questions, self.functions)

    def test_good_set_is_valid(self):
        self.assertEqual(self.problems(lambda q: None), [])

    def test_unknown_source_is_reported(self):
        found = self.problems(lambda q: q[0]["expect"].update(source="nope"))
        self.assertTrue(any("not a function in expected.py" in p for p in found))

    def test_bad_kind_site_and_cite_are_reported(self):
        def mutate(q):
            q[0]["expect"]["kind"] = "avg"
            q[1]["site"] = "huge"
            q[2]["cite"] = []

        found = self.problems(mutate)
        self.assertEqual(len(found), 3)

    def test_missing_required_id_and_duplicate_id(self):
        found = self.problems(lambda q: q.pop())
        self.assertTrue(any("is missing" in p for p in found))
        found = self.problems(lambda q: q[1].update(id=q[0]["id"]))
        self.assertTrue(any("duplicate id" in p for p in found))


if __name__ == "__main__":
    unittest.main()
