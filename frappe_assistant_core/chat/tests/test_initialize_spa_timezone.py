# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""``initialize_spa`` names the zone of every naive server datetime (spec §8.6).

Frappe stores session ``last_activity`` and message ``timestamp`` naive, in the
site's system timezone. A client in another zone cannot place them without
knowing that zone, so every boot payload carries ``system_timezone``: the early
exit for a user who cannot chat yet as well as the full payload.
"""

import ast
import inspect
import textwrap
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest

GATE_READY = {"can_use": True, "status": "ready", "show_widget": True, "is_admin": False, "preferences": {}}
GATE_NO_ROLE = {"can_use": False, "status": "no_role", "show_widget": False, "is_admin": False}
AUTH_READY = {
    "user_exists": True,
    "user_status": "Active",
    "has_mcp_servers": True,
    "active_server_count": 1,
    "servers_with_expired_tokens": [],
    "ready_for_streaming": True,
}


class TestInitializeSpaTimezone(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user(self.make_throwaway_user("tz-member"))

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _boot(self, gate: dict) -> dict:
        from frappe_assistant_core.chat.api import init as init_mod

        client = MagicMock()
        client.get_user_auth_status.return_value = AUTH_READY
        client.get_terms_status.return_value = None
        with ExitStack() as stack:
            stack.enter_context(
                patch("frappe_assistant_core.chat.api.settings.access.can_use_faco", return_value=gate)
            )
            stack.enter_context(
                patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client)
            )
            stack.enter_context(
                patch.object(init_mod, "_get_cached_or_fetch_capabilities", return_value=None)
            )
            # Keep the quota read off the shared cache: a mocked AR client would
            # mark the site's quota seed as failed for everyone on the dev site.
            stack.enter_context(patch.object(init_mod, "_build_quota", return_value={}))
            return init_mod.initialize_spa()

    def test_the_early_exit_names_the_zone(self):
        payload = self._boot(GATE_NO_ROLE)

        self.assertIsNone(payload["user_auth"])
        self.assertEqual(payload["system_timezone"], frappe.utils.get_system_timezone())

    def test_the_full_payload_names_the_zone(self):
        payload = self._boot(GATE_READY)

        self.assertIsNotNone(payload["user_auth"])
        self.assertTrue(payload["system_timezone"])
        self.assertEqual(payload["system_timezone"], frappe.utils.get_system_timezone())

    def test_every_return_path_carries_the_key(self):
        from frappe_assistant_core.chat.api import init as init_mod

        tree = ast.parse(textwrap.dedent(inspect.getsource(init_mod.initialize_spa)))
        returns = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict)
        ]
        self.assertGreaterEqual(len(returns), 2, "expected the early exit and the full payload")
        for node in returns:
            keys = [key.value for key in node.value.keys if isinstance(key, ast.Constant)]
            self.assertIn("system_timezone", keys, f"return at line {node.lineno} drops the key")
