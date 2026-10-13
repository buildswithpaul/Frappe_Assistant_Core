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

"""What FACO writes is markdown with rich blocks; Raven shows sanitised HTML and cannot draw charts."""

from frappe_assistant_core.integrations.raven import formatting
from frappe_assistant_core.tests.base_test import BaseAssistantTest

URL = "http://site/copilot/chat/s1"


class TestRavenFormatting(BaseAssistantTest):
    def test_markdown_becomes_html(self):
        self.assertIn("<strong>Open</strong>", formatting.to_raven_html("**Open**", URL))

    def test_a_chart_becomes_a_note_that_links_to_fac_chat(self):
        md = 'Here:\n```chart title="Monthly revenue"\n{"type":"bar"}\n```\nDone.'
        html = formatting.to_raven_html(md, URL)
        self.assertIn("Monthly revenue", html)
        self.assertIn(URL, html)
        self.assertNotIn('"type":"bar"', html)

    def test_a_callout_keeps_its_words(self):
        html = formatting.to_raven_html('```callout type="warning"\nCheck the due date.\n```', URL)
        self.assertIn("Check the due date.", html)

    def test_model_html_is_sanitised(self):
        html = formatting.to_raven_html("<script>alert(1)</script><img src=x onerror=alert(1)>ok", URL)
        self.assertNotIn("<script", html)
        self.assertNotIn("onerror", html)

    def test_handoff_names_the_action_and_links_the_session(self):
        html = formatting.handoff_html("create_document", {"doctype": "Sales Order"}, URL)
        self.assertIn("create a Sales Order", html)
        self.assertIn(URL, html)

    def test_a_question_hands_off_with_its_own_words(self):
        # Live: "FACO has a question for you" alone left the person guessing what was asked.
        html = formatting.handoff_html(
            "ask_user", {"question": "Delete ToDo tt8ko48kuj?", "description": "This is permanent."}, URL
        )
        self.assertIn("Delete ToDo tt8ko48kuj?", html)
        self.assertIn("This is permanent.", html)
        self.assertIn("Answer in FAC Chat", html)

    def test_out_of_credits_reads_like_the_widget(self):
        self.assertIn(
            "used all of this month's credits", formatting.error_text({"error_code": "quota_exhausted"})
        )

    def test_an_unregistered_site_says_so(self):
        self.assertIn("isn't connected to FAC Cloud", formatting.error_text({"action_required": "register"}))

    def test_other_errors_never_leak_detail(self):
        self.assertNotIn("secret", formatting.error_text({"error": "Traceback: secret"}))

    def test_a_refusal_carries_the_gates_reason(self):
        self.assertEqual(formatting.refusal_text({"can_use": False, "reason": "No seat"}), "No seat")

    def test_chat_switched_off_is_said_plainly(self):
        # can_use_faco answers chat_module_disabled with a status and no reason.
        text = formatting.refusal_text({"can_use": False, "status": "chat_module_disabled"})
        self.assertIn("FAC Chat is switched off", text)

    def test_model_text_cannot_mention_people(self):
        # Raven turns this markup into a real mention that notifies anyone named, member or not.
        md = 'Ping <span data-type="userMention" data-id="ceo@x.com">@CEO</span> now'
        html = formatting.to_raven_html(md, URL)
        self.assertNotIn("userMention", html)
        self.assertNotIn("ceo@x.com", html.replace("@CEO", ""))
