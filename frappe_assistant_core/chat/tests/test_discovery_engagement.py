# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""The Your FAC ring: the site's half.

FAC ships six powers and uses AR's list when AR sends one; the site keeps each user's
Settings → Home progress switch and their discovery state, and adds ready questions to the invite.
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

    def test_parse_keeps_only_known_keys_and_ids(self):
        state = parse_discovery_state(
            {
                "seen": ["agents", 3, "", "agents"],
                "used": ["x" * 141, "pages"],
                "coach_done": "yes",
                "tip": {"id": "tip-1", "date": "2026-11-12"},
                "tips_dismissed": ["agents-routine-work"],
                "anything": "else",
            }
        )
        self.assertEqual(state["seen"], ["agents"])
        self.assertEqual(state["used"], ["pages"])
        self.assertFalse(state["coach_done"])
        # No Did you know tips any more: what an older build stored for them is dropped.
        for gone in ("tip", "tips_dismissed", "anything"):
            self.assertNotIn(gone, state)
        self.assertEqual(parse_discovery_state("not json")["seen"], [])

    def test_a_closed_guide_stays_closed_on_every_device(self):
        # The guide on a power's page: its close button saves the power id here.
        saved = home.save_discovery_state(json.dumps({"guides_dismissed": ["knowledge", 3, ""]}))
        self.assertEqual(saved["guides_dismissed"], ["knowledge"])
        stored = json.loads(frappe.db.get_value(PREFS, self.user, "discovery_state"))
        self.assertEqual(stored["guides_dismissed"], ["knowledge"])

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

    def test_a_tab_with_older_state_keeps_what_another_tab_saved(self):
        # Two open tabs each post their whole state; the one that saves last knew less.
        home.save_discovery_state({"used": ["ask"], "celebrated": ["ask"], "coach_done": True})
        saved = home.save_discovery_state({"used": ["pages"], "celebrated": ["pages"], "seen": ["agents"]})
        self.assertEqual(saved["used"], ["ask", "pages"])
        self.assertEqual(saved["celebrated"], ["ask", "pages"])
        self.assertEqual(saved["seen"], ["agents"])
        self.assertIs(saved["coach_done"], True)
        self.assertEqual(json.loads(frappe.db.get_value(PREFS, self.user, "discovery_state")), saved)

    def test_save_does_not_load_the_whole_preferences_row(self):
        with patch.object(FACChatUserPreferences, "get_or_create_preferences", autospec=True) as load:
            home.save_discovery_state({"seen": ["pages"]})
        load.assert_not_called()


class TestDiscoverySwitches(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.user = frappe.session.user
        self.addCleanup(frappe.cache.hdel, home.HOME_SIGNALS_CACHE_KEY, self.user)
        home.update_home_preferences(show_progress=True)

    def test_the_switch_is_on_by_default_without_a_preferences_row(self):
        prefs = load_home_preferences("nobody-has-this-user@example.com")
        self.assertTrue(prefs["show_progress"])
        self.assertNotIn("show_tips", prefs)

    def test_the_switch_saves(self):
        result = home.update_home_preferences(show_progress="false")
        self.assertFalse(result["show_progress"])
        self.assertFalse(home.get_home_preferences()["show_progress"])

    def test_the_page_gets_the_switches_and_the_state_with_its_access_check(self):
        home.update_home_preferences(show_progress=False)
        home.save_discovery_state({"used": ["ask"]})
        # can_use_faco hands this helper the user's own preferences row once the seat checks pass.
        prefs = FACChatUserPreferences.get_or_create_preferences(self.user)
        discovery = _discovery_preferences(prefs)
        self.assertEqual(
            {k: v for k, v in discovery.items() if k != "state"},
            {"show_progress": False},
        )
        self.assertEqual(discovery["state"]["used"], ["ask"])

    def test_the_page_can_tell_a_first_load_from_an_empty_state(self):
        # Every user's first load with Your FAC (new, or just upgraded): nothing saved yet.
        prefs = FACChatUserPreferences.get_or_create_preferences(self.user)
        frappe.db.set_value(PREFS, self.user, "discovery_state", None, update_modified=False)
        prefs.reload()
        self.assertIsNone(_discovery_preferences(prefs)["state"])


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


class TestDefaultPowers(BaseAssistantTest):
    def test_every_site_gets_the_six_powers_when_ar_sends_none(self):
        # No site_config switch: a site whose AR has no discovery block still shows the ring.
        from frappe_assistant_core.chat.api import init as init_mod

        powers = init_mod._with_default_discovery({"features": {}})["discovery"]["powers"]
        self.assertEqual(
            [p["id"] for p in powers], ["setup", "ask", "templates", "knowledge", "pages", "agents"]
        )
        self.assertEqual(powers[-1]["try_route"], "/agents?tab=marketplace")

    def test_the_chat_pages_own_capabilities_call_keeps_the_powers(self):
        # ChatView reloads capabilities through get_capabilities after init; without the powers
        # there, the Your FAC ring, its panel and the Unlocked toast all vanished.
        from frappe_assistant_core.chat.api.settings import capabilities

        fetch = patch(
            "frappe_assistant_core.chat.fac_cloud_client.get_capabilities",
            autospec=True,
            return_value={"features": {"billing": True}},
        )
        with fetch:
            result = capabilities.get_capabilities()
        self.assertEqual(result["discovery"]["powers"][0]["id"], "setup")

    def test_ar_unreachable_still_shows_the_ring(self):
        from frappe_assistant_core.chat.api.settings import capabilities

        with patch(
            "frappe_assistant_core.chat.fac_cloud_client.get_capabilities", autospec=True, return_value=None
        ):
            result = capabilities.get_capabilities()
        self.assertTrue(result["discovery"]["progress_enabled"])

    def test_ar_powers_win_over_the_defaults(self):
        from frappe_assistant_core.chat.api import init as init_mod

        caps = {"discovery": {"powers": [{"id": "ask", "label": "From AR"}]}}
        self.assertEqual(init_mod._with_default_discovery(caps), caps)
        off = {"discovery": {"progress_enabled": False, "powers": []}}
        self.assertEqual(init_mod._with_default_discovery(off), off)
