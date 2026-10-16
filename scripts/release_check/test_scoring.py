"""Tests for the release-check scoring and comparison. Pure Python: python -m unittest."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scoring import extract_numbers, is_cited, regressions, score_mentions, score_top_n, score_total

HERE = Path(__file__).resolve().parent


class TestExtractNumbers(unittest.TestCase):
    def test_western_grouping_and_decimals(self):
        self.assertEqual(extract_numbers("Total was $1,234,567.89 today"), [1234567.89])

    def test_indian_grouping_with_rupee_sign(self):
        self.assertEqual(extract_numbers("₹1,23,456.78 outstanding"), [123456.78])

    def test_plain_number(self):
        self.assertEqual(extract_numbers("We hold 42 units"), [42.0])

    def test_million_forms(self):
        self.assertEqual(extract_numbers("about 1.2M"), [1200000.0])
        self.assertEqual(extract_numbers("about 1.2 million"), [1200000.0])

    def test_lakh_and_crore(self):
        self.assertEqual(extract_numbers("12 lakh"), [1200000.0])
        self.assertEqual(extract_numbers("1.5 crore"), [15000000.0])

    def test_thousand_and_billion(self):
        self.assertEqual(extract_numbers("350K and 2 billion"), [350000.0, 2000000000.0])

    def test_trailing_sentence_period_is_not_a_decimal(self):
        self.assertEqual(extract_numbers("We have 500."), [500.0])

    def test_no_numbers(self):
        self.assertEqual(extract_numbers("none here"), [])


class TestScoreTotal(unittest.TestCase):
    def test_exact_and_within_half_percent(self):
        self.assertTrue(score_total("Net sales: 100,000.00", 100000))
        self.assertTrue(score_total("Net sales: 100,400", 100000))

    def test_outside_half_percent(self):
        self.assertFalse(score_total("Net sales: 100,600", 100000))

    def test_any_number_in_the_answer_may_match(self):
        self.assertTrue(score_total("Across 12 invoices the total is 5,000.50", 5000.5))

    def test_lakh_form_matches(self):
        self.assertTrue(score_total("Receivable is ₹12 lakh", 1200000))

    def test_zero_expected_needs_zero_like_number(self):
        self.assertTrue(score_total("There are 0 units", 0))
        self.assertFalse(score_total("There are 3 units", 0))

    def test_empty_answer(self):
        self.assertFalse(score_total("", 100))


class TestScoreTopN(unittest.TestCase):
    NAMES = ["Alpha Co", "Beta Ltd"]

    def test_all_names_present_case_insensitive(self):
        self.assertTrue(score_top_n("1. alpha co 2. BETA LTD", self.NAMES))

    def test_one_missing_fails(self):
        self.assertFalse(score_top_n("Alpha Co only", self.NAMES))

    def test_empty_expected_never_passes(self):
        self.assertFalse(score_top_n("anything", []))


class TestScoreMentions(unittest.TestCase):
    def test_all_terms(self):
        self.assertTrue(score_mentions("RC Vendor Alpha paid 1,000.00", ["RC Vendor Alpha", "1,000.00"]))

    def test_missing_term(self):
        self.assertFalse(score_mentions("RC Vendor Alpha", ["RC Vendor Alpha", "1,000.00"]))

    def test_alternatives_any_one_satisfies(self):
        self.assertTrue(score_mentions("paid 1000.00", [["1,000.00", "1000.00"]]))
        self.assertFalse(score_mentions("paid 999", [["1,000.00", "1000.00"]]))

    def test_empty_terms_never_pass(self):
        self.assertFalse(score_mentions("x", []))


class TestIsCited(unittest.TestCase):
    def test_any_name_in_text(self):
        self.assertTrue(is_cited("I ran the Sales Register report", ["Sales Invoice", "Sales Register"]))

    def test_case_insensitive(self):
        self.assertTrue(is_cited("see accounts receivable", ["Accounts Receivable"]))

    def test_none_cited(self):
        self.assertFalse(is_cited("I guessed", ["Sales Register"]))

    def test_no_cite_names(self):
        self.assertFalse(is_cited("anything", []))


def _result(question_id, correct):
    return {"id": question_id, "correct": correct}


class TestRegressions(unittest.TestCase):
    def test_only_correct_to_incorrect_counts(self):
        old = [_result("a", True), _result("b", True), _result("c", False), _result("d", False)]
        new = [_result("a", False), _result("b", True), _result("c", True), _result("d", False)]
        self.assertEqual(regressions(old, new), ["a"])

    def test_question_missing_from_new_run_is_a_regression(self):
        self.assertEqual(regressions([_result("a", True)], []), ["a"])

    def test_new_question_is_not_a_regression(self):
        self.assertEqual(regressions([], [_result("a", False)]), [])

    def test_no_regressions(self):
        same = [_result("a", True)]
        self.assertEqual(regressions(same, same), [])


class TestCompareScript(unittest.TestCase):
    """Run compare.py itself on two hand-made results files (test input, not business answers)."""

    def _run(self, old, new):
        with tempfile.TemporaryDirectory() as folder:
            paths = []
            for name, rows in (("old.json", old), ("new.json", new)):
                path = os.path.join(folder, name)
                with open(path, "w") as handle:
                    json.dump({"model": "m", "results": rows}, handle)
                paths.append(path)
            return subprocess.run(
                [sys.executable, str(HERE / "compare.py"), *paths], capture_output=True, text=True
            )

    def test_exit_non_zero_on_regression(self):
        done = self._run([_result("a", True)], [_result("a", False)])
        self.assertEqual(done.returncode, 1)
        self.assertIn("REGRESSION", done.stdout)

    def test_exit_zero_when_nothing_regressed(self):
        done = self._run([_result("a", False)], [_result("a", True)])
        self.assertEqual(done.returncode, 0)


if __name__ == "__main__":
    unittest.main()
