# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Did you know tips, What's new stories and the Your FAC ring: the site's half.

AR sends the words (tip/story notifications, the powers list); the site keeps each user's
three Settings → Home switches and their discovery state, and adds ready questions to the
invite. Samples only show on a site that asks for them in site_config.
"""

import json
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import frappe

from frappe_assistant_core.chat.api import home
from frappe_assistant_core.chat.api.settings.access import _discovery_preferences
from frappe_assistant_core.chat.doctype.fac_chat_user_preferences.fac_chat_user_preferences import (
    FACChatUserPreferences,
)
from frappe_assistant_core.chat.home_preferences import load_home_preferences, parse_discovery_state
from frappe_assistant_core.tests.base_test import BaseAssistantTest

PREFS = "FAC Chat User Preferences"


class TestDiscoveryState(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.user = frappe.session.user
        FACChatUserPreferences.get_or_create_preferences(self.user)
        frappe.db.set_value(PREFS, self.user, "discovery_state", None, update_modified=False)

    def test_parse_keeps_only_known_keys_ids_and_dates(self):
        state = parse_discovery_state(
            {
                "seen": ["agents", 3, "", "agents"],
                "used": ["x" * 141, "pages"],
                "coach_done": "yes",
                "tip": {"id": "tip-1", "date": "12/11/2026"},
                "tip_hidden_on": "2026-11-12",
                "first_day": "2026-11-01",
                "anything": "else",
            }
        )
        self.assertEqual(state["seen"], ["agents"])
        self.assertEqual(state["used"], ["pages"])
        self.assertFalse(state["coach_done"])
        self.assertIsNone(state["tip"])
        self.assertEqual(state["tip_hidden_on"], "2026-11-12")
        self.assertNotIn("anything", state)
        self.assertEqual(parse_discovery_state("not json")["seen"], [])

    def test_parse_caps_every_list(self):
        state = parse_discovery_state({"seen": [f"id-{i}" for i in range(80)]})
        self.assertEqual(len(state["seen"]), 50)
        self.assertEqual(state["seen"][-1], "id-79")

    def test_save_stores_the_clean_state_on_the_users_preferences(self):
        saved = home.save_discovery_state(
            json.dumps({"seen": ["agents"], "stories_seen": ["story-1"], "coach_done": True, "junk": 1})
        )
        self.assertEqual(saved["seen"], ["agents"])
        stored = json.loads(frappe.db.get_value(PREFS, self.user, "discovery_state"))
        self.assertEqual(stored, saved)
        self.assertNotIn("junk", stored)

    def test_save_keeps_the_cached_needs_you_cards(self):
        # Saved on most clicks; a full doc save would run on_update and drop the Needs you cache each time.
        cached = {"computed_at": 1, "payload": {"items": []}}
        frappe.cache.hset(home.HOME_SIGNALS_CACHE_KEY, self.user, cached)
        self.addCleanup(frappe.cache.hdel, home.HOME_SIGNALS_CACHE_KEY, self.user)
        home.save_discovery_state({"seen": ["pages"]})
        self.assertEqual(frappe.cache.hget(home.HOME_SIGNALS_CACHE_KEY, self.user), cached)


class TestDiscoverySwitches(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.user = frappe.session.user
        self.addCleanup(frappe.cache.hdel, home.HOME_SIGNALS_CACHE_KEY, self.user)
        home.update_home_preferences(show_tips=True, show_whats_new=True, show_progress=True)

    def test_switches_are_on_by_default_without_a_preferences_row(self):
        prefs = load_home_preferences("nobody-has-this-user@example.com")
        self.assertTrue(prefs["show_tips"])
        self.assertTrue(prefs["show_whats_new"])
        self.assertTrue(prefs["show_progress"])

    def test_each_switch_saves_on_its_own(self):
        result = home.update_home_preferences(show_whats_new="false")
        self.assertFalse(result["show_whats_new"])
        self.assertTrue(result["show_tips"])
        self.assertTrue(result["show_progress"])
        self.assertFalse(home.get_home_preferences()["show_whats_new"])

    def test_the_page_gets_the_switches_and_the_state_with_its_access_check(self):
        home.update_home_preferences(show_progress=False)
        home.save_discovery_state({"used": ["ask"]})
        # can_use_faco hands this helper the user's own preferences row once the seat checks pass.
        prefs = FACChatUserPreferences.get_or_create_preferences(self.user)
        discovery = _discovery_preferences(prefs)
        self.assertEqual(
            {k: discovery[k] for k in ("show_tips", "show_whats_new", "show_progress")},
            {"show_tips": True, "show_whats_new": True, "show_progress": False},
        )
        self.assertEqual(discovery["state"]["used"], ["ask"])


class TestInviteQuestions(BaseAssistantTest):
    INVITEE = "invitee_questions@example.com"

    def setUp(self):
        super().setUp()
        if not frappe.db.exists("User", self.INVITEE):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": self.INVITEE,
                    "first_name": "Invitee",
                    "send_welcome_email": 0,
                    "roles": [{"role": "Accounts User"}],
                }
            ).insert(ignore_permissions=True)

    def test_three_questions_for_the_users_area_each_opening_fac_with_it_typed(self):
        from frappe_assistant_core.chat.api.prompts import _role_bucket_prompts
        from frappe_assistant_core.chat.api.users import invite_questions

        questions = invite_questions(self.INVITEE)
        expected = [p["description"] for p in _role_bucket_prompts(frappe.get_roles(self.INVITEE))[:3]]
        self.assertEqual([q["question"] for q in questions], expected)
        self.assertIn("Who owes us the most, and since when?", expected)
        for q in questions:
            url = urlparse(q["url"])
            self.assertEqual(url.path, "/copilot/chat")
            self.assertEqual(parse_qs(url.query)["prompt"], [q["question"]])

    def test_invite_bell_says_who_and_the_email_links_the_questions(self):
        from frappe_assistant_core.chat.api.users import _notify_invited_user

        frappe.db.delete("Notification Log", {"for_user": self.INVITEE})
        with patch(
            "frappe.desk.doctype.notification_log.notification_log.enqueue_create_notification"
        ) as send:
            _notify_invited_user(self.INVITEE, "User", "Administrator")
        user, doc = send.call_args.args
        self.assertEqual(user, self.INVITEE)
        self.assertIn("gave you FAC Chat", doc["subject"])
        self.assertIn("/copilot/chat?prompt=", doc["link"])
        self.assertEqual(doc["email_content"].count("<li>"), 3)
        self.assertIn("as Member", doc["email_content"])


class TestDiscoverySamples(BaseAssistantTest):
    def test_samples_only_on_a_site_that_asks_for_them(self):
        from frappe_assistant_core.chat.api import init as init_mod
        from frappe_assistant_core.chat.api import notifications

        caps = {"features": {}}
        with patch.dict(frappe.conf, {"fac_discovery_samples": 0}):
            self.assertEqual(notifications._response([], "u", degraded=False)["notifications"], [])
            self.assertNotIn("discovery", init_mod._with_sample_discovery(caps))
        with patch.dict(frappe.conf, {"fac_discovery_samples": 1}):
            styles = [
                n["display_style"] for n in notifications._response([], "u", degraded=False)["notifications"]
            ]
            self.assertEqual(styles, ["tip", "story"])
            self.assertEqual(init_mod._with_sample_discovery(caps)["discovery"]["powers"][0]["id"], "setup")

    def test_ar_powers_win_over_the_samples(self):
        from frappe_assistant_core.chat.api import init as init_mod

        caps = {"discovery": {"powers": [{"id": "ask", "label": "From AR"}]}}
        with patch.dict(frappe.conf, {"fac_discovery_samples": 1}):
            self.assertEqual(init_mod._with_sample_discovery(caps), caps)
