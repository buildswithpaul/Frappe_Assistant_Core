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

"""Tests for the signed, single-use consent token behind MCP tool confirmations."""

import base64
import json
import time
from pathlib import Path
from unittest.mock import patch

import frappe

from frappe_assistant_core.mcp import confirmation
from frappe_assistant_core.mcp.confirmation import (
    INPUT_KEY,
    STATE_TTL_SECONDS,
    ConsentRefused,
    accepted,
    consume_state,
    input_required,
    issue_state,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest

RETRY_FIXTURE = Path(__file__).parent / "fixtures" / "mcp_mrtr_retry.json"

USER = "Administrator"
TOOL = "delete_document"
ARGS = {"doctype": "ToDo", "name": "abc123"}


def _flip(text: str, index: int) -> str:
    return text[:index] + ("A" if text[index] != "A" else "B") + text[index + 1 :]


class TestMcpConfirmation(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self._issued = []

    def tearDown(self):
        # Nonce markers live in Redis, which the test transaction rollback does not touch.
        for state in self._issued:
            nonce = self._nonce(state)
            if nonce:
                frappe.cache.delete_value(confirmation._nonce_key(nonce))
        super().tearDown()

    def _issue(self, user=USER, tool=TOOL, arguments=None):
        state = issue_state(user, tool, ARGS if arguments is None else arguments)
        self._issued.append(state)
        return state

    @staticmethod
    def _nonce(state):
        try:
            segment = state.split(".")[0]
            payload = base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
            return json.loads(payload)["nonce"]
        except Exception:
            return None

    def test_constants(self):
        self.assertEqual(STATE_TTL_SECONDS, 600)
        self.assertEqual(INPUT_KEY, "confirm")

    def test_round_trip(self):
        consume_state(self._issue(), USER, TOOL, ARGS)

    def test_changed_arguments_refused(self):
        state = self._issue()
        with self.assertRaises(ConsentRefused):
            consume_state(state, USER, TOOL, {"doctype": "ToDo", "name": "other456"})

    def test_other_user_refused(self):
        state = self._issue()
        with self.assertRaises(ConsentRefused):
            consume_state(state, "Guest", TOOL, ARGS)

    def test_other_tool_refused(self):
        state = self._issue()
        with self.assertRaises(ConsentRefused):
            consume_state(state, USER, "document_action", ARGS)

    def test_tampered_refused(self):
        state = self._issue()
        payload, mac = state.split(".")
        for tampered in (
            _flip(payload, len(payload) // 2) + "." + mac,
            payload + "." + _flip(mac, len(mac) // 2),
        ):
            with self.assertRaises(ConsentRefused):
                consume_state(tampered, USER, TOOL, ARGS)

    def test_tampered_refusal_leaves_state_usable(self):
        state = self._issue()
        payload, mac = state.split(".")
        with self.assertRaises(ConsentRefused):
            consume_state(payload + "." + _flip(mac, 3), USER, TOOL, ARGS)
        consume_state(state, USER, TOOL, ARGS)

    def test_forged_payload_with_reused_mac_refused(self):
        state = self._issue()
        _, mac = state.split(".")
        forged = {
            "user": USER,
            "tool": TOOL,
            "args_sha256": "0" * 64,
            "exp": 9999999999,
            "nonce": "x",
        }
        segment = base64.urlsafe_b64encode(json.dumps(forged).encode()).rstrip(b"=").decode()
        with self.assertRaises(ConsentRefused):
            consume_state(segment + "." + mac, USER, TOOL, ARGS)

    def test_expired_refused(self):
        # A user who waits more than STATE_TTL_SECONDS before answering the prompt.
        eleven_minutes_ago = time.time() - 11 * 60
        with patch.object(confirmation.time, "time", return_value=eleven_minutes_ago):
            state = self._issue()
        with self.assertRaises(ConsentRefused):
            consume_state(state, USER, TOOL, ARGS)

    def test_not_yet_expired_accepted(self):
        nine_minutes_ago = time.time() - 9 * 60
        with patch.object(confirmation.time, "time", return_value=nine_minutes_ago):
            state = self._issue()
        consume_state(state, USER, TOOL, ARGS)

    def test_single_use(self):
        state = self._issue()
        consume_state(state, USER, TOOL, ARGS)
        with self.assertRaises(ConsentRefused):
            consume_state(state, USER, TOOL, ARGS)

    def test_each_issue_is_independent(self):
        first, second = self._issue(), self._issue()
        self.assertNotEqual(first, second)
        consume_state(first, USER, TOOL, ARGS)
        consume_state(second, USER, TOOL, ARGS)

    def test_argument_key_order_irrelevant(self):
        state = self._issue(arguments={"doctype": "ToDo", "name": "abc123"})
        consume_state(state, USER, TOOL, {"name": "abc123", "doctype": "ToDo"})

    def test_malformed_state_refused(self):
        for bad in (None, 42, {}, "", "abc", "a.b.c", "!!!.???", "e30.e30", "bm90anNvbg.AAAA"):
            with self.subTest(state=bad), self.assertRaises(ConsentRefused):
                consume_state(bad, USER, TOOL, ARGS)

    def test_signed_payload_with_wrong_types_refused(self):
        # Only reachable by someone holding the key; consume_state must still refuse cleanly.
        for payload in (
            [],
            {"user": USER},
            {"user": USER, "tool": TOOL, "args_sha256": "x", "exp": "soon", "nonce": "n"},
            {"user": USER, "tool": TOOL, "args_sha256": "x", "exp": 9999999999, "nonce": 7},
        ):
            with self.subTest(payload=payload), self.assertRaises(ConsentRefused):
                consume_state(confirmation._sign(payload), USER, TOOL, ARGS)

    def test_accepted(self):
        recorded = json.loads(RETRY_FIXTURE.read_text())["body"]["params"]["inputResponses"]
        self.assertIs(accepted(recorded), True)
        self.assertIs(accepted({"confirm": {"action": "accept", "content": {"confirm": True}}}), True)
        for responses in (
            {"confirm": {"action": "decline"}},
            {"confirm": {"action": "cancel"}},
            {"confirm": {"action": "accept", "content": {"confirm": False}}},
            {"confirm": {"action": "accept", "content": {"confirm": "true"}}},
            {"confirm": {"action": "accept", "content": {}}},
            {"confirm": {"action": "accept"}},
            {"confirm": {"action": "accept", "content": None}},
            {"confirm": "accept"},
            {"other": {"action": "accept", "content": {"confirm": True}}},
            {},
            None,
            [],
            "accept",
        ):
            with self.subTest(responses=responses):
                self.assertIs(accepted(responses), False)

    def test_input_required_shape(self):
        expected = json.loads(RETRY_FIXTURE.read_text())["first_call_result"]
        result = input_required(
            "Delete ToDo abc123? This can't be undone.", "Delete", "FAC_REQUEST_STATE_PLACEHOLDER"
        )
        self.assertEqual(result, expected)
