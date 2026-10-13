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

"""The sink turns relay events into edits of one Raven message, at most once a second."""

from frappe_assistant_core.integrations.raven.sink import ReplySink, ReplyWriter
from frappe_assistant_core.tests.base_test import BaseAssistantTest

URL = "http://site/copilot/chat/s1"


class FakeWriter(ReplyWriter):
    """Records what would be written to the Raven message and its status strip."""

    def __init__(self):
        self.saves, self.statuses = [], []

    def update(self, html: str) -> None:
        self.saves.append(html)

    def status(self, text: str | None) -> None:
        self.statuses.append(text)


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class TestReplySink(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.writer, self.clock = FakeWriter(), Clock()
        self.sink = ReplySink(self.writer, URL, clock=self.clock)

    def chunk(self, text: str, at: float) -> None:
        self.clock.now = at
        self.sink({"event": "stream_chunk", "accumulated": text})

    def test_chunks_inside_one_second_are_saved_once(self):
        self.chunk("He", 0.0)
        self.chunk("Hello", 0.4)
        self.chunk("Hello wor", 0.9)
        self.assertEqual(len(self.writer.saves), 1)
        self.chunk("Hello world", 1.1)
        self.assertEqual(len(self.writer.saves), 2)

    def test_the_final_text_is_always_saved(self):
        self.chunk("Hello", 0.0)
        self.chunk("Hello wor", 0.3)
        self.sink({"event": "stream_complete", "full_response": "Hello world"})
        self.assertIn("Hello world", self.writer.saves[-1])
        self.assertTrue(self.sink.done)
        self.assertIsNone(self.writer.statuses[-1])

    def test_a_tool_call_shows_in_the_status_strip(self):
        self.sink(
            {
                "event": "tool_call_start",
                "tool_name": "get_document",
                "input": {"doctype": "HD Ticket", "name": "3238"},
            }
        )
        self.assertIn("HD Ticket", self.writer.statuses[-1])

    def test_an_approval_ends_the_reply_with_the_hand_off(self):
        self.chunk("Let me create it.", 0.0)
        self.sink(
            {
                "event": "approval_required",
                "tool_name": "create_document",
                "input": {"doctype": "Sales Order"},
            }
        )
        self.assertIn("Review and approve in FAC Chat", self.writer.saves[-1])
        self.assertIn("Let me create it.", self.writer.saves[-1])
        self.assertTrue(self.sink.done)

    def test_events_after_the_hand_off_change_nothing(self):
        self.sink({"event": "approval_required", "tool_name": "create_document", "input": {}})
        saves = len(self.writer.saves)
        self.sink({"event": "stream_chunk", "accumulated": "resumed in FAC Chat"})
        self.assertEqual(len(self.writer.saves), saves)

    def test_an_error_replaces_the_reply_with_a_plain_sentence(self):
        self.sink({"event": "stream_error", "error_code": "quota_exhausted", "error": "internal detail"})
        self.assertIn("credits", self.writer.saves[-1])
        self.assertNotIn("internal detail", self.writer.saves[-1])
        self.assertTrue(self.sink.done)

    def test_a_stop_keeps_what_was_written(self):
        self.chunk("Partial", 0.0)
        self.sink({"event": "stream_aborted", "partial_response": "Partial answer"})
        self.assertIn("Partial answer", self.writer.saves[-1])
        self.assertIn("Stopped", self.writer.saves[-1])

    def test_an_empty_chunk_never_blanks_the_placeholder(self):
        # Live: the reply flashed empty when the first chunk arrived with no text yet.
        self.chunk("", 0.0)
        self.assertEqual(self.writer.saves, [])
