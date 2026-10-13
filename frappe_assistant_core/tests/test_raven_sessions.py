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

"""Each Raven conversation is a FAC Chat session of its own, owned by the asker."""

from unittest.mock import patch

from frappe_assistant_core.integrations.raven import sessions
from frappe_assistant_core.integrations.raven.sessions import session_id_for, session_url
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestRavenSessions(BaseAssistantTest):
    def test_the_same_place_and_person_continue_one_conversation(self):
        self.assertEqual(session_id_for("dm-1", "a@x.com"), session_id_for("dm-1", "a@x.com"))

    def test_two_people_in_one_thread_never_share_a_conversation(self):
        self.assertNotEqual(session_id_for("thread-1", "a@x.com"), session_id_for("thread-1", "b@x.com"))

    def test_the_link_opens_the_session_in_fac_chat(self):
        self.assertTrue(session_url("abc").endswith("/copilot/chat/abc"))

    def test_a_session_id_cannot_be_computed_from_public_values(self):
        # A session with no saved messages passes the owner check, so a guessable id would let
        # someone claim another person's Raven conversation first. The id is keyed by a site secret.
        with patch.object(sessions, "_secret", autospec=True, return_value="site-a"):
            first = session_id_for("dm-1", "a@x.com")
        with patch.object(sessions, "_secret", autospec=True, return_value="site-b"):
            second = session_id_for("dm-1", "a@x.com")
        self.assertNotEqual(first, second)
