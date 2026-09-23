"""The FAC proxy. This is the hop where "which member" is established.

AR authenticates the workspace, not the member, so a payload-supplied user_id
would be a claim. Every method here derives it from frappe.session.user.
"""

import inspect
import unittest
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.chat.api import routing_preferences as api


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


class TestIdentityIsDerivedNotAccepted(unittest.TestCase):
    def test_no_endpoint_takes_a_user_id_from_the_caller(self):
        # The single most important property of this module.
        for name in (
            "list_routing_preferences",
            "create_routing_preference",
            "set_routing_preference_status",
            "set_routing_preference_mode",
            "delete_routing_preference",
            "forecast_routing_preference",
        ):
            params = inspect.signature(_unwrap(getattr(api, name))).parameters
            self.assertNotIn("user_id", params, name)

    def test_every_endpoint_derives_it_from_the_session(self):
        for name in (
            "list_routing_preferences",
            "create_routing_preference",
            "set_routing_preference_status",
            "set_routing_preference_mode",
            "delete_routing_preference",
            "forecast_routing_preference",
        ):
            src = inspect.getsource(getattr(api, name))
            self.assertIn("_ar_user_id(frappe.session.user)", src, name)

    def test_writes_declare_post(self):
        # Frappe rolls back safe methods, so a missing declaration is a write
        # that is discarded while still answering success.
        src = inspect.getsource(api)
        for name in (
            "create_routing_preference",
            "set_routing_preference_status",
            "set_routing_preference_mode",
            "delete_routing_preference",
            "forecast_routing_preference",
        ):
            at = src.index(f"def {name}(")
            self.assertIn('methods=["POST"]', src[max(0, at - 200) : at], name)


class TestValidation(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        patcher = patch.object(api, "_client", return_value=self.client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_personal_rule_is_refused_with_a_reason(self):
        with self.assertRaises(frappe.ValidationError):
            _unwrap(api.create_routing_preference)(
                match_kind="keyword", match_value="invoice", target_tier="Economy", scope="User"
            )

    def test_an_unknown_match_kind_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            _unwrap(api.create_routing_preference)(
                match_kind="app", match_value="erpnext", target_tier="Economy"
            )

    def test_a_blank_match_value_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            _unwrap(api.create_routing_preference)(
                match_kind="keyword", match_value="   ", target_tier="Economy"
            )

    def test_a_missing_tier_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            _unwrap(api.create_routing_preference)(
                match_kind="keyword", match_value="invoice", target_tier=None
            )

    def test_a_valid_create_reaches_the_client_trimmed(self):
        _unwrap(api.create_routing_preference)(
            match_kind="keyword", match_value="  invoice  ", target_tier="Economy"
        )
        kwargs = self.client.create_routing_preference.call_args.kwargs
        self.assertEqual(kwargs["match_value"], "invoice")
        self.assertEqual(kwargs["scope"], "Tenant")
        self.assertEqual(kwargs["origin"], "settings")

    def test_an_unknown_status_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            _unwrap(api.set_routing_preference_status)(preference_id="P1", status="banana")

    def test_a_missing_preference_id_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            _unwrap(api.delete_routing_preference)(preference_id=None)

    def test_an_unknown_rule_mode_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            _unwrap(api.set_routing_preference_mode)(preference_id="P1", rule_mode="banana")

    def test_off_is_not_a_rule_mode_a_workspace_can_set(self):
        # `off` is the platform kill switch, not a state a workspace can put
        # its own rule into. Passing it through would look like it worked.
        with self.assertRaises(frappe.ValidationError):
            _unwrap(api.set_routing_preference_mode)(preference_id="P1", rule_mode="off")

    def test_a_mode_change_without_a_rule_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            _unwrap(api.set_routing_preference_mode)(preference_id=None, rule_mode="on")

    def test_a_valid_mode_change_reaches_the_client(self):
        _unwrap(api.set_routing_preference_mode)(preference_id="P1", rule_mode="on")
        kwargs = self.client.set_routing_preference_mode.call_args.kwargs
        self.assertEqual(kwargs["preference_id"], "P1")
        self.assertEqual(kwargs["rule_mode"], "on")


class TestUnregisteredSite(unittest.TestCase):
    def test_the_listing_degrades_instead_of_erroring(self):
        # A settings page that cannot load is worse than one that says there
        # is nothing to show.
        with patch("frappe_assistant_core.chat.fac_cloud_client." "get_fac_cloud_client", return_value=None):
            out = _unwrap(api.list_routing_preferences)()
        self.assertEqual(out["mine"], [])
        self.assertEqual(out["team"], [])
        self.assertFalse(out["can_manage_team"])


if __name__ == "__main__":
    unittest.main()
