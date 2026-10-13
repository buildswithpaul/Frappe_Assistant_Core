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

"""Every Raven message passes FAC Bot's trigger, so deciding must be cheap and exact."""

import unittest
from unittest.mock import patch

import frappe

from frappe_assistant_core.integrations.raven import bot, triggers
from frappe_assistant_core.tests.base_test import BaseAssistantTest

TURN_JOB = "frappe_assistant_core.integrations.raven.turn.run"


def message(**fields):
    """A Raven Message as the hook sees it, with only the fields the trigger reads."""
    base = {
        "name": "m1",
        "is_bot_message": 0,
        "message_type": "Text",
        "mentions": [],
        "channel_id": "c1",
        "owner": "a@x.com",
        "message_batch_id": None,
        "file": None,
        "flags": frappe._dict(),
    }
    return frappe._dict({**base, **fields})


def mention_of_bot():
    return [frappe._dict(user=bot.BOT_NAME)]


class TestAddressed(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.state = self.enterContext(patch.object(bot, "state", autospec=True, return_value="on"))
        self.channel = frappe._dict(is_direct_message=0, dm_user_1=None, dm_user_2=None)
        self.enterContext(patch.object(triggers.frappe, "get_cached_doc", return_value=self.channel))

    def test_a_mention_of_fac_bot_addresses_it(self):
        self.assertEqual(triggers.addressed(message(mentions=mention_of_bot())), "mention")

    def test_a_dm_with_fac_bot_addresses_it(self):
        self.channel.update(is_direct_message=1, dm_user_1=bot.BOT_NAME, dm_user_2="a@x.com")
        self.assertEqual(triggers.addressed(message()), "dm")

    def test_a_files_only_dm_addresses_it(self):
        self.channel.update(is_direct_message=1, dm_user_1=bot.BOT_NAME, dm_user_2="a@x.com")
        self.assertEqual(triggers.addressed(message(message_type="File", file="/private/files/a.pdf")), "dm")

    def test_an_ordinary_channel_message_does_not_address_it(self):
        self.assertIsNone(triggers.addressed(message(mentions=[frappe._dict(user="b@x.com")])))

    def test_bot_messages_never_address_it(self):
        self.assertIsNone(triggers.addressed(message(is_bot_message=1, mentions=mention_of_bot())))

    def test_polls_and_system_messages_never_address_it(self):
        for kind in ("Poll", "System"):
            self.assertIsNone(triggers.addressed(message(message_type=kind, mentions=mention_of_bot())))

    def test_a_message_during_migrate_never_addresses_it(self):
        frappe.flags.in_migrate = True
        self.addCleanup(frappe.flags.pop, "in_migrate", None)
        self.assertIsNone(triggers.addressed(message(mentions=mention_of_bot())))

    def test_a_site_without_fac_bot_skips_everything(self):
        self.state.return_value = "absent"
        self.assertIsNone(triggers.addressed(message(mentions=mention_of_bot())))

    def test_a_switched_off_bot_is_still_addressed_so_it_can_say_so(self):
        self.state.return_value = "off"
        self.assertEqual(triggers.addressed(message(mentions=mention_of_bot())), "mention")


class TestTriggerEnqueue(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.enterContext(patch.object(bot, "state", autospec=True, return_value="on"))
        self.enqueue = self.enterContext(patch.object(triggers.frappe, "enqueue"))

    def test_an_addressed_message_is_enqueued_once_after_commit_by_name(self):
        triggers.on_insert(message(mentions=mention_of_bot(), message_batch_id="b1"))
        args, kwargs = self.enqueue.call_args
        self.assertEqual(args[0], TURN_JOB)
        self.assertEqual((kwargs["message_id"], kwargs["kind"]), ("m1", "mention"))
        self.assertTrue(kwargs["enqueue_after_commit"])
        self.assertTrue(kwargs["deduplicate"])
        self.assertEqual(kwargs["job_id"], "fac-raven:b1")

    def test_a_flood_of_messages_is_capped_per_person(self):
        # A scripted sender must not keep the worker busy: the HTTP send endpoint caps at 30/min.
        owner = f"flood-{frappe.generate_hash(length=6)}@x.com"
        self.addCleanup(frappe.cache.delete, frappe.cache.make_key(f"fac_raven_rate:{owner}"))
        for i in range(triggers.TURNS_PER_MINUTE + 3):
            triggers.on_insert(message(name=f"m{i}", owner=owner, mentions=mention_of_bot()))
        self.assertEqual(self.enqueue.call_count, triggers.TURNS_PER_MINUTE)

    def test_editing_a_message_never_starts_a_second_turn(self):
        msg = message(mentions=mention_of_bot())
        msg.is_new = lambda: False
        msg.has_value_changed = lambda field: False
        triggers.on_update(msg)
        self.enqueue.assert_not_called()

    def test_a_file_set_after_insert_is_answered(self):
        msg = message(message_type="File", file="/private/files/a.pdf", mentions=mention_of_bot())
        msg.is_new = lambda: False
        msg.has_value_changed = lambda field: field == "file"
        triggers.on_update(msg)
        self.enqueue.assert_called_once()


class TestTriggerCost(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "raven" not in frappe.get_installed_apps():
            raise unittest.SkipTest("Raven is not installed")

    def test_an_ordinary_channel_message_costs_no_query(self):
        bot.state()  # warm, as every message after the first finds it
        channel = frappe._dict(is_direct_message=0, dm_user_1=None, dm_user_2=None)
        with patch.object(triggers.frappe, "get_cached_doc", return_value=channel):
            with self.assertQueryCount(0):
                triggers.on_insert(message(mentions=[frappe._dict(user="b@x.com")]))
