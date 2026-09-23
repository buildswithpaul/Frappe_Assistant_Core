# Frappe Assistant Core - Powered by FAC Cloud
# Copyright (C) 2026 Paul Clinton
# AGPLv3

"""Type-aware ordering comparisons in trigger filters.

Both sides used to be coerced with ``float()``, so every Date, Datetime, Time
and Data comparison the filter editor invites raised and returned False. Filters
are AND-only, so one such row silently killed the whole trigger with no log row
and nothing to debug.
"""

import datetime
import unittest

from frappe_assistant_core.chat.workflows.triggers.filters import (
    evaluate_filters,
    first_failing_filter,
)


class _Row:
    """Stand-in for a FAC Workflow Trigger Filter child row."""

    def __init__(self, fieldname, operator, value):
        self.fieldname = fieldname
        self.operator = operator
        self.value = value


class TestNumericComparisons(unittest.TestCase):
    def test_numbers_still_compare_as_numbers(self):
        doc = {"grand_total": 250}
        self.assertTrue(evaluate_filters(doc, [_Row("grand_total", ">", "100")]))
        self.assertFalse(evaluate_filters(doc, [_Row("grand_total", "<", "100")]))

    def test_numeric_strings_compare_as_numbers_not_text(self):
        # "9" > "10" as text; 9 > 10 is False.
        self.assertFalse(evaluate_filters({"qty": "9"}, [_Row("qty", ">", "10")]))


class TestDateComparisons(unittest.TestCase):
    def test_date_field_compares_chronologically(self):
        doc = {"due_date": datetime.date(2026, 6, 1)}
        self.assertTrue(evaluate_filters(doc, [_Row("due_date", ">", "2026-01-01")]))
        self.assertFalse(evaluate_filters(doc, [_Row("due_date", "<", "2026-01-01")]))

    def test_datetime_field_compares_chronologically(self):
        doc = {"creation": datetime.datetime(2026, 6, 1, 12, 30)}
        self.assertTrue(evaluate_filters(doc, [_Row("creation", ">=", "2026-06-01 00:00:00")]))
        self.assertFalse(evaluate_filters(doc, [_Row("creation", ">", "2026-06-02 00:00:00")]))

    def test_time_field_compares_as_a_duration(self):
        doc = {"posting_time": datetime.timedelta(hours=14, minutes=5)}
        self.assertTrue(evaluate_filters(doc, [_Row("posting_time", ">", "09:00:00")]))
        self.assertFalse(evaluate_filters(doc, [_Row("posting_time", "<", "09:00:00")]))

    def test_an_unparseable_date_does_not_match(self):
        doc = {"due_date": datetime.date(2026, 6, 1)}
        self.assertFalse(evaluate_filters(doc, [_Row("due_date", ">", "not a date")]))


class TestTextComparisons(unittest.TestCase):
    def test_text_falls_back_to_string_ordering(self):
        doc = {"item_code": "ITEM-B"}
        self.assertTrue(evaluate_filters(doc, [_Row("item_code", ">", "ITEM-A")]))
        self.assertFalse(evaluate_filters(doc, [_Row("item_code", ">", "ITEM-C")]))

    def test_a_missing_value_has_no_position_in_an_ordering(self):
        # The old float() path answered "absent equals zero", so `< 100`
        # matched every unset amount.
        self.assertFalse(evaluate_filters({"amount": None}, [_Row("amount", "<", "100")]))
        self.assertFalse(evaluate_filters({"amount": ""}, [_Row("amount", ">", "100")]))


class TestFirstFailingFilter(unittest.TestCase):
    def test_reports_the_row_that_stopped_the_fire(self):
        doc = {"status": "Open", "grand_total": 500}
        rows = [
            _Row("grand_total", ">", "100"),
            _Row("status", "=", "Closed"),
        ]
        failing = first_failing_filter(doc, rows)
        self.assertIsNotNone(failing)
        self.assertEqual(failing.fieldname, "status")

    def test_returns_none_when_everything_passes(self):
        doc = {"status": "Closed"}
        self.assertIsNone(first_failing_filter(doc, [_Row("status", "=", "Closed")]))

    def test_no_filters_is_no_constraint(self):
        self.assertIsNone(first_failing_filter({}, []))
        self.assertTrue(evaluate_filters({}, []))
