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

"""A Raven turn watches the same relay events the widget receives, without forking the relay."""

from unittest.mock import patch

from frappe_assistant_core.chat.api.chat import turn_observers
from frappe_assistant_core.chat.api.chat.helpers import _emit_socket_event
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestTurnObservers(BaseAssistantTest):
    def tearDown(self):
        turn_observers.unregister("s-obs")
        super().tearDown()

    def test_an_observer_sees_every_event_of_its_session_and_no_other(self):
        seen = []
        turn_observers.register("s-obs", seen.append)
        with patch("frappe.publish_realtime"):
            _emit_socket_event("s-obs", {"event": "stream_chunk", "chunk": "a"})
            _emit_socket_event("s-other", {"event": "stream_chunk", "chunk": "b"})
        self.assertEqual([e["chunk"] for e in seen], ["a"])

    def test_a_failing_observer_never_breaks_the_relay(self):
        def boom(_data):
            raise RuntimeError("sink down")

        turn_observers.register("s-obs", boom)
        with patch("frappe.publish_realtime") as publish, patch("frappe.log_error") as log:
            _emit_socket_event("s-obs", {"event": "stream_chunk", "chunk": "a"})
        publish.assert_called_once()
        log.assert_called_once()

    def test_unregistered_sessions_cost_nothing(self):
        with patch("frappe.publish_realtime"):
            _emit_socket_event("s-none", {"event": "stream_chunk"})
