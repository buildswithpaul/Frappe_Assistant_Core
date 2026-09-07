"""Signal gathering for curated suggestions — pure helpers + mocked frappe."""

import unittest
from unittest.mock import patch


class TestRouteDoctypes(unittest.TestCase):
    def test_parses_form_and_list_routes(self):
        from frappe_assistant_core.chat.api.suggestion_signals import _doctypes_from_routes

        routes = [
            "Form/Sales Invoice/ACC-SINV-0001",
            "Form/Sales Invoice/ACC-SINV-0002",
            "List/Customer",
            "app/random",
            "Form/Sales Invoice/ACC-SINV-0003",
        ]
        counts = _doctypes_from_routes(routes)
        self.assertEqual(counts["Sales Invoice"], 3)
        self.assertEqual(counts["Customer"], 1)
        self.assertNotIn("random", counts)

    def test_empty_and_malformed_routes(self):
        from frappe_assistant_core.chat.api.suggestion_signals import _doctypes_from_routes

        self.assertEqual(dict(_doctypes_from_routes(["", "Form", None])), {})


class TestRepeatedStems(unittest.TestCase):
    def test_finds_repeated_normalized_stems(self):
        from frappe_assistant_core.chat.api.suggestion_signals import _repeated_stems

        contents = [
            "Show me overdue invoices for ACME",
            "show me overdue invoices for Globex!",
            "Show me overdue invoices for Initech",
            "Totally unrelated one-off question",
        ]
        stems = _repeated_stems(contents)
        self.assertEqual(stems, ["show me overdue invoices for"])

    def test_no_repeats_returns_empty(self):
        from frappe_assistant_core.chat.api.suggestion_signals import _repeated_stems

        self.assertEqual(_repeated_stems(["one", "two", "three"]), [])


class TestGatherSignals(unittest.TestCase):
    @patch("frappe_assistant_core.chat.api.suggestion_signals.frappe")
    def test_shape_and_role_filtering(self, mock_frappe):
        mock_frappe.get_all.side_effect = [
            # FAC Chat Message rows
            [
                {"content": "Audit Sales Invoice data", "role": "user", "context_doctype": "Sales Invoice"},
                {
                    "content": "Audit Sales Invoice data please",
                    "role": "user",
                    "context_doctype": "Sales Invoice",
                },
                {"content": "reply", "role": "assistant", "context_doctype": None},
            ],
            # Route History rows
            [{"route": "Form/Customer/C-001"}, {"route": "List/Customer"}],
        ]
        mock_frappe.get_roles.return_value = ["All", "Guest", "Accounts Manager", "System Manager"]
        mock_frappe.local.lang = "en"
        from frappe_assistant_core.chat.api.suggestion_signals import gather_suggestion_signals

        out = gather_suggestion_signals("someone@example.com")
        self.assertEqual(out["roles"], ["Accounts Manager"])
        self.assertIn("Sales Invoice", out["top_doctypes"])
        self.assertIn("Customer", out["top_doctypes"])
        # chat-context doctypes outweigh navigation
        self.assertEqual(out["top_doctypes"][0], "Sales Invoice")
        self.assertEqual(out["locale"], "en")
        self.assertLessEqual(len(out["sample_prompts"]), 5)
        for s in out["sample_prompts"]:
            self.assertLessEqual(len(s), 120)
