# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""The chosen model is saved on the server so every browser and the Desk widget share it."""

import unittest
from unittest.mock import MagicMock, patch

import frappe
from frappe.handler import is_valid_http_method
from frappe.tests.utils import FrappeTestCase
from frappe.utils import random_string

from frappe_assistant_core.chat.api import models

PREFS = "FAC Chat User Preferences"


def _make_user(email: str) -> None:
    if not frappe.db.exists("User", email):
        frappe.get_doc(
            {"doctype": "User", "email": email, "first_name": "Model Pref", "send_welcome_email": 0}
        ).insert(ignore_permissions=True)


class TestSetSelectedModelEndpoint(unittest.TestCase):
    """Needs no column, so it runs on a site that has not migrated yet."""

    def test_it_is_post_only(self):
        self.assertIn(models.set_selected_model, frappe.whitelisted)
        self.assertEqual(
            frappe.allowed_http_methods_for_whitelisted_func[models.set_selected_model], ["POST"]
        )

    def test_a_get_request_is_refused(self):
        original = getattr(frappe.local, "request", None)
        frappe.local.request = MagicMock(method="GET")
        try:
            with self.assertRaises(frappe.PermissionError):
                is_valid_http_method(models.set_selected_model)
        finally:
            frappe.local.request = original


@unittest.skipUnless(
    frappe.db.has_column(PREFS, "selected_model"),
    "selected_model column is not on this site yet: run `bench migrate` to create it",
)
class TestSelectedModelPreference(FrappeTestCase):
    def setUp(self):
        super().setUp()
        suffix = random_string(6).lower()
        self.user = f"model-pref-{suffix}@example.com"
        self.other = f"model-pref-other-{suffix}@example.com"
        for email in (self.user, self.other):
            _make_user(email)
        self.addCleanup(frappe.set_user, "Administrator")

    def tearDown(self):
        frappe.set_user("Administrator")
        for email in (self.user, self.other):
            frappe.delete_doc(PREFS, email, force=True, ignore_missing=True)
            frappe.delete_doc("User", email, force=True, ignore_missing=True)
        super().tearDown()

    def _as(self, email: str) -> None:
        # nosemgrep: frappe-setuser — the endpoints act on the session user
        frappe.set_user(email)

    def test_set_then_get_round_trips(self):
        self._as(self.user)
        self.assertEqual(models.set_selected_model("gpt-saved")["selected_model"], "gpt-saved")
        self.assertEqual(models._saved_model(), "gpt-saved")

    def test_auto_is_accepted(self):
        self._as(self.user)
        models.set_selected_model("auto")
        self.assertEqual(models._saved_model(), "auto")

    def test_empty_clears(self):
        self._as(self.user)
        models.set_selected_model("gpt-saved")
        models.set_selected_model("")
        self.assertEqual(models._saved_model(), "")

    def test_an_overlong_id_is_refused(self):
        self._as(self.user)
        with self.assertRaises(frappe.ValidationError):
            models.set_selected_model("m" * 141)

    def test_another_users_row_is_untouched(self):
        # Production reaches this state when a colleague has already saved a choice.
        self._as(self.other)
        models.set_selected_model("colleague-model")
        self._as(self.user)
        models.set_selected_model("gpt-saved")
        self._as(self.other)
        self.assertEqual(models._saved_model(), "colleague-model")

    def test_get_available_models_returns_the_saved_choice(self):
        self._as(self.user)
        models.set_selected_model("gpt-saved")
        client = MagicMock()
        client.list_available_models.return_value = {"models": [], "max_tier_rank": 3}
        with patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client):
            result = models.get_available_models()
        self.assertEqual(result["selected_model"], "gpt-saved")

    def test_get_available_models_hides_a_saved_model_that_is_no_longer_offered(self):
        # Production reaches this when a model is retired or the plan is downgraded after the user
        # chose it. The stored row is intentionally untouched: Frappe rolls back writes made in a
        # GET, and a stale id is harmless (turns skip it, and it returns if the model is offered again).
        self._as(self.user)
        models.set_selected_model("retired-model")
        client = MagicMock()
        client.list_available_models.return_value = {"models": [{"model_id": "gpt-5"}]}
        with patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client):
            result = models.get_available_models()
        self.assertEqual(result["selected_model"], "")
        self.assertEqual(models._saved_model(), "retired-model")

    def test_choosing_a_model_drops_the_cached_availability(self):
        self._as(self.user)
        models._remember_available(["gpt-5"])
        models.set_selected_model("claude-new")
        self.assertIsNone(frappe.cache.get_value(models.available_models_key()))

    def test_get_available_models_keeps_auto_and_an_offered_model(self):
        self._as(self.user)
        client = MagicMock()
        client.list_available_models.return_value = {"models": [{"model_id": "gpt-5"}]}
        with patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client):
            for saved in ("auto", "gpt-5"):
                models.set_selected_model(saved)
                self.assertEqual(models.get_available_models()["selected_model"], saved)
