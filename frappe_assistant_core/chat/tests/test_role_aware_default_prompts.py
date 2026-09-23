# Frappe Assistant Core - Role-aware default prompt tests
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""The landing suggestion grid must always be able to backfill to 4 tiles
with defaults matched to the user's Frappe roles — an Accounts user should
never be offered "common support issues" as their default."""

import unittest

from frappe_assistant_core.chat.api.prompts import _role_bucket_prompts


class TestRoleBucketPrompts(unittest.TestCase):
    def test_sales_roles_get_sales_prompts_first(self):
        prompts = _role_bucket_prompts(["Sales User"])
        self.assertGreaterEqual(len(prompts), 4)
        self.assertIn("sales", prompts[0]["name"])

    def test_accounts_roles_get_accounts_prompts_first(self):
        prompts = _role_bucket_prompts(["Accounts Manager"])
        self.assertIn("accounts", prompts[0]["name"])

    def test_two_buckets_round_robin(self):
        prompts = _role_bucket_prompts(["Sales User", "Accounts User"])
        heads = [p["name"].split("_")[0] for p in prompts[:2]]
        self.assertEqual(sorted(heads), ["accounts", "sales"])

    def test_unknown_roles_fall_back_to_generic(self):
        prompts = _role_bucket_prompts(["Blogger"])
        self.assertGreaterEqual(len(prompts), 4)
        self.assertTrue(all(p["name"].startswith("generic_") for p in prompts))

    def test_all_prompts_are_default_source(self):
        for p in _role_bucket_prompts(["Sales User", "HR User"]):
            self.assertEqual(p["source"], "default")

    def test_generic_filler_always_appended(self):
        prompts = _role_bucket_prompts(["Sales User"])
        self.assertTrue(any(p["name"].startswith("generic_") for p in prompts))
