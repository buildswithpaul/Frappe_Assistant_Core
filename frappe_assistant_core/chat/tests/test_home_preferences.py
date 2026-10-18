# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

import json
import unittest
from unittest.mock import patch

import frappe

from frappe_assistant_core.chat import home_signals
from frappe_assistant_core.chat.api import home, prompts
from frappe_assistant_core.chat.doctype.fac_chat_user_preferences.fac_chat_user_preferences import (
    FACChatUserPreferences,
)
from frappe_assistant_core.chat.home_preferences import load_home_preferences
from frappe_assistant_core.chat.home_signals import Signal, SignalResult, compute_home_signals
from frappe_assistant_core.tests.base_test import BaseAssistantTest


def _result():
    return SignalResult(count=1, title="t", detail="d", ask="a", action="act", source="s")


class HomePreferencesTestCase(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.user = frappe.session.user
        self.addCleanup(frappe.cache.hdel, home.HOME_SIGNALS_CACHE_KEY, self.user)
        frappe.cache.hdel(home.HOME_SIGNALS_CACHE_KEY, self.user)
        # The transaction rolls back per class, not per test, so start each test from the defaults.
        home.update_home_preferences(
            show_needs_you=True,
            needs_you_count=3,
            hidden_signals=[],
            show_suggested_prompts=True,
            show_personalized_suggestions=True,
        )

    def _signal(self, signal_id, calls=None, tone="neutral"):
        def compute(user, company):
            if calls is not None:
                calls.append(signal_id)
            return _result()

        return Signal(
            id=signal_id,
            label=signal_id,
            lenses=(),
            tone=tone,
            requires_doctypes=(),
            requires_apps=(),
            compute=compute,
        )


class TestSignalFiltering(HomePreferencesTestCase):
    def test_hidden_signal_is_not_computed_and_absent_from_items(self):
        calls: list[str] = []
        # Manufactured: the test catalogue stands in for the real one; "todos" is a real id so the
        # hide goes through the production endpoint.
        catalogue = [self._signal("todos", calls), self._signal("b", calls)]
        home.hide_home_signal("todos")
        with patch.object(home_signals, "CATALOGUE", catalogue):
            payload = compute_home_signals(self.user)
        self.assertEqual(calls, ["b"])
        self.assertEqual([i["id"] for i in payload["items"]], ["b"])
        self.assertIn("todos", payload["hidden_signals"])

    def test_needs_you_off_runs_no_signal(self):
        calls: list[str] = []
        home.update_home_preferences(show_needs_you=False)
        with patch.object(home_signals, "CATALOGUE", [self._signal("a", calls)]):
            payload = compute_home_signals(self.user)
        self.assertEqual(calls, [])
        self.assertEqual(payload["items"], [])
        self.assertFalse(payload["needs_you_enabled"])

    def test_count_one_caps_items_to_one(self):
        catalogue = [self._signal("a"), self._signal("b")]
        home.update_home_preferences(needs_you_count=1)
        with patch.object(home_signals, "CATALOGUE", catalogue):
            payload = compute_home_signals(self.user)
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["needs_you_count"], 1)
        self.assertTrue(payload["needs_you_enabled"])

    def test_defaults_without_a_preferences_row(self):
        prefs = load_home_preferences("nobody-has-this-user@example.com")
        self.assertEqual(
            prefs,
            {
                "show_needs_you": True,
                "needs_you_count": 3,
                "hidden_signals": [],
                "show_suggested_prompts": True,
                "show_personalized_suggestions": True,
            },
        )


class TestPreferenceEndpoints(HomePreferencesTestCase):
    def test_unknown_id_is_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            home.update_home_preferences(hidden_signals=["approvals", "nope"])
        with self.assertRaises(frappe.ValidationError):
            home.hide_home_signal("nope")

    def test_failed_workflows_is_hideable_and_listed(self):
        result = home.hide_home_signal("failed_workflows")
        self.assertIn("failed_workflows", result["hidden_signals"])
        self.assertIn("failed_workflows", [s["id"] for s in home.get_home_preferences()["signals"]])

    def test_hide_dedupes_and_invalidates_cache(self):
        home.hide_home_signal("todos")
        frappe.cache.hset(home.HOME_SIGNALS_CACHE_KEY, self.user, {"computed_at": 1, "payload": {}})
        result = home.hide_home_signal("todos")
        self.assertEqual(result["hidden_signals"].count("todos"), 1)
        self.assertIsNone(frappe.cache.hget(home.HOME_SIGNALS_CACHE_KEY, self.user))

    def test_update_changes_only_provided_fields_and_coerces_strings(self):
        before = home.get_home_preferences()
        after = home.update_home_preferences(
            show_needs_you="0", needs_you_count="9", hidden_signals=json.dumps(["todos", "todos"])
        )
        self.assertFalse(after["show_needs_you"])
        self.assertEqual(after["needs_you_count"], 3)
        self.assertEqual(after["hidden_signals"], ["todos"])
        self.assertEqual(after["show_suggested_prompts"], before["show_suggested_prompts"])
        self.assertEqual(home.update_home_preferences(needs_you_count=0)["needs_you_count"], 1)
        result = home.update_home_preferences(show_personalized_suggestions="false")
        self.assertFalse(result["show_personalized_suggestions"])
        self.assertEqual(result["show_suggested_prompts"], before["show_suggested_prompts"])

    def test_update_invalidates_cache(self):
        frappe.cache.hset(home.HOME_SIGNALS_CACHE_KEY, self.user, {"computed_at": 1, "payload": {}})
        home.update_home_preferences(show_needs_you=True)
        self.assertIsNone(frappe.cache.hget(home.HOME_SIGNALS_CACHE_KEY, self.user))

    def test_non_string_ids_raise_a_validation_error(self):
        for bad in ({}, 5, None):
            with self.assertRaises(frappe.ValidationError):
                home.update_home_preferences(hidden_signals=[bad])
        with self.assertRaises(frappe.ValidationError):
            home.update_home_preferences(hidden_signals="5")


class TestPreferencesController(HomePreferencesTestCase):
    def test_direct_save_invalidates_cache_and_rejects_unknown_id(self):
        # Direct save is how Desk, REST and the privacy erase write the row.
        prefs = FACChatUserPreferences.get_or_create_preferences(self.user)
        frappe.cache.hset(home.HOME_SIGNALS_CACHE_KEY, self.user, {"computed_at": 1, "payload": {}})
        prefs.show_needs_you = 0
        prefs.save(ignore_permissions=True)
        self.assertIsNone(frappe.cache.hget(home.HOME_SIGNALS_CACHE_KEY, self.user))

        prefs.hidden_home_signals = json.dumps(["nope"])
        with self.assertRaises(frappe.ValidationError):
            prefs.save(ignore_permissions=True)

    def test_retired_stored_id_is_dropped_but_a_new_unknown_id_is_rejected(self):
        home.update_home_preferences(hidden_signals=["todos"])
        # Manufactured: production reaches this when a later release retires a signal id that
        # users had already hidden, leaving the retired id in their stored JSON.
        frappe.db.set_value(
            "FAC Chat User Preferences",
            self.user,
            "hidden_home_signals",
            json.dumps(["todos", "retired_signal"]),
        )
        self.assertNotIn("retired_signal", home.get_home_preferences()["hidden_signals"])

        prefs = FACChatUserPreferences.get_or_create_preferences(self.user)
        prefs.hidden_home_signals = json.dumps(["todos", "retired_signal", "brand_new_unknown"])
        with self.assertRaises(frappe.ValidationError):
            prefs.save(ignore_permissions=True)

        prefs = FACChatUserPreferences.get_or_create_preferences(self.user)
        prefs.hidden_home_signals = json.dumps(["todos", "retired_signal", "approvals"])
        prefs.save(ignore_permissions=True)
        self.assertEqual(json.loads(prefs.hidden_home_signals), ["todos", "approvals"])

    def test_direct_save_clamps_count(self):
        prefs = FACChatUserPreferences.get_or_create_preferences(self.user)
        prefs.needs_you_count = 99
        prefs.save(ignore_permissions=True)
        self.assertEqual(prefs.needs_you_count, 3)


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's role set")
class TestApplicableSignals(HomePreferencesTestCase):
    def test_accounts_only_user_does_not_see_hr_or_stock_signals(self):
        email = "home-prefs-accounts@example.com"
        frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": "Accounts",
                "send_welcome_email": 0,
                "roles": [{"role": "Accounts User"}],
            }
        ).insert(ignore_permissions=True)
        self.addCleanup(frappe.set_user, "Administrator")
        # nosemgrep: frappe-setuser — test acts as the user the endpoint serves
        frappe.set_user(email)
        ids = {s["id"] for s in home.get_home_preferences()["signals"]}
        self.assertTrue(
            ids.isdisjoint(
                {
                    "leave_to_approve",
                    "expense_claims_to_approve",
                    "below_reorder",
                    "late_purchase_orders",
                    "pending_material_requests",
                    "quotations_expiring",
                    "late_sales_orders",
                    "stale_leads",
                }
            ),
            ids,
        )
        self.assertIn("approvals", ids)
        self.assertIn("failed_workflows", ids)


class TestPersonalisedSuggestionsSwitch(HomePreferencesTestCase):
    CURATED = [{"text": "Curated question about sales", "subtext": "", "category": "general"}]

    def _suggestions(self):
        with (
            patch("frappe_assistant_core.chat.api.curated.get_cached_curated", return_value=self.CURATED),
            patch(
                "frappe_assistant_core.chat.api.curated.schedule_regeneration_if_stale", autospec=True
            ) as scheduler,
            patch.object(prompts, "_get_template_suggestions", return_value=([], {})),
            patch(
                "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=None
            ) as ar,
        ):
            result = prompts.get_suggested_prompts()
        return result, scheduler, ar

    def test_on_serves_curated_and_schedules(self):
        result, scheduler, _ar = self._suggestions()
        scheduler.assert_called_once_with(self.user)
        self.assertIn("personalized", {s["source"] for s in result["suggestions"]})

    def test_unreadable_preferences_fail_closed(self):
        with patch.object(
            prompts, "load_home_preferences", autospec=True, side_effect=RuntimeError("db down")
        ):
            result, scheduler, ar = self._suggestions()
        scheduler.assert_not_called()
        ar.assert_not_called()
        self.assertNotIn("personalized", {s["source"] for s in result["suggestions"]})

    def test_off_serves_no_curated_and_schedules_nothing(self):
        home.update_home_preferences(show_personalized_suggestions=False)
        result, scheduler, ar = self._suggestions()
        scheduler.assert_not_called()
        ar.assert_not_called()
        self.assertNotIn("personalized", {s["source"] for s in result["suggestions"]})
        self.assertFalse(result["suggestions_disabled"])
        self.assertTrue(result["suggestions"])


if __name__ == "__main__":
    unittest.main()
