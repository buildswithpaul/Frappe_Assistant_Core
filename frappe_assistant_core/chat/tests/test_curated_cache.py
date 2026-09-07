"""Curated-suggestion caching + merge behavior. frappe fully mocked."""

import unittest
from unittest.mock import MagicMock, patch


class TestCuratedCache(unittest.TestCase):
    @patch("frappe_assistant_core.chat.api.curated.frappe")
    def test_cache_hit_returns_rows_and_skips_enqueue(self, mock_frappe):
        mock_frappe.cache.get_value.return_value = {
            "suggestions": [{"text": "Ask", "subtext": "why", "category": "data"}],
            "generated_at": "x",
        }
        from frappe_assistant_core.chat.api.curated import (
            get_cached_curated,
            schedule_regeneration_if_stale,
        )

        rows = get_cached_curated("u@example.com")
        self.assertEqual(rows[0]["text"], "Ask")
        schedule_regeneration_if_stale("u@example.com")
        mock_frappe.enqueue.assert_not_called()

    @patch("frappe_assistant_core.chat.api.curated.frappe")
    def test_cache_miss_enqueues_dedup_job(self, mock_frappe):
        mock_frappe.cache.get_value.return_value = None
        from frappe_assistant_core.chat.api.curated import schedule_regeneration_if_stale

        schedule_regeneration_if_stale("u@example.com")
        mock_frappe.enqueue.assert_called_once()
        kwargs = mock_frappe.enqueue.call_args.kwargs
        self.assertEqual(kwargs["queue"], "short")
        self.assertTrue(kwargs["deduplicate"])
        self.assertEqual(kwargs["job_id"], "curated-sugg-u@example.com")
        self.assertEqual(kwargs["for_user"], "u@example.com")

    @patch("frappe_assistant_core.chat.api.curated.gather_suggestion_signals", return_value={"roles": []})
    @patch("frappe_assistant_core.chat.api.curated._ar_user_id", return_value="u@example.com")
    @patch("frappe_assistant_core.chat.api.curated.get_fac_cloud_client")
    @patch("frappe_assistant_core.chat.api.curated.frappe")
    def test_regenerate_success_writes_cache(self, mock_frappe, mock_get_client, _uid, _sig):
        client = MagicMock()
        client.generate_curated_suggestions.return_value = {
            "suggestions": [
                {"text": "A", "subtext": "", "category": "data"},
                {"text": "B", "subtext": "", "category": "docs"},
            ],
            "generated_at": "now",
        }
        mock_get_client.return_value = client
        from frappe_assistant_core.chat.api.curated import regenerate_curated_suggestions

        regenerate_curated_suggestions(for_user="u@example.com")
        mock_frappe.cache.set_value.assert_called_once()
        self.assertEqual(mock_frappe.cache.set_value.call_args.kwargs["expires_in_sec"], 86400)

    @patch("frappe_assistant_core.chat.api.curated.gather_suggestion_signals", return_value={"roles": []})
    @patch("frappe_assistant_core.chat.api.curated._ar_user_id", return_value="u@example.com")
    @patch("frappe_assistant_core.chat.api.curated.get_fac_cloud_client")
    @patch("frappe_assistant_core.chat.api.curated.frappe")
    def test_regenerate_failure_logs_never_raises(self, mock_frappe, mock_get_client, _uid, _sig):
        client = MagicMock()
        client.generate_curated_suggestions.side_effect = RuntimeError("down")
        mock_get_client.return_value = client
        from frappe_assistant_core.chat.api.curated import regenerate_curated_suggestions

        regenerate_curated_suggestions(for_user="u@example.com")  # must not raise
        mock_frappe.log_error.assert_called_once()
        mock_frappe.cache.set_value.assert_not_called()


class TestCuratedSurvivesTemplateFlood(unittest.TestCase):
    """Regression guard: curated rows must be emitted before the template
    catalog so result[:12] in get_suggested_prompts can never truncate them
    out when the catalog alone has 12+ unpinned entries."""

    @patch("frappe_assistant_core.chat.api.prompts._get_default_prompts", return_value=[])
    @patch("frappe_assistant_core.chat.api.curated.schedule_regeneration_if_stale")
    @patch("frappe_assistant_core.chat.api.curated.get_cached_curated")
    @patch("frappe_assistant_core.chat.api.prompts._get_template_suggestions")
    @patch("frappe_assistant_core.chat.api.prompts.frappe")
    def test_curated_rows_survive_twelve_cap_with_flooded_templates(
        self, mock_frappe, mock_get_templates, mock_get_curated, _mock_schedule, _mock_defaults
    ):
        mock_frappe.session.user = "u@example.com"
        mock_frappe.db.get_value.return_value = None

        mock_get_curated.return_value = [
            {"text": f"Curated {i}", "subtext": "", "category": "general"} for i in range(3)
        ]
        template_rows = [
            {
                "name": f"template_{i}",
                "description": f"Template {i}",
                "has_arguments": False,
                "source": "contextual",
            }
            for i in range(15)
        ]
        mock_get_templates.return_value = (
            template_rows,
            {"templates": [], "categories": [], "pinned": []},
        )

        from frappe_assistant_core.chat.api.prompts import get_suggested_prompts

        response = get_suggested_prompts()
        suggestions = response["suggestions"]

        self.assertEqual(len(suggestions), 12)
        curated_descriptions = {f"Curated {i}" for i in range(3)}
        first_twelve_descriptions = {s["description"] for s in suggestions}
        self.assertTrue(curated_descriptions.issubset(first_twelve_descriptions))
        # curated rows must lead the list, ahead of the flooded template catalog
        self.assertEqual(
            [s["description"] for s in suggestions[:3]],
            ["Curated 0", "Curated 1", "Curated 2"],
        )
