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

"""
Request-level tests for asking the user before a destructive tools/call runs (spec §7.3).

Every request is built from ``fixtures/mcp_mrtr_retry.json``, a retry captured from a real MCP
client, so the shape of ``inputResponses`` / ``requestState`` is the one clients actually send.
"""

import base64
import copy
import json
import os

import frappe

from frappe_assistant_core.api.fac_endpoint import _build_tool_registry, mcp
from frappe_assistant_core.mcp import confirmation
from frappe_assistant_core.mcp.protocol import META_SERVER_INFO
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.tests.test_fac_cloud_only_tools import _make_oauth_client, _mint
from frappe_assistant_core.tests.test_mcp_modern_era import _json, _send
from frappe_assistant_core.utils.mcp_caller import FAC_CLOUD_OAUTH_CLIENT_ID

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "mcp_mrtr_retry.json")
NOT_CONFIRMED = "The user did not confirm, so nothing was changed."
ACCEPT = {"confirm": {"action": "accept", "content": {"confirm": True}}}
DECLINE = {"confirm": {"action": "decline"}}

with open(FIXTURE_PATH) as _handle:
    CAPTURED = json.load(_handle)


def _first_call(arguments: dict, *, elicitation: bool = True) -> tuple:
    """The captured request without the retry fields: what the client sends before it is asked."""
    body = copy.deepcopy(CAPTURED["body"])
    params = body["params"]
    params.pop("inputResponses")
    params.pop("requestState")
    params["arguments"] = arguments
    if not elicitation:
        params["_meta"]["io.modelcontextprotocol/clientCapabilities"] = {}
    return body, dict(CAPTURED["headers"])


def _retry(arguments: dict, state, input_responses=None) -> tuple:
    body = copy.deepcopy(CAPTURED["body"])
    body["id"] = 0  # real clients number from 0; a falsy id must still be answered
    params = body["params"]
    params["arguments"] = arguments
    params["requestState"] = state
    if input_responses is None:
        params.pop("inputResponses")
    else:
        params["inputResponses"] = input_responses
    return body, dict(CAPTURED["headers"])


def _nonce(state: str):
    try:
        segment = state.split(".")[0]
        return json.loads(base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4)))["nonce"]
    except Exception:
        return None


class TestMcpConfirmationFlow(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.registry = _build_tool_registry()
        self.assertIn("delete_document", self.registry)
        self._states = []

    def tearDown(self):
        # Nonce markers live in Redis, which the test transaction rollback does not touch.
        for state in self._states:
            nonce = _nonce(state)
            if nonce:
                frappe.cache.delete_value(confirmation._nonce_key(nonce))
        super().tearDown()

    def _todo(self, name: str | None = None) -> str:
        doc = frappe.get_doc({"doctype": "ToDo", "description": "confirmation flow test"})
        return doc.insert(ignore_permissions=True, set_name=name).name

    def _call(self, body: dict, headers: dict):
        response = _send(body, headers, self.registry)
        payload = _json(response)
        state = payload.get("result", {}).get("requestState")
        if state:
            self._states.append(state)
        return response, payload

    def _ask(self, arguments: dict) -> str:
        _response, payload = self._call(*_first_call(arguments))
        self.assertEqual(payload["result"]["resultType"], "input_required")
        return payload["result"]["requestState"]

    def test_delete_asks_first(self):
        name = self._todo()
        _response, payload = self._call(*_first_call({"doctype": "ToDo", "name": name}))

        result = payload["result"]
        self.assertEqual(result["resultType"], "input_required")
        request = result["inputRequests"]["confirm"]
        self.assertEqual(request["method"], "elicitation/create")
        self.assertEqual(request["params"]["mode"], "form")
        self.assertIn(name, request["params"]["message"])
        self.assertEqual(request["params"]["requestedSchema"]["properties"]["confirm"]["title"], "Delete")
        self.assertTrue(frappe.db.exists("ToDo", name))

    def test_accept_deletes(self):
        name = self._todo()
        arguments = {"doctype": "ToDo", "name": name}
        state = self._ask(arguments)

        response, payload = self._call(*_retry(arguments, state, ACCEPT))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["id"], 0)
        self.assertEqual(payload["result"]["resultType"], "complete")
        self.assertFalse(payload["result"]["isError"])
        self.assertFalse(frappe.db.exists("ToDo", name))

    def test_decline_keeps(self):
        name = self._todo()
        arguments = {"doctype": "ToDo", "name": name}
        state = self._ask(arguments)

        _response, payload = self._call(*_retry(arguments, state, DECLINE))

        self.assertTrue(payload["result"]["isError"])
        self.assertEqual(payload["result"]["content"][0]["text"], NOT_CONFIRMED)
        self.assertTrue(frappe.db.exists("ToDo", name))

    def test_confirm_false_keeps(self):
        name = self._todo()
        arguments = {"doctype": "ToDo", "name": name}
        state = self._ask(arguments)
        unticked = {"confirm": {"action": "accept", "content": {"confirm": False}}}

        _response, payload = self._call(*_retry(arguments, state, unticked))

        self.assertEqual(payload["result"]["content"][0]["text"], NOT_CONFIRMED)
        self.assertTrue(frappe.db.exists("ToDo", name))

    def test_declined_state_cannot_be_accepted_later(self):
        name = self._todo()
        arguments = {"doctype": "ToDo", "name": name}
        state = self._ask(arguments)
        self._call(*_retry(arguments, state, DECLINE))

        response, payload = self._call(*_retry(arguments, state, ACCEPT))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(payload["error"]["code"], -32602)
        self.assertTrue(frappe.db.exists("ToDo", name))

    def test_replayed_consent_refused(self):
        name = self._todo()
        arguments = {"doctype": "ToDo", "name": name}
        retry = _retry(arguments, self._ask(arguments), ACCEPT)
        self._call(*retry)
        self.assertFalse(frappe.db.exists("ToDo", name))
        # A record matching the signed arguments again, as when a name is reused after a delete:
        # a replayed consent must not reach it.
        self._todo(name)

        response, payload = self._call(*retry)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(payload["error"]["code"], -32602)
        self.assertTrue(frappe.db.exists("ToDo", name))

    def test_changed_arguments_refused(self):
        asked, other = self._todo(), self._todo()
        state = self._ask({"doctype": "ToDo", "name": asked})

        response, payload = self._call(*_retry({"doctype": "ToDo", "name": other}, state, ACCEPT))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(payload["error"]["code"], -32602)
        self.assertTrue(frappe.db.exists("ToDo", other))
        self.assertTrue(frappe.db.exists("ToDo", asked))

    def test_forged_state_refused(self):
        name = self._todo()
        arguments = {"doctype": "ToDo", "name": name}

        response, payload = self._call(*_retry(arguments, "not.a-token", ACCEPT))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(payload["error"]["code"], -32602)
        self.assertTrue(frappe.db.exists("ToDo", name))

    def test_missing_answer_asks_again_with_a_fresh_state(self):
        name = self._todo()
        arguments = {"doctype": "ToDo", "name": name}
        state = self._ask(arguments)

        _response, payload = self._call(*_retry(arguments, state, None))

        self.assertEqual(payload["result"]["resultType"], "input_required")
        self.assertNotEqual(payload["result"]["requestState"], state)
        self.assertTrue(frappe.db.exists("ToDo", name))
        # The old state was only checked, not used up, so its answer still counts.
        self._call(*_retry(arguments, state, ACCEPT))
        self.assertFalse(frappe.db.exists("ToDo", name))

    def test_missing_answer_with_a_forged_state_is_refused(self):
        name = self._todo()

        response, payload = self._call(*_retry({"doctype": "ToDo", "name": name}, "forged", None))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(payload["error"]["code"], -32602)

    def test_no_elicitation_runs_directly(self):
        name = self._todo()

        _response, payload = self._call(*_first_call({"doctype": "ToDo", "name": name}, elicitation=False))

        self.assertEqual(payload["result"]["resultType"], "complete")
        self.assertFalse(payload["result"]["isError"])
        self.assertFalse(frappe.db.exists("ToDo", name))

    def test_fac_cloud_unchanged(self):
        """FAC Chat shows its own approval card, so FAC Cloud must not be asked a second time."""
        # FAC Cloud's client exists once a site has registered with it; reuse it when it does.
        if not frappe.db.exists("OAuth Client", FAC_CLOUD_OAUTH_CLIENT_ID):
            _make_oauth_client(FAC_CLOUD_OAUTH_CLIENT_ID)
        token = _mint(frappe.session.user, FAC_CLOUD_OAUTH_CLIENT_ID)
        name = self._todo()
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "delete_document", "arguments": {"doctype": "ToDo", "name": name}},
        }

        _response, payload = self._call(
            body, {"MCP-Protocol-Version": "2025-06-18", "Authorization": f"Bearer {token}"}
        )

        self.assertNotIn("resultType", payload["result"])
        self.assertFalse(payload["result"]["isError"])
        self.assertFalse(frappe.db.exists("ToDo", name))

    def test_fac_cloud_declaring_elicitation_is_not_asked(self):
        """Even on the modern era with form elicitation declared, FAC Chat is never asked twice."""
        if not frappe.db.exists("OAuth Client", FAC_CLOUD_OAUTH_CLIENT_ID):
            _make_oauth_client(FAC_CLOUD_OAUTH_CLIENT_ID)
        token = _mint(frappe.session.user, FAC_CLOUD_OAUTH_CLIENT_ID)
        name = self._todo()
        body, headers = _first_call({"doctype": "ToDo", "name": name})
        headers["Authorization"] = f"Bearer {token}"

        _response, payload = self._call(body, headers)

        self.assertEqual(payload["result"]["resultType"], "complete")
        self.assertFalse(payload["result"]["isError"])
        self.assertFalse(frappe.db.exists("ToDo", name))

    def test_handshake_ignores_retry_fields(self):
        name = self._todo()
        params = {
            "name": "delete_document",
            "arguments": {"doctype": "ToDo", "name": name},
            "requestState": "forged",
            "inputResponses": DECLINE,
        }
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": params}

        _response, payload = self._call(body, {"MCP-Protocol-Version": "2025-06-18"})

        self.assertFalse(payload["result"]["isError"])
        self.assertFalse(frappe.db.exists("ToDo", name))

    def test_read_tool_never_asks(self):
        body, headers = _first_call({"doctype": "Role", "name": "System Manager"})
        body["params"]["name"] = headers["mcp-name"] = "get_document"

        _response, payload = self._call(body, headers)

        self.assertEqual(payload["result"]["resultType"], "complete")

    def test_input_required_decorated(self):
        name = self._todo()
        _response, payload = self._call(*_first_call({"doctype": "ToDo", "name": name}))

        self.assertEqual(payload["result"]["_meta"][META_SERVER_INFO]["name"], mcp.name)
        self.assertNotIn("cacheScope", payload["result"])
