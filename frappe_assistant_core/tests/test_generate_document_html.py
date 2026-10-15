# Frappe Assistant Core - generate_document HTML pipeline tests
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Tests for the HTML generate_document hands to the PDF renderer.

The PDF itself depends on which renderer the server has, so these pin the
HTML and the renderer options that decide how it looks.
"""

import sys
from unittest.mock import patch

from frappe_assistant_core.plugins.faco.tools.generate_document import GenerateDocument
from frappe_assistant_core.tests.base_test import BaseAssistantTest


def build(markdown: str, title: str | None = "Report", orientation: str = "portrait") -> str:
    return GenerateDocument()._build_html(markdown, title=title, orientation=orientation, page_size="A4")


class TestMarkdownConversion(BaseAssistantTest):
    def test_list_straight_after_a_line_of_text_is_a_list(self):
        # How models usually write it; strict markdown made it one paragraph of hyphens.
        html = build("Key points:\n- Revenue up\n- Costs down")
        self.assertIn("<li>Revenue up</li>", html)
        self.assertNotIn("- Revenue up", html)

    def test_table_column_alignment_survives_sanitising(self):
        html = build("| Item | Amount |\n|:--|--:|\n| A | 1,000 |")
        self.assertIn('<td align="right">1,000</td>', html)
        self.assertIn('<th align="left">Item</th>', html)

    def test_strikethrough(self):
        self.assertIn("<s>old</s>", build("Price ~~old~~ new"))

    def test_formatting_survives_without_bleach(self):
        # Frappe v16 dropped bleach (frappe/frappe#41960). Its absence made the old
        # sanitiser strip every tag, so on current v16 sites each PDF lost its
        # headings, lists, tables and rich blocks.
        with patch.dict(sys.modules, {"bleach": None}):
            html = build('## Heading\n\n- one\n- two\n\n```callout type="tip"\nA\n```')
        self.assertIn("<h2>Heading</h2>", html)
        self.assertIn("<li>one</li>", html)
        self.assertIn('class="callout"', html)

    def test_script_is_still_stripped(self):
        html = build("Hello <script>alert(1)</script> <img src=x onerror=alert(1)>")
        self.assertNotIn("<script", html)
        self.assertNotIn("onerror", html)


class TestDocumentLayout(BaseAssistantTest):
    def test_title_header_without_a_cover(self):
        self.assertIn('<h1 class="doc-title">Report</h1>', build("Body"))

    def test_no_title_header_when_a_cover_carries_the_title(self):
        # The header plus the cover gave the title a page of its own.
        html = build('```cover title="Report"\n```\n\nBody')
        self.assertNotIn('class="doc-title"', html)
        self.assertIn('class="cover-page"', html)

    def test_margins_are_set_once_on_the_page(self):
        # A .print-format margin rule doubled the page margins in both renderers,
        # and Frappe's get_pdf copies it into wkhtmltopdf's margins as well.
        html = build("Body")
        self.assertIn("margin: 15mm 15mm 20mm 15mm;", html)
        self.assertNotIn(".print-format {", html)

    def test_cover_fits_the_page_in_either_orientation(self):
        self.assertIn("height: 260mm;", build('```cover title="R"\n```'))
        self.assertIn("height: 173mm;", build('```cover title="R"\n```', orientation="landscape"))

    def test_template_avoids_css_wkhtmltopdf_cannot_render(self):
        html = build("Body")
        for unsupported in ("display: flex", "gap:", "100vh"):
            self.assertNotIn(unsupported, html)
        self.assertIn("background-color: #3d56a8;", html)


class TestWkhtmltopdfFallback(BaseAssistantTest):
    def test_fallback_gets_margins_and_a_page_number_footer(self):
        # Production reaches this path whenever WeasyPrint's system libraries are
        # missing: the import fails and the tool falls back to Frappe's get_pdf.
        with patch.dict(sys.modules, {"weasyprint": None}):
            with patch("frappe.utils.pdf.get_pdf", autospec=True, return_value=b"%PDF") as get_pdf:
                GenerateDocument()._generate_pdf("<html></html>", "A4", "portrait", title="Q1 [draft]")
        options = get_pdf.call_args.kwargs["options"]
        self.assertEqual(options["margin-top"], "15mm")
        self.assertEqual(options["margin-bottom"], "20mm")
        self.assertEqual(options["footer-right"], "[page] / [topage]")
        # Square brackets are wkhtmltopdf variables, so a title cannot carry them.
        self.assertEqual(options["footer-left"], "Q1 (draft)")
