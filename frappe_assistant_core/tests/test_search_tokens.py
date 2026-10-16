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

import unittest

from frappe_assistant_core.utils.search_tokens import singular, tokens


class TestSearchTokens(unittest.TestCase):
    def test_plural_forms_meet_their_singular(self):
        for plural, word in (
            ("sales", "sale"),
            ("deliveries", "delivery"),
            ("companies", "company"),
            ("entries", "entry"),
            ("currencies", "currency"),
            ("addresses", "address"),
            ("taxes", "tax"),
            ("batches", "batch"),
            ("invoices", "invoice"),
        ):
            with self.subTest(plural=plural):
                self.assertEqual(singular(plural), singular(word))

    def test_words_that_only_end_in_s_are_left_alone(self):
        self.assertEqual(singular("address"), "address")
        self.assertEqual(singular("gas"), "gas")

    def test_tokens_drop_stopwords_and_case(self):
        self.assertEqual(tokens("What are the Deliveries?"), {"delivery"})
        self.assertEqual(tokens(None), set())
