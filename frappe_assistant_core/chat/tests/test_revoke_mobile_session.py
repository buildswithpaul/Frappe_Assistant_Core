# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Signing out of the FAC mobile app ends its credentials on the server (spec §8.3, F13).

Frappe inserts a new OAuth Bearer Token row on every refresh and never revokes
the previous one, so a refresh token captured before a rotation stays usable
after the app forgets it. ``create_web_session`` also plants a desk ``sid`` in
the app's WebView. ``auth.revoke_mobile_session`` revokes every Active token of
(user, calling client) and ends only the desk sessions minted for that client.
``create_web_session`` also refuses any redirect a browser would read as another
host.

"Refused" is asserted through Frappe's own OAuth validator. An access token that
``validate_bearer_token`` refuses leaves the request as Guest, so
``frappe.auth.validate_auth`` raises AuthenticationError (HTTP 401). A refresh
token that ``validate_refresh_token`` refuses cannot mint a new token: Frappe
v16 raises DoesNotExistError, which the token endpoint answers with HTTP 404,
not RFC 6749 ``invalid_grant``.

Every token, session and user here belongs to throwaway users; Administrator's
rows are never touched.
"""

import json
import re
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import unquote

import frappe
import redis
from frappe.auth import CookieManager
from frappe.oauth import OAuthWebRequestValidator
from frappe.sessions import Session, get_expiry_in_seconds
from frappe.utils import set_request

from frappe_assistant_core.tests.base_test import BaseAssistantTest

REDIRECT = "facomobile://oauth/callback"
REVOKE_PATH = "/api/method/frappe_assistant_core.chat.api.auth.revoke_mobile_session"


def _mint(user: str, client: str) -> SimpleNamespace:
    """An Active token pair, the row Frappe's save_bearer_token writes on sign-in or refresh."""
    token = SimpleNamespace(access=frappe.generate_hash(length=30), refresh=frappe.generate_hash(length=30))
    frappe.get_doc(
        {
            "doctype": "OAuth Bearer Token",
            "client": client,
            "user": user,
            "scopes": "all openid",
            "access_token": token.access,
            "refresh_token": token.refresh,
            "expires_in": 3600,
            "status": "Active",
        }
    ).insert(ignore_permissions=True)
    return token


def _access_accepted(access_token: str) -> bool:
    # Frappe's validator sets request.user on a valid token, so it needs a request-like object, not None.
    return bool(OAuthWebRequestValidator().validate_bearer_token(access_token, ["all"], SimpleNamespace()))


def _refresh_accepted(refresh_token: str) -> bool:
    """False when Frappe refuses the refresh token: v16 raises DoesNotExistError (HTTP 404)."""
    try:
        return bool(OAuthWebRequestValidator().validate_refresh_token(refresh_token, None, SimpleNamespace()))
    except frappe.DoesNotExistError:
        return False


def _session_exists(sid: str) -> bool:
    sessions = frappe.qb.DocType("Sessions")
    return bool(frappe.qb.from_(sessions).select(sessions.sid).where(sessions.sid == sid).run())


def _login_manager(full_name: str) -> type:
    """LoginManager.login_as without on_login hooks: one real Sessions row, plus the
    ``full_name`` cookie Frappe's ``set_user_info`` plants. Never the sid cookie, so a
    served page holds no secret an assertion could print."""

    class _LoginManager:
        def login_as(self, user: str) -> None:
            Session(user=user, full_name=full_name, user_type="System User")
            frappe.local.cookie_manager.set_cookie("full_name", full_name)

    return _LoginManager


def _served(page: str) -> SimpleNamespace:
    """The redirect target and the cookie strings the page's script would apply."""
    redirect = re.search(r"window\.location\.replace\((.*)\);", page)
    cookies = re.findall(r"document\.cookie = (.*);", page)
    return SimpleNamespace(
        redirect=json.loads(redirect.group(1)), cookies=[json.loads(cookie) for cookie in cookies]
    )


def _script_elements(page: str) -> tuple[int, int]:
    lowered = page.lower()
    return lowered.count("<script"), lowered.count("</script")


class TestRevokeMobileSession(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        from frappe_assistant_core.chat.api.auth import _register_mobile_oauth_client

        self.user = self.make_throwaway_user("mobile-revoke")
        self.bystander = self.make_throwaway_user("mobile-bystander")
        suffix = frappe.generate_hash(length=6)
        self.client = _register_mobile_oauth_client(REDIRECT, device_id=f"rv-a-{suffix}").name
        self.other_client = _register_mobile_oauth_client(REDIRECT, device_id=f"rv-b-{suffix}").name

        self.before_refresh = _mint(self.user, self.client)
        self.current = _mint(self.user, self.client)
        self.other_device = _mint(self.user, self.other_client)
        self.bystander_token = _mint(self.bystander, self.client)

        self.addCleanup(setattr, frappe.local, "request", getattr(frappe.local, "request", None))
        self.addCleanup(setattr, frappe.local, "request_ip", getattr(frappe.local, "request_ip", None))
        self.addCleanup(frappe.cache.delete_value, f"fac_mobile_web_sessions:{self.user}")
        frappe.local.request_ip = "127.0.0.1"
        self._present(self.current.access)

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _present(self, access_token: str | None) -> None:
        headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
        set_request(method="POST", path=REVOKE_PATH, headers=headers)
        frappe.set_user(self.user)

    def _start_desk_session(self, user: str | None = None) -> str:
        sid = Session(user=user or self.user, full_name="Revoke Test", user_type="System User").sid
        self.addCleanup(frappe.cache.hdel, "session", sid)
        frappe.set_user(self.user)
        return sid

    def _revoke(self) -> dict:
        from frappe_assistant_core.chat.api.auth import revoke_mobile_session

        return revoke_mobile_session()

    def _open_web_session(self, redirect_to: str | None = None, full_name: str = "Revoke Test") -> str:
        """Run create_web_session for real and return the page it served."""
        from frappe_assistant_core.chat.api import mobile_stream

        self.addCleanup(
            setattr, frappe.local, "cookie_manager", getattr(frappe.local, "cookie_manager", None)
        )
        frappe.local.cookie_manager = CookieManager()
        frappe.form_dict.pop("redirect_to", None)
        if redirect_to is not None:
            frappe.form_dict["redirect_to"] = redirect_to

        with patch("frappe.auth.LoginManager", _login_manager(full_name)):
            response = mobile_stream.create_web_session()
        self.addCleanup(frappe.cache.hdel, "session", frappe.session.sid)
        self.assertEqual(response.status_code, 200)
        return response.get_data(as_text=True)

    def test_every_token_of_the_calling_device_stops_working(self):
        for token in (self.before_refresh, self.current):
            self.assertTrue(_access_accepted(token.access), "premise: Frappe keeps pre-refresh tokens Active")
            self.assertTrue(_refresh_accepted(token.refresh), "premise: a rotated refresh token still works")

        result = self._revoke()

        self.assertEqual(result["revoked_tokens"], 2)
        for token in (self.before_refresh, self.current):
            self.assertFalse(_access_accepted(token.access), "a revoked access token must get a 401")
            self.assertFalse(_refresh_accepted(token.refresh), "a revoked refresh token must be refused")

    def test_other_devices_and_other_users_keep_their_tokens(self):
        self._revoke()

        for token in (self.other_device, self.bystander_token):
            self.assertTrue(_access_accepted(token.access))
            self.assertTrue(_refresh_accepted(token.refresh))

    def test_create_web_session_records_the_session_it_mints(self):
        self._open_web_session()
        sid = frappe.session.sid

        recorded = frappe.cache.hgetall(f"fac_mobile_web_sessions:{self.user}")
        fields = {frappe.safe_decode(key): value for key, value in recorded.items()}
        # Fixed messages only: a failure must never print the sid.
        self.assertTrue(_session_exists(sid), "create_web_session must mint a real desk session")
        self.assertTrue(
            fields == {sid: self.client},
            "create_web_session must record exactly the sid it minted, tagged with its client",
        )

    def test_the_record_outlives_the_session_expiry(self):
        """The TTL lands on the very Redis hash ``hset`` wrote (the site-prefixed key) and
        is twice the session expiry, so a desk session that slides on activity stays recorded."""
        from frappe_assistant_core.chat.api._mobile_sessions import record_web_session

        record_web_session(self.user, "sid-under-test", self.client)

        hash_key = frappe.cache.make_key(f"fac_mobile_web_sessions:{self.user}")
        self.assertTrue(redis.Redis.hexists(frappe.cache, hash_key, "sid-under-test"))
        self.assertGreater(frappe.cache.ttl(hash_key), get_expiry_in_seconds())
        self.assertLessEqual(frappe.cache.ttl(hash_key), 2 * get_expiry_in_seconds())

    def test_create_web_session_serves_no_markup_from_its_inputs(self):
        """A ``</script>`` in the redirect path or in a cookie value (``full_name`` is
        user-editable) must not end the page's script: its value stays intact."""
        hostile = "</script><script>alert(document.cookie)//"
        for redirect_to, full_name in (
            ("/" + hostile, "Revoke Test"),
            ("/ok/path", 'Eve "' + hostile + "; & <b>"),
        ):
            with self.subTest(redirect_to=redirect_to, full_name=full_name):
                page = self._open_web_session(redirect_to, full_name=full_name)

                self.assertEqual(_script_elements(page), (1, 1), "the page must hold exactly one script")
                served = _served(page)
                self.assertEqual(served.redirect, redirect_to)
                name, _sep, value = served.cookies[0].partition("; ")[0].partition("=")
                self.assertEqual(name, "full_name")
                self.assertEqual(unquote(value), full_name, "the desk decodes the cookie to the name")
                self.assertNotRegex(value, r'[;"<>&\s]')

    def test_create_web_session_redirects_only_to_a_same_site_path(self):
        for redirect_to, destination in (
            ("/\\evil.example", "/app"),
            ("/\t/evil.example", "/app"),
            ("/\n/evil.example", "/app"),
            ("/ /evil.example", "/app"),
            ("/\x7f/evil.example", "/app"),
            ("/\xa0/evil.example", "/app"),
            ("//evil.example", "/app"),
            ("https://evil.example", "/app"),
            ("/ok/path", "/ok/path"),
        ):
            with self.subTest(redirect_to=redirect_to):
                page = self._open_web_session(redirect_to)

                self.assertEqual(_served(page).redirect, destination)

    def test_sign_out_ends_only_the_sessions_minted_for_this_device(self):
        from frappe_assistant_core.chat.api._mobile_sessions import record_web_session

        minted_here = self._start_desk_session()
        minted_elsewhere = self._start_desk_session()
        browser = self._start_desk_session()
        record_web_session(self.user, minted_here, self.client)
        record_web_session(self.user, minted_elsewhere, self.other_client)
        self._present(self.current.access)

        result = self._revoke()

        self.assertEqual(result["ended_sessions"], 1)
        self.assertFalse(_session_exists(minted_here))
        self.assertTrue(_session_exists(minted_elsewhere))
        self.assertTrue(_session_exists(browser))

    def test_a_stray_record_never_ends_another_users_session(self):
        """Sign-out re-checks each recorded sid against the Sessions row's user."""
        from frappe_assistant_core.chat.api._mobile_sessions import record_web_session

        bystanders_session = self._start_desk_session(self.bystander)
        record_web_session(self.user, bystanders_session, self.client)
        self._present(self.current.access)

        result = self._revoke()

        self.assertEqual(result["ended_sessions"], 0)
        self.assertTrue(_session_exists(bystanders_session), "another user's session must survive")

    def test_a_cache_outage_still_revokes_the_tokens(self):
        """Ending desk sessions fails open: the durable token revocation must not be lost."""
        from frappe_assistant_core.chat.api.auth import _register_mobile_oauth_client

        for outage in (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
            with self.subTest(outage=outage.__name__):
                device = f"rv-o-{frappe.generate_hash(length=6)}"
                client = _register_mobile_oauth_client(REDIRECT, device_id=device).name
                tokens = (_mint(self.user, client), _mint(self.user, client))
                self._present(tokens[1].access)

                with patch.object(frappe.cache, "hgetall", side_effect=outage):
                    result = self._revoke()

                self.assertEqual(result, {"success": True, "revoked_tokens": 2, "ended_sessions": 0})
                for token in tokens:
                    self.assertFalse(_access_accepted(token.access), "a revoked access token must get a 401")
                    self.assertFalse(
                        _refresh_accepted(token.refresh), "a revoked refresh token must be refused"
                    )
                logged = frappe.get_all(
                    "Error Log", filters={"reference_name": client}, pluck="error", limit=1
                )
                self.assertTrue(logged, "the outage must be logged")
                self.assertFalse(
                    any(t.access in logged[0] or t.refresh in logged[0] for t in tokens),
                    "the log must carry no token",
                )

    def test_a_repeat_call_changes_nothing(self):
        from frappe_assistant_core.chat.api._mobile_sessions import record_web_session

        record_web_session(self.user, self._start_desk_session(), self.client)
        self._present(self.current.access)

        first = self._revoke()
        second = self._revoke()

        self.assertEqual((first["revoked_tokens"], first["ended_sessions"]), (2, 1))
        self.assertEqual(second, {"success": True, "revoked_tokens": 0, "ended_sessions": 0})
        self.assertTrue(_access_accepted(self.other_device.access))

    def test_a_non_mobile_client_is_refused(self):
        integration = frappe.get_doc(
            {
                "doctype": "OAuth Client",
                "app_name": "Revoke Test Integration",
                "scopes": "all openid",
                "redirect_uris": "https://integration.example.com/callback",
                "default_redirect_uri": "https://integration.example.com/callback",
                "grant_type": "Authorization Code",
                "response_type": "Code",
            }
        ).insert(ignore_permissions=True)
        token = _mint(self.user, integration.name)
        self._present(token.access)

        with self.assertRaises(frappe.PermissionError):
            self._revoke()
        self.assertTrue(_access_accepted(token.access))
        self.assertTrue(_access_accepted(self.current.access))

    def test_a_request_without_a_bearer_is_refused(self):
        self._present(None)

        with self.assertRaises(frappe.AuthenticationError):
            self._revoke()
        self.assertTrue(_access_accepted(self.current.access))

    def test_another_users_bearer_is_refused(self):
        self._present(self.bystander_token.access)

        with self.assertRaises(frappe.AuthenticationError):
            self._revoke()
        self.assertTrue(_access_accepted(self.bystander_token.access))
