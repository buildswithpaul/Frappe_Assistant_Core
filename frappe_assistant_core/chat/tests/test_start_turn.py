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

"""The Raven bot starts turns through the same service as the HTTP endpoint, so gates cannot drift."""

from concurrent.futures import Future
from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api.chat import messages
from frappe_assistant_core.tests.base_test import BaseAssistantTest

GATE = "frappe_assistant_core.chat.api.settings.can_use_faco"


class TestStartTurn(BaseAssistantTest):
    def test_start_turn_submits_the_relay_with_the_callers_client_type_and_returns_its_future(self):
        done = Future()
        with (
            patch(GATE, return_value={"can_use": True}),
            patch.object(messages._relay_pool, "submit", return_value=done) as submit,
        ):
            future = messages.start_turn("s-start-turn", "hi", client_type="raven")
        self.assertIs(future, done)
        # submit(fn, session_id, prompt, message, context, msg, user, site, model, att, addendum, client_type)
        self.assertEqual(submit.call_args.args[11], "raven")

    def test_start_turn_refuses_like_the_endpoint_when_faco_is_unavailable(self):
        with patch(GATE, return_value={"can_use": False, "reason": "No seat"}):
            with self.assertRaises(frappe.ValidationError):
                messages.start_turn("s-start-turn", "hi")
