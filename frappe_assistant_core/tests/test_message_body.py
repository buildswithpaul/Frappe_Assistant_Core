# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Message bodies are sent the way the approval card shows them."""

from unittest.mock import patch

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.message_body import as_html_body


class TestMessageBody(BaseAssistantTest):
    def test_plain_text_becomes_escaped_html_with_line_breaks(self):
        self.assertEqual(
            as_html_body("1 < 2 & co,\nThanks *Bob*"), "<div>1 &lt; 2 &amp; co,<br>Thanks *Bob*</div>"
        )

    def test_html_is_left_alone(self):
        self.assertEqual(as_html_body("<p>Hi</p>\n<p>Bye</p>"), "<div><p>Hi</p>\n<p>Bye</p></div>")

    def test_markdown_leaves_the_body_alone(self):
        # Helpdesk sends with as_markdown=True; Frappe markdowns any body not starting with "<".
        self.assertNotIn("<em>", frappe.utils.md_to_html(as_html_body("Ships *Friday*\nThanks")))

    def test_send_email_sends_plain_text_as_the_card_shows_it(self):
        from frappe_assistant_core.plugins.core.tools.send_email import SendEmail

        with patch("frappe.sendmail") as sendmail:
            out = SendEmail().execute(
                {"recipients": ["a@example.com"], "subject": "Hi", "message": "Line one\nLine two"}
            )
        self.assertTrue(out["success"], out)
        self.assertEqual(sendmail.call_args.kwargs["message"], "<div>Line one<br>Line two</div>")
