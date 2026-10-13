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

"""Raven has no Stop button: deleting FAC Bot's streaming reply stops the turn. A sweep finishes
replies whose worker died, so none is left streaming forever."""

import time
import unittest

import frappe

from frappe_assistant_core.chat.api.chat import cancel
from frappe_assistant_core.integrations.raven import bot, formatting, triggers
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestStopAndSweep(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "raven" not in frappe.get_installed_apps():
            raise unittest.SkipTest("Raven is not installed")

    def setUp(self):
        super().setUp()
        from frappe_assistant_core.integrations.raven.turn import REPLIES_KEY

        self.key = REPLIES_KEY
        self.addCleanup(bot.clear_state_cache)
        self.addCleanup(cancel.clear, "s-stop")
        bot.ensure_bot()
        self.raven_bot = frappe.get_doc("Raven Bot", bot.BOT_NAME)
        user = self.make_throwaway_user("raven-stop", roles=("Raven User",))
        self.dm = self.raven_bot.create_direct_message_channel(user)

    def _reply(self, updated: float) -> str:
        # Production: turn.run posts the reply and records it while the relay streams into it.
        reply = self.raven_bot.send_message(self.dm, "<p>Partial answer</p>")
        frappe.cache.hset(self.key, reply, {"session_id": "s-stop", "updated": updated})
        self.addCleanup(frappe.cache.hdel, self.key, reply)
        return reply

    def test_deleting_a_streaming_reply_stops_the_turn(self):
        reply = self._reply(time.time())
        frappe.delete_doc("Raven Message", reply, ignore_permissions=True)
        self.assertTrue(cancel.is_cancelled("s-stop"))

    def test_deleting_an_ordinary_message_costs_no_query(self):
        ordinary = frappe._dict(name="m-x", is_bot_message=0, bot=None)
        with self.assertQueryCount(0):
            triggers.on_trash(ordinary)
        self.assertFalse(cancel.is_cancelled("s-stop"))

    def test_a_reply_quiet_for_ten_minutes_is_finished_as_interrupted(self):
        from frappe_assistant_core.integrations.raven.sweep import finish_interrupted_replies

        stale, fresh = self._reply(time.time() - 700), self._reply(time.time())
        self.assertEqual(finish_interrupted_replies(), 1)
        self.assertIn(str(formatting.INTERRUPTED), frappe.db.get_value("Raven Message", stale, "text"))
        self.assertNotIn(str(formatting.INTERRUPTED), frappe.db.get_value("Raven Message", fresh, "text"))
        self.assertIsNone(frappe.cache.hget(self.key, stale))

    def test_writing_to_a_reply_someone_deleted_is_a_quiet_no_op(self):
        # Live: after a Stop, the relay's last event tried to edit the deleted reply and logged an error.
        from frappe_assistant_core.integrations.raven.sink import RavenReplyWriter

        reply = self._reply(time.time())
        frappe.delete_doc("Raven Message", reply, ignore_permissions=True)
        RavenReplyWriter(reply, self.dm, bot.BOT_NAME).update("<p>late</p>")
        self.assertFalse(frappe.db.exists("Raven Message", reply))

    def test_the_status_strip_is_published_at_once_not_after_a_commit(self):
        # From the relay thread, an after-commit event waits for the next text save — or never shows.
        from unittest.mock import patch

        from frappe_assistant_core.integrations.raven.sink import RavenReplyWriter

        with patch("frappe.publish_realtime", autospec=True) as publish:
            RavenReplyWriter("r1", self.dm, bot.BOT_NAME).status("FAC Bot is reading HD Ticket 1…")
        self.assertFalse(publish.call_args.kwargs["after_commit"])
