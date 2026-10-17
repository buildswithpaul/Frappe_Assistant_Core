# Frappe Assistant Core - Role-aware default prompt tests
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""The landing suggestion grid must always be able to backfill to 4 tiles
with defaults matched to the user's Frappe roles — an Accounts user should
never be offered "common support issues" as their default."""

import datetime
import unittest
from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api import prompts
from frappe_assistant_core.chat.api.prompts import _get_default_prompts, _role_bucket_prompts
from frappe_assistant_core.chat.page_asks import GENERIC_FORM_ASKS, LIST_ASKS, page_asks_for

APPS = ["frappe", "erpnext"]


class TestRoleBucketPrompts(unittest.TestCase):
    def test_sales_roles_get_sales_prompts_first(self):
        prompts = _role_bucket_prompts(["Sales User"], APPS)
        self.assertGreaterEqual(len(prompts), 4)
        self.assertTrue(prompts[0]["name"].startswith("sales_"))

    def test_accounts_roles_get_accounts_prompts_first(self):
        prompts = _role_bucket_prompts(["Accounts Manager"], APPS)
        self.assertTrue(prompts[0]["name"].startswith("accounts_"))

    def test_two_lenses_round_robin(self):
        prompts = _role_bucket_prompts(["Sales User", "Accounts User"], APPS)
        heads = [p["name"].split("_")[0] for p in prompts[:2]]
        self.assertEqual(sorted(heads), ["accounts", "sales"])

    def test_purchase_user_gets_stock_lens_prompts(self):
        prompts = _role_bucket_prompts(["Purchase User"], APPS)
        self.assertTrue(prompts[0]["name"].startswith("stock_"))
        self.assertFalse(any(p["name"].startswith("purchase_") for p in prompts))

    def test_support_bucket_kept(self):
        prompts = _role_bucket_prompts(["Support Team"], APPS)
        self.assertTrue(prompts[0]["name"].startswith("support_"))

    def test_hr_lens_needs_hrms(self):
        without = _role_bucket_prompts(["HR User"], APPS)
        self.assertTrue(without[0]["name"].startswith("generic_"))
        with_hrms = _role_bucket_prompts(["HR User"], [*APPS, "hrms"])
        self.assertTrue(with_hrms[0]["name"].startswith("hr_"))

    def test_unknown_roles_fall_back_to_generic(self):
        prompts = _role_bucket_prompts(["Blogger"], APPS)
        self.assertGreaterEqual(len(prompts), 4)
        self.assertTrue(all(p["name"].startswith("generic_") for p in prompts))

    def test_all_prompts_are_default_source(self):
        for p in _role_bucket_prompts(["Sales User", "HR User"], [*APPS, "hrms"]):
            self.assertEqual(p["source"], "default")

    def test_generic_filler_always_appended(self):
        prompts = _role_bucket_prompts(["Sales User"], APPS)
        self.assertTrue(any(p["name"].startswith("generic_") for p in prompts))

    def test_accounts_starters_are_concrete(self):
        descriptions = [p["description"] for p in _role_bucket_prompts(["Accounts User"], APPS)]
        self.assertIn("Who owes us the most, and since when?", descriptions)
        self.assertIn("Compare collections this month with last month", descriptions)
        self.assertIn("Draft a payment reminder to my most overdue customer", descriptions)
        self.assertIn(f"Summarise GST payable for {prompts._current_month_name()}", descriptions)
        self.assertIn("Which customers pay late most often?", descriptions)

    def test_current_month_name_follows_todays_month(self):
        for month, name in ((1, "January"), (3, "March"), (12, "December")):
            with patch.object(prompts, "getdate", return_value=datetime.date(2026, month, 15)):
                self.assertEqual(prompts._current_month_name(), name)

    def test_gst_starter_names_the_month(self):
        with patch.object(prompts, "getdate", return_value=datetime.date(2026, 3, 15)):
            starters = prompts._lens_starters()["accounts"]
        gst = next(s for s in starters if s["name"] == "accounts_gst_payable")
        self.assertEqual(gst["description"], "Summarise GST payable for March")
        self.assertEqual(gst["kind"], "see")

    def test_each_lens_offers_one_starter_of_every_kind(self):
        for lens, starters in prompts._lens_starters().items():
            kinds = {s["kind"] for s in starters}
            self.assertEqual(kinds, set(prompts.STARTER_KINDS), lens)

    def test_do_starters_are_actions_that_draft_or_prepare(self):
        for lens, starters in prompts._lens_starters().items():
            do = [s for s in starters if s["kind"] == "do"]
            self.assertEqual(len(do), 1, lens)
            self.assertRegex(do[0]["description"], r"^(Draft|Prepare|Help me)", lens)

    def test_kind_is_passed_through_to_the_returned_prompts(self):
        for p in _role_bucket_prompts(["Sales User"], APPS):
            self.assertIn(p["kind"], prompts.STARTER_KINDS)


class TestPageAsks(unittest.TestCase):
    def test_form_context_returns_page_asks_with_placeholders(self):
        asks = page_asks_for("Form", "Sales Invoice")
        self.assertTrue(asks)
        for ask in asks:
            self.assertIn("{name}", ask["description"])
            self.assertEqual(ask["source"], "page")
            self.assertFalse(ask["has_arguments"])

    def test_unknown_doctype_form_gets_generic_asks(self):
        asks = page_asks_for("Form", "Some Custom Doctype")
        self.assertEqual([a["description"] for a in asks], [str(t) for t in GENERIC_FORM_ASKS])

    def test_list_context_gets_list_asks(self):
        asks = page_asks_for("List", "Sales Invoice")
        self.assertEqual([a["description"] for a in asks], [str(t) for t in LIST_ASKS])
        self.assertTrue(all("{doctype}" in a["description"] for a in asks))

    def test_general_or_missing_doctype_gets_none(self):
        self.assertEqual(page_asks_for("General", None), [])
        self.assertEqual(page_asks_for("Form", None), [])

    def test_form_defaults_still_include_role_starters(self):
        with patch.object(frappe, "get_roles", autospec=True, return_value=["Accounts User"]):
            result = _get_default_prompts({"type": "Form", "doctype": "Sales Invoice"})
        sources = [p["source"] for p in result]
        self.assertEqual(sources[0], "page")
        self.assertIn("default", sources)
        self.assertTrue(any(p["name"].startswith("accounts_") for p in result))


class TestSuggestionCap(unittest.TestCase):
    def test_templates_cannot_push_out_page_asks_or_starter_kinds(self):
        # Manufactured: production reaches this when curated, pinned and marketplace templates
        # together exceed the cap; the template source is patched to return that many.
        templates = [
            {"name": f"tpl_{i}", "description": f"Template {i}", "has_arguments": False, "source": "pinned"}
            for i in range(14)
        ]
        context = '{"type": "Form", "doctype": "Sales Invoice"}'
        with (
            patch.object(prompts, "_get_template_suggestions", autospec=True, return_value=(templates, {})),
            patch.object(frappe, "get_roles", autospec=True, return_value=["Accounts User"]),
        ):
            suggestions = prompts.get_suggested_prompts(context)["suggestions"]

        self.assertEqual(len(suggestions), prompts.SUGGESTIONS_CAP)
        self.assertTrue([s for s in suggestions if s["source"] == "page"])
        self.assertEqual({s.get("kind") for s in suggestions if s.get("kind")}, set(prompts.STARTER_KINDS))
