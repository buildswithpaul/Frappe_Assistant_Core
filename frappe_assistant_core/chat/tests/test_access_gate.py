# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Tests for can_use_faco membership-based access gate.

Regression coverage for the bug where FACO access was gated on the user's
Frappe role instead of FACO membership: an active, billed member whose ERP
role changed away from System Manager / Assistant User was instantly locked
out even though their AR Tenant User seat was intact.
"""

from contextlib import contextmanager
from unittest.mock import patch

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest


class _SettingsStub:
    """Minimal stand-in for the FAC Chat Settings single doc.

    Only the fields can_use_faco reads on the way to the membership check
    are populated, so the registration gate passes without depending on the
    test site's real FAC Chat Settings state.
    """

    registration_status = "Registered"
    tenant_id = "t"
    tenant_secret = "s"
    fac_cloud_url = "https://x"


class TestAccessGate(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def _make_user(self, email, roles=None):
        if not frappe.db.exists("User", email):
            u = frappe.get_doc(
                {
                    "doctype": "User",
                    "email": email,
                    "first_name": "Gate",
                    "enabled": 1,
                    "send_welcome_email": 0,
                }
            )
            u.insert(ignore_permissions=True)
        u = frappe.get_doc("User", email)
        # Strip System Manager etc. so the Frappe role can't accidentally grant
        # (or deny) access — these tests isolate the membership signal.
        u.set("roles", [])
        for r in roles or []:
            u.append("roles", {"role": r})
        u.save(ignore_permissions=True)
        return email

    @contextmanager
    def _reach_membership_check(self, is_member: bool, is_owner: bool = False):
        """Patch everything between the master gate and the membership check.

        - is_chat_enabled -> True (skip the master FAC Chat gate)
        - frappe.get_single("FAC Chat Settings") -> Registered stub
          (skip the registration / tenant-credential gates)
        - _is_faco_member -> the desired membership signal
        - _is_tenant_owner -> the desired ownership signal (default False)
        - get_quota_snapshot / preferences -> harmless stubs so the success
          path completes without touching cloud state.
        """
        real_get_single = frappe.get_single

        def fake_get_single(doctype):
            if doctype == "FAC Chat Settings":
                return _SettingsStub()
            return real_get_single(doctype)

        from frappe_assistant_core.chat.doctype.fac_chat_user_preferences.fac_chat_user_preferences import (
            FACChatUserPreferences,
        )

        prefs_stub = frappe._dict(
            keyboard_shortcut="Ctrl+Shift+K",
            enable_keyboard_shortcut=0,
            show_suggested_prompts=1,
            hide_widget=0,
            privacy_consent_complete=0,
        )

        with patch(
            "frappe_assistant_core.chat.api.settings.access.is_chat_enabled",
            return_value=True,
        ), patch(
            "frappe_assistant_core.chat.api.settings.access.frappe.get_single",
            side_effect=fake_get_single,
        ), patch(
            "frappe_assistant_core.chat.api.settings.access._is_faco_member",
            return_value=is_member,
        ), patch(
            "frappe_assistant_core.chat.api.settings.access._is_tenant_owner",
            return_value=is_owner,
        ), patch.object(
            FACChatUserPreferences,
            "get_or_create_preferences",
            return_value=prefs_stub,
        ), patch(
            "frappe_assistant_core.chat.quota_cache.get_quota_snapshot",
            return_value={},
        ):
            yield

    def test_member_without_assistant_role_has_access(self):
        """The reported bug: a registered member with a NON-assistant Frappe
        role (e.g. Purchase Manager) must still have FACO access."""
        email = self._make_user("gate_member@example.com", roles=["Purchase Manager"])
        frappe.set_user(email)
        from frappe_assistant_core.chat.api.settings.access import can_use_faco

        try:
            with self._reach_membership_check(is_member=True):
                result = can_use_faco()
        finally:
            frappe.set_user("Administrator")

        self.assertTrue(result.get("can_use"), f"member should have access, got {result}")
        self.assertEqual(result.get("status"), "ready")

    def test_non_member_non_admin_is_blocked(self):
        email = self._make_user("gate_outsider@example.com", roles=["Purchase Manager"])
        frappe.set_user(email)
        from frappe_assistant_core.chat.api.settings.access import can_use_faco

        try:
            with self._reach_membership_check(is_member=False):
                result = can_use_faco()
        finally:
            frappe.set_user("Administrator")

        self.assertFalse(result.get("can_use"))
        self.assertEqual(result.get("status"), "no_role")

    def test_system_manager_without_membership_denied(self):
        """USE FACO follows membership, not Frappe role: a System Manager who is
        NOT a member cannot chat until seated (the admin USE-bypass is gone)."""
        email = self._make_user("gate_admin@example.com", roles=["System Manager"])
        frappe.set_user(email)
        from frappe_assistant_core.chat.api.settings.access import can_use_faco

        try:
            with self._reach_membership_check(is_member=False):
                result = can_use_faco()
        finally:
            frappe.set_user("Administrator")

        self.assertFalse(result.get("can_use"), f"non-member admin must be denied, got {result}")
        self.assertEqual(result.get("status"), "no_role")

    # ------------------------------------------------------------------
    # show_widget visibility gate (widget hidden for non-member non-admins;
    # System Manager / Administrator always see the launcher).
    # can_use semantics are unchanged — these assert ONLY on show_widget.
    # ------------------------------------------------------------------

    def test_non_member_non_admin_widget_hidden(self):
        """A non-member without an admin role gets no widget at all."""
        email = self._make_user("gate_hide@example.com", roles=["Purchase Manager"])
        frappe.set_user(email)
        from frappe_assistant_core.chat.api.settings.access import can_use_faco

        try:
            with self._reach_membership_check(is_member=False):
                result = can_use_faco()
        finally:
            frappe.set_user("Administrator")

        self.assertFalse(result.get("show_widget"), f"non-member non-admin must be hidden, got {result}")
        self.assertFalse(result.get("can_use"))
        self.assertEqual(result.get("status"), "no_role")

    def test_system_manager_non_member_widget_shown(self):
        """A System Manager who is NOT a member still SEES the widget (bypass),
        even though can_use stays False (no seat = no chat)."""
        email = self._make_user("gate_sm@example.com", roles=["System Manager"])
        frappe.set_user(email)
        from frappe_assistant_core.chat.api.settings.access import can_use_faco

        try:
            with self._reach_membership_check(is_member=False):
                result = can_use_faco()
        finally:
            frappe.set_user("Administrator")

        self.assertTrue(result.get("show_widget"), f"admin must see widget, got {result}")
        self.assertFalse(result.get("can_use"), "non-member admin has no seat -> no chat")

    def test_administrator_non_member_widget_shown(self):
        """The Administrator account always sees the widget, membership aside."""
        from frappe_assistant_core.chat.api.settings.access import can_use_faco

        # Runs as Administrator (setUp default); is_member=False.
        with self._reach_membership_check(is_member=False):
            result = can_use_faco()

        self.assertTrue(result.get("show_widget"), f"Administrator must see widget, got {result}")

    def test_member_widget_shown(self):
        """A seated member sees the widget (unchanged behavior)."""
        email = self._make_user("gate_seat@example.com", roles=["Purchase Manager"])
        frappe.set_user(email)
        from frappe_assistant_core.chat.api.settings.access import can_use_faco

        try:
            with self._reach_membership_check(is_member=True):
                result = can_use_faco()
        finally:
            frappe.set_user("Administrator")

        self.assertTrue(result.get("show_widget"), f"member must see widget, got {result}")
        self.assertTrue(result.get("can_use"))
        self.assertEqual(result.get("status"), "ready")

    # ------------------------------------------------------------------
    # enable_browser_diagnostics: the browser recorder's kill switch reads
    # this field BEFORE the show_widget decision, so it must reach a user
    # whose launcher never renders (chat off, non-member) — not just the
    # ones who make it to load_widget_settings().
    # ------------------------------------------------------------------

    def test_chat_module_disabled_reports_diagnostics_false(self):
        """enable_fac_chat off reports diagnostics disabled outright,
        regardless of the per-feature flag — no assistant exists to consume
        the buffers on a site with chat off, so recording is pure cost."""
        from frappe_assistant_core.chat.api.settings.access import can_use_faco

        with patch(
            "frappe_assistant_core.chat.api.settings.access.is_chat_enabled",
            return_value=False,
        ):
            result = can_use_faco()

        self.assertFalse(result.get("show_widget"))
        self.assertIs(result.get("enable_browser_diagnostics"), False, f"got {result}")

    def test_non_member_widget_hidden_still_carries_diagnostics_flag(self):
        """A non-member whose launcher never renders (show_widget=False) must
        still carry the real tenant diagnostics setting — this is the only
        way the recorder's kill switch reaches a browser that never gets the
        widget at all."""
        email = self._make_user("gate_diag_off@example.com", roles=["Purchase Manager"])
        frappe.set_user(email)
        from frappe_assistant_core.chat.api.settings.access import can_use_faco

        class _DiagOffSettingsStub(_SettingsStub):
            enable_browser_diagnostics = False

        real_get_single = frappe.get_single

        def fake_get_single(doctype):
            if doctype == "FAC Chat Settings":
                return _DiagOffSettingsStub()
            return real_get_single(doctype)

        try:
            with patch(
                "frappe_assistant_core.chat.api.settings.access.is_chat_enabled",
                return_value=True,
            ), patch(
                "frappe_assistant_core.chat.api.settings.access.frappe.get_single",
                side_effect=fake_get_single,
            ), patch(
                "frappe_assistant_core.chat.api.settings.access._is_faco_member",
                return_value=False,
            ), patch(
                "frappe_assistant_core.chat.api.settings.access._is_tenant_owner",
                return_value=False,
            ):
                result = can_use_faco()
        finally:
            frappe.set_user("Administrator")

        self.assertFalse(result.get("show_widget"), f"non-member non-admin must be hidden, got {result}")
        self.assertIs(
            result.get("enable_browser_diagnostics"),
            False,
            f"diagnostics flag must reach a user whose widget never renders, got {result}",
        )

    def test_member_reports_diagnostics_true_by_default(self):
        """A registered tenant with the flag unset (getattr default) reports
        diagnostics enabled — the fail-open default."""
        email = self._make_user("gate_diag_on@example.com", roles=["Purchase Manager"])
        frappe.set_user(email)
        from frappe_assistant_core.chat.api.settings.access import can_use_faco

        try:
            with self._reach_membership_check(is_member=True):
                result = can_use_faco()
        finally:
            frappe.set_user("Administrator")

        self.assertIs(result.get("enable_browser_diagnostics"), True, f"got {result}")

    def test_diagnostics_true_against_the_real_fac_chat_settings_single(self):
        """Regression test for the Single-default trap.

        Every test in this file, including the one directly above, stubs out
        frappe.get_single — so none of them could have caught the real bug:
        FAC Chat Settings is a pre-existing Single, and Frappe only applies a
        field's declared `default` when a document is *created*. A Check
        field added to an already-live Single reads 0 (cint(None)) on every
        upgraded site regardless of its JSON default. This test goes through
        the real Single record instead of a stub.
        """
        from frappe_assistant_core.chat.api.settings.access import can_use_faco

        # Force the earliest return that still carries enable_browser_diagnostics,
        # so this test never reaches AR network calls further down the function.
        frappe.db.set_single_value("FAC Chat Settings", "registration_status", "Not Registered")

        with patch(
            "frappe_assistant_core.chat.api.settings.access.is_chat_enabled",
            return_value=True,
        ):
            result = can_use_faco()

        self.assertEqual(result.get("status"), "not_registered")
        self.assertIs(
            result.get("enable_browser_diagnostics"),
            True,
            f"real FAC Chat Settings single must resolve the Check field's declared default, got {result}",
        )

    def test_exception_branch_omits_the_diagnostics_key_entirely(self):
        """An internal error must not return enable_browser_diagnostics=True.

        The field's ABSENCE is what tells widget.js the value is an inferred
        fail-open default (skip persisting it), not a real answer from the
        server. Returning a literal True here — even though True is the
        correct in-memory value for this tab — would make the client persist
        "on" over a genuine, earlier persisted "off" the very next time this
        branch fires. Same defect class fixed in widget.js's own fail-open
        writer, one layer up."""
        from frappe_assistant_core.chat.api.settings.access import can_use_faco

        with patch(
            "frappe_assistant_core.chat.api.settings.access.is_chat_enabled",
            return_value=True,
        ), patch(
            "frappe_assistant_core.chat.api.settings.access.frappe.get_single",
            side_effect=RuntimeError("boom"),
        ):
            result = can_use_faco()

        self.assertEqual(result.get("status"), "error")
        self.assertNotIn("enable_browser_diagnostics", result, f"got {result}")

    # ------------------------------------------------------------------
    # Tenant owner without a seat: must be offered the Connect flow (ready +
    # needs_user_setup), NOT the "ask your admin" AccessDenied (no_role), so the
    # owner can self-provision the very first time.
    # ------------------------------------------------------------------

    def test_owner_without_seat_gets_setup_not_no_role(self):
        email = self._make_user("gate_owner@example.com", roles=["System Manager"])
        frappe.set_user(email)
        from frappe_assistant_core.chat.api.settings.access import can_use_faco

        try:
            with self._reach_membership_check(is_member=False, is_owner=True):
                result = can_use_faco()
        finally:
            frappe.set_user("Administrator")

        self.assertEqual(result.get("status"), "ready", f"owner should get ready, got {result}")
        self.assertTrue(result.get("needs_user_setup"), f"owner should be offered setup, got {result}")
        self.assertTrue(result.get("show_widget"))
        self.assertFalse(result.get("can_use"), "no seat yet -> cannot chat until connected")

    def test_non_member_non_owner_stays_no_role(self):
        """A non-member who is NOT the owner is still sent to AccessDenied."""
        email = self._make_user("gate_notowner@example.com", roles=["System Manager"])
        frappe.set_user(email)
        from frappe_assistant_core.chat.api.settings.access import can_use_faco

        try:
            with self._reach_membership_check(is_member=False, is_owner=False):
                result = can_use_faco()
        finally:
            frappe.set_user("Administrator")

        self.assertEqual(result.get("status"), "no_role")

    # ------------------------------------------------------------------
    # _is_faco_member: authoritative AR Tenant User status (the real helper)
    #
    # Membership is now decided by AR's get_user_auth_status (the same source
    # Settings > Users manages), NOT a local OAuth token proxy. We mock the
    # FAC Cloud client so these tests exercise the helper's status mapping,
    # caching, and fail-open/fail-closed branches against the real contract.
    # ------------------------------------------------------------------

    @contextmanager
    def _patch_client(self, status_result):
        """Patch get_fac_cloud_client so get_user_auth_status returns status_result.

        Yields the mock client so callers can assert call counts (caching).
        Patches the symbol on its source module since access._is_faco_member
        imports it lazily (``from ...fac_cloud_client import get_fac_cloud_client``).
        """
        from unittest.mock import MagicMock

        client = MagicMock()
        client.get_user_auth_status.return_value = status_result
        with patch(
            "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client",
            return_value=client,
        ):
            yield client

    def _clear_member_cache(self, *emails):
        for email in emails:
            frappe.cache.delete_value(f"faco_member:{email}")

    def test_member_active_status_grants(self):
        from frappe_assistant_core.chat.api.settings.access import _is_faco_member

        self._clear_member_cache("active@example.com")
        with self._patch_client({"user_exists": True, "user_status": "Active"}):
            self.assertTrue(_is_faco_member("active@example.com"))

    def test_member_pending_status_grants(self):
        """Pending members are admitted so an invited user can enter and
        auto-activate on first use."""
        from frappe_assistant_core.chat.api.settings.access import _is_faco_member

        self._clear_member_cache("pending@example.com")
        with self._patch_client({"user_exists": True, "user_status": "Pending"}):
            self.assertTrue(_is_faco_member("pending@example.com"))

    def test_membership_queries_ar_by_email_not_username(self):
        """AR keys AR Tenant Users by email. _is_faco_member must query AR with
        the user's email, not the raw Frappe username — otherwise the
        Administrator owner (username 'Administrator', seat keyed by email) is
        wrongly reported as a non-member and blocked from chat (the 417
        'Cannot use FACO' bug)."""
        from frappe_assistant_core.chat.api.auth import _ar_user_id
        from frappe_assistant_core.chat.api.settings.access import _is_faco_member

        admin_email = _ar_user_id("Administrator")
        self.assertTrue(admin_email and "@" in admin_email)
        self._clear_member_cache("Administrator", admin_email)

        with self._patch_client({"user_exists": True, "user_status": "Active"}) as client:
            self.assertTrue(_is_faco_member("Administrator"))
            # AR must have been asked about the EMAIL, not "Administrator".
            self.assertEqual(client.get_user_auth_status.call_args.kwargs.get("user_id"), admin_email)

    def test_suspended_status_denied(self):
        """A definitive AR 'Suspended' is a real no — fail CLOSED."""
        from frappe_assistant_core.chat.api.settings.access import _is_faco_member

        self._clear_member_cache("susp@example.com")
        with self._patch_client({"user_exists": True, "user_status": "Suspended"}):
            self.assertFalse(_is_faco_member("susp@example.com"))

    def test_nonexistent_user_denied(self):
        """AR says user_exists False (a definitive answer) — fail CLOSED."""
        from frappe_assistant_core.chat.api.settings.access import _is_faco_member

        self._clear_member_cache("ghost@example.com")
        with self._patch_client({"user_exists": False, "user_status": None}):
            self.assertFalse(_is_faco_member("ghost@example.com"))

    def test_ar_unreachable_fails_open(self):
        """Transient AR failure (_ar_unreachable) must NOT lock out a
        logged-in member — fail OPEN, trust the session."""
        from frappe_assistant_core.chat.api.settings.access import _is_faco_member

        self._clear_member_cache("blip@example.com")
        with self._patch_client({"_ar_unreachable": True, "error": "boom"}):
            self.assertTrue(_is_faco_member("blip@example.com"))

    def test_no_client_denies(self):
        """An unregistered site (no cloud client) is not a member — the
        registration gate runs first, but the helper stays self-consistent."""
        from frappe_assistant_core.chat.api.settings.access import _is_faco_member

        self._clear_member_cache("noclient@example.com")
        with patch(
            "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client",
            return_value=None,
        ):
            self.assertFalse(_is_faco_member("noclient@example.com"))

    def test_result_cached_60s(self):
        """A second call within the TTL must NOT re-hit the cloud client."""
        from frappe_assistant_core.chat.api.settings.access import _is_faco_member

        self._clear_member_cache("cached@example.com")
        with self._patch_client({"user_exists": True, "user_status": "Active"}) as client:
            self.assertTrue(_is_faco_member("cached@example.com"))
            self.assertTrue(_is_faco_member("cached@example.com"))
            self.assertEqual(
                client.get_user_auth_status.call_count,
                1,
                "second call within TTL should be served from cache",
            )

    def _cache_ttl_for(self, status_result):
        """Call _is_faco_member with a patched client + spied set_value, and
        return the expires_in_sec the membership result was cached with."""
        from unittest.mock import MagicMock
        from unittest.mock import patch as _patch

        from frappe_assistant_core.chat.api.settings import access

        client = MagicMock()
        client.get_user_auth_status.return_value = status_result
        self._clear_member_cache("ttl@example.com")
        with _patch(
            "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client",
            return_value=client,
        ), _patch.object(access.frappe.cache, "set_value", wraps=access.frappe.cache.set_value) as spy:
            access._is_faco_member("ttl@example.com")
        # the membership write is the set_value carrying our cache key
        for call in spy.call_args_list:
            if call.args and call.args[0] == "faco_member:ttl@example.com":
                return call.kwargs.get("expires_in_sec")
        return None

    def test_definitive_answer_cached_full_ttl(self):
        """A real AR yes/no is trusted for the full 60s."""
        self.assertEqual(self._cache_ttl_for({"user_exists": True, "user_status": "Active"}), 60)

    def test_failopen_grant_cached_briefly(self):
        """A fail-OPEN grant (transient blip) is cached only briefly so a real
        suspension takes effect quickly once AR is reachable again."""
        self.assertEqual(self._cache_ttl_for({"_ar_unreachable": True}), 5)

    def test_unexpected_exception_fails_open(self):
        """An unexpected error in the membership check must FAIL OPEN (grant) so
        an internal bug can't silently lock out logged-in members — and must log.

        This is distinct from the deterministic ``_ar_unreachable`` path: here the
        client itself raises, hitting the ``except Exception`` fail-open branch.
        """
        from unittest.mock import MagicMock

        from frappe_assistant_core.chat.api.settings.access import _is_faco_member

        self._clear_member_cache("boom@example.com")
        client = MagicMock()
        client.get_user_auth_status.side_effect = RuntimeError("boom")
        with patch(
            "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client",
            return_value=client,
        ), patch("frappe_assistant_core.chat.api.settings.access.frappe.log_error") as mock_log:
            result = _is_faco_member("boom@example.com")

        self.assertTrue(result, "unexpected exception must fail OPEN (grant), not lock out")
        self.assertTrue(mock_log.called, "the failure must be logged")
