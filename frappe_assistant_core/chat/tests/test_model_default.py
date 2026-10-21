# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""A turn sent with no model choice runs on the user's saved model; an explicit choice wins."""

from concurrent.futures import Future
from unittest.mock import patch

from frappe_assistant_core.chat.api.chat import messages
from frappe_assistant_core.tests.base_test import BaseAssistantTest

GATE = "frappe_assistant_core.chat.api.settings.can_use_faco"
MODEL_ARG = 8  # submit(fn, session_id, prompt, message, context, msg, user, site, model, ...)


class TestTurnModelDefault(BaseAssistantTest):
    def _sent_model(self, saved, **kwargs):
        # The saved value is what set_selected_model stores for the user; reading it is the
        # same _saved_model call production makes.
        with (
            patch(GATE, return_value={"can_use": True}),
            patch.object(messages, "_saved_model", return_value=saved),
            patch.object(messages._relay_pool, "submit", return_value=Future()) as submit,
        ):
            messages.start_turn("s-model-default", "hi", **kwargs)
        return submit.call_args.args[MODEL_ARG]

    def test_no_choice_uses_the_saved_model(self):
        for sent in ({}, {"model_id": None}, {"model_id": ""}, {"model_id": "  "}):
            with self.subTest(sent=sent):
                self.assertEqual(self._sent_model("claude-opus-4-1", **sent), "claude-opus-4-1")

    def test_explicit_auto_stays_auto(self):
        self.assertEqual(self._sent_model("claude-opus-4-1", model_id="auto"), "auto")

    def test_explicit_model_wins(self):
        self.assertEqual(self._sent_model("claude-opus-4-1", model_id="gpt-5"), "gpt-5")

    def test_nothing_saved_leaves_the_default_to_ar(self):
        self.assertIsNone(self._sent_model("", model_id=None))
