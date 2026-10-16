# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""The word normaliser shared by report search and topic search."""

from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.search_tokens import singular, tokens


class TestSearchTokens(BaseAssistantTest):
    def test_plural_and_singular_normalise_to_the_same_word(self):
        for plural, word in (
            ("purchases", "purchase"),
            ("warehouses", "warehouse"),
            ("expenses", "expense"),
            ("analyses", "analysis"),
            ("statuses", "status"),
            ("cases", "case"),
            ("addresses", "address"),
            ("taxes", "tax"),
            ("batches", "batch"),
            ("classes", "class"),
            ("deliveries", "delivery"),
            ("companies", "company"),
            ("entries", "entry"),
            ("currencies", "currency"),
            ("sales", "sale"),
            ("invoices", "invoice"),
        ):
            with self.subTest(plural=plural):
                self.assertEqual(singular(plural), singular(word))

    def test_a_plural_meets_the_name_it_was_asked_about(self):
        self.assertTrue(tokens("purchases") & tokens("Purchase Register"))
        self.assertTrue(tokens("warehouses") & tokens("Warehouse wise Stock Balance"))

    def test_words_that_only_end_in_s_are_left_alone(self):
        self.assertEqual(singular("address"), "address")
        self.assertEqual(singular("gas"), "gas")

    def test_tokens_drop_stopwords_and_case(self):
        self.assertEqual(tokens("What are the Deliveries?"), {"delivery"})
        self.assertEqual(tokens(None), set())
