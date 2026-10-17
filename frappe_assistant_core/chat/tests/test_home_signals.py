# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

import time
import unittest
from unittest.mock import patch

import frappe
from frappe.utils import add_days, today

from frappe_assistant_core.chat import home_signals
from frappe_assistant_core.chat.api import home
from frappe_assistant_core.chat.home_signals import (
    Signal,
    SignalResult,
    compute_home_signals,
    rank,
    resolve_lenses,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest


def _signal(signal_id, tone="neutral", lenses=(), doctypes=(), compute=None):
    return Signal(
        id=signal_id,
        lenses=lenses,
        tone=tone,
        requires_doctypes=doctypes,
        requires_apps=(),
        compute=compute or (lambda user, company: _result(1)),
    )


def _result(count):
    return SignalResult(count=count, title="t", detail="d", ask="a", source="s")


class TestResolveLenses(unittest.TestCase):
    def test_accounts_user_gets_accounts_lens(self):
        self.assertEqual(resolve_lenses(["Accounts User"], ["erpnext"]), ["accounts"])

    def test_hr_lens_needs_hrms_installed(self):
        self.assertEqual(resolve_lenses(["HR Manager"], ["erpnext"]), [])
        self.assertEqual(resolve_lenses(["HR Manager"], ["erpnext", "hrms"]), ["hr"])

    def test_multiple_roles_keep_catalogue_order(self):
        self.assertEqual(
            resolve_lenses(["Sales User", "Accounts Manager"], ["erpnext"]), ["accounts", "sales"]
        )


class TestRank(unittest.TestCase):
    def test_zero_counts_are_dropped(self):
        items = rank([(_signal("a"), _result(0)), (_signal("b"), _result(2))], cap=3)
        self.assertEqual([i["id"] for i in items], ["b"])

    def test_danger_outranks_warning_outranks_neutral(self):
        results = [
            (_signal("n", "neutral"), _result(1)),
            (_signal("w", "warning"), _result(1)),
            (_signal("d", "danger"), _result(1)),
        ]
        self.assertEqual([i["id"] for i in rank(results, cap=3)], ["d", "w", "n"])

    def test_cap_limits_items(self):
        results = [(_signal(f"s{i}"), _result(1)) for i in range(5)]
        self.assertEqual(len(rank(results, cap=3)), 3)

    def test_ties_keep_catalogue_order(self):
        first, second = _signal("first", "warning"), _signal("second", "warning")
        with patch.object(home_signals, "CATALOGUE", [first, second]):
            items = rank([(second, _result(9)), (first, _result(1))], cap=3)
        self.assertEqual([i["id"] for i in items], ["first", "second"])

    def test_item_shape(self):
        item = rank([(_signal("a", "danger"), _result(4))], cap=3)[0]
        self.assertEqual(
            item,
            {"id": "a", "tone": "danger", "source": "s", "count": 4, "title": "t", "detail": "d", "ask": "a"},
        )


class TestHomeSignalsEndpoint(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.user = frappe.session.user
        frappe.cache.delete_value("fac_home_signals_err:boom")
        frappe.cache.hdel(home.HOME_SIGNALS_CACHE_KEY, self.user)

    def _insert_todo(self, date):
        # Production path: a user assigns a ToDo to themselves.
        return frappe.get_doc(
            {
                "doctype": "ToDo",
                "description": "home signal test",
                "date": date,
                "allocated_to": self.user,
                "assigned_by": self.user,
            }
        ).insert()

    def _todo_count(self):
        items = compute_home_signals(self.user)["items"]
        return next((i["count"] for i in items if i["id"] == "todos"), 0)

    def test_todo_due_today_is_counted(self):
        before = self._todo_count()
        self._insert_todo(today())
        self.assertEqual(self._todo_count(), before + 1)

    def test_future_todo_is_not_counted(self):
        before = self._todo_count()
        self._insert_todo(add_days(today(), 3))
        self.assertEqual(self._todo_count(), before)

    def test_missing_doctype_signal_is_skipped_silently(self):
        ghost = _signal("ghost", doctypes=("No Such DocType",))
        errors = frappe.db.count("Error Log")
        with patch.object(home_signals, "CATALOGUE", [ghost]):
            payload = compute_home_signals(self.user)
        self.assertEqual(payload["items"], [])
        self.assertEqual(frappe.db.count("Error Log"), errors)

    def test_raising_signal_logs_once_per_hour(self):
        def boom(user, company):
            raise RuntimeError("nope")

        errors = frappe.db.count("Error Log")
        with patch.object(home_signals, "CATALOGUE", [_signal("boom", compute=boom)]):
            compute_home_signals(self.user)
            compute_home_signals(self.user)
        self.assertEqual(frappe.db.count("Error Log"), errors + 1)

    def test_mixed_lenses_use_business_area(self):
        with (
            patch.object(home_signals, "CATALOGUE", []),
            patch("frappe.get_roles", return_value=["Sales User", "Accounts User"]),
        ):
            payload = compute_home_signals(self.user)
        self.assertEqual(payload["area"], "business")
        self.assertEqual(payload["lenses"], ["accounts", "sales"])

    def test_single_lens_uses_its_area(self):
        with patch.object(home_signals, "CATALOGUE", []), patch(
            "frappe.get_roles", return_value=["Sales User"]
        ):
            payload = compute_home_signals(self.user)
        self.assertEqual((payload["lens"], payload["area"]), ("sales", "pipeline"))

    def test_primary_lens_follows_top_ranked_signal(self):
        catalogue = [
            _signal("acc", "neutral", lenses=("accounts",)),
            _signal("sal", "danger", lenses=("sales",)),
        ]
        with (
            patch.object(home_signals, "CATALOGUE", catalogue),
            patch("frappe.get_roles", return_value=["Sales User", "Accounts User"]),
        ):
            payload = compute_home_signals(self.user)
        self.assertEqual(payload["lens"], "sales")

    def test_endpoint_serves_cache_when_fresh(self):
        home.get_home_signals()
        with patch.object(home, "compute_home_signals", autospec=True) as mocked:
            home.get_home_signals()
        mocked.assert_not_called()

    def test_endpoint_recomputes_when_stale(self):
        home.get_home_signals()
        entry = frappe.cache.hget(home.HOME_SIGNALS_CACHE_KEY, self.user)
        entry["computed_at"] = time.time() - 601
        frappe.cache.hset(home.HOME_SIGNALS_CACHE_KEY, self.user, entry)
        with patch.object(home, "compute_home_signals", autospec=True, return_value={"items": []}) as mocked:
            home.get_home_signals()
        mocked.assert_called_once()
