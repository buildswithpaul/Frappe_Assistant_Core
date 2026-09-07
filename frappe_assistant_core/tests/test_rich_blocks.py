# Frappe Assistant Core - Rich block preprocessing tests
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Pure-logic tests for the PDF rich-block preprocessor.

``rich_blocks`` imports nothing from frappe, so these run as plain unittest
without a site or database.
"""

import unittest

from frappe_assistant_core.plugins.faco.tools.rich_blocks import (
    preprocess_rich_blocks,
    restore_rich_blocks,
)


def render(markdown: str) -> str:
    """Run a markdown string through the full substitute → restore round trip."""
    processed, tokens = preprocess_rich_blocks(markdown)
    return restore_rich_blocks(processed, tokens)


class TestMetricDialects(unittest.TestCase):
    """A metric fence carries its data as fence attributes *or* as a JSON body.

    The documented dialect is attributes, but the model generalises from the
    ``chart`` fence beside it and writes a JSON body most of the time. Both
    surfaces (chat and PDF) have to accept both, or the same reply renders one
    way on screen and another in the download.
    """

    def test_fence_attribute_dialect(self):
        out = render('```metric title="Monthly Revenue" value="Rs 14,25,000" change="+18%" trend="up"\n```')
        self.assertIn("Monthly Revenue", out)
        self.assertIn("Rs 14,25,000", out)
        self.assertIn("+18%", out)

    def test_json_body_dialect(self):
        out = render('```metric\n{"label":"Companies shortlisted","value":"15"}\n```')
        self.assertIn("Companies shortlisted", out)
        self.assertIn(">15<", out)

    def test_json_suffix_renders(self):
        out = render('```metric\n{"label": "Hotel / Lodging", "value": "USD 275", "suffix": "/ night"}\n```')
        self.assertIn("Hotel / Lodging", out)
        self.assertIn("/ night", out)

    def test_json_numeric_value_coerced(self):
        out = render('```metric\n{"label":"Open tickets","value":15}\n```')
        self.assertIn("Open tickets", out)
        self.assertIn(">15<", out)

    def test_fence_attributes_win_over_body(self):
        out = render('```metric title="From attrs" value="1"\n{"label":"From body","value":"2"}\n```')
        self.assertIn("From attrs", out)
        self.assertNotIn("From body", out)

    def test_unrenderable_metric_falls_back_to_visible_code(self):
        # An empty card is indistinguishable from a rendering glitch; keep the
        # raw fence visible so a bad shape is reportable instead of invisible.
        out = render('```metric\n{"headline":"unknown shape"}\n```')
        self.assertIn("unknown shape", out)
        self.assertNotIn('class="metric-card"', out)

    def test_metric_values_are_escaped(self):
        out = render('```metric\n{"label":"<script>x</script>","value":"1"}\n```')
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)


class TestOtherBlocksUnaffected(unittest.TestCase):
    def test_chart_still_renders(self):
        out = render(
            '```chart\n{"type":"bar","title":"T","data":{"categories":["x"],'
            '"series":[{"name":"s","values":[1]}]}}\n```'
        )
        self.assertIn("<svg", out)
        self.assertIn("chart-wrap", out)

    def test_callout_still_renders(self):
        out = render('```callout type="warning" title="Heads up"\nBody text\n```')
        self.assertIn("callout", out)
        self.assertIn("Heads up", out)
        self.assertIn("Body text", out)


class TestCalloutJsonBody(unittest.TestCase):
    """The same "generalised from ``chart``" mistake, on the callout fence.

    Observed on a client instance: a ``{"type":"warning","title":…,
    "content":…}`` body rendered an *info* box with no title and the raw JSON
    as its text. The PDF renderer has to read the body for the same reason the
    chat one does — one reply, one appearance.
    """

    def test_reads_type_title_and_content_from_a_json_body(self):
        out = render(
            '```callout\n{"type":"warning","title":"Data quality caveat",'
            '"content":"All 216 Leads were bulk-imported."}\n```'
        )
        # The warning palette, not the info default the attrs-only read gave.
        self.assertIn("#f59e0b", out)
        self.assertIn('<div class="callout-title">Data quality caveat</div>', out)
        self.assertIn("All 216 Leads were bulk-imported.", out)
        # No JSON punctuation survives — escaped or otherwise. Matching on a
        # bare '"type"' would pass on the *unfixed* renderer, which escapes
        # the body to &quot;type&quot; before it reaches the page.
        self.assertNotIn("quot;", out)

    def test_attributes_win_over_the_json_body(self):
        out = render(
            '```callout type="error" title="From attrs"\n'
            '{"type":"warning","title":"From body","content":"Text"}\n```'
        )
        self.assertIn("From attrs", out)
        self.assertNotIn("From body", out)

    def test_message_alias_is_accepted(self):
        out = render('```callout\n{"type":"tip","message":"Try the filter."}\n```')
        self.assertIn("#10b981", out)
        self.assertIn("Try the filter.", out)
        self.assertNotIn("quot;", out)

    def test_unrecognised_json_body_stays_visible(self):
        out = render('```callout\n{"headline":"unknown shape"}\n```')
        self.assertIn("headline", out)


class TestMetricJsonArray(unittest.TestCase):
    """A JSON array is how the model writes a whole KPI row in one fence."""

    def test_renders_one_card_per_entry(self):
        out = render(
            '```metric\n[{"label":"Communications logged (all time)","value":"16"},'
            '{"label":"Logged against a Lead/Opp/Customer","value":"9"}]\n```'
        )
        self.assertEqual(out.count('class="metric-card"'), 2)
        self.assertIn("Communications logged (all time)", out)
        self.assertIn("Logged against a Lead/Opp/Customer", out)
        self.assertNotIn('"label"', out)

    def test_skips_entries_with_neither_title_nor_value(self):
        out = render('```metric\n[{"label":"Kept","value":"1"},{"note":"dropped"}]\n```')
        self.assertEqual(out.count('class="metric-card"'), 1)
        self.assertIn("Kept", out)

    def test_falls_back_to_raw_when_no_entry_is_usable(self):
        out = render('```metric\n[{"note":"a"},{"note":"b"}]\n```')
        self.assertNotIn('class="metric-card"', out)
        self.assertIn("note", out)

    def test_escapes_markup_from_an_array_entry(self):
        out = render('```metric\n[{"label":"<script>x</script>","value":"1"}]\n```')
        self.assertIn('class="metric-card"', out)
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)


if __name__ == "__main__":
    unittest.main()
